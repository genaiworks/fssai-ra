# Trust by Construction: A Testable Architecture for Sovereign AI Agents in Education

**Proposed contribution:** Panel 2 — Agentic AI in the Loop: From Autonomous Tools to Shared Capacity  
**Keywords:** agentic AI; education; institutional sovereignty; fail-secure architecture; human oversight; reproducibility; open reference implementation

## 1. Problem and research question

An AI agent helping a university process student-support applications may read confidential records, interpret eligibility guidance, draft recommendations, and invoke administrative tools. A malicious instruction in an uploaded document could redirect this workflow. An inaccurate recommendation could also cause harm without any attacker. The institutional question is therefore concrete: when an agent is wrong or compromised, what prevents its proposal from becoming an unauthorized decision, and what evidence enables a person to challenge the outcome?

This contribution proposes a fail-secure reference architecture for sovereign agentic AI in education. Sovereignty means an institution's effective ability to govern data access, model deployment, cryptographic keys, policy changes, and operational evidence, including its ability to replace a provider. Local hosting supports these capabilities but does not establish them by itself. Fail-secure means that uncertainty or failure in required authorization controls prevents a consequential automated action, while a defined manual service preserves access to support. Confidentiality, decision quality, availability, and accountability require distinct safeguards.

The research question is: can a portable control contract contain specified agent failures while preserving useful assistance and feasible institutional oversight? The proposed contribution is an integration and evaluation method, grounded in an educational workflow, rather than a claim to invent zero trust or guarantee secure AI.

## 2. Contribution and assurance scope

NIST's zero-trust architecture provides a foundation for explicit authorization [1], while its Generative AI Profile organizes relevant risks [2]. OWASP's agentic guidance identifies threats arising from agents' goals, tools, identities, and context [3]. Its Agent Control Standard describes portable runtime controls [4]. Building on these resources, the proposed contribution connects governance requirements to independently enforced controls, failure tests, recovery procedures, and named institutional responsibilities.

The control contract records, for each requirement, a protected asset, permitted operation, enforcement point, owner, test, evidence artifact, and failure response. For example, a student-support agent may prepare a recommendation for an assigned case, but cannot approve an award, broaden its own access, or delete its evidence. Successful authorization requires the execution service to verify the actual operation and current policy independently of the model's explanation.

The threat model assumes hostile documents and potentially compromised agent processes. It requires functioning enforcement services and protected administrative credentials. Compromise of a shared host administrator, signing authority, or multiple colluding control owners can defeat this assumption. Separate containers on one host demonstrate logical separation, not independent administrative trust. The architecture therefore makes bounded claims about identified failure paths, with its trusted components and remaining risks explicitly documented.

## 3. Architecture and educational workflow

Five functional domains organize the system. They represent responsibilities that institutions can implement with different technologies, rather than a mandatory procurement stack. Identity, policy administration, key management, and evidence protection cut across the domains and require authority separate from the agent runtime.

**Controlled import.** External documents and updates enter through quarantine, provenance checks, constrained parsing, and explicit release. Approved records retain source identifiers and content hashes. Removing active content reduces some risks but does not remove malicious instructions embedded in ordinary language or establish factual truth. Sensitive deployments may add a hardware one-way gateway on the import link. Its directional guarantee applies to that link only. Maintenance connections, operator interfaces, telemetry, and authorized outputs require their own controls.

**Traceable transport.** Each accepted item receives a stable identifier and a documented ordering scope. A durable queue supports restart and replay, with duplicate detection at downstream consumers. Kafka is one possible implementation, but partition ordering and configured retention do not constitute a permanent decision archive [5]. Missing, duplicate, and out-of-order events trigger explicit handling rather than silent assumptions about exactly-once processing.

**Reconstructable evidence.** Versioned datasets preserve the records used for a decision, together with transformation code, retrieval configuration, and the exact retrieved passages. Iceberg is one possible implementation, provided retention protects the required snapshots and their referenced files [6]. A signed manifest identifies evidence but cannot reconstruct data that has been deleted. Reconstruction means recovering the decision's inputs and recorded outputs; it does not promise identical text from a nondeterministic model rerun.

**Bounded assistance.** An approved model helps staff assemble evidence and draft an explanation. Each agent has a case-scoped identity, a restricted tool list, and limits on execution time and resource use. Retrieval services enforce record and field permissions before data reaches the model. Task routing can select a model, but cannot grant privileges or lower the required review level. Untrusted content never supplies authoritative access labels, approval status, or tool permissions.

**Accountable action.** Agents submit structured proposals to an execution service that holds the necessary credentials. A consequential operation requires an authorized reviewer to inspect the affected case, supporting evidence, uncertainty, and proposed change. Approval binds to the exact action, target, arguments, evidence version, and expiry. A changed proposal requires renewed approval. The executor rechecks policy and current record state, rejects reused approvals, and requires a durable intent receipt before attempting the action. Idempotent execution and reconciliation address interrupted operations whose outcome is uncertain. An independent evidence service records authorization and outcome, with a separate monitor checking continuity.

