# Autonomous Blockchain-Enabled Digital Product Passport for the Textile Circular Economy

Reference implementation and reproducibility package for the paper:

> **[PAPER TITLE]**
> [Author names]
> *[Journal name]*, [Year]. DOI: [10.xxxx/xxxxx]

This repository contains the complete simulation code used to produce the
evaluation results reported in the paper, including all six scenarios (S1–S6)
and the automated cross-check against **Table 15**.

---

## Overview

The framework implements a three-layer architecture for a Digital Product
Passport (DPP) system aligned with the EU **Ecodesign for Sustainable Products
Regulation (ESPR)**:

| Layer | Component | Files |
|---|---|---|
| **Interface** | RESTful DPP API (Flask) | `api.py` |
| **Logic** | ESG evaluation & token distribution | `smart_contract.py`, `xml_validator.py` |
| **Ledger** | SHA-256 Proof-of-Work chain, RSA-2048 identities | `blockchain.py`, `wallet.py` |

A `TokenSmartContract` evaluates four ESG dimensions under **AND-gate logic** —
all must pass for a DPP to be issued. Compliant registrations mine a block and
mint tokens; non-compliant ones are rejected without mining a block and raise an
EPR penalty flag.

### ESG thresholds (ESPR Delegated Act — Table 2)

| Dimension | Threshold | Direction |
|---|---|---|
| CO₂ intensity | 8.5 kg CO₂e / garment | ≤ |
| Recycled content | 30 % by weight | ≥ |
| Repairability score | 6.0 / 10 | ≥ |
| GOTS certification | must be present | — |

### Token reward schedule (Section 3.1.3)

| Event | Reward |
|---|---|
| Producer base (compliant registration) | 50 tokens |
| Performance bonus | 6 tokens per dimension above threshold (max 18) |
| Citizen repair | 25 tokens |
| Repair enterprise | 40 tokens |
| Donation | 15 tokens |

---

## Repository structure

```
dpp_blockchain/
├── blockchain.py         SHA-256 PoW chain, DPP registry, rejection log
├── wallet.py             RSA-2048 actor wallets + registry
├── smart_contract.py     ESG evaluation, token distribution, routing logic
├── xml_validator.py      GS1-aligned XML schema validation + payload builders
├── api.py                Flask REST API (7 endpoints)
├── main.py               Scenario runner + Table 15 validation harness
├── requirements.txt
└── scenarios/
    ├── s1_dpp_activation.py    New garment purchase & DPP activation
    ├── s2_citizen_repair.py    Citizen scans DPP, chooses repair
    ├── s3_secondhand_resale.py Second-hand resale with verified DPP
    ├── s4_esg_failure.py       Multidimensional ESG compliance failure
    ├── s5_repair_economy.py    Repair-economy socioeconomic pricing (MVRP)
    └── s6_equity_access.py     Equity access & textile bank routing
```

---

## Requirements

- Python **3.10+** (tested on 3.14.7)
- `flask` ≥ 3.0
- `cryptography` ≥ 42.0

## Installation

```bash
git clone https://github.com/AnirudhS0301/dpp_blockchain.git
```

```bash
cd dpp_blockchain && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
```

On macOS/Linux use `source .venv/bin/activate` instead.

---

## Reproducing the paper results

Run the full scenario suite. Every numerical result in Table 15 is asserted
automatically; the process exits `0` only if all checks pass.

```bash
python main.py
```

| Flag | Effect |
|---|---|
| `--quiet` | Suppress per-scenario detail; print summary + validation only |
| `--json` | Emit machine-readable JSON results |
| `--no-check` | Skip the Table 15 validation harness |

> **Windows note:** the console output uses Unicode box-drawing characters.
> If you see a `UnicodeEncodeError` under the default `cp1252` code page, run
> with UTF-8 forced:
>
> ```bash
> set PYTHONIOENCODING=utf-8 && python main.py
> ```

### Expected output

