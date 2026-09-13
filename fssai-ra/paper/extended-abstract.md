# Trust by Construction: A Cross-Sector Reference Architecture for Governed Agentic AI

**Submission:** Extended abstract, UNU Macau AI Conference 2026 — *AI × Education: AI for Learning, Learning for AI*, 25–26 November 2026, Macau SAR, China.
**Proposed panel:** Agentic AI in the Loop — From Autonomous Tools to Shared Capacity.
**Keywords:** agentic AI; system literacy; secure data governance; institutional sovereignty; reference architecture; fail-secure systems; verifiable governance; digital public goods.
**Reference implementation:** Apache-2.0, `https://github.com/genaiworks/fssai-ra`, release `v1.0.0` for the baseline figures; the oversight, composition, cross-domain, governed-disclosure, threat-catalogue, and adversary-corpus results below are current-source and published separately.

**Thesis I will argue on the panel: intelligence is untrusted; power and data are mediated.** The model is no longer the right unit of AI governance; the governed object is the whole system that acquires data, proposes, delegates, authorizes, acts, records, and recovers. Every future AI system should rest on three commitments. *Untrusted intelligence:* treat each model as capable, persuasive, and possibly misaligned or manipulated. *Mediated power:* every effect and every flow of protected data passes a mediator the model cannot bypass, influence, or impersonate. *Evidenced trust:* every mediation is contracted, tested, and evidenced where it is relied on. As capability grows, verifying intentions gets harder; verifying boundaries stays tractable. The thesis is falsifiable: one configuration in which model output alone causes a governed effect or disclosure refutes it.

## 1. The model is not the system

A company releases a confidential dataset; a hospital shares a record; a university corrects a transcript; a public body decides support. Different laws apply, yet each must answer the same questions: **what was allowed, who or what had authority, which evidence was used, what actually happened, and how can the outcome be challenged or reversed?** A safe model cannot answer those questions on behalf of an unsafe system.

Two rules anchor the design. **A model may propose an action; it cannot manufacture the authority to execute it. A model may request information; it cannot manufacture the entitlement to see it, or launder what it saw.** Both are enforced outside the model, by components that alone hold write and record credentials and recheck purpose, consent, and revocation at every use. Authority only narrows as agents delegate; restriction only accumulates as data flows. Trustworthiness becomes an institutional capability that can be specified and tested, not a property bought with a model, region, or certificate.

## 2. Trust by Construction as a reference pattern

The contribution is a sector-neutral reference architecture with a “narrow waist”: an executable control contract between policy and implementation. For each consequential capability, its **seven fields** name the protected asset, permitted operation, independent enforcement point, accountable owner, failure test, evidence artifact, and failure response. If an institution cannot fill every field, it has found an unresolved governance decision rather than a capability ready for automation.

Around that contract, the pattern separates seven planes. The **boundary** plane authenticates ingress and egress, quarantines untrusted input, and exposes a no-read-back seam certified hardware can replace. The **governed data** plane keeps stable identifiers, replayable events, and versioned snapshots. The **intelligence** plane holds replaceable models but no write authority. The **authority** plane issues purpose-, time-, and holder-bound grants and approvals. The **execution** plane rechecks policy, identity, version, approval, and replay before using the write credential. The **evidence** plane binds intent to outcome. The **resilience** plane fails securely, reconciles, revokes, and routes work to fallback.

No mechanism here is new. Reference monitors and least privilege [12], lattice information flow [13], and separation of duties [14] precede AI; capability and flow control for language-model agents [15, 16] and AI control under intentional subversion [17] are recent. The contribution is their composition with institutional purpose, consent, review capacity, and evidence, and a method that measures itself.

These are logical responsibilities, not products. The implementation maps them to FastAPI, PostgreSQL or Redis, Kafka, PySpark, Iceberg, object storage, local-model adapters, signing, and a software one-way seam. Adopters may replace any of them but must rerun conformance evidence, so the reference stack cannot become a vendor dependency disguised as sovereignty.

## 3. Secure data is governed through its full journey

Encryption, de-identification, isolation, and certification are necessary, yet none refuses a prohibited read. Most harm in a corporate copilot or clinical-record assistant changes no state: it reads, summarises, and sends. Role-based retrieval permits one role for treatment, research, and model training, and summaries leave unlabelled.

The second rule is enforced by a **context gate** that alone holds the record-store credential. A signed grant binds holder, purpose, subjects, fields, classes, and expiry. Consent and revocation are checked at every read, and each class reaches only model endpoints in declared zones. Every output carries the join of everything its session received: restriction only accumulates as data flows, just as authority only narrows as it is delegated. Only an exact-output declassification by an independent declared role lowers a label. Emergency access is bounded and opens a review obligation, and the disclosure log holds digests, never values.

Across corporate, healthcare, financial, and government packs, **98 of 98 hostile data flows were contained**. Conventional access control, with signed class-cleared grants and an output check on the model's claimed label, **contained 32**. **All 14 checks were load-bearing**, **22,220 read and release configurations showed zero violations**, and 11 of 11 legitimate flows completed. Single-step enumeration missed one defect: stateful testing, **800 sequences and 32,000 operations** against an independent reference model, found that a summary drafted before consent was withdrawn could still be released. Release now rechecks consent, revocation, and expiry; the sequences agree.

## 4. Authority must remain bounded under composition

An approval binds to an exact proposal digest covering target, transition, evidence and resource versions, requester, role, audience, and expiry; any change needs new authorization. The executor, not the agent, reads the review class from the profile.

Agentic systems make composition the next fault line. **No principal may pass on authority it does not itself hold.** Nine invariants, from attenuation and rootedness to holder binding, are all load-bearing; **768 enumerated chain shapes and zero violations** were observed. Validating each hop against its immediate caller — a plausible design — **contains 2 of 10 risk classes where verifying the chain contains 10**. Local correctness at every service is not chain correctness.

Human review works only while a reviewer is deciding, so the pattern declares capacity, a deliberation floor, escalation, and fallback. With the reference assumptions, **a roster of 11 reviewers sustains 2,640 consequential actions per day**. In a queue trial, **Without load control, 4 such merit failures execute. With it, 0 do, and 32 actions defer to manual review**. A sweep found that across 25 parameter combinations the control was load-bearing in 16 of the 20 where harm was possible, harm reached zero in 16, and repairing contradictory defaults **drove the false-positive cost to 0**.

A model-assisted reviewer needs a different model, evidence path, and adversarial posture: the trial observed **5 merit failures with a dependent assistant, 1 with an independent one**.

## 5. Domain packs make the architecture transferable

The kernel is incomplete without a domain pack declaring purpose, data classes, obligations, owners, transitions, disclosure policy, fallback, and limits. Policy leaders author its meaning; engineers bind it to enforcement. Packs for healthcare, corporate data, consumer finance, public benefits, and education share one kernel; education is one case, not the universal one.

One successful example cannot establish transfer. **6 independently reported domain packs cover 55,440 bounded configurations, 180 of 180 hostile scenarios contained, 58 of 58 benign tasks completed, and zero unauthorized mutations.** The academic-record pack independently reports **4,800 configurations with zero violations, 30 of 30 scenarios contained, 9 of 9 benign tasks, 26 conformance checks**. These synthetic packs demonstrate reuse of the authority mechanism, not compliance, privacy, fairness, educational quality, or clinical safety.

## 6. Evidence must test the architecture, not repeat its promises

Assurance asks distinct questions: property and bounded checks compare real enforcement with independent predicates, ablation asks whether harm returns, and conformance reruns properties on substituted backends. Applying the contract to itself found that **eighteen of twenty-eight were prose bound to nothing.** Coverage is now published as machine-verified, organizationally attested, or unverified, **reading 41, 3, 0 today**. A named test that does not exist fails the build.

Against the reference profile, **30 of 30 adversarial scenarios contained**, **240 configurations with zero violations**, **11 distinct denial controls**, **8 of 8 ablated controls restored their harm when removed**, and **26 conformance checks passing on 2 backend profiles**. A **32-caller race produced 1 mutation and 1 receipt**. The repository runs **699 deterministic tests** offline. Utility is reported beside containment: **6 of 6 benign tasks completed, false-denial rate 0.0**. A system that denies everything scores perfectly on containment and remains useless.

Against an unguarded agent, a prompt with an allowlist, and this architecture, the same attacks delivered 28, 8, and 0 harmful actions.

The design assumes the model may be misaligned. A catalogue of 33 failure classes, including specification gaming, deceptive risk reporting, oversight flooding, collusion, laundering, injection, poisoning, and compromised signers, records **18 contained, 10 bounded, and 5 residual**, each bound to evidence checked to exist. Six falsifiers then try to refute the thesis across every pack. Their first run did: five contract bindings named functions that did not exist. Repaired, **102,933 bounded attempts found zero counterexamples**, and removing one mediator check produces them. Zero is not proof. Containment rests on enforcement code, not model behaviour; merit errors within granted authority, evaluation-aware models, covert channels, re-identification, and compromised administrators remain open.

Because the builders wrote every attack, an open corpus accepts YAML cases without records or contributor code. The evaluator publishes provenance; today that number is **0**.

## 7. Education is the dissemination mechanism, not the boundary

The conference theme matters because this architecture requires **system literacy**: distinguishing proposals from powers and requests from entitlements, locating the mediator, and reconstructing an outcome and its redress. A two-hour offline lab has participants break a boundary, remove a control, watch harm return, and transfer the contract to their own domain. No learning gain is claimed; none has been measured.

For *AI for Learning*, an education domain pack governs an institutional workflow. For *Learning for AI*, the contribution is a reusable method for learning how AI systems acquire and exercise power. The repository is offered as a digital public good: any institution can inspect the same rules, replace the domain pack, and publish its own evidence rather than inherit ours.

## 8. Limits and research agenda

The results are fixture observations in declared environments: **not security probabilities**, certification, or evidence of production readiness. **Not yet evidenced:** resistance to a compromised host administrator or signing authority; de-identification quality, since redaction is not anonymity; a certified hardware diode deployment; injection rates for a named model; real reviewer accuracy or proposer-assistant error correlation; any real multi-agent deployment; privacy, fairness, accessibility, cost, energy, cross-jurisdiction interoperability, and independent audit. Containers on one host provide **logical separation, not independent administrative trust**. The design relocates trust rather than removing it: gates, executor, signing keys, evidence store, identity provider, and administrators form a declared trusted base whose compromise defeats both rules.

Nor does this architecture decide whether an institution's rule is legitimate. A perfectly governed agent can enforce an unjust policy faster. It makes the action attributable and contestable; it **does not make a rule fair**. Future work must add participatory rulemaking, independent red teaming, and pilots.

## 9. Direction for future AI systems

1. **Build on the Mediation Thesis.** Treat intelligence as untrusted, mediate every effect and data flow, and publish the attempts to refute it.
2. **Govern reads as strictly as writes.** Bind every context to purpose, subject, field, consent, and location, and label every output by what produced it.
3. **Make every consequential capability contractable.** No capability should ship without the seven fields, a test bound to something that runs, a recovery owner, and a conformance claim by class.
4. **Treat sovereignty as a demonstrable lifecycle capability.** Measure control of keys, data movement, model replacement, evidence, recovery, and exit, not hosting location.
5. **Publish authority and oversight ceilings before automation roadmaps.** Delegation depth and review capacity are safety limits, not staffing footnotes.
6. **Build sectors as domain packs over a shared kernel.** Preserve the invariants, replace the institutional meaning, and regenerate the evidence.
7. **Trade failure cases, not sensitive data.**

An AI system should be governed less like an application and more like an institution: with a constitution, separated powers, a memory it cannot rewrite, and a safe way to stop. That is the proposed direction — not a claim that the current prototype has completed it.

*Full method and results for assisted review and delegated authority are in the composition supplement; normative requirements are in `docs/SPECIFICATION.md` and positioning in `docs/RELATED_WORK.md`.*

## References

[1] Rose, S., Borchert, O., Mitchell, S., and Connelly, S. (2020). *Zero Trust Architecture*. NIST SP 800-207. https://doi.org/10.6028/NIST.SP.800-207

[2] Autio, C., et al. (2024). *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*. NIST AI 600-1. https://doi.org/10.6028/NIST.AI.600-1

[3] OWASP GenAI Security Project (2025). *OWASP Top 10 for Agentic Applications 2026*. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

[4] OWASP GenAI Security Project (2026). *Agent Control Standard*. https://genai.owasp.org/resource/agent-control-standard-acs/

[5] MITRE (2024). *ATLAS: Adversarial Threat Landscape for Artificial-Intelligence Systems*. https://atlas.mitre.org/

[6] ISO/IEC (2023). *ISO/IEC 42001:2023 — Information technology, Artificial intelligence, Management system*. https://www.iso.org/standard/81230.html

[7] Miao, F., and Cukurova, M. (2024). *AI competency framework for teachers*. UNESCO. https://unesdoc.unesco.org/ark:/48223/pf0000391104

[8] United Nations (2024). *Global Digital Compact*. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact

[9] Parasuraman, R., and Manzey, D. (2010). Complacency and bias in human use of automation: an attentional integration. *Human Factors*, 52(3), 381–410. https://doi.org/10.1177/0018720810376055

[10] Apache Software Foundation. *Apache Kafka Documentation: Design*. https://kafka.apache.org/documentation/#design

[11] Apache Software Foundation. *Apache Iceberg Documentation*. https://iceberg.apache.org/docs/latest/

[12] Saltzer, J. H., and Schroeder, M. D. (1975). The protection of information in computer systems. *Proceedings of the IEEE*, 63(9), 1278–1308. https://doi.org/10.1109/PROC.1975.9939

[13] Denning, D. E. (1976). A lattice model of secure information flow. *Communications of the ACM*, 19(5), 236–243. https://doi.org/10.1145/360051.360056

[14] Clark, D. D., and Wilson, D. R. (1987). A comparison of commercial and military computer security policies. *IEEE Symposium on Security and Privacy*, 184–194.

[15] Debenedetti, E., et al. (2025). *Defeating Prompt Injections by Design*. https://arxiv.org/abs/2503.18813

[16] Costa, M., et al. (2025). *Securing AI Agents with Information-Flow Control*. https://arxiv.org/abs/2505.23643

[17] Greenblatt, R., Shlegeris, B., Sachan, K., and Roger, F. (2024). AI control: Improving safety despite intentional subversion. *Proceedings of the 41st International Conference on Machine Learning*. https://arxiv.org/abs/2312.06942
