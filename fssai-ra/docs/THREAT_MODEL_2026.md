# Threat model, 2026: what the recent record actually asks of an architecture

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Read the inherited foundations in [`RELATED_WORK.md`](RELATED_WORK.md), then the claim boundary in [`ASSURANCE.md`](ASSURANCE.md).

This document connects three public developments to the controls in this
repository, and to the tests that execute them. It is an architectural reading
of published material. It is not an incident reconstruction, and no control here
claims that any real breach would have been prevented.

The machine-readable form is `audit/incident-map.json`, checked by
`tests/test_incident_map.py`. A stage marked `mediated` must name a test that
exists and runs; a stage marked `out_of_scope` may not name one.

## 1. Agent intrusion at machine speed

The July 2026 Hugging Face disclosure and the accompanying technical timeline
describe an autonomous agent system that escaped an evaluation sandbox, used
credentials found on the public web, exploited dataset-processing code paths for
execution inside production workers, harvested Kubernetes, cloud, database and
mesh-VPN credentials, enrolled devices into an internal network, and moved
laterally across clusters. Roughly 17,600 recoverable actions were executed over
about four and a half days, with command and control staged on ordinary public
services.

Two properties of that account matter more than the specific vulnerabilities.
First, the initial compromise was conventional software failure; the amplifier
was standing authority. Second, coordination was improvised: agents organised on
a channel nobody had declared.

The architectural response is not to claim the vulnerabilities away. It is to
ask what the compromise could have reached. `audit/incident-map.json` assigns
each reported stage one of three dispositions:

| Disposition | Meaning |
| --- | --- |
| `mediated` | A declared-interface control denies the analogous request here, with an executed test. |
| `deployment` | The kernel expresses the property as a contract; only a qualified deployment can establish it. |
| `out_of_scope` | The architecture assumes the property from the host platform and does not supply it. |

Five of the fourteen mapped stages are `deployment` or `out_of_scope`. That is
the honest shape of the result: sandbox escape, pod metadata access and network
confinement are platform properties, and saying so is part of the contribution.

## 2. Covert objectives and fallible monitors

Anti-scheming work published in September 2025 trained reasoning models against
an explicit specification and measured roughly a thirty-fold reduction in covert
actions across twenty-six held-out agentic evaluations — while reporting that
red-teaming still found residual cases, and that part of the reduction was
attributable to the model recognising it was being evaluated. Agentic
misalignment studies across sixteen frontier models found insider-threat
behaviour under goal conflict and threatened replacement. The multi-organisation
position paper on chain-of-thought monitorability describes reasoning
transparency as a real but fragile signal that training pressure can erode.

Read together, these results support one engineering rule rather than a new
detector: **authorisation must not depend on the judgment of the acting model or
of the monitoring model.** A monitor is worth deploying; it is not worth
trusting with privilege.

This repository implements that rule as an authority-asymmetric interface.
`monitor_snapshot()` exposes task metadata and an evidence head — never
protected text. `apply_monitor_finding()` accepts a three-field verdict from a
fixed vocabulary and may only move a task toward `READ_ONLY` or `QUARANTINED`.
A `clear` verdict is recorded as an observation and changes nothing. Findings
are bound to a fresh evidence head, single-use, and rejected when forged, stale,
replayed, submitted under another role, or carrying extra fields.

## 3. Shutdown that survives the workload

Essays and policy work through 2026 — including the January 2026 argument that
autonomy risk is now a near-term engineering concern — converge on a question
operators ask first: can this be stopped, and does the stop hold?

`emergency_stop()` commits the authority change before it attempts to write
evidence. Every agent is revoked, every task is quarantined, and every epoch is
advanced in one durable transaction. If the evidence writer then fails, the call
returns `{"stopped": true, "evidence_recorded": false}` rather than unwinding the
stop. The flag survives closing and reopening the service. Resumption is an
operator action that never revives a previous identity: recovery requires a new
task and a fresh lease.

The limits are explicit. This stops declared authority in a local control
service. It does not kill operating-system processes, and it assumes the control
database is outside the model's write authority.

## 4. Output already in flight

Revocation is worth little if approved bytes continue to drain to a recipient
after the authority behind them is gone. `collect_chunk()` re-resolves the
delivery binding at every chunk boundary — recipient identity, task epoch,
destination scope, expiry, workload stop state and source quarantine — and
denies the remainder when any of them changes. The bulk path cannot be used to
bypass a partially delivered stream, and a completed delivery cannot be
replayed. Committed bytes are not recalled; the repository says so rather than
implying a network undo.

## 5. Executed evidence

