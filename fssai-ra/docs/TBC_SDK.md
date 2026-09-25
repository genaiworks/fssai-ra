# Trust by Construction SDK

**Documentation navigation:** [Documentation map](README.md) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)

**Recommended next:** Follow the [extension guide](EXTENDING.md) to bind the reference to an institutional adapter.

The `fssaira.tbc` package implements the mechanisms specified in TBC v11 as a persistent, local reference service. Historical Word manuscripts and their alignment manifests are local-only. The public Passport, runtime, and behavioral tests are sufficient to reproduce the SDK without those files. Existing component benchmarks retain their original denominators; they are not measurements of this new composition.

## Run the engineering demonstration

From `fssai-ra/`, using the existing development environment:

```sh
.venv/bin/python scripts/tbc_demo.py --output /tmp/tbc-demo-new
.venv/bin/python -m pytest tests/test_tbc_sdk.py tests/test_sdk_inventory.py
.venv/bin/python scripts/check_sdk_inventory.py
```

Choose a new output directory on each demo run. The demo writes a real SQLite database and a JSON report. It uses generated bearer tokens, synthetic records, a deterministic summarizer and simulated named source/reviewer identities. It makes no network request and does not use a model provider. The assertions examine committed records, recipient bytes, memory labels, stored authority state and evidence integrity.

The demo executes: enroll task → issue short-lived capability → authorize context → invoke bounded summarizer → persist and reauthorize memory → spawn a narrower child → send and receive a labelled message → propose a typed record correction → obtain independent source confirmation → approve the exact proposal → revalidate and commit → approve exact release bytes → deliver to an independently authenticated recipient → contract authority → reject the old lease → restore through a named operator → issue a fresh lease.

## Components and enforcement

| Paper mechanism | Implementation | Enforcement behavior |
|---|---|---|
| Workload Passport | `tbc/contracts.py`, `profiles/tbc/education-passport.json` | Strict schema, approved models, classes, zones, tools, resources, destinations, operations, channels, memory namespaces, budgets and default-deny interface inventory |
| Task Contract | `TaskContract`, `TrustRuntime.create_task` | Purpose, subject, resource, expiry and budget; enrollment requires operator authority and intersects trusted identity/data rights |
| Dynamic Capability Envelope | `TrustRuntime._agent`, capability dispatch | Passport ∩ task ∩ identity ∩ every ancestor ∩ current runtime scope ∩ Guardian mode; budget and TTL checked in the same transaction |
| Context Security Gateway | `request_context` | Checks canonical resource and classification before reading; charges cumulative bytes before returning data |
| Memory Gateway | `persist_memory`, `read_memory` | Authenticated immutable objects, provenance, purpose, namespace, retention expiry, epoch and source reauthorization |
| Typed AI-IR | `propose_effect`, `execute_effect` | Fixed operation, canonical resource, expected version, desired state and destination; references independent source confirmation and exact approval |
| Data Lineage Firewall | `TrustRuntime._taint` | Monotone session classification and source union; summaries, generated text, memory and messages cannot erase restrictions |
| Release Escrow | `authorize_release`, `release_artifact`, `collect_release` | Named review of exact digest/destination; expiry, epoch, explicit declassification and single use; authenticated recipient collection |
| Agent Census and population governor | `census`, `spawn_agent`, `_charge` | Persistent identity/parent/task/model/zone/expiry; attenuation, depth, lifetime population ceiling and shared task/workload budgets |
| Semantic Airlock | `send_message`, `receive_message` | Typed channels, recipient rights, inherited labels, epoch, live sender and source validation; text never grants authority |
| Security Digital Twin | `Guardian._evaluate_locked` | Declared agent/message graph, transitive reachability and concrete source-to-public counterexample paths |
| Guardian | `Guardian`, `TrustRuntime.restore` | Five nested modes, contraction, ancestor revocation, configuration drift detection; restoration requires named operator authority and fresh leases |
| Decision receipts | `decision_receipts`, `prune_receipts` | Every model request, allowed or denied, and every fan-in acceptance writes an integrity-checked receipt binding policy version, Passport digest, task epoch, source lineage, artifact digest, recipient, outcome and stable refusal code. Receipts carry identifiers and digests, not record text; only operator or monitor authority reads them, and a configured retention horizon prunes them |
| Shared budget reservations | `reserve_budget`, `settle_reservation`, `cancel_reservation` | A trusted scheduler reserves from the one task and workload balance before dispatching parallel workers; settlement returns unused budget, cancellation returns all of it, and a reservation settles at most once |
| Declared task graph (P10) | `admit_graph`, `task_graph` | Opt-in per task. Once declared, an agent acts only after operator admission as a node, and a message crosses only an admitted (source, target, channel) edge; replanning is a further admission. Tasks without a declaration behave as before |
| Fan-in gate | `accept_result` | Before a coordinator accepts a worker result: object MAC and exact expected digest, a live producer in the same task, the current epoch, admitted edge when a graph is declared, labels within the coordinator's data rights, unquarantined sources and a permitted destination |
| Task revocation epoch | `Guardian.revoke_task` | Raises the task epoch so queued proposals and approvals, stale leases, escrows and later release chunks fail revalidation; disclosed bytes are not recalled |
| Freshness proofs | `issue_freshness`, `check_freshness` | An adapter committing outside the mediator's transaction rejects a proof whose epoch moved, whose task stopped or quarantined, or which is older than its bound; a partitioned worker without a fresh proof must stop |
| Minimum review time | `TrustRuntime(min_deliberation_seconds=...)`, `manual_queue` | An approval issued sooner than the floor after its proposal is refused with `REVIEW_DEFERRED_TO_MANUAL` and recorded on a manual route; the default floor of 0 keeps previous behaviour |
| SDK integration | `SDKClient`, `tbc/api.py` | Transport-independent model client and optional HTTP endpoint; administrative grant/approval/restoration APIs are not exposed on the model endpoint |

## Authority and transaction model

Only `TrustRuntime.dispatch(agent_token, raw_json)` is an untrusted request boundary. The runtime, adapter code, SQLite connection, enrollment and administrative credentials belong to the trusted service. Model outputs are data for this interface. They cannot supply a Passport, change their identity, forge lineage, register a tool, insert an approval, execute SQL or select an arbitrary URL.

The service checks all ancestors on every use. A child has an opaque identity token and a subset of its parent's current scope, with an expiry no later than its parent. Child calls consume the same task and workload balances. Enrollment of another task does not reset the workload balance. Population limits count all identities ever enrolled in the workload, including expired identities, so churn cannot multiply the lifetime allowance. Resetting these bounds is an explicit administrative lifecycle decision, not a model primitive.

`BEGIN IMMEDIATE` serializes authorization, balance consumption, immutable object creation, record effects, release-use consumption and evidence. A denied authenticated attempt consumes one call and receives a denial receipt, while a savepoint rolls back its effects and other resource charges. If evidence is unavailable, the whole transaction rolls back. Anonymous ingress needs deployment rate limiting. Independent-process tests exercise both exhausted shared budgets and concurrent use of one escrow approval. A release is a committed local sink record; `collect_release` returns that record only to the matching recipient identity. This is not a network-delivery protocol or an exactly-once guarantee for remote APIs.

The existing `joined_workflow.Workflow` performs the actual domain mutation and its version/replay checks. TBC databases carry a persistent mediator marker; opening them through the default legacy workflow fails. This prevents accidentally serving the same database through the older JSON dispatcher. A trusted process that can change code or directly read SQLite is still inside the security boundary.

## Composition controls

The controls above the SDK row implement the composition contract in the V27 paper. None adds a model primitive, so the Passport inventory and dispatcher schemas are unchanged; all are trusted-side calls under operator, reviewer or monitor authority. Reservations, admission, fan-in acceptance and freshness proofs are issued by the control service, never by agent output. Agreement among agents is not an input to any of them. Distributed enforcement across separate control services, remote exactly-once effects and the manual-route outcome itself remain outside what these local tests show; `tests/test_tbc_composition_controls.py` exercises each refusal.

## Model-side client

```python
from fssaira.tbc import SDKClient

# transport(agent_token, raw_json) must call the isolated mediation service.
client = SDKClient(transport, provisioned_agent_token)
client.request_capability(ttl=60)
context = client.request_context("campus/s1")
summary = client.invoke_tool("summarize", context["artifact"], max_chars=256)
memory = client.persist_memory(summary["artifact"], "task-notes", retention=60)
proposal = client.propose_effect(
    context["context"], "correct_transcript", "B", "recipient"
)
# Independent source confirmation and human approval occur outside this client.
result = client.execute_effect(proposal["proposal"], independently_issued_approval)
client.release_artifact(result["artifact"], "recipient", independently_issued_escrow)
```

