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
