# Trust by Construction specification

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Choose the conformance classes your system needs, then build the evidence with [`EXTENDING.md`](EXTENDING.md) and [`PATTERNS.md`](PATTERNS.md).

**Status:** draft 1.0 for public comment · **Scope:** any AI system that reads
sensitive data, recommends or takes consequential actions, delegates work between
agents, or operates tools, in any sector.

## 1. Purpose

This page states the architecture as normative requirements that any
implementation can claim, and that anyone can check. It is written so that a
corporation, hospital, public body, or vendor can say which classes a system
conforms to, and so that an auditor or procurement officer can ask for the
evidence behind each requirement.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as described
in RFC 2119 and RFC 8174.

This reference implementation cites, for every requirement, the executable test
that checks it here. A different implementation MUST produce its own evidence for
the same requirement. Evidence does not transfer between deployments.

## 2. The thesis and the two constitutional rules

> **Intelligence is untrusted. Power and data are mediated.**

The thesis and its falsifiers are stated in [`THESIS.md`](THESIS.md).

> **R1.** A model may propose an action. It cannot manufacture the authority to
> execute it.
>
> **R2.** A model may request information. It cannot manufacture the entitlement to
> see it, and it cannot launder what it saw.

Every requirement below makes one of these rules checkable. Neither rule may depend
on the model being aligned. A system conforms only if each rule holds when the
model is assumed to be mistaken, manipulated, or adversarial.

## 3. Conformance

A system claims conformance **by class**. A claim for a class means that every
MUST requirement in that class is met and evidenced in the deployment that makes
the claim. Every SHOULD not met is listed with a reason.

| Class | Name | Required when the system |
|---|---|---|
| **TBC-T** | Trusted base | always |
| **TBC-A** | Authority | can change a record, access, resource, or obligation |
| **TBC-D** | Governed disclosure | reads personal, confidential, or regulated data into a model context |
| **TBC-C** | Composition and oversight | delegates to other agents or tools, or relies on human review |
| **TBC-E** | Evidence and recovery | always |
| **TBC-V** | Verification | always |

Evidence is one of three kinds, named in the final column of each table.

- **Test:** an executable check that fails when the requirement is broken.
- **Attestation:** a named role's signed statement on a declared cadence, for
  properties that are organisational rather than computational.
- **Measurement:** an observation of the deployed system in its real environment.

A conformance claim MUST name the kind of evidence for every requirement.
Attestation MUST NOT be counted as a test.

## 4. Requirements

### TBC-T Trusted base

The safety case moves trust away from the model. It must say where that trust went.

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| T-1 | MUST | Declare the trusted computing base: every component whose compromise defeats R1 or R2. At minimum, list enforcement points, signing authorities, evidence store, identity provider, and administrators. | attestation: see [`SECURITY.md`](SECURITY.md) |
| T-2 | MUST | Declare the interface inventory: every path into and out of the trusted base, with an owner. An undeclared interface is an unreviewed change. | test: `tests/test_diode_transport.py::test_an_interface_without_an_owner_is_flagged` |
| T-3 | MUST | Hold no credential for an authoritative write or a record store in any process that runs a model. | test: `tests/test_privilege_invariance.py::test_model_output_cannot_introduce_a_capability` |
| T-5 | MUST | Persist grants, revocations, consent, sessions, outputs, and emergency-access obligations in a store where each decision commits atomically. A restart MUST NOT forget a revocation. | test: `tests/test_disclosure_production.py::test_sql_store_survives_restart_and_forgets_nothing` |
| T-4 | SHOULD | Separate administration of the model runtime from administration of signing keys and evidence custody. | attestation |

### TBC-A Authority

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| A-1 | MUST | Treat every model output as a proposal. Only an enforcement point independent of the model may execute. | test: `tests/test_privilege_invariance.py::test_a_class_downgrading_model_gains_nothing` |
| A-2 | MUST | Take an action's review class from an institution-owned catalogue, never from the proposal. Unknown capabilities MUST be treated as consequential. | test: `tests/test_privilege_invariance.py::test_an_unknown_capability_fails_closed` |
| A-3 | MUST | Bind every approval to the exact proposal digest, resource version, approver role, audience, and expiry. Any change voids it. | test: `tests/test_exact_action.py::test_target_or_arguments_changed_after_approval_are_denied` |
| A-4 | MUST | Re-check the live resource version before executing. | test: `tests/test_exact_action.py::test_changed_authoritative_case_requires_renewed_review` |
| A-5 | MUST NOT | Allow a requester to approve their own proposal. | test: `tests/test_exact_action.py::test_requester_cannot_approve_own_proposal` |
| A-6 | MUST | Make retries idempotent under a persistent request identity. | test: `tests/test_exact_action.py::test_retry_is_idempotent_and_cross_request_reuse_is_denied` |

