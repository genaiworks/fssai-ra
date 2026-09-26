# Framework control catalogue

> **Documentation navigation:** [Documentation map](../README.md) · [Framework](../FRAMEWORK.md) · [Master guide](../MASTER_GUIDE.md)
>
> **Recommended next:** Answer the questions below in the assessment template (`fssaira framework init`), then run `fssaira framework assess`.

Generated from `src/fssaira/framework_catalogue.yaml` (catalogue 1.0) by `fssaira framework render`. Do not edit by hand: a test fails if this file and the catalogue differ.

**50 controls** in 9 domains. Maturity levels: 1 Access-controlled · 2 Authority-bound · 3 Disclosure-governed · 4 Composition-safe · 5 Evidenced.

| Domain | Controls | By level |
|---|---|---|
| **GOV** Governance and accountability | 4 | L1: 1, L2: 1, L3: 1, L4: 1 |
| **IDN** Identity, credentials and containment | 4 | L1: 3, L4: 1 |
| **AUT** Authority over actions | 5 | L2: 3, L4: 2 |
| **DAT** Data and disclosure | 6 | L3: 5, L4: 1 |
| **SWM** Swarm composition | 8 | L4: 8 |
| **EFF** Effects and adapters | 3 | L2: 1, L4: 1, L5: 1 |
| **EVD** Evidence | 8 | L1: 1, L2: 1, L3: 3, L5: 3 |
| **OVS** Human oversight | 5 | L2: 1, L4: 3, L5: 1 |
| **ASR** Assurance and verification | 7 | L2: 1, L3: 2, L4: 1, L5: 3 |

## GOV — Governance and accountability

### GOV-1 · Named owners and a manual fallback for every workflow (level 1)

- **Objective:** Every agentic workflow has a named accountable owner and a human service route used whenever automation refuses.
- **Prevents:** refusals that strand the person being served, and decisions nobody answers for
- **Ask yourself:** Does every agentic workflow have a named owner and a documented manual route that works when the system says no?
- **Owner:** Workflow owner
- **Requires:** nothing
- **Implemented in:** `packs/template.pack.yaml`, `src/fssaira/scaffold.py`
- **Prove it:** `attestation: manual_fallback and owner declared in every domain pack`
- **Standards:** NIST AI RMF GOVERN, ISO/IEC 42001

### GOV-2 · Task contract with purpose, exact scope, budget and expiry (level 2)

- **Objective:** Work starts only from a contract naming task, purpose, subject, tenant, exact scope, shared budget and expiry; over-broad mandates do not start.
- **Prevents:** wildcard authority and open-ended agents
- **Ask yourself:** Does every agent task start from a written contract with exact identifiers, a budget and an expiry, and is an over-broad one refused?
- **Owner:** Workflow owner
- **Requires:** GOV-1
- **Implemented in:** `src/fssaira/tbc/contracts.py`, `src/fssaira/tbc/mandate.py`
- **Prove it:** `tests/test_mandate_lint.py::test_with_declared_purposes_an_over_broad_mandate_does_not_start`; `tests/test_tbc_sdk.py::test_lease_expiry_and_task_expiry_are_checked_on_use`
- **Refusal codes:** `TASK_EXPIRED`, `TASK_BUDGET_EXCEEDS_PASSPORT`
- **Standards:** OWASP LLM06 Excessive Agency, NIST AI RMF MAP

### GOV-3 · Versioned policy with sanctioned migration (level 4)

- **Objective:** Policy changes only through a named, reasoned, monotonic migration that contracts uncovered tasks and sends held effects to re-review.
- **Prevents:** silent rule changes, and approvals given under old rules executing under new ones
- **Ask yourself:** Can you change agent policy without stopping everything, with in-flight approvals re-reviewed under the new rules?
- **Owner:** Risk, legal, DPO
- **Requires:** GOV-2
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_approval_policy_pinning.py::test_migration_is_named_monotonic_and_survives_restart`
- **Refusal codes:** `POLICY_VERSION_NOT_INCREASING`, `POLICY_WORKLOAD_MISMATCH`, `PASSPORT_DRIFT`
- **Standards:** ISO/IEC 42001, NIST AI RMF GOVERN

### GOV-4 · Sector release table with cited basis (level 3)

- **Objective:** Where law defines who may receive data, encode it as a decision table in which every answer cites its basis and unmodelled paths are refused.
- **Prevents:** releases that are technically authorised but legally wrong
- **Ask yourself:** Are your sector's disclosure rules (FERPA, HIPAA, GDPR, banking secrecy...) encoded as testable decisions that cite their legal basis?
- **Owner:** Risk, legal, DPO · **Applies when:** the workflow touches regulated personal data
- **Requires:** GOV-2
- **Implemented in:** `src/fssaira/ferpa.py`, `packs/healthcare.pack.yaml`, `packs/finance.pack.yaml`
- **Prove it:** `tests/test_ferpa_pack.py::test_consent_must_match_holder_records_recipient_and_purpose`
- **Refusal codes:** `FERPA_CONSENT_REQUIRED`, `FERPA_PATH_NOT_MODELLED`
- **Standards:** FERPA 34 CFR 99, GDPR Art. 6, HIPAA Privacy Rule


## IDN — Identity, credentials and containment

### IDN-1 · Agents hold no credentials (level 1)

- **Objective:** No process that runs a model holds a credential for a record store or external system; the gateway acts on its behalf.
- **Prevents:** a manipulated model using standing access directly
- **Ask yourself:** Is every agent unable, even when fully compromised, to reach a database, API key or cloud role on its own?
- **Owner:** Enforcer operations
- **Requires:** nothing
- **Implemented in:** `src/fssaira/isolation.py`, `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_isolation.py::test_standing_credentials_in_the_agent_environment_are_a_violation`; `tests/test_privilege_invariance.py::test_model_output_cannot_introduce_a_capability`
- **Refusal codes:** `ENVELOPE_DENIED`
- **Standards:** OWASP LLM06 Excessive Agency, NIST AI RMF MANAGE

### IDN-2 · Authenticated agents with expiring, non-expanding leases (level 1)

- **Objective:** Every call carries an agent identity and a capability lease that expires and can never widen any authority axis.
- **Prevents:** token reuse, forged capability and lease escalation
- **Ask yourself:** Does every agent call carry its own short-lived capability that cannot grant more than its parent holds?
- **Owner:** Enforcer operations
- **Requires:** IDN-1
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_sdk.py::test_wrong_tokens_duplicate_fields_nonfinite_and_foreign_capability`; `tests/test_tbc_sdk.py::test_lease_cannot_expand_any_authority_axis`
- **Refusal codes:** `AUTHENTICATION_REQUIRED`, `STALE_OR_FOREIGN_CAPABILITY`, `CAPABILITY_SCOPE_DENIED`
- **Standards:** NIST AI RMF MANAGE

### IDN-3 · Declared interfaces only (level 1)

- **Objective:** Agents reach the trusted base only through declared primitives with declared fields; anything else fails closed with no effect.
- **Prevents:** undeclared tools and side doors
- **Ask yourself:** Is there a closed list of operations an agent can call, with everything else refused before it does anything?
- **Owner:** Enforcer operations
- **Requires:** IDN-1
- **Implemented in:** `src/fssaira/integration/messages.py`, `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_sdk.py::test_untrusted_interfaces_fail_closed_without_effects`
- **Refusal codes:** `UNDECLARED_INTERFACE`, `OBJECT_REQUIRED`
- **Standards:** OWASP LLM05 Improper Output Handling

### IDN-4 · Measured agent cells; unqualified hosts refused (level 4)

- **Objective:** Each agent runs in a cell measured from inside -- no metadata service, no service-account token, default-deny egress, non-root, immutable code -- and production refuses a cell it cannot confirm.
- **Prevents:** ambient cloud or cluster credentials leaking into a supposedly credential-less agent
- **Ask yourself:** Have you measured, from inside the running agent container, that it cannot reach cloud metadata, cluster tokens or the internet?
- **Owner:** Enforcer operations
- **Requires:** IDN-1
- **Implemented in:** `src/fssaira/agent_cell.py`, `src/fssaira/isolation.py`
- **Prove it:** `tests/test_isolation.py::test_reachable_cloud_metadata_is_a_violation`; `tests/test_isolation.py::test_a_readable_service_account_token_is_a_violation`; `tests/test_agent_cell.py::test_every_property_must_be_observed_and_satisfied`
- **Standards:** OWASP LLM06 Excessive Agency, NIST AI 600-1 Information Security


## AUT — Authority over actions

### AUT-1 · A proposal is not authority (level 2)

- **Objective:** Model output is a structured proposal; only an enforcement point independent of the model executes, and the action's class comes from an institution catalogue.
- **Prevents:** prompt injection turning into action
- **Ask yourself:** Is model output only ever a proposal, so that even a fully manipulated model cannot change a record, send a message or move money by itself?
- **Owner:** Enforcer operations
- **Requires:** IDN-3
- **Implemented in:** `src/fssaira/exact_action.py`, `src/fssaira/control_plane.py`
- **Prove it:** `tests/test_privilege_invariance.py::test_a_class_downgrading_model_gains_nothing`; `tests/test_ablations.py::test_removing_least_privilege_lets_agent_approve_awards`
- **Refusal codes:** `AI_IR_SCOPE_DENIED`
- **Standards:** OWASP LLM01 Prompt Injection, OWASP LLM06 Excessive Agency

### AUT-2 · Exact-action approval (level 2)

- **Objective:** An approval binds the exact proposal digest, resource version, role, audience and expiry; any change voids it.
- **Prevents:** approving X and executing Y
- **Ask yourself:** If a draft changes by one character after approval, is the approval void?
- **Owner:** Approvers
- **Requires:** AUT-1
- **Implemented in:** `src/fssaira/exact_action.py`
- **Prove it:** `tests/test_exact_action.py::test_target_or_arguments_changed_after_approval_are_denied`; `tests/test_exact_action.py::test_changed_authoritative_case_requires_renewed_review`
- **Refusal codes:** `EXACT_APPROVAL_REQUIRED`, `ARTIFACT_DIGEST_MISMATCH`
- **Standards:** NIST AI RMF MANAGE

### AUT-3 · No self-approval; independent confirmation (level 2)

- **Objective:** The proposer never approves its own proposal, and consequential effects need a confirmation from a different named person.
- **Prevents:** agreement between agents, or one person, masquerading as oversight
- **Ask yourself:** Does every consequential action need approval from someone other than whoever proposed it?
- **Owner:** Approvers
- **Requires:** AUT-2
- **Implemented in:** `src/fssaira/exact_action.py`, `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_exact_action.py::test_requester_cannot_approve_own_proposal`; `tests/test_tbc_sdk.py::test_full_sdk_workflow_uses_independent_approval_and_real_effect`
- **Refusal codes:** `INDEPENDENT_CONFIRMATION_REQUIRED`
- **Standards:** ISO/IEC 42001, NIST AI RMF GOVERN

### AUT-4 · Policy-bound approval (level 4)

- **Objective:** Proposals and approvals record the policy version; execution under any other version is refused and re-reviewed.
- **Prevents:** approve under old rules, execute under new
- **Ask yourself:** Does an approval stop working when the policy it was given under changes?
- **Owner:** Approvers
- **Requires:** AUT-2, GOV-3
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_approval_policy_pinning.py::test_approval_under_old_policy_does_not_execute_under_new`
- **Refusal codes:** `POLICY_VERSION_CHANGED`
- **Standards:** ISO/IEC 42001

### AUT-5 · Objection window for irreversible effects (level 4)

- **Objective:** Approved effects wait a declared window in which an objection or revocation cancels them before they reach the system of record.
- **Prevents:** irreversible effects (email, payment) that revocation arrives too late for
- **Ask yourself:** For actions you cannot undo, is there a window in which a person can still stop them?
- **Owner:** Workflow owner · **Applies when:** agents can trigger irreversible external effects
- **Requires:** AUT-2
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_effect_escrow.py::test_an_objection_inside_the_window_cancels_the_effect`; `tests/test_effect_escrow.py::test_revoking_the_task_during_the_window_cancels_at_commit`
- **Refusal codes:** `OBJECTION_WINDOW_CLOSED`, `EFFECT_NOT_PENDING`
- **Standards:** NIST AI RMF MANAGE


## DAT — Data and disclosure

### DAT-1 · Purpose-bound grants through a single gate (level 3)

- **Objective:** Data enters a model context only through a gate that alone holds the record-store credential, under a grant naming holder, purpose, subjects, fields and expiry.
- **Prevents:** agents reading whatever they can reach
- **Ask yourself:** Does every read by an agent name the person, the fields and the purpose, and go through one gate that alone can read the store?
- **Owner:** Risk, legal, DPO
- **Requires:** IDN-1, GOV-2
- **Implemented in:** `src/fssaira/disclosure.py`, `src/fssaira/disclosure_api.py`
- **Prove it:** `tests/test_disclosure_api.py::test_governed_model_task_reads_only_what_the_grant_allows_and_labels_its_output`; `tests/test_disclosure.py::test_requests_must_name_subjects_and_fields_and_endpoints_must_be_declared`
- **Refusal codes:** `PURPOSE_MISMATCH`, `CONTEXT_SCOPE_DENIED`
- **Standards:** OWASP LLM02 Sensitive Information Disclosure, GDPR Art. 5(1)(b)

### DAT-2 · Live consent and revocation at read and at release (level 3)

- **Objective:** Consent, revocation and expiry are checked at every read and again at every release of anything derived.
- **Prevents:** consent withdrawn after the read but before the release
- **Ask yourself:** If someone withdraws consent mid-task, does the next read and the pending release both fail?
- **Owner:** Risk, legal, DPO
- **Requires:** DAT-1
- **Implemented in:** `src/fssaira/disclosure.py`
- **Prove it:** `tests/test_disclosure.py::test_consent_withdrawal_and_revocation_take_effect_at_next_read`; `tests/test_disclosure.py::test_release_rechecks_consent_and_revocation_after_the_read`
- **Refusal codes:** `RELEASE_CONSENT_WITHDRAWN`, `CONSENT_REVOKED`
- **Standards:** GDPR Art. 7(3)

### DAT-3 · Label inheritance and sealed release (level 3)

- **Objective:** Every output carries the join of every label it was built from, ignores labels the model claims, and is released only to destinations cleared for all of them.
- **Prevents:** the reader -> summariser -> publisher leak
- **Ask yourself:** If an agent summarises a confidential record, does the summary stay confidential wherever it goes?
- **Owner:** Risk, legal, DPO
- **Requires:** DAT-1
- **Implemented in:** `src/fssaira/disclosure.py`, `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_disclosure.py::test_model_claimed_label_cannot_launder_a_summary`; `tests/test_tbc_sdk.py::test_memory_and_generated_output_cannot_drop_session_lineage`
- **Refusal codes:** `DESTINATION_DENIED`, `DECLASSIFICATION_REQUIRED`
- **Standards:** OWASP LLM02 Sensitive Information Disclosure

### DAT-4 · Independent, exact declassification (level 3)

- **Objective:** A label is lowered only through a declared rule, with approval bound to the exact output digest by someone other than its holder.
- **Prevents:** self-declassification and "approve the gist"
- **Ask yourself:** Is lowering an output's sensitivity only possible through a declared rule and someone other than its holder?
- **Owner:** Risk, legal, DPO
- **Requires:** DAT-3
- **Implemented in:** `src/fssaira/disclosure.py`
- **Prove it:** `tests/test_disclosure.py::test_declassification_requires_exact_independent_approval`
- **Refusal codes:** `DECLASSIFICATION_SELF_APPROVED`, `DECLASSIFICATION_WRONG_OUTPUT`
- **Standards:** ISO/IEC 42001

