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

## Second review: the assumptions underneath the controls

The gap table above named six items. Five are now implemented, tested and bound
to executed capability contracts; the sixth is an instrument for a study that has
not been run. What follows states, for each, what changed and what did not.

### Process and network isolation

`fssaira.isolation` probes eight declared properties against the live host and
qualifies it. `not_measurable` is a third outcome and is never counted as
success. Production qualification requires every required property measured
satisfied, evidence under a day old, and a named operator and host.
`tests/test_isolation.py` contains a test whose only purpose is to fail if this
repository's own machine ever reports `production`.

This does not implement isolation. The probe runs inside a cooperative process,
so it establishes the absence of a path *from this process*, not the absence of
every path. The acceptance requirement in the earlier table -- an adversarial
process in the intended deployment -- stands unchanged.

### Qualified outbound transport

`fssaira.integration.transport` opens the socket the destination contract always
assumed. It connects to the pinned literal address with no name-service lookup
(not even the no-op lookup `socket.create_connection` performs on a literal),
verifies the hostname, enforces a TLS floor, compares the peer's
SubjectPublicKeyInfo against declared pins, refuses redirects back to the
authorisation layer, refuses chunked and duplicated framing, and enforces the
byte ceiling during the read.

Thirty-three tests exercise this against a real handshake with a controlled peer.
The peer is a loopback server; `qualification_only` propagates from the policy
through the evidence into the promotion gate, which refuses it as production
transport evidence. The acceptance requirement -- the institution's real peer,
certificates and firewall -- stands unchanged.

### Live-model monitor quality

`fssaira.monitor_eval` runs labelled held-out trajectories through the real
runtime and reports false restriction, missed attacks, latency, retained utility
and adaptive evasion with denominators and Wilson intervals. It accepts a live
backend, and labels the report `live` when one is used.

The load-bearing result is that across a denial oracle, a blind monitor and a
hostile monitor that inverts every verdict, no protected outcome changes. The
hostile monitor costs all of the availability and none of the authority. The
adaptive family -- an attacker that probes once and thereafter stays inside its
envelope -- evades every monitor reading a metadata-only snapshot, and the report
says so in its own claims block rather than burying it.

### A defect the harness found

Building that harness surfaced a real defect in the runtime. Refusals raised
before the request savepoint exists -- a revoked agent, a stopped workload, an
assurance failure -- returned `DENIED` and wrote no evidence at all. Five
requests issued after an emergency stop left the evidence chain unchanged, so an
operator reviewing it could not see that something was still trying.

Blocked attempts are now recorded outside the failed transaction, bound to the
known identity and task, with the control service's own stable reason code. A
failure to record one never restores authority; the Guardian's contraction is
not rolled back by the recording; and an unknown token records nothing, so
anonymous traffic cannot be used to grow the evidence chain. Three regressions
cover this, and the event is visible in the monitor snapshot.

### Remote effect recovery

`fssaira.remote_effects` derives an idempotency key from the approved decision,
writes intent durably before the call, and treats an unacknowledged call as
`UNCERTAIN`. An uncertain effect is never retried blindly, blocks dependent work
until it settles, and is reconciled against the provider by key. A crash between
intent and acknowledgement leaves a record that says "this may have happened",
and a restart reconciles rather than resends. A provider that reports two
different results for one key raises an integrity violation.

The guarantee is at-most-once with attributable reconciliation, and
exactly-once-observable only where the provider supports lookup by key. A
provider without lookup leaves a permanent uncertain remainder, stated rather
than resolved by assumption.

### Federation, witnesses and lifecycle controls

`fssaira.federation` implements audience-bound, single-use, depth-limited grants
whose scope is intersected with the receiving service's ceiling and never merged;
k-of-n witness attestation with explicit fork detection, because a chain held by
one custodian is as trustworthy as that custodian; and a promotion gate requiring
conformance, isolation, transport, attestation, effect settlement and bundle
identity, fresh and together, that names each missing item instead of returning a
verdict. `make qualify` runs it here and prints `reference`.

### Institutional utility and fairness

This is the one gap that code cannot close, and the module is written so that it
cannot appear to. `fssaira.institutional_eval` publishes a full preregistration
and computes every preregistered quantity, then refuses conclusions on synthetic
data, below the preregistered sample, on subgroups under the cell minimum, or
under a changed analysis plan. Selection rate, equal-opportunity gap and reviewer
overturn are reported together, so a single favourable measure is not a result.
No study has been run and none is claimed.

### Current state

1,375 regression cases pass with none skipped. Thirty-one capability contracts
execute against named tests. Thirty-five manuscript anchors are bound to test
locators and recorded evidence. The architecture register is unchanged at 109
controls with its partial, deployment-dependent and unimplemented statuses
intact. This review closed the gaps it could close and made the remaining ones
measurable; it did not turn a local reference into a production deployment, and
the promotion gate in this repository refuses to say otherwise.
