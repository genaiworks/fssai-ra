# AIE CODE Summit SF 2026 — three proposed submissions

Select **Brand new session** for each. These are three alternatives with distinct audience outcomes, not a sequence that requires accepting all three. Suggested submission order: deployment talk, evaluation talk, disclosure workshop. The AI Con proposal remains separate.

Each proposal below uses the six supplied form fields. Track labels are suggestions; match them to the options actually offered. No special flags are claimed.

# Proposal 1 — deployment-security talk

## Session Title

Your Coding Agent Has Approval. Is It for This Deploy?

## Description

Learn how to keep a coding agent from turning approval for one build into permission to deploy another. In this live Python demo, we put a tool dispatcher between a hostile agent and a synthetic production service, then inspect what actually gets deployed.

Follow a release request through three attacks: a worker borrows another agent’s authority, an approved build is swapped for a different build, and concurrent callers replay the same approval. We trace each request from the delegated permissions to the exact principal, resource, and arguments the human reviewed.

Then we attack the wrapper itself. A cached-result shortcut skipped approval validation even though the underlying executor checked signatures correctly. We reproduce the defect, fix the path, and turn it into a regression test. A 32-caller test checks that successful replay executes one callback within a guard instance; we explain why that still does not establish crash-safe execution of external effects.

You’ll leave with a runnable Python dispatcher, approval-binding tests, and a concrete integration plan for caller identity, credential isolation, and durable idempotency. The demonstration uses scripted requests and synthetic state, runs locally without a model API, and makes its deployment assumptions explicit.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

I’m Rachna Srivastava, an enterprise architect presenting independent work in a personal capacity. I built the reference implementation and attack harness used in this talk, including the dispatcher example and exact-action approval flow.

Coding agents connect repository work to tools that can change running systems. Engineers need to know what a human approval actually authorizes when workers delegate, arguments change, and requests retry. This talk answers that question through one release workflow and inspectable code.

The distinctive material is the failure analysis: the integration wrapper bypassed a check that the kernel implemented correctly. I show the defect, the regression, and the fix. The audience gets concrete implementation guidance and an honest account of where the reference library ends and production infrastructure begins.

This submission focuses on execution and approval. My evaluation talk covers experimental design; my workshop focuses on data disclosure through worker handoffs. Each stands alone.

## Possible Tracks

Coding Agents; Security; Agent Infrastructure.


---

# Proposal 2 — evaluation talk

## Session Title

Your Agent Said “Denied.” Check What Actually Happened.

## Description

Build agent security evaluations that catch a bad deployment or a leaked credential even when the guard logs “denied.” This session shows how to observe the side effect, challenge the control, and verify that the attacker can reach the thing you are trying to protect.

We start with a synthetic coding-agent workflow and an oracle that inspects register mutations and released data. Then we remove a control, rerun the same attack, restore the control, and compare outcomes. A weakened-system positive control checks that the attacker can actually cause harm.

The reference harness holds its targeted properties on 25 fixed falsifiers. Harm returns in 25 of 29 ablation configurations: 27 single-control removals and two paired removals. Four single removals stay blocked by a redundant control. We unpack one pair to show why “nothing changed when I deleted it” does not establish that a check is useless.

Finally, we examine the boundary the harness missed: its integration wrapper. New regressions exposed bypasses despite the original suite passing. You’ll leave with an effect-oracle pattern, an ablation reporting template, and a way to test your evaluator’s blind spots. These are scripted fixture experiments, not estimates of production attack rates.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

I’m Rachna Srivastava, an enterprise architect presenting independent work in a personal capacity. I built the falsification harness, ablation configurations, and policy worlds behind this session.

For teams wiring coding agents into internal tools, a refusal message is a poor substitute for evidence about the resulting state. This talk gives engineers an evaluation protocol they can apply to their own controls: define observable harm, include legitimate work, remove and restore a check, and prove the attacker can win in a weakened system.

