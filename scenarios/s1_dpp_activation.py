"""
S1 — New Garment Purchase and DPP Activation (Section 5.1)

A European textile producer registers a Recycled Polyester Jacket on the
DPP blockchain.  The TokenSmartContract evaluates all three ESPR ESG
thresholds simultaneously; on approval it mines block #4821, issues
68 tokens (50 base + 18 bonus), and assigns DPP ID DPP-EU-2024-TXT-00847-A1F9.

Expected result:
  status          : APPROVED
  tokens_issued   : 68
  dpp_id          : DPP-EU-2024-TXT-00847-A1F9
  block_index     : 4821
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from blockchain import Blockchain
from wallet import create_default_wallets
from smart_contract import TokenSmartContract
from xml_validator import XMLSchemaValidator, build_raw_material_xml, build_production_xml

DIVIDER = "─" * 60


def run(chain: Blockchain = None, wallets=None, verbose: bool = True) -> dict:
    """
    Execute Scenario S1 and return the ContractResult as a dict.

    Parameters
    ----------
    chain   : Blockchain  — pass a shared instance for cross-scenario continuity
    wallets : WalletRegistry
    verbose : bool        — print formatted output
    """
    if chain is None:
        chain = Blockchain()
    if wallets is None:
        wallets = create_default_wallets()

    validator = XMLSchemaValidator()
    contract  = TokenSmartContract()

    if verbose:
        print(f"\n{'='*60}")
        print("S1 — DPP Activation: Recycled Polyester Jacket")
        print(f"{'='*60}")

    # ── Step 1: Build XML payloads ─────────────────────────────────────
    raw_xml = build_raw_material_xml(
        product_id="TXT-2024-EUR-00847",
        garment_type="Recycled Polyester Jacket",
        recycled_polyester_pct=72,
        organic_cotton_pct=20,
        elastane_pct=8,
        origin_region="European Union",
        gots_certification="GOTS-2024-EU-7821",
        spare_parts_available=True,
    )

    prod_xml = build_production_xml(
        product_id="TXT-2024-EUR-00847",
        total_co2_kg_equiv=6.82,
        recycled_content_pct=72,
        repairability_score=7.4,
        renewable_energy_pct=84.6,
        worker_safety_incidents=0,
        iot_benchmark="EEA_textile_benchmark_v2.3",
    )

    # ── Step 2: Schema validation ──────────────────────────────────────
    rv = validator.validate_raw_material(raw_xml)
    pv = validator.validate_production(prod_xml)

    if verbose:
        print(f"\n[Schema] RawMaterialRecord : {'✓ VALID' if rv.is_valid else '✗ INVALID'}")
        print(f"[Schema] ProductionRecord  : {'✓ VALID' if pv.is_valid else '✗ INVALID'}")

    assert rv.is_valid, f"RawMaterialRecord schema error: {rv.errors}"
    assert pv.is_valid, f"ProductionRecord schema error: {pv.errors}"

    # ── Step 3: TokenSmartContract evaluation ─────────────────────────
    result = contract.evaluate_registration(
        raw_material=rv.parsed_data,
        production=pv.parsed_data,
        producer_wallet_id="PRODUCER-WALLET-EU-001",
        blockchain=chain,
        wallet_registry=wallets,
    )

    if verbose:
        print(f"\n[TokenSmartContract] Status  : {result.status}")
        print(f"[TokenSmartContract] DPP ID  : {result.dpp_id}")
        print(f"[TokenSmartContract] Block   : #{result.block_index}")
        print(f"[TokenSmartContract] Hash    : {result.block_hash[:24]}...")
        print(f"[TokenSmartContract] Nonce   : {chain.last_block.nonce:,}")
        print(f"\n[Tokens] Base   : 50")
        print(f"[Tokens] Bonus  : {result.performance_bonus}  (6 × 3 dimensions)")
        print(f"[Tokens] Total  : {result.tokens_issued} → PRODUCER-WALLET-EU-001")
        print(f"\n[Wallet] Producer balance : {wallets.get('PRODUCER-WALLET-EU-001').token_balance} tokens")

        print(f"\n[Token Record]\n{json.dumps(result.to_dict(), indent=2)}")

    # ── Step 4: Initial retail purchase (producer → citizen) ──────────
    # S1 is titled "New Garment Purchase and DPP Activation" — the retail
    # handoff transfers DPP ownership to the first buyer.
    dpp_rec = chain.get_dpp(result.dpp_id)
    if dpp_rec:
        dpp_rec["owner_wallet"] = "CITIZEN-WALLET-EU-4412"
        dpp_rec["lifecycle_stage"] = "RETAIL_SOLD"
        chain.update_dpp(result.dpp_id, dpp_rec)

    if verbose:
        print(f"\n[Retail Transfer] PRODUCER-WALLET-EU-001 → CITIZEN-WALLET-EU-4412")
        print(DIVIDER)

    return result.to_dict()


if __name__ == "__main__":
    run()
