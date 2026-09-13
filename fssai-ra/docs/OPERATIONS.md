# Operations and Recovery Runbook

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Policy leader → [`SECURITY.md`](SECURITY.md) · engineer → [`EXTENDING.md`](EXTENDING.md)

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
- `/health` → `declared_controls` shows what this deployment has declared about
  review capacity, assistant independence, and delegation depth. A `null` there
  is a posture rather than an omission, and `fssaira doctor` says what it costs.
- `fssaira_review_capacity_declared` is **0** when no ceiling is declared. Alert
  on it: a deployment with no ceiling is indistinguishable on every other metric
  from one running comfortably inside its ceiling, right up to the point where
  it is not.
- `fssaira_review_headroom` reaching **0** means a reviewer is saturated and the
  next arrival takes the manual fallback. That is a capacity signal, not an
  error, and paging someone to raise the quota is the wrong response — see the
  fail-secure table below.

## What this deployment must declare about itself

Three controls cannot be derived from the software, because they are facts about
an institution rather than about a program. None of them falls back to a
reference value: a capacity figure inherited from this repository is one nobody
at your institution ever agreed to.

| Declaration | Variables | If you declare nothing |
|---|---|---|
| **Review capacity** | `FSSAI_REVIEW_MAX_PER_WINDOW`, `FSSAI_REVIEW_WINDOW_SECONDS`, `FSSAI_REVIEW_DELIBERATION_FLOOR`, `FSSAI_REVIEW_SECOND_REVIEWER_AFTER`, `FSSAI_REVIEW_SECONDS_PER_DAY` | Approvals are unlimited. Every consequential action still routes to a named human, and that human is assumed to have infinite attention. Reported as a **high** finding |
| **Review-assistant independence** | `FSSAI_REVIEW_ASSISTANCE_MODE`, `FSSAI_REVIEW_ASSISTANCE_DECLARED_BY`, `FSSAI_REVIEW_ASSISTANT_INDEPENDENT_MODEL`, `FSSAI_REVIEW_ASSISTANT_INDEPENDENT_EVIDENCE`, `FSSAI_REVIEW_ASSISTANT_ADVERSARIAL` | Reviewers are treated as unaided and the full deliberation floor applies — the strict default. Declaring assistance *without* independence, and lowering the floor anyway, is **blocking**: the deployment does not start |
| **Delegation bound** | `FSSAI_MAX_DELEGATION_DEPTH`, `FSSAI_HUMAN_APPROVAL_BELOW_DEPTH`, `FSSAI_ALLOW_MACHINE_DELEGATED_CONSEQUENCE` | No depth bound is enforced. Correct if one agent calls one tool; wrong the moment it calls a tool server, a plugin, or a sub-agent nobody here wrote. Reported as **info** |

Work the first one out before committing to it:

```bash
fssaira oversight profiles/your_profile.yaml --sweep   # what a roster sustains
fssaira assisted-review profiles/your_profile.yaml     # what an assistant costs
fssaira delegation --max-depth 3                       # what a chain confers
fssaira doctor                                         # what you have declared
```

`deploy/.env.example` carries the same variables with the reasoning inline, and
a test fails the build if it ever documents a variable no code reads.

> **The deliberation floor is the number to be honest about.** It is the time a
> careful reading genuinely takes, not the time you wish it took. Entering a
> number you would not defend to the person whose case was refused produces a
> ceiling you cannot defend either, and the tool cannot tell the difference.

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
| `REVIEW_CAPACITY_EXCEEDED` | No approval is issued; the action takes the manual fallback | Do not raise the quota to clear a backlog. The deferral count is the measurement: demand exceeded the capacity this institution declared. Staff it, narrow what counts as consequential, or publish the queue length |
| `DELIBERATION_TOO_SHORT` | No approval is issued | Check whether reviewers acquired an assistant nobody declared. Lowering the floor is correct only in proportion to declared independence |
| `SECOND_REVIEWER_REQUIRED` | No approval is issued | Supply a distinct second reviewer, or take the manual fallback. Two signatures under the same backlog are not two independent judgements |
| `FLOOR_BELOW_DECLARED_INDEPENDENCE` | The deployment refuses to start | Raise the floor, or establish and declare a different model, a different evidence path, and an adversarial posture for the review assistant |
| `SCOPE_NOT_ATTENUATED`, `CHAIN_NOT_ROOTED`, `CHAIN_CYCLE`, `DEPTH_EXCEEDED` | No mutation | A chain tried to confer authority its root never granted. Record the chain and the hop that failed; treat an unrooted chain as an unreviewed authority path |
| `REQUESTER_NOT_CHAIN_LEAF` | No mutation | A principal presented a chain that authorises someone else. Treat as a credential-handling incident, not a routing bug |
| `DELEGATION_OUTLIVES_DELEGATOR` | No mutation | An ancestor grant lapsed. Note that revocation is **not** pushed to already-issued descendants: they fail at use time, and the window is unbounded |
| `INVALID_REVIEW_POLICY`, `INVALID_REVIEW_ASSISTANCE`, `INVALID_DELEGATION_POLICY` | Readiness is blocking and deployment assembly fails for the malformed declaration | Correct the named environment variable. Ambiguous booleans and malformed numbers are not silently interpreted as permission |

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
