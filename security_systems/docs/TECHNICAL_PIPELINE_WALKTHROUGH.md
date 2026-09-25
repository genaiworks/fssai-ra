# Evidence-plane reference pipeline (companion deployment)

This walkthrough traces one record through the evidence plane of the companion deployment (`fssai-ra`): an authenticated producer, Kafka, Spark, Iceberg on object storage, PostgreSQL, Redis and an independent verifier. It is a reference architecture for a technical demonstration, not a claim that a production cluster has been qualified.

## Why this stack

The authorization decision happens in the decision plane: the `trustkernel` guard in the dispatcher, plus a PostgreSQL transaction whose primary keys enforce single-use approvals and idempotent receipts. This pipeline is the **evidence plane**. It makes every decision durable, replayable, retained for years and verifiable by a party that doesn't trust the system that wrote it. It runs strictly downstream of the decision and is never consulted to authorize an action, because a stream or lake view can lag. [Why this stack](TOOLING_RATIONALE.md) ties each tool to its requirement, the alternative a reviewer might propose, and the code. In short:

| Tool | Requirement it meets |
|---|---|
| PostgreSQL | Strongly consistent decisions; a transactional outbox so the log carries only committed truth |
| Kafka | Ordered, retained, replayable evidence shared by many consumers without database credentials |
| Spark | Verification independent of the writer (different process, credentials and engine), from per-event checks to full-history re-verification |
| Iceberg on MinIO/S3 | Evidence reproducible as of decision time through snapshots and time travel; open format; affordable multi-year retention |
| Redis | Fast leases and lookups, never authority |
| Ollama | Local models on an internal-only network, so sensitive data never leaves the boundary |

The conference demonstrations run the decision plane alone as an offline library, so every attendee can reproduce them. This walkthrough shows how the same design carries into an enterprise deployment.

## 1. The pipeline in one view

```text
producer/API
   │ HTTPS + HMAC request signature
   ▼
ingress gateway ── audit/quarantine ──► Kafka topic
   │                                      │
   │                                      ▼
   │                               Spark Structured Streaming
   │                               parse → validate → hash-check
   │                                      │
   │                                      ▼
   │                               Iceberg REST catalog
   │                                      │
   │                         metadata + manifests + snapshots
   │                                      │
   │                                      ▼
   │                                   MinIO/S3
   │
   ├── PostgreSQL: workflow state, approvals, outbox, encrypted records
   └── Redis: bounded cache/lease/idempotency accelerator, never sole authority
```

The security guard sits at the tool-dispatch boundary. It controls who may
request a consequential operation and which data classes may leave a session;
the pipeline controls how accepted evidence is transported, stored, replayed
and independently verified. These are related controls with different trust
boundaries.

## 2. Example input record

An external publisher submits a document using a stable `ingest_id`:

```json
{
  "source": "research-partner",
  "content_type": "text/plain",
  "data": "Temperature excursion observed at site 17.",
  "ingest_id": "partner-2026-00041",
  "signature": "hmac-sha256-over-canonical-envelope"
}
```

The canonical signed message is compact JSON with sorted keys:

```text
{"content_type":"text/plain","data":"Temperature excursion observed at site 17.","ingest_id":"partner-2026-00041","source":"research-partner"}
```

The gateway authenticates the source key, checks content type and size, strips
active content where policy requires it, and computes:

```text
content_hash = SHA-256(UTF-8(sanitized_text))
trace_id     = stable trace identifier for the accepted envelope
```

The signature authenticates the sender and envelope integrity. It does not
prove that the document's claims are true.

## 3. Kafka envelope and delivery semantics

The gateway publishes one JSON envelope to `fssaira.imports`:

```json
{
  "published_at": "2026-09-23T12:47:21Z",
  "trace_id": "672ea0c44fc9f580",
  "value": {
    "source": "research-partner",
    "text": "Temperature excursion observed at site 17.",
    "stripped": [],
    "content_hash": "103cbe6c37e369ab817b62b8addb80e18315351e6c897eed11776d220819b333",
    "ingest_id": "partner-2026-00041"
  }
}
```

Kafka metadata is part of the downstream identity:

```text
(kafka_topic, topic_generation, kafka_partition, kafka_offset)
```

`ingest_id` prevents duplicate business submissions at the gateway. Kafka
position prevents duplicate delivery into the sink. `topic_generation` must be
incremented when an operator deletes and recreates a topic, because offsets
restart at zero. A consumer group and checkpoint provide at-least-once
recovery; they do not make an arbitrary external side effect exactly once.

For a protected deployment, use TLS for the Kafka listener, verify the broker
CA and hostname, restrict topic ACLs, and keep producer and consumer identities
separate. The gateway may publish inward; it does not receive a read-back route
from the control plane.

## 4. Spark processing contract

Spark Structured Streaming reads one immutable topic and parses the envelope
with a strict schema. A malformed JSON row is retained as a null-bearing row so
the batch fails visibly; it is not silently filtered.

For each micro-batch:

1. Parse the envelope and attach Kafka topic, generation, partition, offset and
   ingestion timestamp.
2. Reject missing `source`, `text`, `trace_id` or `content_hash`.
3. Recompute `SHA-256(text)` and reject a mismatch before any Iceberg commit.
4. Check position conflicts: an existing Kafka position with a different trace
   or hash indicates topic reset or tampering and stops the stream.
5. Deduplicate within the batch by the complete source position.
6. `MERGE` into Iceberg on topic, generation, partition and offset.
7. Commit the Spark checkpoint only after the Iceberg operation succeeds.

This ordering matters. A checkpoint is progress state, not evidence backup. If a
process dies after an Iceberg commit and before the checkpoint commit, Spark may
replay the batch. The `MERGE` identity makes that replay idempotent at the table
boundary.

Why Spark rather than a lighter consumer: the same contract runs as a stream
and as a batch over the entire history, for example re-verifying every hash in
years of evidence after a key rotation, an incident or an audit request, and it
scales out as history grows. Its verifier jobs also run in a different engine,
process and credential set from the Python control plane that wrote the
evidence, which is what makes their result independent.

## 5. Iceberg and object storage

The REST catalog owns namespace and table metadata. MinIO stores the warehouse
objects. The imported table contains:

```sql
CREATE TABLE sovereign.fssaira.imported_evidence (
  source STRING NOT NULL,
  text STRING NOT NULL,
  stripped ARRAY<STRING>,
  content_hash STRING,
  trace_id STRING NOT NULL,
  ingest_id STRING,
  kafka_topic STRING,
  topic_generation STRING,
  kafka_partition INT NOT NULL,
  kafka_offset BIGINT NOT NULL,
  imported_at TIMESTAMP NOT NULL
)
USING iceberg
PARTITIONED BY (days(imported_at));
```

One successful write creates data files, manifests, a manifest list and new
table metadata. The catalog atomically advances the current metadata pointer.
The snapshot ID is the durable reference to the committed table view; it is not
the Kafka offset and must be recorded with any decision that depends on it.

Retention is a policy control. Expiring snapshots or deleting orphan files
before the appeal and audit windows close can destroy the ability to reproduce a
decision. A manifest identifies files but does not preserve a deleted file.

Two limits matter for security. First, snapshot immutability is not tamper
evidence: anyone with write access to the bucket or catalog can commit a new
snapshot. Tamper evidence comes from the hash-chained ledger and signed
checkpoints held outside the lake, and the verifier checks the table against
them. Second, immutable storage conflicts with erasure. Keep secrets and personal
data out of lake tables in plaintext: store ciphertext under per-subject keys, or
hashes, so destroying the key erases the data without rewriting history.

## 6. PostgreSQL state and encryption

PostgreSQL is the system of record for workflow state: cases, proposals,
approvals, encrypted fields, audit records and the transactional event outbox.
The outbox row is written in the same database transaction as the state change;
a relay publishes it to Kafka with a stable `event_id`. Consumers deduplicate
that ID because relay delivery is at least once.

For sensitive fields, use envelope encryption:

```text
master key (KMS/HSM, never application plaintext)
       │ unwraps
per-subject/class DEK
       │ AES-256-GCM(random 96-bit nonce, authenticated AAD)
plaintext ───────────────────────────────► ciphertext BYTEA
```

Store the nonce, ciphertext, key version and AAD binding. A typical AAD binds
the subject, field, classification, record identifier and schema version. The
database service can store and query ciphertext but must not receive the DEK.
Rotate by wrapping a new DEK or re-encrypting under a new key version according
to the custody policy. Destroying a subject's DEK makes retained ciphertext
unreadable, but does not erase plaintext that escaped into logs, exports,
caches or model memory.

## 7. Redis: role, keys and limits

Redis is an accelerator and coordination store, not a replacement for
PostgreSQL. Suitable keys include:

```text
case:{case_id}                 JSON/hash view with version
approval-use:{approval_id}     single-use marker with TTL
receipt:{request_id}           idempotency result with TTL/retention policy
lease:{resource}               short-lived worker lease
```

Use `MULTI/EXEC` or a Lua script for compare-and-set version checks, bounded
retry with backoff, and an explicit conflict result. Enable AOF and a durable
volume, require authentication, and use TLS in a networked deployment. Redis
loss must degrade to PostgreSQL recovery or a fail-closed refusal; it must not
silently authorize from stale state. Do not place plaintext sensitive records
in a cache unless the cache has the same classification, retention and erasure
controls as the source of record.

## 8. How the guard joins the pipeline

The model can propose:

```json
{"tool":"trigger_deploy","arguments":{"service":"svc-payments","build":"v42"}}
```

The dispatcher, not the model, resolves the authenticated principal and
server-issued context. It verifies the delegation chain, binds defaults,
canonicalizes arguments and checks an Ed25519 approval over:

```text
request_id + principal + tool + resource + canonical_arguments + audience + expiry
```

Only after verification does it invoke the callback that writes PostgreSQL and
the outbox. A read from the evidence pipeline carries a data-class label into
the session before the read body executes. Every worker handoff unions labels;
the release gate checks recipient clearance and purpose. A model cannot lower a
label by describing a secret as public.

## 9. Verification commands

The technical demonstration should show independent checks, not only service
logs:

```bash
# run the conference security demo and wrapper tests
python demo.py --no-color
python -m pytest -q
make evidence

# The companion deployment implementation runs this in its analytics image:
# spark-submit jobs/verify_import_pipeline.py --trace-id <trace-id>
```

The verifier should report one row for the trace, zero bad hashes, zero
duplicate source positions and the current Iceberg snapshot ID. Repeat after a
Spark restart; the same trace must remain one row. For a stronger demonstration,
replay a committed Kafka offset with a fresh checkpoint and verify that the
Iceberg row count does not increase.

## 10. What this walkthrough can and cannot claim

The pipeline demonstrates ordering, authenticated envelopes, content-integrity
checks, snapshot references, replay-safe sink identity and independent output
verification. It does not establish multi-broker failover, sustained-load
capacity, KMS/HSM qualification, hardware one-way transfer, production identity
provider integration or regulatory compliance. Those require deployment-specific
evidence and should be listed as open work in any write-up that cites this pipeline rather than
hidden behind a green unit-test count.
