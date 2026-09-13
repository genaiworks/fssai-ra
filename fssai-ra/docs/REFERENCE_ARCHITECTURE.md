# Trust by Construction Reference Architecture

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Domain packs](DOMAIN_PACKS.md) · [Platform mapping](PLATFORM.md) · [Security model](SECURITY.md) · [Assurance](ASSURANCE.md)
>
> **Recommended next:** Policy leaders continue to [Procurement](PROCUREMENT.md). Engineers continue to [Platform mapping](PLATFORM.md).

## Purpose

Trust by Construction is a cross-sector pattern for AI systems that read sensitive
data, recommend consequential actions, delegate work, or operate tools. It is
intended for corporations, healthcare organizations, universities, public bodies,
and other institutions whose AI systems can affect access, records, rights,
resources, safety, or disclosure.

The architecture begins with one rule:

> **A model may propose an action. It cannot manufacture the authority to
> execute it.**

The model is not the governed unit. The governed unit is the end-to-end system
that imports data, derives context, produces a proposal, delegates capability,
authorizes an action, changes an authoritative resource, records the result, and
recovers when the result is uncertain.

This document defines the stable pattern. [`PLATFORM.md`](PLATFORM.md) shows one
implementation using Python, FastAPI, PostgreSQL or Redis, Kafka, PySpark,
Iceberg, object storage, local-model adapters, signing, and a one-way boundary
seam. Those products are replaceable. The responsibilities and invariants below
are the portable framework.

## Intended use and limits

Use this reference architecture to:

- frame an AI system before selecting products;
- translate policy duties into enforceable interfaces;
- review or procure one consequential capability;
- separate model inference from institutional authority;
- build a new sector domain pack;
- qualify replacement infrastructure through conformance tests;
- create an assurance case with explicit limits and recovery owners; and
- teach system literacy to policymakers, engineers, auditors, and affected groups.

It is not a compliance certificate, universal policy, clinical-safety case,
fairness method, production security approval, or hardware-isolation proof. A
domain owner must supply applicable law, legitimate purpose, affected-person
protections, operational controls, and evidence for the actual deployment.

## The two constitutional rules

The first rule governs the write path. Its companion governs the read path:

> **A model may request information. It cannot manufacture the entitlement to
> see it, and it cannot launder what it saw.**

A system over corporate or medical data can cause serious harm without executing
a single state change. It reads, summarises, and sends. The authority plane
therefore issues two kinds of institutional permission. Exact-action approvals
govern effects. Purpose-bound disclosure grants govern what may enter a model
context. The boundary plane labels every derived output from what its session
received, so a model can never lower the sensitivity of its own output.
[`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md) specifies the lattice, the
fourteen checks, invariants DX-1 to DX-7, and stateful sequence testing. [`PATTERNS.md`](PATTERNS.md) turns
both rules into a reusable pattern language.

## The constitutional model

An institution should govern a consequential AI system more like an institution
than a normal application. The pattern supplies four constitutional properties:

1. **Separated powers.** The component that proposes cannot also create authority,
   approve the proposal, execute the protected change, and rewrite its evidence.
2. **Bounded delegation.** Every grant is rooted in a named authority and can only
   narrow as it travels through agents and tools.
3. **Independent memory.** Intent and outcome evidence is held outside the model's
   control and remains reconstructable after models and components change.
4. **Safe suspension.** Missing policy, stale data, expired authority, uncertain
   execution, or unavailable evidence stops automation and invokes a named route.

These properties are implemented through seven logical planes. A small deployment
may combine several planes in one process, but it must preserve their distinct
identities, credentials, interfaces, and failure behavior. A high-assurance
deployment may place them in separate administrative or physical trust zones.

## The seven planes

| Plane | Institutional duty | Required boundary | Reference mechanisms |
|---|---|---|---|
| **1 Boundary** | Control what may enter and leave each trust zone | Untrusted content cannot grant authority or create an unrecorded return path | import gateway, source and schema checks, signature verification, quarantine, egress allowlist, software no-read-back seam, certified data diode where required |
| **2 Governed data** | Preserve identity, provenance, purpose, versions, and lifecycle | Data cannot lose its origin, approved purpose, classification, or replay identity during movement and transformation | stable resource and event IDs, Kafka, PySpark, Iceberg snapshots, retention and deletion jobs, legal-hold state |
| **3 Intelligence** | Produce bounded analysis or proposals | The model process holds no authoritative write credential and cannot label its own action as low risk | local or hosted model adapter, retrieval, prompt and model version, narrow tool interface, context minimization |
| **4 Authority** | Issue and verify institutional permission | Grants and approvals are purpose-, scope-, holder-, audience-, version-, and time-bound; delegation only attenuates | policy catalogue, workload and human identity, signed exact-action approval, quorum or review service, revocation |
| **5 Execution** | Perform an authorized state change once | An independent executor rechecks the live resource, policy, authority, approval, and replay state before using a write credential | FastAPI control surface, transaction, optimistic version check, idempotency key, outbox, system adapter |
| **6 Evidence** | Reconstruct what was attempted and what occurred | The proposer cannot alter or selectively omit intent, denial, approval, execution, or recovery evidence | hash-chained records, signed decision packet, atomic intent and outcome, immutable or append-only custody |
| **7 Resilience** | Preserve safety when components fail | Ambiguous outcomes are reconciled, never blindly repeated; unavailable controls invoke fail-secure fallback | pending-outcome register, bounded retry, circuit breaker, reconciliation, manual route, incident response |

The planes describe responsibilities, not network diagrams. For example, placing
an executor and model in separate containers on one administrator-controlled host
provides logical separation, not independent administrative trust. The deployment
must state that distinction rather than borrowing a stronger claim from the
diagram.

## The narrow waist between policy and code

Every consequential capability must have a seven-field control contract:

| Field | Policy question | Engineering question |
|---|---|---|
| **Protected asset** | What right, record, resource, dataset, or external effect is at stake? | Which resource identifier and authoritative system represent it? |
| **Permitted operation** | What exact change may be considered, for which purpose and subject? | Which typed operation and before/after states are accepted? |
| **Enforcement point** | Where is the decision made independently of the model? | Which component rechecks policy and alone holds the write capability? |
| **Accountable owner** | Who remains answerable for the rule, service, and affected person? | Which role owns policy, service, data, security, privacy, and recovery? |
| **Failure test** | What misuse or fault must the institution show it can stop? | Which executable test proves refusal or safe recovery? |
| **Evidence artifact** | What can an auditor or affected person inspect? | Which signed packet, event, snapshot, denial, approval, and receipt are retained? |
| **Failure response** | What happens when automation cannot proceed safely? | Which state, queue, operator, deadline, and reconciliation procedure take over? |

A capability is not ready for automation when a field is blank, a failure test is
only prose, the enforcement point is controlled by the model, or the fallback has
no owner and operating window. The repository's coverage command distinguishes
machine-verified, organizationally attested, and unverified requirements rather
than letting policy prose count as executable evidence.

## Non-negotiable invariants

Technology may change. These properties should not:

1. **Proposal is not authority.** Model output is untrusted input to the authority
   service, even when the model is local, aligned, or highly accurate.
2. **Exact-action binding.** Approval covers the exact operation, target, state
   transition, evidence version, requester, resource version, role, audience, and
   expiry. A changed field requires new authority.
3. **Independent execution.** The model cannot access the credential or interface
   that performs the authoritative change.
4. **Live revalidation.** Execution checks current policy, identity, resource
   version, approval, revocation, and replay state instead of trusting an earlier
   decision.
5. **Monotonic delegation.** A delegate never receives more scope, time, depth,
   consequence, or beneficiary access than the complete rooted chain permits.
6. **Single consequential effect.** Concurrent or repeated requests produce at
   most one authoritative mutation and a stable receipt, or enter reconciliation.
7. **Intent and outcome evidence.** Attempt, refusal, approval, execution, and
   recovery are distinguishable and attributable.
8. **Fail-secure uncertainty.** An unknown outcome is not treated as success or as
   permission to retry the external effect.
9. **Lifecycle enforcement.** Purpose, minimization, retention, deletion,
   residency, legal hold, and incident duties travel with the resource.
10. **Contestability.** The domain pack names a route to inspect, challenge,
    correct, revoke, or reverse an outcome where the domain permits it.
11. **Visible limits.** Evidence states its environment, denominator, exclusions,
    failures, and unresolved questions.
12. **Model replaceability.** Replacing a model does not require granting it new
    authority or discarding the evidence chain.

## The governed lifecycle

The reference lifecycle is a loop, not a linear inference call:

```text
purpose and authority declared
            |
            v
controlled import -> quarantine -> validated event -> versioned data state
                                                    |
                                                    v
                                          bounded model proposal
                                                    |
                                                    v
                                         independent policy check
                                                    |
                                      deny / review / authorize
                                                    |
                                                    v
                                        exact-action execution
                                                    |
                           outcome known -----------+----------- outcome uncertain
                                  |                                    |
                                  v                                    v
                         intent + receipt evidence              reconciliation queue
                                  |                                    |
                                  +---------------+--------------------+
                                                  v
                                   retain / revoke / correct / delete
```

At each transition, the deployment should be able to identify the controlling
policy, service identity, input version, permitted next states, evidence written,
and safe result of failure. [`OPERATIONS.md`](OPERATIONS.md) turns the last part
into a runbook; [`RESILIENCE.md`](RESILIENCE.md) covers crash and replay behavior.

## Domain packs

The base kernel is sector-neutral because it does not pretend that sectors share
the same purpose, legal basis, harms, or decision rights. A domain pack provides
that institutional meaning. Every production-intent pack should declare:

- domain, purpose, deployment status, and authoritative owner;
- data classes and subjects;
- applicable law, regulation, contract, ethics, and internal policy;
- processing basis and permitted purposes;
- prohibited uses and non-delegable actions;
- minimization, retention, deletion, residency, and legal-hold rules;
- state transitions and required authority for each operation;
- review or quorum policy, including capacity and independence;
- incident, outage, correction, appeal, and manual fallback routes;
- data, privacy, security, service, policy, and recovery owners;
- hostile cases, benign cases, invariants, conformance checks, and limits; and
- evidence that must be regenerated in the target environment.

The domain pack is not a configuration convenience. It is the boundary between
portable system properties and local legitimacy. The shared kernel can prove that
only an authorized role executed an exact transition; it cannot prove that the
role, policy, or transition is fair, lawful, clinically safe, or socially
legitimate.

## Cross-sector application patterns

### Corporate confidential data

Govern dataset classification, purpose-bound internal use, external disclosure,
revocation, legal hold, downstream copying, and deletion. Bind authority to exact
dataset, fields, recipient, purpose, duration, region, and version. Keep external
release credentials outside the model plane. Integrate with IAM, data catalog,
DLP, key management, records, and incident systems through conformance-tested
adapters.

### Healthcare data

Separate access and disclosure governance from clinical decision support. Bind
access to patient or cohort, requester, purpose, basis, minimum fields, duration,
consent or review status, and emergency context. Preserve break-glass evidence and
retrospective review. Diagnosis, treatment, triage, prescribing, and record
alteration require separate clinical-safety, quality, and human-factors cases.

### Education and research data

Govern support preparation, academic-record correction, research access, consent,
retention, and redress. Do not let an educational example stand in for the whole
architecture. Its added value is that the same implementation can teach learners
to inspect authority, provenance, failure, and evidence before transferring the
pattern to another domain.

### Public and regulated services

Distinguish decision support from the statutory act that changes eligibility,
status, payment, sanction, license, or access. Bind delegated authority to the
legal mandate, case, operation, evidence version, and accountable officer. Preserve
notice, reasons, correction, appeal, and manual continuity. A technically valid
transition under an unjust rule remains unjust; participatory policy review is a
separate and necessary control.

### Industrial and critical operations

Separate analytic recommendations from commands that alter production, safety,
physical access, or operational technology. Add safety interlocks, deterministic
control, change windows, operator roles, environment constraints, and physical
fail-safe states. The reference repository does not claim to implement functional
safety or operational-technology assurance.

## Mapping the pattern to the reference stack

| Architecture duty | Reference implementation | What an adopter may replace | Property that must survive |
|---|---|---|---|
| Controlled service interface | FastAPI | gateway, service mesh, RPC framework | authenticated typed operations and independent policy checks |
| Authoritative state and atomic evidence | PostgreSQL; memory and SQLite for teaching | approved transactional store | mutation, intent, outcome, version, and receipt remain consistent |
| Short-lived coordination | Redis adapter | cache, lock, queue, state service | failure behavior, durability limits, and replay semantics are explicit |
| Replayable event movement | Kafka | another durable event log | stable event identity, provenance, ordering assumptions, and replay tests |
| Reproducible transforms | PySpark | another batch or stream engine | versioned code, inputs, outputs, checkpoints, and deterministic identity |
| Time-addressable data history | Iceberg and object storage | another table or snapshot format | lineage, snapshot reference, retention, deletion, and legal hold are enforceable |
| Bounded inference | Ollama and model adapters | local model, hosted model, rules, human analysis | no model-held write power; endpoint and data-movement claims remain truthful |
| Signed authority | application signing adapter | KMS, HSM, institutional PKI | key custody, audience, expiry, rotation, revocation, and verifier independence |
| One-way transfer seam | low-side gateway and unidirectional transport model | certified diode or cross-domain solution | directionality and failure behavior are tested in the deployed topology |
| Operator view | React console and signed decision packets | case tool, workflow suite, audit portal | the interface cannot enlarge authority and shows evidence and limits accurately |

## Adoption sequence

### Stage 0 Inventory power

Name one consequential action, the authoritative resource it changes, every path
that can invoke it, the credential that enables it, and the people affected. Do
not begin with a model or product shortlist.

### Stage 1 Write the domain pack

Complete the governance context and seven-field contract. Name prohibited uses,
owners, manual fallback, correction route, and evidence gaps. Run the generated
attack test before any real records are connected.

### Stage 2 Prove the boundary in teaching mode

Use synthetic data. Demonstrate a permitted proposal, refusal of an unauthorized
variant, stale-version denial, approval binding, replay safety, and a complete
decision packet. Remove a control and show the harm returns.

### Stage 3 Qualify adapters

Connect identity, policy, authoritative state, events, evidence custody, keys,
and recovery services one at a time. Run the conformance suite after every
substitution. Do not inherit test results from the reference backend.

### Stage 4 Exercise operations

Run concurrent calls, abrupt exits, unavailable dependencies, revocation races,
uncertain external outcomes, capacity overload, incident response, restoration,
and contestability. Verify staffing and deadlines, not only code paths.

### Stage 5 Add administrative and physical assurance

Separate operators and key custodians, harden hosts, restrict egress, pin software
artifacts, connect approved secret management, and deploy certified one-way or
cross-domain hardware where the threat model requires it. Independently test the
actual topology.

### Stage 6 Pilot and publish bounded evidence

Begin with a reversible, low-volume, supervised capability. Publish the commit,
environment, domain pack, denominators, benign and hostile outcomes, failures,
exclusions, reviewer assumptions, recovery results, and open evidence register.
Production approval remains the institution's decision.

## Decision gate for policy leaders

Do not approve a consequential AI capability until the institution can answer:

1. What exact asset and action are governed?
2. What purpose and authority make the action legitimate?
3. Which independent component can refuse it and holds the write credential?
4. Can any agent chain enlarge the root grant?
5. What data, model, policy, prompt, and resource versions are bound to approval?
6. What review capacity, independence, and fallback exist under peak load?
7. What happens after a crash or an unknown external outcome?
8. Can intent and outcome be reconstructed after components change?
9. How can affected people obtain reasons, challenge, correct, or appeal?
10. Which claims were reproduced in this deployment and which remain open?

## Implementation gate for engineers

Do not connect a real authoritative system until tests show:

- untrusted input cannot become policy, identity, or authority;
- the model cannot reach the authoritative credential;
- exact-action approval fails after any bound field changes;
- policy and resource versions are checked at execution time;
- delegation is validated against the complete rooted chain;
- concurrent retries cannot duplicate the protected effect;
- pre-effect failure leaves no false success record;
- post-effect uncertainty enters reconciliation rather than blind retry;
- evidence contains both intent and final outcome;
- revocation, retention, deletion, and legal-hold cases behave as declared;
- legitimate work still completes; and
- substituted backends pass the same conformance properties.

## Evidence ladder

Use explicit evidence classes rather than one undifferentiated “compliant” label:

| Level | Evidence | What it supports |
|---|---|---|
| **Specified** | complete domain pack and control contracts | the institution has made the required decisions explicit |
| **Implemented** | controls and adapters exist | the declared mechanism is present in the reviewed version |
| **Machine verified** | unit, property, bounded, ablation, race, and conformance tests | declared software behavior in the tested environment |
| **Operationally exercised** | recovery, incident, capacity, revocation, and continuity drills | people and systems can perform the declared response |
| **Independently assessed** | external security, privacy, safety, accessibility, and domain review | selected claims survive review outside the builder team |
| **Field evidenced** | monitored pilot and affected-person outcomes | observed performance and harm in the authorized use context |

Advancing one level does not erase the limits of the level below it. A passing
software suite does not prove reviewer attention, hardware isolation, legal
compliance, or fair outcomes.

## What stays fixed and what must change

The reference architecture generalizes through disciplined variation:

| Preserve across domains | Replace for every deployment |
|---|---|
| proposal is not authority | purpose, legal and organizational basis |
| exact-action binding | data classes and affected groups |
| independent enforcement | permitted and prohibited operations |
| monotonic delegation | accountable roles and decision rights |
| live version and replay checks | retention, deletion, residency, and legal hold |
| intent and outcome evidence | review, correction, appeal, and incident routes |
| fail-secure recovery | backend, model, identity, key, and system adapters |
| visible limits and regenerated evidence | domain tests, thresholds, capacity, and field evidence |

That is the core design pattern: preserve the constitution, replace the domain,
and regenerate the evidence.

## Continue through the repository

- Policy leaders: [`PROCUREMENT.md`](PROCUREMENT.md) → [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) → [`GAPS.md`](GAPS.md) → [`ADOPTION.md`](ADOPTION.md).
- Engineers: [`PLATFORM.md`](PLATFORM.md) → [`SECURITY.md`](SECURITY.md) → [`DIODE_DEPLOYMENT.md`](DIODE_DEPLOYMENT.md) → [`RESILIENCE.md`](RESILIENCE.md) → [`EXTENDING.md`](EXTENDING.md).
- Reviewers: [`REVIEWERS.md`](REVIEWERS.md) → [`ASSURANCE.md`](ASSURANCE.md).
- Educators: [`SYSTEM_LITERACY.md`](SYSTEM_LITERACY.md) → [`LAB.md`](LAB.md) → [Authority Boundary Worksheet](worksheet/).
- Conference readers: [`../paper/form-ready-abstract.md`](../paper/form-ready-abstract.md) → [`../paper/extended-abstract.md`](../paper/extended-abstract.md) → [`presenter-and-submission-guide.md`](presenter-and-submission-guide.md).

Return to the [documentation map](README.md) at any point.
