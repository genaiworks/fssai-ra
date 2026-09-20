# Trust by Construction SDK

**Documentation navigation:** [Documentation map](README.md) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)

**Recommended next:** Follow the [extension guide](EXTENDING.md) to bind the reference to an institutional adapter.

The `fssaira.tbc` package implements the mechanisms specified in TBC v11 as a persistent, local reference service. The supplied Word paper is preserved unchanged in `paper/tbc-v11/TBC_v11.docx`. The implementation manifest binds thirteen architectural mechanisms to code and behavioral tests. Existing component benchmarks retain their original denominators; they are not measurements of this new composition.

## Run the engineering demonstration

From `fssai-ra/`, using the existing development environment:

```sh
.venv/bin/python scripts/tbc_demo.py --output /tmp/tbc-demo-new
.venv/bin/python -m pytest tests/test_tbc_sdk.py tests/test_tbc_alignment.py
.venv/bin/python scripts/check_tbc_alignment.py
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
| SDK integration | `SDKClient`, `tbc/api.py` | Transport-independent model client and optional HTTP endpoint; administrative grant/approval/restoration APIs are not exposed on the model endpoint |

## Authority and transaction model

Only `TrustRuntime.dispatch(agent_token, raw_json)` is an untrusted request boundary. The runtime, adapter code, SQLite connection, enrollment and administrative credentials belong to the trusted service. Model outputs are data for this interface. They cannot supply a Passport, change their identity, forge lineage, register a tool, insert an approval, execute SQL or select an arbitrary URL.

The service checks all ancestors on every use. A child has an opaque identity token and a subset of its parent's current scope, with an expiry no later than its parent. Child calls consume the same task and workload balances. Enrollment of another task does not reset the workload balance. Population limits count all identities ever enrolled in the workload, including expired identities, so churn cannot multiply the lifetime allowance. Resetting these bounds is an explicit administrative lifecycle decision, not a model primitive.

`BEGIN IMMEDIATE` serializes authorization, balance consumption, immutable object creation, record effects, release-use consumption and evidence. A denied authenticated attempt consumes one call and receives a denial receipt, while a savepoint rolls back its effects and other resource charges. If evidence is unavailable, the whole transaction rolls back. Anonymous ingress needs deployment rate limiting. Independent-process tests exercise both exhausted shared budgets and concurrent use of one escrow approval. A release is a committed local sink record; `collect_release` returns that record only to the matching recipient identity. This is not a network-delivery protocol or an exactly-once guarantee for remote APIs.

The existing `joined_workflow.Workflow` performs the actual domain mutation and its version/replay checks. TBC databases carry a persistent mediator marker; opening them through the default legacy workflow fails. This prevents accidentally serving the same database through the older JSON dispatcher. A trusted process that can change code or directly read SQLite is still inside the security boundary.

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

## Maintenance and paper synchronization

`paper/tbc-v11/implementation.json` records the unchanged Word file's SHA-256, paragraph anchors, implementation symbols, behavioral test functions and the scope of every binding. `scripts/check_tbc_alignment.py` checks those bindings and compares the Passport inventory with the dispatcher. Pytest executes the bound behavior separately; a locator existing is not itself proof that a claim holds.

When adding a primitive, update the parser, enforcement branch, Passport inventory, tests and mapping together. When changing the paper, review its new claims and update the source hash and anchors deliberately. Do not mechanically refresh the hash to make CI pass. Existing paper figures remain governed by `scripts/generate_results.py --check` and `tests/test_paper_alignment.py`.

## Qualification boundaries

This implementation closes the missing application mechanisms as an executable local reference. It does not establish production security. The current domain adapter supports the synthetic correction workflow; general institutional policies and third-party orchestrators need separately tested adapters. The example contract expiry is illustrative and must be replaced when enrolling a real task.

Compute units meter deterministic adapter input bytes. Memory and traffic budgets measure serialized bytes. No external billing occurs, so the reference has no nonzero cost-producing adapter; GPU time, provider invoices, preemption and arbitrary-code execution are not measured. Memory retention is access expiry, not guaranteed physical erasure of database pages or backups. Object MACs and the evidence key reside in the trusted local service, not an HSM. Distributed revocation, live model identity attestation, remote exactly-once effects, independent red teaming and human-review effectiveness require additional deployment evidence. The application tests must not be used to claim these properties.
