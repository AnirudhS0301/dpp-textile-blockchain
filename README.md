# An Autonomous Blockchain-Enabled Digital Product Passport for Textile Circular Economy

**A Socio-Technical Framework for Upstream ESG Validation and Consumer-Driven Circularity in European Cities**

Reference implementation and reproducibility package for the manuscript by
**Anirudh Subramanyam** and **Omid Fatahi Valilai**.

> *Status: manuscript under review. Journal and DOI to be added on acceptance.*

This repository contains the complete Python prototype used to produce the
proof-of-concept results reported in the paper, including all six evaluation
scenarios (S1–S6) and an automated harness that re-checks every reported
scenario value on each run.

---

## Overview

The textile sector's circular transition is blocked by upstream ESG data that is
fragmented, self-reported, and unverifiable across multi-tier supply chains.
This framework addresses that verification gap with a blockchain-enabled Digital
Product Passport aligned to the **Ecodesign for Sustainable Products Regulation
(ESPR, EU 2024/1781)** and the **Circular Cities and Regions Initiative (CCRI)**.

Developed using **Design Science Research (DSR)** methodology, the prototype
implements a custom blockchain engine with multidimensional smart contracts that
enforce ESG thresholds autonomously, without human intermediation.

A custom chain was built rather than using Ethereum or Hyperledger Fabric
specifically to keep the smart-contract logic fully transparent and reproducible
without platform dependencies (Section 3.2).

### Three-layer architecture

| Layer | Component | Files |
|---|---|---|
| **Interface** | RESTful DPP API (Flask) | `api.py` |
| **Logic** | ESG evaluation, token distribution, schema validation | `smart_contract.py`, `xml_validator.py` |
| **Data** | SHA-256 Proof-of-Work chain, RSA-2048 identities | `blockchain.py`, `wallet.py` |

### ESG thresholds (Table 2 — ESPR draft Delegated Act)

The `TokenSmartContract` evaluates four dimensions under **AND logic** — all four
must pass, or the registration is rejected and no block is mined.

| Dimension | Threshold | Direction |
|---|---|---|
| CO₂ intensity | 8.5 kg CO₂e / garment | ≤ |
| Recycled content | 30 % by weight | ≥ |
| Repairability score | 6.0 / 10 | ≥ |
| GOTS certification | must be present | — |

The contract is **stateless between transactions**: past compliant behaviour
cannot offset a current violation.

### Token reward schedule

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
├── xml_validator.py      GS1 Digital Link schema validation + payload builders
├── api.py                Flask REST API
├── main.py               Scenario runner + validation harness
├── requirements.txt
└── scenarios/
    ├── s1_dpp_activation.py    §5.1  New garment purchase & DPP activation
    ├── s2_citizen_repair.py    §5.2  Citizen scans DPP and chooses repair
    ├── s3_secondhand_resale.py §5.3  Secondhand resale via verified DPP
    ├── s4_esg_failure.py       §5.4  Multidimensional ESG compliance failure
    ├── s5_repair_economy.py    §5.5  Repair economy pricing model
    └── s6_equity_access.py     §5.6  Equitable circular access for low-income citizens
