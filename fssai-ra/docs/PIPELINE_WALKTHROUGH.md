# Technical pipeline walkthrough: from test data to verifiable output

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Run the protected-data lab in section 5, then follow the service setup and verification in sections 9–11.

This guide explains how to build a similar system, starting with actual synthetic inputs and following bytes through encryption, PostgreSQL, Redis, Kafka, Spark, Iceberg, model context, authorization and output verification. It describes the implementation in this repository, with deployment work explicitly separated from runnable examples.

**If the architecture feels overwhelming, read the one-page [end-to-end workflow](END_TO_END_WORKFLOW.md) or section 0 first.** Then read sections 1–4, run the lab in section 5, and follow the service pipeline in sections 6–12. Commands below run from the **inner `fssai-ra/` application directory** containing `pyproject.toml`. The repository root contains another directory with the same name. All people and records in the examples are synthetic. The healthcare example exercises access control only; it does not generate clinical advice.

[Documentation index](README.md) · [Architecture](REFERENCE_ARCHITECTURE.md) · [Platform deployment](PLATFORM.md) · [Privacy implementation](PRIVACY_REFERENCE.md)

## 0. Read this first: the whole system in one page

### 0.1 The idea in one sentence

An AI model may help with decisions about sensitive records, but it never holds keys, never sees more than the task needs, and never acts on its own. Every read is checked before it happens. Every change needs a human-approved, exact action. Every step leaves evidence that someone else can check.

Most of the apparent complexity is **breadth, not depth**. The same idea (*check before acting, then record what happened*) is applied in three places, and each place uses infrastructure that could be swapped for something else.

### 0.2 Three rooms and one rule

Think of a records office with three rooms.

| Room | Everyday analogy | What the code does | Main modules |
|---|---|---|---|
| **Vault room** (protected read and release) | Files are locked in cabinets. A clerk checks your permission slip *before* opening a drawer, blacks out names before an assistant reads the file, and checks again at the door before anything leaves. | Encrypt fields → check grant → decrypt only allowed fields → replace identities with tokens → model → re-check → restore names only for entitled recipients | `key_custody`, `encrypted_records`, `disclosure`, `privacy_vault`, `privacy_pipeline` |
| **Change desk** (accountable state change) | Nobody edits a record directly. Someone fills in a form, a supervisor signs *that exact form*, a clerk carries out exactly what was signed, once, and writes it in the ledger. | Proposal → review → approval bound to the proposal digest → executor checks version and replay → state, receipt and evidence committed together | `control_plane`, `exact_action`, `atomic_execution`, `sql_backend` / `redis_backend` |
| **Mailroom and archive** (external evidence ingestion) | Public letters arrive. Someone checks the sender and removes anything suspicious, puts them on a conveyor belt, and a librarian shelves them in a catalogued archive. | HMAC source check and sanitization → Kafka topic → Spark micro-batches → Iceberg table on MinIO | `import_boundary`, `import_api`, `kafka_backend`, `jobs/kafka_to_iceberg.py` |

**The one rule that ties them together:** model output is always a *suggestion*. It is never a grant, an approval or a release. Every room re-checks authority itself instead of trusting what came before it.

### 0.3 Which tool belongs to which room

| Tool | Room | Role in one line | Running by default in Compose? |
|---|---|---|---|
| FastAPI control API (`:8080`) | Change desk, plus the vault room through `/v1/propose-task` | The only HTTP front door for proposals, approvals, execution and evidence | Yes (core) |
| PostgreSQL | Change desk | Authoritative state; state, receipt and evidence commit in one transaction | Yes (core) |
| Redis | Change desk (*alternative*) | Backend used only when no database URL is set. **In Compose it runs but holds no control state** (section 8.1) | Runs, but idle for state |
| Kafka | Mailroom (`fssaira.imports`) and change desk notifications (`fssaira.events`) | Conveyor belt; carries data, does not decide anything | Yes (core) |
| Import gateway (`:8081`) and its SQLite audit | Mailroom | Front door for external documents | Yes (core) |
| React console | Change desk | Screens for people; enforces nothing | Yes (core) |
| Ollama | Model | Local model weights on institution hardware | Only with `--profile model` |
| Spark, Iceberg REST catalog, MinIO | Mailroom archive | Turns the conveyor into a queryable, versioned table | Only with `--profile analytics` |
| KeyCustody, TokenVault, DisclosureGate, PrivacyGate | Vault room | Encryption, tokens and permission checks | In-process Python objects; state is **in memory** |
| Evidence ledger and Ed25519 notary | All three | Hash-chained record plus signed checkpoints that detect truncation | In-process |

If you only remember one table, remember this one. When a section below goes deep into a tool, look up its room here first.

### 0.4 Where the rooms actually connect today

The walkthrough mostly treats the three rooms separately because they *are* mostly separate. There is one real connection in the running API, and a few that people often assume exist but do not.

**Implemented connection: `POST /v1/propose-task` with a `governed_context`** (in `src/fssaira/api.py`):

```mermaid
sequenceDiagram
    participant C as Caller
    participant API as Control API
    participant D as Disclosure layer (vault room)
    participant M as Model
    participant P as Proposal workflow (change desk)
    C->>API: POST /v1/propose-task {task, governed_context}
    API->>D: assemble(caller, governed_context)
    D-->>API: allowed values only, identities tokenized, receipt id
    API->>API: sanitize task and evidence text (names to tokens)
    API->>M: propose(task, evidence)
    M-->>API: tool calls (untrusted)
    API->>API: replace model's claimed action class with catalogue class<br/>unknown tool = high_impact
    API-->>C: proposals only + disclosure label + output id
    Note over C,P: Nothing has executed. To change state, a person submits<br/>POST /v1/proposals → review → approval → execute.
```

What to notice:

1. The model gets context **only through the disclosure gate**. If the loaded profile has a privacy gate and the caller sends no `governed_context`, the API returns `422`. If the profile has no disclosure policy, a `governed_context` request returns `404`.
2. The model's *own* claim about how risky its action is gets ignored. The server looks the tool up in its capability catalogue, and anything unknown is treated as `high_impact` and needs a named human.
3. The proposal list carries the label of everything the session read. Releasing it goes through `/v1/disclosure/outputs/{id}/release`, which re-checks the recipient.
4. Execution is a separate, human-driven step in the change desk.

**Connections that do *not* exist yet** (each one is listed as a gap in section 14):

| People often assume… | What actually happens |
|---|---|
| Imported documents in Iceberg feed the model | No. Nothing reads `imported_evidence` back into the vault room or the model. |
| A PostgreSQL commit and its Kafka event are one atomic step | Half true. The event is written to the `event_outbox` table **in the same transaction**; publishing to Kafka happens afterwards through a relay, at least once, with a stable `event_id` for deduplication (section 7). |
| Decision evidence flows into Iceberg automatically | No. `archive_evidence()` has to be called explicitly. |
| Redis caches PostgreSQL | No. They are alternatives, and Compose uses PostgreSQL. |
| Vault, keys and grants survive an API restart | Grants persist with `FSSAI_DISCLOSURE_STORE`. Custody keys, the erasure journal and encrypted rows persist when `KeyCustody` and `EncryptedRecordSource` are given a `SqlCustodyStore` and the master key file (section 4.3). Token-vault mappings are session-scoped by design and do not survive. |

### 0.5 A learning order that keeps it small

Learn one room at a time, from the one with no containers to the one with the most.

| Step | Command (from the inner `fssai-ra/` directory) | Room learned | Needs Docker? |
|---|---|---|---|
| 1 | `.venv/bin/python scripts/pipeline_walkthrough.py --output work/pipeline-demo-01`, then open files `01`…`07` in order | Vault room, end to end | No |
| 2 | `.venv/bin/python scripts/api_walkthrough.py --self-test` | Change desk, on SQLite | No |
| 3 | Section 9.1: Compose core services plus `smoke_stack.py` | Change desk on PostgreSQL, and the mailroom's front door | Yes |
| 4 | Section 10.4: `--profile analytics` | Mailroom archive (Spark and Iceberg) | Yes |

You can safely skip these on a first read: Redis internals (8.2–8.5), the DLQ details (9.4), Iceberg's `decision_evidence` and `control_events` tables (10.3), and the Spark evidence verifier (11.3).

### 0.6 Find the section for your question

| Your question | Section |
|---|---|
| What exactly is encrypted, and with what? | 4 |
| What does a ciphertext row look like in SQL? | 5.2 |
| Why can't the model see Alice's name? | 6, steps 6–7 |
| What stops the same approval running twice? | 7 and 8.3 |
| Why is Redis empty? | 8.1 |
| What does a Kafka message look like? | 9.3 |
| What if Spark crashes halfway through a batch? | 10.2 |
| How do I prove an output was not altered? | 11.1 |
| What is still missing for production? | 14 |

## 1. The architecture is several connected flows

There is no single implemented chain in which every record automatically passes through PostgreSQL, Redis, Kafka, Spark and a model. These tools have different responsibilities. In particular, enabling PostgreSQL does **not** populate Redis, and receiving an import does **not** automatically authorize it for model use.

```mermaid
flowchart TD
    A[External public or synthetic document] --> B[FastAPI import gateway]
    B --> C[Type, size, source HMAC and sanitization]
    C --> D[Kafka fssaira.imports]
    C --> E[Low-side SQLite import audit]
    D --> F[Spark Structured Streaming]
    F --> G[Iceberg imported_evidence]
    G --> H[MinIO or S3 data and metadata files]
    I[Operator or application] --> J[FastAPI control API]
    J --> K[Policy, proposal, review and approval]
    K --> L[Exact-action executor]
    L --> M[PostgreSQL state, receipt and evidence transaction]
    L --> N[Redis alternative state backend]
    J --> O[Kafka fssaira.events]
    O --> P[Independent monitoring projection]
    Q[Sensitive source records] --> R[Classify and encrypt through custody]
    R --> S[Encrypted record store]
    S --> T[Authorized context gate and token vault]
    T --> U[Minimum necessary model values]
    U --> V[Label output and recheck release authority]
    V --> W[Authorized output plus evidence digest]
```

The diagram shows responsibilities, not one transaction. PostgreSQL and Redis are alternative control-state branches. Custody and encrypted records can persist through `SqlCustodyStore` (section 4.3), and lifecycle events use a transactional outbox in every profile (section 7). Iceberg-to-governed-record ingestion, a hardware-backed key service and physical recipient delivery still require integration.

### Three workflows to keep separate

