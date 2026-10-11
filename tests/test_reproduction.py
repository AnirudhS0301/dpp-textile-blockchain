"""Regression tests: the code must reproduce the values reported in the paper."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as runner
from blockchain import Blockchain
from smart_contract import TokenSmartContract
from wallet import create_default_wallets, Wallet
from api import create_app


@pytest.fixture(scope="module")
def results():
    return runner.run_all(verbose=False)


def test_all_paper_values_reproduced(results):
    checks = runner.collect_checks(results, runner.load_paper_values())
    failures = [(label, got, want) for label, got, want in checks if got != want]
    assert not failures, failures


def test_shared_chain_valid_and_indexed_from_4818(results):
    assert results["_chain"]["first_index"] == 4818
    assert results["_chain"]["is_valid"]


def test_and_logic_rejects_single_failure():
    chain, wallets = Blockchain(difficulty=1), create_default_wallets()
    raw = {"recycled_content_pct": 72, "gots_certification": "GOTS-X"}
    prod = {"total_co2_kg_equiv": 9.0, "repairability_score": 7.4}   # CO2 too high
    res = TokenSmartContract().evaluate_registration(
        raw, prod, "PRODUCER-WALLET-EU-001", chain, wallets)
    assert res.status == "REJECTED"
    assert [v.dimension for v in res.violations] == ["CO2"]
    assert len(chain.chain) == 3 and len(chain.rejection_log) == 1


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


def test_api_rejects_bad_input():
    client = create_app(Blockchain(difficulty=1), create_default_wallets()).test_client()
    assert client.post("/api/dpp/transfer-ownership", data="not json").status_code == 400
    assert client.post("/api/dpp/transfer-ownership",
                       json={"payment_eur": "abc"}).status_code == 400
    assert client.get("/api/dpp/UNKNOWN").status_code == 404
