# AI Engineer CODE Summit 2026 — submission fields

One recommended submission for AIE, paired with the separate AI Con proposal. The form allows up to three submissions; there is no need to fill all three slots with overlapping talks.

## Session Title

Your Coding Agent Has Approval. Is It for This Deploy?

## Description

Learn how to keep a coding agent from turning approval for one build into permission to deploy another. In this live Python demo, we put a tool dispatcher between a hostile agent and a synthetic production service, then test what actually gets deployed.

We follow one incident-response workflow through three failure cases: a worker borrowing another agent’s authority, a deploy request changing after human review, and a summarizer passing a credential to a public channel. The fixes are concrete: verify the delegation chain, bind approval to the exact action, and carry data labels through worker handoffs.

Then we attack the fixes. On ten constructed hostile chains, our scope-and-signature-only baseline blocks two; whole-chain verification blocks ten. A legitimate chain completes under all three tested designs. Removing controls exposes which checks prevented harm and which have a backup. We also show bugs found in our own integration wrapper: a changed session identifier erased a label, and cached results skipped approval validation.

You’ll leave with a runnable dispatcher example, adversarial regression tests, and a method for checking side effects instead of trusting “denied” messages. The demo is scripted and runs locally without a model API. The results describe these fixtures—not production effectiveness or a benchmark of commercial agent frameworks.

## Session format

**Stage Talk (15–20 minutes)** — preferred. Willing to adapt to an Online Talk if requested. Select the matching options offered in the form.

## Special Flags

**None.** No special eligibility or launch claim is made.

## Speaker/Session Pitch

I built the Python reference implementation and attack harness used in this session. I can take the audience from a malicious tool request to the authorization check, the resulting system state, and the regression test. I’m Rachna Srivastava, an enterprise architect presenting independent work in a personal capacity.

Coding agents increasingly connect incident triage, worker delegation, and deployment tools. That makes the boundary between “the agent proposed it” and “the service executed it” an immediate engineering concern. This talk gives that boundary a concrete implementation and an adversarial test, using a software-delivery workflow throughout.

The strongest part of the session is the failure analysis: the original harness passed while its integration wrapper still admitted bypasses. I show the defects and fixes alongside the limits of the evidence. The contribution is an inspectable implementation and evaluation method built on established security ideas. I do not claim a new cryptographic primitive or production deployment results.

The stage demo uses local synthetic data and needs no model service. Attendees can rerun the dispatcher example and attack tests. The 20-minute run sheet keeps the broader four-domain evaluation in the supporting material.

## Possible Tracks

**Coding Agents; Security; Evals.** Choose the closest available labels in the form, up to three. The exact dropdown options were not provided.

---

## Organizer facts and author checklist — do not paste into the fields

- Event: November 10–12, 2026, San Francisco. CFP closes October 11, 2026, 11:59 PM Pacific. [Official event](https://ai.engineer/code/2026), [speaker CFP and formats](https://sessionize.com/aiecode26/), checked September 21, 2026.
- Add an anonymously accessible repository/release URL and, ideally, a short demo recording to the committee pitch. No public artifact URL was verified in this review.
- Confirm biography wording with the speaker. The prior academic-submission claim is omitted because it was not verified.
- Rehearse using `docs/TALK.md`. These are session proposals; acceptance or proceedings publication is not implied.