| Workflow | Input | Main path | Result | Runnable entry point |
|---|---|---|---|---|
| Protected read and release | Synthetic personal fields and an access grant | AES-GCM → SQL ciphertext → disclosure gate → tokens → scripted output → release checks | Released bytes, digest, signed evidence checkpoint | `scripts/pipeline_walkthrough.py` |
| External evidence ingestion | Signed public/synthetic text | Import API → sanitization → Kafka → Spark → Iceberg | Queryable, versioned imported evidence | `import_api.py`, `jobs/kafka_to_iceberg.py` |
| Accountable state change | Proposed operation on a resource | API → review → exact approval → executor → PostgreSQL **or** Redis | Versioned state and idempotent execution receipt | `scripts/api_walkthrough.py`, `scripts/smoke_stack.py` |

A production orchestration layer can connect them: select an approved Iceberg snapshot, make it available through an authorized source adapter, build context, obtain a model proposal, get human approval, execute and release. This repository has components for those steps; it does not yet prove the entire composition as a persistent, distributed privacy system.

## 2. Every tool and the data it owns

| Tool/component | Why it exists | What enters and what it saves | What it does not establish |
|---|---|---|---|
| Python / domain YAML | Define fields, purposes, endpoints, roles and permitted transitions | Profile loaded into policy objects | A policy file does not authenticate its author |
| FastAPI / Uvicorn | HTTP interfaces and server-side request validation | JSON requests; authenticated actor resolved by server | A user-supplied role or subject is not authority |
| Import boundary | Check origin and remove known active-content patterns | Raw text becomes normalized `source/text/stripped/content_hash` | Sanitization is neither encryption nor a guarantee against prompt injection |
| PostgreSQL / psycopg | Authoritative transactional control state | Resource rows, proposal/approval JSONB, receipts, evidence | JSONB is not encrypted automatically |
| SQLite | Offline lab and low-side import audit | Teaching databases and import intent/outcome evidence | Offline results do not qualify PostgreSQL concurrency |
| Redis / redis-py | Alternative shared control-state adapter | JSON strings, hashes, evidence list, replay and pending-outcome keys | Not a default PostgreSQL cache; not a single transaction for the whole action/evidence path |
| Kafka / confluent-kafka | Decouple producers and consumers; retain ordered partition logs | Normalized imports and lifecycle-event envelopes | Broker acknowledgment is not successful model processing or output delivery |
| PySpark Structured Streaming | Parse/validate micro-batches and build an analytical table | Kafka bytes → typed rows with partition/offset/timestamp | The import job does not run inference or decrypt personal records |
| Apache Iceberg | Transactional table metadata and snapshot history | Schemas, manifests, snapshot IDs and data-file references | Iceberg is a table format, not an encryption/key service |
| REST catalog | Resolve logical Iceberg table names to current metadata | Namespace/table metadata pointers | The fixture catalog is not production access governance |
| MinIO / S3 | Store Iceberg data and metadata objects | Data files, manifests, metadata files in `warehouse` bucket | Object existence does not prove provenance or policy permission |
| KeyCustody / cryptography | Encrypt fields and wrap per-subject/class keys | Wrapped DEKs, class KEK generations and erasure journal in process memory | Reference object credentials are not HSM isolation |
| TokenVault / PrivacyGate | Replace identities before model use; restore only after entitlement checks | Session token mappings encrypted through custody | Tokens do not make rare attributes anonymous |
| ModelRegistry | Verify approved manifest and runtime identity information | Signed manifests, class/purpose/expiry restrictions | A reported artifact digest is not hardware attestation |
| Deterministic model / Ollama / OpenAI-compatible adapters | Produce proposals or text from allowed context | Model-specific request/response | Model text cannot approve itself; adapter choice does not confer authority |
| Evidence ledger / Ed25519 notary | Record events and independently anchor a count/head | Hash chain, checkpoints, receipts | A self-consistent chain alone cannot detect tail deletion or a full rewrite |
| React operator console | Human interaction with the control API | Browser-session token and displayed decisions | It does not enforce backend authorization |
| Docker Compose | Start a local topology with named volumes/networks | Container config and persistent service volumes | Shared-host containers are not independent administrative trust |
| Telemetry / metrics | Operational visibility | Counts, timing and trace identifiers | Do not send plaintext context, keys, bearer tokens or released identities to telemetry |

## 3. What the test data looks like

### 3.1 Protected source records

The lab reads the checked-in fixture [records.json](../examples/pipeline/records.json):

```json
{
  "synthetic": true,
  "schema_version": 1,
  "records": [
    {
      "subject": "patient-1",
      "fields": {
        "patient_name": "Alice Example",
        "diagnosis": "SYNTHETIC-RECORD-A: access review only"
      }
    },
    {
      "subject": "patient-2",
      "fields": {
        "patient_name": "Bob Example",
        "diagnosis": "SYNTHETIC-RECORD-B: access review only"
      }
    }
  ]
}
```

`profiles/healthcare_record_access.yaml` classifies `patient_name` as `synthetic-health-record` and `diagnosis` as `highly-restricted`. The second class can enter only the `on-premises` model zone. The lab grants the agent access only to patient-1, those two fields and the `treatment` purpose. Here that purpose is a policy label used to exercise access controls, not an instruction to give treatment advice.

`patient-1` is a synthetic surrogate. A real implementation should map institutional identifiers into a tenant-specific namespace. The current custody AAD has no independent tenant field: use an unambiguous tenant-qualified subject or extend/version the binding and migration scheme. Two tenants must not accidentally share a `(subject, class)` key identity.

### 3.2 External evidence is a different input

The import example is a public/synthetic policy document:

```text
Synthetic policy: access requests require an accountable reviewer.
```

It is safe to inspect that teaching payload in Kafka and Iceberg. Do not substitute personal health records: the current import path stores normalized text in clear, and its sanitizer is not a personal-data classifier or encryption stage.

### 3.3 Control-state input

The separate student-support API example starts with:

```json
{"resource_id":"S-500","status":"draft","version":1}
```

It proposes `prepare_case_for_review` with `from_status=draft`, `to_status=ready_for_officer_review` and a declared evidence version. This is an operational status transition, distinct from the protected fields above. Giving it the same subject name would not itself join the two workflows.

## 4. Exactly which cryptography is used

| Purpose | Implemented algorithm and representation | Source |
|---|---|---|
| Field confidentiality and integrity | AES-256-GCM; random 32-byte DEK for each `(subject, data_class)`; fresh random 12-byte nonce for each encryption; body includes 16-byte tag | `src/fssaira/key_custody.py` |
| Envelope encryption of DEKs | AES-256-GCM using class KEK; separate 12-byte wrapping nonce; wrap AAD binds subject and class | Same module |
| Fixture KEK derivation | HMAC-SHA-256 of `kek:<class>:<generation>`, keyed by master seed | Helper named `_hkdf`; it is **not** RFC 5869 HKDF extract-and-expand |
| Source provenance | HMAC-SHA-256 over exact UTF-8 source text | `import_boundary.py:ImportBoundary.sign` |
| Exact-action approvals and reference disclosure grants | HMAC-SHA-256 over each object's canonical signing payload | `exact_action.py`, `disclosure.py` |
| Identity tokens | Session-scoped HMAC-SHA-256, token suffix truncated to 10 hexadecimal characters, collision handling inside the vault | `privacy_vault.py` |
| Data and output digests | SHA-256; integrity comparison, not encryption | Import boundary, output receipt, evidence modules |
| Evidence chain | SHA-256 over sequence, timestamp, kind, payload and previous hash | `evidence.py` and SQL/Redis adapters |
| Independent checkpoints and model manifests | Ed25519 signatures, verified with trusted public keys | `evidence_notary.py`, `model_registry.py` |

AES-GCM authenticates ciphertext and associated data. A nonce must never repeat under a key; the implementation generates random nonces, so deployment needs a key-usage budget and rotation policy. Hex/base64 are encodings and give no confidentiality. HMAC is a shared-secret authenticator, not a public-verifiable digital signature. SHA-256 cannot recover a plaintext value, but hashes of predictable values can still leak information through guessing. See the [cryptography AEAD documentation](https://cryptography.io/en/latest/hazmat/primitives/aead/).

### 4.1 One field, byte by byte

For Alice's name, the lab asks custody to encrypt:

```python
ciphertext = custody.encrypt(
    ingest_credential,
    subject="patient-1",
    field="patient_name",
    data_class="synthetic-health-record",
    plaintext="Alice Example",
    version=1,
)
```

The authenticated associated data is the UTF-8 encoding of Python `json.dumps(..., sort_keys=True)` with these values, including the default spaces:

```json
{"class": "synthetic-health-record", "field": "patient_name", "subject": "patient-1", "version": 1}
```

Custody obtains or creates the subject/class DEK, unwraps it internally, and performs `AESGCM(dek).encrypt(nonce, plaintext_bytes, aad)`. `Alice Example` is 13 UTF-8 bytes, so `body` is 29 bytes: ciphertext plus the 16-byte tag. `nonce` is 12 bytes. The AAD is authenticated but not secret. Ciphertext bytes change on every run.

The wrapped DEK is a different ciphertext from the field body. Its AAD is a sorted JSON object containing `wrap: true`, subject and class. Wrapped DEKs, master seed and KEKs stay in the lab's custody object, outside SQL. The model receives none of these objects or credentials.

Decrypting verifies both the requested subject/field and the AEAD tag. Changing body, class or version fails. Restoring a complete old valid row is a different attack: AEAD alone does not prove freshness. Production needs authoritative versions and anti-rollback state outside the writable ciphertext row.

### 4.2 What encryption does and does not cover

The field lab encrypts values **before** sending them to SQL. It does not encrypt surrogate subject IDs, field names, classifications, versions or row counts. The default action backend stores status and JSONB evidence in clear. Redis JSON, Kafka imports, Spark memory and Iceberg text are also clear unless separately protected.

PostgreSQL passwords, TLS and disk encryption solve different problems. Use authenticated TLS for transport and approved disk/object encryption for files, WAL, backups, Kafka segments and Redis persistence. Neither replaces application field encryption when the database administrator should not read fields. PostgreSQL describes these distinct layers in its [encryption options](https://www.postgresql.org/docs/17/encryption-options.html).

The base Compose file uses plaintext Kafka listeners, Redis TCP and HTTP service endpoints. **The TLS overlay `deploy/compose.tls.yaml` encrypts PostgreSQL, Redis, Kafka and MinIO** and makes every client verify the server certificate and host name (section 9.5). Its PostgreSQL checksum setting detects storage corruption; it is not encryption. The control API, import gateway and Iceberg REST catalog stay plain HTTP on internal networks; put the first two behind a TLS-terminating reverse proxy. Do not describe even the TLS stack as encrypted end to end.

### 4.3 Durable key custody

`KeyCustody(master_seed=..., store=SqlCustodyStore.open(url))` keeps wrapped data keys, key-encryption-key generations, the erasure journal and destroyed subjects in their own tables. `EncryptedRecordSource(..., store=same_store)` keeps encrypted rows (nonce and ciphertext only). Both load at start-up and write through on every change; erasure, rotation and restore each commit in one transaction.

```python
from fssaira.custody_store import SqlCustodyStore, load_master_key
from fssaira.encrypted_records import EncryptedRecordSource
from fssaira.key_custody import KeyCustody

store = SqlCustodyStore.open("postgresql://…/custody")   # or sqlite:///custody.sqlite
custody = KeyCustody(master_seed=load_master_key("/run/secrets/custody-master.key"), store=store)
records = EncryptedRecordSource(field_classes, custody, writer_credential=w,
                                reader_credential=r, store=store)
```

The master key is **never** stored in the database. `load_master_key` reads 32 bytes (raw or hex) and refuses a file other users can read. The database alone yields only ciphertext and wrapped keys: opening it with a different master key fails with `CUSTODY_KEY_UNWRAP_FAILED`. Durable custody refuses to start without a master key rather than silently inventing one. `EvidenceNotary.from_key_file(path)` keeps the notary's signing key stable across restarts the same way. Keep the custody database, the master key file and the notary key apart from the application database and from each other where you can. This is software custody, not an HSM: someone holding both the database and the master key can decrypt.

## 5. Run the protected-data lab and inspect every stage

### 5.1 Local SQL run

From APP:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,privacy,postgres]'
.venv/bin/python scripts/pipeline_walkthrough.py --output work/pipeline-demo-01
```

Use a fresh output directory each time. The lab refuses to overwrite an earlier bundle. It uses real cryptography and SQLite storage with a scripted model. It creates four encrypted field rows, not a mock database response.

| File | What to inspect |
|---|---|
| `01-input.json` | The two synthetic source records |
| `02-encrypted-rows.json` | Actual nonce/body hex, subject, field, class, version, key generation |
| `03-model-values.json` | Only model-facing values, with session tokens replacing name and subject |
| `04-output.json` | Scripted tokenized output, actual released text and SHA-256 digest |
| `05-evidence.json` | Context/release decisions and their chained hashes |
| `06-checkpoint.json` | Ed25519-signed evidence count and head |
| `07-public-keys.json` | Public verification keys only |
| `report.json` | Checks, expected denial codes, backend and limits |
| `records.sqlite3` | SQLite ciphertext store; PostgreSQL mode instead retains rows on the server |

Expected released text:

```text
Access review prepared for Alice Example.
```

The model produced the same sentence with a `[[NAME_...]]` token. The gate restored the name only for `treating_clinician`. The exact token is random between runs; do not write tests that expect a fixed token or ciphertext.

The lab intentionally exports synthetic cleartext input and released text for learning. In a real system those exports would themselves need access controls, retention and encryption.

### 5.2 Run the same encryption and release against PostgreSQL

Use a disposable local database. This command creates a separate container and loopback-only port; credentials below are public lab credentials:

```bash
docker run -d --name fssaira-pipeline-lab \
  -e POSTGRES_PASSWORD=synthetic-local-lab-only \
  -e POSTGRES_DB=pipeline_lab \
  -p 127.0.0.1:55439:5432 postgres:17.6-alpine

docker exec fssaira-pipeline-lab pg_isready -U postgres -d pipeline_lab
# Continue when pg_isready reports accepting connections.
export PIPELINE_LAB_DSN='postgresql://postgres:synthetic-local-lab-only@127.0.0.1:55439/pipeline_lab'
.venv/bin/python scripts/pipeline_walkthrough.py --postgres --output work/pipeline-pg-01
```

The SQL source creates an isolated `pipeline_lab.encrypted_fields` table. Each invocation gets a unique `run_id`. It never modifies the normal `fssaira` control tables.

```sql
CREATE TABLE pipeline_lab.encrypted_fields (
  run_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  field TEXT NOT NULL,
  data_class TEXT NOT NULL,
  version INTEGER NOT NULL CHECK (version > 0),
  key_generation INTEGER NOT NULL,
  nonce BYTEA NOT NULL,
  body BYTEA NOT NULL,
  PRIMARY KEY (run_id, subject, field),
  CHECK (length(nonce) = 12),
  CHECK (length(body) >= 16)
);
```

In Python, SQL values are bound with psycopg `%s` parameters; binary values become PostgreSQL `BYTEA`. The application never sends the plaintext name or DEK to the insert. It reads the binary row back, reconstructs `Ciphertext`, and asks custody to decrypt. The database has no `pgcrypto` decryption function or key column. See PostgreSQL's [binary data types](https://www.postgresql.org/docs/17/datatype-binary.html).

Inspect the saved rows:

```bash
docker exec -i fssaira-pipeline-lab psql -U postgres -d pipeline_lab <<'SQL'
SELECT run_id, subject, field, data_class, version,
       octet_length(nonce) AS nonce_bytes,
       octet_length(body) AS ciphertext_and_tag_bytes,
       encode(nonce, 'hex') AS nonce_hex,
       encode(body, 'hex') AS body_hex
FROM pipeline_lab.encrypted_fields
ORDER BY run_id, subject, field;
SQL
```

For each run expect four rows, `nonce_bytes=12`, and Alice's `patient_name` body length of 29. The lab proves decryption before erasure, denies decryption after erasing patient-1, and proves patient-2 still decrypts. A negative literal search for Alice in a database file is only an additional observation, not proof of encryption or erasure.

**Persistence boundary:** SQL ciphertext survives the process, but this lab's custody, token vault, grants and notary signing key do not. It is an insert-only teaching adapter. For durable custody use `SqlCustodyStore` (section 4.3), which persists keys, the erasure journal and encrypted rows together. The lab also deliberately erases patient-1 before finishing. A second process cannot reopen its ciphertext with a newly generated master seed.

### 5.3 What each check establishes

| Check in `report.json` | Expected result | Meaning |
|---|---|---|
| `sql_roundtrip` | `true` | Fields were encrypted, saved, read and decrypted correctly |
| `ingest_cannot_decrypt` | `CUSTODY_OPERATION_NOT_PERMITTED` | Encrypt authority does not confer decrypt authority |
| `moved_ciphertext_denied` | `CUSTODY_CIPHERTEXT_BINDING_INVALID` | Another subject cannot be substituted |
| `tampered_ciphertext_denied` | Same binding error | Modified bytes fail authentication |
| `changed_version_denied` | Same binding error | Version is authenticated |
| `out_of_scope_subject_denied` | `SUBJECT_OUT_OF_SCOPE` | Patient-2 is outside the grant |
| `denied_before_sql_read` | `true` | That forbidden request never reached the record source |
| `model_values_tokenized` | `true` | Declared identity is absent from the model-facing values |
| `external_release_denied` | `RECIPIENT_CLASS_NOT_CLEARED` | External email is not cleared for these classes |
| `release_digest_matches` | `true` | Receipt digest binds to actual returned UTF-8 bytes |
| `release_after_revocation_denied` | `RELEASE_GRANT_NO_LONGER_CURRENT` | Existing output cannot bypass a revoked grant |
| `erased_sql_ciphertext_unreadable` | `CUSTODY_KEY_DESTROYED` | Live custody can no longer decrypt patient-1 |
| `other_subject_still_readable` | `true` | Erasure is scoped to one subject |
| `signed_checkpoint_valid` | `true` | Exported evidence matches the signed checkpoint |
| `truncated_evidence_denied` | `true` | Removing its tail is detected against that checkpoint |

## 6. How the governed read and release pipeline works

1. **Classify before storage.** The ingestion service maps each declared field to its policy class. Undeclared fields fail. Classification is a schema/policy decision; it is not inferred by an unrestricted model.
2. **Encrypt through a separate custody capability.** The ingest credential has only `encrypt`. The SQL writer receives ciphertext metadata and bytes. Production should make custody a separately authenticated service backed by managed keys/HSMs, not a Python object reachable in the model process.
3. **Issue scoped authority.** An authenticated policy owner issues a grant with holder, subject set, field set, classes, purpose, expiry and processing basis. Reference grants use HMAC. Institutional grant issuers can use the token-verifier integration instead.
4. **Check before fetching.** `DisclosureGate` checks current authority, grant signature, holder, fields, subjects, classes, purpose, consent, endpoint zone and relevant state. The lab counts source fetches to prove its denied subject request never touches records.
The default store-held consent model records withdrawals and permits a pair unless withdrawn. It is a teaching simplification, not evidence of affirmative consent. Connect the institution's authenticated basis/consent service and fail closed when its current decision is unavailable.

5. **Decrypt only authorized fields.** The trusted context gate's credential decrypts the requested SQL rows. Plaintext necessarily exists in the trusted gate's memory. Encrypting at rest does not remove this memory boundary.
6. **Tokenize identity.** `PrivacyGate` and `TokenVault` replace declared names and subject identifiers with session tokens. The reverse mapping is encrypted under the subject's custody keys. Matching across sessions by token is reduced; inference from content is still possible.
7. **Send the minimum model payload.** Send `context.values`, not the whole internal `ModelContext` object: its internal label can contain subject IDs. The lab's scripted model sees only those values. The HTTP privacy integration additionally uses a strict registry to check approved model identity and scope before model use.
8. **Treat the response as untrusted.** A model response is text/proposal, never a grant. Output derivation inherits the context's labels and grant provenance. Known identities in generated text are re-tokenized; detected undeclared contact details are refused.
9. **Recheck release.** Recipient class/purpose/zone and current grant/consent state are checked again. Requesting identity restoration adds a distinct entitlement check. A grant revoked after generation blocks release of the saved output.
10. **Return bytes and retain evidence.** The reference returns content to the authorized caller; it does not deliver email. Production delivery must authenticate the actual recipient and use an idempotent, audited channel. The restoration event includes `released_content_digest`, calculated over the actual restored UTF-8 content.

Example model input shape (token suffixes are illustrative):

```json
{
  "[[PATIENT_1A2B3C4D5E]].patient_name": "[[NAME_A1B2C3D4E5]]",
  "[[PATIENT_1A2B3C4D5E]].diagnosis": "SYNTHETIC-RECORD-A: access review only"
}
```

This is still sensitive context. Do not assume tokenization permits sending it to a public model: the `highly-restricted` label remains attached internally and restricts processing/release.

## 7. What the normal PostgreSQL control backend saves

The field-encryption lab table above is separate from the normal SQL backend in `src/fssaira/sql_backend.py`. The latter creates these tables under `fssaira`:

| Table | Key and important columns | Example/purpose |
|---|---|---|
| `resources` | `resource_id`, `status`, `version`, `updated_at` | `S-500`, `draft`, `1` before execution |
| `objects` | `(namespace,key)`, `value JSONB` | Namespaces `proposal`, `approval`, `review_session`, `review_endorsement`, `result` |
| `execution_results` | `request_id`, `resource_id`, `version`, `status`, `receipt_hash`, `created_at` | One durable result per logical execution request |
| `evidence` | `seq`, `ts`, `kind`, `payload JSONB`, `prev_hash`, `hash` | Decision/effect audit chain |
| `approval_uses` | `approval_id`, `request_id`, `bound_at` | Bind one approval to one request |
| `pending_outcomes` | `request_id`, `payload JSONB`, `created_at` | Recovery metadata where used |
| `counters` | `name`, `value` | Durable implementation counters |

A proposal records the exact operation, resource, expected state/version, target state and evidence reference. Human review creates a server-side review record; approval binds the reviewed proposal digest. The executor rejects changed content, stale versions, wrong roles and replay under incompatible content.

For SQL execution, the authoritative state transition, intent/outcome evidence and execution result share a transaction. A successful first request changes `draft/v1` to `ready_for_officer_review/v2`. Repeating the same request returns the original receipt with replay status and does not increment the resource to v3. PostgreSQL row locking is used; multi-writer serialization/retry qualification remains a separate deployment task.

**Events use a transactional outbox.** Every lifecycle event carries a stable `event_id` (`resource.registered:<id>`, `action.proposed:<request_id>`, `action.approved:<approval_id>`, `action.executed:<request_id>`). In the SQL profile, `SqlEventOutbox` writes each one to the `event_outbox` table, and `AtomicExecutor` writes `action.executed` inside the same transaction as the state change, receipt and evidence. `OutboxRelay` then publishes pending rows to Kafka in `seq` order, using the `event_id` as the trace ID, and stamps `published_at`.

| Situation | Before | Now |
|---|---|---|
| Kafka down during `execute` | State committed but the API returned an error, and the event was lost | Request succeeds; event waits in the outbox |
| Crash after commit, before publish | Event lost | Event is in the outbox; next relay publishes it |
| Replay of the same request | Second `action.executed` event | No new event (same `event_id`) |

During a broker outage, the first failed relay pauses inline attempts for `FSSAI_EVENT_RELAY_BACKOFF_SECONDS` (default 30), so requests do not each wait for the producer's delivery timeout. `POST /v1/recovery/reconcile` relays immediately regardless. When a delivery times out, the publisher purges its local queue so the client library does not deliver a stale copy later while the relay also resends it.

Delivery to Kafka is **at least once**: a crash between publishing and stamping, or two relays running together, can send an event twice. `EvidenceProjector` ignores an `event_id` it has already applied. `/health` and `/metrics` report `unpublished_events`, and `POST /v1/recovery/reconcile` relays the backlog.

```sql
SELECT seq, event_id, published_at IS NOT NULL AS published
FROM fssaira.event_outbox ORDER BY seq;
```

The Redis profile uses `RedisOutboxStore`: `RedisCaseRegister` writes `action.executed` in the same `MULTI/EXEC` as the transition, and the other events are written before publishing. The in-memory profile, when Kafka is configured, uses `MemoryOutboxStore`, which survives an outage but not a restart. With no Kafka configured, events are recorded as published at once, so `unpublished_events` stays 0. Published events older than `FSSAI_EVENT_OUTBOX_RETENTION_SECONDS` (default seven days) are pruned; unpublished ones are never pruned.

Use the existing API walkthrough:

```bash
.venv/bin/python scripts/api_walkthrough.py --self-test
# For an already running Compose API with generated credentials:
.venv/bin/python scripts/api_walkthrough.py --env-file deploy/.env
```

The self-test starts an isolated local API/SQLite path. It does not silently run PostgreSQL. For the full development stack, use `bootstrap_dev_env.py`, then Compose and `smoke_stack.py` as described in [PLATFORM.md](PLATFORM.md).

Within that stack, inspect PostgreSQL:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml exec postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT resource_id,status,version FROM fssaira.resources ORDER BY resource_id;"'
```

Or run in a psql session:

```sql
SELECT namespace, key FROM fssaira.objects ORDER BY namespace, key;
SELECT request_id, resource_id, version, receipt_hash FROM fssaira.execution_results;
SELECT seq, kind, prev_hash, hash FROM fssaira.evidence ORDER BY seq;
SELECT COUNT(*) FROM fssaira.pending_outcomes;
```

Do not dump `objects.value` or `evidence.payload` from real systems into shared logs. The current schema does not encrypt them. Disclosure state has its own optional store configured by `FSSAI_DISCLOSURE_STORE`; setting the main database URL does not make every privacy component persistent.

## 8. Exactly how Redis saves data

### 8.1 Selection: Redis is an alternative backend

`runtime_factory.build_control_plane()` chooses in this order:

```text
FSSAI_DATABASE_URL set?  -> SQL register, SQL objects, SQL evidence, AtomicExecutor
otherwise REDIS_URL set? -> Redis adapters and best-effort executor
otherwise               -> in-memory teaching stores
```

The actual variable is `FSSAI_REDIS_URL`. The Compose control API sets **both** database and Redis URLs, so its main control state uses PostgreSQL. A healthy Redis container or empty Redis keys is not evidence of a cache failure. No automatic PostgreSQL cache population, TTL cache-aside strategy or PostgreSQL/Redis synchronization is implemented.

### 8.2 Key-by-key layout

Default prefix: `fssaira`. The adapter uses standard Redis data structures, not the RedisJSON module.

| Key pattern | Redis type | Value and write operation |
|---|---|---|
| `fssaira:case:S-500` | String | JSON `{"status":"draft","version":1}` via `SET ... NX` on seed |
| `fssaira:result:req-500` | String | JSON execution result with request/case IDs, version, status, receipt hash and proposal digest |
| `fssaira:objects:proposal` | Hash | Field `req-500` → serialized proposal JSON (`HSET`/`HSETNX`) |
| `fssaira:objects:approval` | Hash | Request ID → serialized approval JSON |
| `fssaira:objects:review_session` | Hash | Review-session key → JSON server-recorded review state |
| `fssaira:objects:review_endorsement` | Hash | Request ID → endorsement JSON |
| `fssaira:objects:result` | Hash | Request ID → API result object; distinct from the register's replay-result string |
| `fssaira:approval-uses` | Hash | Approval ID → request ID, bound with `HSETNX` |
| `fssaira:pending-outcomes` | Hash | Request ID → pending-outcome JSON; `HDEL` after reconciliation |
| `fssaira:evidence` | List | One JSON `EvidenceRecord` per entry, appended with `RPUSH` |
| `fssaira:mutation-count` | String integer | Incremented once per committed new transition |

There are **no TTLs** on these authority/replay/evidence keys. Treating them as an ordinary evictable cache could lose replay protection and audit history. Do not share this authority store with an unconstrained cache; choose explicit memory limits, no-eviction behavior, access rules and monitored retention procedures.

### 8.3 Transition workflow in Redis

`RedisCaseRegister.transition()` performs:

```text
WATCH case-key result-key
  read existing request result
  if present: validate replay identity and return original receipt
  read case status/version
  reject missing case, stale version or wrong starting state
MULTI
  SET case-key new status/version JSON
  SET result-key execution-result JSON
  INCR mutation-count
EXEC
```

If another writer changes a watched key, `EXEC` fails and the code retries. Case state and replay receipt commit together in this transaction. The separate `RedisEvidenceLedger.append()` watches the evidence list, reads its length/head, constructs the next hash, and appends in another `MULTI/EXEC`. Therefore the entire effect plus intent/outcome ledger is **not** one Redis transaction. Pending-outcome reconciliation is necessary if execution succeeds while evidence recording fails. See Redis [transaction semantics](https://redis.io/docs/latest/develop/using-commands/transactions/).

The adapter's key patterns are not Redis Cluster hash-tagged. Do not switch to clustered Redis and assume multi-key transactions work unchanged; affected keys must share a slot and failover/recovery must be qualified. Retries are bounded: after `FSSAI_REDIS_MAX_ATTEMPTS` conflicts (default 64, with short jittered backoff) a transition fails closed with `STATE_CONTENTION` and writes nothing, and an evidence append raises `EVIDENCE_CONTENTION`, which the executor turns into a pending outcome for reconciliation. Monitor both codes.

### 8.4 Memory to disk: AOF and volume

Compose starts Redis with `--appendonly yes` and mounts `redis-data:/data`. Redis holds data structures in memory and writes the operation log to AOF files. The configured password controls access; it does not encrypt stored JSON or the AOF.

Compose does not set `appendfsync`; inspect the effective configuration. The usual `everysec` mode can lose roughly the most recent second of acknowledged writes after a severe failure. Choose durability to match authority/replay requirements and exercise restore. AOF rewriting compacts the persistence representation; it does not mean application evidence was erased. Details are in [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

### 8.5 Inspect Redis without scanning everything into a log

For the generated Compose development stack:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml exec redis \
  redis-cli --askpass
```

Enter the generated `REDIS_PASSWORD` from your private `deploy/.env` at the password prompt. The Compose Redis service does not export a `REDIS_PASSWORD` environment variable. At the Redis prompt, on synthetic data:

```text
SCAN 0 MATCH fssaira:* COUNT 100
TYPE fssaira:case:S-500
GET fssaira:case:S-500
HGET fssaira:objects:proposal req-500
GET fssaira:result:req-500
GET fssaira:mutation-count
HLEN fssaira:pending-outcomes
LLEN fssaira:evidence
LRANGE fssaira:evidence 0 2
CONFIG GET appendonly
CONFIG GET appendfsync
INFO persistence
```

Continue `SCAN` with the returned cursor until zero. Empty results are expected if PostgreSQL is selected. To exercise Redis independently, unset `FSSAI_DATABASE_URL` in a separate test process and set `FSSAI_REDIS_URL` plus a fresh `FSSAI_REDIS_PREFIX`. Do not redirect a running institution's authority store just to try this example.

A tiny reproducible synthetic storage example, against an already configured local test Redis:

```python
import os
from fssaira.redis_backend import connect_redis, RedisCaseRegister, RedisObjectStore
client = connect_redis(os.environ["PIPELINE_LAB_REDIS_URL"])
register = RedisCaseRegister(client, prefix="pipeline-lab")
objects = RedisObjectStore(client, prefix="pipeline-lab")
register.seed("S-500", status="draft", version=1)
objects.put("example", "req-500", {"synthetic": True, "resource_id": "S-500"})
assert register.get("S-500") == {"status": "draft", "version": 1}
assert objects.get("example", "req-500")["synthetic"] is True
```

This only demonstrates storage. The API/executor path supplies authorization, approval, transitions and reconciliation.

## 9. External data → import API → Kafka

### 9.1 Bootstrap the development services

```bash
.venv/bin/python scripts/bootstrap_dev_env.py
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d \
  postgres redis kafka control-api import-gateway
.venv/bin/python scripts/smoke_stack.py --env-file deploy/.env
```

Bootstrap generates local credentials. Read health warnings and keep the generated `.env` private. These commands operate on the existing Compose project name `fssaira`; use an isolated checkout/project for experiments if that stack is already in use. The smoke test checks action/replay behavior and the import API, not a running Spark sink.

### 9.2 Sign and send one document

This local script reads the configured source key without printing it, signs the **exact** text, and sends JSON to the gateway:

```bash
.venv/bin/python - <<'PY'
import hashlib, hmac, json, sys, urllib.request
from pathlib import Path
sys.path.insert(0, 'scripts')
from smoke_stack import load_env
env = load_env(Path('deploy/.env'))
keys = json.loads(env['FSSAI_IMPORT_SOURCE_KEYS_JSON'])
source = next(iter(keys))
data = 'Synthetic policy: access requests require an accountable reviewer.'
body = {'source': source, 'content_type': 'text/plain', 'data': data,
        'signature': hmac.new(keys[source].encode(), data.encode(), hashlib.sha256).hexdigest()}
request = urllib.request.Request('http://127.0.0.1:8081/v1/imports',
    data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(request, timeout=15) as response:
    print(response.status, response.read().decode())
PY
```

Expected: HTTP `202` and `{"status":"accepted","broker_offset":...}`. The gateway checks declared type, actual UTF-8 byte length and source HMAC. Bad provenance returns a quarantined response; successful validation removes known active-content patterns, computes the SHA-256 of **cleaned** text, writes `ingest_intent` to its low-side SQLite audit, publishes inward, then writes `ingest`.

A broker failure leaves an intent/failure record and no successful acceptance. A timeout can be ambiguous: publication may have succeeded before the response was lost.

**Use an `ingest_id` to make retries safe.** When a request includes `ingest_id` (1–128 characters of `A–Z a–z 0–9 . _ : -`), the signature must cover the ID, source, content type and data, computed with `ImportBoundary.sign_envelope`. The gateway authenticates first, then:

* first time: publishes and answers `202 accepted`;
* same ID, same content: answers `200 {"status":"duplicate","broker_offset":<original>}` and publishes nothing;
* same ID, different content: answers `409 conflict`.

Accepted IDs are stored in the audit SQLite (`FSSAI_IMPORT_AUDIT_PATH`), so they survive a gateway restart. An ID is remembered only after the broker acknowledges, so a failed publish can be retried. Requests without `ingest_id` keep the original data-only signature and are not deduplicated. The ID is also carried in the Kafka value. If the gateway itself loses the broker's acknowledgement, it can still publish twice; the ID lets downstream readers recognise that.

### 9.3 Kafka envelope and topic roles

Topic `fssaira.imports` carries:

```json
{
  "value": {
    "source": "configured-source-name",
    "text": "Synthetic policy: access requests require an accountable reviewer.",
    "stripped": [],
    "content_hash": "<64 hex SHA-256 characters of the cleaned text>"
  },
  "trace_id": "<generated trace reference>",
  "published_at": 1790035200.0
}
```

`trace_id`, timestamp and offset vary. Kafka key is the source name. The broker supplies topic, partition, offset and record timestamp; these are outside the JSON value. Ordering is within a partition, not global. A producer configured with `enable.idempotence=true`, `acks=all`, retries and bounded in-flight requests protects its own broker retries; it does not deduplicate a newly issued business request. See [Kafka producer configuration](https://kafka.apache.org/33/configuration/producer-configs/).

Topic `fssaira.events` carries control events shaped as `value: {kind, payload}`. It is separate from imported document text. `EvidenceProjector` builds a monitoring view from these events. After the replay fix it ignores already applied offsets per topic/partition in an ordered run. Its view and offset state are in memory; after restart it rebuilds from the beginning. `DurableEvidenceProjector(url)` stores the view, the applied `event_id`s and the next offset per partition in one transaction per event, so a restart resumes from `resume_offsets()` and a crash never leaves half an event applied.

### 9.4 Consumer acknowledgment and dead letters

`KafkaEventConsumer.run(handler)` commits the source offset synchronously only after the handler succeeds, or after a failed message is durably acknowledged by the dead-letter publisher. With no DLQ, or a failing DLQ, it raises and leaves the source uncommitted. Invalid UTF-8 follows this path too; the added regression test verifies it.

The low-level `poll()`/`stream()` helpers do not perform this full handler/commit/DLQ workflow; use `run()` or implement acknowledgment deliberately. The built-in DLQ uses the first subscribed topic plus `.dlq`; for strict per-topic handling use one topic per consumer. DLQ payloads can contain original content and error text, so they need the same classification, access and retention controls as the source.

Inspect a synthetic import:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml exec kafka \
  /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:29092 \
  --topic fssaira.imports --from-beginning --max-messages 1 \
  --property print.partition=true --property print.offset=true --property print.key=true
```

Compose uses one broker, replication factor 1 and 168-hour log retention. The log now lives on the `kafka-data` volume (`KAFKA_LOG_DIRS`). Previously the image wrote to `/tmp` inside the container, so every container recreate silently emptied Kafka and restarted offsets at zero. Upgrading an existing stack starts once from an empty log; the Spark start-up check in section 10.2 then asks you to raise the topic generation. `acks=all` on one broker is not multi-node durability. Retention can make replay impossible after a prolonged outage; Kafka is transport, not the sole evidence archive.

### 9.5 Encrypt service traffic with the TLS overlay

```bash
.venv/bin/python scripts/make_dev_certs.py --out deploy/certs     # git-ignored
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.tls.yaml \
  --profile analytics up --build -d
```

`make_dev_certs.py` creates a development CA and one certificate per service, named for its Compose host name, plus a Java truststore for Spark and the catalog. A one-shot `tls-init` service copies each private key into a volume owned by the user its server runs as. Then:

| Service | Server setting | Client setting |
|---|---|---|
| PostgreSQL | `ssl=on`; `pg_hba` allows `hostssl` only | `sslmode=verify-full&sslrootcert=/tls/ca.crt` in `FSSAI_DATABASE_URL` |
| Redis | TLS port only (`--port 0`) | `rediss://` URL plus `FSSAI_REDIS_CA_FILE` |
| Kafka | `INTERNAL` listener is `SSL` (PEM key and truststore) | `FSSAI_KAFKA_SECURITY_PROTOCOL=SSL`, `FSSAI_KAFKA_SSL_CA_LOCATION`; Spark reads the same variables |
| MinIO | `--certs-dir` | `https://minio:9000` endpoints; Java clients use the PKCS12 truststore |

What the live check showed (section 15): plain connections to all four are refused, TLS with the CA connects (PostgreSQL negotiated TLSv1.3), and a wrong host name or a missing CA is refused. Python 3.13 verifies strictly, which requires key identifiers in certificates; the generator adds them and `tests/test_service_tls_config.py` performs a real strict handshake.

Use the institution's CA and certificate rotation in a deployment. The development CA key sits in `deploy/certs/ca.key`; anyone with it can issue trusted certificates for this stack.

## 10. Kafka → Spark → Iceberg → MinIO: the data pipeline

### 10.1 What Spark actually does

The checked-in job `jobs/kafka_to_iceberg.py` is a micro-batch Structured Streaming application:

```text
subscribe to one Kafka import topic
    ↓ load value/key/partition/offset/timestamp
decode value bytes as JSON using ENVELOPE_SCHEMA
    ↓ preserve malformed rows for validation
select source, text, stripped, content_hash, trace_id,
       kafka_partition, kafka_offset, imported_at
    ↓ foreachBatch approximately every 10 seconds
reject missing required fields or a mismatching SHA-256
    ↓ drop duplicate partition/offset pairs inside batch
MERGE rows into sovereign.fssaira.imported_evidence
    ↓ commit Iceberg snapshot
Spark records source progress under checkpointLocation
```

The default trigger is a 10-second micro-batch that runs until stopped. Setting `FSSAI_AVAILABLE_NOW=true` switches to Spark's `availableNow` trigger instead: it processes every offset available at start-up, then stops. That is useful for tests and one-off catch-up runs.

`startingOffsets=earliest` applies when there is no existing checkpoint. A restart with the same checkpoint resumes its saved progress. `failOnDataLoss=true` prevents quietly skipping unavailable Kafka offsets. The job now fails the batch before writing when required fields/hash checks fail; it does not silently filter malformed JSON away.

The failure policy is deliberately stop-and-investigate. It does not yet have a Spark quarantine sink. A poison record will fail again on restart until an operator uses a reviewed repair/quarantine workflow. Do not “fix” the alert by deleting checkpoints or silently adding a filter.

### 10.2 Why `MERGE` matters

A crash can occur after an Iceberg commit but before Spark checkpoints the batch. Spark may replay that batch. `foreachBatch` provides at-least-once calls, so the job uses the source position as an idempotency key:

```sql
MERGE INTO sovereign.fssaira.imported_evidence target
USING fssaira_import_microbatch source
ON target.kafka_partition = source.kafka_partition
   AND target.kafka_offset = source.kafka_offset
WHEN NOT MATCHED THEN INSERT *;
```

The row identity is now **topic, topic generation, partition and offset**:

```sql
ON target.kafka_topic = source.kafka_topic
   AND target.topic_generation = source.topic_generation
   AND target.kafka_partition = source.kafka_partition
   AND target.kafka_offset = source.kafka_offset
```

`topic_generation` comes from `FSSAI_IMPORT_TOPIC_GENERATION` (default `1`). Kafka restarts offsets at zero when a topic is deleted and recreated, so raise the generation when you recreate one. Two checks now make a forgotten generation fail loudly instead of losing records silently (both were found and verified on a live stack):

* **At start-up**, `check_topic_continuity` compares the broker's earliest record and latest offset per partition with what the table stores for this generation. A different record at a stored position, or stored offsets beyond the broker's latest, stops the job with "the import topic was reset or recreated … Raise FSSAI_IMPORT_TOPIC_GENERATION". Without it, a restarted stream resumed from its old checkpoint and skipped the new topic's first records.
* **In each batch**, `position_conflicts` refuses to merge a record whose position is already stored with a different `trace_id` or hash. A genuine replay has the same `trace_id` and is skipped as before.

Each generation also gets its own checkpoint (`…/imports` for generation 1, `…/imports-g<N>` after), so a new generation always reads the topic from the beginning. The job still subscribes to exactly one topic. Tables created before this change are migrated by `bootstrap_iceberg.py`, which adds the two columns and backfills existing rows with the configured topic and generation. One writer per table is still the supported setup.

Checkpoint directory `/opt/fssaira/checkpoints/imports` is mounted on `spark-checkpoints`. It is Spark progress state, not a backup of source text or encryption keys. Do not share a checkpoint between different queries. Spark explains the `foreachBatch` replay contract in its [streaming guide](https://spark.apache.org/docs/3.5.6/structured-streaming-programming-guide.html).

### 10.3 Iceberg table rows and files

`bootstrap_iceberg.py` creates namespace `sovereign.fssaira` and three tables:

| Table | Schema/purpose | Populated automatically? |
|---|---|---|
| `imported_evidence` | Source/text/hash/trace plus Kafka partition/offset and timestamp; partitioned by day | Only after starting `kafka_to_iceberg.py` |
| `decision_evidence` | Sequence, time, kind, request ID, payload JSON, previous hash, hash, archive time | Explicit `archive_evidence()` call/integration required |
| `control_events` | Event kind, resource, payload JSON, trace, observation time | DDL exists; no default streaming population job |

Imported table DDL:

```sql
CREATE TABLE IF NOT EXISTS sovereign.fssaira.imported_evidence (
  source STRING NOT NULL,
  text STRING NOT NULL,
  stripped ARRAY<STRING>,
  content_hash STRING,
  trace_id STRING NOT NULL,
  kafka_partition INT NOT NULL,
  kafka_offset BIGINT NOT NULL,
  imported_at TIMESTAMP NOT NULL
) USING iceberg
PARTITIONED BY (days(imported_at))
TBLPROPERTIES ('format-version'='2');
```

The table name resolves through the REST catalog. Spark writes data files (typically Parquet with the runtime defaults), manifests describing file membership, a manifest list and new table metadata. A catalog commit advances the current metadata pointer atomically. Files live in the configured `s3://warehouse/` warehouse on MinIO. Do not hard-code generated object filenames; inspect table metadata and snapshot IDs. The [Iceberg specification](https://iceberg.apache.org/spec/) explains these layers.

A snapshot ID identifies a committed table view, not a wall-clock timestamp or a Kafka offset. Save the actual snapshot ID with a decision if you need to reconstruct its input. Old snapshots require their referenced files to remain available. Expiring snapshots or deleting orphan files must respect appeal and audit retention; see [Iceberg maintenance](https://iceberg.apache.org/docs/latest/maintenance/).

### 10.4 Start analytics with compatible binaries

The analytics profile is built from pinned, checksum-verified inputs. Starting it brings up five services in dependency order, with no manual bucket, bootstrap or `--packages` step:

| Order | Service | What it does | Pinned by |
|---|---|---|---|
| 1 | `minio` | Object store for Iceberg data and metadata files | Image digest |
| 2 | `minio-init` | Creates the `warehouse` bucket (`mc mb --ignore-existing`), then exits | Same image digest |
| 3 | `iceberg-rest` | REST catalog; its catalog database lives on the `catalog-data` volume | `deploy/Dockerfile.catalog`: `apache/iceberg-rest-fixture:1.9.1` by digest |
| 4 | `iceberg-bootstrap` | Waits up to 60 s for the catalog's `/v1/config`, creates `sovereign.fssaira` and its three tables, then exits | `deploy/Dockerfile.analytics` |
| 5 | `spark-iceberg` | Runs `jobs/kafka_to_iceberg.py` as its default command and restarts unless stopped | Same image as step 4 |

`deploy/Dockerfile.analytics` starts from `apache/spark:3.5.1-scala2.12-java17-python3-ubuntu`, pinned by digest (Spark 3.5.1, Scala 2.12.18, Java 17, **Python 3.10**). The earlier `3.5.1-python3` tag ships Python 3.8, on which the jobs cannot import the `fssaira` package (it requires Python 3.10+), so the bootstrap step always failed there. At **build time** it downloads the jars listed in `deploy/analytics/jars.lock.json` from Maven Central and rejects any whose SHA-512 does not match. The jars are the Iceberg Spark runtime 1.9.1 for Spark 3.5 and Scala 2.12, the Iceberg AWS bundle 1.9.1, `spark-sql-kafka-0-10_2.12` 3.5.1 and its token provider, `kafka-clients` 3.4.1 and `commons-pool2` 2.11.1. The build therefore needs internet access, and the running containers do not: they sit on the internal `data` and `catalog` networks.

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml \
  --profile analytics up --build -d

# Confirm the one-shot steps succeeded and the stream is running
docker compose --env-file deploy/.env -f deploy/compose.yaml ps -a \
  minio-init iceberg-bootstrap spark-iceberg
docker compose --env-file deploy/.env -f deploy/compose.yaml logs -f spark-iceberg

# Confirm the runtime versions match the lock file
docker compose --env-file deploy/.env -f deploy/compose.yaml exec spark-iceberg \
  /opt/spark/bin/spark-submit --version
```

`minio-init` and `iceberg-bootstrap` should show `Exited (0)`. A non-zero exit means `spark-iceberg` never started because it depends on both. If you change the Spark version, you must also change every Scala- and Spark-specific jar in the lock file. Mixing a Spark 3.5/Scala 2.12 runtime with a Spark 4.x/Scala 2.13 connector fails at run time.

**One-shot catch-up run.** Stop the long-running service first, because two queries must never share one checkpoint directory:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml stop spark-iceberg
docker compose --env-file deploy/.env -f deploy/compose.yaml --profile analytics \
  run --rm -e FSSAI_AVAILABLE_NOW=true spark-iceberg
docker compose --env-file deploy/.env -f deploy/compose.yaml start spark-iceberg
```

Do not loosen the internal-network policy to fetch dependencies at run time. If a jar is missing, fix the lock file and rebuild.

### 10.5 Query and verify the actual sink

Run these in an Iceberg-configured Spark session (`build_spark()` in `jobs/bootstrap_iceberg.py` supplies the configuration):

```python
import sys
sys.path.insert(0, '/opt/fssaira/jobs')
from bootstrap_iceberg import build_spark
spark = build_spark('pipeline-inspect')
spark.sql('''SELECT source, text, content_hash, trace_id,
                    kafka_partition, kafka_offset, imported_at
             FROM sovereign.fssaira.imported_evidence
             ORDER BY imported_at DESC''').show(truncate=False)
spark.sql('''SELECT kafka_partition, kafka_offset, COUNT(*) AS copies
             FROM sovereign.fssaira.imported_evidence
             GROUP BY kafka_partition, kafka_offset HAVING COUNT(*) > 1''').show()
spark.sql('''SELECT COUNT(*) AS bad_hashes
             FROM sovereign.fssaira.imported_evidence
             WHERE content_hash IS NULL OR content_hash <> sha2(text, 256)''').show()
spark.sql('''SELECT snapshot_id, committed_at, operation, summary
             FROM sovereign.fssaira.imported_evidence.snapshots
             ORDER BY committed_at''').show(truncate=False)
spark.stop()
```

Save that snippet as a job under APP/jobs or run in `pyspark` with the same catalog/runtime dependencies. Expect no duplicate-position rows and `bad_hashes=0`. Match source/trace/hash/partition/offset with the Kafka sample. An empty table is not success: verify that your specific input is present, that a new snapshot exists, and that the query is active without exceptions.

Use the actual numeric snapshot ID for time travel:

```sql
-- Replace 123456789 with an ID returned by this table's snapshots query.
SELECT * FROM sovereign.fssaira.imported_evidence VERSION AS OF 123456789;
```

A controlled replay test reuses the same input positions and confirms row count does not increase. Do it in a disposable topic/table/checkpoint. Restarting an up-to-date stream with no new input is useful for recovery checks but does not prove it replayed a committed batch.

## 11. Evidence archive and independent output verification

### 11.1 Output bytes, policy and execution are different checks

Verify four things separately:

1. **Bytes:** Recompute the released UTF-8 SHA-256 and compare the final restoration receipt. This proves matching content, not that the content is true.
2. **Authority:** Verify the relevant grant, approval, class/purpose/recipient constraints and their current versions. A valid hash does not grant permission.
3. **Effect:** Query authoritative resource state and replay receipt. An API `200` alone is insufficient evidence of a durable, single effect.
4. **History:** Recompute the hash chain and compare against an independently trusted signed checkpoint. A valid internal chain does not prove the author told the truth.

The new lab exports everything necessary for a second process to verify its output and signed checkpoint:

```bash
.venv/bin/python - <<'PY'
import hashlib, json
from pathlib import Path
from fssaira.evidence import EvidenceRecord
from fssaira.evidence_notary import Checkpoint, verify_against_checkpoint
p = Path('work/pipeline-demo-01')
def load(name):
    return json.loads((p / name).read_text())
out = load('04-output.json')
assert hashlib.sha256(out['released_content'].encode('utf-8')).hexdigest() == out['sha256']
records = [EvidenceRecord(**r) for r in load('05-evidence.json')]
checkpoint = Checkpoint(**load('06-checkpoint.json'))
keys = {k: bytes.fromhex(v) for k, v in load('07-public-keys.json').items()}
assert verify_against_checkpoint(records, checkpoint, keys).valid
assert not verify_against_checkpoint(records[:-1], checkpoint, keys).valid
print('Released bytes and signed checkpoint verified; tail deletion rejected.')
PY
```

For teaching, the public key and checkpoint are in the same bundle. In production, pin the public key and retain fresh checkpoints in an independently controlled service. An attacker able to replace the whole bundle, including its public key, can make their own bundle verify. The lab's one process simulates the notary role; it does not establish organizational separation.

### 11.2 Moving evidence to Iceberg is explicit

`iceberg_backend.archive_evidence(ledger, store)` converts each ledger record into a `decision_evidence` row and appends it through `IcebergSnapshotStore`. It returns a snapshot ID, record count, a content manifest digest and the ledger's internal verification result. It does not automatically run with the streaming import job.

`archive_evidence(ledger, store, ledger_id="primary")` is incremental and safe to re-run. Rows are keyed by `(ledger_id, seq)`, so several ledgers can share the table. Each call reads the highest archived `seq` for that ledger and then:

| Archive state | Result |
|---|---|
| Behind the ledger, hashes agree | Appends only the newer records |
| Level with the ledger | Appends nothing and creates no snapshot |
| Ahead of the ledger | Refuses with `ARCHIVE_AHEAD_OF_LEDGER` (the primary was truncated) |
| Same `seq`, different hash | Refuses with `ARCHIVE_DIVERGED` (the primary was rewritten) |

The report includes `records`, `first_seq`, `last_seq` and the snapshot ID. Run one archiver per `ledger_id`: Iceberg appends do not conflict, so two concurrent archivers could append the same records, which the verifier below reports as duplicates. Existing tables gain the `ledger_id` column through bootstrap, with old rows backfilled as `primary`.

### 11.3 Spark evidence verification

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml exec spark-iceberg \
  /opt/spark/bin/spark-submit /opt/fssaira/jobs/verify_evidence_chain.py
```

The job reads one ledger (`--ledger-id`, default `primary`), recomputes hashes and links, and reports sequence gaps and **duplicate `seq` values**. On its own it checks internal consistency only, so a contiguous but shorter archive passes and `tail_truncation_checked` is `false`.

Give it a signed checkpoint retained outside the archive and it also detects a deleted tail or a rewritten history:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml exec spark-iceberg \
  /opt/spark/bin/spark-submit /opt/fssaira/jobs/verify_evidence_chain.py \
  --checkpoint /path/to/06-checkpoint.json --public-keys /path/to/07-public-keys.json
```

With a checkpoint the report sets `tail_truncation_checked: true` and adds `checkpoint.code` (`CHECKPOINT_VALID`, `LEDGER_TRUNCATED`, `HISTORY_REWRITTEN` or a signature error). `--since-seq` trusts the first returned predecessor and cannot be combined with `--checkpoint`. An empty table reports `EMPTY`, which is not proof of a successful archive. The checking logic is `verify_rows()`, which is tested without Spark in `tests/test_verify_evidence_chain.py`.

The current verifier collects records to the driver. For large archives, implement distributed verification with partition-boundary checks and authenticated checkpoint comparison; do not assume this teaching verifier scales to an unlimited ledger.

## 12. Failure and recovery walkthrough

| Failure point | Observable result | Safe recovery / what to verify |
|---|---|---|
| Undeclared field or bad import HMAC | Rejected before accepted record | Correct producer schema/credential; inspect quarantine metadata |
| Ciphertext byte/AAD modified | Custody binding error | Isolate corrupted row; restore authenticated ciphertext/version from approved source |
| Wrong subject or purpose | Context denied | Verify grant scope; do not broaden automatically |
| PostgreSQL write interrupted before commit | Transaction rolls back | Retry same logical request and inspect state/result |
| PostgreSQL commit succeeds, API response lost | Client is uncertain | Retry original request ID; same receipt and one version increment |
| PostgreSQL commits, Kafka publish fails | Request succeeds; `unpublished_events` > 0 | Event waits in `event_outbox`; relay publishes it on the next event or `POST /v1/recovery/reconcile` |
| Redis process restarts | Recovery depends on AOF/volume/fsync | Verify case, result, approval binding, evidence and pending outcomes together |
| Redis mutation succeeds, evidence append fails | Pending outcome / incomplete evidence path | Run reconciliation and match receipt; Redis is not SQL's atomic profile |
| Kafka redelivers an event | Same topic/partition/offset | Idempotent handler; fixed in-memory projector does not double count |
| DLQ publish fails | Source offset stays uncommitted | Restore DLQ availability; retry without acknowledging loss |
| Malformed import / mismatched cleaned-text hash in Spark | Batch fails before sink/checkpoint | Investigate; approved quarantine/repair required; no silent row dropping |
| Iceberg commit succeeds, checkpoint fails | Batch can replay | MERGE same source positions; no duplicate row in the single-writer scope |
| Kafka retention removes unread offsets | Stream fails due to data loss | Recover from an independent source/archive; do not silently set failOnDataLoss=false |
| MinIO bucket/files missing | Catalog/write/read errors | Restore required objects and metadata; a snapshot ID alone cannot recover bytes |
| Grant/consent revoked after generation | Release denied | Reauthorize through the institutional process; saved output does not retain permission |
| Custody process lost in this lab | Ciphertext remains but keys are gone | The lab is ephemeral by design. With `SqlCustodyStore` and the master key file, a restarted process reads the same data; without the master key it cannot |
| Kafka container recreated | Previously: empty topic, offsets restart at 0 | Log is on the volume now; if a topic is still reset, the Spark start-up check stops and asks for a new generation |
| Old key backup restored after erasure | Risk of reintroducing DEKs | Replay authenticated current erasure journal with independent freshness watermark |
| Evidence tail deleted | Plain chain may still verify | Compare signed count/head from independent custody |

Cryptographic erasure cannot retract plaintext already released to people, screenshots, provider logs or memory outside the governed custody boundary. Production needs a copy inventory covering SQL replicas/WAL/backups, Redis persistence, Kafka/DLQs, Iceberg snapshots, token mappings, vector indexes, export files, logs and model caches. Record what was tested unreadable, what was absent and what remains unverified.

## 13. Build a similar system: implementation sequence

### Phase A — Establish the contract and identities

Choose one use case, one authoritative resource and one allowed state transition. Declare fields/classes, purpose, consent/processing basis, approved model zones, recipient classes, manual fallback and named policy owners. Keep actor identity separate from request JSON. Use institutional OIDC/workload identities and scoped service roles.

Create a schema/version contract for source records and event envelopes. Include tenant/source namespace, stable ingest/request IDs, event kind, schema version and authenticated provenance. The example's simpler schemas are not a multi-tenant protocol.

### Phase B — Implement the protected data plane

Use a KMS/HSM or audited custody service. Generate independent per-subject/class DEKs, wrap them with managed KEKs, persist wrapped-key identifiers/generations and ciphertext atomically where required, and keep KEKs out of application databases. Implement authenticated AAD serialization, nonce-use budgets, version freshness, rotation and backup restoration. KEK rewrapping does not rotate the DEK or re-encrypt field ciphertext; if a DEK is compromised, the response is different.

Persist token mappings encrypted, bind them to sessions/tenants and define expiry. Enforce purpose/field/subject checks before decrypting. Expose the model-facing values through a narrow serializer, never the custody object or full internal label. Verify runtime identity and route only to allowed zones.

### Phase C — Implement operational state and events

Choose PostgreSQL when state and evidence can share a transaction. Use migrations and separate least-privilege roles for state mutation, evidence append, audit read and schema administration. The example DDL creator is not a complete role-provisioning system. Append-only application behavior does not prevent a database superuser rewriting history.

Use Redis only for explicitly chosen responsibilities. If it becomes a cache, design invalidation and avoid treating a stale grant cache as current authority. If it remains the authority backend, preserve replay keys and qualify persistence/recovery. Keep the SQL profile's transactional event outbox and run the relay; remember delivery is at least once and deduplicate on `event_id`.

### Phase D — Implement analytics and evidence retention

Choose a compatible, pinned Spark/Scala/Iceberg/connector set. Define one immutable source identity per sink or extend the sink schema. Provision catalog and bucket, start the stream, validate malformed inputs, record checkpoints, test replay and monitor consumer lag. Use stable event IDs for repeated business submissions, not only broker positions.

Separate operational imports from decision-evidence archives. Give archives independent access/retention controls; protect Iceberg metadata as well as data files. Sign and retain evidence checkpoints outside the writer's administration. Test backup restoration and erasure against retained snapshots.

### Phase E — Verify before extending

Run positive and negative tests for unauthorized fields, wrong tenant/subject, stale versions, tampering, replay, expired/revoked authority, unapproved models, unentitled recipients, unavailable stores and lost acknowledgments. Record actual commands, environment versions and raw results. Add load/concurrency/failover tests for the chosen deployment; local SQLite and parser tests are narrower evidence.

## 14. Corrections made and remaining implementation gaps

| Finding | Change or explicit remaining requirement |
|---|---|
| No single example showed source values → ciphertext SQL rows → tokenized model values → restored output | Added fixture, runnable SQLite/PostgreSQL lab and exported stage artifacts |
| Redis role could be mistaken for a PostgreSQL cache | Documented runtime selection, actual key structures, AOF, transactions and recovery limits |
| Kafka monitoring projection double-counted delivered offsets | Added per-topic/partition high-water deduplication for ordered in-memory projection and regression test |
| Invalid UTF-8 dead-letter handling lacked a focused regression | Added a test confirming existing durable DLQ-before-commit behavior |
| Spark silently filtered malformed JSON envelopes | Preserve rows; reject missing required values or wrong content hash before sink write |
| Spark sink identity omitted topic | Enforce one subscribed topic; document immutable topic/table lifetime; generalized identity migration remains open |
| Guide hard-coded a connector without checking quickstart runtime | Replaced fixed-version assumption with version inspection and compatibility instructions |
| Hash chain described as detecting all deletion | Corrected ledger/PostgreSQL/Spark descriptions; added signed-checkpoint truncation demonstration |
| `all` optional dependencies omitted explicit privacy package | Added `cryptography` to the `all` extra |
| Duplicate software citation files disagreed on release date | Aligned application citation metadata with the repository-root citation |
| Sensitive record/vault/key persistence was not wired to default PostgreSQL | **Fixed in code.** `SqlCustodyStore` persists wrapped keys, generations, erasure journal and encrypted rows (SQLite and PostgreSQL, verified live); master key and notary key load from owner-only files. The token vault stays session-scoped by design |
| PostgreSQL and Kafka are not one commit | **Fixed in code.** `event_outbox` table written in the state transaction, `OutboxRelay`, stable `event_id`s, projector deduplication, backlog on `/health` and `/metrics` (`tests/test_event_outbox.py`) |
| Iceberg archives can append duplicate full ledgers | **Fixed in code.** `ledger_id` column, incremental archive from the high-water mark, refusal on truncation or divergence (`tests/test_iceberg_backend.py`) |
| Spark sink identity omitted topic and topic generation | **Fixed in code.** MERGE key is topic, generation, partition, offset; bootstrap migrates and backfills old tables |
| Spark evidence verifier could not detect a deleted tail or duplicates | **Fixed in code.** Duplicate `seq` detection and optional signed-checkpoint verification (`tests/test_verify_evidence_chain.py`) |
| Import gateway could publish a retried request twice | **Fixed in code.** Optional signed `ingest_id`; duplicate and conflict answers; IDs survive restart |
| Redis retries were unbounded | **Fixed in code.** Bounded retry budget with backoff; fail closed with `STATE_CONTENTION` |
| Quickstart bucket/catalog/dependency provisioning incomplete | Compose now pins MinIO and the catalog by digest, builds Spark 3.5.1 with SHA-512-locked jars, creates the bucket and tables automatically, persists the catalog database, and starts the stream (section 10.4). It has now been run end to end (section 15), which found and fixed a Python 3.8 base image that made bootstrap fail. Qualification under load and failover remains open |
| Walkthrough did not say how the three workflows relate | Added section 0: one mental model, a tool-to-workflow map, the one implemented join (`/v1/propose-task` with governed context) and the joins that do not exist yet |
| Service transports were plaintext | **Fixed as an overlay.** `deploy/compose.tls.yaml` + `scripts/make_dev_certs.py`: PostgreSQL, Redis, Kafka and MinIO accept only TLS; clients verify CA and host name (verified live, including refusals). Stored operational JSON is still not field-encrypted |
| Redis and in-memory profiles published events directly | **Fixed in code.** `RedisOutboxStore` (written in the transition's MULTI/EXEC) and `MemoryOutboxStore`; published events pruned after `FSSAI_EVENT_OUTBOX_RETENTION_SECONDS` |
| Monitoring projection lost its view and position on restart | **Fixed in code.** `DurableEvidenceProjector` |
| Kafka stored its log in the container, not on its volume | **Fixed.** `KAFKA_LOG_DIRS` on the volume, fixed `CLUSTER_ID` |
| Spark could silently skip records after a topic reset | **Fixed in code.** Start-up continuity check, per-batch position-conflict check, per-generation checkpoints |

This is an implementation walkthrough and a bounded set of repairs, not a claim that all production gaps are closed. The broader [gap register](GAPS.md), [privacy reference limits](PRIVACY_REFERENCE.md) and [security guide](SECURITY.md) remain applicable.

## 15. Verification commands and evidence scope

```bash
.venv/bin/python -m pytest tests/test_pipeline_walkthrough.py tests/test_kafka_backend.py \
  tests/test_privacy_custody.py tests/test_privacy_integration.py tests/test_iceberg_backend.py
.venv/bin/python -m pytest tests/test_spark_imports.py
.venv/bin/python scripts/check_public_docs.py
.venv/bin/python -m ruff check src tests scripts jobs adapters
```

The Spark test needs PySpark and Java and otherwise reports a skip. It uses a real local Spark parser/validator; it does not qualify Kafka-to-Iceberg delivery. Record skips explicitly. The PostgreSQL lab must also be executed with `--postgres` to support a PostgreSQL storage claim.

Keep separate evidence for (a) SQLite lab, (b) real PostgreSQL lab, (c) Redis adapter behavior, (d) Kafka broker consumption/replay, (e) real Spark parsing, and (f) a complete live Kafka/Iceberg stack. One successful category must not be reported as all six.

### Recorded validation for this revision

Executed on 22 September 2026 against a modified working tree based on commit
`58362212b25ceeaec6b593b5a1b9e6a2725c5d66`:

| Check | Observed result |
|---|---|
| Full public Python suite | **1,353 passed, 2 skipped, 82 manuscript checks deselected** |
| Local SQLite encrypted-field lab | Four encrypted rows; all 15 reported checks passed |
| Real PostgreSQL 17.6 encrypted-field lab | Four `BYTEA` field rows; all 15 reported checks passed |
| Real Redis 8.2.9 action and replay | One mutation, same replay receipt, valid evidence; recovered after a normal container restart |
| Real Spark 3.5.1 / Scala 2.12 / Java 17 parser tests | Two tests passed, including malformed and hash-tampered input refusal |
| Python lint | Passed for source, tests, scripts, jobs and adapters |
| Documentation links/anchors | Passed across 54 maintained Markdown documents |
| Complete live Kafka → Spark → Iceberg stack | **Passed** in the live Compose analytics stack; details below |
| Production KMS, failover, power-loss, concurrent-writer and physical recipient-delivery qualification | **Not established by these checks** |

The two skipped tests in the default Python environment are the Spark tests
executed separately in the Spark container. Its 3.5.1 runtime is a parser-test
runtime, not a claim that the unpinned analytics Compose images use that version.
Private manuscripts were outside this public-runtime test run. Sample bundles
contain synthetic data and public verification keys; no private signing/custody
keys are exported.

### Recorded validation for the gap-closure revision

Executed on 23 September 2026 on a working tree based on commit `775c53f`, against the live Compose analytics stack: Kafka, the signed import gateway, MinIO, Iceberg REST catalog 1.9.1 and the rebuilt Spark 3.5.1 / Scala 2.12 / Java 17 analytics image. All data was synthetic.

| Check | Observed result |
|---|---|
| Analytics bootstrap on the previous `3.5.1-python3` image | **Failed**: Python 3.8 cannot import `fssaira`. Fixed by the base-image change in section 10.4 |
| Bootstrap on the new image | Namespace and three tables created |
| Signed import with `ingest_id`, then identical retry, then same ID with other text | `202 accepted` (offset 0), `200 duplicate` (offset 0), `409 conflict`. Kafka topic held exactly the accepted messages |
| Kafka → Spark → Iceberg stream | Both accepted documents present with `kafka_topic` and `topic_generation`; 0 bad hashes; 0 duplicate keys |
| Replay of every committed offset with a fresh checkpoint | Spark re-read both records; row count stayed 2 |
| Migration of an old-schema `imported_evidence` table | Two columns added; existing row backfilled with topic and generation; second bootstrap run changed nothing |
| Spark parser tests inside the analytics image | 3 passed |
| Incremental evidence archive through pyiceberg 0.9.1 | 3 records, then 0 on re-run (same snapshot), then 1; truncated primary refused with `ARCHIVE_AHEAD_OF_LEDGER` |
| Spark verifier with signed checkpoint | `INTACT` / `CHECKPOINT_VALID`; after deleting the archived tail row: `COMPROMISED` / `LEDGER_TRUNCATED`, exit code 2 |
| Smoke test and outbox on PostgreSQL | Passed; 4 outbox events, all published; 4 messages on `fssaira.events` despite a replayed request |
| Full action workflow with Kafka stopped | Passed (state changed once, same receipt on retry, chain valid); 4 events pending. First attempt took 711 s, which led to the relay back-off and producer purge; after those fixes the same workflow took 10 s |
| Kafka restarted, then `POST /v1/recovery/reconcile` | `events_relayed: 4`, `unpublished_events: 0`. Before the purge fix the topic held 5 extra copies; after it, exactly one copy per event |
| Fresh signed HTTP import through gateway | `202 accepted`, Kafka offset 0; the envelope contained `trace_id=672ea0c44fc9f580` and a SHA-256 `content_hash` |
| Independent Spark verifier against Iceberg | `trace_rows=1`, `bad_hashes=0`, `duplicate_kafka_positions=0`, `snapshot_count=2`, verdict **PASS** |
| Spark restart and checkpoint recovery | Container restarted cleanly; rerunning the verifier returned **PASS** with the same snapshot and no duplicate source position |

Not covered by this run: multi-broker Kafka, PostgreSQL failover, concurrent writers and sustained load.

### Recorded validation for the open-items revision

Executed on 23 September 2026 against a second live stack (`-p fssaira-tls`) started with `deploy/compose.tls.yaml`, and against a disposable PostgreSQL 17 container. All data was synthetic.

| Check | Observed result |
|---|---|
| TLS stack start-up | All services healthy; `tls-init` installed keys; bootstrap reached MinIO over HTTPS |
| PostgreSQL | Plain connection rejected by `pg_hba`; `verify-full` connected with TLSv1.3; wrong host name refused |
| Redis | Plain connection reset; TLS with CA connected; TLS without CA refused. First attempt **failed** because generated certificates lacked key identifiers that Python 3.13's strict verification requires; fixed in the generator and covered by a strict-handshake test |
| Kafka | Plain producer timed out; TLS producer delivered; Spark's Kafka client ran with `security.protocol = SSL` and a PEM truststore |
| MinIO | Plain HTTP answered `400` (HTTP to HTTPS port); HTTPS with CA `200`; HTTPS without CA refused |
| Smoke test over TLS | Passed; 4 outbox events, all published |
| Signed import over TLS into Iceberg | Row present, read back over HTTPS S3 |
| Kafka container recreated (old config) | **Defect found:** topic emptied and offsets restarted at 0, because the log was in `/tmp` inside the container. Spark then silently skipped a new document at a reused offset |
| Kafka recreated after the `KAFKA_LOG_DIRS` fix | Offsets 0–1 present before and after (`fssaira.imports:0:2` both times) |
| Per-batch position guard | Reused position with different record: batch refused with the reset message |
| Start-up continuity check | Generation 1 after a reset: job refused to start, nothing written. Before this check, a restarted stream resumed from a stale checkpoint and lost "Persistence probe one" |
| Generation raised to 3 | New checkpoint `imports-g3`; both probe documents written, including the one previously lost |
| Durable custody on PostgreSQL 17 | Data readable after restart; rotation (generation 2) and erasure persisted; other subject unaffected; only custody tables created; plaintext absent from `pg_dump` |

The live run used a disposable topic named `fssaira_imports_final` and checkpoint
directory `/opt/fssaira/checkpoints/final`. The topic name is deliberately paired
with its checkpoint and the Iceberg source-position columns
(`kafka_topic`, `topic_generation`, `kafka_partition`, `kafka_offset`). If a topic
is deleted and recreated, increment `FSSAI_IMPORT_TOPIC_GENERATION`; otherwise an
offset such as zero could describe two different log histories. The failed
attempts against earlier disposable topics contained malformed test messages and
were intentionally refused before an Iceberg commit; they are not evidence of a
successful production run.

After inspecting your disposable database, cleanup of the **lab container you created** is optional:

```bash
docker stop fssaira-pipeline-lab
docker rm -v fssaira-pipeline-lab
```

Do not use these names against an existing service, and do not use `docker compose down -v` on a shared environment. Preserve your evidence bundle before deleting test storage.
