# Trust by Construction: A Testable Architecture for Sovereign AI Agents in Education

**Submission:** Extended abstract, UNU Macau AI Conference 2026 — *AI × Education: AI for Learning, Learning for AI*, 25–26 November 2026, Macau SAR, China.
**Proposed panel:** Agentic AI in the Loop — From Autonomous Tools to Shared Capacity.
**Keywords:** agentic AI; educational administration; institutional sovereignty; fail-secure architecture; human oversight; verifiable governance; digital public goods.
**Reference implementation:** Apache-2.0, `https://github.com/genaiworks/fssai-ra`, release `v1.0.0`.

## 1. The problem, stated concretely

A student's support application is refused. She asks why.

Somewhere in that process an agent read her file, interpreted the eligibility guidance, drafted a recommendation, and called an administrative tool. She is entitled to three questions: **who decided this and were they allowed to; what did they see; how do I contest it.** In most agentic systems being deployed today there is no answer to any of them — not because anyone intended that, but because nothing was built to produce one.

A sentence inside an uploaded document could have redirected that workflow; so could an ordinary mistake, with no attacker anywhere. From where she stands the two are indistinguishable: an outcome, and no way in.

That problem is narrower and more useful than "is the AI safe?". The central rule is one sentence: **a model may propose an action; it cannot manufacture the authority to execute it.** Everything below exists to make that rule testable rather than asserted, and her three questions answerable as properties of the system rather than matters of institutional goodwill.

Most current answers concern *where the model runs*. Local hosting is necessary for sovereignty and nowhere near sufficient. Sovereignty is better understood as capabilities an institution can exercise and demonstrate: governing data access, deploying and replacing models, holding keys, changing policy, producing evidence, and leaving a vendor. Each is testable; none is established by a data-centre postcode, and none alone answers her questions. This contribution proposes that authority boundaries be **specified, exercised, failed, and independently evidenced**, with a reference implementation whose results a second institution can reproduce on a disconnected laptop.

## 2. Contribution: the control contract, and three ways to check it

The original contribution is the **control contract**. For each consequential capability it records seven fields: protected asset, permitted operation, enforcement point, accountable owner, failure test, evidence artifact, failure response. These are not documentation convention but a diagnostic — a capability whose seven fields cannot be filled is one nobody is ready to automate.

This builds on rather than restates existing guidance [1,2,3,4,6]. None of it supplies a way for an institution to *demonstrate* that a named boundary held, in its own deployment, after it replaced the vendor's components with its own. That demonstration is the gap.

Recording a contract is easy; the harder claim is that it is *enforced*. Three artifacts make it checkable rather than aspirational, each answering a question a hand-written test suite cannot.

**What about the combination nobody imagined?** Randomised property testing puts 6,800 generated tool calls against a reference predicate written independently of the implementation, with zero disagreements. A bounded model checker then enumerates the profile's whole declared authority space — every operation, transition, approval variant, version, and identity pairing — runs the real enforcement code against each, and checks five invariants. The reference profile explores 240 configurations with zero violations. It surfaced a defect worth reporting. Because the approval signature covers the expiry, audience, and role fields, every attack that *tampered* with them was caught one check early, leaving those three checks unexercised: the suite was measuring less than it claimed. Repairing it needed adversaries carrying genuine signatures — a real reviewer's real approval, pointed at the wrong proposal, executor, or transition. 11 distinct denial controls are now each reached by at least one configuration.

**Is each control load-bearing?** The evaluation removes one control at a time and measures whether the harm returns; a control whose removal changes nothing was decorative, and the assurance matrix should stop claiming credit for it. We report an **authority coverage** figure: 8 of 8 ablated controls restored their harm when removed.

**Does it still hold after you replace a component?** Institutions will substitute their own database, bus, model, and identity service. A portable conformance suite runs the properties against whatever backends a deployment has configured, naming for each check the governance requirement it defends, so a failure says which claim was lost rather than merely going red. 25 checks pass on 2 independent backend profiles — and the suite caught a real defect in our own SQL adapter: the evidence write credential was not enforced.

## 3. Architecture in five domains

Five domains organise the system — controlled import, traceable transport, reconstructable evidence, bounded assistance, accountable action — as responsibilities an institution can implement with different technologies, not a procurement stack. Two properties carry the argument.

**The model cannot set its own review level.** A local model (Ollama by default) proposes and never executes, retrieved text is fenced as data, and the **action class of any proposal is read from the deployment's capability catalogue, never from the proposal**. A compromised agent labelling an award approval "reversible" changes nothing: it is reclassified, still routed to a named human, and the downgrade attempt is itself recorded. Without this, the claim that the model merely proposes leaks, because the proposer would be setting its own oversight requirement.

**A record cannot go missing.** An approval binds to one exact proposal — target, arguments, evidence version, resource version, approver role, audience, expiry — so a changed proposal requires renewed review and retries return the stored receipt without a second mutation. Where the register and the evidence ledger share a database, the mutation, receipt, intent, and outcome commit in **one transaction**: a case moving with no record of who moved it becomes unreachable rather than merely detectable, closing a gap the previous release could only document. The residual is precise — no transaction can include a foreign system, so an external side effect still needs the outbox, an idempotency key, and reconciliation. Both paths ship, and the deployment reports which guarantee is in force.