In the illustrative workflow, a student uploads synthetic supporting documents. The agent drafts a support recommendation, but a named officer decides whether to authorize a change. Students receive an understandable explanation and a route to correction or appeal. The institution retains responsibility for the underlying eligibility policy and its fairness. Human approval alone cannot establish that a recommendation is accurate or equitable.

## 4. Planned evaluation

This extended abstract presents a design, teaching-profile implementation, and broader evaluation protocol. The current in-memory prototype reports no production deployment, security certification, or completed stochastic benchmark. In a verified local run on 10 September 2026, twenty-three deterministic contract, adversarial, ablation, and exact-action tests passed. The exact-action tests include authenticated approval fields, trusted-key selection, fail-closed empty trust configuration, operation allowlisting, stale-state checks, and idempotent retry without duplicate evidence. They demonstrate only the specified software properties in the declared synthetic environment. The next evaluation stage will compare a model-only guardrail baseline, the complete proposed control configuration, and variants that remove one control at a time. Each comparison will hold the task, attack input, model configuration, and relevant data state constant, with repeated trials where model behavior is stochastic.

The initial scenarios cover malicious instructions in retrieved documents, poisoned source evidence, an unauthorized tool request, substitution of an unapproved model artifact, alteration or replay of an approved action, and an attempt to modify decision evidence. Fault injection will additionally interrupt policy and evidence services and crash the executor around an external action. A benign task set will check whether legitimate assistance remains usable. These scenarios sample recognized risk classes [2,3]; they do not establish comprehensive threat coverage.

For each scenario, evaluation traces the initiating threat, enforcement decision, containment boundary, observable evidence, recovery step, and responsible actor. Primary measures include unauthorized actions completed per attempt, protected records disclosed per attempt, benign task completion, false denials, evidence reconstruction success, and unresolved execution outcomes. Operational measures include recovery time, approval delay, reviewer effort, and resource consumption. Results will include denominators, configuration details, and uncertainty rather than a single security score.

A release candidate must pass all predefined critical authorization and evidence tests in its declared environment. Any prohibited action completed, protected record exposed, or required evidence silently lost constitutes failure. Zero observed violations will describe the tested sample only. Review exercises will separately examine whether staff detect misleading recommendations and whether the appeal process yields a usable correction. Synthetic cases cannot establish real-world fairness or learning benefits.

## 5. Shared capacity and open implementation

The architecture addresses both directions of the conference theme. For “AI for Learning,” it proposes a way to support educational administration while keeping consequential authority accountable. For “Learning for AI,” the same testbed becomes a teaching environment: participants identify a trust boundary, attempt a policy violation, inspect its evidence, and recover the workflow. This complements UNESCO's emphasis on teachers' AI knowledge, ethics, and professional capacity [7].

The Apache-2.0 companion repository at https://github.com/genaiworks/fssai-ra contains the control contract, synthetic cases, executable teaching-profile tests, adapter seams, security limits, and an extension guide. Planned additions include deployment profiles, recovery runbooks, and versioned evaluation reports. A laptop teaching profile makes the concepts accessible; an institutional profile must separate control administration and evidence custody. A hardware-isolated profile must document additional equipment and operational requirements. Passing a teaching profile does not imply equivalent production assurance.

Adoption begins with one bounded workflow and a named service owner. Institutions will establish a manual fallback, validate local-language evidence and accessibility, train reviewers, and measure workload before expanding autonomy. Cost and energy benefits remain empirical questions, including hardware, utilization, maintenance, and staff time. Sharing test cases and control improvements can build capacity across institutions without exchanging student records, supporting the Global Digital Compact's commitment to digital public goods and cooperation [8].

The central proposition is actionable: every consequential agent capability should have an identified authorization boundary, an executable failure test, and a recovery owner. Publishing these together would give institutions a concrete basis for deciding which powers to delegate, which evidence to demand, and when automation must stop.

## References

[1] Rose, S., Borchert, O., Mitchell, S., and Connelly, S. (2020). *Zero Trust Architecture*. NIST SP 800-207. https://doi.org/10.6028/NIST.SP.800-207

[2] Autio, C., et al. (2024). *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*. NIST AI 600-1. https://doi.org/10.6028/NIST.AI.600-1

[3] OWASP GenAI Security Project (2025). *OWASP Top 10 for Agentic Applications 2026*. Published 9 December 2025. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

[4] OWASP GenAI Security Project (2026). *Agent Control Standard (ACS)*. Resource page published 1 September 2026. https://genai.owasp.org/resource/agent-control-standard-acs/

[5] Apache Software Foundation. *Apache Kafka 4.1 Documentation: Design*. https://kafka.apache.org/41/design/design/

[6] Apache Software Foundation. *Apache Iceberg Documentation: Maintenance*. https://iceberg.apache.org/docs/latest/maintenance/

[7] UNESCO (2024). *AI Competency Framework for Teachers*. https://www.unesco.org/en/articles/ai-competency-framework-teachers

[8] United Nations (2024). *Global Digital Compact*. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact

Web references checked 9 September 2026.
