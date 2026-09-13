# Trust by Construction: A Cross-Sector Reference Architecture for Governed Agentic AI

**Proposed panel:** Agentic AI in the Loop - From Autonomous Tools to Shared Capacity
**Keywords:** agentic AI; reference architecture; secure data governance; privacy by design; institutional sovereignty; fail-secure systems; system literacy; digital public goods
**Reference implementation:** https://github.com/genaiworks/fssai-ra (release v1.0.0 for baseline figures, plus current-source supplements; record the reviewed commit at submission)

> Paste each section below into the matching form field. Headings are field
> labels, not prose. Run `python scripts/check_submission.py` before submitting.

## Introduction

An AI agent can now read a patient file, draft a credit decision, or change a transcript in seconds. Most AI governance still asks whether the model is safe. Yet harm happens in the system: a record read without need, a summary sent to the wrong person, a plausible plan turned into an act no one approved. As models grow more capable, their intent gets harder to verify, while a boundary stays easy to test.

This paper proposes Trust by Construction, an open reference architecture and build method for agentic AI in any sector. It rests on one testable thesis: intelligence is untrusted; power and data are mediated. Two rules follow. A model may propose an act, but it cannot grant itself the right to do it. It may ask for data, but it cannot grant itself the right to see it, or pass on what it saw.

We show how both rules become running code: a control contract, seven planes, a privacy pipeline that keeps identities out of models, and domain packs from schools to hospitals. The code is open, and every figure in this paper can be rerun offline. For AI x Education, the design is also a tool for system literacy: learners see where power sits, who holds the keys, and how to contest a decision.

## Development Section 1 Methodology Core Argument and Case Context

We treat the whole AI system, not the model, as the unit of trust, and we test it the way a safety case is tested: by trying to break it. The design joins proven ideas, namely reference monitors, least privilege, lattice information flow, separation of duties, and recent capability and flow control for agents, with institutional purpose, consent, review capacity, and evidence.

Contract. Each consequential capability gets a seven-field contract: asset, operation, enforcement point, owner, failure test, evidence, and failure response. A treatment-access capability, for example, names the patient record, one state change, the executor, a privacy officer, a wrong-patient test, a signed receipt, and revoke with manual fallback. A field that cannot be filled is an open policy choice, not a task for engineers. Each field is bound to a check that must exist and run.

Planes. Seven planes split duties. The boundary plane admits and quarantines input. The data plane keeps records encrypted, versioned, and replayable. The intelligence plane holds models and agents but no keys. The authority plane issues grants bound to holder, purpose, and time. The execution plane rechecks each act before one write. The evidence plane links intent to outcome. The resilience plane revokes, reconciles, and falls back to manual work. Two mediators, the executor and the context gate, alone hold write rights, record access, and keys.

Privacy pipeline. Before any model sees data, personal details become vault tokens, so the model can reason about which case a fact concerns without learning who it is. Fields are sealed under per-person keys held by the gate; erasing a person means destroying one key, which also voids backups. A semantic router reads the intent and data class of each request and picks the cheapest model allowed for that class, so restricted data stays on an attested local model. The router only advises: the gate checks grant, purpose, consent, zone, and model signature, then decrypts only the fields needed. Outputs carry the labels of all inputs, and real names return only for an entitled recipient.

Ten steps. Every request runs the same path: admit, protect, route, entitle, reason, authorize, execute, release, record, recover. Only one step is done by the model, and it yields a proposal, never an effect. Approval binds to the exact proposal, authority can only narrow as agents delegate, and human review is declared as capacity with a minimum time to decide, so overload defers work instead of turning approval into a rubber stamp.

Cases. Domain packs carry local meaning over one shared kernel. In health, diagnosis stays on premises and a privacy officer approves access. In corporate data, trade secrets stay private and a data protection officer approves release. In finance, credit and fraud data stay in the bank and a risk officer approves limits. In public benefits, identity and immigration data stay sovereign and appeals go to an independent officer. In education, a registrar applies a transcript fix only after the instructor confirms it.

Build method. Teams follow seven stages: frame one capability, fill the contract, write the pack, bind keys to mediators, falsify on synthetic data, promote only on fresh evidence, then operate. Any change of model, vendor, or backend returns to falsify. The reference stack uses FastAPI, PostgreSQL, Kafka, Iceberg, and Ollama; each part can be replaced once the same tests pass again.

Evaluation. The same attacks go to three designs: no mediation, a careful conventional control, and this architecture. We remove each control to see whether harm returns, enumerate bounded state spaces, run random stateful sequences against a reference model, and run six falsifiers that try to refute the thesis.

## Development Section 2 Results Analysis and Impact

All figures are reproducible fixture observations from synthetic domain packs, and utility is shown next to safety, since a system that refuses everything is safe and useless.

Acts. Seven attacks went to all three designs. The unguarded agent let 28 harmful actions through, a safety prompt with a tool allowlist let 8 through, and this architecture let none through; every benign task completed in all three, and the false-denial rate was 0.0. On the reference profile, 30 of 30 attack scenarios were contained, 240 configurations showed no violation, and 8 of 8 controls were load-bearing: removing any one brought its harm back. A 32-caller replay race produced one change and one receipt.

Data. Across health, corporate, finance, and government packs, 106 of 106 hostile data flows were contained, including wrong-patient requests, purpose switches, withdrawn consent, and self-labelled summaries. Conventional access control stopped 32. All 14 checks were load-bearing, 24,272 configurations showed no violation, and 15 of 15 legitimate flows completed. Stateful testing over 800 sequences and 32,000 random operations found a flaw single-step checks missed: a draft made before consent was withdrawn could still be released. Release now rechecks consent.

Agents. Checking only the calling agent stopped 2 of 10 chain attacks; checking the whole chain stopped all 10, across 768 chain shapes with no violation. Each service being correct does not make the chain correct.

Human review. Oversight is a finite resource. A roster of 11 reviewers sustains 2,640 consequential actions per day. When 40 cases reach one reviewer, 4 approvals that are wrong on merit execute without load control and none with it, while 32 cases move to manual review. Across 25 parameter settings, the control never raised harm. An AI assistant raised completed work fivefold, but a dependent assistant let 5 errors through and an independent one let 1, so a dependent setup is refused.

Transfer. Six domain packs share one kernel: 55,440 configurations checked, 180 of 180 hostile scenarios contained, 58 of 58 benign tasks completed, and no unauthorised change. Each pack reports its own denominators, so no sector borrows another's evidence. The academic records pack exposed a declared role the runtime ignored, a flaw one domain could never show.

Alignment. The safety case does not assume a well-behaved model. Of 36 failure classes, from specification gaming and deceptive risk reports to collusion and poisoned inputs, 21 are contained, 10 bounded, and 5 set as research goals. Six falsifiers made 104,997 attempts to cause an effect or disclosure from model output alone and found none; removing one mediator check makes them succeed. Their first run did find something: five contract entries named code that did not exist. The method was also turned on itself: 18 of 28 early requirements were prose bound to no test, and coverage now reads 41 machine-verified, 3 attested, and 0 unverified.

Impact. For institutions, trust becomes something a buyer can demand and an auditor can rerun: named mediators, filled contracts, declared review limits, and fresh evidence. Procurement officers can require the seven fields before signing, and regulators can check purpose, consent, and erasure as running controls rather than policy text. Sovereignty is measured as control of keys, data flow, model swap, and exit, not server location. For education, a two-hour offline lab lets learners break a boundary, remove a control, watch harm return, and rebuild the contract for their own field. Code, tests, and figures are open as a digital public good.

## Conclusion

Trust by Construction moves AI governance from the model to the system. Its claim is simple and testable: intelligence is untrusted; power and data are mediated. A model may reason, draft, and propose, but it cannot act without granted authority, see data without entitlement, learn identities it does not need, or rewrite the record of what happened.

Five steps follow for any institution adopting AI. Name the mediators and the keys only they hold. Keep identities out of models and restricted data on attested local models. Bind every consequential act and sensitive read to a purpose, an owner, and a failure test. Declare review capacity before automation targets. Rerun the evidence whenever a model, vendor, or backend changes.

Policy makers and buyers can then ask for proof, not promises. Engineers get a pattern they can build in any stack. Educators get a way to teach how AI systems gain and use power. For AI for Learning, a school can govern its agents with the same kernel as a hospital; for Learning for AI, learners get a concrete map of power, data, and redress. The next stage is field pilots with partner institutions, independent audit, and certified hardware. Governance built this way does not ask anyone to trust a model; it lets everyone check the system.

## References

Clark, D. D., and Wilson, D. R. (1987). A comparison of commercial and military computer security policies. IEEE Symposium on Security and Privacy, 184-194.

Costa, M., et al. (2025). Securing AI agents with information-flow control. https://arxiv.org/abs/2505.23643

Debenedetti, E., et al. (2025). Defeating prompt injections by design. https://arxiv.org/abs/2503.18813

Denning, D. E. (1976). A lattice model of secure information flow. Communications of the ACM, 19(5), 236-243. https://doi.org/10.1145/360051.360056

European Parliament and Council. (2016). Regulation (EU) 2016/679 (General Data Protection Regulation). https://eur-lex.europa.eu/eli/reg/2016/679/oj

Greenblatt, R., Shlegeris, B., Sachan, K., and Roger, F. (2024). AI control: Improving safety despite intentional subversion. Proceedings of the 41st International Conference on Machine Learning. https://arxiv.org/abs/2312.06942

ISO/IEC. (2023). ISO/IEC 42001:2023 - Information technology, Artificial intelligence, Management system. https://www.iso.org/standard/81230.html

Kissel, R., Regenscheid, A., Scholl, M., and Stine, K. (2014). Guidelines for Media Sanitization. NIST SP 800-88 Rev. 1. https://doi.org/10.6028/NIST.SP.800-88r1

Miao, F., and Cukurova, M. (2024). AI competency framework for teachers. UNESCO. https://unesdoc.unesco.org/ark:/48223/pf0000391104

National Institute of Standards and Technology. (2024). Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile. NIST AI 600-1. https://doi.org/10.6028/NIST.AI.600-1

OWASP GenAI Security Project. (2025). OWASP Top 10 for Agentic Applications 2026. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

Parasuraman, R., and Manzey, D. (2010). Complacency and bias in human use of automation: an attentional integration. Human Factors, 52(3), 381-410. https://doi.org/10.1177/0018720810376055

Rose, S., Borchert, O., Mitchell, S., and Connelly, S. (2020). Zero Trust Architecture. NIST SP 800-207. https://doi.org/10.6028/NIST.SP.800-207

Saltzer, J. H., and Schroeder, M. D. (1975). The protection of information in computer systems. Proceedings of the IEEE, 63(9), 1278-1308. https://doi.org/10.1109/PROC.1975.9939

United Nations. (2024). Global Digital Compact. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact
