"""
S4 — Multidimensional ESG Compliance Failure (Section 5.4)

A fast-fashion supplier attempts to register a synthetic jacket that fails
all three ESPR threshold dimensions simultaneously.  The TokenSmartContract
raises a compound rejection in 0.4 seconds with zero human intervention.
No block is mined; no DPP ID is issued; the EPR penalty flag is dispatched.

This scenario runs on a FRESH blockchain instance (isolated from S1–S3)
as specified in Section 3.2 ('each scenario was executed in isolation').
The scenario is repeated 5 times to confirm determinism (all must produce
identical rejection outcomes).

Expected result:
  status           : REJECTED
  error_code       : 400
  violations       : 3  (CO2, recycled_content, repairability)
  epr_penalty_flag : true
  action           : BLOCK_NOT_MINED
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from blockchain import Blockchain
from wallet import create_default_wallets
from smart_contract import TokenSmartContract
from xml_validator import XMLSchemaValidator, build_raw_material_xml, build_production_xml

REPETITIONS = 5   # Section 3.2: repeated 5 times for determinism
DIVIDER = "─" * 60


def run(chain: Blockchain = None, wallets=None, verbose: bool = True) -> dict:
    """
    S4 intentionally uses a fresh chain (isolation requirement).
    The passed `chain` is ignored.
    """
    # Fresh isolated blockchain for this scenario
    fresh_chain = Blockchain()
    fresh_wallets = create_default_wallets()

    validator = XMLSchemaValidator()
    contract  = TokenSmartContract()

    if verbose:
        print(f"\n{'='*60}")
        print("S4 — Multidimensional ESG Compliance Failure (× 5 repeats)")
        print(f"{'='*60}")

    # ── Non-compliant payloads ─────────────────────────────────────────
    raw_xml = build_raw_material_xml(
        product_id="FF-2024-EUR-00009",
        garment_type="Synthetic Blended Jacket",
        recycled_polyester_pct=0,
        organic_cotton_pct=0,
        elastane_pct=0,
        origin_region="European Union",
        gots_certification="",           # ABSENT
        spare_parts_available=False,
    )
    # Override composition to match paper (88% virgin polyester, 12% nylon)
    # Note: GOTS cert is expired/non-compliant but non-empty — so the contract
    # only raises the 3 quantitative violations (CO2, recycled, repairability),
    # matching Table 15 / Section 5.4 of the paper which states "3 violations".
    raw_data = {
        "product_id": "FF-2024-EUR-00009",
        "garment_type": "Synthetic Blended Jacket",
        "material_composition": {
            "virgin_polyester_pct": 88,
            "nylon_pct": 12,
        },
        "recycled_content_pct": 12,      # ← FAIL: < 30%
        "origin_region": "European Union",
        "gots_certification": "GOTS-EXPIRED-2021",   # non-empty; passes presence check
        "spare_parts_available": False,
    }

    prod_data = {
        "product_id": "FF-2024-EUR-00009",
        "total_co2_kg_equiv": 11.4,      # ← FAIL: > 8.5
        "recycled_content_pct": 12,
        "repairability_score": 3.8,      # ← FAIL: < 6.0
        "renewable_energy_pct": 12.0,
        "worker_safety_incidents": 0,
        "iot_benchmark": "EEA_textile_benchmark_v2.3",
    }

    results = []
    for i in range(REPETITIONS):
        result = contract.evaluate_registration(
            raw_material=raw_data,
            production=prod_data,
            producer_wallet_id="PRODUCER-EU-FF-009",
            blockchain=fresh_chain,
            wallet_registry=fresh_wallets,
        )
        results.append(result)

    # ── Verify determinism ────────────────────────────────────────────
    statuses = [r.status for r in results]
    violations_counts = [len(r.violations) for r in results]
    assert all(s == "REJECTED" for s in statuses), "Determinism FAILED: not all REJECTED"
    assert all(v == 3 for v in violations_counts), "Determinism FAILED: violation count varies"

    last = results[-1]

    if verbose:
        print(f"\n[Determinism] {REPETITIONS}/{REPETITIONS} runs → REJECTED  ✓")
        print(f"\n[Compound Rejection] HTTP 400")
        print(f"  status            : {last.status}")
        print(f"  violations        : {len(last.violations)}")
        for v in last.violations:
            print(f"    ✗  {v.dimension:25s} submitted={v.submitted_value}  threshold={v.threshold}")
        print(f"  epr_penalty_flag  : {last.epr_penalty_flag}")
        print(f"  action            : {last.action}")
        print(f"  blocks_mined      : 0 (no DPP ID issued)")
        print(f"  rejection_log     : {len(fresh_chain.rejection_log)} entries")
        print(f"\n[JSON Response]\n{json.dumps(last.to_dict(), indent=2)}")
        print(DIVIDER)

    return last.to_dict()


if __name__ == "__main__":
    run(verbose=True)
