# Documentation map: what FSSAI-RA means and where to go next

> **Start here if you opened this repository for the first time.** Choose a
> route below. Every main document links back to this map.

## What this repository means

FSSAI-RA is a **reference architecture and teaching testbed for governing the
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

## The shared first three steps

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

1. [`REVIEWERS.md`](REVIEWERS.md) — reproduce the current public claims in about
   ten minutes with `make reviewer`.
2. [`ASSURANCE.md`](ASSURANCE.md) — inspect every claim and its boundary.
3. [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) — check unresolved governance risks.
4. [`GAPS.md`](GAPS.md) — verify that every open claim names the evidence needed
   to close it and remains open until that evidence exists.
5. [`REVIEWER_ASSESSMENT.md`](REVIEWER_ASSESSMENT.md) — read the dated editorial
   review record; it is historical context, not current evidence.
6. [`github-implementation-blueprint.md`](github-implementation-blueprint.md) —
   compare the original proposed build specification with the implemented
   repository; do not treat its proposed results as current results.

## Conference author and presenter route

1. [`presenter-and-submission-guide.md`](presenter-and-submission-guide.md) —
   submission constraints, positioning, claims, and rehearsal advice.
2. [`../paper/form-ready-abstract.md`](../paper/form-ready-abstract.md) — the four
   validated form fields.
3. [`../paper/extended-abstract.md`](../paper/extended-abstract.md) — the readable
   proceedings-oriented version.
4. [`../paper/composition-supplement.md`](../paper/composition-supplement.md) —
   delegated authority and assisted review in full, for questions the abstract
   compresses.
5. [Maintained browser deck](presentation/slides.html) — the current presentation.
6. [Maintained panel script](presentation/speaker-script.md) — timings and cut
   paths for 5, 10, 12, or 16 minutes.

The following files are retained for provenance and are **not the rehearsal
source**: [`speaker-script.md`](speaker-script.md) and
[`trust-by-construction-final.pptx`](trust-by-construction-final.pptx). The
current Word abstract is [`extended-abstract.docx`](extended-abstract.docx).

## What to run at each confidence level

| Need | Command | Meaning |
|---|---|---|
| Install from the repository root | `make setup` | creates the project environment with `python3` |
| See the idea | `make demo` | one synthetic walkthrough |
| Check implementation | `make test` | deterministic engineering tests |
| Check public claims | `make reviewer` | evaluation, verification, transfer, oversight, delegation, assisted review, resilience, and result-drift checks |
| Inspect deployment honesty | `fssaira doctor` | active defaults and readiness blockers; not certification |
| Check the read path | `fssaira disclosure profiles/healthcare_record_access.yaml` | what a model may see and what may leave, against three architectures |
| Extend a domain | `fssaira init my_domain --output PATH` | new structure with intentionally empty assurance |

Always activate the virtual environment first. On macOS, the initial interpreter
is usually `python3`; after `source .venv/bin/activate`, use `python`.

## Complete documentation and artifact index

### Current guidance

- [`README.md`](README.md) — this map.
- [`START_HERE.md`](START_HERE.md) — self-directed repository walkthrough.
- [`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) — seven-plane cross-sector pattern, invariants, lifecycle, adoption sequence, and policy and engineering gates.
- [`THESIS.md`](THESIS.md) — the Mediation Thesis: intelligence is untrusted; power and data are mediated. Three commitments, precise invariants, six falsifiers, predictions, and what an institution does next.
- [`SPECIFICATION.md`](SPECIFICATION.md) — normative requirements in six conformance classes, each tied to an executable test, attestation, or measurement.
- [`RELATED_WORK.md`](RELATED_WORK.md) — foundations inherited, overlap with CaMeL, FIDES, agent design patterns, and AI control, and the contribution stated narrowly.
- [`PATTERNS.md`](PATTERNS.md) — pattern language, anti-patterns, blueprints, maturity levels, and design review checklist for AI systems over sensitive data.
- [`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md) — the second constitutional rule: what a model may read and what may leave.
- [`DOMAIN_PACKS.md`](DOMAIN_PACKS.md) — reusable corporate, healthcare, and education domain packs.
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
- [`extended-abstract.docx`](extended-abstract.docx) — current formatted abstract.

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
- [`trust-by-construction-final.pptx`](trust-by-construction-final.pptx) —
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
