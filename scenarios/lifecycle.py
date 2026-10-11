"""
Fresh-state construction for the evaluation scenarios.

Paper Section 3.1 (Testing Environment): each scenario runs on a fresh
blockchain instance to prevent state carry-over. Scenarios S2, S3, S5 and S6 act
on a garment that already exists, so the prerequisite scenarios are replayed
silently on the fresh chain first; only the scenario under test is reported.
"""

from blockchain import Blockchain
from wallet import create_default_wallets

from . import (
    s1_dpp_activation,
    s2_citizen_repair,
    s3_secondhand_resale,
    s4_esg_failure,
    s5_repair_economy,
    s6_equity_access,
)

SCENARIOS = {
    "S1": s1_dpp_activation,
    "S2": s2_citizen_repair,
    "S3": s3_secondhand_resale,
    "S4": s4_esg_failure,
    "S5": s5_repair_economy,
    "S6": s6_equity_access,
}

# Scenarios that must already have run on the garment's chain.
PREREQUISITES = {
    "S1": [],
    "S2": ["S1"],
    "S3": ["S1", "S2"],
    "S4": [],                      # isolated; builds its own chain
    "S5": ["S1", "S2", "S3"],
    "S6": ["S1", "S2", "S3", "S5"],
}


def run_on_fresh_chain(key: str, verbose: bool = False):
    """
    Run scenario `key` on a brand-new chain and wallet registry.

    Returns (result_dict, chain). For S4 the chain is the scenario's own
    isolated instance, which it does not expose, so None is returned.
    """
    if key == "S4":
        return s4_esg_failure.run(chain=None, wallets=None, verbose=verbose), None

    chain = Blockchain()
    wallets = create_default_wallets()
    for prereq in PREREQUISITES[key]:
        SCENARIOS[prereq].run(chain=chain, wallets=wallets, verbose=False)
    return SCENARIOS[key].run(chain=chain, wallets=wallets, verbose=verbose), chain
