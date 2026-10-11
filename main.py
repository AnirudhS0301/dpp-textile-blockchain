"""
main.py — DPP Blockchain: End-to-End Scenario Runner

Executes the six evaluation scenarios (S1-S6, Section 4 of the paper), prints a
results summary and cross-checks every reported value against
``data/paper_values.json``.

Usage
-----
  python main.py             # full verbose output + validation
  python main.py --quiet     # summary + validation only
  python main.py --json      # machine-readable JSON on stdout (nothing else)
  python main.py --no-check  # skip the validation harness

The process exits 0 only if every check passes.

Architecture
------------
  S1 -> S2 -> S3 -> S5 -> S6  share one blockchain instance (one garment's lifecycle)
  S4                          uses a fresh, isolated chain
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows consoles default to cp1252, which cannot print the box-drawing
# characters, arrows and euro signs used in the scenario output.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from blockchain import Blockchain
from wallet import create_default_wallets
from scenarios import (
    s1_dpp_activation,
    s2_citizen_repair,
    s3_secondhand_resale,
    s4_esg_failure,
    s5_repair_economy,
    s6_equity_access,
)

PAPER_VALUES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "paper_values.json"
)

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  Digital Product Passports for Circular Textiles             ║
║  Evaluation Scenarios S1–S6                                  ║
╚══════════════════════════════════════════════════════════════╝
"""

SEPARATOR = "═" * 62


def run_all(verbose: bool = True) -> dict:
    """Run S1-S6 and return their results plus chain metadata."""
    shared_chain = Blockchain()
    shared_wallets = create_default_wallets()

    results = {}
    t0_global = time.perf_counter()

    # (key, module, uses the shared chain?)
    plan = [
        ("S1", s1_dpp_activation, True),
        ("S2", s2_citizen_repair, True),
        ("S3", s3_secondhand_resale, True),
        ("S4", s4_esg_failure, False),      # isolated chain
        ("S5", s5_repair_economy, True),
        ("S6", s6_equity_access, True),
    ]
    for key, module, shared in plan:
        t0 = time.perf_counter()
        if shared:
            results[key] = module.run(chain=shared_chain, wallets=shared_wallets, verbose=verbose)
        else:
            results[key] = module.run(chain=None, wallets=None, verbose=verbose)
        results[key]["_elapsed_s"] = round(time.perf_counter() - t0, 3)

    results["_chain"] = {
        "length": len(shared_chain.chain),
        "first_index": shared_chain.chain[0].index,
        "last_index": shared_chain.last_block.index,
        "is_valid": shared_chain.is_valid(),
    }
    results["_total_elapsed_s"] = round(time.perf_counter() - t0_global, 3)
    return results


def print_summary(results: dict) -> None:
    print(f"\n{SEPARATOR}")
    print("RESULTS SUMMARY")
    print(SEPARATOR)

    s1, s2, s3, s4, s5, s6 = (results[k] for k in ("S1", "S2", "S3", "S4", "S5", "S6"))

    rows = [
        ("S1", "DPP Activation",
         f"status={s1.get('status')}  dpp_id={s1.get('dpp_id')}  "
         f"block=#{s1.get('block_index')}  tokens={s1.get('tokens_issued')}"),
        ("S2", "Citizen Repair",
         f"status={s2.get('status')}  citizen={s2.get('citizen_tokens')} tkn  "
         f"enterprise={s2.get('enterprise_tokens')} tkn"),
        ("S3", "Secondhand Resale",
         f"status={s3.get('status')}  price=€{s3.get('payment_eur')}  "
         f"premium=€{s3.get('sustainability_premium_eur')}"),
        ("S4", "ESG Failure (×5)",
         f"status={s4.get('status')}  violations={len(s4.get('violations', []))}  "
         f"epr={s4.get('epr_penalty_flag')}  action={s4.get('action')}"),
        ("S5", "Repair Economy",
         f"MVRP: €{s5.get('mvrp_traditional')} → €{s5.get('mvrp_dpp')}  "
         f"reduction={s5.get('reduction_pct')}%  viable={s5.get('viable_vs_resale')}"),
        ("S6", "Equity / Donation",
         f"routing={s6.get('routing')}  donor={s6.get('donor_tokens')} tkn  "
         f"throughput={s6.get('throughput_factor')}×"),
    ]
    for tag, label, detail in rows:
        print(f"\n  [{tag}] {label}")
        print(f"        {detail}")

    chain = results["_chain"]
    print(f"\n{SEPARATOR}")
    print(f"  Shared chain      : {chain['length']} blocks "
          f"(#{chain['first_index']}–#{chain['last_index']}), valid={chain['is_valid']}")
    print(f"  Total runtime     : {results['_total_elapsed_s']} s")
    print(SEPARATOR)


def load_paper_values() -> dict:
    with open(PAPER_VALUES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def collect_checks(results: dict, expected: dict) -> list:
    """Return [(label, actual, expected)] comparing results against paper values."""
    actual = {
        "S1": {k: results["S1"].get(k) for k in expected["S1"]},
        "S2": {k: results["S2"].get(k) for k in expected["S2"]},
        "S3": {k: results["S3"].get(k) for k in expected["S3"]},
        "S4": {
            "status": results["S4"].get("status"),
            "violation_count": len(results["S4"].get("violations", [])),
            "epr_penalty_flag": results["S4"].get("epr_penalty_flag"),
        },
        "S5": {k: results["S5"].get(k) for k in expected["S5"]},
        "S6": {k: results["S6"].get(k) for k in expected["S6"]},
    }
    return [
        (f"{scenario} {field}", actual[scenario][field], value)
        for scenario in ("S1", "S2", "S3", "S4", "S5", "S6")
        for field, value in expected[scenario].items()
    ]


def validate_results(results: dict, quiet: bool = False) -> bool:
    """Cross-check results against data/paper_values.json; return True if all pass."""
    checks = collect_checks(results, load_paper_values())
    ok = True
    out = (lambda *a, **k: None) if quiet else print

    out(f"\n{SEPARATOR}")
    out("VALIDATION  (cross-check against data/paper_values.json)")
    out(SEPARATOR)
    for label, actual, want in checks:
        passed = actual == want
        ok &= passed
        status = "PASS" if passed else f"FAIL  (expected {want!r}, got {actual!r})"
        out(f"  {'✓' if passed else '✗'}  {label:30s} {status}")
    out(SEPARATOR)
    out(f"\n  {'ALL CHECKS PASSED ✓' if ok else 'SOME CHECKS FAILED ✗'}  ({len(checks)} checks)\n")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="DPP Blockchain Scenario Runner")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-scenario output")
    parser.add_argument("--json", action="store_true", help="Print results as JSON only")
    parser.add_argument("--no-check", action="store_true", help="Skip paper-value validation")
    args = parser.parse_args()

    if args.json:
        # Keep stdout machine-readable: no banner, no scenario chatter.
        results = run_all(verbose=False)
        print(json.dumps(results, indent=2, default=str))
        sys.exit(0 if args.no_check or validate_results(results, quiet=True) else 1)

    print(BANNER)
    results = run_all(verbose=not args.quiet)
    print_summary(results)
    if not args.no_check:
        sys.exit(0 if validate_results(results) else 1)


if __name__ == "__main__":
    main()
