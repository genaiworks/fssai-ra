# Trust by Construction canonical patterns

[Framework](../FRAMEWORK.md) · [Operational controls](CONTROLS.md)

Generated from `src/fssaira/framework_catalogue.yaml` (catalogue 1.1) by `fssaira framework render`. Edit the catalogue, not this document.

**34 patterns, 59 operational controls, one framework.** P1–P10 retain the reviewed V27 decision and composition core. P11–P34 retain V28's evidence, containment, visibility and consequence extensions. Controls add owners, dependencies and assessment obligations; they are not a second pattern list.

The evidence scopes below describe reference mechanisms and their limits. A named test is an executable evidence locator, not a claim that it passed on your host. Observations may be refusals, configuration findings or properties; only the separately listed registered codes belong to the refusal-code registry.

## One assessment scale

| Level | Name |
|---|---|
| 0 | Model-centred (no evidenced level) |
| 1 | Access-controlled |
| 2 | Authority-bound |
| 3 | Disclosure-governed |
| 4 | Composition-safe |
| 5 | Evidenced |

V28's alternative labels for levels 3–5 are superseded. Level 0 is a baseline, not an additional certified tier. Assessment answers are self-reported; an evidence bundle and reviewer must substantiate them. No level grants blanket production approval.

## Pattern index

| Pattern | Family | Operational controls | Evidence scope |
|---|---|---|---|
| P1 Declared authority ceiling | Decision and composition | GOV-2, IDN-2 | local-reference |
| P2 Task contract | Decision and composition | GOV-2, SWM-1, SWM-6 | local-reference |
| P3 Credentialless runtime | Decision and composition | IDN-1, AUT-1 | deployment-dependent |
| P4 Attenuated delegation | Decision and composition | SWM-2, SWM-4 | local-reference |
| P5 Mediated context | Decision and composition | DAT-1, DAT-2 | local-reference |
| P6 Reauthorised memory | Decision and composition | SWM-8 | local-reference |
| P7 Typed effect | Decision and composition | AUT-1, AUT-2, AUT-3, AUT-4, EFF-1, EFF-2, EFF-3 | local-reference |
| P8 Sealed release | Decision and composition | DAT-2, DAT-3, DAT-4 | local-reference |
| P9 Restricting monitor | Decision and composition | SWM-7 | local-reference |
| P10 Declared task graph | Decision and composition | SWM-3, SWM-5 | local-reference |
| P11 Intent before effect | Evidence and lifecycle | EVD-1, EVD-2 | local-reference |
| P12 Witnessed checkpoints | Evidence and lifecycle | EVD-3, EVD-6, EVD-7, EVD-8 | deployment-dependent |
| P13 Divergence-refusing archive | Evidence and lifecycle | EVD-9 | deployment-dependent |
| P14 Recompute, never read | Evidence and lifecycle | EVD-4 | deployment-dependent |
| P15 Signed crossing | Evidence and lifecycle | EVD-10 | deployment-dependent |
| P16 Quarantine by position | Evidence and lifecycle | EVD-10 | local-reference |
| P17 No silent loss | Evidence and lifecycle | EVD-10 | deployment-dependent |
| P18 Assurance bound to exact code | Evidence and lifecycle | ASR-8 | deployment-dependent |
| P19 Kernel floor | Evidence and lifecycle | GOV-5 | local-reference |
| P20 Fail-secure declaration | Evidence and lifecycle | GOV-6 | deployment-dependent |
| P21 Proportionate evidence plane | Evidence and lifecycle | ASR-9 | deployment-dependent |
| P22 Erasure by key destruction | Evidence and lifecycle | DAT-7 | deployment-dependent |
| P23 Contained agent cell | Containment and visibility | IDN-4 | deployment-dependent |
| P24 Bounded execution | Containment and visibility | IDN-5 | deployment-dependent |
| P25 Monitor without trust | Containment and visibility | SWM-7 | bounded-mitigation |
| P26 Metadata-only visibility | Containment and visibility | EVD-5, DAT-5 | local-reference |
| P27 Measured covert channels | Containment and visibility | DAT-6 | bounded-mitigation |
| P28 Self-describing deployment | Containment and visibility | GOV-6, EVD-5 | local-reference |
| P29 Evidence-grounded effect | Correctness and consequence | AUT-6 | bounded-mitigation |
| P30 Mandate linting | Correctness and consequence | GOV-5 | bounded-mitigation |
| P31 Behaviour watch | Correctness and consequence | SWM-7 | bounded-mitigation |
| P32 Delayed commitment | Correctness and consequence | AUT-5 | bounded-mitigation |
| P33 Reviewer canaries | Correctness and consequence | OVS-1, OVS-2, OVS-3, OVS-4, OVS-5 | bounded-mitigation |
| P34 Channel budget | Correctness and consequence | DAT-6 | bounded-mitigation |

## P1 Declared authority ceiling

The operator installs a workload’s maximum authority. A model never requests it.

- **Operational controls:** GOV-2, IDN-2
- **Implementation:** `src/fssaira/tbc/contracts.py`, `src/fssaira/tbc/mandate.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_tbc_sdk.py::test_lease_cannot_expand_any_authority_axis`
- **Test observation:** ENVELOPE_DENIED
- **Registered refusal codes:** `ENVELOPE_DENIED`
- **Evidence scope:** local-reference
- **Limits:** The installed ceiling can itself be wrong; policy ownership and independent review remain necessary.

## P2 Task contract

Every task names purpose, subject, tenant, scope, budget and expiry before work starts.

- **Operational controls:** GOV-2, SWM-1, SWM-6
- **Implementation:** `src/fssaira/tbc/contracts.py`, `src/fssaira/tbc/mandate.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_tbc_sdk.py::test_aggregate_sibling_budget_does_not_multiply`
- **Test observation:** INVALID_TASK_FIELDS
- **Registered refusal codes:** `INVALID_TASK_FIELDS`
- **Evidence scope:** local-reference
- **Limits:** Shared-state and freshness tests cover declared local configurations, not arbitrary distributed interleavings.

## P3 Credentialless runtime

The component that reasons holds no store credential and no write credential.

- **Operational controls:** IDN-1, AUT-1
- **Implementation:** `src/fssaira/control_plane.py`, `src/fssaira/exact_action.py`, `src/fssaira/isolation.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_isolation.py::test_standing_credentials_in_the_agent_environment_are_a_violation`
- **Test observation:** no path exists
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** Credential separation depends on the deployed process, host and connector boundaries; SDK conventions alone do not isolate an agent.

## P4 Attenuated delegation

A child holds the intersection of every ancestor, and expires no later than its parent.

- **Operational controls:** SWM-2, SWM-4
- **Implementation:** `src/fssaira/delegation.py`, `src/fssaira/grant_delegation.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_delegation.py::test_a_hop_cannot_pass_on_authority_it_does_not_hold`
- **Test observation:** SCOPE_NOT_ATTENUATED
- **Registered refusal codes:** `SCOPE_NOT_ATTENUATED`
- **Evidence scope:** local-reference
- **Limits:** Attenuation does not establish correctness or benevolence of an authorised action.

## P5 Mediated context

The gate alone reads records, and returns grant ∩ request ∩ live consent ∩ zone.

- **Operational controls:** DAT-1, DAT-2
- **Implementation:** `src/fssaira/disclosure.py`, `src/fssaira/disclosure_api.py`
- **Test:** `tests/test_tbc_sdk.py::test_lease_expiry_and_task_expiry_are_checked_on_use`
- **Test observation:** CONTEXT_SCOPE_DENIED
- **Registered refusal codes:** `CONTEXT_SCOPE_DENIED`
- **Evidence scope:** local-reference
- **Limits:** Purpose identifiers select policy; they do not prove the model’s intention or source truth.

## P6 Reauthorised memory

Stored context carries provenance and retention, and is rechecked against live authority.

- **Operational controls:** SWM-8
- **Implementation:** `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_tbc_sdk.py::test_memory_integrity_retention_scope_and_reauthorization`
- **Test observation:** MEMORY_REAUTHORIZATION_DENIED
- **Registered refusal codes:** `MEMORY_REAUTHORIZATION_DENIED`
- **Evidence scope:** local-reference
- **Limits:** Restrictions are only as complete as the captured context and provenance; a claim to forget is not isolation.

## P7 Typed effect

An effect names operation, resource, expected version and state; approval signs that digest.

- **Operational controls:** AUT-1, AUT-2, AUT-3, AUT-4, EFF-1, EFF-2, EFF-3
- **Implementation:** `src/fssaira/adapter_qualification.py`, `src/fssaira/control_plane.py`, `src/fssaira/exact_action.py`, `src/fssaira/revocation_chaos.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_approval_boundary.py::test_executor_independently_refuses_signed_self_approval`
- **Test observation:** RESOURCE_RIGHTS_DENIED
- **Registered refusal codes:** `RESOURCE_RIGHTS_DENIED`
- **Evidence scope:** local-reference
- **Limits:** External effects require qualified adapters and reconciliation. A receipt does not make an irreversible effect reversible.

## P8 Sealed release

Release is a named review of exact bytes to an authenticated recipient, used once.

- **Operational controls:** DAT-2, DAT-3, DAT-4
- **Implementation:** `src/fssaira/disclosure.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_tbc_sdk.py::test_memory_and_generated_output_cannot_drop_session_lineage`
- **Test observation:** DESTINATION_DENIED
- **Registered refusal codes:** `DESTINATION_DENIED`
- **Evidence scope:** local-reference
- **Limits:** Already disclosed bytes cannot be recalled; redaction is not a general de-identification guarantee.

## P9 Restricting monitor

A monitor may contract authority. It can never grant any.

- **Operational controls:** SWM-7
- **Implementation:** `src/fssaira/tbc/behaviour.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_monitor_evaluation.py::test_a_hostile_monitor_costs_availability_not_authority`
- **Test observation:** contraction only
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** local-reference
- **Limits:** A hostile monitor can deny service. It must not expand authority.

## P10 Declared task graph

The agent and message graph is declared; a gate admits each node and edge before use.

- **Operational controls:** SWM-3, SWM-5
- **Implementation:** `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_tbc_composition_controls.py::test_declared_graph_admits_each_node_and_edge_before_use`
- **Test observation:** AIRLOCK_CHANNEL_DENIED
- **Registered refusal codes:** `AIRLOCK_CHANNEL_DENIED`
- **Evidence scope:** local-reference
- **Limits:** The declared graph must include every actual channel. Orchestrator-scale completeness is a deployment obligation.

## P11 Intent before effect

Record what is about to cross a boundary before it crosses; an unclosed intent is a recoverable signal

- **Operational controls:** EVD-1, EVD-2
- **Implementation:** `src/fssaira/evidence.py`, `src/fssaira/joined_workflow.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_import_api.py::test_import_gateway_records_an_unclosed_intent_when_delivery_fails`
- **Test observation:** no evidence write authority
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** local-reference
- **Limits:** Intent records identify incomplete work; durable mutation-and-outcome atomicity depends on the chosen backend.

## P12 Witnessed checkpoints

Sign the ledger's count and head; an out-of-process witness co-signs only heads that extend what it already signed

- **Operational controls:** EVD-3, EVD-6, EVD-7, EVD-8
- **Implementation:** `src/fssaira/evidence_federation.py`, `src/fssaira/evidence_notary.py`, `src/fssaira/forward_secure.py`, `src/fssaira/time_anchor.py`, `src/fssaira/transparency.py`, `src/fssaira/witness.py`
- **Test:** `tests/test_witness.py::test_an_enforcer_holding_the_notary_key_cannot_get_a_rewritten_past_cosigned`
- **Test observation:** WITNESS_FORK
- **Registered refusal codes:** `WITNESS_FORK`
- **Evidence scope:** deployment-dependent
- **Limits:** Independent administration and external retention must be established in deployment. Witnesses cannot prevent a compromised enforcer from signing new false events.

## P13 Divergence-refusing archive

Keep a second copy under other administration; refuse to archive a primary that got shorter or different

- **Operational controls:** EVD-9
- **Implementation:** `src/fssaira/iceberg_backend.py`, `src/fssaira/small_data.py`
- **Test:** `tests/test_tier_equivalence.py::test_rewritten_ledger_is_refused`
- **Test observation:** ARCHIVE_DIVERGED
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** Detects divergence against the retained archive; it does not establish truth of original events or independence of administrators.

## P14 Recompute, never read

A separate process recomputes every hash from the archived copy; incremental passes are anchored and a full pass recurs

- **Operational controls:** EVD-4
- **Implementation:** `src/fssaira/chain_verification.py`, `src/fssaira/small_data.py`
- **Test:** `tests/test_small_data.py::test_incremental_pass_catches_a_bad_new_record_and_a_changed_head`
- **Test observation:** VERIFIED_HEAD_CHANGED
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** Incremental passes do not re-read all earlier records; detection latency depends on full-verification cadence and retained anchors.

## P15 Signed crossing

Inputs are source-signed at the gateway and MAC-sealed onward; the sink recomputes the content hash before any commit

- **Operational controls:** EVD-10
- **Implementation:** `src/fssaira/import_boundary.py`, `src/fssaira/small_data.py`
- **Test:** `tests/test_small_data.py::test_content_hash_mismatch_commits_nothing`
- **Test observation:** invalid import envelope or content hash
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** Authenticated origin is not truth; signing keys and source identity must be protected.

## P16 Quarantine by position

A rejected record is kept as its position and a hash of its bytes, never its content; the stream continues

- **Operational controls:** EVD-10
- **Implementation:** `src/fssaira/import_boundary.py`, `src/fssaira/small_data.py`
- **Test:** `tests/test_small_data.py::test_forged_record_is_quarantined_by_position_not_content`
- **Test observation:** envelope MAC missing or invalid
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** local-reference
- **Limits:** Positions and hashes remain metadata requiring access controls and retention limits.

## P17 No silent loss

Logs carry a generation; a reset, truncation or gap stops the sink instead of being skipped

- **Operational controls:** EVD-10
- **Implementation:** `src/fssaira/import_boundary.py`, `src/fssaira/small_data.py`
- **Test:** `tests/test_small_data.py::test_a_record_deleted_before_import_stops_the_sink`
- **Test observation:** a record was deleted before it was imported
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** Continuity checks cover declared logs and generations, not unknown events never recorded by the source.

## P18 Assurance bound to exact code

A backend inherits no assurance until conformance ran on its exact implementation digest

- **Operational controls:** ASR-8
- **Implementation:** `src/fssaira/kernel/assurance.py`
- **Test:** `tests/kernel/test_kernel_assurance.py::test_code_changed_after_the_run_refuses`
- **Test observation:** ASSURANCE_IMPLEMENTATION_CHANGED
- **Registered refusal codes:** `ASSURANCE_IMPLEMENTATION_CHANGED`
- **Evidence scope:** deployment-dependent
- **Limits:** A digest pins identity, not correctness. A passing conformance suite supports only its exercised properties.

## P19 Kernel floor

A domain pack may tighten the kernel, never loosen it; a weakening pack stops the server from starting

- **Operational controls:** GOV-5
- **Implementation:** `src/fssaira/pack_floor.py`, `src/fssaira/tbc/mandate.py`
- **Test:** `tests/test_profile_floor.py::test_the_runtime_refuses_to_start_with_a_weakened_pack`
- **Test observation:** PACK_NON_HUMAN_APPROVER
- **Registered refusal codes:** `PACK_NON_HUMAN_APPROVER`
- **Evidence scope:** local-reference
- **Limits:** The kernel floor is itself trusted policy and must be reviewed; pack validation does not establish regulatory compliance.

## P20 Fail-secure declaration

A deployment that declares itself pilot or production refuses to start with a teaching default or an unknown declaration

- **Operational controls:** GOV-6
- **Implementation:** `src/fssaira/api.py`, `src/fssaira/security.py`
- **Test:** `tests/test_production_posture.py::test_a_pilot_with_teaching_defaults_refuses_to_start`
- **Test observation:** TEACHING_APPROVAL_KEY
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** A configuration declaration does not prove physical deployment. Startup checks cover recognised settings.

## P21 Proportionate evidence plane

The decision plane is identical at every scale; only the evidence plane is sized, and its verdicts must not change

- **Operational controls:** ASR-9
- **Implementation:** `src/fssaira/iceberg_backend.py`, `src/fssaira/small_data.py`
- **Test:** `tests/test_tier_equivalence.py::test_missing_tail_is_caught_only_by_the_signed_checkpoint`
- **Test observation:** BIG_TIER_WITHOUT_BROKER
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** Equivalence is bounded to the exercised scenarios. Backend concurrency and failure modes may differ; cost measurements are host-specific.

## P22 Erasure by key destruction

Subject data is sealed under custody keys; erasure destroys the key, so backups, indexes and restores stay unreadable

- **Operational controls:** DAT-7
- **Implementation:** `src/fssaira/custody_store.py`, `src/fssaira/key_custody.py`
- **Test:** `tests/test_custody_persistence.py::test_a_database_restore_does_not_resurrect_an_erased_subject`
- **Test observation:** CUSTODY_KEY_DESTROYED
- **Registered refusal codes:** `CUSTODY_KEY_DESTROYED`
- **Evidence scope:** deployment-dependent
- **Limits:** Erasure requires destruction of every usable key copy; exported plaintext and independent key backups remain outside this guarantee.

## P23 Contained agent cell

Qualify each deployed agent cell from inside its actual host boundary; refuse unmet or unmeasurable requirements.

- **Operational controls:** IDN-4
- **Implementation:** `src/fssaira/agent_cell.py`, `src/fssaira/isolation.py`
- **Test:** `tests/test_agent_cell.py::test_a_real_cell_is_isolated_when_measured_from_inside`
- **Test observation:** CELL_NOT_ISOLATED
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** A local container probe is a host observation, not proof against kernel exploits or evidence that every swarm worker is isolated.

## P24 Bounded execution

Generated code runs in a separate interpreter with an empty environment, limits recorded by the parent, and a timeout that kills its process group

- **Operational controls:** IDN-5
- **Implementation:** `src/fssaira/integration/sandbox.py`
- **Test:** `tests/integration/test_integration_sandbox.py::test_wall_clock_timeout_kills_the_process_group`
- **Test observation:** the sandbox requires POSIX rlimits and process groups
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** deployment-dependent
- **Limits:** A process under the same operating-system user is not a strong isolation boundary; use a qualified cell for hostile code.

## P25 Monitor without trust

A monitor can only restrict; across oracle, blind and hostile monitors and the live-model adapter, no protected outcome changes

- **Operational controls:** SWM-7
- **Implementation:** `src/fssaira/tbc/behaviour.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_monitor_evaluation.py::test_a_hostile_monitor_costs_availability_not_authority`
- **Test observation:** finding outside the declared vocabulary
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** bounded-mitigation
- **Limits:** Scripted and stand-in monitor results do not estimate production detector accuracy; an in-policy attack can evade detection.

## P26 Metadata-only visibility

Monitors see task metadata and the evidence head; metrics export counters; neither carries protected text, so watching cannot become a data path

- **Operational controls:** EVD-5, DAT-5
- **Implementation:** `src/fssaira/disclosure.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_agent_dossier.py::test_the_dossier_holds_no_protected_content`
- **Test observation:** metadata only, by construction
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** local-reference
- **Limits:** Metadata can identify people or reveal activity; avoid protected payloads and apply access controls and retention limits.

## P27 Measured covert channels

Compute and declare capacity for the explicitly modelled release choices; report unbounded or unmeasured dimensions.

- **Operational controls:** DAT-6
- **Implementation:** `src/fssaira/channel_slo.py`, `src/fssaira/covert_channels.py`
- **Test:** `tests/test_covert_channels.py::test_the_measured_leak_never_exceeds_the_declared_capacity`
- **Test observation:** EgressBudgetExhausted
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** bounded-mitigation
- **Limits:** Only modelled choices are measured. Unmodelled timing, count, payload and side channels may exceed the declared capacity.

## P28 Self-describing deployment

Publish declared and undeclared limits and derive agent dossiers from mediated state and integrity-checked receipts.

