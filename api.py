"""
api.py
======
RESTful DPP API (Flask) — Interface Layer of the three-layer architecture.

Endpoints (Section 3.1):
  POST  /api/dpp/register              — Producer DPP registration
  GET   /api/dpp/<dpp_id>              — Citizen consumer query (READ-ONLY)
  GET   /api/dpp/repair-data           — Repair enterprise material profile
  POST  /api/dpp/log-repair            — Enterprise repair log submission
  POST  /api/dpp/transfer-ownership    — Secondhand ownership transfer
  POST  /api/dpp/donation-scan         — Textile bank quality routing
  GET   /api/epr/aggregate             — Local authority EPR data feed

Average API response time: 1.8 seconds on single-node localhost (Section 3.1).
"""

import time
from flask import Flask, request, jsonify

from blockchain import Blockchain
from wallet import WalletRegistry, create_default_wallets
from smart_contract import TokenSmartContract
from xml_validator import XMLSchemaValidator


# ─────────────────────────────────────────────────────────────────────────────
# Application factory
# ─────────────────────────────────────────────────────────────────────────────

def create_app(
    blockchain: Blockchain = None,
    wallet_registry: WalletRegistry = None,
) -> Flask:
    """
    Create and configure the Flask DPP API application.

    Parameters
    ----------
    blockchain      : shared Blockchain instance (created if None)
    wallet_registry : shared WalletRegistry  (created with defaults if None)
    """
    app = Flask(__name__)

    # Shared singletons
    chain    = blockchain      or Blockchain()
    wallets  = wallet_registry or create_default_wallets()
    contract = TokenSmartContract()
    validator = XMLSchemaValidator()

    # ──────────────────────────────────────────────────────────────────
    # POST /api/dpp/register
    # ──────────────────────────────────────────────────────────────────
    @app.route("/api/dpp/register", methods=["POST"])
    def register_dpp():
        """
        Producer submits two XML payloads (RawMaterialRecord + ProductionRecord).
        TokenSmartContract evaluates ESG thresholds and approves or rejects.
        """
        t0 = time.time()
        body = request.get_json(force=True, silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object body required"}), 400

        producer_wallet_id = body.get("producer_wallet_id", "")
        raw_xml = body.get("raw_material_xml")
        prod_xml = body.get("production_xml")

        # Accept dict payloads too (for programmatic use from scenario runners)
        raw_data  = body.get("raw_material")  or {}
        prod_data = body.get("production")    or {}

        # Schema validation
        if raw_xml:
            rv = validator.validate_raw_material(raw_xml)
            if not rv.is_valid:
                return jsonify({"error": rv.errors, "error_code": rv.error_code}), 400
            raw_data = rv.parsed_data
        if prod_xml:
            pv = validator.validate_production(prod_xml)
            if not pv.is_valid:
                return jsonify({"error": pv.errors, "error_code": pv.error_code}), 400
            prod_data = pv.parsed_data

        result = contract.evaluate_registration(
            raw_material=raw_data,
            production=prod_data,
            producer_wallet_id=producer_wallet_id,
            blockchain=chain,
            wallet_registry=wallets,
        )

        response = result.to_dict()
        response["response_time_seconds"] = round(time.time() - t0, 3)
        status = result.http_status
        return jsonify(response), status

    # ──────────────────────────────────────────────────────────────────
    # GET /api/dpp/<dpp_id>  (citizen consumer query, READ-ONLY)
    # ──────────────────────────────────────────────────────────────────
    @app.route("/api/dpp/<dpp_id>", methods=["GET"])
    def get_dpp(dpp_id: str):
        """Return full ESG snapshot for a registered DPP (citizen-facing)."""
        t0 = time.time()
        record = chain.get_dpp(dpp_id)
        if record is None:
            return jsonify({"error": "DPP not found", "dpp_id": dpp_id}), 404

        # Consumer-facing subset (read-only ESG snapshot)
        response = {
            "dpp_id": dpp_id,
            "repairability_score": record.get("repairability_score"),
            "recycled_content_pct": record.get("recycled_content_pct"),
            "co2_kg_equiv": record.get("co2_kg_equiv"),
            "spare_parts_available": record.get("spare_parts_available"),
            "esg_status": record.get("esg_status"),
            "repair_count": record.get("repair_count", 0),
            "co2_avoided_kg": record.get("co2_avoided_kg", 0),
            "lifecycle_stage": record.get("lifecycle_stage"),
            "material_composition": record.get("material_composition"),
            "gots_certification": record.get("gots_certification"),
            "response_time_seconds": round(time.time() - t0, 3),
        }
        return jsonify(response), 200

    # ──────────────────────────────────────────────────────────────────
    # GET /api/dpp/repair-data  (enterprise repair material profile)
    # ──────────────────────────────────────────────────────────────────
    @app.route("/api/dpp/repair-data", methods=["GET"])
    def get_repair_data():
        """Return verified material profile for a repair enterprise."""
        t0 = time.time()
        dpp_id = request.args.get("dpp_id")
        requester_id = request.args.get("requester_id", "")

        if not dpp_id:
            return jsonify({"error": "dpp_id required"}), 400

        record = chain.get_dpp(dpp_id)
        if record is None:
            return jsonify({"error": "DPP not found"}), 404

        # Disassembly time from last repair record if available
        history = record.get("repair_history", [])
        disassembly_time = history[-1].get("disassembly_time_hrs", 1.5) if history else 1.5

        response = {
            "dpp_id": dpp_id,
            "material_composition": record.get("material_composition"),
            "spare_parts_available": record.get("spare_parts_available"),
            "certified_parts": ["YKK_zipper_20cm_EU_certified"],
            "disassembly_time_hrs": disassembly_time,
            "epr_credit_eligible": record.get("esg_status") == "COMPLIANT",
            "repairability_score": record.get("repairability_score"),
            "repair_history": history,
            "status": "REPAIR_READY",
            "response_time_seconds": round(time.time() - t0, 3),
        }
        return jsonify(response), 200

    # ──────────────────────────────────────────────────────────────────
    # POST /api/dpp/log-repair
    # ──────────────────────────────────────────────────────────────────
    @app.route("/api/dpp/log-repair", methods=["POST"])
    def log_repair():
        """Enterprise logs a completed repair. Dual token reward issued."""
        t0 = time.time()
        body = request.get_json(force=True, silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object body required"}), 400

        dpp_id             = body.get("dpp_id")
        citizen_wallet     = body.get("citizen_wallet_id", "")
        enterprise_wallet  = body.get("enterprise_wallet_id", "")
        repair_data        = {
            "repair_type":             body.get("repair_type"),
            "new_repairability_score": body.get("new_repairability_score"),
            "extended_lifetime_months":body.get("extended_lifetime_months", 0),
            "repair_co2_offset_kg":    body.get("repair_co2_offset_kg", 0),
            "disassembly_time_hrs":    body.get("disassembly_time_hrs", 1.5),
        }

        result = contract.evaluate_repair(
            dpp_id=dpp_id,
            repair_data=repair_data,
            citizen_wallet_id=citizen_wallet,
            enterprise_wallet_id=enterprise_wallet,
            blockchain=chain,
            wallet_registry=wallets,
        )

        response = result.to_dict()
        response["response_time_seconds"] = round(time.time() - t0, 3)
        return jsonify(response), result.http_status

    # ──────────────────────────────────────────────────────────────────
    # POST /api/dpp/transfer-ownership
    # ──────────────────────────────────────────────────────────────────
    @app.route("/api/dpp/transfer-ownership", methods=["POST"])
    def transfer_ownership():
        """Secondhand platform initiates DPP ownership transfer."""
        t0 = time.time()
        body = request.get_json(force=True, silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object body required"}), 400

        try:
            payment_eur = float(body.get("payment_eur", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "payment_eur must be numeric"}), 400

        result = contract.evaluate_transfer(
            dpp_id=body.get("dpp_id"),
            seller_wallet_id=body.get("seller_wallet_id", ""),
            buyer_wallet_id=body.get("buyer_wallet_id", ""),
            payment_eur=payment_eur,
            blockchain=chain,
            wallet_registry=wallets,
        )

        response = result.to_dict()
        response["response_time_seconds"] = round(time.time() - t0, 3)
        return jsonify(response), result.http_status

    # ──────────────────────────────────────────────────────────────────
    # POST /api/dpp/donation-scan
    # ──────────────────────────────────────────────────────────────────
    @app.route("/api/dpp/donation-scan", methods=["POST"])
    def donation_scan():
        """Textile bank scans a donated garment for quality routing."""
        t0 = time.time()
        body = request.get_json(force=True, silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON object body required"}), 400

        result = contract.evaluate_donation(
            dpp_id=body.get("dpp_id"),
            donor_wallet_id=body.get("donor_wallet", ""),
            social_enterprise_id=body.get("requester_id", ""),
            blockchain=chain,
            wallet_registry=wallets,
        )

        response = result.to_dict()
        response["assessment_time_seconds"] = 1.8   # simulated (Section 3.1)
        response["response_time_seconds"] = round(time.time() - t0, 3)
        return jsonify(response), result.http_status

    # ──────────────────────────────────────────────────────────────────
    # GET /api/epr/aggregate
    # ──────────────────────────────────────────────────────────────────
    @app.route("/api/epr/aggregate", methods=["GET"])
    def epr_aggregate():
        """
        EPR authority data feed — aggregate ESG performance across all
        registered DPPs for local authority fee calculation (Section 3.1).
        """
        records = {}
        for dpp_id in chain._dpp_registry:
            r = chain.get_dpp(dpp_id)
            records[dpp_id] = {
                "esg_status":          r.get("esg_status"),
                "co2_kg_equiv":        r.get("co2_kg_equiv"),
                "recycled_content_pct":r.get("recycled_content_pct"),
                "repairability_score": r.get("repairability_score"),
                "repair_count":        r.get("repair_count", 0),
                "co2_avoided_kg":      r.get("co2_avoided_kg", 0),
            }

        rejections = len(chain.rejection_log)

        return jsonify({
            "registered_dpps": records,
            "total_registrations": len(records),
            "total_rejections": rejections,
            "chain_length": len(chain.chain),
            "chain_valid": chain.is_valid(),
            "token_balances": wallets.all_balances(),
        }), 200

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Dev server entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()
    print("DPP Blockchain API running on http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