### DAT-5 · Refusals reveal nothing (level 3)

- **Objective:** Record sources are read only after authorization, and agents see only DENIED, so a refusal does not reveal whether a record exists.
- **Prevents:** existence oracles and policy probing through error codes
- **Ask yourself:** Do refusals look identical to the agent, so it cannot learn whether a record exists?
- **Owner:** Enforcer operations
- **Requires:** DAT-1
- **Implemented in:** `src/fssaira/disclosure.py`, `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_disclosure_production.py::test_record_sources_are_read_only_after_authorization_so_existence_does_not_leak`
- **Standards:** OWASP LLM02 Sensitive Information Disclosure

### DAT-6 · Covert-channel budget and rate objective (level 4)

- **Objective:** Choices left to agents at release (destination, path, time, size, count) are made canonical where possible; the remainder is charged in bits against a budget and an organisation-wide bits-per-minute objective.
- **Prevents:** agents signalling through legitimate choices
- **Ask yourself:** Have you measured how many bits per minute agents could leak through their allowed choices, and set a limit?
- **Owner:** Enforcer operations · **Applies when:** agent outputs leave the organisation or cross trust zones
- **Requires:** DAT-3
- **Implemented in:** `src/fssaira/covert_channels.py`, `src/fssaira/channel_slo.py`
- **Prove it:** `tests/test_channel_budget.py::test_releases_past_the_channel_budget_go_to_a_person`; `tests/test_master_guide_measures.py::test_channel_slo_is_a_rate_and_fails_when_unbounded`
- **Refusal codes:** `CHANNEL_BUDGET_EXHAUSTED`, `CHANNEL_SLO_EXCEEDED`
- **Standards:** NIST AI 600-1 Information Security


## SWM — Swarm composition

### SWM-1 · One shared budget for the whole swarm (level 4)

- **Objective:** Every descendant draws on the task budget through atomic reservations, so spawning workers multiplies neither spend nor data access.
- **Prevents:** parallelism as a budget and authority multiplier
- **Ask yourself:** When an agent spawns workers, do they all draw on one shared task budget?
- **Owner:** Enforcer operations
- **Requires:** GOV-2
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_sdk.py::test_aggregate_sibling_budget_does_not_multiply`; `tests/test_tbc_composition_controls.py::test_sibling_reservations_share_one_balance_and_settle_once`
- **Refusal codes:** `AGGREGATE_BUDGET_EXHAUSTED`, `CALL_BUDGET_EXHAUSTED`
- **Standards:** OWASP LLM10 Unbounded Consumption

### SWM-2 · Attenuating delegation, verified across the whole chain (level 4)

- **Objective:** A delegate receives at most the intersection of every grant above it, recomputed from the institutional root on every call; machines cannot pass on consequential authority without a named human.
- **Prevents:** authority laundering through a chain of agents (per-hop checks alone contained 2 of 10 risk classes)
- **Ask yourself:** When agent A delegates to B and B to C, is C's authority recomputed from the root every time, not just checked against B?
- **Owner:** Enforcer operations · **Applies when:** agents delegate to other agents or tools
- **Requires:** IDN-2
- **Implemented in:** `src/fssaira/delegation.py`, `src/fssaira/grant_delegation.py`
- **Prove it:** `tests/test_delegation.py::test_a_hop_cannot_pass_on_authority_it_does_not_hold`; `tests/test_delegation.py::test_a_machine_may_not_pass_consequential_authority_onward`
- **Refusal codes:** `DELEGATION_AMPLIFICATION`, `DELEGATION_DEPTH`
- **Standards:** OWASP LLM06 Excessive Agency

### SWM-3 · Declared task graph (level 4)

- **Objective:** Every node and message edge in the swarm is admitted before use; retracting an edge stops messages already queued on it.
- **Prevents:** undeclared agents and side channels between agents
- **Ask yourself:** Is the shape of your swarm (who may talk to whom) declared up front and enforced?
- **Owner:** Workflow owner
- **Requires:** SWM-2
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_composition_controls.py::test_declared_graph_admits_each_node_and_edge_before_use`; `tests/test_tbc_composition_controls.py::test_retracting_an_edge_stops_messages_already_queued_on_it`
- **Refusal codes:** `GRAPH_NOT_DECLARED`, `NODE_NOT_ADMITTED`
- **Standards:** NIST AI RMF MAP

### SWM-4 · Population and depth ceilings (level 4)

