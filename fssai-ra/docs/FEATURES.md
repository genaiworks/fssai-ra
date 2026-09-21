# Feature catalogue

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Follow the [user guide](USER_GUIDE.md) for a walkthrough or the [research guide](RESEARCH_GUIDE.md) to record an experiment.

This catalogue covers the maintained implementation areas. Commands below run from the **inner `fssai-ra/` directory** after installation and environment activation. For syntax and outputs, use [Commands](COMMANDS.md). A component being present does not mean it is enabled in every runtime.

## Policy, authority, and accountable actions

| Feature | Purpose and use | Entry point / evidence | Boundary |
|---|---|---|---|
| Domain profiles | Declare permitted transitions, reviewer roles, ownership, and data obligations | `fssaira profiles`; [Domain packs](DOMAIN_PACKS.md); `tests/test_domain_packs.py` | Synthetic profiles do not validate a sector's real policy |
| Seven-field control contract | Connect an asset and operation to enforcement, owner, test, evidence, and recovery | `fssaira contract`; `fssaira validate-contract contract`; [Specification](SPECIFICATION.md) | Written requirements need executable or explicitly attested bindings |
| Contract coverage | Find requirements with no implementation evidence | `fssaira coverage`; `contract/bindings/`; `tests/test_coverage.py` | A locator existing is weaker than running its behavioral test |
| Exact-action approval | Reject changed payloads, stale versions, unauthorized roles, and replay | `exact_action.py`, `control_plane.py`; `tests/test_exact_action.py` | Correct authorization does not establish source truth or fairness |
| Atomic execution | Couple supported state transitions and evidence under a transaction | `atomic_execution.py`; `tests/test_atomic_execution.py` | Guarantees depend on backend; remote effects need reconciliation |
| Joined workflow | Exercise read, confirmation, approval, action, release, revocation, and appeal together | `python scripts/joined_demo.py --output work/joined-01`; [Walkthrough](../audit/QUICKSTART.md) | Synthetic identities, real local SQLite effects, trusted host |
| Delegation | Restrict authority through every ancestor and test chain attacks | `fssaira delegation`; `tests/test_delegation.py` | Component experiment and SDK composition have distinct fixtures |
| Human oversight | Explore queue capacity, deliberation floors, escalation, and overload | `fssaira oversight profiles/student_support.yaml --sweep`; [Calculator](oversight/index.html) | Declared simulation; no observed reviewer-performance claim |
| Assisted review | Compare dependent and independent reviewer-assistant assumptions | `fssaira assisted-review`; `tests/test_assisted_review.py` | Configured independence is not measured cognitive independence |

## Data access, privacy, and evidence

| Feature | Purpose and use | Entry point / evidence | Boundary |
|---|---|---|---|
| Governed disclosure | Bind reads/releases to subject, fields, purpose, consent, recipient, and region | `fssaira disclosure profiles/healthcare_record_access.yaml`; [Disclosure](GOVERNED_DISCLOSURE.md) | Authorized access can still expose sensitive information to an authorized party |
| Labels and declassification | Preserve restrictions after reading/derivation; require explicit release authority | `disclosure.py`, `disclosure_tokens.py`; `tests/test_disclosure.py` | Labels and trusted adapters must cover every real path |
| Persistent disclosure state | Exercise durable grants, consent, stateful behavior, and concurrency | `disclosure_store.py`; `tests/test_disclosure_production.py`, `tests/test_disclosure_tokens_and_concurrency.py` | Backend tests do not qualify an institution's deployment |
| Tokenized privacy profile | Encrypt reference records, tokenize declared identifiers, gate entitled restoration | [Privacy reference](PRIVACY_REFERENCE.md); `tests/test_privacy_integration.py` | Opt-in, memory reference; not universal anonymization or persistent key custody |
| Import boundary | Validate imported bytes, provenance, limits, signatures, and quarantine behavior | `import_boundary.py`, `import_api.py`; `tests/test_import_api.py` | Accepted content remains untrusted; authenticity is not truth |
| One-way transport | Model a low-side send / high-side receive seam | `fssaira diode inventory`; [Diode deployment](DIODE_DEPLOYMENT.md) | Software transport does not prove physical directionality |
| Evidence chain | Record and check ordered evidence and retained checkpoints | `fssaira evidence verify PATH`; `evidence.py`, `evidence_notary.py` | Tamper evidence needs a trusted anchor outside an attacker's control |
| Decision packets | Export/inspect a bounded decision record with an expected digest | `fssaira packet-check PATH --expected-sha256 DIGEST`; `tests/test_decision_packet.py` | Unanchored inspection exits 2; integrity is not policy correctness |
| Reproducible data | Bind derived evidence to data snapshots and transformations | `reproducible_data.py`, `jobs/`; [Platform](PLATFORM.md) | External storage and analytics need their own configuration and validation |

## SDK: tasks, cooperating agents, and Guardian

Start with `python scripts/tbc_demo.py --output work/sdk-01` and [TBC SDK](TBC_SDK.md). The components below live in `src/fssaira/tbc/`; `tests/test_tbc_sdk.py` exercises their behavior.

