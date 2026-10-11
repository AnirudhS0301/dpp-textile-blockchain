"""Regression tests: the code must reproduce the values reported in the paper."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as runner
from api import create_app
from blockchain import Blockchain
from smart_contract import (
    TokenSmartContract, registration_payload, transfer_payload, CO2_AVOIDED_VS_NEW_KG,
)
from wallet import Wallet, create_default_wallets

SINGLE = {k: 1 for k in runner.REPEATS}


@pytest.fixture(scope="module")
def results():
    return runner.run_all(verbose=False, repeats=SINGLE)


def test_all_paper_values_reproduced(results):
    checks = runner.collect_checks(results, runner.load_paper_values())
    failures = [(label, got, want) for label, got, want in checks if got != want]
    assert not failures, failures


def test_lifecycle_chain_matches_paper_indices(results):
    chain = results["_chain"]
    assert (chain["first_index"], chain["last_index"]) == (4818, 4823)   # Section 3.1
    assert chain["is_valid"]


def test_repeat_protocol_matches_paper():
    assert runner.REPEATS == {"S1": 5, "S2": 5, "S3": 5, "S4": 5, "S5": 1, "S6": 1}


def test_co2_avoided_is_paper_reference_value():
    assert CO2_AVOIDED_VS_NEW_KG == 18.4


def _register_payloads():
    raw = {"recycled_content_pct": 72, "gots_certification": "GOTS-X", "product_id": "P-00001"}
    prod = {"total_co2_kg_equiv": 9.0, "repairability_score": 7.4, "product_id": "P-00001"}
    return raw, prod


def test_and_logic_rejects_single_failure():
    chain, wallets = Blockchain(difficulty=1), create_default_wallets()
    raw, prod = _register_payloads()                       # CO2 too high
    wid = "PRODUCER-WALLET-EU-001"
    sig = wallets.sign_transaction(wid, registration_payload(raw, prod, wid))
    res = TokenSmartContract().evaluate_registration(raw, prod, wid, chain, wallets, sig)
    assert res.status == "REJECTED" and res.action == "BLOCK_NOT_MINED"
    assert [v.dimension for v in res.violations] == ["CO2"]
    assert len(chain.chain) == 3 and len(chain.rejection_log) == 1


def test_unsigned_or_forged_transaction_is_rejected():
    chain, wallets = Blockchain(difficulty=1), create_default_wallets()
    raw, prod = _register_payloads()
    prod["total_co2_kg_equiv"] = 6.0                       # compliant
    wid = "PRODUCER-WALLET-EU-001"
    contract = TokenSmartContract()

    unsigned = contract.evaluate_registration(raw, prod, wid, chain, wallets)
    forged_sig = Wallet("X", "PRODUCER").sign(registration_payload(raw, prod, wid))
    forged = contract.evaluate_registration(raw, prod, wid, chain, wallets, forged_sig)
    assert unsigned.action == forged.action == "SIGNATURE_INVALID"
    assert unsigned.http_status == 401 and len(chain.chain) == 3

    good = wallets.sign_transaction(wid, registration_payload(raw, prod, wid))
    assert contract.evaluate_registration(raw, prod, wid, chain, wallets, good).status == "APPROVED"


def test_signature_does_not_cover_altered_payload():
    chain, wallets = Blockchain(difficulty=1), create_default_wallets()
    sig = wallets.sign_transaction("CITIZEN-WALLET-EU-4412",
                                   transfer_payload("D", "CITIZEN-WALLET-EU-4412", "B", 10.0))
    res = TokenSmartContract().evaluate_transfer(
        "D", "CITIZEN-WALLET-EU-4412", "B", 99.0, chain, wallets, sig)   # price tampered
    assert res.action == "SIGNATURE_INVALID"


def test_duplicate_dpp_registration_rejected():
    chain, wallets = Blockchain(difficulty=1), create_default_wallets()
    raw, prod = _register_payloads()
    prod["total_co2_kg_equiv"] = 6.0
    wid = "PRODUCER-WALLET-EU-001"
    sig = wallets.sign_transaction(wid, registration_payload(raw, prod, wid))
    contract = TokenSmartContract()
    assert contract.evaluate_registration(raw, prod, wid, chain, wallets, sig).status == "APPROVED"
    assert contract.evaluate_registration(raw, prod, wid, chain, wallets, sig).action == "DPP_ALREADY_REGISTERED"


def test_tampering_breaks_chain():
    chain = Blockchain(difficulty=1)
    chain.add_block({"x": 1})
    assert chain.is_valid()
    chain.chain[-1].data["x"] = 2
    assert not chain.is_valid()


def test_wallet_signature_roundtrip():
    w = Wallet("PRODUCER-WALLET-EU-001", "PRODUCER")
    sig = w.sign({"a": 1})
    assert w.verify({"a": 1}, sig)
    assert not w.verify({"a": 2}, sig)


def test_api_paper_routes_and_input_handling():
    chain, wallets = Blockchain(difficulty=1), create_default_wallets()
    client = create_app(chain, wallets).test_client()

    assert client.post("/api/dpp/transfer-ownership", data="not json").status_code == 400
    assert client.post("/api/dpp/transfer-ownership", json={"payment_eur": "abc"}).status_code == 400
    assert client.get("/api/dpp/UNKNOWN").status_code == 404
    assert client.get("/dpp/UNKNOWN").status_code == 404                  # Section 3.1 route
    assert client.get("/epr/aggregate").status_code == 200                # Section 3.1 route
    assert client.post("/repair/UNKNOWN", json={}).status_code in (400, 401, 404)

    raw, prod = _register_payloads()
    prod["total_co2_kg_equiv"] = 6.0
    wid = "PRODUCER-WALLET-EU-001"
    body = {"producer_wallet_id": wid, "raw_material": raw, "production": prod}
    assert client.post("/api/dpp/register", json=body).status_code == 401  # unsigned
    body["signature"] = wallets.sign_transaction(wid, registration_payload(raw, prod, wid)).hex()
    assert client.post("/api/dpp/register", json=body).status_code == 200
