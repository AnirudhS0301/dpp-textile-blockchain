"""
S2 — Citizen Scans DPP and Chooses Repair (Section 4.2)

18 months post-purchase, the garment's zipper fails.  The citizen scans
the GS1 QR code; the DPP API returns the ESG snapshot in 1.2 s.  The
citizen then takes the garment to a registered repair enterprise.  The
enterprise logs the completed repair and the TokenSmartContract issues a
dual token reward autonomously.

Depends on S1 having registered DPP-EU-2024-TXT-00847-A1F9.

Expected result:
  status                   : APPROVED
  citizen_tokens           : 25  → CITIZEN-WALLET-EU-4412
  enterprise_tokens        : 40  → REPAIR-EU-001
  new_repairability_score  : 8.1
  co2_offset_kg            : 4.2
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


def run(chain: Blockchain = None, wallets=None, verbose: bool = True) -> dict:
    if chain is None:
        raise RuntimeError("S2 requires a blockchain instance pre-seeded by S1.")
    if wallets is None:
        wallets = create_default_wallets()

    contract = TokenSmartContract()

    if verbose:
        print(f"\n{'='*60}")
        print("S2 — Citizen Repair: Zipper Replacement")
        print(f"{'='*60}")

    # ── Step 1: Consumer DPP query (simulated) ─────────────────────────
    record = chain.get_dpp(DPP_ID)
    assert record is not None, f"DPP {DPP_ID} not found — run S1 first"

    if verbose:
        print(f"\n[DPP Query] GET /api/dpp/<dpp_id>")
        print(f"  dpp_id             : {DPP_ID}")
        print(f"  repairability_score: {record['repairability_score']}")
        print(f"  spare_parts        : {record['spare_parts_available']}")
        print(f"  esg_status         : {record['esg_status']}")
        print(f"  response_time      : 1.2 seconds (simulated)")

    # ── Step 2: Repair transaction ─────────────────────────────────────
    repair_data = {
        "repair_type":              "zipper_replacement",
        "new_repairability_score":  8.1,
        "extended_lifetime_months": 36,
        "repair_co2_offset_kg":     4.2,
        "disassembly_time_hrs":     1.5,
    }

    result = contract.evaluate_repair(
        dpp_id=DPP_ID,
        repair_data=repair_data,
        citizen_wallet_id="CITIZEN-WALLET-EU-4412",
        enterprise_wallet_id="REPAIR-EU-001",
        blockchain=chain,
        wallet_registry=wallets,
    )

    if verbose:
        print(f"\n[Repair Log] POST /api/dpp/log-repair")
        print(f"  status                  : {result.status}")
        print(f"  citizen_tokens          : {result.metadata.get('citizen_tokens')} → CITIZEN-WALLET-EU-4412")
        print(f"  enterprise_tokens       : {result.metadata.get('enterprise_tokens')} → REPAIR-EU-001")
        print(f"  new_repairability_score : {result.metadata.get('new_repairability_score')}")
        print(f"  co2_offset_kg           : {result.metadata.get('co2_offset_kg')}")
        print(f"  lifetime_extension_mo   : {result.metadata.get('lifetime_extension_months')}")
        print(f"  block_index             : #{result.block_index}")

        citizen_bal    = wallets.get("CITIZEN-WALLET-EU-4412").token_balance
        enterprise_bal = wallets.get("REPAIR-EU-001").token_balance
        print(f"\n[Wallets] CITIZEN-WALLET-EU-4412 : {citizen_bal} tokens")
        print(f"[Wallets] REPAIR-EU-001           : {enterprise_bal} tokens")
        print(DIVIDER)

    return result.to_dict()


if __name__ == "__main__":
    # S2 can't run standalone without S1's chain; print a helpful message
    print("S2 requires S1's blockchain. Run main.py to execute all scenarios in sequence.")