```

---

## Requirements

- Python **3.11** (the environment reported in Section 3.2; tested here on 3.14.7)
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

## Reproducing the results

Run the full scenario suite. Every scenario value reported in the paper is
asserted automatically; the process exits `0` only if all checks pass.

```bash
python main.py
```

| Flag | Effect |
|---|---|
| `--quiet` | Suppress per-scenario detail; print summary + validation only |
| `--json` | Emit machine-readable JSON results |
| `--no-check` | Skip the validation harness |

> **Windows note:** console output uses Unicode box-drawing characters. If you
> hit a `UnicodeEncodeError` under the default `cp1252` code page, force UTF-8:
>
> ```bash
> set PYTHONIOENCODING=utf-8 && python main.py
> ```

### Expected output

All 17 assertions pass, in roughly 11 seconds — runtime is dominated by
Proof-of-Work mining at difficulty 4.

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

**Note on the nonce.** Section 3.2 reports an average of 193,847 nonce
iterations for block #4821. Because each block hashes its own wall-clock
timestamp, the nonce is **not** bit-reproducible across runs — only the
difficulty target (four leading zeros) and the resulting order of magnitude are.
The deterministic, reproducible outputs are the ESG decisions, token awards,
prices, and routing outcomes asserted above.

---

## Scenarios

S1 → S2 → S3 → S5 → S6 share a single chain instance, tracking one garment
(`DPP-EU-2024-TXT-00847-A1F9`) across its full lifecycle: manufacture → retail →
repair → resale → second repair → donation. **S4 runs on a fresh, isolated
chain** and is repeated five times to confirm deterministic rejection.

| ID | § | Scenario | Key result |
|---|---|---|---|
| **S1** | 5.1 | Recycled polyester jacket registered by an EU producer | `APPROVED`, 68 tokens (50 + 18 bonus), block #4821 |
| **S2** | 5.2 | Citizen repair — zipper replacement 18 months post-purchase | 25 citizen + 40 enterprise tokens; repairability 7.4 → 8.1 |
| **S3** | 5.3 | Secondhand resale on a DPP-integrated platform | €52.80 sale; **€14.80** sustainability premium (+38.9 %) |
| **S4** | 5.4 | Fast-fashion supplier fails three ESG dimensions at once | `REJECTED`, no block mined, EPR penalty flag raised |
| **S5** | 5.5 | Repair-economy pricing — verified data eliminates *C*ᵣᵢₛₖ | MVRP €58.00 → €43.00 (**−26 %**) |
| **S6** | 5.6 | Textile bank donation, three-tier quality routing | `PREMIUM_RESALE`, 15 donor tokens, **1500×** throughput |

S1 and S4 can be run standalone:

```bash
python scenarios/s1_dpp_activation.py
```

```bash
python scenarios/s4_esg_failure.py
```

S2, S3, S5 and S6 depend on chain state seeded by their predecessors and must be
run through `main.py`.

---

## API

```bash
python api.py
```

The API listens on `http://localhost:5000`. Citizen queries averaged 1.8 s on
the single-node localhost prototype, excluding network latency.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/dpp/register` | Producer DPP registration (ESG evaluation) |
| `GET` | `/api/dpp/<dpp_id>` | Citizen consumer query (read-only ESG snapshot) |
| `GET` | `/api/dpp/repair-data` | Repair enterprise material profile |
| `POST` | `/api/dpp/log-repair` | Enterprise repair log submission |
| `POST` | `/api/dpp/transfer-ownership` | Secondhand ownership transfer |
| `POST` | `/api/dpp/donation-scan` | Textile bank quality routing |
| `GET` | `/api/epr/aggregate` | Local authority EPR data feed |

```bash
curl http://localhost:5000/api/dpp/DPP-EU-2024-TXT-00847-A1F9
```

---

## Scope and limitations

These are **proof-of-concept demonstrations, not empirically validated results**.
The prototype runs on a single node with assumed input parameters; quantitative
outcomes follow from those assumptions and should not be generalised without
independent empirical validation (Section 8).

Specifically:

- **Single-node prototype.** No multi-node consensus, no validator-compromise
  scenarios, no adversarial testing.
- **In-memory state.** The chain and DPP registry are not persisted between runs.
- **Seeded chain.** The chain starts at index 4818 so the primary DPP
  registration lands on block #4821, matching the paper's narrative.
- **Simulated latencies.** Response times attributed to scanning and network
  operations are constants in the scenario scripts, not measured values.
- **The oracle problem.** The framework verifies that data is *consistently
  recorded*, not that it is *true*. A DPP carrying falsified upstream material
  data would generate false confidence.
- **S3 premium** (€14.80) is computed from a single hypothetical transaction
  using an assumed willingness-to-pay of €52.80 against a €38.00 baseline.
  Whether consumers actually pay this premium is unverified.
- **S5 MVRP reduction** (26 %) is a best-case figure assuming DPP data fully
  eliminates the information-gap risk premium *C*ᵣᵢₛₖ.
- **Signatures.** RSA-2048 wallet signing is implemented and exercised, but
  scenario runners invoke the contract directly rather than through signed
  transactions.

---

## Citation

```bibtex
@unpublished{subramanyam_dpp_blockchain,
  title  = {An Autonomous Blockchain-Enabled Digital Product Passport for
            Textile Circular Economy: A Socio-Technical Framework for Upstream
            ESG Validation and Consumer-Driven Circularity in European Cities},
  author = {Subramanyam, Anirudh and Fatahi Valilai, Omid},
  note   = {Manuscript under review},
  year   = {2026}
}
```

**Keywords:** Digital Product Passport; Blockchain; Circular Economy; ESG
Validation; Smart Contracts; Repair Economy; Socioeconomic Equity; Urban
Circularity; Extended Producer Responsibility; Design Science Research

---

## Funding

This work has been supported by the European Union's Horizon Europe programme
through the project **SORT4CIRC** (Intelligent Textile Sorting for enabling
CIRCularity), Grant Agreement No. **101181988**.

The views and opinions expressed are those of the authors only and do not
necessarily reflect those of the European Union or the granting authority.
Neither the European Union nor the granting authority can be held responsible
for them.

---

## License

[Not yet specified — add a `LICENSE` file. Horizon Europe projects generally
expect open licensing of research outputs; MIT or Apache-2.0 are conventional
for reproducibility packages.]