The results include inconvenient cases: redundant checks, authored baselines with limited scope, and wrapper defects the original harness missed. That makes the session a practical lesson in experimental design and failure analysis. I explain what the fixtures establish and what would require independent attacks or deployment measurements.

This talk centers on how to test a control; the deployment talk centers on implementing exact-action approval. Either can be selected independently.

## Possible Tracks

Evals; Security; Agent Reliability.


---

# Proposal 3 — hands-on workshop

## Session Title

Stop Your Coding Agent’s Summarizer from Leaking Secrets

## Description

Build a worker-to-summarizer pipeline that refuses to publish a credential—even when the generated summary calls itself “public.” In this hands-on Python lab, you’ll track what each worker read, carry that label through handoffs, and check recipient clearance before releasing output.

Start with a coordinator, a metrics worker, a credential-reading worker, and a synthetic team channel. First, get a useful metrics summary through. Then route a protected value through a summarizer and observe the release denial. Remove the label-propagation control in the reference harness and inspect the leaked value.

Next, attack the integration: attempt to reset a session label and let a reading tool raise an exception before it returns. Write regressions that check retained labels and observable output. Finish by adapting the example to a tool schema you supply, using synthetic data.

You’ll leave with a working handoff example and tests for authorized release, blocked disclosure, and label-reset attempts. We also identify the paths a decorator cannot secure: direct network access, uninstrumented logs, and arbitrary code in the guard process.

Bring a laptop with Python 3.10+ and permission to install dependencies before the session. The lab uses scripted agents and synthetic credentials; no model API, GPU, or production secrets are needed.

## Session format

Workshop — 90 minutes, within the published 1–2-hour workshop range.

## Special Flags

None.

## Speaker/Session Pitch

I’m Rachna Srivastava, an enterprise architect presenting independent work in a personal capacity. I built the guard, disclosure fixtures, and adversarial tests used in this workshop. I can guide attendees from a failed release to the policy rule and the handoff that caused it.

Multi-worker coding workflows move information as well as authority. A summarizer can carry a credential into an output even when its own tool permissions are narrow. This workshop makes that integration problem tangible: every attendee gets both a useful release and a blocked disclosure working, then removes a control to see the failure.

The existing dispatcher example and disclosure harness supply the exercises. The lab deliberately includes failure paths and deployment limits, so attendees understand why labeling and output mediation must be enforced by trusted orchestration code. All runtime exercises work locally after setup.

This is a hands-on data-flow session. The two stage proposals focus separately on deployment approval and evaluation methodology.

## Possible Tracks

Multi-Agent Systems; Security; Coding Agents.

---

# Author preparation — do not paste into the submission fields

- Confirm biography and first-person authorship statements before submission.
- Add an anonymously accessible artifact/release URL to each committee pitch. A short recording strengthens the stage proposals. No public URL or recording was verified during this review.
- The original suite passed 203 tests; the hardened code passed 218. Those counts support the artifact review, not a security probability or a production claim.
- Stage talk formats and workshop range come from the [official speaker CFP](https://sessionize.com/aiecode26/), checked September 21, 2026. The user's form establishes the maximum of three submissions. No submission has been sent.
- The workshop is proposed for 90 minutes: setup and benign release (15), labels and handoffs (20), leak under ablation (20), wrapper regressions (20), adaptation and discussion (15). Test installation on a clean laptop and prepare exercise checkpoints before delivery; this proposal does not assert that a complete teaching kit has already been produced.
- Workshop participants should use synthetic fixtures. No production credential or private repository is needed.

## Keep the three presentations distinct

| Submission | Central question | Main artifact | Material to keep brief |
|---|---|---|---|
| Deployment talk | What exact action did the human authorize? | Dispatcher and replay regressions | Disclosure and broad ablation tables |
| Evaluation talk | Did the control prevent the observed harm? | Effect oracle, single/pair ablations | Approval implementation internals |
| Disclosure workshop | Where must labels follow data? | Worker handoffs and release tests | Full delegation comparison and governance architecture |
