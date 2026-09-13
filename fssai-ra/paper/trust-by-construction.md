# Trust by Construction: A Cross-Sector Reference Architecture for Governed Agentic AI

**Submission:** Full paper, UNU Macau AI Conference 2026 — *AI × Education: AI for Learning, Learning for AI*, 25–26 November 2026, Macau SAR, China.
**Proposed panel:** Agentic AI in the Loop — From Autonomous Tools to Shared Capacity.
**Keywords:** agentic AI; reference architecture; secure data governance; privacy by construction; institutional sovereignty; fail-secure systems; system literacy; digital public goods.
**Reference implementation:** Apache-2.0, https://github.com/genaiworks/fssai-ra, release `v1.0.0`; every figure in this paper regenerates offline from the repository with `make results`.

## Abstract

AI governance still centres on models, yet harm arises in systems: an agent reads a record it should not see, sends a summary it should not release, or turns a plausible proposal into an irreversible action. This paper presents Trust by Construction, a sector-neutral reference architecture and development method for agentic AI, built on one falsifiable thesis: **intelligence is untrusted; power and data are mediated.** Two constitutional rules follow. A model may propose an action, but it cannot manufacture the authority to execute it. A model may request information, but it cannot manufacture the entitlement to see it, or launder what it saw.

The architecture enforces both rules outside the model through a seven-field control contract, seven logical planes, and two mediators that alone hold write credentials, record access, and data keys. A privacy pipeline replaces personal data with vault tokens before any model sees it, encrypts records under per-subject keys, routes restricted work to attested local models, and restores identity only for entitled recipients. A seven-stage lifecycle shows teams in any sector how to frame, contract, bind, falsify, promote, and operate a new AI capability. Across six domain packs spanning education, corporate data, healthcare, consumer finance, and public benefits, the reference implementation contained 180 of 180 hostile scenarios and 106 of 106 hostile data flows while completing every legitimate task, and 104,997 bounded attempts found no counterexample to the thesis.

## 1. Introduction

A company releases a confidential dataset; a hospital shares a record; a university corrects a transcript; a public body decides support. Different laws apply, yet each institution must answer the same questions: **what was allowed, who or what had authority, which evidence was used, what actually happened, and how can the outcome be challenged or reversed?** A safe model cannot answer those questions on behalf of an unsafe system.

Model-centred governance faces four structural problems that grow with capability. First, a model's intentions cannot be verified, and more capable models are more persuasive and harder to evaluate. Second, agents compose: an assistant delegates to a tool that calls another agent, and local correctness at every hop does not make a chain correct. Third, most harm in a corporate copilot or clinical assistant changes no state at all; it reads, summarises, and sends. Fourth, human review is a finite resource, and an approval given faster than a reviewer can think is a signature, not oversight.

Trust by Construction answers all four with one thesis and three commitments. *Untrusted intelligence:* treat every model as capable, persuasive, and possibly misaligned or manipulated. *Mediated power:* every effect and every flow of protected data passes a mediator the model cannot bypass, influence, or impersonate. *Evidenced trust:* every mediation is contracted, tested, and evidenced where it is relied on. As capability grows, verifying intentions gets harder; verifying boundaries stays tractable. The thesis is falsifiable: one configuration in which model output alone causes a governed effect or disclosure refutes it.

The paper makes five contributions:

1. **A reference architecture** that separates seven planes around an executable control contract and two mediators (Section 3).
2. **A governed request path in ten steps**, including a privacy pipeline of tokenization, envelope encryption, sensitivity-aware routing, and model attestation (Section 4).
3. **A transfer method**: domain packs that carry institutional meaning over one shared kernel, illustrated across five sectors (Section 5), and a seven-stage lifecycle for building any future AI capability (Section 6).
4. **Evidence that tests the architecture instead of restating it**: comparisons with conventional controls, ablation of every control, bounded model checking, stateful testing, and falsifiers, all regenerable offline (Section 7).
5. **A teaching method for system literacy**, so that policymakers, engineers, and learners can inspect the same boundaries (Section 8).

