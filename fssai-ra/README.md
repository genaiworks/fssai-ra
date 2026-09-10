# FSSAI-RA — Fail-Secure Sovereign AI Reference Architecture

A **runnable, vendor-neutral reference implementation** for building next-generation,
AI-based systems on big-data tooling (Kafka, Spark, Iceberg) with a security spine
(one-way data diode, least-privilege agents, human-in-the-loop, tamper-evident
evidence).

> **Design claim: containment, not invulnerability.** No single compromised file,
> model, agent, user, or software layer should gain unchecked access, take a
> consequential action, or erase the record without meeting an *independent*
> control. When a required authorization is missing or uncertain, the system
> **fails secure** — the automated action is denied and a defined manual path
> preserves service.

This repository is the working code behind the paper *Trust by Construction: A
Fail-Secure Reference Architecture for Sovereign Agentic AI*. It runs with **no
external infrastructure** (in-memory reference backends) so you can read it, run
it, and test it in seconds — then swap in real Kafka/Spark/Iceberg/local-LLM via
the adapter seams.

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
pip install -e ".[dev]"      # or: pip install pyyaml pytest
pytest -q                    # 11 tests: contract + 5 attacks + 3 ablations
python examples/demo_student_support.py
```

## Repository map

| Domain | Module | Contract |
|---|---|---|
| Import boundary (diode) | `src/fssaira/diode.py`, `import_boundary.py` | `contract/1_import_boundary.yaml` (IB-1, IB-2) |
| Event transport | `src/fssaira/event_transport.py` | `contract/2_event_transport.yaml` (ET-1) |
| Reproducible data | `src/fssaira/reproducible_data.py` | `contract/3_reproducible_data.yaml` (RD-1) |
| Bounded intelligence | `src/fssaira/bounded_intelligence.py` | `contract/4_bounded_intelligence.yaml` (BI-1, BI-2) |
| Accountable action | `src/fssaira/accountable_action.py`, `evidence.py` | `contract/5_accountable_action.yaml` (AA-1..3) |

The **control contract** (`contract/*.yaml`) records, for every requirement, the
seven fields from the paper — protected asset, permitted operation, enforcement
point, owner, test, evidence artifact, failure response — as machine-readable
YAML, so it doubles as a conformance checklist.

## How each failure is contained

| Adversarial case | Independent control | Test |
|---|---|---|
| Prompt injection | active content stripped; retrieved text is untrusted evidence; egress tools denied; diode has no outward path | `test_prompt_injection_is_stripped_and_egress_blocked` |
| Poisoned source data | lineage + snapshots → identify and roll back to last approved state | `test_poisoned_data_is_contained_by_rollback` |
| Model hallucination / wrong action | advice separated from authority; high-impact needs a named human | `test_hallucinated_high_impact_action_needs_named_human` |
| Compromised model / update | signature-checked ingestion + quarantine; no self-escalation | `test_compromised_update_is_quarantined_and_no_self_escalation` |
| Insider record tampering | append-only hash chain detects silent edits | `test_insider_record_tampering_is_detected` |

`tests/test_ablations.py` removes one control at a time and shows the harm
returns — evidence that each control is load-bearing.

## Extending it into your own framework

- **Swap in production backends** via `adapters/`: `kafka_adapter.py`,
  `iceberg_adapter.py`, `spark_adapter.py`, and `local_model_ollama.py` (a real
  local LLM). Each seam is chosen so a backend is acceptable only if the domain's
  contract test still passes.
- **Add a new application** (health, courts, benefits) by reusing the five
  domains: register tools, define a least-privilege agent, and add contract
  entries + tests for the new consequential actions. See `CONTRIBUTING.md`.

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

## License

Apache-2.0 — see `LICENSE`. Built to be adopted, audited, and extended.
