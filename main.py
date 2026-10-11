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
  Paper Section 3.1: every scenario runs on a fresh blockchain instance, S1-S4
  are executed five times each (S4 additionally repeats its rejection five
  times internally) and S5-S6 once. Scenarios that act on an existing garment
  (S2, S3, S5, S6) first replay their prerequisites silently on the fresh chain.
  Repeated runs must agree on every deterministic field (hashes and nonces
  legitimately differ because blocks hash their own timestamp).
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

from scenarios.lifecycle import run_on_fresh_chain

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


REPEATS = {"S1": 5, "S2": 5, "S3": 5, "S4": 5, "S5": 1, "S6": 1}   # Section 3.1


def _stable(value):
    """Drop fields that legitimately vary between runs (block hashes)."""
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items() if k != "block_hash"}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def run_all(verbose: bool = True, repeats: dict = None) -> dict:
    """
    Run S1-S6, each on a fresh chain, repeated per `repeats` (default: paper's
    protocol). Raises AssertionError if repeated runs disagree.
    """
    repeats = repeats or REPEATS
    results = {}
    t0_global = time.perf_counter()

    for key in ("S1", "S2", "S3", "S4", "S5", "S6"):
        t0 = time.perf_counter()
        runs, chain = [], None
        n = repeats[key]
        for i in range(n):
            # Print the scenario narrative once, for the final repetition.
            res, chain = run_on_fresh_chain(key, verbose=verbose and i == n - 1)
            runs.append(res)
        reference = _stable(runs[0])
        deterministic = all(_stable(r) == reference for r in runs[1:])
        assert deterministic, f"{key}: repeated runs disagree"

        results[key] = runs[-1]
        results[key]["_runs"] = n
        results[key]["_deterministic"] = deterministic
        results[key]["_elapsed_s"] = round(time.perf_counter() - t0, 3)
        if key == "S3":
            # Chain after the manufacture -> retail -> repair -> resale lifecycle.
            results["_chain"] = {
                "length": len(chain.chain),
                "first_index": chain.chain[0].index,
                "last_index": chain.last_block.index,
                "is_valid": chain.is_valid(),
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
    print(f"  S1–S3 chain       : {chain['length']} blocks "
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
    parser.add_argument("--single-run", action="store_true",
                        help="Run each scenario once instead of the paper's 5x protocol (faster)")
    parser.add_argument("--no-check", action="store_true", help="Skip paper-value validation")
    args = parser.parse_args()

    repeats = {k: 1 for k in REPEATS} if args.single_run else REPEATS

    if args.json:
        # Keep stdout machine-readable: no banner, no scenario chatter.
        results = run_all(verbose=False, repeats=repeats)
        print(json.dumps(results, indent=2, default=str))
        sys.exit(0 if args.no_check or validate_results(results, quiet=True) else 1)

    print(BANNER)
    results = run_all(verbose=not args.quiet, repeats=repeats)
    print_summary(results)
    if not args.no_check:
        sys.exit(0 if validate_results(results) else 1)


if __name__ == "__main__":
    main()