## 2. Background and related work

The architecture deliberately inherits rather than invents its mechanisms. The reference monitor and the principles of least privilege, complete mediation, and fail-safe defaults [12] place every access behind a mediator. Lattice information flow [13] lets restriction accumulate as data moves. Well-formed transactions and separation of duties [14] make integrity a property of the process, not of the actor. Zero trust architecture [1] removes implicit trust from network location.

Recent work applies these ideas to language-model agents. CaMeL separates control flow from untrusted data and attaches capabilities to values [15]; FIDES tracks confidentiality and integrity labels through an agent's planner [16]; AI control designs protocols that remain safe when the model actively tries to subvert them [17]. Governance frameworks supply the vocabulary of risk and management: the NIST AI RMF generative AI profile [2], ISO/IEC 42001 [6], the OWASP agentic top ten [3] and agent control standard [4], and MITRE ATLAS [5]. Data-protection law adds purpose limitation, pseudonymisation, and the right to erasure [18], and the EU AI Act adds obligations for high-risk systems [19].

What remains missing is an executable architecture that institutions can adopt across sectors: one that governs actions, reads, releases, delegation, review capacity, and evidence together, protects personal data before any model sees it, and carries a method for transferring all of it to a new domain. Standards say what must be achieved; agent-security research protects a single agent's control flow. Trust by Construction composes both with institutional purpose, consent, review capacity, and evidence, and measures itself.

## 3. The architecture

### 3.1 Two constitutional rules

**A model may propose an action; it cannot manufacture the authority to execute it. A model may request information; it cannot manufacture the entitlement to see it, or launder what it saw.** Both rules are enforced by components that alone hold write credentials, record access, and data keys, and that recheck purpose, consent, and revocation at every use. Authority only narrows as agents delegate; restriction only accumulates as data flows. Trustworthiness becomes an institutional capability that can be specified and tested, not a property bought with a model, a region, or a certificate.

### 3.2 The control contract

The narrow waist of the architecture is an executable contract between policy and implementation. For each consequential capability, its **seven fields** name the protected asset, permitted operation, independent enforcement point, accountable owner, failure test, evidence artifact, and failure response (Table 1). If an institution cannot fill every field, it has found an unresolved governance decision rather than a capability ready for automation. The contract is machine-readable, and each requirement is bound to a check that is itself checked to exist.

**Table 1.** The seven fields of the control contract, with one capability from the healthcare domain pack.

| Field | Question it answers | Example: authorize treatment access |
|---|---|---|
| Protected asset | What could be harmed? | A patient's treatment record |
| Permitted operation | Exactly what may happen? | `identity_verified` → `treatment_access_active`, nothing else |
| Enforcement point | Which component outside the model refuses? | The executor, sole holder of the write credential |
| Accountable owner | Who answers for the outcome? | Healthcare privacy officer |
| Failure test | Which test proves the refusal? | Wrong-patient, purpose-switch, and self-approval scenarios |
| Evidence artifact | What proves what happened? | Receipt bound to the exact proposal digest |
| Failure response | What happens when something fails? | Revoke, reconcile, and route to the manual fallback |

### 3.3 Seven planes and two mediators

Around the contract, the pattern separates seven planes (Fig. 1). The **boundary** plane authenticates ingress and egress, quarantines untrusted input, and exposes a no-read-back seam that certified one-way hardware can replace. The **governed data** plane keeps stable identifiers, replayable events, and versioned snapshots, encrypted at rest under per-subject keys. The **intelligence** plane holds a semantic router, replaceable attested models, agents, and retrieval, but no credential or key. The **authority** plane issues purpose-, time-, and holder-bound grants and approvals, holds model manifests, and provides key custody. The **execution** plane rechecks policy, identity, version, approval, and replay before using the write credential. The **evidence** plane binds intent to outcome. The **resilience** plane fails securely, reconciles uncertain effects, revokes, and routes work to fallback.

Two components are mediators in the reference-monitor sense. The **executor** enforces the first rule; the **context gate** enforces the second. Together with the contract, signing keys, key custody, evidence store, and identity provider, they form a small, declared trusted base. This is the architecture's central economy: assurance effort concentrates on a handful of named components rather than on every model an institution will ever adopt.

Planes are logical responsibilities, not products. The reference stack maps them to FastAPI, PostgreSQL or Redis, Kafka, PySpark, Iceberg, object storage, Ollama-served local models, signing, and a software one-way seam. Adopters may replace any component, but a replacement inherits no assurance until the same conformance and falsification suites pass on it, so the reference stack cannot become a vendor dependency disguised as sovereignty.

## 4. One governed request in ten steps

A single request passes through ten steps (Fig. 2). They run identically in every domain; only the domain pack changes what each step checks.

**Steps 1–2: admit and protect.** The boundary authenticates every caller and source and wraps retrieved content as untrusted data, so an injected instruction is text to be reasoned about, never a command. The privacy pipeline then detects personal data and replaces it with vault tokens. Tokens are keyed, scoped to a session, and never reproduce the identifier they stand for; the token map lives with the gate. Sensitive fields are stored under envelope encryption: each subject has a data key, wrapped by a key-encryption key for its data class and held by key custody [10], and each ciphertext is bound to its subject and field so it cannot be moved to another record. Tokenization is chosen over redaction because a model needs to reason about *which* patient or applicant a fact concerns without learning *who* they are.

**Steps 3–4: route and entitle.** A semantic router classifies each request's intent and the sensitivity of the data classes it needs, and chooses the cheapest attested model whose processing zone may handle every class; restricted classes default to a local model on institutional hardware. Routing is advisory. The context gate then decides: it verifies a signed grant binding holder, purpose, subjects, fields, classes, and expiry; checks live consent and revocation; confirms that the chosen endpoint's zone may process every class; and confirms that the model presents a registered, signed manifest whose artifact digest matches. Only then does the gate read the record source and decrypt the minimum necessary fields. A subverted router can therefore choose a worse model, never a more exposed one.

**Steps 5–6: reason and authorize.** The model drafts or proposes over tokens and labelled context. It holds no key, no token map, and no write credential, so its output is a proposal, never a power. An approval binds to the exact proposal digest covering target, transition, evidence and resource versions, requester, role, audience, and expiry; any change needs new authorization. No principal may pass on authority it does not itself hold, so delegation chains only attenuate. Human review is declared as capacity with a deliberation floor, escalation, and fallback, so demand beyond capacity defers instead of turning approval into ritual.

**Steps 7–8: execute and release.** The executor rechecks policy, identity, version, approval, and replay, then makes one write and issues one receipt; a retry returns the same receipt or enters reconciliation. Every output carries the join of the labels of everything its session received, so a model cannot declassify its own summary. At release the gate rechecks consent, revocation, and expiry, requires the recipient to dominate the output's label, and restores real values in place of tokens only for a recipient entitled to that subject. Lowering a label requires an exact-output declassification by an independent declared role.

**Steps 9–10: record and recover.** The evidence plane binds intent to outcome in an append-only chain that stores digests, never protected values. Resilience revokes grants, reconciles uncertain effects, and routes work to a manual fallback. Erasure is implemented by destroying a subject's data key, a cryptographic erase [11] that renders every stored copy unreadable, including snapshots and backups.

## 5. One kernel, many domains

The kernel is complete only with a **domain pack**: a declarative file that supplies purposes, data classes and their processing zones, recipients, transitions and their approvers, declassification rules, emergency access, and fallback. Policy leaders author its meaning; engineers bind it to enforcement. A new sector replaces the pack, not the kernel, and regenerates its own evidence. Table 2 shows the same steps expressed in five sectors, drawn directly from the released packs.

**Table 2.** The same architecture in five sectors. Each cell is declared in that sector's domain pack and enforced by the shared kernel.

| Step | Healthcare | Corporate data | Consumer finance | Public benefits | Education |
|---|---|---|---|---|---|
| Declared purposes (4, 8) | treatment, research, emergency treatment, patient access | internal analysis, external release, legal review | credit decision, fraud investigation, customer access, regulatory reporting | eligibility, appeal, applicant access, statistics, urgent safeguarding | student-support casework, academic record correction |
| Most restricted data and where it may be processed (2–4) | diagnosis, mental-health notes, genomic markers: on-premises model only | contract terms, customer contacts, product roadmap: private model only | identifiers, credit score, transactions, fraud signals: bank-private model only | national ID, disability and immigration status: sovereign model only | governed through action rules and exact approvals |
| Consequential action and independent approver (6–7) | treatment access: healthcare privacy officer | external release: data protection officer | credit-limit change: credit risk officer | benefit decision: benefit approver; appeal: independent appeals officer | transcript correction: registrar, after instructor confirmation |
| Governed release (8) | clinician; de-identified to researchers after research review | aggregates to partners after data protection approval | aggregates to the regulator after compliance approval | aggregates to the statistics office after data protection approval | decision returned through the case record |
| Exception path (10) | break-glass for emergency treatment, one hour, reviewed | legal hold freezes the dataset | fraud break-glass, thirty minutes, compliance review | urgent safeguarding, one hour, reviewed | appeal reopens a rejected correction |
| Refused by construction | public model API; external email | public model API; personal email | marketing partner receives nothing | enforcement agency receives nothing | a correction no instructor confirmed |

## 6. Building future AI systems: a seven-stage lifecycle

An architecture becomes a practice only when a team knows what to do on Monday. Figure 3 gives the lifecycle every new AI capability follows, in any sector (Fig. 3). Each stage produces an artifact and passes a gate before the next begins.

1. **Frame.** Name one consequential capability, the asset it touches, the harm it could cause, and its owner. Start with one capability and a manual fallback.
2. **Contract.** Fill the seven fields. An empty field is an open governance decision, returned to its owner rather than engineered around.
3. **Pack.** Declare purposes, data classes and zones, recipients, transitions, declassification, emergency access, and fallback in a domain pack that validates.
4. **Bind.** Give write credentials, record access, and keys only to mediators; register and sign a manifest for every model endpoint.
5. **Falsify.** Before real records or keys are connected, run hostile scenarios, ablate every control, enumerate bounded configurations, and run the falsifiers on synthetic data. Proceed only with zero counterexamples and every control load-bearing.
6. **Promote.** Rerun conformance on the target stack and deploy only when a fresh run matches the committed evidence.
7. **Operate.** Watch review capacity, revoke and reconcile, honour erasure, and keep the ability to replace any model or vendor. Any such change returns to stage 5.

The lifecycle gives each audience a concrete role. Policymakers and procurement officers can demand the seven fields, the trusted base, and the regenerated evidence before a contract is signed. Engineers can map each duty to an enforced interface. Auditors can rerun the evidence rather than trust a report.

## 7. Evaluation

### 7.1 Method

The evaluation asks distinct questions of the reference implementation. Property and bounded checks compare real enforcement against independent predicates over declared configuration spaces; ablation asks whether harm returns when a control is removed; conformance reruns the properties on substituted backends; stateful testing drives random sequences against an independent reference model; comparison arms send identical hostile inputs to weaker designs; and falsifiers try to refute the thesis directly. Utility is always reported beside containment, because a system that denies everything scores perfectly on containment and remains useless. The repository runs **724 deterministic tests** offline, with no network access and no model weights, so a second institution can check every number rather than trust it.

### 7.2 Mediation against conventional controls

Against an unguarded agent, a safety prompt with a per-agent tool allowlist, and this architecture, the same seven attacks delivered 28, 8, and 0 harmful actions, with every benign task completed in all three arms (Fig. 4a). Against the reference profile, **30 of 30 adversarial scenarios contained**, **240 configurations with zero violations**, **11 distinct denial controls** were reached, **8 of 8 ablated controls restored their harm when removed**, and **26 conformance checks passing on 2 backend profiles**; utility held at **6 of 6 benign tasks completed, false-denial rate 0.0**. A **32-caller race produced 1 mutation and 1 receipt**.

Reads were tested the same way. Across corporate, healthcare, financial, and government packs, **106 of 106 hostile data flows were contained**, including wrong-patient injections, purpose switches, withdrawn consent, and self-labelled summaries. Conventional access control, with signed class-cleared grants and an output check on the model's claimed label, **contained 32** (Fig. 4b). **All 14 checks were load-bearing**, **24,272 read and release configurations showed zero violations**, and 15 of 15 legitimate flows completed. Stateful testing, **800 sequences and 32,000 operations** against an independent reference model, found a defect single-step enumeration missed: a summary drafted before consent was withdrawn could still be released. Release now rechecks consent, revocation, and expiry, and the sequences agree.

Composition was tested with delegation chains. Nine invariants, from attenuation and rootedness to holder binding, are all load-bearing across **768 enumerated chain shapes and zero violations**. Validating each hop against its immediate caller, a plausible design, **contains 2 of 10 risk classes where verifying the chain contains 10** (Fig. 4c). Local correctness at every service is not chain correctness.

### 7.3 Review capacity

With the reference assumptions, **a roster of 11 reviewers sustains 2,640 consequential actions per day**. In a queue trial where 40 arrivals reach one reviewer, **Without load control, 4 such merit failures execute. With it, 0 do, and 32 actions defer to manual review** (Fig. 5). Across 25 parameter combinations the control was load-bearing in 16 of the 20 where harm was possible, harm reached zero in 16, and repairing contradictory defaults **drove the false-positive cost to 0**. Automation bias makes a hurried reviewer ratify what an assistant recommends [9]. A model-assisted reviewer multiplies throughput, but only independence keeps it safe: the trial observed **5 merit failures with a dependent assistant, 1 with an independent one**, so the architecture refuses to start a dependent assistant at a lowered deliberation floor.

### 7.4 Transfer across sectors

One successful domain cannot establish transfer (Fig. 6). **6 independently reported domain packs cover 55,440 bounded configurations, 180 of 180 hostile scenarios contained, 58 of 58 benign tasks completed, and zero unauthorized mutations.** The academic-record pack independently reports **4,800 configurations with zero violations, 30 of 30 scenarios contained, 9 of 9 benign tasks, 26 conformance checks**; its first run exposed a role declared in the pack but ignored at runtime, a defect invisible with a single domain.

### 7.5 A safety case that does not rest on alignment

A catalogue of 36 failure classes, including specification gaming, deceptive risk reporting, oversight flooding, collusion, authority laundering, injection, poisoning, and compromised signers, records **21 contained, 10 bounded, and 5 residual**, each bound to evidence checked to exist (Fig. 7a). Six falsifiers then try to refute the thesis across every pack. Their first run did: five contract bindings named functions that did not exist. Repaired, **104,997 bounded attempts found zero counterexamples**, and removing a single mediator check produces them (Fig. 7b). Because containment rests on enforcement code rather than model behaviour, the result does not depend on how any model behaves.

The method also applies to itself. Applying the contract to the repository's own requirements found that **eighteen of twenty-eight were prose bound to nothing.** Coverage is now published as machine-verified, organizationally attested, or unverified, **reading 41, 3, 0 today**, and a named test that does not exist fails the build. Every defect reported in this section was found by the method, not by its authors' review.

## 8. Education as the dissemination mechanism

The conference theme matters because this architecture requires **system literacy**: distinguishing proposals from powers and requests from entitlements, locating the mediator, following a token back to the entitlement that permits it, and reconstructing an outcome and its redress. A two-hour offline lab has participants break a boundary, remove a control, watch the harm return, and transfer the contract to their own domain.

For *AI for Learning*, the education packs govern institutional workflows such as student support and transcript correction with the same rules as a hospital or a benefits agency. For *Learning for AI*, the contribution is a reusable method for learning how AI systems acquire and exercise power. The repository is offered as a digital public good [8]: any institution can inspect the rules, replace the pack, and publish its own evidence, and educators can teach the same boundaries to policymakers, engineers, and students [7].

## 9. Scope and research agenda

Every figure is a reproducible fixture observation: any institution can regenerate it offline from the released repository and rerun it in its own environment. The architecture names its trusted base, so assurance effort concentrates on a small, declared set of components rather than on every model an institution adopts.

The research agenda moves the pattern from reproducible evidence to field evidence: institutional pilots, certified hardware one-way deployments, independent red teaming and audit, measured reviewer performance with and without assistants, and studies of de-identification, fairness, accessibility, cost, and energy. Because every governed action is attributable and contestable, the same records give institutions a foundation for participatory rulemaking over the rules their agents enforce.

## 10. Conclusion: directions for future AI systems

1. **Build on the Mediation Thesis.** Treat intelligence as untrusted, mediate every effect and data flow, and publish the attempts to refute it.
2. **Govern reads as strictly as writes.** Bind every context to purpose, subject, field, consent, and location, and label every output by what produced it.
3. **Keep identities out of models.** Tokenize personal data before inference, hold keys with the mediator, and restore identity only for an entitled recipient.
4. **Make every consequential capability contractable.** No capability ships without the seven fields, a test bound to something that runs, a recovery owner, and a conformance claim.
5. **Treat sovereignty as a demonstrable lifecycle capability.** Measure control of keys, data movement, model replacement, evidence, recovery, and exit, not hosting location.
6. **Publish authority and oversight ceilings before automation roadmaps.** Delegation depth and review capacity are safety limits, not staffing footnotes.
7. **Build sectors as domain packs over a shared kernel,** and trade failure cases, not sensitive data.

An AI system should be governed less like an application and more like an institution: with a constitution, separated powers, a memory it cannot rewrite, and a safe way to stop. The reference implementation shows that this direction can be built today.

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

[10] Barker, E. (2020). *Recommendation for Key Management: Part 1 — General*. NIST SP 800-57 Part 1 Rev. 5. https://doi.org/10.6028/NIST.SP.800-57pt1r5

[11] Kissel, R., Regenscheid, A., Scholl, M., and Stine, K. (2014). *Guidelines for Media Sanitization*. NIST SP 800-88 Rev. 1. https://doi.org/10.6028/NIST.SP.800-88r1

[12] Saltzer, J. H., and Schroeder, M. D. (1975). The protection of information in computer systems. *Proceedings of the IEEE*, 63(9), 1278–1308. https://doi.org/10.1109/PROC.1975.9939

[13] Denning, D. E. (1976). A lattice model of secure information flow. *Communications of the ACM*, 19(5), 236–243. https://doi.org/10.1145/360051.360056

[14] Clark, D. D., and Wilson, D. R. (1987). A comparison of commercial and military computer security policies. *IEEE Symposium on Security and Privacy*, 184–194.

[15] Debenedetti, E., et al. (2025). *Defeating Prompt Injections by Design*. https://arxiv.org/abs/2503.18813

[16] Costa, M., et al. (2025). *Securing AI Agents with Information-Flow Control*. https://arxiv.org/abs/2505.23643

[17] Greenblatt, R., Shlegeris, B., Sachan, K., and Roger, F. (2024). AI control: Improving safety despite intentional subversion. *Proceedings of the 41st International Conference on Machine Learning*. https://arxiv.org/abs/2312.06942

[18] European Parliament and Council (2016). *Regulation (EU) 2016/679 (General Data Protection Regulation)*. https://eur-lex.europa.eu/eli/reg/2016/679/oj

[19] European Parliament and Council (2024). *Regulation (EU) 2024/1689 (Artificial Intelligence Act)*. https://eur-lex.europa.eu/eli/reg/2024/1689/oj
