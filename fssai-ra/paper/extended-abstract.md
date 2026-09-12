# Trust by Construction: A Testable Architecture for Sovereign AI Agents in Education

**Submission:** Extended abstract, UNU Macau AI Conference 2026 — *AI × Education: AI for Learning, Learning for AI*, 25–26 November 2026, Macau SAR, China.
**Proposed panel:** Agentic AI in the Loop — From Autonomous Tools to Shared Capacity.
**Keywords:** agentic AI; educational administration; institutional sovereignty; fail-secure architecture; human oversight; verifiable governance; digital public goods.
**Reference implementation:** Apache-2.0, `https://github.com/genaiworks/fssai-ra`, release `v1.0.0` for the baseline figures; the oversight, second-domain, and adversary-corpus results below are current-source and published separately.

**Position I will argue on the panel.** Institutions are being sold autonomy and told to add a human. Both halves are wrong. Authority, not autonomy, is the quantity that matters, and it can be specified and tested. Human oversight is not a safeguard you attach afterwards; it is a scarce resource with a ceiling an institution can compute, and above that ceiling "a human approved it" stops being true while every audit log continues to say it is.

## 1. A student asks why

A support application is refused. She asks why — and is entitled to three answers: **who decided this and were they allowed to, what did they see, and how do I contest it.** Somewhere in that process an agent read her file, interpreted eligibility guidance, drafted a recommendation, and called an administrative tool. A sentence inside an uploaded document could have redirected that workflow; so could an ordinary mistake, with no attacker anywhere. From where she stands the two are indistinguishable: an outcome, and no way back in.

That problem is narrower and more useful than "is the AI safe?". The central rule is one sentence: **a model may propose an action; it cannot manufacture the authority to execute it.** Everything below exists to make that rule testable rather than asserted.

Most current answers concern *where the model runs*. Local hosting is necessary for sovereignty and nowhere near sufficient. Sovereignty is better understood as capabilities an institution can exercise and demonstrate: governing data access, replacing models, holding keys, changing policy, producing evidence, and leaving a vendor — none of which a data-centre postcode establishes.

## 2. The contribution: authority as a testable property

The original contribution is the **control contract**: for each consequential capability, seven fields — protected asset, permitted operation, enforcement point, accountable owner, failure test, evidence artifact, failure response. Not documentation convention but a diagnostic: a capability whose seven fields cannot be filled is one nobody is ready to automate. It works unmodified as a procurement questionnaire.

Recording a contract is easy; the harder claim is that it is *enforced*. Three artifacts make it checkable. Randomised property testing puts 6,800 generated tool calls against a predicate written independently of the implementation. A bounded model checker enumerates the profile's declared authority space — every operation, transition, approval variant, version, and identity pairing — runs the real enforcement code against each and checks five invariants, exploring 240 configurations with zero violations. Ablation removes one control at a time to see whether the harm returns, because a control whose removal changes nothing was decorative. A conformance suite re-runs the properties against whatever backends a deployment substitutes.

Each of the three has caught a defect in our own work, which is the only evidence that any of them is doing anything.

## 3. The argument this panel should have: oversight is a finite resource

Every control above routes a consequential action to a named human, then says nothing about what happens when four thousand cases meet eleven officers. That silence is the field's, not only ours, and it is where the "human in the loop" formula quietly fails. An approval requirement is a control only while the person supplying it is still deciding. Push the queue past their attention and every mechanism still passes: digests bind, signatures verify, the evidence is complete — and the oversight it all funnels into has become a signature service. **A system can be perfectly accountable and completely unreviewed.**

So we model review as any scarce safety-relevant resource is modelled: a **declared capacity** per reviewer per window, a **deliberation floor** below which an approval is refused rather than flagged, **mandatory escalation** to a second reviewer under sustained load, and a **published measurement** of headroom. Refusing to *issue* the approval is what makes this a control rather than a dashboard; the action then takes the declared manual fallback.

The consequence is arithmetic an institution can run on its own numbers. With the shipped defaults, a roster of 11 reviewers sustains 2,640 consequential actions per day, bound by the declared quota rather than by reviewer attention. Demand above that line is not a choice between fast and slow review; it is a choice between review and the appearance of it.

We then test it. Forty arrivals reach one reviewer budgeted for eight — five times declared capacity. Some proposals are structurally perfect and substantively wrong: right operation, current version, authentic approval, ineligible applicant. No digest detects that and no invariant excludes it; the only control behind that class of harm is a person who is reading. Without load control, 4 such merit failures execute. With it, 0 do, and 32 actions defer to manual review instead. **That deferral count is the finding, not a defect to tune away** — it is the institution's over-capacity made arithmetic instead of invisible.

One trial with three chosen numbers invites the obvious objection, so we sweep them: across 25 parameter combinations the control was load-bearing in 16 of the 20 where harm was possible, harm reached zero in 16, and it never increased harm in any cell. The 4 non-binding cells are those with no deliberation floor configured, reported rather than omitted. The sweep also caught our own defaults pairing a quota with a floor that contradicted it, throttling reviewers who *were* reading; repairing the declaration drove the false-positive cost to 0. One caveat: the degradation curve is a *declared parameter*, not a measurement of any officer, and observing real reviewers is named open work. What is demonstrated is that given any curve an institution will declare, the ceiling is computable and the control binds at it.

## 4. Does the method travel?

Every figure above was measured on the profile the architecture was designed around — the weakest position from which to claim a *method*. So a second, structurally different education domain was added through the documented extension path: academic record correction, with a multi-role chain, a rejection an appeal can reopen, and its own evidence.

The identical verifier, evaluator, and conformance suite hold on it with no change to library code: 4,800 configurations with zero violations, 30 of 30 scenarios contained, 9 of 9 benign tasks, 25 conformance checks. It also failed on first run, and the defect was real — a declared approval role on a routine transition was silently ignored, because the enforcement map was built only from *consequential* rules. A mandatory schema field, visible to any reviewer, doing nothing at runtime. One domain could not reach it; two did immediately. That is the argument against trusting any single-domain result, including the rest of ours.

## 5. Evidence, with denominators

A containment figure means nothing without a baseline, so identical hostile proposals and identical legitimate work went to three architectures. An *unguarded* arm contained 0% and delivered 28 harmful actions. A *prompt-guarded* arm — a safety prompt plus a per-agent tool allowlist, the two mitigations most commonly deployed — contained 29% and delivered 8. That arm is not a strawman; what it lacks is an enforcement point independent of the model. This architecture contained all seven and delivered none.

Against the reference profile: 30 of 30 adversarial scenarios contained, zero unauthorized mutations, 11 distinct denial controls each exercised, 8 of 8 ablated controls restored their harm when removed, 25 conformance checks passing on 2 backend profiles, a 32-caller race produced 1 mutation and 1 receipt, and 371 deterministic tests run offline in seconds.

One figure matters more than the containment rate: **6 of 6 benign tasks completed, false-denial rate 0.0.** A system that denies everything scores perfectly on containment and is useless. Reporting both is what stops either being optimised alone.

## 6. Shared capacity, made mechanical

Every attack above was written by the people who built the defence — a suite that samples its authors' imagination. So an **open adversary corpus** ships: an attack is seven fields of YAML naming the grant an agent holds and what a compromised model proposes, scored against all three arms and attributed to its contributor. No student record, deployment detail, or vendor name is required, and no contributor code executes. The tool prints how many attacks came from outside the project; today that number is **0**, reported in the output rather than buried in a limitations paragraph. Its first run found a defect in our own *measurement*.

This is the panel's "shared capacity" in concrete form: institutions that cannot pool infrastructure, data, or budget can pool failure cases. For **AI for Learning**, this addresses educational administration, where agentic AI reaches students soonest. For **Learning for AI**, a ninety-minute offline lab ships with it: participants name a boundary, attempt a violation, watch a control refuse it, remove the control, watch the harm return, and compute their own institution's ceiling in a browser tool that sends nothing anywhere. That is the practical judgement UNESCO's competency frameworks ask for. No learning gain is claimed; none has been measured.

## 7. What this does not fix

These are fixture observations in a declared environment: **not security probabilities**, a certification, or evidence of production readiness. **Not yet evidenced:** resistance to a compromised host administrator or signing authority; injection rates for a named model; real reviewer accuracy under load; appeal quality, fairness, accessibility, cost, energy; and any independent audit. Separate containers on one host are **logical separation, not independent administrative trust**.

One caveat belongs in the argument, not a footnote. A perfectly governed agent enforcing an unjust policy produces well-documented injustice, faster. This architecture makes harm **attributable**; it **does not make a rule fair**. What changes is that the student who asked why can be answered.

## 8. Three propositions for the panel

1. **Publish your oversight ceiling before your automation roadmap.** An institution that cannot say how many consequential decisions it can genuinely review per day has not established that it can oversee what it is deploying.
2. **No consequential agent capability without a named authorization boundary, an executable failure test, and a recovery owner.** Publishable for one capability, this quarter, by an institution with no budget.
3. **Trade failure cases, not platforms.** Shared attacks build capacity without moving a single student record — the Global Digital Compact's commitment to digital public goods, in practice.

We are about to hand consequential decisions about people to systems that cannot yet answer her. That is a choice rather than a trajectory, and it is still open.

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
