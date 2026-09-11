# Operations and Recovery Runbook

## Routine checks

- `/health` reports the loaded profile, evidence-chain status, and unsafe teaching
  defaults.
- Redis persistence, replication, backup restoration, and memory limits meet the
  institution's recovery objectives.
- Kafka consumer lag, under-replicated partitions, authentication failures, and
  retention settings are monitored.
- Spark checkpoints and Iceberg snapshot/file retention remain mutually consistent.
- Evidence continuity is independently checked and anchored outside the writer's
  administrative domain.
- Manual fallback staffing and contact paths are exercised, not merely documented.

## Fail-secure events

| Signal | Automated response | Operator response |
|---|---|---|
| `APPROVAL_PAYLOAD_MISMATCH` | No mutation | Reopen review on the new proposal |
| `APPROVER_ROLE_NOT_ALLOWED` | No mutation | Correct identity or role assignment; do not bypass |
| `CASE_VERSION_CONFLICT` | No mutation | Reload current resource and seek renewed approval |
| `OUTCOME_EVIDENCE_PENDING` | Do not repeat mutation | Reconcile receipt, inspect target, then close incident |
| Evidence verification false | Freeze consequential automation | Preserve stores, investigate continuity, restore from trusted checkpoint |
| Import sequence stale or corrupt | Quarantine and stop affected feed | Use manual fallback; inspect source and transfer boundary |
| Kafka or policy dependency unavailable | Reject new consequential workflow | Restore dependency or use governed manual service |

## Recovery test schedule

Before a pilot and after material changes, inject failure immediately before target
commit, immediately after commit, before evidence append, during reconciliation, and
during service restart. Confirm that each request ends in exactly one of three states:
denied with no mutation, completed with one receipt, or explicitly uncertain and
owned until reconciled. Test restoration from backup in an isolated environment and
record actual recovery time.

## Production gaps intentionally left to adopters

The reference stack does not provide an identity provider, hardware security module,
certificate authority, Kafka authorization policy, Redis high availability, backup
system, SIEM integration, user-facing appeal service, domain policy, fairness study,
or certified data diode. Those choices are jurisdictional and institutional. Their
required observable properties belong in the adopter's control contract and tests.
