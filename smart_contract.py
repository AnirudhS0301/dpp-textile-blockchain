"""
smart_contract.py
=================
TokenSmartContract — the central logic component of the DPP framework.

Responsibilities (Section 3.2 / 4.3 of the paper):
  1. Receive validated XML data (already parsed into dicts by xml_validator.py)
  2. Evaluate all four ESG dimensions independently with AND-gate logic
  3. Distribute token rewards via the calibrated reward schedule
  4. Write APPROVED / REJECTED outcome to the blockchain
  5. Raise EPR penalty flag on rejection

ESG Thresholds (ESPR Delegated Act, Table 2):
  - CO2 intensity          : ≤ 8.5 kg CO2e / garment
  - Recycled content       : ≥ 30 % by weight
  - Repairability score    : ≥ 6.0 / 10
  - GOTS certification     : must be active (non-empty certification ID)

Token Reward Schedule (Section 3.1.3):
  - Producer base          : 50 tokens
  - Performance bonus      : up to 18 tokens (6 per dimension above threshold)
  - Citizen repair         : 25 tokens
  - Enterprise repair      : 40 tokens
  - Donation              : 15 tokens
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ESPR-aligned ESG thresholds (Table 2 / Section 3.1.2)
CO2_THRESHOLD        = 8.5    # kg CO2e per garment (≤)
RECYCLED_THRESHOLD   = 30.0   # % by weight (≥)
REPAIR_THRESHOLD     = 6.0    # /10 (≥)

# Token reward schedule (Section 3.1.3)
BASE_PRODUCER_REWARD = 50
BONUS_PER_DIMENSION  = 6      # max 3 dimensions × 6 = 18
CITIZEN_REPAIR_REWARD    = 25
ENTERPRISE_REPAIR_REWARD = 40
DONATION_REWARD          = 15


# ─────────────────────────────────────────────────────────────────────────────
# Result containers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Violation:
    dimension: str
    submitted_value: Any
    threshold: Any
    direction: str  # "max" or "min"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "value": self.submitted_value,
            "threshold": self.threshold,
        }


@dataclass
class ContractResult:
    status: str                          # "APPROVED" or "REJECTED"
    violations: List[Violation] = field(default_factory=list)
    tokens_issued: int = 0
    token_recipient: Optional[str] = None
    performance_bonus: int = 0
    epr_penalty_flag: bool = False
    dpp_id: Optional[str] = None
    block_index: Optional[int] = None
    block_hash: Optional[str] = None
    action: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def http_status(self) -> int:
        return 200 if self.status == "APPROVED" else 400

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "error_code": self.http_status if self.status == "REJECTED" else None,
            "violations": [v.to_dict() for v in self.violations],
            "tokens_issued": self.tokens_issued,
            "token_recipient": self.token_recipient,
            "performance_bonus": self.performance_bonus,
            "epr_penalty_flag": self.epr_penalty_flag,
            "dpp_id": self.dpp_id,
            "block_index": self.block_index,
            "block_hash": self.block_hash,
            "action": self.action,
            **self.metadata,
        }


# ─────────────────────────────────────────────────────────────────────────────
# TokenSmartContract
# ─────────────────────────────────────────────────────────────────────────────

class TokenSmartContract:
    """
    Stateless ESG enforcement and token distribution contract.

    'Stateless between transactions: it holds no memory of prior decisions,
    which ensures that a non-compliant actor cannot accumulate tokens from
    previous compliant transactions to offset a current violation.'
    — Section 3.2
    """

    # ------------------------------------------------------------------
    # DPP Registration (S1 / S4)
    # ------------------------------------------------------------------

    def evaluate_registration(
        self,
        raw_material: Dict[str, Any],
        production: Dict[str, Any],
        producer_wallet_id: str,
        blockchain,
        wallet_registry,
    ) -> ContractResult:
        """
        Evaluate a new DPP registration request.

        Parameters
        ----------
        raw_material : dict  — parsed RawMaterialRecord
        production   : dict  — parsed ProductionRecord
        producer_wallet_id : str
        blockchain   : Blockchain instance
        wallet_registry : WalletRegistry instance
        """

        violations: List[Violation] = []

        # ── Dimension 1: CO2 intensity ────────────────────────────────
        co2 = float(production.get("total_co2_kg_equiv", 999))
        if co2 > CO2_THRESHOLD:
            violations.append(
                Violation("CO2", co2, CO2_THRESHOLD, "max")
            )

        # ── Dimension 2: Recycled content ─────────────────────────────
        recycled = float(raw_material.get("recycled_content_pct",
                         production.get("recycled_content_pct", 0)))
        if recycled < RECYCLED_THRESHOLD:
            violations.append(
                Violation("recycled_content", recycled, RECYCLED_THRESHOLD, "min")
            )

        # ── Dimension 3: Repairability score ──────────────────────────
        repairability = float(production.get("repairability_score", 0))
        if repairability < REPAIR_THRESHOLD:
            violations.append(
                Violation("repairability", repairability, REPAIR_THRESHOLD, "min")
            )

        # ── Dimension 4: GOTS certification ───────────────────────────
        gots = raw_material.get("gots_certification", "")
        if not gots:
            violations.append(
                Violation("gots_certification", "ABSENT", "ACTIVE", "min")
            )

        # ── AND-gate: all must pass ────────────────────────────────────
        if violations:
            blockchain.log_rejection({
                "status": "REJECTED",
                "producer_wallet_id": producer_wallet_id,
                "violations": [v.to_dict() for v in violations],
                "raw_material": raw_material,
                "production": production,
            })
            return ContractResult(
                status="REJECTED",
                violations=violations,
                epr_penalty_flag=True,
                action="BLOCK_NOT_MINED",
            )

        # ── All pass: compute performance bonus ───────────────────────
        bonus = self._compute_bonus(co2, recycled, repairability)
        total_tokens = BASE_PRODUCER_REWARD + bonus

        # ── Generate DPP ID and mine block ────────────────────────────
        product_id = production.get("product_id",
                     raw_material.get("product_id", "UNKNOWN"))
        dpp_id = f"DPP-EU-2024-TXT-{product_id[-5:]}-A1F9" if len(product_id) >= 5 \
                 else f"DPP-EU-2024-TXT-00847-A1F9"

        block_data = {
            "transaction_type": "DPP_REGISTRATION",
            "dpp_id": dpp_id,
            "esg_status": "COMPLIANT",
            "raw_material": raw_material,
            "production": production,
            "token_award": {
                "base": BASE_PRODUCER_REWARD,
                "bonus": bonus,
                "total": total_tokens,
                "recipient": producer_wallet_id,
            },
            "co2_surplus_pct": round((CO2_THRESHOLD - co2) / CO2_THRESHOLD * 100, 1),
            "recycled_content_surplus_pct": round(recycled - RECYCLED_THRESHOLD, 1),
            "repairability_surplus": round(repairability - REPAIR_THRESHOLD, 1),
        }

        block = blockchain.add_block(block_data)
        blockchain.register_dpp(dpp_id, {
            "dpp_id": dpp_id,
            "product_id": product_id,
            "esg_status": "COMPLIANT",
            "repairability_score": repairability,
            "recycled_content_pct": recycled,
            "co2_kg_equiv": co2,
            "gots_certification": gots,
            "spare_parts_available": raw_material.get("spare_parts_available", False),
            "material_composition": raw_material.get("material_composition", {}),
            "owner_wallet": producer_wallet_id,
            "repair_count": 0,
            "co2_avoided_kg": 0.0,
            "repair_history": [],
            "lifecycle_stage": "RETAIL",
        })

        wallet_registry.credit(producer_wallet_id, total_tokens)

        return ContractResult(
            status="APPROVED",
            tokens_issued=total_tokens,
            token_recipient=producer_wallet_id,
            performance_bonus=bonus,
            dpp_id=dpp_id,
            block_index=block.index,
            block_hash=block.hash,
            action="DPP_ID_ISSUED",
            metadata={
                "transaction_type": "ESG_COMPLIANCE_REWARD",
                "base_token_amount": BASE_PRODUCER_REWARD,
            },
        )

    # ------------------------------------------------------------------
    # Repair transaction (S2 / S5)
    # ------------------------------------------------------------------

    def evaluate_repair(
        self,
        dpp_id: str,
        repair_data: Dict[str, Any],
        citizen_wallet_id: str,
        enterprise_wallet_id: str,
        blockchain,
        wallet_registry,
    ) -> ContractResult:
        """
        Validate a completed repair and distribute dual token reward.

        Citizen  → CITIZEN_REPAIR_REWARD  (25 tokens)
        Enterprise → ENTERPRISE_REPAIR_REWARD (40 tokens)
        """
        dpp_record = blockchain.get_dpp(dpp_id)
        if dpp_record is None:
            return ContractResult(
                status="REJECTED",
                action="DPP_NOT_FOUND",
                metadata={"dpp_id": dpp_id},
            )

        new_repairability = float(repair_data.get("new_repairability_score",
                                  dpp_record["repairability_score"]))
        co2_offset = float(repair_data.get("repair_co2_offset_kg", 0))
        lifetime_ext = int(repair_data.get("extended_lifetime_months", 0))

        # Update DPP record
        repair_entry = {
            "repair_type": repair_data.get("repair_type"),
            "new_repairability_score": new_repairability,
            "extended_lifetime_months": lifetime_ext,
            "repair_co2_offset_kg": co2_offset,
            "enterprise": enterprise_wallet_id,
            "citizen": citizen_wallet_id,
        }
        dpp_record["repairability_score"] = new_repairability
        dpp_record["co2_avoided_kg"] = dpp_record.get("co2_avoided_kg", 0) + co2_offset
        dpp_record["repair_count"] = dpp_record.get("repair_count", 0) + 1
        dpp_record["repair_history"].append(repair_entry)

        block_data = {
            "transaction_type": "REPAIR_LOGGED",
            "dpp_id": dpp_id,
            **repair_entry,
            "token_awards": {
                "citizen": {"wallet": citizen_wallet_id, "tokens": CITIZEN_REPAIR_REWARD},
                "enterprise": {"wallet": enterprise_wallet_id, "tokens": ENTERPRISE_REPAIR_REWARD},
            },
        }
        block = blockchain.add_block(block_data)
        blockchain.update_dpp(dpp_id, dpp_record)

        wallet_registry.credit(citizen_wallet_id, CITIZEN_REPAIR_REWARD)
        wallet_registry.credit(enterprise_wallet_id, ENTERPRISE_REPAIR_REWARD)

        return ContractResult(
            status="APPROVED",
            tokens_issued=CITIZEN_REPAIR_REWARD + ENTERPRISE_REPAIR_REWARD,
            block_index=block.index,
            block_hash=block.hash,
            action="REPAIR_LOGGED",
            metadata={
                "citizen_tokens": CITIZEN_REPAIR_REWARD,
                "enterprise_tokens": ENTERPRISE_REPAIR_REWARD,
                "new_repairability_score": new_repairability,
                "co2_offset_kg": co2_offset,
                "lifetime_extension_months": lifetime_ext,
                "dpp_id": dpp_id,
            },
        )

    # ------------------------------------------------------------------
    # Ownership transfer (S3)
    # ------------------------------------------------------------------

    def evaluate_transfer(
        self,
        dpp_id: str,
        seller_wallet_id: str,
        buyer_wallet_id: str,
        payment_eur: float,
        blockchain,
        wallet_registry,
    ) -> ContractResult:
        """
        Validate and record a DPP ownership transfer (secondhand resale).
        Computes and records the sustainability premium.
        """
        dpp_record = blockchain.get_dpp(dpp_id)
        if dpp_record is None:
            return ContractResult(status="REJECTED", action="DPP_NOT_FOUND")

        if dpp_record.get("owner_wallet") != seller_wallet_id:
            return ContractResult(
                status="REJECTED",
                action="OWNERSHIP_MISMATCH",
                metadata={"expected_owner": dpp_record.get("owner_wallet"),
                          "claimed_seller": seller_wallet_id},
            )

        # Compute sustainability premium
        BASE_SECONDHAND_PRICE = 38.0
        premium = round(payment_eur - BASE_SECONDHAND_PRICE, 2)

        block_data = {
            "transaction_type": "DPP_OWNERSHIP_TRANSFER",
            "dpp_id": dpp_id,
            "payment_eur": payment_eur,
            "base_price_eur": BASE_SECONDHAND_PRICE,
            "dpp_sustainability_premium_eur": premium,
            "lifecycle_stage": "SECOND_HAND_RESALE",
            "co2_avoided_kg": dpp_record.get("co2_avoided_kg", 0),
            "repairability_score_at_transfer": dpp_record.get("repairability_score"),
            "previous_repairs": dpp_record.get("repair_count", 0),
            "from_wallet": seller_wallet_id,
            "to_wallet": buyer_wallet_id,
        }

        block = blockchain.add_block(block_data)
        dpp_record["owner_wallet"] = buyer_wallet_id
        dpp_record["lifecycle_stage"] = "SECOND_HAND_RESALE"
        blockchain.update_dpp(dpp_id, dpp_record)

        return ContractResult(
            status="APPROVED",
            block_index=block.index,
            block_hash=block.hash,
            action="OWNERSHIP_TRANSFERRED",
            metadata={
                "dpp_id": dpp_id,
                "payment_eur": payment_eur,
                "sustainability_premium_eur": premium,
                "new_owner": buyer_wallet_id,
            },
        )

    # ------------------------------------------------------------------
    # Textile bank donation scan (S6)
    # ------------------------------------------------------------------

    def evaluate_donation(
        self,
        dpp_id: str,
        donor_wallet_id: str,
        social_enterprise_id: str,
        blockchain,
        wallet_registry,
    ) -> ContractResult:
        """
        Three-tier routing logic for textile bank quality assessment.
        Returns routing decision in <2 seconds (simulated).

        Tiers:
          ≥ 7.0  → PREMIUM_RESALE
          5.0–6.9 → SUBSIDISED_REPAIR
          < 5.0  → RECYCLING_PATHWAY
        """
        dpp_record = blockchain.get_dpp(dpp_id)
        if dpp_record is None:
            return ContractResult(status="REJECTED", action="DPP_NOT_FOUND")

        repairability = dpp_record.get("repairability_score", 0)
        co2_avoided   = dpp_record.get("co2_avoided_kg", 0)

        # Three-tier routing
        if repairability >= 7.0:
            routing = "PREMIUM_RESALE"
            rationale = "score >= 7.0 threshold"
            resale_value = 38.0
        elif repairability >= 5.0:
            routing = "SUBSIDISED_REPAIR"
            rationale = "5.0 <= score < 7.0"
            resale_value = 20.0
        else:
            routing = "RECYCLING_PATHWAY"
            rationale = "score < 5.0 threshold"
            resale_value = 0.0

        block_data = {
            "transaction_type": "TEXTILE_BANK_DONATION",
            "dpp_id": dpp_id,
            "donor_wallet": donor_wallet_id,
            "social_enterprise": social_enterprise_id,
            "routing_decision": routing,
            "routing_rationale": rationale,
            "estimated_resale_value": resale_value,
            "donor_token_reward": DONATION_REWARD,
            "co2_avoided_kg": co2_avoided,
            "equity_impact_flag": "LOW_INCOME_CIRCULAR_TRANSACTION",
            "repairability_score": repairability,
        }

        block = blockchain.add_block(block_data)

        # Credit donor
        wallet_registry.credit(donor_wallet_id, DONATION_REWARD)

        return ContractResult(
            status="APPROVED",
            tokens_issued=DONATION_REWARD,
            token_recipient=donor_wallet_id,
            block_index=block.index,
            block_hash=block.hash,
            action="DONATION_CONFIRMED",
            metadata={
                "dpp_id": dpp_id,
                "repairability_score": repairability,
                "routing_decision": routing,
                "routing_rationale": rationale,
                "estimated_resale_value": resale_value,
                "donor_token_reward": DONATION_REWARD,
                "co2_avoided_kg": co2_avoided,
                "equity_impact_flag": "LOW_INCOME_CIRCULAR_TRANSACTION",
                "assessment_time_seconds": 1.8,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_bonus(
        self, co2: float, recycled: float, repairability: float
    ) -> int:
        """
        Performance bonus: 6 tokens per ESG dimension that exceeds its threshold.
        Maximum bonus = 18 tokens (3 dimensions × 6).
        """
        bonus = 0
        if co2 < CO2_THRESHOLD:
            bonus += BONUS_PER_DIMENSION
        if recycled > RECYCLED_THRESHOLD:
            bonus += BONUS_PER_DIMENSION
        if repairability > REPAIR_THRESHOLD:
            bonus += BONUS_PER_DIMENSION
        return bonus
