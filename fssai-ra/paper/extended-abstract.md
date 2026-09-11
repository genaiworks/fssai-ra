# Trust by Construction: A Testable Architecture for Sovereign AI Agents in Education

**Submission:** Extended abstract, UNU Macau AI Conference 2026 — *AI × Education: AI for Learning, Learning for AI*, 25–26 November 2026, Macau SAR, China.
**Proposed panel:** Agentic AI in the Loop — From Autonomous Tools to Shared Capacity.
**Keywords:** agentic AI; educational administration; institutional sovereignty; fail-secure architecture; human oversight; verifiable governance; digital public goods.
**Reference implementation:** Apache-2.0, `https://github.com/genaiworks/fssai-ra`, release `v1.0.0`.

## 1. The problem, stated concretely

A university deploys an agent to help process student-support applications. It reads confidential records, interprets eligibility guidance, drafts recommendations, and calls administrative tools. A sentence inside an uploaded document can redirect that workflow. So can an ordinary mistake, with no attacker present at all.

The institutional question is narrower and more useful than "is the AI safe?". It is: **when the agent is wrong or compromised, what stops its proposal from becoming an unauthorized decision, and what evidence lets a student challenge the outcome?**

The architecture's central rule is one sentence: **a model may propose an action; it cannot manufacture the authority to execute it.** Everything below exists to make that rule testable rather than asserted.

Most answers today are about *where the model runs*. Local hosting is necessary for sovereignty and nowhere near sufficient. Sovereignty is better understood as a set of capabilities an institution can exercise and demonstrate: governing data access, deploying and replacing models, holding cryptographic keys, changing policy, producing evidence, and leaving a vendor. Each is testable. None is established by a data-centre postcode.

This contribution proposes that authority boundaries should be **specified, exercised, failed, and independently evidenced** — and it supplies a runnable, extensible reference implementation that does so, with results a second institution can reproduce on a disconnected laptop.

## 2. Contribution: the control contract, and three ways to check it

The original contribution is the **control contract**. For each consequential capability, it records seven fields: protected asset, permitted operation, enforcement point, accountable owner, failure test, evidence artifact, and failure response. The fields are not documentation convention. They are a diagnostic: a capability whose seven fields cannot be filled is a capability nobody is ready to automate.

This builds on, rather than restates, existing guidance. NIST SP 800-207 supplies explicit per-request authorization; NIST AI 600-1 organises the risk classes; OWASP's agentic work names threats arising from an agent's goals, tools, identity, and context; ISO/IEC 42001 frames the management system. What none of them supplies is a way for an institution to *demonstrate* that a named boundary held, in its own deployment, after it replaced the vendor's components with its own. That demonstration is the gap this work addresses.

Recording a contract is easy. The harder claim is that it is *enforced*. Three artifacts make the contract checkable rather than aspirational, and each answers a question that a hand-written test suite cannot.

**What about the combination nobody imagined?** A bounded model checker enumerates the application profile's entire declared authority space — every operation, state transition, approval variant, resource version, and identity pairing — and executes the real enforcement code against each one, then checks five invariants over the results. The reference profile explores 240 configurations with zero violations. This surfaced a defect worth reporting: because the approval signature covers the expiry, audience, and role fields, every attack that *tampered* with them was caught one check early, leaving the expiry, audience, and role checks themselves unexercised. The suite was measuring less than it claimed. Repairing it required adversarial cases carrying genuine signatures — a real reviewer's real approval, pointed at the wrong proposal, the wrong executor, or the wrong transition. 11 distinct denial controls are now each reached by at least one configuration.

**Is each control load-bearing?** The evaluation removes one control at a time and measures whether the harm returns. A control whose removal changes nothing was decorative, and the assurance matrix should stop claiming credit for it. We report this as an **authority coverage** figure: 8 of 8 ablated controls restored their harm when removed.

**Does it still hold after you replace a component?** Institutions will substitute their own database, message bus, model, and identity service. A portable conformance suite runs the architecture's properties against whatever backends a deployment has configured, naming for each check the governance requirement it defends, so a failure says which claim was lost rather than merely going red. 25 checks pass on 2 independent backend profiles. During development the suite immediately caught a real defect in our own SQL adapter, where the evidence write credential was not being enforced.

## 3. Architecture in five domains

**Controlled import.** External artifacts pass type, size, schema, and source-signature checks; recognisable active content is stripped. The inward channel exposes no read, reply, or acknowledgement method, verified by inspection and by a working unidirectional transport. Stripping removes *mechanical* injection, not instructions in ordinary language, and nothing downstream relies on it.

**Traceable transport and reconstructable evidence.** Accepted items receive stable identifiers and ordering; versioned snapshots preserve the exact inputs a decision used. Delivery is described as at-least-once, never exactly-once, and retention is a governance setting that must outlive the appeal window.

**Bounded assistance.** A local model — Ollama by default — proposes; it never executes. Retrieved text is fenced as data. Critically, the **action class of any proposal is read from the deployment's capability catalogue, never from the proposal**. A compromised agent that labels an award approval "reversible" changes nothing: it is reclassified, still routed to a named human, and the attempted downgrade is recorded as its own evidence. Without this, the claim that the model merely proposes leaks, because the proposer would be setting its own oversight requirement.

**Accountable action.** An approval binds to one exact proposal: target, arguments, evidence version, resource version, approver role, audience, and expiry. A changed proposal requires renewed review; retries return the stored receipt without a second mutation.

Here the implementation closes a gap the previous release could only document. When the register and the evidence ledger share a database, the mutation, receipt, intent, and outcome commit in **one transaction**: the state in which a case moved with no record of who moved it becomes unreachable rather than merely detectable. The residual is precise — no transaction can include a foreign system, so an external side effect still needs the outbox, an idempotency key, and reconciliation. Both paths are implemented, and the deployment reports which durability guarantee is in force.

## 4. Evidence, with denominators

Against the synthetic student-support profile: 30 of 30 adversarial scenarios contained, with **zero unauthorized mutations**; 240 model-checked states with zero invariant violations; authority coverage 1.0; 25 conformance checks passing on 2 backend profiles; 149 deterministic tests requiring no network and no model weights.

One figure matters more than the containment rate. **6 of 6 benign tasks completed, false-denial rate 0.0.** A system that denies everything scores perfectly on containment and is useless; reporting the two together is what stops either being optimised alone. A previous version of this work listed the utility baseline as future work, which meant its headline number had no denominator.

These are fixture observations in a declared environment. They are not security probabilities, a certification, or evidence of production readiness. Not yet evidenced: resistance to a compromised host administrator or signing authority; stochastic prompt-injection rates for a named model; reviewer accuracy, workload, appeal quality, fairness, accessibility, cost, or energy; and any independent audit. Separate containers on one host demonstrate logical separation, not independent administrative trust.

## 5. Relevance to the theme, and to adoption

For **AI for Learning**, this addresses educational administration — the domain where agentic AI will touch students soonest and where a wrong decision is felt as an unexplained outcome. For **Learning for AI**, the same testbed is a teaching environment: a participant identifies a trust boundary, attempts a policy violation, watches a named control refuse it, inspects the evidence, and recovers the workflow. This is a concrete complement to UNESCO's AI competency frameworks, which ask for practical judgement rather than vocabulary.

The contract also turns out to be a procurement instrument. An institution can put the seven fields to a vendor as seven questions, and a supplier who cannot name the enforcement point or the recovery owner for a consequential capability has answered the question that matters. This is the "shared capacity" the panel theme points at: not shared infrastructure, which few institutions can pool, but shared tests, shared failure cases, and a shared vocabulary for refusing a capability that nobody can evidence.

Adoption begins with one bounded workflow and a named service owner, and the repository is built to be used rather than only read. A browser worksheet takes one capability through the seven fields in about fifteen minutes, flags the answers a reviewer would reject — an owner that is a team, an enforcement point that is the model itself, a failure test written as an aspiration — and emits runnable configuration rather than a document. A 30/60/90-day playbook and a supplier questionnaire that turns the seven fields into seven procurement questions accompany it. `fssaira init` then scaffolds the domain with a profile, a contract, and a deliberately failing test that must be replaced with the adversarial case the institution actually fears. The scaffold ships an *empty* assurance file: a new domain inherits the structure and none of the evidence. Sharing test cases and control improvements builds capacity across institutions without exchanging a single student record, which is what the Global Digital Compact's commitment to digital public goods looks like in practice.

The proposition is actionable. Every consequential agent capability should have a named authorization boundary, an executable failure test, and a recovery owner — and publishing those three together gives institutions a concrete basis for deciding which powers to delegate, which evidence to demand, and when automation must stop.

---

*Full paper, reference implementation, machine-readable evaluation results, and the conformance suite are available at the repository above. Web references checked 10 September 2026.*
