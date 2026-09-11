# Assurance claims and evidence

This document is the claim boundary for release `v0.3.0`. A passing test means the
specified property held for the synthetic fixture and implementation exercised by
that test. It does not establish comprehensive security, fairness, educational
benefit, or production readiness.

## Claim matrix

| Public claim | Enforcement or mechanism | Executable evidence | Limit |
|---|---|---|---|
| The control contract is structurally complete | Schema validation across five functional domains | `tests/test_contract.py` | Completeness of fields does not prove control effectiveness |
| The teaching agent cannot directly approve an award | Tool and operation allowlists in the policy enforcement point | `test_hallucinated_high_impact_action_needs_named_human` | A compromised enforcement service or host administrator is outside this claim |
| The simulated egress tool is denied by default | Explicit egress classification and default-deny policy | `test_prompt_injection_is_stripped_and_egress_blocked` | This does not inventory every real output, telemetry, DNS, or maintenance path |
| A bad-signature model specimen is quarantined | Trusted-source key check at import | `test_compromised_update_is_quarantined_and_no_self_escalation` | The demo uses a shared-secret digest, not production artifact signing |
| Altering a past evidence record is detectable | Hash-linked in-memory evidence records | `test_insider_record_tampering_is_detected` | A privileged writer can truncate or replace an uncheckpointed history |
| Approval fields are authenticated | Trusted-key HMAC verification in the executor | `test_tampered_approval_is_rejected_before_mutation`; `test_untrusted_approval_key_is_rejected_before_mutation` | The repository key is intentionally non-secret and must be replaced by a production identity and signing service |
| Approval covers one exact proposal | Canonical proposal digest checked by the executor | `test_target_or_arguments_changed_after_approval_are_denied` | The teaching authority is not a production identity service |
| The executor limits its own authority | Independent operation allowlist | `test_executor_rejects_an_approved_but_unallowlisted_operation` | A compromised executor or administrator remains outside this claim |
| A stale case requires renewed review | Expected authoritative case version and state | `test_changed_authoritative_case_requires_renewed_review` | Concurrent distributed databases require stronger transaction design |
| Retrying the same request does not duplicate the transition or its evidence | Persistent request identity and cached execution result | `test_retry_is_idempotent_and_cross_request_reuse_is_denied` | External tools must provide compatible idempotency, evidence, and status lookup |
| The requester cannot approve its own proposal | Separation-of-duties check in the approval authority | `test_requester_cannot_approve_own_proposal` | Identity administration and collusion are outside the teaching profile |
| Removing selected controls restores the demonstrated harm | Egress, human-approval, and least-privilege ablations | `tests/test_ablations.py` | A small ablation suite does not prove universal causality |

## What is not yet evidenced

- resistance to a shared host administrator or compromised signing authority;
- physical one-way transfer or a complete interface inventory;
- stochastic prompt-injection rates for a named model and configuration;
- real Kafka, Spark, Iceberg, or local-model conformance;
- policy/evidence outages and crashes around a real external side effect;
- reviewer accuracy, workload, appeal quality, fairness, accessibility, cost, or energy;
- institutional deployment, independent audit, penetration test, or certification.

These are planned evaluation areas. New evidence should be versioned with its test
inputs, environment, denominators, results, failures, and exclusions.

## Reproduction record

For a result intended for citation, record the repository commit, Python and
dependency versions, operating system, command, test count, and complete output.
Retain raw outputs before writing a narrative summary. Use a release tag rather than
an unversioned branch URL when comparing results across institutions.