### TBC-D Governed disclosure

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| D-1 | MUST | Release data into a model context only through a gate that alone holds the record-store credential. | test: `tests/test_disclosure_api.py::test_governed_model_task_reads_only_what_the_grant_allows_and_labels_its_output` |
| D-2 | MUST | Require a grant bound to holder, purpose, subjects, fields, data classes, and expiry, issued by someone other than the holder except for declared emergency access. | test: `tests/test_disclosure.py::test_disclosure_bounded_model_check_holds` |
| D-3 | MUST | Require every request to name its subjects and fields. There is no request for all data. | test: `tests/test_disclosure.py::test_requests_must_name_subjects_and_fields_and_endpoints_must_be_declared` |
| D-4 | MUST | Check consent and revocation at every read. | test: `tests/test_disclosure.py::test_consent_withdrawal_and_revocation_take_effect_at_next_read` |
| D-5 | MUST | Check consent, revocation, and expiry again at every release of anything already derived. | test: `tests/test_disclosure.py::test_release_rechecks_consent_and_revocation_after_the_read` |
| D-6 | MUST | Send each data class only to model endpoints in zones declared for that class. Undeclared endpoints MUST receive nothing. | test: `tests/test_disclosure.py::test_requests_must_name_subjects_and_fields_and_endpoints_must_be_declared` |
| D-7 | MUST | Label every output with the join of everything its session received, and ignore any label the model claims. | test: `tests/test_disclosure.py::test_model_claimed_label_cannot_launder_a_summary` |
| D-8 | MUST | Lower a label only through a declared rule, with an approval bound to the exact output digest from a declared role held by someone other than the output's holder. | test: `tests/test_disclosure.py::test_declassification_requires_exact_independent_approval` |
| D-9 | MUST | Bound emergency access by purpose, duration, and justification. Each use MUST open a review obligation, and overdue reviews MUST block further emergency access. | test: `tests/test_disclosure.py::test_break_glass_opens_review_obligation_and_blocks_repeat` |
| D-10 | SHOULD | Track labels per value rather than per session where a trusted orchestrator can name the values used, recomputing labels from issued values and falling back to the session label when unnamed values appear. | test: `tests/test_disclosure_production.py::test_value_level_labels_release_what_session_labels_would_refuse` |
| D-11 | MUST | Read the record source only after every authorization check passes, so a refusal reveals nothing about whether a subject exists. | test: `tests/test_disclosure_production.py::test_record_sources_are_read_only_after_authorization_so_existence_does_not_leak` |
| D-12 | MUST | Accept externally issued grants only when signed with the issuer's published asymmetric keys, for the configured issuer and audience, with every standard claim present. | test: `tests/test_disclosure_tokens_and_concurrency.py::test_grant_tokens_are_rejected_when_anything_is_wrong` |
| D-13 | MUST | Refuse, and record why, when the record source, consent service, or state store cannot answer. | test: `tests/test_disclosure_production.py::test_live_consent_service_is_checked_at_read_and_release_and_fails_closed` |

### TBC-C Composition and oversight

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| C-1 | MUST | Never let a principal pass on authority it does not hold. A chain confers the intersection of its grants. | test: `tests/test_delegation.py::test_a_hop_cannot_pass_on_authority_it_does_not_hold` |
| C-2 | MUST | Bind every delegation chain to the principal that presents it. | test: `tests/test_delegation.py::test_a_chain_is_bound_to_the_principal_it_names` |
| C-3 | MUST NOT | Let a machine pass on consequential authority without a named human approving that hop. | test: `tests/test_delegation.py::test_a_machine_may_not_pass_consequential_authority_onward` |
| C-4 | MUST | Declare review capacity and refuse approvals beyond it, deferring excess to a staffed fallback. | test: `tests/test_oversight.py::test_the_ceiling_refuses_the_next_approval_rather_than_flagging_it` |
| C-5 | MUST | Refuse approvals faster than the declared deliberation floor. | test: `tests/test_oversight.py::test_an_approval_faster_than_the_deliberation_floor_is_refused` |
| C-6 | MUST | Accept a lowered deliberation floor for assisted review only with declared model, evidence-path, and adversarial independence. | test: `tests/test_assisted_review.py::test_a_lowered_floor_without_declared_independence_is_refused` |
| C-7 | SHOULD | Measure reviewer accuracy under load before relying on a declared degradation curve. | measurement: open; see [`GAPS.md`](GAPS.md) |

