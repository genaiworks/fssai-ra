# Architecture in code: kernel, planes, mediators and lifecycle

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Reference architecture](REFERENCE_ARCHITECTURE.md) · [Deployment](DEPLOYMENT.md) · [Pack authoring](PACK_AUTHORING.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Engineers continue to [Pack authoring](PACK_AUTHORING.md) to add a sector, then [Deployment](DEPLOYMENT.md) to promote it.

[`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) explains the pattern.
This page shows where each part of the pattern is enforced in the repository,
and which command or test fails if the enforcement goes away. Every row below is
checked by code. None is a description kept up to date by hand.

## The thesis and two rules

**Intelligence is untrusted; power and data are mediated.**

| Rule | Mediator (sole holder of) | Code | What fails if it is broken |
|---|---|---|---|
| 1. A model may propose an action; it cannot manufacture the authority to execute it | Executor (the write credential) | `fssaira.mediators.executor` → `exact_action.AccountableExecutor`, `atomic_execution.AtomicExecutor`, `accountable_action.PolicyEnforcementPoint` | `tests/mediators/test_mediator_executor.py` (identical decision under five rationale variants, with a positive control) |
| 2. A model may request information; it cannot manufacture the entitlement to see it, or launder what it saw | Context gate (record access and data keys) | `fssaira.mediators.context_gate` → `disclosure.DisclosureGate`, `privacy_pipeline.PrivacyGate` | `tests/mediators/test_mediator_context_gate.py`, `tests/test_disclosure.py` |

The mediator modules are names for the one implementation of each mediator. A
test fails if either module ever grows logic of its own.

## The kernel

What no domain pack may replace.

| Module | Responsibility | Gate |
|---|---|---|
| `kernel/contract.py` | Seven-field capability contracts. An empty field is an open governance decision; a named failure test must exist as an exact pytest node | `fssaira contract --gate` |
| `kernel/claims.py` | Claims register: `machine_verified`, `attested`, `unverified` | `fssaira contract --gate` (`claims_register_no_unverified`) |
| `kernel/state_machine.py` | Nine effect states; uncertain effects are reconciled, never retried; compensation needs its own authorization | `tests/kernel/test_kernel_state_machine.py` (all 81 state pairs) |
| `kernel/evidence.py` | Hash-chained ledger and a checkpoint signed by a key the writer does not hold | `tests/test_conference_falsification.py` |
| `kernel/invariants.py` | Action invariants INV-1..5 and delegation invariants under bounded enumeration | `fssaira verify`, `fssaira delegation` |
| `kernel/packs.py` | Domain-pack loader, cross-check against enforced configuration, kernel floor | `fssaira pack` |
| `kernel/assurance.py` | A backend inherits no assurance until conformance passes on its exact implementation | `fssaira promote` |

## Seven planes and two mediators

`fssaira.planes.ALL_PLANES` declares each plane's responsibility, its components
and its must-NOT list. Every prohibition names a pytest node, and
`tests/planes/test_planes.py` fails if that node does not exist or a component
does not import.

| Plane | Kind | Components (examples) |
|---|---|---|
| boundary | trusted | `ImportBoundary`, `OneWayChannel`, `UdpDiodeReceiver` |
| data | trusted | `EncryptedRecordSource`, `SnapshotStore`, `EventLog` |
| intelligence | **untrusted** | `SemanticRouter`, `BoundedAgent`, `TaskRouter` |
| authority | trusted | `AsymmetricApprovalAuthority`, `DelegationAuthority`, `GrantAuthority`, `ModelRegistry`, `KeyCustody` |
| execution | **mediator** | `AccountableExecutor`, `AtomicExecutor`, `PolicyEnforcementPoint` |
| context_gate | **mediator** | `DisclosureGate`, `PrivacyGate`, `TokenVault` |
| evidence | trusted | `EvidenceLedger`, `EvidenceNotary` |
| resilience | trusted | `EffectRecord`, `PendingOutcomeStore`, `BoundedReviewQueue` |

`fssaira bind` fails if any untrusted component takes a key, token or credential
in its constructor, or if a live agent holds the evidence write credential. The
first run of this check found that the agent had been handed that credential and
never used it. The credential was removed.

**Logical planes are not process isolation.** Hostile code running as the same
OS user can bypass every in-process check. See [Deployment](DEPLOYMENT.md).

## GenAI integration contract

A future model, orchestrator or tool plugs into typed interfaces in
`fssaira.integration`. It never plugs into the kernel.

| Module | Contract |
|---|---|
| `integration/typed.py` | Proposals and context requests admit bounded structures, enumerated operations and canonical IDs. The server derives principal, policy version, classification and authority |
| `integration/retrieval.py` | Retrieval is a protected read: every chunk comes from `DisclosureGate.assemble_context`, so the label on a retrieved context is always the gate's, never one the orchestrator computed. Provenance and the gate-issued value id survive chunking and ranking |
| `integration/memory.py` | Memory, caches, summaries, vector entries and handoffs carry their originating label and retention |
| `integration/bundle.py` | A model change is a versioned bundle that must be re-attested; a self-reported digest is not evidence |
| `integration/streaming.py` | A streamed response is a sequence of disclosures that stops on revocation |
| `integration/sandbox.py` | Generated code runs in a separate, resource-bounded process with no inherited secrets. This is containment, not a security boundary |

## One governed request in ten steps

`admit → protect → route → entitle → reason → authorize → execute → release →
record → recover`. Only *reason* runs untrusted intelligence, and it yields a
proposal or draft. `fssaira.governed_request.STEPS` runs the path over the
education world, and `joined_workflow.py` runs the durable SQLite slice.

## The lifecycle

| Stage | Command | Gate |
|---|---|---|
| 1 Frame | `fssaira frame frame.yaml` | One capability; asset, harm, owner and manual fallback named |
| 2 Contract | `fssaira contract --gate` | Seven fields filled; every failure test exists; no unverified claim |
| 3 Pack | `fssaira pack packs/<sector>.pack.yaml` | Manifest agrees with enforced configuration; kernel floor passes |
| 4 Bind | `fssaira bind` | No model holds a key or credential |
| 5 Falsify | `fssaira falsify` | Zero counterexamples, a live positive control, ablations restore harm |
| 6 Promote | `fssaira promote --profile deploy/profiles/<p>.yaml` | Every gate the deployment profile requires; conformance current; evidence matches a fresh run |
| 7 Operate | `fssaira operate` | Reconciliation, revocation and review-capacity status |

## Extending without touching the kernel

- **A new sector** is a new profile plus `packs/<sector>.pack.yaml`. See [Pack authoring](PACK_AUTHORING.md).
- **A new model** is a new re-attested bundle.
- **A new backend** is an adapter that passes the conformance suite on its exact implementation digest.

In each case the kernel and mediator source are unchanged, and a test hashes
them to prove it.
