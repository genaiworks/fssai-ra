# Trust by Construction: A Cross-Sector Reference Architecture for Governed Agentic AI

**Proposed panel:** Agentic AI in the Loop - From Autonomous Tools to Shared Capacity
**Keywords:** agentic AI; system literacy; secure data governance; institutional sovereignty; reference architecture; fail-secure systems; verifiable governance; digital public goods
**Reference implementation:** https://github.com/genaiworks/fssai-ra (release v1.0.0 for baseline figures, plus current-source supplements; record the reviewed commit at submission)

> Paste each section below into the matching form field. Headings are field
> labels, not prose. Run `python scripts/check_submission.py` before submitting.

## Introduction

AI governance still centres on models. The governed object is the whole system that moves data, grants power, acts, records effects, and recovers. Corporate, medical, and academic systems face different laws yet the same questions: who held power, what was seen, what happened, and how can it be challenged?

This work presents Trust by Construction and one foundational thesis: intelligence is untrusted; power and data are mediated. Treat every model as capable, persuasive, and possibly misaligned. Route every effect and every flow of protected data through mediators the model cannot bypass. Trust only what is contracted, tested, and evidenced where it is relied on. Two rules follow. A model may propose an action; it cannot manufacture the authority to execute it. A model may request information; it cannot manufacture the entitlement to see it, or launder what it saw.

Mediators alone hold write and record credentials, recheck purpose, consent, and revocation at every use, and label outputs by what built them. Authority only narrows; restriction only accumulates. The thesis is falsifiable: one model output that alone causes a governed effect or disclosure refutes it. Building on reference monitors, information-flow control, and AI control, the paper offers an open, testable foundation; education spreads it as system literacy.

## Development Section 1 Methodology Core Argument and Case Context

The method treats an agentic AI system less like an application and more like a governed institution. It needs separated powers, a memory it cannot rewrite, and a safe way to stop. Its mechanisms are not new: reference monitors, lattice information flow, separation of duties, and recent capability and flow control for agents precede it. The contribution is composing them with institutional purpose, consent, review capacity, and evidence.

The contract is machine-readable; each check names the requirement it defends. Teams begin with one consequential capability and a manual fallback, writing the failure test before connecting real data or keys. If any field cannot be filled, the team has found an unresolved governance choice rather than a function ready to automate.

Seven logical planes implement the pattern. The boundary plane authenticates ingress and egress, quarantines untrusted input, and exposes a no-read-back seam that certified one-way hardware can replace. The data plane keeps stable IDs, replayable events, and versioned snapshots. The intelligence plane contains replaceable models and retrieval but no write power. The authority plane issues purpose-, time-, and holder-bound grants. The execution plane rechecks identity, policy, version, approval, and replay before writing. The evidence plane binds intent to outcome. The resilience plane revokes, reconciles uncertain effects, fails securely, and routes work to fallback.

The open stack maps these duties to FastAPI, PostgreSQL or Redis, Kafka, PySpark, Iceberg, object storage, local models, signing, and a software one-way seam. They are replaceable adapters: a new stack inherits no assurance until the same failure cases pass in its environment.

Reading is governed like acting. A context gate alone holds the record-store credential. A signed grant binds holder, purpose, subjects, fields, classes, and expiry; consent and revocation are checked at every read; each class reaches only model endpoints in approved zones. Every output inherits the labels of all data its session received, so a model cannot declassify its own summary. Only an independent role approving that exact output can.

An approval signs an exact proposal digest covering the operation, target, before and after state, evidence version, requester, resource version, role, audience, and expiry. A change needs new authority. The executor reads the review class from a deployment pack, never from the model. A retry returns the same receipt or enters reconciliation; it cannot improvise a second action.

Authority may cross agent chains, but no principal may pass power it does not hold. Chain invariants cover roots, scope, holder, beneficiary, depth, time, cycles, provenance, and non-delegable acts. Human review is one authorization source, not the architecture. When used, declared capacity, a deliberation floor, escalation, and fallback stop excess demand from becoming empty approval. An AI review assistant must differ in model, evidence path, and adversarial posture from the proposing agent.

Domain packs supply institutional meaning: purpose, basis, data classes, duties, bans, lifecycle rules, owners, transitions, disclosure policy, fallback, tests, and limits. The corporate pack governs classification, internal use, external release, revocation, and legal hold. The health pack governs record access and secondary use while excluding diagnosis, treatment, triage, prescribing, and record alteration. Education packs govern support and record correction. New sectors replace the pack, not the kernel.

Assurance combines randomized properties, bounded state checks, ablation, backend conformance, race tests, an open adversary corpus, and a threat catalogue whose evidence must exist. Each asks whether an unimagined state breaks an invariant, a control is load-bearing, or a replacement preserves behavior.

## Development Section 2 Results Analysis and Impact

All results are fixture observations in declared local environments: not security probabilities, a certification, or evidence of production readiness.

Against the synthetic student-support profile, 30 of 30 adversarial scenarios were contained with zero unauthorised mutations, and 6 of 6 benign tasks completed for a false-denial rate of 0.0. Bounded model checking explored 240 configurations with zero invariant violations, reaching 11 distinct denial controls. Eight of eight ablated controls restored their harm when removed: authority coverage 1.0. Twenty-six conformance checks passed on two independent backends, and a 32-caller replay race produced one mutation and one receipt.

The same hostile proposals and legitimate work went to three architectures. An unguarded agent contained none and delivered 28 harmful actions. A prompt-guarded arm, adding a safety prompt and per-agent tool allowlist, contained 29 percent and delivered 8. The full architecture contained all seven and delivered none, at no cost to benign completion.

Review capacity shows why human oversight is a system resource, not a slogan. With the reference assumptions, a roster of 11 reviewers sustains 2,640 consequential actions per day. In a queue trial, 40 arrivals reach one reviewer budgeted for 8. Some proposals are structurally valid yet wrong on merit. Without load control, four such failures execute. With it, none do, and 32 actions defer to manual review. The degradation curve is a declared parameter, not a measure of real officers; field study remains open.

Across four synthetic packs, the identical kernel covers 33,600 bounded configurations, contains 120 of 120 hostile scenarios, completes 37 of 37 benign tasks, and records zero unauthorised mutations. This demonstrates reuse, not sector compliance or safety. The academic pack retains the transfer baseline: 4,800 configurations with zero violations, 30 of 30 scenarios contained, 9 of 9 benign tasks, 26 conformance checks. Its first run exposed a role declared in the pack but ignored at runtime.

Reads were tested the same way. Across corporate and healthcare packs, 48 of 48 hostile data flows were contained, including wrong-patient injections, purpose switches, withdrawn consent, and self-labelled summaries. Conventional access control contained 16. All 14 checks were load-bearing, and 9,168 configurations showed zero violations. Stateful testing, 16,000 random operations against an independent model, found that release skipped the consent recheck; fixed, it agrees everywhere.

The design assumes the model may be misaligned. Of 33 failure classes, from specification gaming and deceptive risk reports to oversight flooding and compromised signers, 18 are contained, 10 bounded, and 5 residual. Six falsifiers made 55,937 bounded attempts to refute the thesis and found no counterexample.

An open adversary corpus scores YAML attacks without records or code and reports external contributions; today that number is zero.

Composition adds two findings. Checking only an immediate delegator contained 2 of 10 hostile chain classes; full-chain checks contained all 10. Model-assisted review completed five times the valid work of the unaided arm, but a dependent assistant repeated more merit errors than an independent one.

For AI for Learning, an education pack governs an institutional workflow. For Learning for AI, the architecture teaches system literacy: trace data, bound delegation, locate independent enforcement, calculate capacity, and reconstruct accountability. No learning gain is claimed; none has been measured.

Open questions include the trusted base itself, hardware isolation, covert channels, re-identification, reviewer accuracy, fairness, cost, and independent audit. Containers on one host are logical separation, not independent administrative trust.

## Conclusion

Trust by Construction moves AI governance from models to systems on one thesis: intelligence is untrusted; power and data are mediated. A model may reason, but cannot change a protected record, see beyond its grant, launder what it saw, approve its own proposal, rewrite evidence, or hide an uncertain outcome. Safety rests on verifiable boundaries, not on trusted intentions.

Five actions follow for any institution building AI: name each mediator and the credential only it holds; bind every consequential action and sensitive read to a purpose, an owner, and a failure test; declare the trusted base and review capacity; claim conformance by class with locally regenerated evidence; and share failure cases, not sensitive data.

Policymakers can then demand named powers, limits, fallback, and proof. Engineers can map each duty to an enforced interface and rerun the falsifiers after replacing any model or product. Education supplies the literacy to inspect both.

The claim is bounded. A governed agent can enforce an unjust rule faster; mediation makes action attributable and contestable, not fair. The prototype proves neither production security nor compliance. It offers a falsifiable foundation for law, public voice, hardware assurance, and independent evidence to build on.

## References

Costa, M., et al. (2025). Securing AI agents with information-flow control. https://arxiv.org/abs/2505.23643

Debenedetti, E., et al. (2025). Defeating prompt injections by design. https://arxiv.org/abs/2503.18813

Denning, D. E. (1976). A lattice model of secure information flow. Communications of the ACM, 19(5), 236-243. https://doi.org/10.1145/360051.360056

Greenblatt, R., Shlegeris, B., Sachan, K., and Roger, F. (2024). AI control: Improving safety despite intentional subversion. Proceedings of the 41st International Conference on Machine Learning. https://arxiv.org/abs/2312.06942

Saltzer, J. H., and Schroeder, M. D. (1975). The protection of information in computer systems. Proceedings of the IEEE, 63(9), 1278-1308. https://doi.org/10.1109/PROC.1975.9939

Autio, C., et al. (2024). Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile. NIST AI 600-1. https://doi.org/10.6028/NIST.AI.600-1

ISO/IEC. (2023). ISO/IEC 42001:2023 - Information technology, Artificial intelligence, Management system. https://www.iso.org/standard/81230.html

Miao, F., and Cukurova, M. (2024). AI competency framework for teachers. UNESCO. https://unesdoc.unesco.org/ark:/48223/pf0000391104

OWASP GenAI Security Project. (2025). OWASP Top 10 for Agentic Applications 2026. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

Parasuraman, R., and Manzey, D. (2010). Complacency and bias in human use of automation: an attentional integration. Human Factors, 52(3), 381-410. https://doi.org/10.1177/0018720810376055

Rose, S., Borchert, O., Mitchell, S., and Connelly, S. (2020). Zero Trust Architecture. NIST SP 800-207. https://doi.org/10.6028/NIST.SP.800-207

United Nations. (2024). Global Digital Compact. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact
