# Why this stack: requirement-driven justification for the tool choices

The companion deployment (`fssai-ra`) runs PostgreSQL, Redis, Kafka, Spark, Iceberg on MinIO, and Ollama. A critic will ask why an AI-agent security system needs big-data tools. The short answer: **the big-data tools don't make the authorization decision. They do the other half of trustworthy AI, which is proving afterwards, to someone who doesn't trust you, exactly what the agents did.** Each tool below is tied to the requirement it meets, the simpler alternative a reviewer might propose, and the code that implements it.

## The architecture in one idea: two planes

```text
DECISION PLANE (synchronous, strongly consistent)          EVIDENCE PLANE (asynchronous, durable, independent)

model request                                              outbox relay ──► Kafka  fssaira.events / fssaira.imports
   │                                                                          │  ordered, retained, replayable
   ▼                                                                          ▼
dispatcher + trustkernel guard                             Spark: validate, dedupe, MERGE on source position
caller → delegation → exact-action approval → labels                          │
   │                                                                          ▼
   ▼                                                       Iceberg on MinIO/S3: snapshots, time travel, open format
PostgreSQL, ONE transaction:                                                  │
  state + receipt (request_id PK) + approval use             ▼
  (approval_id PK) + hash-chained evidence + outbox ──────►  Spark verifier: recompute the chain, check the notary

Ollama: local models on an internal-only network. Sensitive data never leaves the boundary.
```

This split is the same pattern as command/query separation and event sourcing, applied to AI accountability. The decision plane stays small, fast and strongly consistent. The evidence plane makes every decision durable, replayable, independently verifiable and queryable for years, and it scales with the number of agents without slowing a single decision.

## What the evidence plane must guarantee

Agent systems generate far more consequential events than human workflows. Every tool call, delegation hop, approval, label change and release is a decision someone may later have to explain. An evidence plane for AI agents must provide:

| # | Requirement | Why it matters for AI agents |
|---|---|---|
| E1 | Every decision and effect is recorded durably, in order, and can be replayed | Incident reconstruction and re-verification depend on the full sequence, not a sample |
| E2 | Many parties read the record without write access to the system of record | Security monitoring, compliance, analytics and auditors each need the evidence; none should hold database credentials for the live system |
| E3 | Verification is independent of the writer | Self-verification is not verification: a compromised control plane can report its own chain as intact |
| E4 | Evidence can be reproduced exactly as it was at decision time, years later | Appeals, audits and regulators ask what the system knew when it acted |
| E5 | Retention is long, cheap and in an open format that auditors can query with their own tools | Evidence that only the vendor's engine can read is not independent evidence |
| E6 | Throughput grows with agent count without touching decision latency | Adding agents must not slow approvals or weaken consistency |
| E7 | Sensitive data and model inference stay inside the boundary | Secrets, source code and personal data can't be sent to an external model API |

## Tool by tool

### PostgreSQL: the decision plane's system of record

**Meets:** consistency for every authorization and the source of truth for E1.
**Why this tool:** single-use approvals and idempotent receipts become primary-key constraints (`approval_uses.approval_id`, `execution_results.request_id`) in the same transaction as the state change and its hash-chained evidence record. The transactional outbox writes the event in that same transaction, so Kafka only ever carries committed truth, and a crash can't produce a state change without its evidence, or evidence without its state change.
**Alternative considered:** a key-value store. Rejected because single-use and exactly-one-effect need transactional constraints, not best-effort writes.
**Code:** `src/trustkernel/kernel/sql_backend.py` (the same SQL runs on SQLite in CI); the transactional outbox and relay are `fssai-ra/src/fssaira/event_outbox.py`.

### Kafka: the ordered, replayable, shared evidence log

**Meets:** E1, E2, E6.
**Why this tool:** a partitioned, ordered, retained log with independent consumer groups. The SIEM, the compliance archive, the analytics jobs and the verifier each read at their own pace, and none of them needs database credentials. Retention allows replay to rebuild or re-verify a downstream store. The source position `(topic, generation, partition, offset)` is a globally unique identity that makes the Iceberg sink idempotent under replay. Producers publish inward only, and the gateway has no read-back route to the control plane.
**Alternatives considered:** consumers polling PostgreSQL, which couples every reader to the live database and its credentials and offers no retained replay; and traditional queues (RabbitMQ, SQS), which delete messages on consumption and so lose the shared, replayable history that audit requires.
**Code:** `kafka` service on the isolated `data` network in `fssai-ra/deploy/compose.yaml`; topics `fssaira.events` and `fssaira.imports`; HMAC-signed envelopes (`FSSAI_EVENT_ENVELOPE_KEY`, `FSSAI_IMPORT_ENVELOPE_KEY`) and, in `compose.tls.yaml`, TLS with required client certificates.

### Spark: independent verification at any scale

**Meets:** E3, E6.
**Why this tool:** the verifier recomputes the evidence chain from the Iceberg archive in a different process, with different credentials, on a different schedule, and in a different execution engine from the Python control plane that wrote it. It checks every hash, every link, contiguous sequence numbers and no duplicates, and it checks the archive against checkpoints signed by an independent notary, which detects a deleted tail or a fully rewritten chain. The same engine runs streaming ingest (validate, dedupe, `MERGE` on source position, commit progress only after the table commit) and batch re-verification of the entire history, for example after a key rotation, an incident or an audit request, scaling out as history grows. This is the effect-oracle principle from the talks at platform scale: the judge is never the component being judged.
**Alternatives considered:** verification inside the control plane, rejected as self-verification; a single Python consumer, adequate for per-event checks at low volume but not for full-history re-verification, and it would share a codebase and language with the writer, which weakens independence.
**Code:** `fssai-ra/jobs/kafka_to_iceberg.py`, `jobs/verify_import_pipeline.py`, `jobs/verify_evidence_chain.py`; the `spark-iceberg` service.

### Iceberg on MinIO/S3: evidence as it was, for as long as needed

**Meets:** E4, E5, E6.
**Why this tool:** atomic table commits with snapshot IDs mean a decision can record the exact snapshot it relied on, and time travel reproduces that view years later. It supports `MERGE` for idempotent ingest and schema evolution as policies change. It's an open table format read by Spark, Trino, DuckDB and others, so an auditor can bring their own engine, and object storage keeps multi-year retention affordable.
**Alternatives considered:** history tables in PostgreSQL, which keep years of evidence on the transactional database and offer no engine-independent time travel; raw Parquet files, which have no atomic commits and so allow torn reads; and a proprietary warehouse, where auditors would depend on the vendor's access.
**Code:** `iceberg-rest`, `minio` and `iceberg-bootstrap` services; `fssai-ra/jobs/bootstrap_iceberg.py`.

### Redis: speed without authority

**Meets:** decision-plane latency for leases, rate limits and fast idempotency lookups.
**Why this tool:** sub-millisecond coordination for hot keys. It is never the authority: a Redis miss or failover degrades to PostgreSQL or to a fail-closed refusal, because asynchronous replication can lose an acknowledged write.
**Code:** `redis` service on the internal `control` network; bounded retries in the companion deployment.

### Ollama: sovereign models inside the boundary

**Meets:** E7, plus offline reproducibility.
**Why this tool:** models run on an internal-only network with no route off the host, so secrets, source code and personal data never reach an external API. The world policies make this enforceable rather than aspirational: model manifests declare which data classes each model may receive, and residency plus model attestation stop secret-bearing classes from being routed to a weaker or external model. The ablation study shows the two controls back each other up. The same runtime powers the offline workshop and demos, and an optional live attacker (`trustkernel redteam --live`).
**Code:** `ollama` service (profile `model`) in `fssai-ra/deploy/compose.yaml`; `model_manifests` in `worlds/*/pack.yaml`; `src/trustkernel/agents.py`.

## Design rules that make the stack defensible

These are the rules a careful reviewer checks, and each one is implemented:

1. **The evidence plane never authorizes.** A stream or lake view can lag, and a stale "approval not yet used" would be a replay hole. Authority lives only in the decision plane's constraints.
2. **Outbox, never dual write.** Kafka receives only what PostgreSQL committed.
3. **Snapshots are not tamper evidence; signatures are.** Anyone with bucket or catalog write access can commit a snapshot. The hash-chained ledger and notary-signed checkpoints, checked by the independent Spark verifier, make tampering detectable.
4. **Erasure by key, not by rewriting history.** Secrets and personal data go into immutable storage only as ciphertext under per-subject keys, or as hashes. Destroying the key erases the data (`src/trustkernel/kernel/key_custody.py`). Snapshot expiry follows the retention policy but never runs shorter than the audit window.
5. **Progress is not evidence.** A Spark checkpoint records progress; the `MERGE` on source position makes a replayed batch idempotent at the table.
6. **Recreated topics get a new generation,** because offsets restart at zero.

## Why the measured attacker is a grammar, not a local LLM

The threat model assumes the model is hostile and may emit any request the tool interface accepts; the dispatcher sees requests, not reasoning. The strongest attacker for a containment claim therefore searches the request space directly. The seeded grammar fuzzer and the bandit attacker do that, and they prove they can win: 105 of 300 fuzzed attacks and 60 of 60 bandit episodes succeed once the execution mediator is removed.

A small local model is a weaker searcher. In two local runs on September 24, 2026 (`trustkernel redteam --live --attempts 20 --remove execution_mediator`, `llama3.2:3b` through Ollama, temperature 0.9), it caused **0** unauthorized effects even against the weakened system. It spent its attempts on data-widening moves and never tried approval forgery. Reported as a security result, that zero would have been meaningless, which is exactly what the positive control exists to catch. This is a dated observation from a nondeterministic model, not a published figure. Ollama's job is sovereignty and offline reproducibility; the attacker's job is coverage.

## Questions a critic will ask, answered in one breath

- **"Isn't this over-engineered for authorization?"** Authorization uses only the guard and PostgreSQL. The big-data tools serve accountability: shared, replayable, independently verified, long-retained evidence. Each maps to a requirement above.
- **"Why Kafka at low volume?"** Replay, shared history and separation of duties matter at any volume. Volume only adds to the case.
- **"Why Spark instead of a Python consumer?"** Independence and full-history re-verification. The verifier must not share a process, credentials or engine with the writer.
- **"Why not keep evidence in PostgreSQL?"** Years of evidence belong in an open, snapshot-versioned format that auditors can query with their own engines, not on the transactional database.
- **"Single broker, replication factor 1?"** The compose file is the single-node reference stack for development and demonstration. A production deployment runs at least three brokers with replication factor 3 and a minimum of two in-sync replicas, plus replicated object storage. Failover and sustained-load qualification are deployment-specific evidence still to be gathered.
- **"Do the talks need any of this?"** No. They demonstrate the decision plane as a library, offline, so every attendee can run it. The evidence plane shows how the same design carries into an enterprise deployment.
