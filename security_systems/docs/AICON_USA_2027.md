# AI Con USA 2027 — proposed technical session

Event: June 6–11, 2027, Seattle and online. Submission deadline: October 18, 2026. TechWell describes standard sessions as one hour, including ten minutes of questions. Sources checked September 21, 2026: [speaker guidance](https://www.techwell.com/software-conferences/be-a-speaker), [event](https://aiconusa.techwell.com/).

## Session title

Does Your Agent Security Control Work? Attack It, Remove It, Measure the Effect

## Abstract

An agent security test returns “denied.” Did the control prevent a harmful action, or did the attack never reach the system it was meant to test?

This technical session presents a reproducible evaluation method for agent authorization and disclosure controls. We start with a synthetic software-delivery workflow: workers read operational data, propose a deployment, and exchange summaries. Success is measured from changed system state or released data, rather than the guard’s own refusal message.

The Python harness pairs adversarial cases with legitimate work, removes controls, restores them, and gives attackers a weakened-system positive control. Across 25 falsifiers, all targeted properties hold in the supplied fixtures. Harm returns in 25 of 29 ablation configurations; the denominator includes 27 single-control removals and two paired removals. Four single-control removals remain blocked by a redundant control. That distinction prevents a misleading claim that every check is independently necessary.

We also examine what the harness missed: integration-wrapper defects involving modified contexts, approval replay, and argument binding. Those become regression tests and explicit deployment assumptions. Four policy worlds demonstrate reuse of the same harness, not independent evidence of industry readiness.

Attendees leave able to design effect-based oracles, interpret ablations, and separate reference-code guarantees from deployment responsibilities. The demonstration is scripted and runs without a model API; production reliability and model-level attack resistance remain unmeasured.

## Key takeaways

1. Define an observable harmful outcome and a legitimate-work control before writing attack prompts.
2. Interpret single and paired ablations without mistaking redundancy for a useless control.
3. Audit the dispatcher around the kernel: caller identity, approval validation, label propagation, and crash-safe execution.

## Audience and format

Engineers, security practitioners, architects, and technical evaluators; intermediate Python and authorization knowledge. Proposed topic areas: AI Security & Safety, Agentic AI, and evaluation. Concurrent technical session: 50 minutes plus 10 minutes Q&A, subject to the organizer's final format.

## Session outline

| Minutes | Content | Audience outcome |
|---|---|---|
| 0–5 | Deployment and disclosure failures | Agree on what counts as harm |
| 5–15 | Delegation, exact-action approval, labels | Locate the enforcement boundaries |
| 15–28 | Effect oracles and attacker positive controls | Distinguish refusal from containment |
| 28–38 | Single and paired ablations | Explain all 29 configurations |
| 38–45 | Wrapper defects and regression tests | Challenge the integration, not only the kernel |
| 45–50 | Transfer to another policy world; limitations | Plan an evaluation without overstating it |
| 50–60 | Questions | Inspect assumptions and failure cases |

## Speaker biography

Rachna Srivastava is an enterprise architect working independently on agent authorization and evaluation. She built the reference implementation and attack harness presented in this session. She presents in a personal capacity; this work does not represent an employer or institution.

## Committee note

This is a technical experience report about a reference implementation. Its contribution is the combination of observable-effect evaluation, explicit ablations, positive controls, and a candid integration failure analysis. Delegated capabilities and information-flow controls have substantial prior art. The session does not claim to invent them or to establish regulatory compliance.

## Submission preparation — exclude this section from the form

Provide the public artifact URL, a demo recording, and the accompanying technical handout (`docs/TECHNICAL_NOTE.md`). Confirm the author's biography. These are speaker proposals; no acceptance, publication, production use, or independent security audit is claimed.