- **Objective:** A task has a maximum number of agents and a maximum delegation depth.
- **Prevents:** runaway spawning
- **Ask yourself:** Is there a hard ceiling on how many agents a task may create and how deep delegation may go?
- **Owner:** Enforcer operations
- **Requires:** SWM-1
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_sdk.py::test_population_ceiling_is_enforced`; `tests/test_tbc_sdk.py::test_population_depth_ancestry_and_revocation`
- **Refusal codes:** `POPULATION_LIMIT`, `DELEGATION_DEPTH`
- **Standards:** OWASP LLM10 Unbounded Consumption

### SWM-5 · Fan-in gate; agreement is evidence, not authority (level 4)

- **Objective:** A coordinator accepts a worker result only with verified identity, provenance, current epoch and permitted destination; consensus among agents never substitutes for approval.
- **Prevents:** poisoned or stale worker results and fake consensus
- **Ask yourself:** When a coordinator combines worker outputs, does it verify where each came from, and is agreement ever treated as permission?
- **Owner:** Enforcer operations
- **Requires:** SWM-3
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_composition_controls.py::test_fan_in_checks_identity_provenance_epoch_and_destination`; `tests/test_tbc_composition_controls.py::test_fan_in_refuses_results_without_provenance_or_from_revoked_workers`
- **Refusal codes:** `STALE_RESULT`
- **Standards:** OWASP LLM09 Misinformation

### SWM-6 · Revocation epoch and freshness proofs (level 4)

- **Objective:** Revocation raises the task epoch so queued work, stale leases and later release chunks fail; adapters outside the transaction demand a fresh proof.
- **Prevents:** work that outlives the authority that started it
- **Ask yourself:** When consent or authority is withdrawn, does queued and in-flight agent work fail immediately?
- **Owner:** Enforcer operations
- **Requires:** SWM-1
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_composition_controls.py::test_task_revocation_fails_queued_writes_and_later_release_chunks`; `tests/test_tbc_composition_controls.py::test_freshness_proof_fails_on_epoch_change_age_stop_or_forgery`
- **Refusal codes:** `STALE_PROPOSAL`, `FRESHNESS_UNPROVEN`, `AGENT_REVOKED_OR_EXPIRED`
- **Standards:** NIST AI RMF MANAGE

### SWM-7 · Monitors are brakes, never keys (level 4)

- **Objective:** Monitors and behaviour watches can restrict or quarantine but hold no method to grant or restore authority; probing agents are contracted.
- **Prevents:** a fooled or hostile monitor escalating privilege
- **Ask yourself:** Can your monitoring stack only ever restrict agents, never grant them power?
- **Owner:** Evidence auditor
- **Requires:** SWM-6
- **Implemented in:** `src/fssaira/tbc/runtime.py`, `src/fssaira/tbc/behaviour.py`
- **Prove it:** `tests/test_behaviour_watch.py::test_an_agent_probing_its_boundary_is_quarantined`; `tests/test_behaviour_watch.py::test_only_a_monitor_can_run_the_watch`
- **Refusal codes:** `MONITOR_REPLAY`, `STALE_MONITOR_EVIDENCE`
- **Standards:** NIST AI RMF MEASURE

### SWM-8 · Agent memory is scoped, retained and lineage-carrying (level 4)

- **Objective:** Persistent memory is namespaced, epoch-bound, expires on a declared retention, and keeps the labels and lineage of what was stored.
- **Prevents:** memory poisoning across tasks and label laundering through memory
- **Ask yourself:** Is agent memory scoped to its task and expiring, so it cannot leak into or poison another task?
- **Owner:** Enforcer operations
- **Requires:** DAT-3, SWM-6
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_sdk.py::test_memory_integrity_retention_scope_and_reauthorization`
- **Refusal codes:** `RETENTION_TOO_LONG`
- **Standards:** OWASP LLM04 Data and Model Poisoning


## EFF — Effects and adapters

### EFF-1 · Idempotent retries and reconciled uncertain outcomes (level 2)

- **Objective:** Retries reuse a persistent request identity; an outcome that is unknown is marked uncertain and reconciled once, never blindly retried.
- **Prevents:** the double email and the double payment
- **Ask yourself:** When a call times out, does your system establish whether the action happened before it retries?
- **Owner:** Enforcer operations
- **Requires:** AUT-1
- **Implemented in:** `src/fssaira/exact_action.py`
- **Prove it:** `tests/test_exact_action.py::test_retry_is_idempotent_and_cross_request_reuse_is_denied`; `tests/test_exact_action.py::test_completed_mutation_is_marked_uncertain_then_reconciled_once`
- **Standards:** NIST AI RMF MANAGE

### EFF-2 · Fenced commit across adapters (level 4)

- **Objective:** External effects commit in one linearizable step against the current epoch, carry an idempotency key, and are held when the store is unreachable.
- **Prevents:** stale effects under partition or clock skew, and duplicates on retry
- **Ask yourself:** Do your real adapters commit each action at most once and never after revocation, even under network faults?
- **Owner:** Enforcer operations · **Applies when:** agents cause effects in external systems
- **Requires:** EFF-1, SWM-6
- **Implemented in:** `src/fssaira/revocation_chaos.py`
- **Prove it:** `tests/test_revocation_chaos.py::test_fenced_commit_holds_every_invariant_and_each_ablation_breaks_one`; `command: fssaira assure chaos`
- **Standards:** NIST AI RMF MANAGE

### EFF-3 · Your own store and sink are qualified (level 5)

