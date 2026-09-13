# Trust by Construction: A Cross-Sector Reference Architecture for Governed Agentic AI

**Submission:** Extended abstract, UNU Macau AI Conference 2026 — *AI × Education: AI for Learning, Learning for AI*, 25–26 November 2026, Macau SAR, China.
**Proposed panel:** Agentic AI in the Loop — From Autonomous Tools to Shared Capacity.
**Keywords:** agentic AI; system literacy; secure data governance; institutional sovereignty; reference architecture; fail-secure systems; verifiable governance; digital public goods.
**Reference implementation:** Apache-2.0, `https://github.com/genaiworks/fssai-ra`, release `v1.0.0` for the baseline figures; the oversight, composition, cross-domain, governed-disclosure, threat-catalogue, and adversary-corpus results below are current-source and published separately.

**Position I will argue on the panel.** The model is no longer the right unit of AI governance. The governed object is the whole system that acquires sensitive data, produces a proposal, delegates capability, authorizes an action, changes the world, records what happened, and recovers when the outcome is uncertain. Future AI infrastructure therefore needs a constitutional layer: the intelligence may change, but no model should be able to create its own powers, see beyond its entitlement, rewrite its own evidence, or silently cross the institution's data boundary. That layer must hold when the model is not aligned. As capability grows, verifying a model's intentions gets harder; verifying its boundaries stays tractable.

## 1. The model is not the system

A company authorizes release of a confidential dataset; a hospital permits secondary use of a medical record; a university changes an academic record; a public body determines access to support. Different sectors and laws sit above them, yet each system must answer the same questions: **what was allowed, who or what had authority, which evidence was used, what actually happened, and how can the outcome be challenged or reversed?** A safe model cannot answer those questions on behalf of an unsafe system.

Two rules anchor the design. **A model may propose an action; it cannot manufacture the authority to execute it. A model may request information; it cannot manufacture the entitlement to see it, or launder what it saw.** This reframes trustworthy AI from a property purchased with a model, cloud region, private endpoint, or certificate into an institutional capability that can be specified and tested. Sovereignty is a lifecycle property of the system.

## 2. Trust by Construction as a reference pattern

The contribution is a sector-neutral reference architecture with a “narrow waist”: an executable control contract between policy and implementation. For each consequential capability, its **seven fields** name the protected asset, permitted operation, independent enforcement point, accountable owner, failure test, evidence artifact, and failure response. If an institution cannot fill every field, it has found an unresolved governance decision rather than a capability ready for automation.

Around that contract, the pattern separates seven planes. The **boundary** plane authenticates ingress and egress, quarantines untrusted input, and exposes a no-read-back seam certified hardware can replace. The **governed data** plane keeps stable identifiers, replayable events, and versioned snapshots. The **intelligence** plane holds replaceable models but no write authority. The **authority** plane issues purpose-, time-, and holder-bound grants and approvals. The **execution** plane rechecks policy, identity, version, approval, and replay before using the write credential. The **evidence** plane binds intent to outcome. The **resilience** plane fails securely, reconciles, revokes, and routes work to fallback.

These are logical responsibilities, not products. The implementation maps them to FastAPI, PostgreSQL or Redis, Kafka, PySpark, Iceberg, object storage, local-model adapters, signing, and a software one-way seam. Adopters may replace any of them but must rerun conformance evidence, so the reference stack cannot become a vendor dependency disguised as sovereignty.

## 3. Secure data is governed through its full journey

Encryption, de-identification, network isolation, and certification are necessary, yet none refuses a prohibited read. Most harm in a corporate copilot or clinical-record assistant involves no state change: it reads, summarises, and sends. Role-based retrieval permits the same role for treatment, research, and model training, and a summary of restricted data leaves as unlabelled text.