Generated text goes through `derive_artifact`; the service adds the agent's accumulated labels and sources. The caller cannot submit a lower classification or omit a source. Directly model-generated rationales are not evidence or authority. The built-in `summarize` tool is deterministic truncation, and `classify` returns existing labels; neither is an LLM or semantic security classifier. A real model may propose these JSON requests through the transport without receiving the service object or database credentials.

## Optional HTTP deployment boundary

Install the existing `api` extra if it is not available. Provision the Passport, task and agent identity through a trusted administrative process, then create the model-facing application:

```python
from fssaira.tbc.api import create_app

app = create_app(database_path, validated_passport)
```

Serve it with the deployment's ASGI runner. Requests use `POST /v1/tbc/request`, an `Authorization: Bearer <agent-token>` header and the primitive's JSON fields. The adapter caps request bodies, passes raw JSON to the duplicate-key-rejecting parser, and opens one SQLite connection per request. It does not expose task enrollment, source confirmation, human approval, recipient collection or restoration. Bind those through separately authenticated institutional services; do not add model-accessible wrappers around them.

Run the mediator under a different service identity from model workers, deny worker access to the SQLite file and signing material, and enforce worker filesystem and network restrictions at the OS/container boundary. The SDK cannot enforce host isolation against arbitrary Python with the same UID. All registered tools in this reference are local and network-free; its network class is therefore no network. A destination such as `public` is a classification of a logical sink, not an enabled Internet connection.

## Guardian operation

The modes form nested allowed-operation sets:

- NORMAL permits the installed scope.
- RESTRICTED removes tool invocation, spawning and message sending.
- PROPOSAL_ONLY also removes execution, release and memory writes.
- READ_ONLY allows context and memory reads, received messages and restricted lease requests.
- QUARANTINED permits no model operations.

A contraction can further narrow any scope axis and increments the task epoch. Old leases, effect proposals, memory authorizations, messages and escrow approvals cannot cross that epoch. A named operator may restore the original task ceiling, but cannot revive old leases or reset budgets through restoration. Ancestor revocation remains effective after restoration.

Graph checks run inside every model request and before committing a new message edge. They consider both actual session labels and potential protected reads, so even a clean handshake is rejected if the resulting channel creates a future source-to-public route. On an already-present prohibited graph or changed stored Passport, the Guardian commits quarantine and denies the pending request. It emits the actual path as a counterexample. It observes only the declared topology: deployment events for new external channels must be imported by trusted adapters before those channels become usable.

## Maintenance and optional manuscript synchronization

The public `scripts/check_sdk_inventory.py` checks Passport, SDK, and dispatcher agreement. To check a private historical manuscript as well, use `make manuscript-check` with the required local archives.

The local-only `paper/tbc-v11/implementation.json` records the unchanged Word file's SHA-256, paragraph anchors, implementation symbols, behavioral test functions and the scope of every binding. `scripts/check_tbc_alignment.py` checks those bindings and compares the Passport inventory with the dispatcher. Pytest executes the bound behavior separately; a locator existing is not itself proof that a claim holds.

When adding a primitive, update the parser, enforcement branch, Passport inventory, tests and mapping together. When changing the paper, review its new claims and update the source hash and anchors deliberately. Do not mechanically refresh the hash to make CI pass. Existing paper figures remain governed by `scripts/generate_results.py --check` and `tests/test_paper_alignment.py`.

## Qualification boundaries

This implementation closes the missing application mechanisms as an executable local reference. It does not establish production security. The current domain adapter supports the synthetic correction workflow; general institutional policies and third-party orchestrators need separately tested adapters. The example contract expiry is illustrative and must be replaced when enrolling a real task.

Compute units meter deterministic adapter input bytes. Memory and traffic budgets measure serialized bytes. No external billing occurs, so the reference has no nonzero cost-producing adapter; GPU time, provider invoices, preemption and arbitrary-code execution are not measured. Memory retention is access expiry, not guaranteed physical erasure of database pages or backups. Object MACs and the evidence key reside in the trusted local service, not an HSM. Distributed revocation, live model identity attestation, remote exactly-once effects, independent red teaming and human-review effectiveness require additional deployment evidence. The application tests must not be used to claim these properties.