| Feature | What it does | What to inspect |
|---|---|---|
| Workload Passport | Declares approved models, resources, tools, destinations, budgets, and interface inventory | `profiles/tbc/education-passport.json` |
| Task Contract | Narrows a workload to a purpose, subject, resource, expiry, and budget | `profiles/tbc/education-task.json` |
| Capability envelope | Intersects task, identity, Passport, ancestors, and current runtime restrictions | Lease issuance and request dispatch |
| Context gateway | Authorizes reads and charges cumulative context bytes | Context authorization and denied out-of-scope reads |
| Governed memory | Preserves provenance, labels, purpose, expiry, and source validity across storage | Persist/read/invalidate memory paths |
| Typed effects | Uses fixed operation schemas and exact approvals | Proposal → confirmation → approval → execution |
| Release escrow | Binds approved bytes to digest, recipient, expiry, epoch, and single use | Release authorization and recipient collection |
| Population governor | Limits child scopes, depth, identity counts, and shared budgets | Spawn and cumulative budget tests |
| Labelled messaging | Prevents messages from creating authority or stripping data restrictions | Sender/recipient checks and inherited labels |
| Graph checks | Look for prohibited routes in the declared communication graph | Concrete counterexample paths |
| Guardian | Contracts permissions through NORMAL, RESTRICTED, PROPOSAL_ONLY, READ_ONLY, QUARANTINED | Revocation, stale-epoch denials, named restoration |
| SDK client and HTTP adapter | Exposes a model-facing request boundary | `SDKClient`, `POST /v1/tbc/request` |

The SDK is a trusted local service. It does not isolate hostile code running under the same OS identity, observe undeclared channels, or measure provider billing/GPU usage. Memory expiry is not guaranteed physical erasure. Administrative enrollment, approval, and restoration must be separately protected.

## Integration and deployment

| Feature | Purpose and use | Entry point / evidence | Boundary |
|---|---|---|---|
| FastAPI control plane | Inspect governance, propose/review/execute, and inspect evidence | `fssaira serve`; [API schema](openapi.json) | Teaching defaults are not institutional identity management |
| Operator console | Show deployment findings, governance, actions, intelligence, evidence, assurance | [Console](../console/README.md) | Client-side UI grants no independent authority |
| Model adapters | Exercise deterministic/adversarial fixtures or configured local/compatible services | `fssaira model list`; `models/`; `tests/test_models_and_plugins.py` | External adapters can make network calls; model proposals remain untrusted |
| Backend registry | Discover and replace implementations of defined ports | `fssaira plugins`; `ports.py`, `plugins.py` | Every replacement needs conformance evidence |
| Storage | Memory, SQLite, PostgreSQL, and Redis paths for supported components | `sql_backend.py`, `postgres_backend.py`, `redis_backend.py` | Redis/best-effort behavior differs from transactional execution |
| Event and analytics adapters | Kafka transport, Spark jobs, Iceberg snapshots, object storage | `kafka_backend.py`, `iceberg_backend.py`, `adapters/`, `jobs/` | Optional infrastructure, not exercised by the dependency-free demo |
| Qualified transport | Fetch independently approved artifact bytes using destination and integrity controls | [Developer guide](../DEVELOPER_GUIDE.md); `tests/test_qualified_transport.py` | Network policy and independently supplied expected hashes remain obligations |
| Tool supply chain | Bind approved tool-server identities and definitions | `integration/tool_servers.py`; `tests/test_tool_supply_chain.py` | A tool description is not permission |
| Remote-effect ledger | Keep lost/queued acknowledgements uncertain until authoritative reconciliation | `remote_effects.py`; `tests/test_remote_effects.py` | It does not manufacture provider idempotency or approval |
| Federation | Exercise bounded cross-service authority mechanisms | `federation.py`; `tests/test_federation.py` | Does not imply a qualified distributed production deployment |
| Telemetry and isolation probes | Expose observations and measure deployment prerequisites | `telemetry.py`, `isolation.py`; `make qualify` | Findings apply to the measured host, identity, and configuration |

## Experiments and learning tools

| Tool | Run or open | How to interpret it |
|---|---|---|
| Authored attacks, utility, ablations | `fssaira evaluate profiles/student_support.yaml` | Inspect forbidden effects and legitimate completion together |
| Bounded model checking | `fssaira verify profiles/student_support.yaml` | Exhaustive only within the declared bounded model |
| Backend conformance | `fssaira conformance --backend sql` | Port behavior under that backend/configuration |
| Thread/process races and recovery | `fssaira race-test profiles/student_support.yaml`; `fssaira resilience profiles/student_support.yaml` | Local concurrency/restart evidence, not arbitrary distributed exactly-once proof |
| Open adversary corpus | `fssaira challenge`; [Challenges](../challenges/README.md) | Disclose authorship and external contribution counts |
| Threat catalogue | `fssaira threats`; [Security](SECURITY.md) | Distinguish contained, bounded, and residual classes |
| Mediation falsifiers | `fssaira thesis` | Attempt specified counterexamples; not a universal theorem |
| Education failure lab | `fssaira conference lab` | Browser attack exercise under a historical command name |
| Stateful/adaptive attacks | `fssaira conference stateful`; `fssaira conference adaptive` | Report seeds, budgets, splits, controls, and search limits |
| Covert-channel measurements | `python scripts/measure_covert_channels.py --check` | Declared channel model; inspect remaining bandwidth assumptions |
| Institutional pilot record | `fssaira pilot-check PATH`; [Pilot protocol](PILOT_PROTOCOL.md) | Checks record structure, not successful institutional adoption |
| Authority worksheet | [Open worksheet](worksheet/index.html) | Translate one real capability into seven accountable fields |
| Oversight calculator | [Open calculator](oversight/index.html) | Explore declared staffing assumptions, not measured human capacity |
| Facilitated workshop | [Lab guide](LAB.md), [System literacy](SYSTEM_LITERACY.md) | Teach transfer and critique; learning benefit needs a study |

Use [Assurance](ASSURANCE.md), [Architecture review](ARCHITECTURE_REVIEW.md), and [Gaps](GAPS.md) to inspect claims that require evidence beyond these local experiments.
