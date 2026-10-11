# Digital Product Passports for Circular Textiles

**A Socio-Technical Framework and Prototype Evaluation — reference implementation and reproducibility package**

[![reproduce](https://github.com/AnirudhS0301/dpp_blockchain/actions/workflows/ci.yml/badge.svg)](https://github.com/AnirudhS0301/dpp_blockchain/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

Code accompanying the manuscript by **Anirudh Subramanyam** and **Omid Fatahi Valilai**
(Emerging Technologies in Industrial Engineering group, Constructor University Bremen).

> *Status: manuscript under review. Journal and DOI will be added on acceptance.*

The repository contains the Python prototype behind the proof-of-concept results in the paper:
a custom SHA-256 Proof-of-Work blockchain, RSA-2048 actor wallets, an ESG-enforcing
`TokenSmartContract`, GS1-style XML schema validation, a Flask REST API, and the six
evaluation scenarios (S1–S6). Every scenario value reported in the paper is re-checked
automatically on each run.

## Contents

- [Quick start](#quick-start)
- [What is reproduced](#what-is-reproduced)
- [Repository layout](#repository-layout)
- [Framework summary](#framework-summary)
- [REST API](#rest-api)
- [Scope and limitations](#scope-and-limitations)
- [Differences between code and manuscript](#differences-between-code-and-manuscript)
- [Citation](#citation) · [Funding](#funding) · [License](#license)

## Quick start

Requires Python 3.11 or newer.

```bash
git clone https://github.com/AnirudhS0301/dpp_blockchain.git
cd dpp_blockchain
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python main.py
```

`main.py` runs S1–S6, prints a summary, and exits `0` only if all 17 paper-value checks pass
(about 10 s; runtime is dominated by Proof-of-Work mining at difficulty 4).

| Command | Effect |
|---|---|
| `python main.py --quiet` | Summary and validation only |
| `python main.py --json` | Results as JSON on stdout (nothing else); exit code still reflects validation |
| `python main.py --no-check` | Skip validation |
| `pytest` | Regression tests (paper values, AND-logic, chain tamper detection, signatures, API input handling) |

## What is reproduced

Expected values live in [`data/paper_values.json`](data/paper_values.json) and are asserted by both `main.py` and the tests.

| ID | Paper § | Scenario | Reproduced result |
|---|---|---|---|
| S1 | 4.1 | Recycled-polyester jacket registered by an EU producer | `APPROVED`, 68 tokens (50 + 18 bonus), block #4821, `DPP-EU-2024-TXT-00847-A1F9` |
| S2 | 4.2 | Citizen repair (zipper) | 25 citizen + 40 enterprise tokens; repairability 7.4 → 8.1 |
| S3 | 4.3 | Secondhand resale | €52.80 sale, **€14.80** sustainability premium (+38.9 %) |
| S4 | 4.4 | Fast-fashion supplier fails three dimensions | `REJECTED` ×5 identical runs, no block mined, EPR flag raised |
| S5 | 4.5 | Repair-economy pricing | MVRP €58.00 → €43.00 (**−26 %**) |
| S6 | 4.6 | Textile-bank donation routing | `PREMIUM_RESALE`, 15 donor tokens, 1500× throughput factor |

S1 → S2 → S3 → S5 → S6 share one chain (one garment's lifecycle); S4 runs on a fresh, isolated chain.

**On the nonce.** The paper reports 193,847 nonce iterations for block #4821. Blocks hash their own
wall-clock timestamp, so the nonce is *not* bit-reproducible; only the difficulty target (four leading zeros)
and its order of magnitude are. ESG decisions, token awards, prices and routing are deterministic.

## Repository layout

```
├── main.py               Scenario runner + validation harness
├── blockchain.py         SHA-256 PoW chain, DPP registry, rejection log
├── wallet.py             RSA-2048 actor wallets and registry
├── smart_contract.py     TokenSmartContract: ESG evaluation, tokens, routing
├── xml_validator.py      XML schema validation + payload builders
├── api.py                Flask REST API
├── scenarios/            s1 … s6 scenario scripts
├── data/paper_values.json  Values reported in the paper (validation targets)
├── tests/                pytest suite
├── .github/workflows/    CI: runs main.py and pytest on every push
├── CITATION.cff · LICENSE · requirements*.txt
```

## Framework summary

Three layers: **Data** (`blockchain.py`, `wallet.py`), **Logic** (`smart_contract.py`, `xml_validator.py`),
**Interface** (`api.py`). A custom chain is used instead of Ethereum or Hyperledger Fabric so the contract logic is
transparent and free of platform dependencies (paper §3.1).

**ESG thresholds** (AND logic — all must pass, otherwise no block is mined; contract is stateless between transactions):

| Dimension | Threshold |
|---|---|
| CO₂ intensity | ≤ 8.5 kg CO₂e / garment |
| Recycled content | ≥ 30 % by weight |
| Repairability score | ≥ 6.0 / 10 |
| GOTS certification | certificate ID present |

**Tokens:** producer 50 base + 6 per dimension above threshold (max 18); citizen repair 25; repair enterprise 40; donation 15.

## REST API

```bash
python api.py        # serves on http://127.0.0.1:5000 (localhost only, no authentication)
```

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/dpp/register` | Producer DPP registration |
| `GET` | `/api/dpp/<dpp_id>` | Citizen ESG snapshot (read-only) |
| `GET` | `/api/dpp/repair-data?dpp_id=…` | Repair-enterprise material profile |
| `POST` | `/api/dpp/log-repair` | Repair log + dual token reward |
| `POST` | `/api/dpp/transfer-ownership` | Secondhand ownership transfer |
| `POST` | `/api/dpp/donation-scan` | Textile-bank routing |
| `GET` | `/api/epr/aggregate` | Authority EPR data feed |

## Scope and limitations

These are proof-of-concept demonstrations, not empirically validated results (paper §6.1).

- **Single node, in-memory.** No multi-node consensus, adversarial testing or persistence.
- **Oracle problem.** The framework verifies that data is *consistently recorded*, not that it is *true*.
- **GOTS check is presence-only.** Any non-empty certificate ID passes (S4 uses an expired ID that still passes).
- **Seeded chain.** The chain starts at index 4818 so the primary registration lands on block #4821.
- **Simulated latencies.** Response times quoted in scenario output (1.2 s, 1.7 s, 1.8 s, 3.1 s) are constants, not measurements.
- **Assumed economics.** The €14.80 premium (S3) and −26 % MVRP (S5, best case with `C_risk` = 0) follow from assumed inputs.
- **Signatures.** Wallets can sign and verify, but scenario runners call the contract directly rather than through signed transactions.
- **API.** Development server only; bound to localhost, no authentication.

## Differences between code and manuscript

Listed so reviewers are not surprised:

1. §3.1 states every scenario ran on a fresh chain and S1–S3 five times each; here S1–S3, S5, S6 share one chain and only S4 is repeated (×5).
2. §3.1 describes endpoints `GET /dpp/{id}`, `POST /repair/{id}`, `GET /epr/aggregate`; the implementation uses the `/api/…` routes above.
3. §3.1 says every DPP write requires a verified signature; see *Signatures* above.
4. S6 Listing 6 quotes repairability 7.4 and 18.4 kg CO₂ avoided; the code's lifecycle yields 8.3 and 7.0 kg. Both route to `PREMIUM_RESALE`.
5. The paper describes a five-block chain (4818–4823); the shared chain here has 8 blocks (#4818–#4825).

## Citation

See [`CITATION.cff`](CITATION.cff). Until publication:

```bibtex
@unpublished{subramanyam_dpp_textiles,
  title  = {Digital Product Passports for Circular Textiles: A Socio-Technical
            Framework and Prototype Evaluation},
  author = {Subramanyam, Anirudh and Fatahi Valilai, Omid},
  note   = {Manuscript under review},
  year   = {2026}
}
```

Correspondence: Omid Fatahi Valilai (OFatahiValilai@Constructor.University); code questions: Anirudh Subramanyam (asubramany@Constructor.University).

## Funding

Supported by the European Union's Horizon Europe programme through the project **SORT4CIRC**
(Intelligent Textile Sorting for enabling CIRCularity), Grant Agreement No. 101181988. The views and opinions
expressed are those of the authors only and do not necessarily reflect those of the European Union or the granting
authority. Neither the European Union nor the granting authority can be held responsible for them.

## License

[MIT](LICENSE).
