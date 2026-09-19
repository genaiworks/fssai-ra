# Security review of the v13 reference implementation

This review fixes three local security-boundary defects and keeps the paper's
claims tied to observable behavior. It does not certify that all defects or all
architecture gaps have been eliminated. The manuscript remains v13; its current
source is `paper/tbc-v13/TBC_v13_Frontier_Threat_Revision.docx`.

## Reproduced defects and repairs

| Defect | Consequence | Repair and evidence |
| --- | --- | --- |
| Monitor history scanned the last 128 global events before selecting a task, and findings depended on the global evidence head | Unrelated work could hide relevant history or invalidate pending advice | Select task evidence before limiting it; separate task and global-control freshness. The regression floods another task with 140 operations, preserves the first task's history, applies its pending restriction and verifies the other task still works. |
| Monitor verdict/reason values entered set-membership checks without type validation | Lists or objects raised an uncontrolled TypeError | Require string fields before interpretation. Fifteen malformed-value cases check controlled rejection and legitimate continuation. |
| Destination paths admitted matrix parameters, encoded delimiters and other parser ambiguities | A downstream router could interpret an approved path differently | Reject ambiguous paths before authorization. Nine negative cases plus a positive unreserved-encoding and mixed-DNS case exercise the contract. |

The 58-case focused suite fails 14 cases against the pre-review implementation
at `3f65aae` and passes after these changes. The old code was evaluated in an
isolated source copy against the new tests. This is a before/after defect check,
not a benchmark of model susceptibility. The added 27 cases are included in the
full suite; they must not be added again to the aggregate total.

```sh
# From fssai-ra after installing development dependencies
make security-review PYTHON=.venv/bin/python
make all PYTHON=.venv/bin/python
```

`make all` executes lint, the full regression suite, preserved-paper bindings,
capability-contract tests, current-paper evidence checks and regeneration of
126 reported numeric results. The manuscript is byte-reproducible from its
preserved source and reviewed JSON content. The separate verification JSON in
the delivery package records the executed counts and commit.

## Practical use

An institution can use the reference to exercise a transcript-correction
workflow before connecting an agent to real records: separate source
confirmation from review, scope data access, deny forged approvals, preserve
source restrictions through memory, stop authority durably, and reauthorize
recipient delivery. A safety monitor's generated finding may contract authority
but cannot approve a business action. The reference's failure tests make these
properties inspectable even when an agent or monitor supplies hostile input.

Recent research added to the paper includes
[AgentSecBench](https://arxiv.org/abs/2605.26269) and
[AgentDyn](https://arxiv.org/abs/2602.03117). Both strengthen the motivation for
checking security and useful task completion together. Neither benchmark was
run here, and no comparative score is claimed. The repository threat model also
records the September 2026 incident assessment separately from the research-paper
bibliography.

## Remaining gaps and concrete acceptance requirements

The 109-control architecture register remains the scope authority. Local tests
cannot establish properties of infrastructure that has not been deployed.

| Remaining work | Evidence needed before claiming it |
| --- | --- |
| Process and network isolation | Run an adversarial process in the intended deployment; demonstrate denied direct filesystem, credential, metadata-service and socket access outside declared mediation. |
| Qualified outbound transport | Validate actual peer IP pinning, TLS hostname verification, redirect reauthorization, timeouts and byte limits using a controlled transport harness. The current destination module opens no sockets. |
| Live-model monitor quality | Run held-out benign and adversarial trajectories, report false restrictions, missed attacks, latency and utility, and measure adaptive evasion. Scripted findings are not detector accuracy. |
| Remote effect recovery | Integrate provider idempotency and reconciliation; test lost acknowledgements and uncertain outcomes. A local transaction cannot guarantee exactly-once remote effects. |
| Federation, witnesses and lifecycle controls | Implement cross-service authority, independent evidence custody and training/promotion controls; retain explicit partial/unimplemented status until tested. |
| Institutional utility and fairness | Conduct an approved institutional evaluation; synthetic fixtures do not measure student outcomes or equitable decisions. |

Global control changes still conservatively stale all monitor advice. SQLite
writer contention, resource exhaustion and malicious authorized monitor false
alarms remain availability concerns. A snapshot is metadata, not an explanation
of model intent. Already released bytes cannot be recalled.

The conference contribution is a testable composition of authority controls and
failure behavior, with falsifiable claims and explicit deployment obligations.
It is not a claim to have solved alignment or every current GenAI security risk.
