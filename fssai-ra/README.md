# FSSAI-RA — Fail-Secure Sovereign AI Reference Architecture

[![Tests](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml/badge.svg)](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-0B7261.svg)](../LICENSE)
[![Release v1.0.0](https://img.shields.io/badge/release-v1.0.0-4C566A.svg)](https://github.com/genaiworks/fssai-ra/tree/v1.0.0)

> **A model may propose an action. It cannot manufacture the authority to execute it.**

An **extensible, runnable reference platform** for specifying and testing the
authority boundaries of agentic AI. It ships a dependency-free teaching mode and
a distributed reference deployment built with FastAPI, PostgreSQL, Redis, Apache
Kafka, PySpark, Apache Iceberg, S3-compatible storage, a local model through
Ollama, and a React operator console. A low-side gateway and a working
unidirectional transport model the seam a certified one-way data diode occupies.

**Companion paper:** *Trust by Construction: A Testable Architecture for
Sovereign AI Agents in Education* — extended abstract in
[`paper/extended-abstract.md`](paper/extended-abstract.md), prepared for the
**UNU Macau AI Conference 2026** (*AI × Education: AI for Learning, Learning for
AI*) and its UNU–Springer proceedings.

**Submission and presentation:** the form-safe paste fields are in
[`paper/form-ready-abstract.md`](paper/form-ready-abstract.md), validated by
`python scripts/check_submission.py`. The current PowerPoint is
[`docs/trust-by-construction-final.pptx`](docs/trust-by-construction-final.pptx);
the browser deck and timed script remain under [`docs/presentation/`](docs/presentation/).

> **Bounded claim: testable containment in a declared environment.** The teaching
> profile demonstrates independent checks for specified failure paths. It is not a
> production deployment, a security certification, a hardware-isolation proof, or
> a claim that a single host can withstand its own administrator.

---

## Sixty seconds

```bash
git clone https://github.com/genaiworks/fssai-ra.git
cd fssai-ra/fssai-ra
pip install -e ".[dev]"

pytest                                            # 187 deterministic tests, fully offline
fssaira doctor                                    # what is this deployment, really?
fssaira verify   profiles/student_support.yaml    # bounded model check: 240 states, 0 violations
fssaira evaluate profiles/student_support.yaml    # adversarial + utility + ablation
fssaira conformance --backend sql                 # does it still hold on another backend?
fssaira race-test profiles/student_support.yaml   # 32 callers, 1 mutation, 1 receipt
```

No network, no model weights, no GPU. The whole suite reproduces on a
disconnected laptop in under two seconds, which is the point: a second
institution can **check** these numbers rather than trust them.

## What is new in v1.0.0

Release `v0.5.0` could specify authority boundaries and test the attacks its
authors thought of. This release adds the three things that make the assurance
argument survive contact with another institution.

| | Question it answers | Result |
|---|---|---|
| **Bounded model checking** | What about the combination nobody imagined? | 240 configurations, 5 invariants, 0 violations |
| **Ablation-measured coverage** | Is each control load-bearing, or decorative? | 8 of 8 controls restored their harm |
| **Portable conformance** | Does it still hold after you replace a component? | 25 checks, 2 independent backend profiles |
| **Concurrent replay race** | Can simultaneous retries duplicate an approved action? | 32 callers, 1 mutation, 1 receipt |

Plus: **single-transaction execution** on PostgreSQL, which removes — rather than
merely detects — the one failure mode the previous release could only document;
**privilege invariance**, so a model cannot declare its own review level; real
**authentication** replacing spoofable headers; a **React console**; and a
**utility baseline** reported beside every containment figure.

See [`CHANGELOG.md`](CHANGELOG.md).

## The pipeline

```
 external sources / signed updates
              │
   ┌──────────▼───────────┐   validate type·size·schema·signature,
   │  1. IMPORT BOUNDARY   │   strip active content, protocol break
   │   (one-way diode)     │   →  NO ordinary path back out
   └──────────┬───────────┘
              │  inward only
   ┌──────────▼───────────┐   durable, ordered, replayable
   │  2. EVENT TRANSPORT   │   (Kafka: offsets, hash, trace)
   └──────────┬───────────┘
   ┌──────────▼───────────┐   clean/validate (Spark) + versioned
   │  3. REPRODUCIBLE DATA │   snapshots + rollback
   │   (Spark + Iceberg)   │   (Iceberg: manifests, time travel)
   └──────────┬───────────┘
   ┌──────────▼───────────┐   local model (Ollama) + least-privilege
   │ 4. BOUNDED INTELLIGENCE│  agents; retrieved text is DATA;
   │                       │   action class from the CATALOGUE
   └──────────┬───────────┘
   ┌──────────▼───────────┐   policy verifies the ACTUAL operation
   │ 5. ACCOUNTABLE ACTION │   (not the model's story); consequential
   │  policy + human + log │   needs a named human; append-only,
   └──────────────────────┘   hash-chained evidence, one transaction
```

## The control contract

The original contribution. For each consequential capability, seven fields:
**protected asset, permitted operation, enforcement point, accountable owner,
failure test, evidence artifact, failure response.** Twenty-five requirements
live in [`contract/*.yaml`](contract/) as machine-readable YAML, so the contract
doubles as a conformance checklist — and `pytest` fails if any field is empty.

Not a documentation convention. A **diagnostic**: a capability whose seven fields
cannot be filled is a capability nobody is ready to automate. It also works
unmodified as an RFP section.

```bash
fssaira contract --output contract.json     # the whole contract, human or machine readable
```

## Run the reference deployment

```bash
python scripts/bootstrap_dev_env.py
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d          # core stack
docker compose --env-file deploy/.env -f deploy/compose.yaml --profile model up -d   # + Ollama
python scripts/smoke_stack.py
```

| Service | Where | What it is |
|---|---|---|
| Operator console | `http://localhost:8088` | React; deployment state, governance, actions, evidence, assurance |
| Control API | `http://localhost:8080/docs` | The only way to change a governed resource |
| Import gateway | `http://localhost:8081` | Low-side, inward only, no read-back route |

Add `--profile analytics` for MinIO, the Iceberg REST catalog, and Spark. See
[`docs/PLATFORM.md`](docs/PLATFORM.md).

## Extend it

Everything is a port with at least one reference adapter, discovered through
entry points, a dotted path, or in-process registration.

```bash
fssaira plugins                     # every backend this process can see
fssaira model list                  # ollama (default) · openai-compatible · deterministic · …
fssaira init my-domain              # scaffold a profile, a contract, and a failing test
```

```toml
# your own package — no fork required
[project.entry-points."fssaira.models"]
my-institution = "mypkg.models:InstitutionModel"
```

A replacement is acceptable when the **same conformance suite still passes**
against it — not because it inherits from a blessed base class.

```bash
fssaira conformance --backend sql --output conformance.json
```

The scaffold ships an **empty** assurance file on purpose. A new domain inherits
the structure and none of the evidence; borrowing another domain's results is how
a method decays into a vocabulary. Start at [`docs/EXTENDING.md`](docs/EXTENDING.md).

## How each failure is contained

| Adversarial case | Independent control | Where |
|---|---|---|
| Prompt injection in a retrieved document | markers stripped; retrieved text stays untrusted; egress denied; the inward channel exposes no outward method | `injection_specimen_stripped_at_import` |
| A fully compromised model | least-privilege grant plus default-deny policy; every hostile proposal denied | `compromised_model_against_least_privilege` |
| A model that understates its own action class | class re-derived from the capability catalogue; downgrade recorded | `model_declares_its_own_action_class` |
| Exfiltration hidden in a tool argument | argument inspection on non-egress tools | `exfiltration_hidden_in_arguments` |
| A proposal changed after review | canonical digest binding; zero mutations | `changed_target_after_approval` |
| A genuine approval for another executor, proposal, role, or past its expiry | audience, digest, role, and expiry checked independently of the signature | 4 model-check variants |
| Poisoned source data | lineage plus snapshot rollback to the last approved state | `poisoned_data_rolled_back_to_approved_snapshot` |
| Insider record tampering | append-only hash chain; independent Spark re-verification catches truncation too | `insider_record_tampering_detected` |
| Interrupted outcome evidence | single transaction where possible; otherwise reported uncertain and reconciled once | `outcome_evidence_interruption_and_recovery` |

`fssaira evaluate` runs all 30, plus 6 benign tasks and 8 ablations.

## Results

| Measure | Result | What it does and does not mean |
|---|---|---|
| Adversarial scenarios contained | `30/30` | containment of sampled risk classes, not coverage of a threat catalogue |
| Unauthorized mutations | `0` | across every denial scenario |
| Benign tasks completed | `6/6` | the denominator that makes a containment rate meaningful |
| False-denial rate | `0.0` | a system that denies everything scores perfectly on containment |
| Authority coverage | `1.0` | 8/8 controls restored their harm when removed |
| States explored | `240` | 5 invariants, 0 violations |
| Conformance checks | `25` | on 2 independent backend profiles |

Full table and its limits: [`evaluation/results/RESULTS.md`](evaluation/results/RESULTS.md).
Regenerate with `python scripts/generate_results.py`.

**Every figure the paper and the deck quote comes from that generator**, and
[`tests/test_paper_alignment.py`](tests/test_paper_alignment.py) fails the build
if prose and code disagree. Alignment is a test here, not a promise.

## Read this first

**If you are reviewing this**

- [`docs/REVIEWERS.md`](docs/REVIEWERS.md) — **check every claim in ten minutes**, offline
- [`docs/ASSURANCE.md`](docs/ASSURANCE.md) — every public claim, its mechanism, its test, and its limit
- [`docs/RESPONSIBLE_AI.md`](docs/RESPONSIBLE_AI.md) — risk → mitigation → test → result, with the open rows marked open
- [`docs/IMPACT.md`](docs/IMPACT.md) — who benefits, labelled *demonstrated*, *reasoned*, *hypothesis*, or *out of scope*

**If you are using it**

- [`docs/DEMO.md`](docs/DEMO.md) — the two-minute demonstration
- [`docs/ADOPTION.md`](docs/ADOPTION.md) — a 30/60/90-day path to a pilot
- [`docs/PROCUREMENT.md`](docs/PROCUREMENT.md) — the seven fields as supplier questions
- [`docs/EXTENDING.md`](docs/EXTENDING.md) — adding a domain without inheriting unsupported claims
- [`docs/PLATFORM.md`](docs/PLATFORM.md) — the distributed deployment
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — failure and recovery procedures
- [`docs/SECURITY.md`](docs/SECURITY.md) · [`docs/DIODE_DEPLOYMENT.md`](docs/DIODE_DEPLOYMENT.md) — threat model, and where the directionality claim stops

## Security and limitations

Read [`docs/SECURITY.md`](docs/SECURITY.md) first. In short: this contains
categories of catastrophic failure by structure, but it is **not** proof against
a compromised host administrator, a subverted signing authority, or colluding
control owners. A hardware diode governs one link; every other path needs its own
control. Tamper-evidence detects, it does not prevent.

Report vulnerabilities per [`SECURITY.md`](SECURITY.md).

## Standards alignment (not certification)

NIST SP 800-207 · NIST AI 600-1 · OWASP Top 10 for LLM Applications · OWASP
Agentic Security · MITRE ATLAS · ISO/IEC 42001 · UNESCO AI Competency Framework ·
UN Global Digital Compact.

## Citation

> R. Srivastava, *Trust by Construction: A Testable Architecture for Sovereign AI
> Agents in Education* (UNU Macau AI Conference 2026). Reference implementation:
> this repository, release `v1.0.0`.

Machine-readable metadata in [`CITATION.cff`](CITATION.cff).

## License

Apache-2.0 — see [`LICENSE`](../LICENSE). Contributions that preserve explicit
assurance boundaries are welcome; see [`CONTRIBUTING.md`](CONTRIBUTING.md).