- **Objective:** The deployment's own authority store and external systems pass the fault campaign and the concurrent linearization audit.
- **Prevents:** a correct protocol running on an incorrect database or connector
- **Ask yourself:** Have your production authority store and connectors themselves passed fault-injected qualification?
- **Owner:** Enforcer operations · **Applies when:** agents cause effects in external systems
- **Requires:** EFF-2
- **Implemented in:** `src/fssaira/adapter_qualification.py`
- **Prove it:** `tests/test_adapter_qualification.py::test_reference_sql_store_and_sink_qualify`; `tests/test_adapter_qualification.py::test_a_store_that_forgets_the_epoch_is_not_qualified`
- **Refusal codes:** `ADAPTER_NOT_QUALIFIED`, `STORE_STALE_COMMIT`
- **Standards:** NIST AI RMF MEASURE


## EVD — Evidence

### EVD-1 · Tamper-evident log, intent before effect, no protected values (level 1)

- **Objective:** Intent is recorded before any effect, the log is hash-chained and written through a credential agents do not hold, and it never contains protected values.
- **Prevents:** silent actions and logs that become a second data breach
- **Ask yourself:** Is every agent action logged before it happens, in a log agents cannot write to and that contains no personal data?
- **Owner:** Evidence auditor
- **Requires:** nothing
- **Implemented in:** `src/fssaira/evidence.py`, `src/fssaira/joined_workflow.py`
- **Prove it:** `tests/test_disclosure.py::test_intent_evidence_failure_releases_nothing`; `tests/test_disclosure.py::test_evidence_never_contains_protected_values`
- **Refusal codes:** `LEDGER_CHAIN_BROKEN`
- **Standards:** NIST AI RMF MEASURE, ISO/IEC 42001

### EVD-2 · Decision receipts (level 2)

- **Objective:** Every decision yields a chained receipt binding policy version, epoch, lineage, artifact digest, recipient and outcome -- digests, never text.
- **Prevents:** incidents and appeals nobody can reconstruct
- **Ask yourself:** For any agent decision, can you show which policy, which inputs and which approval produced it, without reading the data?
- **Owner:** Evidence auditor
- **Requires:** EVD-1
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_tbc_composition_controls.py::test_receipts_bind_policy_epoch_lineage_digest_recipient_and_outcome`; `tests/test_tbc_composition_controls.py::test_receipt_chain_detects_deletion_and_survives_pruning`
- **Standards:** ISO/IEC 42001, NIST AI RMF GOVERN

### EVD-3 · Signed checkpoints and an independent witness (level 3)

- **Objective:** A notary signs checkpoints and a separately administered witness co-signs only consistent growth, refusing forks and rollbacks.
- **Prevents:** an insider or compromised enforcer rewriting history
- **Ask yourself:** Would a party outside your administrators detect it if someone with admin access rewrote the agent logs?
- **Owner:** Evidence auditor
- **Requires:** EVD-1
- **Implemented in:** `src/fssaira/evidence_notary.py`, `src/fssaira/witness.py`
- **Prove it:** `tests/test_witness.py::test_an_enforcer_holding_the_notary_key_cannot_get_a_rewritten_past_cosigned`; `tests/test_witness.py::test_a_truncated_ledger_is_a_rollback`
- **Refusal codes:** `WITNESS_FORK`, `WITNESS_ROLLBACK`, `LEDGER_HISTORY_REWRITTEN`
- **Standards:** NIST AI 600-1 Information Integrity

### EVD-4 · Independent recomputation on a cadence (level 3)

- **Objective:** A verifier outside the enforcer recomputes the archive hourly (incremental) and daily (full); forged records are quarantined by position, not content.
- **Prevents:** trusting stored verdicts
- **Ask yourself:** Does someone other than the system itself recompute the evidence regularly?
- **Owner:** Evidence auditor
- **Requires:** EVD-3
- **Implemented in:** `src/fssaira/small_data.py`, `src/fssaira/chain_verification.py`
- **Prove it:** `tests/test_small_data.py::test_forged_record_is_quarantined_by_position_not_content`; `command: fssaira small verify --mode full`
- **Standards:** NIST AI RMF MEASURE

### EVD-5 · Metadata-only visibility and agent dossiers (level 3)

- **Objective:** Dashboards and dossiers show identity, authority, actions, refusals and channel capacity per agent, without protected content.
- **Prevents:** observability that becomes surveillance or a leak
- **Ask yourself:** Can you see what each agent may do and has done without anyone reading protected data?
- **Owner:** Evidence auditor
- **Requires:** EVD-2
- **Implemented in:** `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_agent_dossier.py::test_the_dossier_holds_no_protected_content`
- **Standards:** NIST AI RMF MEASURE

### EVD-6 · Merkle proofs and a witness quorum across organisations (level 5)

- **Objective:** Evidence is committed in an RFC 9162 tree; witnesses in distinct administrative domains co-sign from consistency proofs; split views are detected.
- **Prevents:** one organisation (or one coerced witness) vouching for history; different logs for different audiences
- **Ask yourself:** Do at least two organisations outside yours co-sign your evidence, and would they catch you showing different logs to different people?
- **Owner:** Evidence auditor
- **Requires:** EVD-3
- **Implemented in:** `src/fssaira/transparency.py`
- **Prove it:** `tests/test_transparency.py::test_quorum_counts_distinct_domains_not_keys`; `tests/test_transparency.py::test_split_view_is_proven_by_two_signed_heads`
- **Refusal codes:** `WITNESS_QUORUM_NOT_MET`, `EVIDENCE_SPLIT_VIEW`, `MERKLE_FORK`
- **Standards:** NIST AI 600-1 Information Integrity

### EVD-7 · Forward-secure keys and anchored time (level 5)

- **Objective:** Checkpoints are signed with period keys erased after use and anchored to several independent time sources.
- **Prevents:** a stolen key or a moved clock backdating history
- **Ask yourself:** If your signing key were stolen today, would a checkpoint the thief backdated to last month be rejected?
- **Owner:** Evidence auditor
- **Requires:** EVD-6
- **Implemented in:** `src/fssaira/forward_secure.py`, `src/fssaira/time_anchor.py`
- **Prove it:** `tests/test_forward_secure_and_time.py::test_a_key_stolen_today_cannot_sign_yesterday`; `tests/test_forward_secure_and_time.py::test_a_lying_server_is_caught_by_the_chain`
- **Refusal codes:** `FS_WRONG_PERIOD`, `TIME_SOURCES_DISAGREE`, `CHECKPOINT_TIME_UNANCHORED`
- **Standards:** NIST AI 600-1 Information Integrity

### EVD-8 · Federated publication with per-record proofs (level 5)

- **Objective:** Each checkpoint is published in one step (root, forward-secure signature, time anchor, quorum) and verified in one verdict; any single record can be proven included.
- **Prevents:** evidence controls checked piecemeal, and appeals that need the whole ledger
- **Ask yourself:** Can an auditor verify a checkpoint in one step, and can you prove one decision is in it without revealing the rest?
- **Owner:** Evidence auditor
- **Requires:** EVD-6, EVD-7
- **Implemented in:** `src/fssaira/evidence_federation.py`
- **Prove it:** `tests/test_evidence_federation.py::test_the_real_runtime_ledger_publishes_and_proves_a_receipt`
- **Refusal codes:** `EVIDENCE_ROOT_MISMATCH`, `EVIDENCE_RECORD_NOT_INCLUDED`
- **Standards:** NIST AI 600-1 Information Integrity


## OVS — Human oversight

### OVS-1 · Deliberation floor (level 2)

- **Objective:** Approvals faster than a declared minimum review time are refused and routed to the manual queue.
- **Prevents:** rubber-stamping
- **Ask yourself:** Are approvals faster than a declared minimum review time refused and sent to a person?
- **Owner:** Workflow owner
- **Requires:** AUT-3
- **Implemented in:** `src/fssaira/oversight.py`, `src/fssaira/tbc/runtime.py`
- **Prove it:** `tests/test_oversight.py::test_an_approval_faster_than_the_deliberation_floor_is_refused`; `tests/test_tbc_composition_controls.py::test_minimum_review_time_defers_fast_approvals_to_the_manual_route`
- **Refusal codes:** `REVIEW_DEFERRED_TO_MANUAL`
- **Standards:** NIST AI 600-1 Human-AI Configuration

### OVS-2 · Declared review capacity and escalation (level 4)

- **Objective:** Each reviewer's capacity is declared; approvals past it are refused, and sustained load escalates to a second distinct reviewer.
- **Prevents:** fatigue silently deleting the last human control
- **Ask yourself:** Do you know how many consequential approvals a reviewer can do well per day, and does the system stop at that number?
- **Owner:** Workflow owner
- **Requires:** OVS-1
- **Implemented in:** `src/fssaira/oversight.py`
- **Prove it:** `tests/test_oversight.py::test_the_ceiling_refuses_the_next_approval_rather_than_flagging_it`; `tests/test_oversight.py::test_sustained_load_escalates_to_a_second_distinct_reviewer`
- **Standards:** NIST AI 600-1 Human-AI Configuration

### OVS-3 · Staffed to the floor (level 4)

- **Objective:** Headcount is computed from arrival rate and review time with the floor as minimum service time; understaffing defers, never lowers the floor.
- **Prevents:** queues that tempt someone to switch the floor off
- **Ask yourself:** Is review staffing calculated from demand, and is the answer to overload "more people", never "faster approvals"?
- **Owner:** Workflow owner
- **Requires:** OVS-2
- **Implemented in:** `src/fssaira/oversight_staffing.py`
- **Prove it:** `tests/test_master_guide_measures.py::test_staffing_honours_the_floor_and_reports_understaffing`; `command: fssaira assure staffing`
- **Standards:** NIST AI RMF MANAGE

### OVS-4 · Independent assistance for review (level 4)

- **Objective:** A lowered floor for AI-assisted review needs declared model, evidence-path and adversarial independence from the proposer.
- **Prevents:** the assistant repeating the proposer's error while every control stays green
- **Ask yourself:** If an AI helps reviewers, is it independent of the AI that made the proposal?
- **Owner:** Workflow owner · **Applies when:** reviewers are assisted by an AI model
- **Requires:** OVS-1
- **Implemented in:** `src/fssaira/assisted_review.py`
- **Prove it:** `tests/test_assisted_review.py::test_a_lowered_floor_without_declared_independence_is_refused`
- **Refusal codes:** `ASSISTANCE_NOT_DECLARED`
- **Standards:** NIST AI 600-1 Human-AI Configuration

### OVS-5 · Reviewer calibration with canaries (level 5)

- **Objective:** Known-wrong canary proposals are planted at a declared rate; a reviewer who approves them loses capacity and gains a second reviewer; canaries never execute.
- **Prevents:** capacity declared but never measured
- **Ask yourself:** Do you test, continuously and safely, that reviewers actually catch bad proposals?
- **Owner:** Workflow owner
- **Requires:** OVS-2
- **Implemented in:** `src/fssaira/review_calibration.py`
- **Prove it:** `tests/test_review_calibration.py::test_a_reviewer_who_approves_canaries_loses_capacity_and_gains_a_second_reviewer`; `tests/test_review_calibration.py::test_a_canary_never_executes_whatever_the_reviewer_decides`
- **Standards:** NIST AI RMF MEASURE


## ASR — Assurance and verification

### ASR-1 · Registered refusal codes (level 2)

- **Objective:** Every refusal code the build can emit is in a registry generated from source; the build fails when it drifts.
- **Prevents:** contracts and dashboards that test for codes that do not exist
- **Ask yourself:** Is there a complete, generated list of every reason your system can refuse?
- **Owner:** Evidence auditor
- **Requires:** nothing
- **Implemented in:** `src/fssaira/refusal_registry.py`
- **Prove it:** `tests/test_master_guide_measures.py::test_refusal_registry_is_current_with_the_code`
- **Standards:** ISO/IEC 42001

### ASR-2 · Every control is load-bearing (level 3)

- **Objective:** Removing each control in turn brings back a named harm.
- **Prevents:** controls that exist on paper but do nothing
- **Ask yourself:** For each control, have you shown the harm that returns when it is switched off?
- **Owner:** Evidence auditor
- **Requires:** ASR-1
- **Implemented in:** `src/fssaira/conformance.py`
- **Prove it:** `tests/test_ablations.py::test_removing_human_approval_enables_unilateral_high_impact`; `tests/test_ablations.py::test_removing_egress_control_enables_exfiltration`
- **Standards:** NIST AI RMF MEASURE

### ASR-3 · Bounded model check of the authority space (level 3)

- **Objective:** The declared authority and disclosure space is enumerated against a reference predicate written independently of the implementation.
- **Prevents:** configurations nobody thought to test
- **Ask yourself:** Has every combination of role, operation and state in your policy been checked, not just the happy paths?
- **Owner:** Evidence auditor
- **Requires:** ASR-2
- **Implemented in:** `src/fssaira/verification.py`
- **Prove it:** `tests/test_verification_and_conformance.py::test_the_declared_authority_space_contains_no_violation`
- **Standards:** NIST AI RMF MEASURE

### ASR-4 · Falsification campaign (level 4)

- **Objective:** Every falsifier is run for every domain pack in scope; removing one mediator check must produce a counterexample.
- **Prevents:** a safety claim nobody tried to break
- **Ask yourself:** Do you actively try to break your own safety claims, and does the attempt succeed when a check is removed?
- **Owner:** Evidence auditor
- **Requires:** ASR-3
- **Implemented in:** `src/fssaira/thesis.py`, `src/fssaira/falsification.py`
- **Prove it:** `tests/test_thesis.py::test_the_falsifiers_find_counterexamples_when_one_mediator_check_is_removed`
- **Standards:** NIST AI RMF MEASURE

### ASR-5 · Trusted base measured and attested (level 5)

- **Objective:** SLOC per trusted component, an SBOM and a build measurement pinned by attestation; a changed measurement is a changed enforcer.
- **Prevents:** the phrase "small trusted base" used as an unfalsifiable slogan
- **Ask yourself:** Do you know exactly which code you trust, how big it is, and that production runs that code?
- **Owner:** Enforcer operations
- **Requires:** ASR-1
- **Implemented in:** `src/fssaira/trusted_base.py`
- **Prove it:** `tests/test_master_guide_measures.py::test_trusted_base_is_measured_and_a_minority_of_the_package`; `command: fssaira assure trusted-base`
- **Standards:** OWASP LLM03 Supply Chain

### ASR-6 · Reproducible assurance report per release (level 5)

- **Objective:** Each release carries a digest-stamped report of every engineering check; buyers reproduce the digest.
- **Prevents:** assurance that is a slide, not a result
- **Ask yourself:** Can a buyer or auditor rerun your assurance and get the same digest?
- **Owner:** Evidence auditor
- **Requires:** ASR-5, EFF-2, EVD-8
- **Implemented in:** `src/fssaira/assurance_report.py`
- **Prove it:** `tests/test_assurance_report.py::test_report_passes_and_its_digest_is_reproducible`; `command: fssaira assure report`
- **Standards:** ISO/IEC 42001

### ASR-7 · Independent review and field evidence (level 5)

- **Objective:** An independent security review and a bounded pilot produce findings, remediation and outcome measures for this deployment.
- **Prevents:** authors grading their own threat model
- **Ask yourself:** Has someone outside the team attacked this deployment, and has a real pilot measured outcomes?
- **Owner:** Executive sponsor
- **Requires:** ASR-6
- **Implemented in:** `docs/PILOT_PROTOCOL.md`, `docs/GAPS.md`
- **Prove it:** `attestation: independent review report and pilot exit report, versioned to the deployment`
- **Standards:** NIST AI RMF GOVERN, ISO/IEC 42001