- **Operational controls:** GOV-6, EVD-5
- **Implementation:** `src/fssaira/api.py`, `src/fssaira/security.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_api.py::test_health_publishes_what_this_deployment_has_declared`
- **Test observation:** not declared: approvals are unlimited and the ceiling is unbounded
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** local-reference
- **Limits:** A dossier reports mediated records and declared limits, not hidden behavior or model reasoning.

## P29 Evidence-grounded effect

The source confirms only the value its own record supports; a wrong or steered value never gets the confirmation an approval needs

- **Operational controls:** AUT-6
- **Implementation:** `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_behaviour_watch.py::test_a_steered_wrong_value_is_refused_at_the_sources_confirmation`
- **Test observation:** UNSUPPORTED_PROPOSAL
- **Registered refusal codes:** `UNSUPPORTED_PROPOSAL`
- **Evidence scope:** bounded-mitigation
- **Limits:** Source confirmation proves consistency with a configured source, not that the source is correct, fair or current.

## P30 Mandate linting

A task contract is checked against its declared purpose and a corpus of known-bad mandates; any excess stops it starting

- **Operational controls:** GOV-5
- **Implementation:** `src/fssaira/pack_floor.py`, `src/fssaira/tbc/mandate.py`
- **Test:** `tests/test_mandate_lint.py::test_with_declared_purposes_an_over_broad_mandate_does_not_start`
- **Test observation:** MANDATE_UNNEEDED_OPERATION
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** bounded-mitigation
- **Limits:** A wrong purpose profile or incomplete known-bad corpus can admit a harmful mandate.

## P31 Behaviour watch

Boundary probing is counted from receipts and sandbagging measured on canaries; findings restrict the task, never grant

- **Operational controls:** SWM-7
- **Implementation:** `src/fssaira/tbc/behaviour.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_behaviour_watch.py::test_an_agent_probing_its_boundary_is_quarantined`
- **Test observation:** BOUNDARY_PROBING
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** bounded-mitigation
- **Limits:** Canaries and boundary-probing heuristics can miss strategic behavior that stays within the tested observables.

## P32 Delayed commitment

An approved effect waits out a window in which objection, revocation or an epoch change cancels it; it commits once, rechecked

- **Operational controls:** AUT-5
- **Implementation:** `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_effect_escrow.py::test_revoking_the_agent_during_the_window_cancels_at_commit`
- **Test observation:** OBJECTION_WINDOW_CLOSED
- **Registered refusal codes:** `OBJECTION_WINDOW_CLOSED`
- **Evidence scope:** bounded-mitigation
- **Limits:** Objection windows delay effects; effects delivered after a valid window still cannot necessarily be undone.

## P33 Reviewer canaries

Use declared review capacity and non-executing canaries to restrict review authority under the configured calibration model.

- **Operational controls:** OVS-1, OVS-2, OVS-3, OVS-4, OVS-5
- **Implementation:** `src/fssaira/assisted_review.py`, `src/fssaira/oversight.py`, `src/fssaira/oversight_staffing.py`, `src/fssaira/review_calibration.py`, `src/fssaira/tbc/runtime.py`
- **Test:** `tests/test_review_calibration.py::test_a_reviewer_who_approves_canaries_loses_capacity_and_gains_a_second_reviewer`
- **Test observation:** REVIEWER_CALIBRATION_LOW
- **Registered refusal codes:** none specified for this binding
- **Evidence scope:** bounded-mitigation
- **Limits:** Synthetic calibration is not a human study; recognisable canaries and manual-route outcomes need field evaluation.

## P34 Channel budget

Each release is charged the bits its open choices can carry against a task budget; past it, releases go to a person

- **Operational controls:** DAT-6
- **Implementation:** `src/fssaira/channel_slo.py`, `src/fssaira/covert_channels.py`
- **Test:** `tests/test_channel_budget.py::test_releases_past_the_channel_budget_go_to_a_person`
- **Test observation:** CHANNEL_BUDGET_EXHAUSTED
- **Registered refusal codes:** `CHANNEL_BUDGET_EXHAUSTED`
- **Evidence scope:** bounded-mitigation
- **Limits:** Enforcement applies to the declared channel model and observed releases; it is not a bound on all information leakage.
