"""
main.py — DPP Blockchain: End-to-End Scenario Runner

Executes all six evaluation scenarios in sequence and prints a final
results table matching Table 15 of the paper.

Usage
-----
  python main.py           # full verbose output
  python main.py --quiet   # results table only
  python main.py --json    # machine-readable JSON

Architecture
------------
  S1 → S2 → S3 → S5 → S6  share one blockchain instance (cumulative lifecycle)
  S4                         uses a fresh isolated chain (paper Section 3.2)
"""

import sys
import json
import time
import argparse

# ── Module path ───────────────────────────────────────────────────────────────
import os
sys.path.insert(0, os.path.dirname(__file__))

from blockchain import Blockchain
from wallet    import create_default_wallets

# ── Scenario imports ──────────────────────────────────────────────────────────
from scenarios import s1_dpp_activation
from scenarios import s2_citizen_repair
from scenarios import s3_secondhand_resale
from scenarios import s4_esg_failure
from scenarios import s5_repair_economy
from scenarios import s6_equity_access


BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  Autonomous Blockchain-Enabled Digital Product Passport      ║
║  Textile Circular Economy — Evaluation Scenarios S1–S6       ║
╚══════════════════════════════════════════════════════════════╝
"""

SEPARATOR = "═" * 62


def run_all(verbose: bool = True) -> dict:
    print(BANNER)

    # Shared chain + wallets for S1 → S2 → S3 → S5 → S6
    shared_chain   = Blockchain()
    shared_wallets = create_default_wallets()

    results = {}
    t0_global = time.perf_counter()

    # ── S1 ────────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    results["S1"] = s1_dpp_activation.run(chain=shared_chain, wallets=shared_wallets, verbose=verbose)
    results["S1"]["_elapsed_s"] = round(time.perf_counter() - t0, 3)

    # ── S2 ────────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    results["S2"] = s2_citizen_repair.run(chain=shared_chain, wallets=shared_wallets, verbose=verbose)
    results["S2"]["_elapsed_s"] = round(time.perf_counter() - t0, 3)

    # ── S3 ────────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    results["S3"] = s3_secondhand_resale.run(chain=shared_chain, wallets=shared_wallets, verbose=verbose)
    results["S3"]["_elapsed_s"] = round(time.perf_counter() - t0, 3)

    # ── S4  (isolated chain — paper Section 3.2) ──────────────────────────────
    t0 = time.perf_counter()
    results["S4"] = s4_esg_failure.run(chain=None, wallets=None, verbose=verbose)
    results["S4"]["_elapsed_s"] = round(time.perf_counter() - t0, 3)

    # ── S5 ────────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    results["S5"] = s5_repair_economy.run(chain=shared_chain, wallets=shared_wallets, verbose=verbose)
    results["S5"]["_elapsed_s"] = round(time.perf_counter() - t0, 3)

    # ── S6 ────────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    results["S6"] = s6_equity_access.run(chain=shared_chain, wallets=shared_wallets, verbose=verbose)
    results["S6"]["_elapsed_s"] = round(time.perf_counter() - t0, 3)

    results["_total_elapsed_s"] = round(time.perf_counter() - t0_global, 3)
    return results


def print_summary(results: dict) -> None:
    print(f"\n{SEPARATOR}")
    print("RESULTS SUMMARY  (matches Table 15)")
    print(SEPARATOR)

    s1 = results["S1"]
    s2 = results["S2"]
    s3 = results["S3"]
    s4 = results["S4"]
    s5 = results["S5"]
    s6 = results["S6"]

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
         f"status={s4.get('status')}  violations={len(s4.get('violations',[]))}  "
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

    print(f"\n{SEPARATOR}")
    print(f"  Blockchain height : {results['S1'].get('block_index', 4821) + 5} blocks")
    print(f"  Total runtime     : {results['_total_elapsed_s']} s")
    print(SEPARATOR)


def validate_results(results: dict) -> bool:
    """
    Assert that all key numerical results match the paper's Table 15.
    Raises AssertionError with a descriptive message on any mismatch.
    """
    ok = True
    checks = []

    # S1
    s1 = results["S1"]
    checks.append(("S1 status",       s1.get("status"),                  "APPROVED"))
    checks.append(("S1 tokens",        s1.get("tokens_issued"),           68))
    checks.append(("S1 block",         s1.get("block_index"),             4821))
    checks.append(("S1 dpp_id",        s1.get("dpp_id"),                  "DPP-EU-2024-TXT-00847-A1F9"))

    # S2  (metadata is spread into top-level by to_dict())
    checks.append(("S2 citizen_tokens",    results["S2"].get("citizen_tokens"),     25))
    checks.append(("S2 enterprise_tokens", results["S2"].get("enterprise_tokens"),  40))

    # S3  (metadata is spread into top-level by to_dict())
    checks.append(("S3 status",       results["S3"].get("status"),                  "APPROVED"))
    checks.append(("S3 premium",      results["S3"].get("sustainability_premium_eur"), 14.80))

    # S4
    s4 = results["S4"]
    checks.append(("S4 status",        s4.get("status"),                  "REJECTED"))
    checks.append(("S4 violations",    len(s4.get("violations", [])),     3))
    checks.append(("S4 epr_flag",      s4.get("epr_penalty_flag"),        True))

    # S5
    s5 = results["S5"]
    checks.append(("S5 mvrp_trad",     s5.get("mvrp_traditional"),        58.0))
    checks.append(("S5 mvrp_dpp",      s5.get("mvrp_dpp"),                43.0))
    checks.append(("S5 reduction",     s5.get("reduction_pct"),           26.0))

    # S6
    s6 = results["S6"]
    checks.append(("S6 routing",       s6.get("routing"),                 "PREMIUM_RESALE"))
    checks.append(("S6 donor_tokens",  s6.get("donor_tokens"),            15))
    checks.append(("S6 throughput",    s6.get("throughput_factor"),       1500))

    print(f"\n{SEPARATOR}")
    print("VALIDATION  (paper Table 15 cross-check)")
    print(SEPARATOR)

    for label, actual, expected in checks:
        passed = actual == expected
        mark   = "✓" if passed else "✗"
        status = "PASS" if passed else f"FAIL  (expected {expected!r}, got {actual!r})"
        print(f"  {mark}  {label:30s} {status}")
        if not passed:
            ok = False

    print(SEPARATOR)
    overall = "ALL CHECKS PASSED ✓" if ok else "SOME CHECKS FAILED ✗"
    print(f"\n  {overall}\n")
    return ok


def main():
    parser = argparse.ArgumentParser(description="DPP Blockchain Scenario Runner")
    parser.add_argument("--quiet",    action="store_true", help="Suppress per-scenario output")
    parser.add_argument("--json",     action="store_true", help="Dump raw JSON results")
    parser.add_argument("--no-check", action="store_true", help="Skip paper-value validation")
    args = parser.parse_args()

    verbose = not args.quiet

    results = run_all(verbose=verbose)

    print_summary(results)

    if not args.no_check:
        passed = validate_results(results)
        sys.exit(0 if passed else 1)

    if args.json:
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