### TBC-E Evidence and recovery

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| E-1 | MUST | Record intent before any effect or disclosure, and refuse to proceed when intent cannot be recorded. | test: `tests/test_disclosure.py::test_intent_evidence_failure_releases_nothing` |
| E-2 | MUST | Make evidence tamper-evident and write it through a credential the model does not hold. | test: `tests/test_attacks.py::test_insider_record_tampering_is_detected` |
| E-3 | MUST NOT | Write protected values into the evidence log. | test: `tests/test_disclosure.py::test_evidence_never_contains_protected_values` |
| E-4 | MUST | Treat an uncertain outcome as uncertain, reconcile it once, and never retry it blindly. | test: `tests/test_exact_action.py::test_completed_mutation_is_marked_uncertain_then_reconciled_once` |
| E-5 | MUST | Record an unclosed intent when delivery across a boundary fails. | test: `tests/test_import_api.py::test_import_gateway_records_an_unclosed_intent_when_delivery_fails` |
| E-6 | MUST | Name a human fallback route and its owner for every refusal. | attestation: `manual_fallback` in every domain pack |

### TBC-V Verification

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| V-1 | MUST | Bind every control requirement to a check that exists and runs, or to a named attestation. Report unverified requirements. | test: `tests/test_threats.py::test_a_locator_naming_a_test_that_does_not_exist_is_reported` |
| V-2 | MUST | Enumerate the declared authority and disclosure space against a reference predicate written independently of the implementation. | test: `tests/test_disclosure.py::test_disclosure_bounded_model_check_holds` |
| V-3 | MUST | Test sequences of operations against a reference model, not only single steps. | test: `tests/test_disclosure.py::test_random_operation_sequences_agree_with_the_reference_model` |
| V-4 | MUST | Remove each control in turn and show that a named harm returns. | test: `tests/test_disclosure.py::test_every_disclosure_check_is_load_bearing` |
| V-5 | MUST | Report utility beside containment, and compare with a careful conventional design. | test: `tests/test_disclosure.py::test_conventional_access_control_leaves_harms_this_architecture_contains` |
| V-6 | MUST | Maintain a threat catalogue in which every containment claim cites evidence and residual threats are stated. | test: `tests/test_threats.py::test_a_catalogue_with_no_residuals_is_refused` |
| V-7 | MUST | Verify that every declared state and review role is reachable. | test: `tests/test_disclosure.py::test_every_domain_pack_reaches_every_declared_status_from_its_start` |
| V-8 | MUST | Rerun all evidence after replacing any component, domain pack, or model. | test: `tests/test_domain_packs.py::test_the_same_authority_kernel_holds_outside_education` |
| V-10 | MUST | Attempt to refute the Mediation Thesis with every falsifier for every domain pack in scope, and publish attempts, counterexamples, scope, trusted base, and residuals. | test: `tests/test_thesis.py::test_the_thesis_is_not_falsified_within_stated_bounds` |
| V-11 | MUST | Test revocation against release, and emergency-access limits, under concurrent threads and independent processes sharing one store. | test: `tests/test_disclosure_tokens_and_concurrency.py::test_independent_processes_share_one_store_without_violating_either_invariant` |
| V-12 | SHOULD | Instrument every pilot with indicators computed from evidence, and state what those indicators cannot measure. | test: `tests/test_disclosure_tokens_and_concurrency.py::test_pilot_indicators_come_from_evidence_and_name_what_they_cannot_measure` |
| V-9 | SHOULD | Obtain independent assessment and field evidence before production use. | measurement: open; see [`GAPS.md`](GAPS.md) |

### Companion profile: agent swarms

Deployments that run many cooperating agents also claim the requirements in
[`SPECIFICATION_SWARM_PROFILE.md`](SPECIFICATION_SWARM_PROFILE.md): measured trusted
base, policy-bound approval and migration, fenced commit under distributed faults, sector
release tables, a covert-channel rate objective, review staffing, Merkle proofs, a
witness quorum across domains, forward-secure keys, time anchoring and a generated
refusal-code registry. They are kept in a separate profile so this core specification,
and every figure computed from it, stays stable.

## 5. What conformance does not mean

Conformance to this specification is not legal compliance, certification, a
security probability, a fairness guarantee, or evidence of alignment. It means the
system's authority and disclosure boundaries are explicit, independently enforced,
and checked. It also means the claim names what remains unproven.

A conforming system can still apply an unjust rule faithfully, and a model can
still cause harm inside the authority it was legitimately granted. Those harms
belong to governance, oversight, and contestability, which this specification
makes visible but does not resolve.

## 6. Changing this specification

A requirement may be added only with a stated failure it prevents and an evidence
kind. A requirement may be removed only with the evidence that it was unnecessary.
[`tests/test_specification.py`](../tests/test_specification.py) fails the build if a
cited test stops existing.
