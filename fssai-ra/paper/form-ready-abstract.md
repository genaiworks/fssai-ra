# Trust by Construction: A Testable Architecture for Sovereign AI Agents in Education

**Proposed panel:** Agentic AI in the Loop From Autonomous Tools to Shared Capacity  
**Keywords:** agentic AI, education, institutional sovereignty, fail secure architecture, human oversight, verifiable governance, digital public goods  
**Reference implementation:** https://github.com/genaiworks/fssai-ra (v1.0.0 baseline plus current-source supplements; record the reviewed commit at submission)

## Introduction

A student's support application is refused. She asks who decided, what evidence they saw, and how she can contest the result. An AI agent may have read private records, applied policy, drafted advice, and called an office tool. A malicious instruction in an uploaded file could redirect that workflow. An ordinary model error could cause the same harm. For the student, both produce a result with no clear route back in.

This work asks a narrower, actionable question than whether AI is trustworthy: what stops a wrong or compromised agent from turning its own proposal into institutional authority? It presents Trust by Construction, a fail secure reference architecture for sovereign AI agents in education. Its central rule is that a model may propose an action but cannot create the authority to execute it.

The original contribution is an executable control contract. For every consequential capability, it names the protected asset, allowed operation, enforcement point, owner, failure test, evidence, and recovery response. Sovereignty thus becomes a set of powers an institution can exercise and show: control of access, models, keys, policy, evidence, and provider exit. The aim is to make authority boundaries falsifiable, portable, and useful for learning rather than leaving them as policy promises.

## Development Section 1 Methodology Core Argument and Case Context

The method joins an education case with executable assurance. It builds on zero trust, the NIST Generative AI Profile, OWASP agent security guidance, ISO IEC 42001, and UNESCO's AI competency framework. It links governance duties to behavior that another institution can test after replacing the original parts.

The control contract is machine readable, not a prose checklist. A rule fails validation if any of its seven fields is absent, and each check names the rule it defends. This traces a governance claim to code, an observed side effect, a saved record, and the person responsible for recovery. A team starts with one consequential capability and a manual service. It writes the failure test before adding real records or keys. If it cannot name an enforcement point or recovery owner, the capability is not ready for automation.

This sequence makes the method teachable. Policy, domain, security, and software staff can inspect one shared object, challenge its assumptions, and agree what proof must exist before a pilot begins or expands.

The example uses synthetic student support records. An agent may fetch evidence for an assigned case, draft an explanation, and propose moving the case from draft to officer review. It cannot approve an award, widen its access, delete evidence, or hold the key that changes the case register. A named officer retains authority. The design requires an explanation and an institutional correction or appeal route. The institution remains responsible for policy, access, and fairness.

Five domains organize the design. Controlled import checks source, type, size, schema, and signature before release inward. Its software interface has no read back method and can be replaced by a certified one way data diode. This seam does not prove physical direction, and hardware governs only its stated link. Traceable transport uses stable IDs and replayable events. Evidence preserves the data snapshot, transforms, retrieved text, model ID, proposal, approval, and outcome. Bounded assistance gives each agent a narrow identity and tool set. Accountable action places the write key in an executor outside the model process.

Approval binds to a proposal digest covering the operation, target, states, evidence version, requester, and resource version. A signature also protects the reviewer role, audience, and expiry. The executor checks these fields before mutation. It gets the review class from a deployment catalogue, never the model's label. When state and evidence share a database, intent, mutation, receipt, and outcome commit together. External effects still need an outbox, idempotency key, and reconciliation.

Three declared profiles prevent assurance transfer. Teaching mode runs offline with synthetic data and memory stores. The distributed profile uses authenticated services and exposes health, readiness, metrics, evidence checks, and recovery. A hardware isolated profile adds a physical map, interface list, maintenance process, and independently tested directional gateway. Passing one profile never proves another. A laptop demo cannot be called sovereign production infrastructure, though each profile keeps the same observable contract.

Property tests compare generated calls with a separate authorization rule. A bounded checker explores five invariants. Ablations remove controls to test whether harm returns. Conformance checks apply the properties to new backends. A separate offline checker compares the recorded proposal, approval, receipt, and selected evidence records. It distinguishes internal consistency from agreement with a separately retained fingerprint. The packet marks missing source content and unchecked approval authentication. A classroom exercise alters a target, then rewrites context and recomputes hashes. This tests verification limits, not whether a valid hash makes a decision sound.

## Development Section 2 Results Analysis and Impact

All results are fixture observations in declared local settings. They are not security odds, certification, or proof of production readiness. Against the synthetic student support profile, 30 of 30 attacks were contained with zero unauthorized mutations. Six of six benign tasks completed, for a 0.0 false denial rate. Reporting utility beside containment stops a system that refuses everything from looking successful.

