# AIE CODE Summit SF 2026 — submission-ready proposals

Select **Brand new session** for each submission. The CFP closes **October 11, 2026** ([Sessionize](https://sessionize.com/aiecode26/)). Submit in the order below. Each session stands alone, with its own format and outcome, so accepting one does not make another redundant. Pick the closest track labels the form offers.

The **Description** is written for attendees. The **Pitch** is written for the program committee and carries the mechanism, evidence and timed outline.

---

# Proposal 1 — recommended first submission

Technical companion: [pipeline walkthrough](TECHNICAL_PIPELINE_WALKTHROUGH.md),
covering the Kafka → Spark → Iceberg path, PostgreSQL encryption/outbox,
Redis replay boundaries and independent verification used to make the security
claims concrete.

## Session Title

Approved for the Build, Used for the Deploy: Binding Coding-Agent Approvals to the Exact Action

## Description

A reviewer approves one build. Your coding agent deploys a different one, and every log line still says "approved."

In this live demo I take a single `trigger_deploy` call from a coding agent's tool dispatcher to the deployment record it changes, and break it three ways:

- **Borrowed authority.** A worker agent presents its coordinator's scope.
- **Argument swap.** The approved build is replaced before execution, including through an omitted default argument the reviewer never saw.
- **Replay with a forged approval.** A forged approval is presented on retry and collects the cached receipt of the real deploy.

Each fix happens in the dispatcher, not the prompt:

- Caller identity comes from a server-issued context, never from the model's request.
- Authority is re-derived from the root grant on every call. Each signed delegation hop must narrow its parent's scope, expire no later than its parent, and end at the agent actually making the request.
- The approval is an Ed25519 signature over the principal, tool, resource and a SHA-256 digest of canonical JSON arguments. The digest is taken after `inspect.Signature.bind()` and `apply_defaults()`, so it covers the call that will actually run.
- A retry re-verifies the approval before any cached result is returned, and it never runs the side effect twice.

Every refusal has a stable code (`REQUESTER_NOT_CHAIN_LEAF`, `APPROVAL_PAYLOAD_MISMATCH`, `APPROVAL_SIGNATURE_INVALID`), and every result is shown as the deployment record, not a log line.

You'll leave with a dispatcher pattern you can drop in front of your own agent's tools, the adversarial regression tests, and a worksheet for identity, credentials, approval and recovery. The demo runs offline with scripted requests: no model API, no Wi-Fi.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

**Why this talk, why now.** Coding agents are being handed deploy credentials, and a human approval step is usually the only brake. In most stacks, though, the approval is a boolean or a chat message. It isn't cryptographically bound to the exact call that runs. This talk shows the three concrete ways that gap is exploited, with the patch for each, in code attendees can read on the slide.

**Evidence the fixes matter.** On ten scripted hostile delegation chains, a dispatcher that trusts the presented scope blocks 0. A dispatcher that verifies each hop against its immediate delegator blocks 2. Re-deriving authority from the root on every call blocks all 10, while the legitimate two-hop chain still completes. A 300-attempt grammar fuzzer causes 0 unauthorized effects against the full dispatcher and 105 when the execution mediator is removed, which shows the attacks are real rather than malformed. All figures come from synthetic fixtures and regenerate from a clean checkout.

**The bug that makes it credible.** The most instructive failure is my own. The executor verified approvals correctly, but a cached-result shortcut in front of it returned a receipt without verifying the approval at all. The original 203-test suite passed with that bug in place. The talk shows the bypass and the ordering that fixes it: validate signature, audience, payload, role and expiry first, and only then serve from cache.

**Positioning.** The primitives aren't new: attenuated delegation is familiar from capability tokens such as macaroons and Biscuit, and signing what the approver saw is standard transaction-authorization practice. What's new is where they break when you wire them into an agent's tool dispatcher. The talk also states plainly what the dispatcher can't do: durable exactly-once effects still need an idempotency key honored by the target service.

**Outline (18 min).** 0–2 the wrong build ships; 2–7 borrowed authority and the 0/2/10 comparison; 7–12 argument swap, default-argument binding and the digest; 12–16 forged approval on replay, the cached-receipt bug and the fix; 16–18 what stays your job (caller authentication, key custody, idempotency).

### Technical implementation detail for reviewers

The live path is deliberately small enough to inspect on a slide:

```text
model request {tool, arguments}
        │
        ▼
authenticated dispatcher → issued context → strict delegation verifier
        │                                  │
        │                                  └─ root, holder, expiry, scope, depth,
        │                                     beneficiary and hop signatures
        ▼
registered tool → proposal digest → Ed25519 approval verifier
        │                                  │
        │                                  └─ principal + tool + resource +
        │                                     canonical JSON args + request id
        ▼
target-side idempotency key → effect observer → receipt/evidence ledger
```

The argument digest is computed after Python signature binding and default
application, then over canonical JSON (`sort_keys=True`, compact separators,
finite numeric values only). The approval payload contains the effective
principal, tool name, resource, bound arguments, audience, request identity and
expiry. A retry verifies the signature, audience, digest, role and expiry before
looking up a cached receipt. The in-process reference cache prevents duplicate
callbacks in one guard instance; a production target must persist the request
identity and outcome and expose reconciliation for an uncertain crash.

The supplied regression tests exercise the important ordering properties:
`tests/test_guard_adversarial.py` presents modified or foreign contexts,
default-argument swaps, forged replay approvals and exception-path labels. The
accepted deployment pattern is a server-side dispatcher that authenticates the
caller, resolves the context, owns the tool credential, and records the effect
at the target service. The decorator is not a Python sandbox and does not claim
network isolation.

**Speaker.** I'm Rachna Srivastava, an enterprise architect working independently on authorization for AI agents. I built the reference implementation and attack harness behind this session and present in a personal capacity.

## Possible Tracks

Coding Agents; Security; Agent Infrastructure.

---

# Proposal 2 — evaluation and failure analysis

## Session Title

203 Tests Passed. Our Agent Guard Still Had Bypasses.

## Description

The suite was green: 203 passing tests. Then I wrote new adversarial tests against the integration wrapper around the agent guard, and ten of them failed. A caller could swap in a modified session handle to widen its scope or drop a secret's data label. A forged approval could collect a cached receipt. A Python tuple and a list serialized to the same JSON, so one approval covered a different call. This talk shows why the original suite couldn't see any of it, and how to build agent-security evaluations that would have.

The root cause is that most agent-security tests assert on what the guard *said*. I show a tool that writes an unreviewed build and then raises "denied." An assertion on the exception passes. An **effect oracle** snapshots system state before and after each attempt, outside the code under test. It judges harm from the diff and catches the write. It's 40 lines of standard-library Python, and you can copy it today.

From there I build the protocol, with an experiment for each step:

1. **Harm is an observable effect**, defined before any attack is written.
2. **Liveness is part of the result.** Every attack is paired with legitimate work that must still succeed, because a guard that refuses everything contains everything.
3. **Positive control.** Remove the control and confirm the attacker gets through. With the execution mediator removed, a 300-attempt grammar fuzzer causes 105 unauthorized effects. With it in place, it causes 0. An adaptive bandit attacker goes from 60/60 to 0/60.
4. **Ablation.** Restore each control and re-run. Across 29 removals, harm returns in 25. The four that stay blocked are two redundant pairs, and removing each pair together brings the harm back. That's a control with a backup, not dead code.

You'll leave with the effect oracle, an ablation worksheet, and runnable positive and negative controls to point at your own agent's tools.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

**Why this talk.** Every team shipping tool-using agents will be asked "how do you know the guardrails work?" The usual evidence is a passing test count and a refusal message, and neither measures what the system did. This talk gives the eval track a security method that attendees can apply the same week, drawn from real defects rather than hypotheticals.

**What's technically distinct.** Most eval talks cover model outputs. This one covers system effects: an oracle that sits outside the mediator and diffs state; an attacker positive control that proves the attack could succeed; and single and joint ablations that separate a useless control from a redundant one. The redundant pairs are concrete. Residency and model attestation each independently stop routing sensitive data to a weaker model. Proposal-digest binding and single-use approvals each independently stop replay.

**The failure story.** Ten new wrapper tests failed against code whose 203-test suite passed. All six defects they exposed are now fixed and regression-tested:

- mutable session contexts
- cached replay skipping approval validation
- lossy JSON coercion in the argument digest
- high-impact tools registrable without an approver role
- an inherited, publicly known delegation secret
- labels attached only after a successful return

I show where the original evaluator stopped looking and what each new test observes.

**Scope, stated once.** All figures come from four synthetic policy worlds that share one kernel and attack grammar. They show the method, not field security rates. Every figure regenerates with `make evidence`, and a test fails if the checked-in evidence drifts.

### Technical evaluation contract

Each attack run starts from a serialized fixture state and records three
independent observations: model inputs, released messages, and target-register
state. The oracle does not read the guard's denial counter. A run is a
containment success only when the protected effect is absent **and** the
experiment itself completed without an unexpected error. A paired legitimate
request is run against the same policy so blanket refusal is reported as a
utility failure. Positive controls remove the selected mediator and must make
the effect reachable before a zero-result attack run is trusted.

The ablation matrix contains 27 single-control removals and two jointly removed
pairs. Results are therefore reported as `harmful configurations / total
configurations`, not as a percentage of independent controls. The checked-in
JSON under `evidence/` is regenerated by `make evidence`; the tests compare the
regenerated JSON byte-for-byte with the published artifact. This protects the
proposal numbers from manual editing while leaving external attack coverage,
real service latency and multi-process failure recovery as explicit follow-up
work.

**Outline (18 min).** 0–2 "203 passed" beside the two bypasses; 2–6 the write-then-deny tool and the effect oracle; 6–10 positive controls (0 vs 105, 0/60 vs 60/60); 10–14 ablations and the redundant pairs; 14–17 the six wrapper defects as a checklist; 17–18 the worksheet.

**Speaker.** I'm Rachna Srivastava, an enterprise architect working independently on authorization and evaluation for AI agents. I built the reference implementation, the 25-case falsification harness and the ablation experiments, and present in a personal capacity.

## Possible Tracks

Evals; Security; Agent Reliability.

---

# Proposal 3 — hands-on workshop

## Session Title

Taint Tracking for Multi-Agent Pipelines: Stop Your Summarizer from Leaking Secrets

## Description

Your summarizer agent has narrow permissions: it can only post to a channel, and it never touches the vault. But the worker that fed it did. Now a credential is on its way to #general inside a summary that calls itself "public." Tool permissions track authority. They don't track information.

In this hands-on Python workshop you'll add information-flow control to a worker → summarizer → publisher pipeline. You'll start from code that leaks a synthetic secret and implement three functions:

1. **Label the read.** Record the data class *before* the tool body runs, so a read that raises halfway through still taints the session.
2. **Propagate on handoff.** The consumer's label becomes the union of its own label and the producer's. Labels only grow, and there is no API to lower one, so a model can't declassify its own output by describing it as public.
3. **Gate the sink.** Release only if the session's label is a subset of the recipient's clearance and the purpose is one that recipient accepts. Otherwise, fail with a stable denial code (`RECIPIENT_CLASS_NOT_CLEARED`, `RECIPIENT_UNKNOWN`).

Two legitimate flows must survive: a public metrics summary, and an authorized disclosure to the security team. A fix that blocks everything fails the exercise.

Then attack your own repair: reset the session, raise mid-read, launder the secret through a second worker, and send to an undeclared recipient. You'll judge each result from the actual output sink, not the logs. Seven checks score the pipeline. The starter passes 2 of 7, and a correct repair passes all 7. Finally, delete one handoff call, watch the leak return, and restore it.

You'll leave with working code, the regression checks, reference solutions, and a worksheet for mapping data classes, handoffs and sinks in your own agent pipeline. Bring Python 3.10+ with dependencies installed beforehand. No model API, GPU or credentials needed.

## Session format

Workshop — 90 minutes.

## Special Flags

None.

## Speaker/Session Pitch

**Why this workshop.** Multi-agent coding systems pass context between workers, and permission models almost never follow it. That's how a summarizer with no secret-reading permission ends up publishing a secret. Information-flow control is the textbook answer, but few engineers have implemented it in an agent pipeline. This workshop has them implement it, break it and fix it in 90 minutes.

**What attendees do (timed).**

| Time | Activity |
|---|---|
| 0–10 | Observe the leak; name the harmful effect |
| 10–25 | Label on read, before exceptions (checkpoint 1) |
| 25–40 | Propagate labels across handoffs (checkpoint 2) |
| 40–55 | Gate the sink; reach 7/7 with both legitimate flows intact |
| 55–75 | Attack reset, exception, two-hop and unknown-recipient paths; remove and restore a handoff |
| 75–90 | Map one of their own tools |

**Technical honesty built in.** The closing segment covers what this layer can't secure: direct network access, uninstrumented logs, and missing `reads` metadata. A label check is not a network proxy, and attendees leave knowing where their own architecture needs more than a decorator.

### Workshop data model

The starter models a session label as a monotone set of data classes. A read
records its class before entering the tool body; a handoff unions the producer
label into the consumer; a release checks both recipient clearance and purpose.
There is no public operation that lowers a label. The minimum implementation
contract is therefore:

```python
session.label = session.label | {"credential"}   # before the read executes
consumer.label |= producer.label                 # at every handoff
if not session.label <= recipient.clearance:
    raise Denied("RECIPIENT_CLASS_NOT_CLEARED")
```

The real exercise uses typed records and stable denial codes rather than this
shorthand. It also tests a read that raises halfway through, a reset attempt,
an undeclared recipient, and a missing handoff. The expected result is seven
observable checks: two legitimate flows survive and five leakage paths remain
blocked.

**The kit is ready now:**

- starter code with three marked TODOs
- two recovery checkpoints for anyone who falls behind
- a reference solution and seven output checks
- a participant handout and answer guide
- a minute-by-minute instructor plan with 60- and 120-minute variants

Every step is machine-tested from a clean install. Everything runs locally, so the room doesn't share a network or API quota.

**Speaker.** I'm Rachna Srivastava, an enterprise architect working independently on authorization for AI agents. I built the guard, the disclosure fixtures and the checks this workshop uses, and present in a personal capacity.

## Possible Tracks

Multi-Agent Systems; Security; Coding Agents.

---

## Before submitting — do not paste this section into the form

These three items do more for a first-time speaker's acceptance odds than any wording change:

1. **Public repository link** in every pitch. A reviewer who can clone the demo in two minutes stops wondering whether the talk exists.
2. **A 3–5 minute screen recording** of Proposal 1's demo (an unlisted YouTube or Loom link). The committee weighs delivery heavily for unknown speakers.
3. **A workshop pilot**, even with three colleagues, to record real setup and checkpoint times. Workshop slots are scarce, and a pilot is the strongest evidence the 90-minute plan works.

Every figure above reproduces from this repository:

| Figure | Source |
|---|---|
| 0/2/10 delegation arms | `evidence/*.json` → `delegation` |
| 0/300 fuzzer violations; 105/300 without the mediator | `redteam`, `redteam_without_execution_mediator` (103 in the other three worlds; the talk quotes devtools) |
| 0/60 bandit; 60/60 positive control | `adaptive` |
| 25/29 ablations; 25/25 falsifiers | `summary` |
| 2/7 and 7/7 workshop checks | `python -m workshop.check --implementation starter` and `--implementation solution` |
| 203 original tests; 10 of 11 new adversarial tests failing (the 11th a concurrency control); six defects | Historical record in `docs/REVIEW.md` and `docs/TECHNICAL_NOTE.md` |
| 40-line oracle | `src/trustkernel/evaluation.py` |