We state the boundary's limits plainly: stripping removes *mechanical* injection only, delivery is at-least-once and never exactly-once, and snapshot retention must outlive the appeal window.

## 4. Evidence, with denominators

**Compared with how agents are built today.** A containment figure means nothing without a baseline, so the same seven attacks — identical hostile proposals, identical legitimate work — went to three architectures. An *unguarded* arm (model, tool registry, loop) contained 0% and delivered 28 harmful actions. A *prompt-guarded* arm adding the two mitigations most commonly deployed, a safety system prompt and a per-agent tool allowlist, contained 29% and delivered 8. That arm is deliberately not a strawman — an allowlist is a real control doing real work — but it cannot tell a legitimate use of a granted tool from a hostile one, or require a person for a consequential one. This architecture contained 7 of 7 and delivered none.

Against the synthetic student-support profile: 30 of 30 adversarial scenarios contained, with **zero unauthorized mutations**; 240 model-checked states with zero invariant violations; authority coverage 1.0; 25 conformance checks passing on 2 backend profiles; 187 deterministic tests run offline. A 32-caller race produced 1 mutation and 1 receipt. This tests one single-process replay property, not distributed linearizability.

One figure matters more than the containment rate. **6 of 6 benign tasks completed, false-denial rate 0.0.** A system that denies everything scores perfectly on containment and is useless; reporting the two together is what stops either being optimised alone. A previous version of this work listed the utility baseline as future work, which meant its headline number had no denominator.

These are fixture observations in a declared environment: not security probabilities, a certification, or evidence of production readiness. Not yet evidenced: resistance to a compromised host administrator or signing authority; injection rates for a named model; reviewer accuracy, workload, appeal quality, fairness, accessibility, cost, energy; and any independent audit. Separate containers on one host are logical separation, not independent administrative trust.

## 5. Relevance to the theme, and to adoption

For **AI for Learning**, this addresses educational administration, where agentic AI reaches students soonest and a wrong decision arrives as an unexplained outcome. For **Learning for AI**, the same testbed teaches: a participant identifies a trust boundary, attempts a violation, watches a named control refuse it, inspects the evidence, and recovers the workflow — a concrete complement to UNESCO's AI competency frameworks [9], which ask for practical judgement rather than vocabulary.

The contract doubles as a procurement instrument: put the seven fields to a vendor as seven questions, and a supplier who cannot name the enforcement point or recovery owner has answered the one that matters. This is the "shared capacity" the panel theme points at — not shared infrastructure, which few institutions can pool, but shared tests, failure cases, and a vocabulary for refusing a capability nobody can evidence. Exchanging those builds capacity without moving a single student record, which is what the Global Digital Compact's commitment to digital public goods [10] looks like in practice.

The repository is built to be used rather than read. A browser worksheet takes one capability through the seven fields in about fifteen minutes, flags the answers a reviewer would reject — an owner that is a team, an enforcement point that is the model itself — and emits runnable configuration rather than a document. A 30/60/90-day playbook and a supplier questionnaire accompany it, and `fssaira init` scaffolds a domain with a deliberately failing test and an *empty* assurance file: a new domain inherits the structure and none of the evidence.

The proposition is actionable. Every consequential agent capability should have a named authorization boundary, an executable failure test, and a recovery owner — three things, publishable for one capability, this quarter, by an institution with no budget.

One caveat belongs here rather than in a footnote. A perfectly governed agent enforcing an unjust policy produces well-documented injustice, faster: this architecture makes harm **attributable**, not rules fair. What it changes is that the student who asked why can be answered — who decided, what they saw, how to contest it. That is a real contribution and a modest one. We are about to hand consequential decisions about people to systems that cannot yet answer her, and that is a choice rather than a trajectory. It is still open.

## References

[1] Rose, S., Borchert, O., Mitchell, S., and Connelly, S. (2020). *Zero Trust Architecture*. NIST SP 800-207. https://doi.org/10.6028/NIST.SP.800-207

[2] Autio, C., et al. (2024). *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*. NIST AI 600-1. https://doi.org/10.6028/NIST.AI.600-1

[3] OWASP GenAI Security Project (2025). *OWASP Top 10 for Agentic Applications 2026*. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

[4] OWASP GenAI Security Project (2026). *Agent Control Standard*. https://genai.owasp.org/resource/agent-control-standard-acs/

[5] MITRE (2024). *ATLAS: Adversarial Threat Landscape for Artificial-Intelligence Systems*. https://atlas.mitre.org/

[6] ISO/IEC (2023). *ISO/IEC 42001:2023 — Information technology, Artificial intelligence, Management system*. https://www.iso.org/standard/81230.html

[7] Apache Software Foundation. *Apache Kafka Documentation: Design*. https://kafka.apache.org/documentation/#design

[8] Apache Software Foundation. *Apache Iceberg Documentation: Maintenance*. https://iceberg.apache.org/docs/latest/maintenance/

[9] UNESCO (2024). *AI Competency Framework for Teachers*. https://www.unesco.org/en/articles/ai-competency-framework-teachers

[10] United Nations (2024). *Global Digital Compact*. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact

---

*Reference implementation, machine-readable evaluation results, the architecture comparison, and the conformance suite are available at the repository above. Web references checked 10 September 2026.*
