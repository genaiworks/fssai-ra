# AIE CODE Summit SF 2026 — submission-ready proposals

Select **Brand new session** for each submission. Submit in the order below: each session stands alone and gives the program committee a different format and outcome, so accepting one does not make another redundant. Pick the closest track labels the form offers.

---

# Proposal 1 — recommended first submission

## Session Title

Approved for the Build, Used for the Deploy: Where Coding-Agent Authorization Breaks

## Description

A reviewer approves one build. Your coding agent deploys a different one, and every log line still says "approved."

In this live demo I follow a single release request from the agent's tool call to the deployment record it changes, then break it three ways. A worker agent borrows the coordinator's authority. The approved build is swapped before execution. A retry pairs a forged approval with a cached receipt. Each attack gets through a dispatcher that looks careful on review.

Then I close each gap in plain Python: take caller identity from the runtime, never from the model's request; verify the whole delegation chain back to the requester, not just the last hop; and sign approval over the effective arguments, defaults included, so it authorizes exactly one action. On ten scripted delegation chains, trusting the presented scope stops none, per-hop checking stops two, and full-chain verification stops all ten while the legitimate chain still completes.

I also cover the opposite mistake: a legitimate retry has to return the original result without asking the human again and without deploying twice.

You'll leave with a small dispatcher to adapt to your own agent stack, adversarial regression tests, and a one-page worksheet covering identity, credentials, approval and recovery. The demo runs offline with scripted requests, so it doesn't depend on conference Wi-Fi or a model API.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

Coding agents are getting deploy keys faster than teams are working out what an approval actually authorizes. This talk answers that for one workflow every attendee recognizes — build, approve, deploy, retry — with code they can read on screen and run afterwards.

I'm Rachna Srivastava, an enterprise architect working independently on authorization for AI agents. I built the reference implementation and the attack harness behind this session, and the most instructive bug in it is mine: the executor verified approval signatures correctly, but a cached-result shortcut in front of it returned a receipt without checking the approval at all. The talk shows that integration mistake live, because it's the kind attendees are most likely to ship.

The session is built for the stage. There's one story, three attacks and three fixes, with every result shown as a changed deployment record rather than a log message. It runs locally, so it works without the network. The repository, recorded run-through and worksheet are ready for reviewers now (links below).

## Possible Tracks

Coding Agents; Security; Agent Infrastructure.

---

# Proposal 2 — evaluation and failure analysis

## Session Title

203 Tests Passed. Our Agent Guard Still Had Bypasses.

## Description

The test suite was green: 203 passing. The integration wrapper around the agent guard still let a modified session context drop a secret's data label, and let a forged approval collect a cached receipt. This talk explains why the tests missed both, and how to build evaluations that wouldn't.

The core problem is that most agent-security tests check the guard's answer, not the world's state. I show a synthetic deployment that writes an unreviewed build and then raises "denied." A test that trusts the refusal passes it. An independent effect oracle, which compares system state before and after, catches the write. It's about 40 lines of standard-library Python, and you can copy it today.

From those two failures I build a repeatable protocol:

1. Define the harmful effect before writing any attack.
2. Pair every attack with legitimate work that must still succeed.
3. Remove the control and confirm the attack succeeds; this is your positive control.
4. Restore the control and confirm the attack fails again.

Applied across 29 control-removal experiments, harm returns in 25. The other four aren't wasted checks. They're redundant pairs, and removing both halves of a pair brings the harm back. That's the difference between "this control does nothing" and "this control has a backup."

You'll leave with the effect oracle, an experiment worksheet, and runnable positive and negative controls, all on synthetic fixtures you can replace with your own.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

Every team wiring agents into internal tools will be asked "how do you know the guardrails work?" A passing test count and a refusal message are the usual answers, and neither measures what the system actually did. This talk gives attendees a better answer, drawn from defects I found in my own implementation after its suite passed.

I'm Rachna Srivastava, an enterprise architect working independently on authorization and evaluation for AI agents. I built the reference implementation, the falsification harness (25 falsifiers, each paired with a legitimate-work check) and the ablation experiments behind this session. It's a failure story told by the person who made the mistakes. That's what makes it credible and useful, and it's still rare on conference stages.

The talk stays focused on two concrete failures and one ablation result; the full experimental tables are in the repository for anyone who wants them. Everything shown can be re-run from a clean checkout with one command.

## Possible Tracks

Evals; Security; Agent Reliability.

---

# Proposal 3 — hands-on workshop

## Session Title

Stop Your Coding Agent's Summarizer from Leaking Secrets

## Description

Your summarizer agent has narrow permissions: it can only post to Slack. It never touches the vault. But the worker that fed it did, and now a credential is on its way to #general inside a summary labeled "public."

In this hands-on Python workshop you'll build the fix yourself. Start from a worker-to-summarizer pipeline that leaks a synthetic secret, then repair three functions:

1. Label what each worker reads.
2. Carry that label through every handoff.
3. Check the recipient before anything reaches a channel.

Two real workflows must keep working throughout: a public metrics summary, and an authorized disclosure to the security team. A fix that blocks everything fails the exercise.

Then attack your own repair. Reset the session, throw an exception mid-read, route the secret through a second worker, and watch the actual output sink rather than the log. Seven supplied checks score your pipeline: the starter passes 2 of 7 and a complete repair passes all 7.

You'll leave with working code, regression checks, reference solutions, and a worksheet for finding the same three boundaries in your own tool pipeline. Recovery checkpoints mean nobody gets stuck. Bring a laptop with Python 3.10 or later and install the dependencies beforehand. No model API, GPU or credentials are needed.

## Session format

Workshop — 90 minutes.

## Special Flags

None.

## Speaker/Session Pitch

Multi-agent coding systems move information as well as authority, and most permission models only track authority. A summarizer with tightly scoped tools can still leak everything its upstream workers read. Attendees will find that missing connection by watching a leak happen and then fixing it in their own editor.

I'm Rachna Srivastava, an enterprise architect working independently on authorization for AI agents. I built the guard, disclosure fixtures and checks this workshop uses.

The kit is complete, and every step has been machine-tested end to end:

- editable starter code with three marked TODOs
- two recovery checkpoints, so late joiners and stuck participants rejoin at the next step
- a reference solution and seven output checks
- a participant handout, an answer guide and a minute-by-minute instructor plan

The exercises deliberately include exception paths and session-reset attacks, and they close with the paths a decorator can't secure, such as direct network access, so attendees leave knowing where their own architecture needs more than code. Everything runs locally, so the room doesn't need to share a network or API quota.

## Possible Tracks

Multi-Agent Systems; Security; Coding Agents.

---

## Before submitting — do not paste this section into the form

These three items do more for an unknown speaker's acceptance odds than any wording change:

1. **A public repository link** in every pitch. Reviewers who can clone the demo in two minutes stop wondering whether the talk exists.
2. **A 3–5 minute screen recording** of Proposal 1's demo (unlisted YouTube or Loom). The AIE committee weighs delivery heavily for first-time speakers.
3. **Replace "(links below)"** in Proposal 1's pitch with those two URLs, and add them to the other two pitches as well.

The quoted figures are reproducible: `evidence/*.json` gives 25/25 falsifiers held and 25/29 ablations with harm in every world, plus the 0/2/10 delegation arms. `python -m workshop.check --implementation starter|solution` gives 2/7 and 7/7. The count of 203 is the historical result recorded in `docs/REVIEW.md`, not a current test count. If a reviewer asks about scope, give them one sentence: all figures are fixture observations on synthetic worlds, not production measurements.
