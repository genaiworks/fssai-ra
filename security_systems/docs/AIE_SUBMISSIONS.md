# AIE CODE Summit SF 2026 — submission-ready proposals

Event: November 10–12, 2026, Hilton Union Square, San Francisco. Select **Brand new session** for each submission. The CFP closes **October 11, 2026, 11:59 PM PDT** ([Sessionize](https://sessionize.com/aiecode26/), checked September 24, 2026). Acceptances go out in waves. Wave 1 (September 15) has passed, and wave 2 is decided at the close, so submit as early as possible: slots taken in a wave are gone. The organizers report a historical acceptance rate of 5–15% and ask for engaging, specific titles focused on coding agents and developer tools.

Submit in the order below. Each session stands alone, with its own format and outcome, so accepting one does not make another redundant. Pick the closest track labels the form offers.

The **Description** is written for attendees. The **Pitch** is written for the program committee and carries the mechanism, evidence, positioning and timed outline. Every field below is plain text that can be pasted as is.

The three sessions share one thesis, and each pitch states it: **agent security is a property of what the system did, not of what the model or the guard said.** The deploy talk applies it to approvals, the evals talk to testing, and the workshop to data flow.

---

# Proposal 1 — recommended first submission

## Session Title

Approved for the Build, Used for the Deploy: Binding Coding-Agent Approvals to the Exact Action

## Description

A reviewer approves one build. Your coding agent deploys a different one, and every log line still says "approved."

Last year a coding agent wiped a production database during a code freeze it had been told, in plain words, to respect. The lesson the industry took was "require approval." This talk is about what happens next, when the approval exists but isn't bound to the action that runs.

Live, offline, I take one `trigger_deploy` call from a coding agent's tool dispatcher to the deployment record it changes, and break it three ways:

- **Borrowed authority.** A worker agent presents its coordinator's scope.
- **Argument swap.** The approved build is replaced before execution, including through a default argument the reviewer never saw.
- **Replay with a forged approval.** A forged approval on retry collects the cached receipt of the real deploy.

Each fix lives in the dispatcher, the same place your MCP server's `tools/call` handler already sits:

- Caller identity comes from a server-issued context, never from the model's request.
- Authority is re-derived from the root grant on every call; each delegation hop must narrow scope and expiry and end at the agent actually asking.
- The approval is an Ed25519 signature over principal, tool, resource and a SHA-256 digest of the canonical arguments, taken after `inspect.Signature.bind()` and `apply_defaults()`, so it covers the call that will actually run.
- A retry re-verifies the approval before any cached result is returned.

"What did the human approve?" gets a byte-exact answer. You'll leave with the dispatcher pattern, the adversarial regression tests, and a worksheet for identity, credentials, approval and recovery.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

**Why this talk, why now.** Coding agents hold deploy credentials, and a human approval step is usually the only brake. After the widely reported July 2025 incident where a Replit agent deleted a production database during a code freeze, the fix Replit announced included approval on destructive commands. In most stacks that approval is a boolean or a chat message. It isn't cryptographically bound to the exact call that runs, so it can be borrowed, swapped or replayed. This talk shows all three with the patch for each, in code attendees can read on the slide.

**Evidence the fixes matter.** On ten scripted hostile delegation chains, a dispatcher that trusts the presented scope blocks 0. One that verifies each hop against its immediate delegator, which is what a careful team would build, blocks 2. Re-deriving authority from the root on every call blocks all 10, and the legitimate two-hop chain still completes. A 300-attempt grammar fuzzer causes 0 unauthorized effects against the full dispatcher and 105 when the execution mediator is removed, so the attacks are real rather than malformed. A 36-case grid of legitimate calls, including a reviewed deploy retried without a second effect, completes 36 of 36. A guarded read costs a median of 11 µs locally, or 47 µs at delegation depth three: noise beside a model call.

**The bug that makes it credible.** The most instructive failure is my own. The executor verified approvals correctly, but a cached-result shortcut in front of it returned a receipt without verifying the approval at all. The original 203-test suite passed with that bug in place. The talk shows the bypass and the ordering that fixes it: validate signature, audience, payload, role and expiry first, and only then serve from cache.

**Positioning.** The primitives aren't new. Attenuated delegation is familiar from capability tokens such as macaroons and Biscuit, and signing what the approver saw is standard transaction-authorization practice. What's new is where they break inside an agent's tool dispatcher: default arguments the reviewer never saw, JSON coercion that makes two calls hash alike, and caches that answer before the verifier runs. The talk also says plainly what the dispatcher can't do: durable exactly-once effects still need an idempotency key honored by the target service.

**What's on the slides.** Model request (tool name plus JSON arguments) → the dispatcher resolves the authenticated caller to an issued context → the delegation chain is re-verified from the root (holder, expiry, scope, depth, hop signatures) → arguments are bound with Python defaults and canonicalized (sorted keys, compact separators, finite numbers only; a tuple is not silently a list) → the Ed25519 approval is checked against principal, tool, resource, request identity, audience, expiry and argument digest → only then does the registered callback receive its credential. An independent observer reads the deployment register before and after. Every refusal carries a stable code (`REQUESTER_NOT_CHAIN_LEAF`, `APPROVAL_PAYLOAD_MISMATCH`, `APPROVAL_SIGNATURE_INVALID`). The demo runs offline with scripted requests, so there's no model API or Wi-Fi to fail on stage.

**Outline (18 min).** 0–2 the wrong build ships; 2–7 borrowed authority and the 0/2/10 comparison; 7–12 argument swap, default-argument binding and the digest; 12–16 forged approval on replay, the cached-receipt bug and the fix; 16–18 what stays your job (caller authentication, key custody, idempotency).

**Speaker.** I'm Rachna Srivastava, an enterprise architect working independently on authorization for AI agents. I built the reference implementation and attack harness behind this session, published the bypasses I found in my own code, and present in a personal capacity.

**Code** (public, runs offline, hosted CI green on Python 3.10 and 3.14; the README has a five-minute reviewer path with one command per session): https://github.com/genaiworks/fssai-ra/tree/main/security_systems

## Possible Tracks

Coding Agents; Security; Agent Infrastructure.

---

# Proposal 2 — evaluation and failure analysis

## Session Title

203 Tests Passed. Our Agent Guard Still Had Bypasses.

## Description

The suite was green: 203 passing tests. Then I wrote new adversarial tests against the integration wrapper around my agent guard, and ten of them failed. A caller could swap in a modified session handle to widen its scope or drop a secret's data label. A forged approval could collect a cached receipt. A Python tuple and a list serialized to the same JSON, so one approval covered a different call. This talk shows why the original suite couldn't see any of it, and how to build agent-security evals that would have.

The root cause: most agent-security tests assert on what the guard *said*. I show a tool that writes an unreviewed build and then raises "denied." An assertion on the exception passes. An **effect oracle** snapshots system state before and after each attempt, outside the code under test. It judges harm from the diff and catches the write. It's 40 lines of standard-library Python, and you can copy it today.

From there I build the protocol, one experiment per step:

1. **Harm is an observable effect**, defined before any attack is written.
2. **Liveness is part of the result.** Every attack is paired with legitimate work that must still succeed, because a guard that refuses everything contains everything.
3. **Positive control.** Remove the control and confirm the attacker gets through. A 300-attempt grammar fuzzer causes 105 unauthorized effects with the execution mediator removed and 0 with it in place. An adaptive bandit attacker goes from 60/60 to 0/60.
4. **Ablation is mutation testing for guardrails.** Delete each control and re-run. If nothing fails, either the control is dead or your evals are blind. Across 29 removals, harm returns in 25. The four that stay blocked are two redundant pairs, and removing each pair together brings the harm back: a control with a backup, not dead code.

You'll leave with the effect oracle, an ablation worksheet, and runnable positive and negative controls to point at your own agent's tools.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

**Why this talk.** Every team shipping tool-using agents will be asked "how do you know the guardrails work?" The usual evidence is a passing test count and a refusal message, and neither measures what the system did. Agents' own reports are no better: an agent can tell you it respected a freeze while the database is gone. This talk gives the evals track a security method attendees can apply the same week, drawn from real defects rather than hypotheticals.

**What's technically distinct.** Most eval talks score model outputs. This one scores system effects, with the three instruments experimental science uses and agent evals mostly skip:

- **An oracle outside the mediator** that diffs state rather than reading denials.
- **A positive control** that proves the attack could have succeeded.
- **Single and joint ablations** that separate a useless control from a redundant one.

The redundant pairs are concrete. Residency and model attestation each independently stop routing sensitive data to a weaker model. Proposal-digest binding and single-use approvals each independently stop replay. A single-removal study would have told us to delete all four.

**The failure story.** Ten new wrapper tests failed against code whose 203-test suite passed. All six defects they exposed are now fixed and regression-tested:

- mutable session contexts
- cached replay skipping approval validation
- lossy JSON coercion in the argument digest
- high-impact tools registrable without an approver role
- an inherited, publicly known delegation secret
- labels attached only after a successful return

I show where the original evaluator stopped looking and what each new test observes.

**The evaluation contract.** Each attack starts from a serialized fixture and records three independent observations: model inputs, released messages and the target register. The oracle never reads the guard's denial counter. A run counts as contained only when the protected effect is absent *and* the experiment completed without an unexpected error, so a crashed attack can't pass. The ablation matrix is 27 single removals plus two joint pairs, reported as harmful configurations out of 29 rather than as a percentage of controls. Liveness is measured too: 36 of 36 authored legitimate cases complete.

**Scope, stated once.** All figures come from four synthetic policy worlds that share one kernel and attack grammar. They show the method, not field security rates. Every figure regenerates with `make evidence`, and a test fails if the checked-in evidence drifts by a single byte.

**Outline (18 min).** 0–2 "203 passed" beside the two bypasses; 2–6 the write-then-deny tool and the effect oracle; 6–10 positive controls (0 vs 105, 0/60 vs 60/60); 10–14 ablations, with the room voting on which controls to delete before the joint removal; 14–17 the six wrapper defects as a checklist; 17–18 the worksheet.

**Speaker.** I'm Rachna Srivastava, an enterprise architect working independently on authorization and evaluation for AI agents. I built the reference implementation, the 25-case falsification harness and the ablation experiments, and present in a personal capacity.

**Code** (public, runs offline, hosted CI green on Python 3.10 and 3.14; the README has a five-minute reviewer path with one command per session): https://github.com/genaiworks/fssai-ra/tree/main/security_systems

## Possible Tracks

Evals; Security; Agent Reliability.

---

# Proposal 3 — hands-on workshop

## Session Title

Taint Tracking Against the Lethal Trifecta: Stop Your Summarizer from Leaking Secrets

## Description

Your summarizer agent has narrow permissions: it can only post to a channel, and it never touches the vault. But the worker that fed it did. Now a credential is on its way to #general inside a summary that calls itself "public." Tool permissions track authority. They don't track information.

This is the lethal trifecta (private data, untrusted content, a way out) spread across agents, and it's the shape of the 2025 GitHub MCP exploit, where an agent read a private repository and published it in a public pull request. You can't reliably detect the injection. You can make the sink know what the data touched.

In this hands-on Python workshop you'll add information-flow control to a worker → summarizer → publisher pipeline. Starting from code that leaks a synthetic secret, you'll implement three functions:

1. **Label the read.** Record the data class *before* the tool body runs, so a read that raises halfway through still taints the session.
2. **Propagate on handoff.** The consumer's label becomes the union of its own and the producer's. Labels only grow, so a model can't declassify its output by calling it public.
3. **Gate the sink.** Release only if the label fits the recipient's clearance and the purpose is one that recipient accepts; otherwise fail with a stable code (`RECIPIENT_CLASS_NOT_CLEARED`, `RECIPIENT_UNKNOWN`).

Two legitimate flows must survive: a public metrics summary, and an authorized disclosure to the security team. A fix that blocks everything fails.

Then attack your own repair: reset the session, raise mid-read, launder the secret through a second worker, send to an undeclared recipient. You judge each result from the actual output sink, not the logs. Seven checks score the pipeline: the starter passes 2, a correct repair passes 7. Finally, delete one handoff call, watch the leak return, and restore it.

You'll leave with working code, regression checks, reference solutions, and a worksheet for mapping data classes, handoffs and sinks in your own pipeline. Bring Python 3.10+ with dependencies installed beforehand. No model API, GPU or credentials needed.

## Session format

Workshop — 90 minutes.

## Special Flags

None.

## Speaker/Session Pitch

**Why this workshop.** Multi-agent coding systems pass context between workers, and permission models almost never follow it. That's how a summarizer with no secret-reading permission ends up publishing a secret, and it's the architecture behind Invariant Labs' May 2025 GitHub MCP disclosure, which they described as an architectural issue rather than a code bug. Simon Willison's "lethal trifecta" gave the community the vocabulary. This workshop gives attendees the mechanism, which they implement, break and fix in 90 minutes.

**Positioning.** Information-flow control for agents is arriving in research and frameworks: DeepMind's CaMeL tracks provenance through a custom interpreter, and Microsoft's FIDES propagates confidentiality labels through Agent Framework tool calls. This workshop doesn't compete with them. Attendees build the minimum version by hand, across agent handoffs, in plain Python, so they understand what those systems enforce and where a hand-rolled or framework version breaks: reads that raise, session resets, two-hop laundering and undeclared recipients. Then they test it by effect rather than by log. Anyone who adopts a framework afterwards knows which of those four cases to test first.

**What attendees do (timed).**

| Time | Activity |
|---|---|
| 0–10 | Observe the leak; name the harmful effect |
| 10–25 | Label on read, before exceptions (checkpoint 1) |
| 25–40 | Propagate labels across handoffs (checkpoint 2) |
| 40–55 | Gate the sink; reach 7/7 with both legitimate flows intact |
| 55–75 | Attack reset, exception, two-hop and unknown-recipient paths; remove and restore a handoff |
| 75–90 | Map one of their own tools |

**The core in three lines.** A session label is a monotone set of data classes:

```python
session.label |= {"credential"}          # before the read executes
consumer.label |= producer.label         # at every handoff
if not session.label <= recipient.clearance: raise Denied("RECIPIENT_CLASS_NOT_CLEARED")
```

The exercise itself uses typed records, purpose checks and stable denial codes rather than this shorthand. It scores seven observable checks: two legitimate flows survive and five leakage paths stay blocked.

**Technical honesty built in.** The closing segment covers what this layer can't secure: direct network access, uninstrumented logs, and missing `reads` metadata. A label check is not a network proxy, and attendees leave knowing where their own architecture needs more than a decorator.

**The kit is ready now:**

- starter code with three marked TODOs
- two recovery checkpoints for anyone who falls behind
- a reference solution and seven output checks
- a participant handout and answer guide
- a minute-by-minute instructor plan with 60- and 120-minute variants

Every step is machine-tested from a clean install. Everything runs locally, so the room doesn't share a network or API quota.

**Speaker.** I'm Rachna Srivastava, an enterprise architect working independently on authorization for AI agents. I built the guard, the disclosure fixtures and the checks this workshop uses, and present in a personal capacity.

**Code** (public, runs offline, hosted CI green on Python 3.10 and 3.14; the README has a five-minute reviewer path with one command per session): https://github.com/genaiworks/fssai-ra/tree/main/security_systems

## Possible Tracks

Multi-Agent Systems; Security; Coding Agents.

---

## Before submitting — do not paste this section into the form

These items do more for a first-time speaker's acceptance odds than any wording change:

1. **A repository reviewers can use in two minutes.** Each pitch already links https://github.com/genaiworks/fssai-ra/tree/main/security_systems, whose README opens with a CI badge and a five-minute reviewer path. Better still is a dedicated repository: create an empty public one (for example `genaiworks/trustkernel`, with no README or licence), run `bash security_systems/scripts/publish_standalone.sh https://github.com/genaiworks/trustkernel.git`, confirm its Actions tab is green, then replace the link in the three **Code** lines.
2. **A 4-minute screen recording** in your own voice (an unlisted YouTube or Loom link), added to each **Code** line. `docs/RECORDING_SCRIPT.md` is the script, and `bash scripts/record_demo.sh` drives the terminal one beat per Enter. Budget 30 minutes including one retake.
3. **A workshop pilot** with two to four people, run with `workshop/PILOT.md`. It ends with the one factual sentence you may then add to Proposal 3. Until then, don't claim the timing has been validated with a live audience.
4. **A fourth submission: Proposal 2 as an Online Talk** (prerecorded, 5–55 minutes). The CFP says online acceptances get a free ticket and priority as a backup speaker, which is a second route onto the stage.

If Sessionize rejects a pitch for length, trim in this order: Proposal 1's "What's on the slides" paragraph, then the "Positioning" paragraph; Proposal 2's "evaluation contract"; Proposal 3's three-line code block. The evidence, the failure story and the outline carry the acceptance case, so keep them.

Keep the companion material out of the form fields. `docs/TECHNICAL_NOTE.md` backs these talks. `docs/TECHNICAL_PIPELINE_WALKTHROUGH.md` describes a Kafka → Spark → Iceberg reference architecture that isn't implemented in this repository, and linking it from a dispatcher talk invites a reviewer to look for code that isn't there.

The incidents and prior art in the pitches are cited so a committee member can check them:

| Reference | Source |
|---|---|
| Replit agent deletes a production database during a code freeze (July 2025); fix includes approval on destructive commands | [AI Incident Database #1152](https://incidentdatabase.ai/cite/1152/), [Fortune](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure) |
| GitHub MCP exploit: a malicious public issue steers an agent to leak a private repository into a public PR (May 26, 2025) | [Invariant Labs](https://invariantlabs.ai/blog/mcp-github-vulnerability) |
| The lethal trifecta (June 16, 2025) | [Simon Willison](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) |
| CaMeL: capabilities and information flow for agents | [arXiv 2503.18813](https://arxiv.org/abs/2503.18813) |
| FIDES: information-flow control in Microsoft Agent Framework | [Microsoft Research](https://www.microsoft.com/en-us/research/publication/securing-ai-agents-with-information-flow-control/), [github.com/microsoft/fides](https://github.com/microsoft/fides) |

Every figure above reproduces from this repository:

| Figure | Source |
|---|---|
| 0/2/10 delegation arms | `evidence/*.json` → `delegation` |
| 0/300 fuzzer violations; 105/300 without the mediator | `redteam`, `redteam_without_execution_mediator` (103 in the other three worlds; the talks quote devtools). On a terminal use `trustkernel matrix --attempts 300`: the default of 150 attempts prints 60 and 57. |
| 0/60 bandit; 60/60 positive control | `adaptive` |
| 25/29 ablations; 25/25 falsifiers; the two redundant pairs (F11, F13) | `summary`, `ablation`; live with `trustkernel ablate --only F11 --only F13` |
| 36/36 legitimate cases; 11 µs and 47 µs median guarded read at depth 0 and 3 | `evidence/guard-workloads.json` (warm, local, in-process, no approval signing; descriptive, not a latency guarantee) |
| 2/7 and 7/7 workshop checks | `python -m workshop.check --implementation starter` and `--implementation solution` |
| 203 original tests; 10 of 11 new adversarial tests failing (the 11th a concurrency control); six defects | Historical record in `docs/REVIEW.md` and `docs/TECHNICAL_NOTE.md` |
| 40-line oracle | `src/trustkernel/evaluation.py` |