The same seven attacks and valid tasks were applied to three designs. An unguarded model, tool list, and loop contained none and delivered 28 harmful actions. A prompt guarded arm with a safety instruction and per agent tool allowlist contained 29 percent and delivered eight. This baseline is credible because an allowlist stops some attacks. The full design contained all seven and delivered none while completing the same benign work.

The bounded model checker explored 240 states with zero invariant breaks and reached 11 denial controls. It exposed a flaw in the earlier tests. Attacks that changed expiry, audience, or reviewer role hit the signature check first, so later controls were never reached. Using genuine approvals for the wrong proposal, executor, or transition made each claimed denial reachable. The conformance suite also found that the first SQL evidence adapter failed to enforce its write key. Both flaws became regression tests.

Eight of eight ablated controls restored their matching harm, for authority coverage of 1.0. Twenty five conformance checks pass on two backend profiles. The fixed v1.0.0 baseline has 187 tests and a 32 caller race producing one mutation and one receipt. A separate supplement adds two races of eight processes and four abrupt exit checkpoints on local SQLite. Generated reports preserve the distinction between baseline and supplemental evidence.

The impact serves both halves of the theme. For AI for Learning, the framework supports education services while keeping high impact authority and redress under institutional rule. For Learning for AI, it is a lab: learners mark a boundary, try a violation, inspect refusal and evidence, remove a control, and recover the service. Institutions can share profiles, tests, and recovery patterns without sharing student records. The seven fields also form a supplier question set and adoption checklist for policy, audit, education, and engineering teams.

Open questions include a compromised host or signer, attack rates for named models, reviewer accuracy and work, appeal quality, fairness, access, cost, energy, and independent audit. Logical separation on one host does not prove independent trust.

The packet exercise makes the teaching claim concrete. Altering the target produces an inconsistency. Rewriting recovery context and recomputing its hash remains internally consistent, but fails against the original fingerprint. Without independent custody, a coherent rewrite can evade a local hash check. Learners must explain which evidence supports each conclusion and what remains unknown. The exercise checks artifact behavior; no gains in learner knowledge are measured. Institutions can adapt this lab, publish new cases, and reproduce observations without exchanging personal records or adopting one vendor stack.

The evaluation separates containment from decision quality. Exact approval can stop an unapproved change yet let biased advice reach a reviewer. Domain pilots must add outcome, access, bias, and appeal measures to the security properties. They must report reviewer effort and false denials because blocking valid support can harm students. Six benign fixtures show completion of the specified tasks; they do not prove educational benefit or usability in an institution.

## Conclusion

Trust by Construction changes AI governance from a model promise to a testable boundary around a high impact action. In the student support case, an agent may gather evidence and propose a change, while an authorized person and separate executor decide if that exact change may occur. A changed or stale proposal needs new review. An uncertain result enters reconciliation, not a blind retry. A complete evidence record supports inquiry and appeal.

Adopters can replace the technology without losing the questions. Each capability must name its protected asset, allowed operation, enforcement point, owner, failure test, evidence, and recovery response. The public repo supplies runnable profiles, attacks, valid tasks, ablations, model checking, conformance tests, a replay race, deployment parts, and extension guidance. A new domain inherits the structure but no assurance claim until its tests pass.

Future work will test distributed interleavings, named local models under varied attacks, reviewer work, access, fairness, recovery time, cost, and energy. Pilots must test identity control, key custody, backup restore, evidence retention, and every physical link around a data diode. Even a governed agent can apply an unjust rule faster. This design makes decisions attributable and contestable; it does not make policy fair. That bounded contribution helps institutions decide which powers to delegate and when automation must stop.

## References

Autio, C., et al. (2024). Artificial Intelligence Risk Management Framework Generative Artificial Intelligence Profile. NIST AI 600 1. https://doi.org/10.6028/NIST.AI.600-1

ISO IEC. (2023). ISO IEC 42001 2023 Information technology Artificial intelligence Management system. https://www.iso.org/standard/81230.html

Miao, F., and Cukurova, M. (2024). AI competency framework for teachers. UNESCO. https://unesdoc.unesco.org/ark:/48223/pf0000391104

OWASP GenAI Security Project. (2025). OWASP Top 10 for Agentic Applications 2026. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

Rose, S., Borchert, O., Mitchell, S., and Connelly, S. (2020). Zero Trust Architecture. NIST SP 800 207. https://doi.org/10.6028/NIST.SP.800-207

United Nations. (2024). Global Digital Compact. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact
