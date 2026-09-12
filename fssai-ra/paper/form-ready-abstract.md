# From Model Literacy to System Literacy: Teaching Trust by Construction for Agentic AI

**Proposed panel:** Agentic AI in the Loop - From Autonomous Tools to Shared Capacity
**Keywords:** agentic AI; educational administration; institutional sovereignty; fail-secure architecture; human oversight; verifiable governance; digital public goods
**Reference implementation:** https://github.com/genaiworks/fssai-ra (release v1.0.0 for baseline figures, plus current-source supplements; record the reviewed commit at submission)

> Paste each section below into the matching form field. Headings are field
> labels, not prose. Run `python scripts/check_submission.py` before submitting.

## Introduction

A student's support application is refused. She asks who decided, what they saw, and how she can contest it. Somewhere in that process an agent read her file, applied policy, drafted a recommendation, and called an administrative tool. A malicious instruction hidden in an uploaded file could have redirected it. So could an ordinary model error, with no attacker. From where she stands the two are the same: an outcome, and no way back in.

This work asks a narrower question than whether AI is trustworthy: what stops a wrong or compromised agent from turning its own proposal into institutional authority? It presents Trust by Construction, a fail-secure architecture for sovereign AI agents in education. Its central rule is one sentence: a model may propose an action; it cannot manufacture the authority to execute it.

The contribution is an executable control contract. For every consequential capability it names the protected asset, permitted operation, enforcement point, accountable owner, failure test, evidence artifact, and recovery response. It turns system literacy from vocabulary into something a learner can demonstrate.

The argument I bring to the panel goes further. Institutions are being sold autonomy and told to add a human. Human oversight is not a safeguard bolted on afterwards; it is a finite resource with a ceiling an institution can calculate, and above that ceiling "a human approved it" stops being true while every audit log continues to say it is.

## Development Section 1 Methodology Core Argument and Case Context

The method joins an education case with executable assurance, informed by zero trust, NIST, OWASP, ISO/IEC 42001, and UNESCO's AI competency framework. Each governance duty becomes behaviour another institution can test after replacing parts.

The control contract is machine-readable. Its seven fields are mandatory, and each check names the requirement it defends. Teams begin with one consequential capability and manual fallback, writing the failure test before connecting real records or keys. If the fields cannot be filled, nobody is ready to automate it.

This becomes five-part system literacy: trace data and versions; distinguish proposals from delegated powers; verify controls independently of the model; make escalation capacity explicit; and reconstruct accountability through a correction route. Learners produce artifacts or failures for each, not definitions. Each learner must also state the limit of the evidence they produce.

The reference case uses synthetic student-support records. An agent may fetch evidence for an assigned case, draft an explanation, and propose moving it from draft to officer review. It cannot approve an award, widen its own access, delete evidence, or hold the key that changes the case register. A named officer retains authority, and the institution remains responsible for policy and fairness.

Five domains organise the design. Controlled import validates source, type, size, schema, and signature through a no-read-back software seam a certified diode can replace. Transport uses stable identifiers and replayable events. Reproducible data preserves snapshots, transforms, retrieved text, model identity, proposal, approval, and outcome. Bounded intelligence narrows identity and tools. Accountable action keeps the write credential outside the model process.

An approval binds to a proposal digest covering the operation, target, states, evidence version, requester, and resource version, with the reviewer role, audience, and expiry also authenticated. The executor rechecks every field before mutation and reads the review class from a deployment catalogue, never from the model's own label.

Two additions answer questions this architecture previously could not. First, review load is modelled as a scarce safety-relevant resource: a declared capacity per reviewer per window, a deliberation floor below which an approval is refused rather than flagged, mandatory escalation to a second reviewer under sustained load, and a published measure of remaining headroom. Refusing to issue the approval, rather than recording a concern afterwards, is what makes this a control instead of a dashboard. Second, because every result had been measured on the one profile the architecture was designed around, a structurally different education domain was added through the documented extension path: academic record correction, with a multi-role chain, a rejection an appeal can reopen, and its own evidence rather than the first domain's.

Assurance is checked four ways, each answering a question a hand-written test suite cannot. Randomised property testing compares generated tool calls against a predicate written independently of the implementation. Bounded model checking enumerates the profile's declared authority space, runs the real enforcement code against every configuration, and checks five invariants: the combination nobody imagined. Ablation removes one control at a time and measures whether the harm returns, because a control whose removal changes nothing was decorative and the assurance matrix should stop claiming it. A portable conformance suite re-runs the properties against whatever backends an institution has substituted, naming for each check the requirement it defends, so a failure states which claim was lost rather than merely turning red.

## Development Section 2 Results Analysis and Impact

All results are fixture observations in declared local environments: not security probabilities, a certification, or evidence of production readiness.

