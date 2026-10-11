"""
S5 — Repair Economy Socioeconomic Pricing Model (Section 4.5)

A social economy repair enterprise queries the DPP Repair API for a garment
with a second fault (seam failure).  Verified material data eliminates the
information-gap risk premium (C_risk), reducing the Minimum Viable Repair Price
(MVRP) by 26%: €58.00 → €43.00.

MVRP = C_labour + C_parts + C_risk
  Traditional (unverified) : €35 + €8 + €15 = €58.00
  DPP-enabled (verified)   : €35 + €8 + €0  = €43.00  (−26%)

This is a best-case computation under the assumption that DPP material data
is accurate and complete (oracle problem acknowledged in Section 6.1).

Expected result:
  mvrp_traditional : 58.0
  mvrp_dpp         : 43.0
  reduction_pct    : 26.0
  viable_vs_resale : True  (€43 < €52.80 resale ceiling)
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from blockchain import Blockchain
from wallet import create_default_wallets
from smart_contract import TokenSmartContract

DPP_ID = "DPP-EU-2024-TXT-00847-A1F9"
DIVIDER = "─" * 60

# Cost parameters (Table 3 / Section 4.5)
C_LABOUR           = 35.00   # 1.5 hrs × €23.33/hr (EU social enterprise rate)
C_PARTS            = 8.00    # EU-certified lining material
C_RISK_TRADITIONAL = 15.00   # Uncertainty premium without DPP (industry benchmark)
C_RISK_DPP         = 0.00    # Eliminated by verified DPP data
RESALE_CEILING     = 52.80   # From S3 — consumer's WTP threshold


def run(chain: Blockchain = None, wallets=None, verbose: bool = True) -> dict:
    if chain is None:
        raise RuntimeError("S5 requires a blockchain pre-seeded by S1–S3.")
    if wallets is None:
        wallets = create_default_wallets()

    contract = TokenSmartContract()

    if verbose:
        print(f"\n{'='*60}")
        print("S5 — Repair Economy Pricing Model: MVRP Reduction")
        print(f"{'='*60}")

    # ── Step 1: Enterprise queries DPP Repair API ─────────────────────
    record = chain.get_dpp(DPP_ID)
    assert record is not None, "DPP not found — run S1–S3 first"

    if verbose:
        print(f"\n[DPP Repair API] GET /api/dpp/repair-data")
        print(f"  material_composition : {record.get('material_composition')}")
        print(f"  spare_parts_available: {record.get('spare_parts_available')}")
        print(f"  disassembly_time_hrs : 1.5  (from S2 repair history)")
        print(f"  epr_credit_eligible  : {record.get('esg_status') == 'COMPLIANT'}")
        print(f"  response_time        : 1.7 seconds (simulated)")

    # ── Step 2: MVRP calculation ───────────────────────────────────────
    mvrp_traditional = C_LABOUR + C_PARTS + C_RISK_TRADITIONAL
    mvrp_dpp         = C_LABOUR + C_PARTS + C_RISK_DPP
    reduction_pct    = round((mvrp_traditional - mvrp_dpp) / mvrp_traditional * 100)  # → 26
    viable_vs_resale = mvrp_dpp < RESALE_CEILING

    if verbose:
        print(f"\n[MVRP] Traditional (unverified):")
        print(f"  C_labour : €{C_LABOUR:.2f}")
        print(f"  C_parts  : €{C_PARTS:.2f}")
        print(f"  C_risk   : €{C_RISK_TRADITIONAL:.2f}  (uncertainty premium)")
        print(f"  MVRP     : €{mvrp_traditional:.2f}  ← marginal vs €{RESALE_CEILING} resale (€{RESALE_CEILING - mvrp_traditional:.2f} gap)")

        print(f"\n[MVRP] DPP-Enabled (verified):")
        print(f"  C_labour : €{C_LABOUR:.2f}")
        print(f"  C_parts  : €{C_PARTS:.2f}")
        print(f"  C_risk   : €{C_RISK_DPP:.2f}  (eliminated by verified data)")
        print(f"  MVRP     : €{mvrp_dpp:.2f}  ← clearly below €{RESALE_CEILING} ceiling (€{RESALE_CEILING - mvrp_dpp:.2f} gap)")
        print(f"\n[Result] Reduction : −{reduction_pct}%  (€{mvrp_traditional:.2f} → €{mvrp_dpp:.2f})")
        print(f"[Result] Viable vs resale : {viable_vs_resale}  (market expanded)")

    # ── Step 3: Log the repair ─────────────────────────────────────────
    repair_data = {
        "repair_type":              "seam_repair",
        "new_repairability_score":  8.3,
        "extended_lifetime_months": 24,
        "repair_co2_offset_kg":     2.8,
        "disassembly_time_hrs":     1.5,
    }

    result = contract.evaluate_repair(
        dpp_id=DPP_ID,
        repair_data=repair_data,
        citizen_wallet_id="CITIZEN-WALLET-EU-8821",
        enterprise_wallet_id="REPAIR-EU-TEXTIL-007",
        blockchain=chain,
        wallet_registry=wallets,
    )

    if verbose:
        print(f"\n[Repair Log] enterprise tokens : {result.metadata.get('enterprise_tokens')} → REPAIR-EU-TEXTIL-007")
        print(f"[Repair Log] block_index       : #{result.block_index}")
        print(DIVIDER)

    return {
        "mvrp_traditional": mvrp_traditional,
        "mvrp_dpp": mvrp_dpp,
        "reduction_pct": reduction_pct,
        "viable_vs_resale": viable_vs_resale,
        "repair_result": result.to_dict(),
        "cost_breakdown": {
            "c_labour": C_LABOUR,
            "c_parts": C_PARTS,
            "c_risk_traditional": C_RISK_TRADITIONAL,
            "c_risk_dpp": C_RISK_DPP,
        },
    }


if __name__ == "__main__":
    print("S5 requires S1–S3's blockchain. Run main.py to execute all scenarios.")
