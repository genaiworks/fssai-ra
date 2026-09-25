# AI Con USA 2027 — two proposed sessions

Event: June 6–11, 2027, Hyatt Regency Seattle and online. Submission deadline: **October 18, 2026**. TechWell describes standard sessions as one hour, including ten minutes of questions, and runs half- and full-day tutorials, which it calls its most popular and highest-rated format. Sources checked September 24, 2026: [speaker guidance](https://www.techwell.com/software-conferences/be-a-speaker), [event](https://aiconusa.techwell.com/conference/88274/front), [tutorials](https://aiconusa.techwell.com/program/tutorials).

Submit both. The session is a 60-minute argument; the tutorial is the same method as a half-day lab. They reach the committee as two different formats, so either can be accepted on its own.

---

# Submission 1 — technical session

## Session title

"Denied" Is Not a Test Result: Effect Oracles, Positive Controls, and Ablations for AI Agent Security

## Abstract

Your agent security test attacks the deployment tool and gets back "denied." The test passes. But did the control stop the action, or did the tool write the unreviewed build first and then raise the refusal? An assertion on the exception can't tell the difference. Most agent-security suites are built from exactly those assertions.

Agents' own reports are no better evidence. In a widely reported 2025 incident, a coding agent deleted a production database during a code freeze it had been told to respect. The only reliable evidence was the database itself. Testers know this principle: assert on the system of record, not on what the component claims.

This session applies the tools testers already trust (oracles, controls and mutation testing) to AI agent authorization and data-disclosure controls. The running example is a multi-agent software-delivery workflow: agents read operational data, delegate to workers, propose deployments that need human approval, and pass summaries between each other.

The method has four parts, each demonstrated live:

- **Effect oracles.** Harm is judged by diffing system state outside the code under test: the deployment register, the released-message sink, the model inputs. The oracle never reads the guard's own decision log. The reference oracle is 40 lines of standard-library Python.
- **Liveness pairs.** Every attack is paired with legitimate work that must still complete, because a control that refuses everything contains everything.
- **Attacker positive controls.** Before trusting a zero, prove the attacker can win against a weakened system. A 300-attempt grammar fuzzer causes 0 unauthorized effects against the full system and 105 with the execution mediator removed. An adaptive bandit attacker goes from 60 of 60 episodes to 0 of 60.
- **Ablation as mutation testing for security controls.** Delete each control, re-run and restore it. If nothing fails, either the control is dead or your tests are blind. Across 29 configurations, harm returns in 25. The four that stay blocked are two redundant pairs, and removing each pair jointly brings the harm back. A naive study would call those controls dead code.

Then comes the part most talks skip: what this harness missed. A 203-test suite passed, yet ten new adversarial tests failed against the integration wrapper. The defects included cached replay that skipped approval verification, session handles that could be swapped to drop a data label, and a JSON coercion that let one approval cover a different call. I walk through each defect as a test-design lesson and show the regression that now pins it.

Every example is real code: a dispatcher that verifies an Ed25519 approval over the exact arguments before the tool runs, and an oracle that catches a tool that writes state and then raises `DENIED`. Attendees get the effect oracle, an ablation worksheet, and a runnable offline example: no model API, no network.

## Key takeaways

1. **Assert on effects, not refusals.** Build an oracle that diffs world state outside the mediator, and pair every attack with a liveness check.
2. **Prove your attacks can win.** Run a weakened-system positive control before reporting a zero, then treat ablation as mutation testing: single and joint removals tell a useless control from a redundant one.
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

## Implementation and reproducibility

The demonstrated boundary is concrete. A request enters as a JSON tool name plus arguments. A trusted dispatcher resolves the authenticated caller to an issued context, re-derives authority from the root delegation, binds Python defaults, canonicalizes the effective arguments, and verifies an Ed25519 approval over the principal, tool, resource, request identity and SHA-256 argument digest. Only then does the registered callback receive its credential. A separate effect oracle snapshots the deployment register and release sink before and after the call, so a callback that writes state and then raises `DENIED` is reported as harm.

Attendees receive a three-layer map of where to observe:

1. **Authorization path:** caller binding → root-derived delegation checks → exact-action approval → registered callback.
2. **Information path:** read metadata → monotone session label → explicit handoff propagation → recipient and purpose release check.
3. **Evidence path:** independent effect snapshot → target-state diff → reproducible JSON result.

The demonstrations use only local commands:

```bash
python examples/effect_oracle.py       # write-then-deny caught by the state diff
python examples/replay_boundary.py     # forged retry refused before the cache
trustkernel redteam --attempts 300     # 0 unauthorized effects (~4 s)
trustkernel redteam --attempts 300 --remove execution_mediator   # 105: the attacker can win
trustkernel ablate --only F11 --only F13                          # the two redundant pairs
make evidence                          # regenerate and byte-compare all figures
```

`make evidence` regenerates the four domain result files in a temporary directory and tests that the checked-in artifacts match. The figures are synthetic, authored attack cases: 25 falsifiers, 27 single ablations plus two paired ablations, and a 300-attempt seeded grammar fuzzer. They demonstrate method, not production attack rates. The talk separates what the reference code demonstrates from what a deployed service still has to supply: authenticated callers, process or container separation, durable target-side idempotency, crash reconciliation and load or failover measurement.

The handout also gives a reusable failure taxonomy:

| Failure | Observable test | Required repair |
|---|---|---|
| Approval says "approved" for the wrong build | Target register contains the unapproved build | Bind canonical effective arguments to the approval digest |
| Cached receipt bypasses verification | Forged retry returns the real receipt | Verify signature, audience, payload and expiry before cache lookup |
| Worker label disappears on exception | Sensitive value reaches a downstream sink after a failed read | Apply the label before entering the tool body |
| Refusal follows a side effect | State diff is non-empty despite `DENIED` | Observe the target outside the guard and fail the test |
| Zero attacks with a dead attacker | Positive-control system never permits the effect | Remove the mediator and prove the attacker can win |
| A control looks deletable | Single ablation shows no harm | Remove it jointly with its suspected backup before deleting it |

## Speaker biography

Rachna Srivastava is an enterprise architect with more than twenty years of experience designing enterprise systems, and now designs and evaluates authorization for AI agent systems. She built the open reference implementation, attack harness and ablation experiments presented in this session, including the regression tests for integration defects she found in her own code. Her focus is making agent security claims testable: every figure she presents regenerates from a clean checkout, and a test fails if the published evidence drifts. She speaks in a personal capacity; this work does not represent any employer or institution.

## Committee note

This is a technical experience report built on a working, public reference implementation. The enforcement primitives are established: attenuated capability delegation, signed exact-action approval and information-flow labels. The session doesn't claim to have invented them. Its contribution is bringing the tester's own toolkit to agent security, with effect oracles, liveness pairs, attacker positive controls and ablation as mutation testing, plus a candid analysis of integration failures that a passing suite missed. That makes it a session a QA audience can apply directly, rather than a security talk they have to translate. Figures come from four synthetic policy worlds sharing one kernel and attack grammar. They are reproducible demonstrations of method, not production measurements or a compliance claim. The code is public, with hosted CI green on Python 3.10 and 3.14 and a five-minute reviewer path in the README: https://github.com/genaiworks/fssai-ra/tree/main/security_systems

---

# Submission 2 — half-day tutorial

## Tutorial title

Prove Your AI Agent's Guardrails Work: A Hands-On Lab in Effect Oracles, Taint Tracking and Ablation

## Abstract

Your team added guardrails to its AI agents: permission checks, human approval before deployment, filters on what can be published. How would you show a skeptical reviewer that they work? A passing test count won't do it, and neither will a log full of "denied." This tutorial teaches you to test agent guardrails the way you would test anything that matters: by observing what the system actually did.

You'll work on a laptop in plain Python, with no model account, GPU or network, against a multi-agent software-delivery workflow with synthetic secrets and a deployment register.

- **Build an effect oracle.** Wrap a tool, snapshot the system of record before and after, and catch a tool that writes an unreviewed build and then raises "denied." Pair each attack with legitimate work that must still succeed.
- **Implement taint tracking across agents.** A worker reads a secret, a summarizer rewrites it, a publisher posts it. You'll label the read, propagate the label across handoffs and gate the output sink, taking a leaking pipeline from 2 of 7 checks to 7 of 7 while both legitimate flows keep working. Then you'll attack your own fix.
- **Prove the attacker can win.** Run a seeded attacker against the full system and against one with its execution mediator removed. You'll see why a zero means nothing until the positive control succeeds.
- **Run ablations, which are mutation testing for security controls.** Delete controls one at a time and in pairs. You'll find two controls that look deletable on their own and turn out to be each other's backup.
- **Port it.** Copy the example world, rename it toward your own system, validate it, and fill in a worksheet of identities, approvals, data classes, handoffs and sinks.

You'll leave with working code, regression checks, and a test plan you can take back to your own agents.

## Key takeaways

1. **An effect oracle, written by you,** that judges harm from system state rather than refusals, plus a liveness check that keeps a do-nothing guard from passing.
2. **Working information-flow control across an agent pipeline,** and the four cases that break naive versions: reads that raise, session resets, two-hop laundering and undeclared recipients.
3. **A validated attack harness,** with a positive control and joint ablations, and a worksheet for applying all of it to your own system.

## Audience and format

For QA and test engineers, SDETs, security engineers and technical leads responsible for AI agents that call tools. Level: intermediate. Attendees should be able to read and edit short Python functions. Format: half-day tutorial (about 3.5 hours including breaks; the organizer sets the exact slot). Attendees bring a laptop with Python 3.10 or later and install the kit from the preflight instructions sent in advance. Everything runs offline.

## Tutorial outline

| Minutes | Module | Attendees leave having |
|---|---|---|
| 0–15 | Opening: a test passes while the build is overwritten | Seen a refusal and a harmful effect in the same result |
| 15–60 | 1. Effect oracles and liveness pairs | Written an oracle for a tool, and caught a forged retry refused before the cache |
| 60–75 | Break | |
| 75–165 | 2. Taint-tracking lab | Taken a leaking pipeline from 2/7 to 7/7 and attacked their own fix |
| 165–180 | Break | |
| 180–200 | 3. Positive controls and ablation, with a room vote on which controls to delete | Validated an attacker, then separated dead controls from redundant ones |
| 200–210 | 4. Port it to your system | A validated world and a completed worksheet |

## Committee note

The tutorial is built on material that already runs. Module 2 is a complete lab kit: starter code with three marked TODOs, two recovery checkpoints, a reference solution, seven machine checks, a participant handout and answer guide, all tested from a clean install. Modules 1, 3 and 4 are instructor-led exercises built on examples and commands that already ship and run offline. The minute-by-minute plan is in `workshop/TUTORIAL_HALF_DAY.md`. Because the room needs no network or model quota, the tutorial can't fail on conference Wi-Fi. Every figure comes from synthetic policy worlds; the tutorial teaches a method, not a product or a compliance claim.

## Tutorial speaker biography

Use the session biography above.

---

## Submission preparation — exclude this section from the form

- Add the **4-minute demo recording** (script `docs/RECORDING_SCRIPT.md`, terminal driven by `bash scripts/record_demo.sh`). TechWell reviewers favor speakers they can see presenting. The repository link is already in the committee note; if you publish the dedicated repository with `scripts/publish_standalone.sh`, swap the link.
- **Pilot the tutorial's Module 1 and Module 3** with two or three colleagues before the program is announced, using `workshop/PILOT.md`. Module 2 is machine-tested, but only a pilot shows whether the 45-minute oracle exercise fits. Don't claim the timing has been validated until then.
- The incident in the abstract is the July 2025 Replit/SaaStr database deletion ([AI Incident Database #1152](https://incidentdatabase.ai/cite/1152/)). It's described, not named, in the attendee text; name it on the slide with the citation.
- Attach `docs/TECHNICAL_NOTE.md` as the technical handout if the form accepts supporting material. Don't attach `docs/TECHNICAL_PIPELINE_WALKTHROUGH.md`: it describes a Kafka/Spark/Iceberg reference architecture that isn't implemented in this repository, and it pulls the session away from testing.
- **If the form caps the abstract length** (the form page couldn't be checked from here), paste this 180-word version for Submission 1 and keep the full text for the notes-to-reviewers field:

  > Your agent security test attacks the deployment tool and gets back "denied." The test passes. But did the control stop the action, or did the tool write the unreviewed build first and then raise the refusal? An assertion on the exception can't tell the difference, and neither can the agent's own report. This session applies the discipline testers already trust to AI agent authorization. **Effect oracles** judge harm by diffing the system of record, never the guard's log. **Liveness pairs** make sure a guard that refuses everything fails. **Positive controls** prove the attacker can win before a zero is trusted: 0 unauthorized effects against the full system, 105 with the mediator removed. **Ablation is mutation testing for security controls:** across 29 removals harm returns in 25, and the other four turn out to be redundant pairs, not dead code. Then comes what the harness missed: 203 tests passed while ten new adversarial tests found real bypasses in the integration wrapper. Attendees leave with the oracle, an ablation worksheet and a runnable offline example.

- The biography now states more than twenty years of experience. If you later speak or publish anywhere, add one line; it is the biggest remaining lever for a first-time TechWell speaker.
- On stage, show 0 vs 105 with the two `trustkernel redteam` commands (about 4 s each). If you show the four-world matrix, run `trustkernel matrix --attempts 300`: the default of 150 attempts prints 60 and 57, not 105 and 103.
- Figure sources:
  - `evidence/devtools.json`: fuzzer 0/300 and 105/300 without the mediator (103 in the other worlds); bandit 0/60 and positive control 60/60; ablations 25/29, with residency + model attestation and proposal-digest binding + single-use approval as the redundant pairs.
  - `docs/REVIEW.md`: 203 original tests, and 10 adversarial tests failing against the original wrapper.

These are speaker proposals. No acceptance, publication, production use or independent security audit is claimed.