The second rule is enforced by a **context gate** that alone holds the record-store credential. A signed grant binds holder, purpose, subjects, fields, classes, and expiry. Consent and revocation are checked at every read, and each class reaches only model endpoints in declared zones. Every output carries the join of everything its session received: restriction only accumulates as data flows, just as authority only narrows as it is delegated. Only an exact-output declassification by an independent declared role lowers a label. Emergency access is bounded and opens a review obligation, and the disclosure log holds digests, never values.

Across the corporate and healthcare packs, **44 of 44 hostile data flows were contained**. Conventional access control, with signed class-cleared grants and an output check on the model's claimed label, **contained 16**. **All 13 checks were load-bearing**, **6,900 read and release configurations showed zero violations**, and 5 of 5 legitimate flows completed. Writing this policy exposed a healthcare break-glass review state that no transition could reach.

## 4. Authority must remain bounded under composition

An approval binds to an exact proposal digest: operation, target, before-and-after state, evidence version, requester, resource version, reviewer role, audience, and expiry. Any change requires new authorization. The executor, not the agent, reads the required review class from the deployment profile and performs the final check.

Agentic systems make composition the next fault line. **No principal may pass on authority it does not itself hold.** Nine invariants cover attenuation, rooted authority, depth, time, acyclicity, provenance, non-delegable consequences, holder binding, and beneficiary scope. All are load-bearing; **768 enumerated chain shapes and zero violations** were observed. Validating each hop against its immediate caller — a plausible design — **contains 2 of 10 risk classes where verifying the chain contains 10**. Local correctness at every service is not chain correctness.

Human review is one authority source, not a magic boundary. It works only while a reviewer is actually deciding. The pattern therefore declares review capacity, a deliberation floor, escalation under sustained load, and manual fallback. With the reference assumptions, **a roster of 11 reviewers sustains 2,640 consequential actions per day**. In a queue trial, **Without load control, 4 such merit failures execute. With it, 0 do, and 32 actions defer to manual review**. A sweep found that across 25 parameter combinations the control was load-bearing in 16 of the 20 where harm was possible, harm reached zero in 16, and repairing contradictory defaults **drove the false-positive cost to 0**.

When the reviewer receives a model assistant, throughput rises but independence becomes an architectural requirement: a different model, a different evidence path, and an adversarial posture. The trial observed **5 merit failures with a dependent assistant, 1 with an independent one**. Assistance changes the ceiling; it does not abolish one.

## 5. Domain packs make the architecture transferable

The kernel is intentionally incomplete without a domain pack. A pack declares purpose, basis, data classes, obligations, prohibited uses, lifecycle rules, owners, transitions, a disclosure policy, fallback, tests, and limits. Policy leaders author its meaning; engineers bind it to enforcement. The healthcare pack excludes diagnosis; the corporate pack governs release and legal hold; education is one case, not the universal one.

One successful example cannot establish transfer. **4 independently reported domain packs cover 33,600 bounded configurations, 120 of 120 hostile scenarios contained, 37 of 37 benign tasks completed, and zero unauthorized mutations.** The academic-record pack independently reports **4,800 configurations with zero violations, 30 of 30 scenarios contained, 9 of 9 benign tasks, 26 conformance checks**. Its first run exposed a declared reviewer role that enforcement ignored on a routine transition. These synthetic packs demonstrate reuse of the authority mechanism, not compliance, privacy, fairness, educational quality, or clinical safety.

## 6. Evidence must test the architecture, not repeat its promises

The assurance strategy asks four different questions. Property tests compare generated calls with a predicate independent of the implementation. Bounded checking enumerates the declared authority space and runs the real enforcement code. Ablation removes controls to see whether harm returns. Conformance runs the same properties against substituted backends. Applying the contract to itself found that **eighteen of twenty-eight were prose bound to nothing.** Coverage is now published as machine-verified, organizationally attested, or unverified, **reading 41, 3, 0 today**. A named test that does not exist fails the build.

Against the reference profile, **30 of 30 adversarial scenarios contained**, **240 configurations with zero violations**, **11 distinct denial controls**, **8 of 8 ablated controls restored their harm when removed**, and **26 conformance checks passing on 2 backend profiles**. A **32-caller race produced 1 mutation and 1 receipt**. The repository runs **648 deterministic tests** offline. Utility is reported beside containment: **6 of 6 benign tasks completed, false-denial rate 0.0**. A system that denies everything scores perfectly on containment and remains useless.

Against an unguarded agent, a prompt plus per-agent allowlist, and the complete architecture, the same attacks delivered 28, 8, and 0 harmful actions. Prompts and allowlists are real controls; an enforcement point independent of the model must complete them.

The design assumes the model may be misaligned. A catalogue of 32 failure classes, including specification gaming, deceptive risk reporting, oversight flooding, collusion, laundering, injection, poisoning, and compromised signers, records **17 contained, 10 bounded, and 5 residual**, each bound to evidence checked to exist. Containment rests on enforcement code, not model behaviour; merit errors within granted authority, evaluation-aware models, covert channels, re-identification, and compromised administrators remain open.

Because the builders authored every attack, an open adversary corpus accepts seven-field YAML cases without records, deployment details, or contributor code. The evaluator publishes provenance; today that number is **0**.

## 7. Education is the dissemination mechanism, not the boundary

The conference theme matters because this architecture requires a shift from model literacy to **system literacy**: tracing provenance, distinguishing proposals from powers and requests from entitlements, locating the enforcement point, calculating oversight capacity, and reconstructing an outcome and its redress path. A two-hour offline lab asks participants to violate a boundary, observe refusal, remove the control, watch harm return, and transfer the contract to their own domain. No learning gain is claimed; none has been measured.

For *AI for Learning*, an education domain pack governs an institutional workflow. For *Learning for AI*, the contribution is a reusable method for learning how AI systems acquire and exercise power. The repository is offered as a digital public good: any institution can inspect the same rules, replace the domain pack, and publish its own evidence rather than inherit ours.

## 8. Limits and research agenda

The results are fixture observations in declared environments: **not security probabilities**, certification, or evidence of production readiness. **Not yet evidenced:** resistance to a compromised host administrator or signing authority; de-identification quality, since redaction is not anonymity; a certified hardware diode deployment; injection rates for a named model; real reviewer accuracy or proposer-assistant error correlation; any real multi-agent deployment; privacy, fairness, accessibility, cost, energy, cross-jurisdiction interoperability, and independent audit. Containers on one host provide **logical separation, not independent administrative trust**.

Nor does this architecture decide whether an institution's rule is legitimate. A perfectly governed agent can enforce an unjust policy faster. It makes the action attributable and contestable; it **does not make a rule fair**. Future work must pair the technical constitution with participatory rulemaking, domain validation, independent red teaming, operational pilots, and evidence about affected people.

## 9. Direction for future AI systems

1. **Govern systems, not models, and do not rest safety on alignment.** Require a constitutional layer separating intelligence from authority, disclosure, execution, evidence, and recovery.
2. **Govern reads as strictly as writes.** Bind every context to purpose, subject, field, consent, and location, and label every output by what produced it.
3. **Make every consequential capability contractable.** No capability should ship without the seven fields, a test bound to something that runs, and a recovery owner.
4. **Treat sovereignty as a demonstrable lifecycle capability.** Measure control of access, keys, data movement, model replacement, evidence, revocation, recovery, and exit — not merely hosting location.
5. **Publish authority and oversight ceilings before automation roadmaps.** Delegation depth and review capacity are safety limits, not staffing footnotes.
6. **Build sectors as domain packs over a shared kernel.** Preserve the invariants, replace the institutional meaning, and regenerate the evidence.
7. **Trade failure cases, not sensitive data.** A shared adversary corpus can build global capacity without centralizing the records that require protection.

An AI system should be governed less like an application and more like an institution: with a constitution, separated powers, a memory it cannot rewrite, and a safe way to stop. That is the proposed direction — not a claim that the current prototype has completed it.

*Full method and results for assisted review and delegated authority are in the composition supplement.*

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
