# AI Con USA 2027 — proposed technical session

Event: June 6–11, 2027, Seattle and online. Submission deadline: October 18, 2026. TechWell describes standard sessions as one hour, including ten minutes of questions. Sources checked September 21, 2026: [speaker guidance](https://www.techwell.com/software-conferences/be-a-speaker), [event](https://aiconusa.techwell.com/).

## Session title

"Denied" Is Not a Test Result: Proving Your AI Agent's Security Controls Actually Work

## Abstract

Your agent security test attacks the deployment tool and gets back "denied." The test passes. But did the control stop the harmful action, or did the tool write the unreviewed build first and then report the refusal? Most agent-security tests can't tell those two apart, because they check what the guard said rather than what the system did.

This session is a practical method for testing AI agent authorization and data-disclosure controls by their effects. It uses a realistic software-delivery workflow: agents read operational data, propose deployments, delegate work and pass summaries between each other. Every result is judged by a small, independent effect oracle that compares system state before and after each attack.

You'll see the four experiments that turn a security claim into evidence:

1. The attack fails with the control in place.
2. The legitimate work still succeeds.
3. The attack succeeds once the control is removed; this is the positive control that proves the attack was real.
4. The attack fails again once the control is restored.

Applied to 29 control-removal experiments, harm returns in 25. The other four reveal redundant pairs, where two independent controls each stop the same attack. That's a design strength that a naive "remove and re-test" study would misreport as dead code.

Then comes the part most talks skip: what this harness missed. A 203-test suite passed while the integration wrapper around the guard still allowed approval replay and a label-dropping context change. I walk through both defects and the regression tests that now catch them.

Attendees get a copyable effect oracle in about 40 lines of standard-library Python, an experiment worksheet, and an offline example they can run on the flight home.

## Key takeaways

1. **Measure effects, not refusals.** Define the harmful outcome and a legitimate-work control before writing a single attack prompt.
2. **Prove your attacks are real.** Use a weakened-system positive control, and read single and paired ablations correctly, so redundancy isn't mistaken for a useless control.
3. **Test the wrapper, not just the guard.** Audit caller identity, approval validation, label propagation and crash-safe retries, which are where integrations actually break.

## Audience and format

For QA and test engineers, security practitioners, architects and technical leads responsible for putting AI agents into production. Level: intermediate. Comfort reading short Python snippets helps, but no security specialism is assumed. Proposed topic areas: AI Security & Safety, Agentic AI, AI Testing & Quality. Format: concurrent technical session of 50 minutes plus 10 minutes of Q&A, subject to the organizer's final format.

## Session outline

| Minutes | Content | Audience outcome |
|---|---|---|
| 0–5 | Live: a test that passes while the build is overwritten | See why "denied" isn't evidence |
| 5–15 | The workflow and its boundaries: delegation, exact-action approval, data labels | Know where enforcement has to happen |
| 15–27 | Effect oracles and attacker positive controls, built live | Tell refusal apart from containment |
| 27–37 | Ablations, with an audience poll: "Which controls can we remove safely?" | Read single and paired results correctly |
| 37–45 | What the harness missed: two wrapper defects and their regressions | Aim tests at the integration, not only the guard |
| 45–50 | Reusing the harness in a second domain; a worksheet for your own system | Leave with a plan for Monday |
| 50–60 | Questions | Pressure-test the method against attendees' own stacks |

## Speaker biography

Rachna Srivastava is an enterprise architect who designs and evaluates authorization for AI agent systems. She built the open reference implementation, attack harness and ablation experiments presented in this session, including the regression tests for defects she found in her own integration. Her work focuses on making agent security claims testable: every figure she presents can be regenerated from a clean checkout. She speaks in a personal capacity; this work does not represent any employer or institution.

## Committee note

This is a technical experience report built around a working, public reference implementation. It builds on established ideas: capability-based delegation and information-flow control. Its contribution is the evaluation discipline — effect oracles, positive controls, paired ablations — and a candid analysis of integration failures that a passing suite missed. Attendees can run the demonstration and every experiment offline, without a model API. The figures come from synthetic fixture worlds and are presented as that, not as production measurements or a compliance claim.

## Submission preparation — exclude this section from the form

- Add the **public repository URL** and a **3–5 minute demo recording** to the form; TechWell reviewers favor speakers they can see presenting.
- Attach the technical handout (`docs/TECHNICAL_NOTE.md`) if the form accepts supporting material.
- Confirm the biography wording. If you have prior speaking, publications or years of architecture experience you're willing to state, add one sentence. It is the biggest remaining lever for a first-time TechWell speaker.
- Figures: `evidence/*.json` gives 25/25 falsifiers held and 25/29 ablations with harm in all four worlds. The count of 203 is the historical result recorded in `docs/REVIEW.md`.

These are speaker proposals. No acceptance, publication, production use or independent security audit is claimed.