```
  ✓  S1 status                      PASS
  ✓  S1 tokens                      PASS
  ✓  S1 block                       PASS
  ✓  S1 dpp_id                      PASS
  ✓  S2 citizen_tokens              PASS
  ✓  S2 enterprise_tokens           PASS
  ✓  S3 status                      PASS
  ✓  S3 premium                     PASS
  ✓  S4 status                      PASS
  ✓  S4 violations                  PASS
  ✓  S4 epr_flag                    PASS
  ✓  S5 mvrp_trad                   PASS
  ✓  S5 mvrp_dpp                    PASS
  ✓  S5 reduction                   PASS
  ✓  S6 routing                     PASS
  ✓  S6 donor_tokens                PASS
  ✓  S6 throughput                  PASS

  ALL CHECKS PASSED ✓
```

Typical total runtime is **~11 s** on a single-node localhost, dominated by
Proof-of-Work mining at difficulty 4.

---

## Scenarios

S1 → S2 → S3 → S5 → S6 share a single blockchain instance, tracking one garment
(`DPP-EU-2024-TXT-00847-A1F9`) across its full lifecycle. **S4 runs on a fresh,
isolated chain** and is repeated 5× to confirm deterministic rejection.

| ID | Scenario | Key result |
|---|---|---|
| **S1** | DPP activation — recycled polyester jacket registered by an EU producer | `APPROVED`, 68 tokens (50 + 18 bonus), block #4821 |
| **S2** | Citizen repair — zipper replacement 18 months post-purchase | 25 citizen + 40 enterprise tokens; repairability 7.4 → 8.1 |
| **S3** | Second-hand resale on a DPP-integrated platform | €52.80 sale; €14.80 sustainability premium (+38.9 %) |
| **S4** | Fast-fashion supplier fails 3 ESG dimensions simultaneously | `REJECTED`, HTTP 400, no block mined, EPR flag raised |
| **S5** | Repair-economy pricing — verified data eliminates risk premium | MVRP €58.00 → €43.00 (−26 %) |
| **S6** | Textile bank donation with three-tier quality routing | `PREMIUM_RESALE`, 15 donor tokens, 1500× throughput |

Individual scenarios can be run standalone where they do not depend on prior
chain state:

```bash
python scenarios/s1_dpp_activation.py
```

```bash
python scenarios/s4_esg_failure.py
```

S2, S3, S5 and S6 require the chain seeded by their predecessors and must be run
via `main.py`.

---

## API

Start the development server:

```bash
python api.py
```

The API listens on `http://localhost:5000`.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/dpp/register` | Producer DPP registration (ESG evaluation) |
| `GET` | `/api/dpp/<dpp_id>` | Citizen consumer query (read-only ESG snapshot) |
| `GET` | `/api/dpp/repair-data` | Repair enterprise material profile |
| `POST` | `/api/dpp/log-repair` | Enterprise repair log submission |
| `POST` | `/api/dpp/transfer-ownership` | Second-hand ownership transfer |
| `POST` | `/api/dpp/donation-scan` | Textile bank quality routing |
| `GET` | `/api/epr/aggregate` | Local authority EPR data feed |

Example — query a registered DPP:

```bash
curl http://localhost:5000/api/dpp/DPP-EU-2024-TXT-00847-A1F9
```

---

## Scope and limitations

This is a **single-node simulation** intended to demonstrate and validate the
framework's logic, not a production deployment. Specifically:

- The chain is pre-seeded to begin at index 4818 so the primary DPP registration
  lands on block #4821, matching the paper's narrative.
- Blockchain state and the DPP registry are held **in memory** and are not
  persisted between runs.
- Response times attributed to network and scanning operations are **simulated
  constants**, not measured latencies.
- The MVRP reduction in S5 is a best-case computation assuming DPP material data
  is accurate and complete — the oracle problem is acknowledged in the paper's
  discussion of limitations.
- Wallet signature verification is implemented and exercised, but scenario
  runners invoke the contract directly rather than through signed transactions.

---

## Citation

If you use this code, please cite the paper:

```bibtex
@article{[CITEKEY],
  title   = {[PAPER TITLE]},
  author  = {[Author names]},
  journal = {[Journal name]},
  year    = {[Year]},
  doi     = {[10.xxxx/xxxxx]}
}
```

---

## License

[Specify a license — MIT and Apache-2.0 are common for reproducibility packages.
Add the corresponding `LICENSE` file to the repository root.]