Against the synthetic student-support profile, 30 of 30 adversarial scenarios were contained with zero unauthorised mutations, and 6 of 6 benign tasks completed for a false-denial rate of 0.0. Reporting utility beside containment stops a system that refuses everything from looking successful. Bounded model checking explored 240 configurations with zero invariant violations, reaching 11 distinct denial controls. Eight of eight ablated controls restored their harm when removed: authority coverage 1.0. Twenty-five conformance checks passed on two independent backends, and a 32-caller replay race produced one mutation and one receipt.

The same hostile proposals and legitimate work went to three architectures. An unguarded agent contained none and delivered 28 harmful actions. A prompt-guarded arm, adding the two mitigations most widely deployed today, contained 29 percent and delivered 8. That arm is a fair account of practice, not a strawman: an allowlist is a real control that lacks enforcement independent of the model. The full architecture contained all seven and delivered none, at no cost to benign completion.

The oversight results are the new contribution. With shipped defaults, a roster of 11 reviewers sustains 2,640 consequential actions per day, bound by the declared quota rather than by attention. In a queue trial, 40 arrivals reach one reviewer budgeted for 8. Some proposals are structurally perfect and substantively wrong: correct operation, current version, authentic approval, ineligible applicant. No digest detects that and no invariant excludes it; the only control behind that harm is a person who is reading. Without load control, four such failures execute. With it, none do, and 32 actions defer to manual review. That deferral is the finding, not a defect to tune away: it makes over-capacity arithmetic instead of invisible. One caveat is essential: the degradation curve is a declared parameter, not a measurement of any officer; observing real reviewers is open work.

The second domain repaid the effort at once. The identical suite holds with no library change: 4,800 configurations with zero violations, 30 of 30 scenarios contained, 9 of 9 benign tasks, 25 conformance checks. It also failed on first run, and the defect was genuine. A declared approval role on a routine transition was silently ignored, because the enforcement map was built only from consequential rules. The field was mandatory in the schema, visible to any reviewer, and absent at runtime. One domain could not reach it; two did.

Because every attack was written by the people who built the defence, an open adversary corpus now ships. A contributed attack is seven fields of YAML, scored against all three architectures and attributed to its contributor. No student record or vendor name is needed, and no contributor code runs. The tool prints how many attacks came from outside the project; today that number is zero, stated in the output rather than buried in a limitation.

For AI for Learning, this governs administration. For Learning for AI, it teaches system literacy: trace data, bound delegation, verify controls, calculate escalation capacity, and reconstruct accountability. Participants violate a boundary, watch refusal, remove the control, and watch harm return. Institutions unable to pool infrastructure can pool failures. No learning gain is claimed; none has been measured.

Open questions remain: a compromised host or signing authority, injection rates for named models, reviewer accuracy under load, appeal quality, fairness, cost, energy, and independent audit. Separate containers on one host are logical separation, not independent administrative trust.

## Conclusion

Trust by Construction moves AI governance from a promise about a model to a testable boundary around a high-impact action. In the student-support case an agent may gather evidence and propose a change, while an authorised person and a separate executor decide whether that exact change may occur. A changed or stale proposal requires fresh review. An uncertain outcome enters reconciliation rather than a blind retry. A complete evidence record supports inquiry and appeal.

Three propositions follow, and I offer them to the panel as claims to argue with. First, an institution should publish its oversight ceiling before its automation roadmap; one that cannot say how many consequential decisions it can genuinely review per day has not established that it can oversee what it is deploying. Second, no consequential agent capability should ship without a named authorisation boundary, an executable failure test, and a recovery owner, which any institution can publish for one capability this quarter with no budget. Third, institutions should trade failure cases rather than platforms, since shared attacks build capacity without moving a single student record.

Even a perfectly governed agent can apply an unjust rule faster. This architecture makes harm attributable and contestable; it does not make a rule fair. That bounded contribution still answers the student who asked why, and it helps institutions decide which powers to delegate and when automation must stop.

## References

Autio, C., et al. (2024). Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile. NIST AI 600-1. https://doi.org/10.6028/NIST.AI.600-1

ISO/IEC. (2023). ISO/IEC 42001:2023 - Information technology, Artificial intelligence, Management system. https://www.iso.org/standard/81230.html

Miao, F., and Cukurova, M. (2024). AI competency framework for teachers. UNESCO. https://unesdoc.unesco.org/ark:/48223/pf0000391104

OWASP GenAI Security Project. (2025). OWASP Top 10 for Agentic Applications 2026. https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

Parasuraman, R., and Manzey, D. (2010). Complacency and bias in human use of automation: an attentional integration. Human Factors, 52(3), 381-410. https://doi.org/10.1177/0018720810376055

Rose, S., Borchert, O., Mitchell, S., and Connelly, S. (2020). Zero Trust Architecture. NIST SP 800-207. https://doi.org/10.6028/NIST.SP.800-207

United Nations. (2024). Global Digital Compact. https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact
