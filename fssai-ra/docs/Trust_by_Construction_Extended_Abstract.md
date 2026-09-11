# Trust by Construction: A Fail-Secure Reference Architecture for Sovereign Agentic AI

> Superseded draft. For the current bounded claims, tested implementation status,
> and conference submission text, use `extended-abstract.md` and release `v0.3.0`.

**Panel 2 — Agentic AI in the Loop: From Autonomous Tools to Shared Capacity**

## Abstract

As AI agents move from conversation into workflows that handle confidential records and shape consequential decisions, model-level guardrails and vendor contracts cannot carry the full security burden. This paper proposes a *fail-secure sovereign AI reference architecture*: a vendor-neutral pattern for local models and bounded agents in which the trust of the whole system rests on structure, not on any single component being trustworthy. Its claim is containment, not invulnerability — no single compromised file, model, agent, user, or software layer should gain unchecked access, take a high-impact action, or erase the record without meeting an independent control. The architecture is expressed as a property-based control contract, instantiated across five interchangeable domains, and evaluated against five adversarial cases drawn from recognized public threat catalogs. To serve as a public good, the contract and a reproducible synthetic-data testbed are to be released as an open, permissively licensed reference implementation that institutions can adopt, verify, and extend — a portable, testable bridge between governance goals and system controls, and a scaffold for the system literacy needed to build and govern it.

**Keywords:** sovereign AI; fail-secure architecture; agentic AI governance; zero-trust; data lineage; human-in-the-loop; auditability; open reference implementation; AI system literacy

## 1. Introduction and Contribution

AI agents are moving from chat into workflows that handle private records and shape important decisions. There, model rules and vendor contracts cannot bear the full security load: prompt injection, poisoned data, over-broad tool access, unsafe updates, and insider misuse can each turn a useful system into a path for data loss or unaccountable action. The problem is acute for the institutions the Global Digital Compact most seeks to empower — universities, hospitals, and ministries — which need modern AI yet cannot export protected data to external model services, even as regulation increasingly designates such deployments high-risk AI systems subject to strict oversight [12]. Sovereignty here means control of data, models, keys, policy, and evidence, not isolation from knowledge.

Existing guidance covers parts of this problem — zero-trust networking [1], AI risk management [2], operational-technology boundary protection [3], and community catalogs of LLM and agent risks [10], [11] — but none specifies, end to end, how the parts of an agentic system should be arranged so a failure in any one is contained by another. This paper supplies that arrangement. Its contribution is fourfold: (i) a *property-based control contract* that turns governance goals into testable requirements — controlled data flow, least privilege, reproducible data states, explicit human authority, and durable evidence; (ii) a five-domain reference architecture instantiating the contract with interchangeable open components; (iii) a six-stage containment-chain method for evaluating it against adversarial cases; and (iv) an openly released reference implementation and conformance test suite, so the contract can be independently verified, adopted, and extended to new application domains. The proposal draws only on public standards, open documentation, and synthetic test cases; it does not describe any specific organization's systems, data, projects, or operational practices, and all views are the author's own.

## 2. Architecture and Method

The study combines threat modeling, architectural review, and adversarial case analysis. It names the assets a high-risk AI system must protect — records, model artifacts, prompts, retrieved evidence, keys, policy, and decision history — and their threats, from hostile web content and poisoned files to excessive agent privileges and insider misuse. For each control it assumes the adjacent layer has already failed and asks whether an independent mechanism can still prevent data loss, block an action, reveal what occurred, or restore a known-good state, following zero-trust [1] and the NIST AI Risk Management Framework [2]. Every control is documented as a property, owner, test, and failure response, so implementations can be compared without a shared software stack (Table 1).

The architecture has five linked domains. A **low-trust import domain** verifies source, signature, type, size, and schema and strips active content on the less-trusted side; a protocol break then converts each approved item into a constrained form that a hardware one-way gateway passes inward. The diode gives strong directional assurance on a single link — it does not secure an endpoint or close paths via service ports, remote tools, removable media, wireless, or staff — so it is paired with pre- and post-transfer validation and separated administrative channels [3]. An **event-transport domain** uses Kafka for durable, ordered, replayable flow; because retention and compaction can drop events, Kafka is not the record of truth [4], and each item carries a hash, source tag, timestamp, and trace id. A **reproducible-data domain** uses Spark, each job logging code version, inputs, rules, and output hash, while Iceberg stores approved data as atomic snapshots with history and rollback [6]; snapshots tied to decisions are pinned or their signed manifests sent to a separate evidence store, and exactly-once behavior is treated as a property of source, job, and sink together [5]. A **bounded-intelligence domain** routes each request to an approved local model or agent by task, data class, cost, and risk, each agent holding a distinct identity, tools, data scope, and limits. An **accountable-action domain** mediates every tool call at a policy point: reversible work runs within limits, high-impact work needs an authorized person, and an append-only evidence service records request, policy, snapshot, model hash, sources, tool calls, result, approval, and act — with separate keys so no agent edits its own record.

**Table 1. The property-based control contract (abridged).**

| Domain | Property | Representative control | Test | Failure response |
|---|---|---|---|---|
| Import boundary | Controlled inflow; no ordinary egress path | One-way gateway + protocol break; pre/post validation | Attempt outbound transfer on the protected side | Block source; quarantine; alert |
| Event transport | Durable, ordered, replayable ingestion | Kafka partitioning, replication, retention; per-item trace | Kill a consumer mid-stream; verify replay | Replay from offset; investigate gap |
| Reproducible data | Versioned, rollback-able states | Spark lineage logging; Iceberg snapshots + pinned manifests | Reconstruct a past decision's exact inputs | Roll back to last approved snapshot |
| Bounded intelligence | Least-privilege, task-scoped agents | Semantic router; per-agent identity, tools, scope, limits | Attempt out-of-scope tool or data access | Deny; scope down; escalate |
| Accountable action | Authorization for consequential acts; tamper-evident record | Policy point; human approval; append-only evidence, separate keys | Attempt unapproved high-impact act; edit own record | Deny; require approver; flag inconsistency |

## 3. Evaluation Against Adversarial Cases

The design is assessed against five cases spanning the recognized risk classes for LLM and agentic systems [10], [11], each traced through one chain: threat, preventive control, containment boundary, evidence, recovery, accountable actor. This does not prove a paper design secure; it defines claims a testbed can measure with synthetic data, signed artifacts, and staged attacks — blocked egress, denied tool calls, decision replay, recovery time, and operator effort.

**Prompt injection** (ranked first by OWASP [10]): low-side conversion strips active content and imported text is treated as untrusted evidence, not instruction; even if it reaches a model, the agent holds only scoped tools, the policy point checks each call, and the import link offers no return path. **Poisoned source data**: schema checks cannot judge truth, so source rules, signatures, cross-checks, and staged release reduce exposure, while Iceberg and signed manifests let operators restore the last approved snapshot and find affected decisions. **Model hallucination** (the misinformation and overreliance risk): cited retrieval and rule checks help, but the essential safeguard is separating advice from authority — high-impact acts need a named approver, and the record preserves what the model saw, proposed, and who accepted or changed it. **Compromised model or update** (supply-chain risk): the import side verifies source and hash, an isolated zone tests behavior before release, a signed registry holds approved artifacts, and agents cannot grant themselves rights or edit policy or their own audit trail. **Insider record manipulation** (a limiting case of excessive agency): authentication, separation of duties, dual approval, signed events, and append-only storage make silent edits hard, and an independent monitor compares live state to signed evidence — though tamper-evidence cannot stop every abuse by a valid user, so access review remains required. In each case a single failure is contained, made visible, and reversible rather than allowed to become silent, irreversible harm.

## 4. Discussion: Portability, Extensibility, and Education

The result is a portable mapping between governance goals and controls that depends on no single vendor: any event bus, compute engine, table format, model runtime, or evidence store may substitute if it preserves the property and passes the test. Because the contract is expressed as properties with tests rather than a fixed stack, it doubles as a conformance checklist and an extensible baseline: an institution adopts a property, chooses tools that pass its test, and adds domains or attack cases as needs evolve — the basis for a community-maintained secure baseline for future application development. Local models and task routing may cut cloud dependence, cost, and energy, though each site must measure this. In education, the same chain can govern admissions triage, student support, assessment, and research — agents prepare or recommend while policy and named people keep consequential authority. The architecture is also a teaching scaffold: it defines a system literacy for the conference's "Learning for AI" dimension, in which builders learn trust boundaries, privileges, lineage, testing, recovery, and human control — aligned with UNESCO's AI competency framework [9] and the Global Digital Compact's call for open tools, local capacity, and human oversight [7].

*Availability.* The reference implementation, control contract, threat model, attack scenarios, and evaluation metrics are to be released under a permissive open-source license so that results can be reproduced, audited, and extended by the community.

## 5. Conclusion and Future Work

The architecture turns broad goals for trustworthy AI into controls that can be inspected and tested. It promises not perfect defense but containment: no single compromised file, model, agent, user, or layer gains unchecked access, takes a high-impact action, or erases the record without meeting another control. The next step is an open, vendor-neutral testbed on synthetic data whose plan states the threat model, attack cases, success metrics, and residual risk, and that compares the full design against ablated variants removing one control at a time — measuring denied egress, blocked actions, replay accuracy, recovery time, and operator burden. The work aligns with existing frameworks — ISO/IEC 42001 for management-system context [8], and NIST and OWASP for risk and threat coverage [2], [10] — rather than claiming status as an adopted standard, and will be published as an open reference implementation and conformance suite the community can extend into a secure baseline for future application development. For Panel 2, the lesson is direct: shared capacity with AI agents depends on bounded power, sound evidence, and meaningful human control, and institutions can build local capability without granting default trust to any provider, network, component, or model.

## References

[1] S. Rose, O. Borchert, S. Mitchell, and S. Connelly, *Zero Trust Architecture*, NIST SP 800-207, 2020. https://doi.org/10.6028/NIST.SP.800-207

[2] National Institute of Standards and Technology, *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*, NIST AI 600-1, 2024. https://doi.org/10.6028/NIST.AI.600-1

[3] UK National Cyber Security Centre, "Secure Connectivity Principles for Operational Technology: Harden Your OT Boundary," 2026. https://www.ncsc.gov.uk/collection/operational-technology/secure-connectivity/principle-5

[4] Apache Software Foundation, "Apache Kafka Design: Log Compaction," 2026. https://kafka.apache.org/design/

[5] Apache Software Foundation, "Structured Streaming Programming Guide," 2026. https://spark.apache.org/docs/latest/streaming/

[6] Apache Software Foundation, "Apache Iceberg Reliability and Maintenance," 2026. https://iceberg.apache.org/docs/latest/maintenance/

[7] United Nations, *Global Digital Compact*, 2024. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact

[8] International Organization for Standardization, *ISO/IEC 42001:2023 — Information Technology — Artificial Intelligence — Management System*, 2023. https://www.iso.org/standard/42001

[9] UNESCO, *AI Competency Framework for Teachers*, 2024. https://unesdoc.unesco.org/ark:/48223/pf0000391104

[10] OWASP GenAI Security Project, *OWASP Top 10 for LLM Applications (2026)*, 2026. https://genai.owasp.org/

[11] MITRE, *MITRE ATLAS: Adversarial Threat Landscape for Artificial-Intelligence Systems*. https://atlas.mitre.org

[12] European Union, *Regulation (EU) 2024/1689 (Artificial Intelligence Act)*, Official Journal of the European Union, 2024. https://eur-lex.europa.eu/eli/reg/2024/1689/oj
