# Trust by Construction: A Cross-Sector Reference Architecture for Governed Agentic AI

**Proposed panel:** Agentic AI in the Loop - From Autonomous Tools to Shared Capacity
**Keywords:** agentic AI; system literacy; secure data governance; institutional sovereignty; reference architecture; fail-secure systems; verifiable governance; digital public goods
**Reference implementation:** https://github.com/genaiworks/fssai-ra (release v1.0.0 for baseline figures, plus current-source supplements; record the reviewed commit at submission)

> Paste each section below into the matching form field. Headings are field
> labels, not prose. Run `python scripts/check_submission.py` before submitting.

## Introduction

AI governance focuses too much on models. The full system moves data, grants power, acts, records effects, and recovers. It is the governed object. Corporate data release, medical record use, academic correction, and public support face different laws yet the same questions: what was allowed, who held power, which evidence was used, what happened, and how can it be challenged?

This work presents Trust by Construction, a cross-sector reference architecture for governed agentic AI. Its central rule is simple: a model may propose an action; it cannot manufacture the authority to execute it. Trust is built through separate data, intelligence, authority, execution, evidence, and recovery duties, not inferred from a model, cloud region, private endpoint, or certificate.

The link between policy and code is a seven-field executable control contract for each consequential capability: asset, operation, enforcement point, owner, failure test, evidence, and response. Domain packs add purpose, data classes, duties, bans, lifecycle rules, owners, and tests for any sector.

Education spreads the method; it does not bound it. System literacy lets policy leaders, engineers, auditors, learners, and affected groups inspect how AI gains and uses power. The paper proposes this constitutional layer for future AI and supplies an open base others can test, replace, and extend.

## Development Section 1 Methodology Core Argument and Case Context

The method treats an agentic AI system less like an application and more like a governed institution. It needs separated powers, a memory it cannot rewrite, and a safe way to stop. Zero trust, NIST, OWASP, ISO/IEC 42001, and UNESCO's AI competency work inform the pattern, but each governance duty becomes behavior another team can test after replacing a component.

The control contract is machine-readable. Its seven fields are mandatory, and each check names the requirement it defends. Teams begin with one consequential capability and a manual fallback, writing the failure test before connecting real data or keys. If any field cannot be filled, the team has found an unresolved governance choice rather than a function ready to automate.

Seven logical planes implement the pattern. The boundary plane authenticates ingress and egress, quarantines untrusted input, and exposes a no-read-back seam that certified one-way hardware can replace. The governed data plane assigns stable IDs, streams replayable events, and preserves versioned snapshots and transforms. The intelligence plane contains replaceable models and retrieval but no write power. The authority plane issues purpose-, time-, and holder-bound grants. The execution plane independently rechecks identity, policy, version, approval, and replay state before using a write credential. The evidence plane binds intent to outcome. The resilience plane revokes, reconciles uncertain effects, fails securely, and routes work to fallback.

The open stack maps these duties to Python and FastAPI, PostgreSQL or Redis, Kafka, PySpark, Iceberg, S3-compatible storage, local-model adapters, signing, and a software model of one-way transfer. These products are reference adapters, not the architecture. An adopter may replace them while preserving the contract and rerunning conformance evidence. Portability is behavioral: a new stack inherits no assurance until the same failure cases, invariants, and recovery checks pass in its environment.

An approval signs an exact proposal digest covering the operation, target, before and after state, evidence version, requester, resource version, role, audience, and expiry. A change needs new authority. The executor reads the review class from a deployment pack, never from the model. A retry returns the same receipt or enters reconciliation; it cannot improvise a second action.

Authority may cross agent chains, but no principal may pass power it does not hold. Chain invariants cover roots, scope, holder, beneficiary, depth, time, cycles, provenance, and non-delegable acts. Human review is one authorization source, not the architecture. When used, declared capacity, a deliberation floor, escalation, and fallback stop excess demand from becoming empty approval. An AI review assistant must differ in model, evidence path, and adversarial posture from the proposing agent.

Domain packs supply institutional meaning. Each declares purpose, basis, data classes, duties, prohibited uses, minimization, retention, deletion, residency, incident response, owners, transitions, fallback, tests, evidence, and limits. The corporate pack governs classification, internal use, external release, revocation, and legal hold. The health pack governs record access and secondary use while excluding diagnosis, treatment, triage, prescribing, and record alteration. Education packs govern support and record correction. New sectors replace the pack, not the kernel.

Assurance combines randomized properties, bounded state checks, control ablation, backend conformance, race tests, and an open adversary corpus. Each asks a distinct question: whether calls match an independent rule, an unimagined state violates an invariant, a control is load-bearing, a replacement preserves behavior, retries duplicate an action, or an external failure case defeats the design.

## Development Section 2 Results Analysis and Impact

All results are fixture observations in declared local environments: not security probabilities, a certification, or evidence of production readiness.

Against the synthetic student-support profile, 30 of 30 adversarial scenarios were contained with zero unauthorised mutations, and 6 of 6 benign tasks completed for a false-denial rate of 0.0. Reporting utility beside containment stops a system that refuses everything from looking successful. Bounded model checking explored 240 configurations with zero invariant violations, reaching 11 distinct denial controls. Eight of eight ablated controls restored their harm when removed: authority coverage 1.0. Twenty-six conformance checks passed on two independent backends, and a 32-caller replay race produced one mutation and one receipt.

The same hostile proposals and legitimate work went to three architectures. An unguarded agent contained none and delivered 28 harmful actions. A prompt-guarded arm, adding a safety prompt and per-agent tool allowlist, contained 29 percent and delivered 8. It is not a strawman: an allowlist is a real control that lacks final enforcement independent of the model. The full architecture contained all seven and delivered none, at no cost to benign completion.

Review capacity shows why human oversight is a system resource, not a slogan. With the reference assumptions, a roster of 11 reviewers sustains 2,640 consequential actions per day. In a queue trial, 40 arrivals reach one reviewer budgeted for 8. Some proposals are structurally valid yet wrong on merit. Without load control, four such failures execute. With it, none do, and 32 actions defer to manual review. Deferral is the visible cost of preserving the boundary. The degradation curve is a declared parameter, not a measure of real officers; field study remains open.

Across four synthetic packs, the identical kernel covers 31,360 bounded configurations, contains 120 of 120 hostile scenarios, completes 36 of 36 benign tasks, and records zero unauthorised mutations. This demonstrates reuse, not sector compliance or safety. The academic pack retains the transfer baseline: 4,800 configurations with zero violations, 30 of 30 scenarios contained, 9 of 9 benign tasks, 26 conformance checks. Its first run exposed a role declared in the pack but ignored at runtime.

An open adversary corpus now accepts seven-field YAML attacks and scores them across all three arms. It needs no sensitive record, vendor name, or contributor code. The tool reports external provenance; today that number is zero. Institutions unable to pool data or infrastructure can still pool failures.

Composition adds two findings. Checking only an immediate delegator contained 2 of 10 hostile chain classes; full-chain checks contained all 10. Model-assisted review completed five times the valid work of the unaided arm, but a dependent assistant repeated more merit errors than an independent one. Throughput therefore changes the authority ceiling; it does not erase it. The contract audit also exposed prose that lacked executable test bindings.

For AI for Learning, an education pack governs an institutional workflow. For Learning for AI, the architecture teaches system literacy: trace data, bound delegation, locate independent enforcement, calculate capacity, and reconstruct accountability. The same exercise transfers to a hospital, company, regulator, or public service. No learning gain is claimed; none has been measured.

Open questions include compromised hosts and signers, certified hardware isolation, named-model attack rates, reviewer accuracy, privacy, fairness, accessibility, cost, energy, cross-border use, and independent audit. Containers on one host are logical separation, not independent administrative trust.

## Conclusion

Trust by Construction changes AI governance from a model question to a system question. Its constitutional layer separates intelligence from authority, execution, evidence, and recovery. A model may reason, but cannot change a protected record, grant itself access, approve its proposal, rewrite evidence, or hide an uncertain outcome.

Five directions follow: govern systems, not models; require a seven-field contract for each consequential capability; verify control of keys, data movement, model replacement, evidence, recovery, and exit; build sectors as domain packs over shared invariants; and exchange failure cases without pooling sensitive data.

This serves policy and engineering. A policymaker can demand named powers, owners, limits, fallback, and proof. An engineer can map each duty to an enforced interface and rerun properties after changing FastAPI, Redis, Kafka, Spark, Iceberg, a model, or a hardware boundary. Education supplies the system literacy to inspect both.

The claim is bounded. A governed agent can enforce an unjust rule faster; this makes action attributable and contestable but not fair. The prototype does not prove production security or compliance. It provides a base pattern and open tests for institutions to extend with domain law, public voice, hardware assurance, operations, and independent evidence. This is the work ahead.

## References

Autio, C., et al. (2024). Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile. NIST AI 600-1. https://doi.org/10.6028/NIST.AI.600-1

ISO/IEC. (2023). ISO/IEC 42001:2023 - Information technology, Artificial intelligence, Management system. https://www.iso.org/standard/81230.html

Miao, F., and Cukurova, M. (2024). AI competency framework for teachers. UNESCO. https://unesdoc.unesco.org/ark:/48223/pf0000391104

OWASP GenAI Security Project. (2025). OWASP Top 10 for Agentic Applications 2026. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

Parasuraman, R., and Manzey, D. (2010). Complacency and bias in human use of automation: an attentional integration. Human Factors, 52(3), 381-410. https://doi.org/10.1177/0018720810376055

Rose, S., Borchert, O., Mitchell, S., and Connelly, S. (2020). Zero Trust Architecture. NIST SP 800-207. https://doi.org/10.6028/NIST.SP.800-207

United Nations. (2024). Global Digital Compact. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact
