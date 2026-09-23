# AI Con USA 2027 — proposed technical session

Event: June 6–11, 2027, Seattle and online. Submission deadline: October 18, 2026. TechWell describes standard sessions as one hour, including ten minutes of questions. Sources checked September 21, 2026: [speaker guidance](https://www.techwell.com/software-conferences/be-a-speaker), [event](https://aiconusa.techwell.com/).

## Session title

"Denied" Is Not a Test Result: Effect Oracles, Positive Controls, and Ablations for AI Agent Security

## Abstract

Your agent security test attacks the deployment tool and gets back "denied." The test passes. But did the control stop the action, or did the tool write the unreviewed build first and then raise the refusal? An assertion on the exception can't tell the difference. Most agent-security suites are built from exactly those assertions.

This session presents a test design for AI agent authorization and data-disclosure controls. It borrows its rigor from experimental method rather than from red-team folklore. The running example is a multi-agent software-delivery workflow: agents read operational data, delegate to workers, propose deployments that need human approval, and pass summaries between each other.

The method has four parts, each demonstrated live:

- **Effect oracles.** Harm is judged by diffing system state outside the code under test: the deployment register, the released-message sink, the model inputs. The oracle never reads the guard's own decision log. The reference oracle is 40 lines of standard-library Python.
- **Liveness pairs.** Every attack is paired with legitimate work that must still complete, because a control that refuses everything contains everything.
- **Attacker positive controls.** Before trusting a zero, prove the attacker can win against a weakened system. A 300-attempt grammar fuzzer causes 0 unauthorized effects against the full system and 105 with the execution mediator removed. An adaptive bandit attacker goes from 60 of 60 episodes to 0 of 60.
- **Single and joint ablations.** Remove each control, re-run and restore it. Across 29 configurations, harm returns in 25. The four that stay blocked are two redundant pairs, and removing each pair jointly brings the harm back. A naive study would call those controls dead code.

Then comes the part most talks skip: what this harness missed. A 203-test suite passed, yet ten new adversarial tests failed against the integration wrapper. The defects included cached replay that skipped approval verification, session handles that could be swapped to drop a data label, and a JSON coercion that let one approval cover a different call. I walk through each defect as a test-design lesson and show the regression that now pins it.

The implementation is concrete rather than conceptual. A request enters as a
JSON tool name plus arguments. A trusted dispatcher resolves the authenticated
caller to an issued context, re-derives authority from the root delegation,
binds Python defaults, canonicalizes the effective arguments, and verifies an
Ed25519 approval over the principal, tool, resource, request identity and
SHA-256 argument digest. Only then does the registered callback receive its
credential. A separate effect oracle snapshots the deployment register and
release sink before and after the call. This lets the audience see the exact
failure boundary: a callback can write state and still raise `DENIED`, which
must be reported as harm.

Attendees get the effect oracle, an ablation worksheet, and a runnable offline example: no model API, no network.

## Key takeaways

1. **Assert on effects, not refusals.** Build an oracle that diffs world state outside the mediator, and pair every attack with a liveness check.
2. **Prove your attacks can win.** Run a weakened-system positive control before reporting a zero, then use single and joint ablations to tell a useless control from a redundant one.
3. **Test the wrapper, not just the guard.** Aim adversarial tests at caller-identity binding, approval-before-cache ordering, argument canonicalization and label propagation on exception paths, which is where integrations actually break.

## Audience and format

For QA and test engineers, security engineers, architects and technical leads putting tool-using AI agents into production. Level: intermediate. Attendees should be comfortable reading short Python snippets; no cryptography or formal-methods background is assumed. Proposed topic areas: AI Security & Safety, AI Testing & Quality, Agentic AI. Format: concurrent technical session of 50 minutes plus 10 minutes of Q&A, subject to the organizer's final format.

## Session outline

| Minutes | Content | Audience outcome |
|---|---|---|
| 0–5 | Live: a test passes while the build is overwritten | See why an exception assertion isn't evidence |
| 5–13 | The workflow's enforcement points: delegation chains re-verified from the root, Ed25519 approval over an argument digest, monotone data labels | Know where the oracle must observe |
| 13–24 | Building the effect oracle and liveness pairs live | Write an effect-based assertion |
| 24–31 | Positive controls: fuzzer 0 vs 105, bandit 0/60 vs 60/60 | Validate the attacker before trusting a zero |
| 31–39 | Ablations, with an audience poll: "Which of these controls can we delete?" | Read single and joint results correctly |
| 39–46 | What the harness missed: the wrapper defects and their regressions | Target tests at the integration seams |
| 46–50 | Porting the harness to a new policy world; the worksheet | Leave with a plan for your own system |
| 50–60 | Questions | Pressure-test the method against attendees' stacks |

## Technical handout and reproducibility

The audience receives a three-layer implementation map:

1. **Authorization path:** caller binding → root-derived delegation checks →
   exact-action approval → registered callback.
2. **Information path:** read metadata → monotone session label → explicit
   handoff propagation → recipient and purpose release check.
3. **Evidence path:** independent effect snapshot → target-state diff → signed
   evidence checkpoint and reproducible JSON result.

The 18-minute demonstration uses only local commands:

```bash
python examples/effect_oracle.py
python examples/replay_boundary.py
trustkernel matrix
make evidence
```

`make evidence` regenerates the four domain result files in a temporary
directory and tests that the checked-in artifacts match. The figures quoted in
the proposal are synthetic, authored attack cases: 25 falsifiers, 27 single
ablations plus two paired ablations, and a 300-attempt seeded grammar fuzzer.
They are not production attack rates. The talk explicitly separates what the
reference code demonstrates from what a deployed service still has to supply:
authenticated callers, process or container separation, durable target-side
idempotency, crash reconciliation, independent attacks and load/failover
measurements.

The technical handout also gives the failure taxonomy attendees can reuse:

| Failure | Observable test | Required repair |
|---|---|---|
| Approval says “approved” for the wrong build | Target register contains the unapproved build | Bind canonical effective arguments to the approval digest |
| Cached receipt bypasses verification | Forged retry returns the real receipt | Verify signature, audience, payload and expiry before cache lookup |
| Worker label disappears on exception | Sensitive value reaches a downstream sink after a failed read | Apply the label before entering the tool body |
| Refusal follows a side effect | State diff is non-empty despite `DENIED` | Observe the target outside the guard and fail the test |
| Zero attacks with a dead attacker | Positive-control system never permits the effect | Remove the mediator and prove the attacker can win |

## Speaker biography

Rachna Srivastava is an enterprise architect who designs and evaluates authorization for AI agent systems. She built the open reference implementation, attack harness and ablation experiments presented in this session, including the regression tests for integration defects she found in her own code. Her focus is making agent security claims testable: every figure she presents regenerates from a clean checkout, and a test fails if the published evidence drifts. She speaks in a personal capacity; this work does not represent any employer or institution.

## Committee note

This is a technical experience report built on a working, public reference implementation. The enforcement primitives are established: attenuated capability delegation, signed exact-action approval and information-flow labels. The session doesn't claim to have invented them. Its contribution is the testing discipline that fits a QA audience (effect oracles, liveness pairs, attacker positive controls, joint ablations) and a candid analysis of integration failures that a passing suite missed. Figures come from four synthetic policy worlds sharing one kernel and attack grammar. They are presented as reproducible demonstrations of method, not production measurements or a compliance claim.

## Submission preparation — exclude this section from the form

- Add the **public repository URL** and a **3–5 minute demo recording**. TechWell reviewers favor speakers they can see presenting.
- Attach the technical handout (`docs/TECHNICAL_NOTE.md`) if the form accepts supporting material.
- Confirm the biography. If you're willing to state prior speaking, publications or years of architecture experience, add one sentence; it is the biggest remaining lever for a first-time TechWell speaker.
- Figure sources:
  - `evidence/devtools.json`: fuzzer 0/300 and 105/300 without the mediator (103 in the other worlds); bandit 0/60 and positive control 60/60; ablations 25/29.
  - `docs/REVIEW.md`: 203 original tests, and 10 adversarial tests failing against the original wrapper.

These are speaker proposals. No acceptance, publication, production use or independent security audit is claimed.
