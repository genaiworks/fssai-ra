# FSSAI-RA — Fail-Secure Sovereign AI Reference Architecture

[![Tests](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml/badge.svg)](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-0B7261.svg)](../LICENSE)
[![Tag v0.4.0](https://img.shields.io/badge/tag-v0.4.0-4C566A.svg)](https://github.com/genaiworks/fssai-ra/tree/v0.4.0)

A **runnable teaching-profile reference implementation** for specifying and testing
the authority boundaries of agentic AI. The synthetic student-support workflow runs
in memory; adapter seams show where Kafka, Spark, Iceberg, and a local model can be
evaluated without pretending those production systems are included in the demo.

**Companion paper:** *Trust by Construction: A Testable Architecture for Sovereign
AI Agents in Education*
**Repository:** https://github.com/genaiworks/fssai-ra

> **Bounded claim: testable containment in a declared environment.** The teaching
> profile demonstrates independent checks for specified failure paths. It is not a
> production deployment, security certification, hardware-isolation proof, or claim
> that a single host can withstand its own administrator.

The original contribution is the **control contract**: each governance requirement
names the protected asset, permitted operation, enforcement point, owner, test,
evidence artifact, and failure response. The code makes that contract inspectable.

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
   │  2. EVENT TRANSPORT   │   (Kafka-like: offsets, hash, trace)
   └──────────┬───────────┘
   ┌──────────▼───────────┐   clean/validate (Spark-like) +
   │  3. REPRODUCIBLE DATA │   versioned snapshots + rollback
   │   (Spark + Iceberg)   │   (Iceberg-like: signed manifests)
   └──────────┬───────────┘
   ┌──────────▼───────────┐   semantic router + local model +
   │ 4. BOUNDED INTELLIGENCE│  least-privilege agents; retrieved
   │                       │   text is DATA, never instructions
   └──────────┬───────────┘
   ┌──────────▼───────────┐   policy verifies the ACTUAL operation
   │ 5. ACCOUNTABLE ACTION │   (not the model's story); high-impact
   │  policy + human + log │   needs a named human; append-only,
   └──────────────────────┘   hash-chained evidence
```

## Quickstart

```bash
git clone https://github.com/genaiworks/fssai-ra.git
cd fssai-ra/fssai-ra
pip install -e ".[dev]"      # or: pip install pyyaml pytest
pytest -q                    # contract, attack, ablation, and exact-action tests
python examples/demo_student_support.py
fssaira validate-profile profiles/student_support.yaml
fssaira evaluate profiles/student_support.yaml --output evaluation-report.json
```

Expected test result for release `v0.4.0`: `32 passed`. The demo uses synthetic
records and performs no network calls or external mutations.

The evaluation command executes eight declared scenarios—including altered
approved payloads, expired and forged approvals, operations and transitions outside
the profile, idempotent retry, and interrupted outcome evidence—and emits a
machine-readable JSON report. The release result is committed at
[`evaluation/results/v0.4.0-student-support.json`](evaluation/results/v0.4.0-student-support.json).

## Read this first

- [`docs/ASSURANCE.md`](docs/ASSURANCE.md) maps every public claim to its test,
  evidence, and limit.
- [`docs/DEMO.md`](docs/DEMO.md) provides a reproducible five-minute walkthrough.
- [`docs/EXTENDING.md`](docs/EXTENDING.md) shows how to add a domain without
  inheriting unsupported assurance claims.
- [`docs/SECURITY.md`](docs/SECURITY.md) defines the threat model and residual risk.
- [`docs/extended-abstract.md`](docs/extended-abstract.md) contains the conference
  paper narrative and evaluation plan.

## Repository map

| Domain | Module | Contract |
|---|---|---|
| Import boundary (diode) | `src/fssaira/diode.py`, `import_boundary.py` | `contract/1_import_boundary.yaml` (IB-1, IB-2) |
| Event transport | `src/fssaira/event_transport.py` | `contract/2_event_transport.yaml` (ET-1) |
| Reproducible data | `src/fssaira/reproducible_data.py` | `contract/3_reproducible_data.yaml` (RD-1) |
| Bounded intelligence | `src/fssaira/bounded_intelligence.py` | `contract/4_bounded_intelligence.yaml` (BI-1, BI-2) |
| Accountable action | `src/fssaira/accountable_action.py`, `exact_action.py`, `evidence.py` | `contract/5_accountable_action.yaml` (AA-1..4) |
| Domain adaptation | `src/fssaira/profiles.py`, `profiles/*.yaml` | validated operation and transition rules |
| Evaluation | `src/fssaira/evaluation.py`, `src/fssaira/cli.py` | machine-readable scenario results |

The accountable-action domain also includes `src/fssaira/exact_action.py`. It
authenticates approval fields with a teaching-profile HMAC, accepts only trusted
approval keys, profiled reviewer roles, operations, and state transitions, and binds approval to the exact target,
arguments, evidence version, and case version. Successful retries return the stored
receipt without a second mutation or duplicate evidence. See
`tests/test_exact_action.py`.

If the authoritative transition succeeds while outcome-evidence append is
interrupted, the executor raises `OUTCOME_EVIDENCE_PENDING`, retains a pending
outcome, and exposes an idempotent reconciliation method. The included store is an
in-memory teaching model; deployments must use a durable outbox committed atomically
with the authoritative mutation.

The **control contract** (`contract/*.yaml`) records, for every requirement, the
seven fields from the paper — protected asset, permitted operation, enforcement
point, owner, test, evidence artifact, failure response — as machine-readable
YAML, so it doubles as a conformance checklist.

## How each failure is contained

| Adversarial case | Independent control | Test |
|---|---|---|
| Prompt injection specimen | one recognizable malicious line is removed; retrieved text remains untrusted; egress tools are denied; the simulated diode exposes no outward method | `test_prompt_injection_is_stripped_and_egress_blocked` |
| Poisoned source data | lineage + snapshots → identify and roll back to last approved state | `test_poisoned_data_is_contained_by_rollback` |
| Model hallucination / wrong action | advice separated from authority; high-impact needs a named human | `test_hallucinated_high_impact_action_needs_named_human` |
| Compromised model / update | signature-checked ingestion + quarantine; no self-escalation | `test_compromised_update_is_quarantined_and_no_self_escalation` |
| Insider record tampering | append-only hash chain detects silent edits | `test_insider_record_tampering_is_detected` |

`tests/test_ablations.py` removes one control at a time and shows the harm returns
in the synthetic scenario. This supports a narrow implementation claim, not a
general causal or security guarantee.

## One-minute exact-action demonstration

1. An agent proposes moving synthetic case `S-104` from `draft` to
   `ready_for_officer_review` against version 7 and evidence snapshot 1.
2. An officer approves the canonical digest of that exact proposal.
3. Changing the target or transition produces `APPROVAL_PAYLOAD_MISMATCH` and zero
   mutations.
4. Executing the reviewed proposal records intent and outcome; retrying returns the
   same receipt without a second mutation.

This demonstrates a governance rule as observable behavior: **a changed proposal
requires renewed review**.

## Extending it into your own framework

- **Swap in production backends** via `adapters/`: `kafka_adapter.py`,
  `iceberg_adapter.py`, `spark_adapter.py`, and `local_model_ollama.py` (a real
  local LLM). Each seam is chosen so a backend is acceptable only if the domain's
  contract test still passes.
- **Add a new application** (health, courts, benefits) by reusing the five
  domains: copy [`profiles/template.yaml`](profiles/template.yaml), name every
  permitted transition and approval role, register least-privilege tools, and add
  contract entries + tests for each consequential action. Start with
  [`docs/EXTENDING.md`](docs/EXTENDING.md) and `CONTRIBUTING.md`.

## Security & limitations

Read `docs/SECURITY.md` first. In short: this contains categories of catastrophic
failure by structure, but it is **not** proof against a compromised host
administrator, a subverted signing authority, or colluding control owners. A
hardware diode governs one link; every other path needs its own control.
Tamper-evidence detects, it does not prevent.

## Standards alignment (not certification)

NIST SP 800-207 · NIST AI 600-1 · OWASP Top 10 for LLM Applications · MITRE ATLAS
· ISO/IEC 42001 · UNESCO AI Competency Framework · UN Global Digital Compact.

## Citation

> R. Srivastava, *Trust by Construction: A Fail-Secure Reference Architecture for
> Sovereign Agentic AI* (UNU Macau AI Conference 2026, Panel 2). Reference
> implementation: this repository.

For stable citation, use release `v0.4.0`. Machine-readable
citation metadata is available in [`CITATION.cff`](CITATION.cff).

## License

Apache-2.0 — see [`LICENSE`](../LICENSE). Cite the paper and software using
`CITATION.cff`.
