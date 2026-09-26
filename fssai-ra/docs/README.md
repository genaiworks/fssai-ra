# FSSAI-RA documentation index


[End-to-end technical workflow](END_TO_END_WORKFLOW.md) — the whole system in four simple flows, step by step. Read this first.

[Full technical pipeline walkthrough](PIPELINE_WALKTHROUGH.md) — source data, encryption, PostgreSQL, Redis, Kafka, Spark, Iceberg and independently verifiable output.

[Scale tiers](SCALE_TIERS.md) — the small-data deployment (SQLite, no cluster) and the big-data one (Kafka, Spark, Iceberg), and how to choose.

## Begin here

This documentation covers the reusable platform across sectors and publications.
For your first visit, read these guides in order; the specialist routes below
remain available when you need more depth.

| Guide | What you will learn |
|---|---|
| [User guide](USER_GUIDE.md) | Prerequisites, first run, evidence walkthrough, installation, API, console, and a new domain |
| [Feature catalogue](FEATURES.md) | Every major implementation area, how to exercise it, and what its evidence does not establish |
| [Command reference](COMMANDS.md) | CLI commands, Make targets, working directories, dependencies, and validation tiers |
| [Repository map](REPOSITORY_MAP.md) | Source layout, reading order, generated evidence, and historical artifacts |
| [Troubleshooting](TROUBLESHOOTING.md) | Common failures and concrete recovery steps |
| [Research guide](RESEARCH_GUIDE.md) | Reproducible evidence and citing the platform in additional papers |
| [Publication register](../../publications/README.md) | Existing submission context and a template for future papers |

[Architecture implementation review](ARCHITECTURE_REVIEW.md) — 109-control traceability, executed contracts and qualification gaps.

[TBC v11 SDK and Guardian engineering guide](TBC_SDK.md) — executable Passport, memory, population and release controls mapped to the supplied Word specification.

> **Start here if you opened this repository for the first time.** Choose a
> route below. Every main document links back to this map.

## What this repository means

Trust by Construction is a **reference architecture and teaching testbed for governing the
authority of AI agents**. It is not a general chatbot, a finished student system,
or a claim that AI makes policy fair.

Its central rule is:

> **A model may propose an action. It cannot manufacture the authority to
> execute it.**

Both rules follow from one thesis, stated in [`THESIS.md`](THESIS.md) and tested by
`fssaira thesis`:

> **Intelligence is untrusted. Power and data are mediated.**

Its second rule governs the read path, where most harm in systems over
corporate and medical data occurs:

> **A model may request information. It cannot manufacture the entitlement to
> see it, and it cannot launder what it saw.**

The repository turns that rule into three connected layers:

| Layer | Question for a policy leader | Question for an AI engineer | What the repository supplies |
|---|---|---|---|
| **Institutional authority** | Which decision may be delegated, to whom, and who remains accountable? | Which identity and capability may request each exact operation? | domain profiles, seven-field control contract, reviewer roles, manual fallback |
| **Independent enforcement** | What prevents a proposal becoming an unauthorised decision? | Where are policy, approval, version, replay, and credential checks enforced outside the model? | control plane, exact-action approval, separate executor, import and egress boundaries |
| **Inspectable assurance** | What evidence can an institution show, and what does it not prove? | Which scenarios, invariants, ablations, races, and backend contracts can be reproduced? | evidence chain, decision packets, verification, conformance, resilience and evaluation tools |

The technology stack—Python, FastAPI, PostgreSQL, Redis, Kafka, PySpark,
Iceberg, local-model adapters, and a deployable data-diode seam—implements those
duties. The technologies are replaceable. The authority contract and its failure
tests are the “narrow waist” that should remain stable.

## Shared learning path

Everyone should take the same opening route before specialising:

1. **Orient:** [`START_HERE.md`](START_HERE.md) — install, run one workflow,
   trace one decision, and learn the repository vocabulary.
2. **Understand the pattern:** [`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) —
   learn the seven planes, invariants, governed lifecycle, and cross-sector gates.
3. **Learn the design language:** [`PATTERNS.md`](PATTERNS.md) — two
   constitutional rules, seven laws, a pattern catalogue, anti-patterns,
   blueprints for corporate, clinical, agentic, and research systems, and a
   maturity scale.
4. **Know the obligations:** [`SPECIFICATION.md`](SPECIFICATION.md) — what a
   system must do to claim each conformance class, and
   [`RELATED_WORK.md`](RELATED_WORK.md) — what this inherits and adds.
5. **See it:** [`DEMO.md`](DEMO.md) — understand the six-act demonstration and
   the observation each act supports.
6. **Choose your role:** continue through one of the routes below. Return to the
   [glossary](GLOSSARY.md) whenever policy and engineering terms stop matching.

## Policy leader route

Use this route if you approve, govern, procure, audit, or own the affected
service. No source-code reading is required.

1. [`SYSTEM_LITERACY.md`](SYSTEM_LITERACY.md) — understand the five capabilities
   people need to govern an agentic system.
2. [`PROCUREMENT.md`](PROCUREMENT.md) — turn “trustworthy AI” into seven supplier
   questions for one consequential capability.
3. [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) — connect each risk to a mitigation,
   test, observed result, and remaining gap.
4. [`GAPS.md`](GAPS.md) — turn every unresolved claim into a named evidence
   obligation; software tests do not close field, human, or hardware gaps.
5. [`IMPACT.md`](IMPACT.md) — distinguish demonstrated outcomes, reasoned
   benefits, hypotheses, and out-of-scope claims.
6. [`ADOPTION.md`](ADOPTION.md) — use the 30/60/90-day route to a bounded pilot.
7. [`OPERATIONS.md`](OPERATIONS.md) — decide who acts when automation refuses,
   fails, or leaves an outcome uncertain.
8. [`SECURITY.md`](SECURITY.md) — approve the threat model and residual risks;
   do not delegate this reading only to the engineering team.
9. [`ASSURANCE.md`](ASSURANCE.md) — inspect the final claim → mechanism → test →
   evidence → limitation chain.

**Policy outcome:** you should be able to publish one authorisation boundary,
one executable failure test, one oversight ceiling, and one named recovery owner.

## AI engineer route

Use this route if you will implement, integrate, test, operate, or replace a
component.

1. [`START_HERE.md`](START_HERE.md) — follow the exact source-reading order from
   profile to decision packet.
2. [`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) — map the seven
   planes and twelve invariants before selecting implementation components.
3. [`DOMAIN_PACKS.md`](DOMAIN_PACKS.md) — see how the same security kernel is
   applied to education, corporate, healthcare, financial, and government data.
   Then read [`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md) — the read-path
   rule: purpose-bound grants, a context gate, session labels, exact-output
   declassification, live consent, residency, and bounded break-glass.
4. [`PLATFORM.md`](PLATFORM.md) — map the teaching implementation to FastAPI,
   PostgreSQL/Redis, Kafka, Spark, Iceberg, object storage, and local models.
5. [`SECURITY.md`](SECURITY.md) — understand trusted components, attacker
   capabilities, egress, identity, keys, and administrative limits.
6. [`DIODE_DEPLOYMENT.md`](DIODE_DEPLOYMENT.md) — locate the one-way seam and
   distinguish a software interface from certified hardware isolation.
7. [`RESILIENCE.md`](RESILIENCE.md) — study request identity, process races,
   crash points, replay, and reconciliation.
8. [`OPERATIONS.md`](OPERATIONS.md) — connect failure states to operational
   ownership and recovery procedures.
9. [`EXTENDING.md`](EXTENDING.md) — add a new domain or adapter without inheriting
   evidence the new deployment has not generated.
10. [`ASSURANCE.md`](ASSURANCE.md) — verify that each engineering mechanism is
   attached to a bounded public claim.
11. [`openapi.json`](openapi.json) — inspect the generated HTTP contract after the
   conceptual and security model are clear.

**Engineering outcome:** you should be able to trace grant → check → state
change → evidence → recovery for an exact consequential operation, substitute a
backend, and rerun the same conformance properties.

## Educator or facilitator route

1. [`SYSTEM_LITERACY.md`](SYSTEM_LITERACY.md) — learning outcomes and assessment
   rubric.
2. [`LAB.md`](LAB.md) — the complete two-hour facilitator sequence, with a ninety-minute path.
3. [Authority Boundary Worksheet](worksheet/) — a browser-only seven-field
   exercise.
4. [Oversight Capacity Calculator](oversight/) — a browser-only exercise using
   an institution’s declared review assumptions.
5. [`challenges/README.md`](../challenges/README.md) — contribute a failure case
   without sharing student records or executable code.

**Teaching outcome:** participants should demonstrate a refusal, an ablation, a
capacity calculation, a packet-verification limit, and transfer to their own
domain. No learning gain is claimed until it is measured.

## Reviewer or auditor route

1. [`REVIEWERS.md`](REVIEWERS.md) — reproduce the current public claims with `make reviewer`; elapsed time depends on the host.
2. [`ASSURANCE.md`](ASSURANCE.md) — inspect every claim and its boundary.
3. [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) — check unresolved governance risks.
4. [`GAPS.md`](GAPS.md) — verify that every open claim names the evidence needed
   to close it and remains open until that evidence exists.
5. [`REVIEWER_ASSESSMENT.md`](REVIEWER_ASSESSMENT.md) — read the dated editorial
   review record; it is historical context, not current evidence.
6. [`github-implementation-blueprint.md`](github-implementation-blueprint.md) —
   compare the original proposed build specification with the implemented
   repository; do not treat its proposed results as current results.

## Research author route

1. [Research guide](RESEARCH_GUIDE.md) — define the question and preserve inputs, commands, environment, and raw outputs.
2. [Publication register](../../publications/README.md) — cite the software independently and create a record for each paper.
3. [Results](../evaluation/results/RESULTS.md) and [Assurance](ASSURANCE.md) — inspect denominators and limits before quoting figures.
4. [Reviewer guide](REVIEWERS.md) — use the broader checks with the archive prerequisites in [Commands](COMMANDS.md#validation-tiers).

## Historical conference and presentation materials

The [presenter and submission guide](presenter-and-submission-guide.md),
[browser deck](presentation/slides.html), and [panel script](presentation/speaker-script.md)
are retained as conference-context materials. They do not define the scope of the
platform or identify the exact bytes submitted. The repository owner reports
that a prior paper has been submitted; see the publication register for the
limits of the retained record.

Older assets remain available for provenance: [speaker script](speaker-script.md),
`trust-by-construction-final.pptx` (local-only historical artifact), and `extended-abstract.docx` (local-only historical artifact).
The entire `paper/` directory is local-only and ignored; clean clones do not
contain its manuscripts or paper-build inputs.

## What to run at each confidence level

| Need | Command | Meaning |
|---|---|---|
| Install from the repository root | `make setup` | creates the project environment with `python3`; installation downloads dependencies |
| See the idea | `make demo` | one synthetic walkthrough |
| Check implementation | `make test` | deterministic engineering tests |
| Check public claims | `make reviewer` | public runtime suite and experiments; private manuscripts are opt-in with `make manuscript-check` |
| Inspect deployment honesty | `fssaira doctor` | active defaults and readiness blockers; not certification |
| Check the read path | `fssaira disclosure profiles/healthcare_record_access.yaml` | what a model may see and what may leave, against three architectures |
| Extend a domain | `fssaira init PATH --domain-id my-domain` | new structure with intentionally empty assurance |

For CLI commands, enter the inner application directory and activate its virtual environment first. On macOS, the initial interpreter
is usually `python3`; after `source .venv/bin/activate`, use `python`.

## Complete documentation and artifact index

### Current guidance

- [`README.md`](README.md) — this map.
- [`START_HERE.md`](START_HERE.md) — self-directed repository walkthrough.
- [`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) — seven-plane cross-sector pattern, invariants, lifecycle, adoption sequence, and policy and engineering gates.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — where the pattern lives in code: kernel, the two mediators, planes with test-bound must-NOT lists, the GenAI integration contract, and the lifecycle commands.
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — deployment profiles, promotion gates, isolation obligations, and the stop conditions a consequential deployment must meet.
- [`THESIS.md`](THESIS.md) — the Mediation Thesis: intelligence is untrusted; power and data are mediated. Three commitments, precise invariants, six falsifiers, predictions, and what an institution does next.
- [`PILOT_PROTOCOL.md`](PILOT_PROTOCOL.md) — the study that closes the field-evidence gap: pre-conditions, evidence indicators, human-judged outcomes, and stop criteria.
- [`SPECIFICATION.md`](SPECIFICATION.md) — normative requirements in six conformance classes, each tied to an executable test, attestation, or measurement.
- [`FRAMEWORK.md`](FRAMEWORK.md) — **the front door for organisations adopting agent swarms:** five-minute start, nine domains, five maturity levels, the eight-step journey, routes by role and every command.
- [`framework/CONTROLS.md`](framework/CONTROLS.md) — the 50-control catalogue generated from `src/fssaira/framework_catalogue.yaml`: objective, failure prevented, self-assessment question, owner, dependencies, implementation, proof, refusal codes and standards.
- [`MASTER_GUIDE.md`](MASTER_GUIDE.md) — the master guide for secure agent swarms: critical review of the draft, control catalogue, trusted-base measurement, distributed revocation invariants, staffing, procurement clauses, and the one-page checklist.
- [`SPECIFICATION_SWARM_PROFILE.md`](SPECIFICATION_SWARM_PROFILE.md) — companion profile: fourteen requirements for cooperating agents, distributed adapters and witness federation, each tied to a test.
- [`refusal_registry.json`](refusal_registry.json) — every refusal code the build can emit, generated from source; a test fails if it drifts.
- [`RELATED_WORK.md`](RELATED_WORK.md) — foundations inherited, overlap with CaMeL, FIDES, agent design patterns, and AI control, and the contribution stated narrowly.
- [`THREAT_MODEL_2026.md`](THREAT_MODEL_2026.md) — the 2026 record read architecturally: the public agent-intrusion disclosure, covert-objective and monitorability research, and which stages this kernel mediates, defers to a deployment, or does not cover.
- [`PATTERNS.md`](PATTERNS.md) — pattern language, anti-patterns, blueprints, maturity levels, and design review checklist for AI systems over sensitive data.
- [`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md) — the second constitutional rule: what a model may read and what may leave.
- [`PRIVACY_REFERENCE.md`](PRIVACY_REFERENCE.md) — the opt-in HTTP privacy profile: session tokens, encrypted records, a strict model registry, entitled identity restoration, and its limits.
- [`../conference/README.md`](../conference/README.md) — the UNU Macau demonstration package: education pack, falsifiers, ablation, attack lab, and generated evidence.
- [`DOMAIN_PACKS.md`](DOMAIN_PACKS.md) — reusable corporate, healthcare, and education domain packs.
- [`PACK_AUTHORING.md`](PACK_AUTHORING.md) — author a new sector pack in five steps (frame, contract, pack, bind, falsify), loaded through the kernel floor with drift checks.
- [`GLOSSARY.md`](GLOSSARY.md) — policy and engineering vocabulary in one table.
- [`SYSTEM_LITERACY.md`](SYSTEM_LITERACY.md) — education framework and rubric.
- [`DEMO.md`](DEMO.md) — demonstration guide.
- [`LAB.md`](LAB.md) — facilitated lab.
- [`PROCUREMENT.md`](PROCUREMENT.md) — supplier and procurement questions.
- [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) — responsible-AI risk register.
- [`GAPS.md`](GAPS.md) — open-evidence register and pilot evidence bundle.
- [`IMPACT.md`](IMPACT.md) — impact claims and measurement agenda.
- [`ADOPTION.md`](ADOPTION.md) — pilot adoption playbook.
- [`PLATFORM.md`](PLATFORM.md) — platform and deployment guide.
- [`SECURITY.md`](SECURITY.md) — security model and residual risks.
- [`DIODE_DEPLOYMENT.md`](DIODE_DEPLOYMENT.md) — hardware-diode integration.
- [`RESILIENCE.md`](RESILIENCE.md) — concurrency and recovery evidence.
- [`OPERATIONS.md`](OPERATIONS.md) — operations and recovery runbook.
- [`EXTENDING.md`](EXTENDING.md) — domains and adapters.
- [`ASSURANCE.md`](ASSURANCE.md) — claims and evidence.
- [`REVIEWERS.md`](REVIEWERS.md) — rapid independent review.
- [`presenter-and-submission-guide.md`](presenter-and-submission-guide.md) —
  conference preparation.
- [`presentation/slides.html`](presentation/slides.html) — maintained deck.
- [`presentation/speaker-script.md`](presentation/speaker-script.md) — maintained
  deck script.
- [`openapi.json`](openapi.json) — generated API contract.
- `extended-abstract.docx` (local-only historical artifact) — earlier formatted abstract.

### Interactive tools and presentation assets

- [`worksheet/index.html`](worksheet/index.html) — worksheet implementation.
- [`oversight/index.html`](oversight/index.html) — capacity calculator.
- [`assets/trust-boundaries-cover.png`](assets/trust-boundaries-cover.png) — cover
  visual; source prompt in [`assets/cover-prompt.txt`](assets/cover-prompt.txt).
- [`presentation/figures/containment-by-arm.svg`](presentation/figures/containment-by-arm.svg),
  [`presentation/figures/harms-by-arm.svg`](presentation/figures/harms-by-arm.svg),
  and [`presentation/figures/utility-by-arm.svg`](presentation/figures/utility-by-arm.svg)
  — generated presentation charts; styling in
  [`presentation/figures/chart.css`](presentation/figures/chart.css).

### Historical or provenance material

- [`REVIEWER_ASSESSMENT.md`](REVIEWER_ASSESSMENT.md) — dated editorial review.
- [`github-implementation-blueprint.md`](github-implementation-blueprint.md) —
  pre-implementation specification.
- [`speaker-script.md`](speaker-script.md) — superseded PowerPoint script.
- `trust-by-construction-final.pptx` (local-only historical artifact) —
  superseded v1.0.0-era deck.

## The stopping rule

Do not proceed from reading to a real pilot until the institution can answer:

1. What exact action can change a person’s rights, access, record, or resources?
2. Which component holds that write authority, and can the model reach it?
3. Who may approve the action, with how much real review capacity?
4. What happens safely when policy, evidence, approval, execution, or logging is
   unavailable?
5. What can the affected person inspect, challenge, and correct?
6. Which claim has been reproduced in the actual deployment rather than inherited
   from this teaching profile?

If any answer is missing, that is the next document, test, or institutional
decision—not a reason to add a larger model.

- [Public verification, Docker, and custom use cases](PUBLIC_VERIFICATION.md)
