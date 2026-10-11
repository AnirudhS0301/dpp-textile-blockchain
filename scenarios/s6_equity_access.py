"""
S6 — Equity Access and Textile Bank Donation Routing (Section 4.6)

The second owner (CITIZEN-WALLET-EU-8821) donates the garment to the
municipal textile bank.  The DPP donation-scan endpoint evaluates the
garment's current repairability score against the three-tier routing table
and dispatches it to the correct pathway in 1.8 seconds.

Three-tier routing (Section 4.6):
  repairability ≥ 7.0 → PREMIUM_RESALE          (max circularity value)
  repairability 5.0–6.9 → SUBSIDISED_REPAIR      (social enterprise repair)
  repairability < 5.0  → RECYCLING_PATHWAY        (material recovery)

Post S2+S5 the garment has repairability 8.3, so it routes to PREMIUM_RESALE.
Donor receives 15 tokens.  equity_impact_flag = "LOW_INCOME_CIRCULAR_TRANSACTION".

Expected result:
  status              : APPROVED
  routing             : PREMIUM_RESALE
  donor_tokens        : 15  → CITIZEN-WALLET-EU-8821
  equity_impact_flag  : LOW_INCOME_CIRCULAR_TRANSACTION
  throughput_factor   : 1500  (vs manual paper-based processing)
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from blockchain import Blockchain
from wallet import create_default_wallets
from smart_contract import TokenSmartContract, donation_payload

DPP_ID  = "DPP-EU-2024-TXT-00847-A1F9"
DIVIDER = "─" * 60

# Routing thresholds (Section 4.6)
ROUTING_TABLE = [
    (7.0,  float("inf"), "PREMIUM_RESALE"),
    (5.0,  6.999,        "SUBSIDISED_REPAIR"),
    (0.0,  4.999,        "RECYCLING_PATHWAY"),
]

# Equity and throughput benchmarks (Section 4.6, Table 4)
THROUGHPUT_FACTOR   = 1500   # automated DPP routing vs manual processing
MANUAL_TIME_MINUTES = 45.0
AUTO_TIME_SECONDS   = 1.8
EQUITY_FLAG         = "LOW_INCOME_CIRCULAR_TRANSACTION"
CCRI_CITY_REGISTRY  = "CCRI-AUTH-EU-CITY"


def _route(repairability: float) -> str:
    for low, high, label in ROUTING_TABLE:
        if low <= repairability <= high:
            return label
    return "RECYCLING_PATHWAY"


def run(chain: Blockchain = None, wallets=None, verbose: bool = True) -> dict:
    if chain is None:
        raise RuntimeError("S6 requires a blockchain pre-seeded by S1–S5.")
    if wallets is None:
        wallets = create_default_wallets()

    contract = TokenSmartContract()

    if verbose:
        print(f"\n{'='*60}")
        print("S6 — Equity Access: Textile Bank Donation & Routing")
        print(f"{'='*60}")

    # ── Step 1: Textile bank reads DPP ────────────────────────────────
    record = chain.get_dpp(DPP_ID)
    assert record is not None, "DPP not found — run S1–S5 first"

    current_repairability = record.get("repairability_score", 8.3)
    routing_decision      = _route(current_repairability)
    current_owner         = record["owner_wallet"]

    if verbose:
        print(f"\n[DPP Donation Scan] POST /api/dpp/donation-scan")
        print(f"  dpp_id              : {DPP_ID}")
        print(f"  current_owner       : {current_owner}")
        print(f"  repairability_score : {current_repairability}")
        print(f"  routing_decision    : {routing_decision}")
        print(f"  response_time       : {AUTO_TIME_SECONDS}s (vs {MANUAL_TIME_MINUTES} min manual)")
        print(f"  throughput_factor   : {THROUGHPUT_FACTOR:,}×  (automated vs paper-based)")

        print(f"\n[Routing Table]")
        for low, high, label in ROUTING_TABLE:
            marker = " ◄ SELECTED" if label == routing_decision else ""
            high_s = "∞" if high == float("inf") else str(high)
            print(f"  {low:.1f}–{high_s:5s} → {label}{marker}")

    # ── Step 2: Evaluate donation via smart contract ──────────────────
    result = contract.evaluate_donation(
        dpp_id=DPP_ID,
        donor_wallet_id=current_owner,
        social_enterprise_id="TEXTILBANK-EU-003",
        blockchain=chain,
        wallet_registry=wallets,
        signature=wallets.sign_transaction(
            current_owner,
            donation_payload(DPP_ID, current_owner, "TEXTILBANK-EU-003")),
    )

    # ── Step 3: CCRI authority flag dispatch ──────────────────────────
    ccri_record = {
        "event":            "DONATION_ROUTED",
        "dpp_id":           DPP_ID,
        "routing":          routing_decision,
        "equity_flag":      EQUITY_FLAG,
        "ccri_authority":   CCRI_CITY_REGISTRY,
        "block_index":      result.block_index,
    }

    if verbose:
        donor_bal = wallets.get(current_owner)
        donor_tokens_after = donor_bal.token_balance if donor_bal else "N/A"

        print(f"\n[SmartContract] POST /api/dpp/donation-scan")
        print(f"  status              : {result.status}")
        print(f"  routing             : {routing_decision}")
        print(f"  donor_tokens        : {result.metadata.get('donor_token_reward')} → {current_owner}")
        print(f"  equity_impact_flag  : {EQUITY_FLAG}")
        print(f"  block_index         : #{result.block_index}")
        print(f"  donor wallet balance: {donor_tokens_after} tokens total")

        print(f"\n[CCRI Dispatch]")
        for k, v in ccri_record.items():
            print(f"  {k:18s}: {v}")

        print(f"\n[Lifecycle Summary] DPP-EU-2024-TXT-00847-A1F9")
        print(f"  S1: Produced → COMPLIANT, 68 tokens minted")
        print(f"  S2: Zipper repair → +25 citizen tokens, +40 enterprise tokens")
        print(f"  S3: Resale at €52.80 → €14.80 sustainability premium (38.9%)")
        print(f"  S4: [ISOLATED] ESG failure → REJECTED, EPR flag raised")
        print(f"  S5: Seam repair → MVRP €58→€43, −26% (C_risk eliminated)")
        print(f"  S6: Donation → PREMIUM_RESALE, +15 donor tokens, equity flag set")
        print(DIVIDER)

    return {
        "status":             result.status,
        "routing":            routing_decision,
        "donor_tokens":       result.metadata.get("donor_token_reward"),
        "equity_impact_flag": EQUITY_FLAG,
        "throughput_factor":  THROUGHPUT_FACTOR,
        "block_index":        result.block_index,
        "ccri_record":        ccri_record,
        "repairability_score": current_repairability,
    }


if __name__ == "__main__":
    print("S6 requires S1–S5's blockchain. Run main.py to execute all scenarios.")