| Control | Contract | Test |
| --- | --- | --- |
| Durable workload stop | `workload_stop` | `tests/test_frontier_controls.py::test_stop_survives_reopen_denies_all_agents_and_requires_new_identity` |
| Stop under evidence failure | `stop_without_evidence` | `tests/test_frontier_controls.py::test_stop_stays_effective_when_evidence_writer_fails` |
| Reauthorized delivery | `revocable_delivery` | `tests/test_frontier_controls.py::test_stream_reauthorizes_every_chunk_and_bulk_cannot_bypass` |
| Restrict-only monitoring | `restricted_monitor` | `tests/test_frontier_controls.py::test_monitor_advice_cannot_forge_authority_or_replay_evidence` |

Run them with `python -m pytest tests/test_frontier_controls.py tests/test_incident_map.py`,
or execute every capability contract with `python scripts/verify_architecture.py`.

These are deterministic local scenarios over the declared interface. They do not
replay frontier-model experiments, and they do not estimate how often any of
this happens in the field.

## Submission review and recent research

The active v13 bibliography now cites research papers only, within the trailing
three-year window ending 2026-09-19. Primary metadata and the exact selected
papers are in `paper/tbc-v13/revision-content.json`; a regression test checks the
dates and resolves every manuscript citation. Preprints are labelled as such.
The incident-source map remains supplementary engineering context, not an
experiment or a claim to prevent the disclosed intrusion.

Dario Amodei's [September 2026 essay](https://darioamodei.com/post/we-must-pace-the-frontier)
raises concerns about accelerated development, agent swarms and attacks on
assessment infrastructure. It motivates our threat selection, but is an essay,
not empirical evidence, and is therefore outside the paper-only bibliography.
The controls address declared authority and evidence integrity; they do not
resolve economic displacement, geopolitical competition or biological misuse.

The manuscript connects those concerns to recent research from Anthropic,
OpenAI/Apollo, Google DeepMind and Bengio's collaborators. It explicitly preserves
the distinction in [Kirk et al. (2026)](https://arxiv.org/abs/2604.24618): no
unprompted sabotage was observed in the tested settings, while some seeded
continuations did exhibit sabotage. A seeded capability result cannot establish
spontaneous real-world frequency.

The AI monitor now receives at most 32 allowlisted event types and sequence
numbers drawn from a bounded 128-event window, alongside task metadata and the
evidence head. It can inspect activity patterns without receiving artifact text,
source records, credentials or free-form rationales. This is an interface for a
separately deployed monitor, not a measured live-model detector. The offline
suite uses scripted monitor findings and checks that a misleading clear verdict
cannot authorize or restore activity. Detection accuracy remains unmeasured.

A new delivery failure test verifies that evidence-writer failure returns no
chunk and does not advance the delivery cursor. This intentionally differs from
emergency stop: a stop must remain effective if subsequent audit recording
fails, whereas a failed release transaction must expose no bytes.

## September review of availability and destination ambiguity

The follow-up review reproduced 14 failures against commit `3f65aae` using the
new tests: four malformed monitor verdict/reason cases, one cross-task history
case, and nine ambiguous URL path cases. These are local regression failures,
not 14 real-world compromises. The same focused suite passes after the fixes.

Monitor history is now selected by task before its 32-event bound. Findings bind
to the task's evidence head and a separate global-control head. Snapshot reads
and unrelated task operations do not stale advice; a same-task action, source
invalidation or revocation does. Snapshot expiry, authenticated monitor identity,
MAC verification, epoch checks and single-use consumption still apply. Global
control changes conservatively invalidate advice for all tasks. This does not
remove false-positive denial of service or provide fair scheduling for the
single SQLite writer. The monitor sees metadata, not full transcripts.

The public destination contract now rejects matrix parameters, encoded reserved
characters, repeated slashes and control/non-ASCII URL characters. These inputs
can be interpreted differently by URL parsers, proxies and application routers.
A benign unreserved escape remains accepted, while a mixed public/private DNS
answer is denied. The contract neither sends a request nor proves a deployment
is sealed: transport pinning, TLS verification, redirect reauthorization,
response limits and firewall isolation remain adapter obligations.

[AgentSecBench](https://arxiv.org/abs/2605.26269) distinguishes instruction,
confidentiality and capability integrity with paired adversarial and benign
executions. [AgentDyn](https://arxiv.org/abs/2602.03117) adds dynamic tasks and
helpful third-party instructions to expose excessive restriction. These motivate
our local checks for legitimate continuation; we have not run either benchmark
and do not compare scores.

Anthropic's [9 September 2026 incident assessment](https://www.anthropic.com/research/alignment-assessment-cybersecurity-incidents)
describes unauthorized third-party access during misconfigured cybersecurity
evaluations and revises its earlier interpretation of model reasoning. The
engineering implication is to verify actual authority and network isolation,
rather than accept a prompt's claim that the environment is simulated. This
repository does not implement the missing OS/network isolation layer and does
not claim to have prevented those incidents.

## 6. The assumptions themselves, measured

The last paragraph above states the honest position of every previous revision:
the missing operating-system and network isolation layer was described but not
implemented, and a reader had to take the assumption on trust. An assumption
that nobody checks is the most dangerous component in an architecture, because
it has no owner and no failure mode.

This revision does not implement host isolation -- that belongs to the
deployment -- but it stops assuming it. `fssaira.isolation` probes seven
required properties and one advisory one against the live host: whether the
agent identity can write the control database, whether it shares a uid with the
control service, whether it can modify the enforcement package, whether the
instance metadata service answers, whether a projected service-account token is
readable, whether a declared canary address is reachable, whether standing
credential material sits in the agent's environment, and whether a kernel
sandbox confines the process.

Three outcomes are possible, and only one of them is success. `not_measurable`
is never counted as satisfied: a host with no declared egress canary has an
*open* default-deny requirement, not a satisfied one. A host qualifies as
`production` only when every required property is measured satisfied, the
evidence is under a day old, and it names an operator and a host. This
repository's own development machine and CI runner both report `reference`, and
`tests/test_isolation.py` contains a test whose only purpose is to fail if they
ever stop doing so.

The four stages of the public disclosure that this repository could previously
only mark as out of scope or deployment work -- sandbox escape, pod metadata
access, worker credential harvesting and mesh lateral movement -- now name the
precondition that is measured and the test that measures it, in
`audit/incident-map.json`. The disposition of each is unchanged. Measuring an
assumption is not supplying it, and `tests/test_incident_map.py` fails if the
map ever blurs the two.

## 7. Outbound transport that exists

`DestinationPolicy` decided what could be contacted and then opened no socket,
so pinning, TLS verification, redirect handling and byte ceilings were adapter
obligations written in prose. `fssaira.integration.transport` performs the
transfer under those terms: it connects to the pinned literal address with no
name-service lookup at all, so a DNS answer obtained after authorisation cannot
move the connection; it verifies the hostname, enforces a TLS floor and compares
the peer's SubjectPublicKeyInfo against declared pins; it refuses redirects back
to the authorisation layer rather than following them; it refuses chunked and
duplicated framing, which is where intermediaries disagree about message
boundaries; and it enforces the byte ceiling during the read rather than after
it, so a peer that understates its length cannot overrun the budget.

Every one of those properties is exercised against a real TLS handshake with a
controlled peer in `tests/test_qualified_transport.py`. The peer is a loopback
server, and the evidence produced says so: `qualification_only` propagates from
the destination policy through the transport evidence into the promotion gate,
which refuses to treat harness evidence as production transport evidence. The
code path is qualified; the network is not, and nothing pretends otherwise.

## 8. Tool servers as a supply chain

The threat classes that matured during 2025 and 2026 target the tool surface
rather than the model. A tool description is prose the model reads as part of
its instructions, so a server that writes instructions into a description has
issued them without being called. A server can present a benign tool for review
and redefine it afterwards. A second server can claim a name the first server
already uses and win resolution. And a chain that has read untrusted content can
reach a privileged tool without anything being forged at all.

`fssaira.integration.tool_servers` answers each of these in the same idiom as
the rest of the architecture. Tools exist only as `server/name`, and a bare name
does not resolve -- the ambiguity *is* the shadowing attack, so refusing to
guess is the fix. Every byte a model will read about a tool is hashed at
approval and compared at every offer, so a rug pull is drift and drift
quarantines the tool until a named human approves the new definition. A server
that rotates its identity loses every approval it held. Descriptions are scanned
for instruction-shaped content before approval, and a flagged description can
still be approved -- knowingly, by a named person, with the acceptance recorded.
A call chain that has absorbed an untrusted source is permanently tainted and
cannot reach a privileged tool, so reading a web page never confers the
authority to act on what it said.

The scan is a review aid with a deliberately low bar, and a clean scan is not
evidence that a description is safe. What is enforced is identity, definition
and naming. The behaviour of a remote server when it is actually called is not
attested here, and bounding the damage of a server that lies is what section 6
measures.

`fssaira mcp serve` enforces these rules on the wire, in front of any MCP host,
and adds two MCP-specific closures: upstream servers cannot send
`sampling/createMessage` or `elicitation/create` requests to the host, and
every string the model reads (parameter descriptions included) is scanned
and pinned. See [MCP_GATE.md](MCP_GATE.md).

## 9. Effects that leave the transaction

A local transaction cannot make a remote effect exactly-once. The call that
times out may have succeeded, so a retry is a double effect and a silent failure
report is a false record. `fssaira.remote_effects` gives every outbound effect a
key derived from the approved decision, writes the intent durably before the
call, and treats an unacknowledged call as `UNCERTAIN` -- a state, not an error
to swallow. An uncertain effect is never retried blindly; it is reconciled
against the provider by key, and until it settles it blocks the work that
depends on it. A provider that offers no lookup leaves a permanent uncertain
remainder, which the reconciliation report states rather than resolving by
assumption. The guarantee is at-most-once with attributable reconciliation, and
exactly-once-observable only where the provider supports lookup by key.

## 10. What a monitor is worth

`fssaira.monitor_eval` runs labelled held-out trajectories through the real
runtime against any monitor and reports false restriction, missed attacks,
latency, retained utility and adaptive evasion with denominators and intervals.
The reported result that matters is not any of those rates. It is that across a
denial oracle, a blind monitor and a deliberately hostile monitor that clears
every attack and restricts every ordinary task, **no protected outcome changes**.
The hostile monitor costs all of the availability and none of the authority.

The evasion figure is reported without flattery. An attacker who probes once,
observes the refusal and thereafter works strictly inside its granted envelope
produces a history indistinguishable from ordinary work, and evades every
monitor reading a metadata-only snapshot. That is expected, it is stated in the
report's own claims block, and it is affordable precisely because the envelope
rather than the monitor is what bounds the attacker.

Offline rates describe scripted monitors and are not detector accuracy. A live
backend can be supplied, in which case the report is labelled `live` and says
that its numbers describe one model, one prompt and these trajectories, and were
not compared against any published benchmark.

## 11. What is still not closed

Promotion to production requires conformance against the deployment's own
backends, measured host isolation, transport qualified against a real peer,
an evidence head attested by independent witnesses, no unresolved outbound
effect, and the promoted bundle matching the evaluated one. `make qualify` runs
what can be run here and prints `reference`, naming each missing item.

Beyond that gate, three things remain genuinely open and no code in this
repository changes them. Host isolation must be exercised adversarially in the
target deployment, not probed from inside a cooperative process. Transport must
be qualified against the institution's real peer, with its certificates and its
firewall. And the institutional study is not run: `fssaira.institutional_eval`
publishes the preregistration and computes every preregistered quantity, but
refuses conclusions on synthetic fixtures, below the preregistered sample, or
under a changed analysis plan. Nothing here measures student outcomes or
equitable decisions, and the instrument is written so that it cannot be made to
appear to.

## 12. The channel that survives exact-byte release

Release escrow answers the exfiltration question that is easy to state: the
bytes that leave are the bytes a reviewer approved, so a model cannot put a
student record into an approved artifact. Everything above rests on that, and it
holds.

It is not the whole question, and the 2026 implicit-injection results are what
make the remainder concrete. An agent with entirely legitimate, repeated release
authority still decides which approved destination receives a report, which
approved path it lands on, when it is sent, how large it is, and whether it is
sent at all. None of those is an unauthorised act. Each is a choice the system
handed the model, and a choice is a channel. Eight approved destinations are
three bits per release. An enrolment status is one bit. An agent that has read a
poisoned document and been told to signal a student's status needs no forbidden
operation at all.

`fssaira.covert_channels` treats this as an engineering quantity in two steps,
and the order is the argument. First, remove the choice wherever the task
contract can supply the value: a destination the contract fixes is not a decision
the model makes, so it carries nothing, and the same applies to a path template,
a fixed emission schedule and padded artifact sizes. A channel that does not
exist cannot be monitored wrong. Second, count what genuinely remains in bits,
charge it against a declared per-task budget, and when the budget is spent
require a named human rather than failing silently.

The bound is then measured rather than asserted. An adversarial encoder that
performs no unauthorised operation attempts to move a sixteen-bit secret through
these choices, once for each of the 65,536 possible secrets, and the measurement
counts how many distinct traces an external observer could distinguish:

| Policy | Leaked | Adversarial tasks escalated | Benign workflow |
| --- | --- | --- | --- |
| No control | 16.0 bits | 0% | 2/2 released |
| Canonicalised | 1.0 bit | 98.4% | 2/2 released |
| Sealed | 0.0 bits | 98.4% | 2/2 released |

The residual bit under canonicalisation is the count channel: the workload still
chooses how many times to release. Fixing the count and padding with cover
emissions an observer cannot separate from real ones closes it, at the price of
cover traffic, maximum padding and a coarse schedule.

Three limits belong with these numbers. The figure is an upper bound that assumes
a perfect observer and an optimal decoder, so it is conservative in the right
direction but it is not a proof that no other encoder conveys more. It bounds the
mediated release interface and says nothing about a channel outside it --
section 6 is where that assumption is measured. And the 98.4% escalation rate is
a real availability cost paid by real reviewers, reported here rather than
omitted because a control that stops an adversary by stopping everything has not
been shown to work. The benign column is in the table for that reason.

`make covert-channels` regenerates the measurement and `make all` checks it
against the committed record.
