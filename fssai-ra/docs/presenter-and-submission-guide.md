# Presenter and submission guide

## Recommended positioning

**Paper title:** From Model Literacy to System Literacy: Teaching Trust by Construction for Agentic AI

**Spoken title:** From Model Literacy to System Literacy

**One-sentence contribution:** We propose a way for institutions to specify, test, and teach the boundaries of an AI agent's authority, using a student-support workflow and a reproducible open testbed.

**The audience's takeaway:** For every consequential capability, identify the independent authorization check, run a failure test, and name the person responsible for recovery.

The strongest part of the contribution is the connection between a governance requirement and observable system behavior. Make that connection visible throughout the talk. An architecture diagram by itself will not distinguish this from a conventional security presentation.

## Conference and submission context

The invitation requests an extended abstract by **21 September 2026**. It describes shortlisting for consideration as a panelist and proceedings development, rather than final acceptance. The official Microsoft Form requires four separately pasted fields: Introduction, strictly 200–250 words; Development Section 1, 550–650 words; Development Section 2, 550–650 words; and Conclusion, strictly 200–250 words. References are entered separately. Its text boxes also expose character caps of 1,500, 3,900, 3,900, and 1,500. The form-ready revision fits both sets of constraints. Run `python scripts/check_submission.py` immediately before pasting.

UNU's published conference announcement confirms **25–26 November 2026** and the theme **“AI × Education: AI for Learning, Learning for AI.”** The supplied draft identifies Panel 2 as “Agentic AI in the Loop: From Autonomous Tools to Shared Capacity.” That panel title comes from your material; the linked conference landing page could not be retrieved during this review. The public book-series page confirms the series' scope but does not independently establish acceptance or publication of this particular contribution.

Sources: [UNU conference announcement](https://unu.edu/macau/news/unu-macau-ai-conference-2026-become-sponsor), [UNU–Springer series](https://unu.edu/macau/announcement/book-series-aisd). Submission length and deadline come from your invitation.

Before sending, add the actual author name, affiliation, corresponding email, and professional title. The form separately requires confirmation that the author respected each word limit and that the work is original. References have no displayed word limit. The repository should be public and verified in a signed-out browser before its URL is included in the submitted text.

The v1.0.0 baseline records 187 collected tests. Its JSON reports cover adversarial containment, benign utility, ablations, bounded model checking, backend conformance, and a 32-caller single-process replay race. Current-source enhancements add two independent-process races, four abrupt-exit recovery fixtures, and proposal-digest checks for replay identity. They are published separately in `evaluation/results/resilience-student-support.json` and documented in `docs/RESILIENCE.md`. Do not attribute these enhancements to the unchanged v1.0.0 tag. Broader stochastic attacks, power-loss and distributed recovery, reviewer burden, cost and energy evaluation remain open work.

## What changed and why

| Original issue | Revision | Why it matters |
|---|---|---|
| Broad sovereign-AI framing with education near the end | Student-support case opens and anchors the contribution | Establishes conference relevance immediately |
| “No single compromised ... layer” can escape containment | Defined compromised-agent threat model and explicit trusted enforcement services | A shared administrator or enforcement compromise can otherwise invalidate the promise |
| “None specifies” an end-to-end arrangement | Integration and evaluation contribution that acknowledges existing guidance | Avoids an unsupported novelty claim, especially after OWASP's recent ACS publication |
| Hardware gateway appears mandatory | Teaching, institutional, and optional hardware-isolated profiles | Makes adoption feasible without conflating a laptop demo with hardware assurance |
| Human approval is a general safeguard | Approval binds to the exact operation and evidence version | Gives builders an implementable rule and the audience a memorable test |
| Append-only evidence sounds sufficient | Separate custody, continuity checking, pre-action receipt, and reconciliation | Addresses deletion, truncation, shared credentials, and uncertain outcomes |
| Snapshot rollback implies recovery | Retain actual data and distinguish record restoration from compensation | A manifest cannot restore deleted inputs; a sent message cannot be unsent |
| Eight fixtures sound like comprehensive evaluation | Report the exact denominator and synthetic boundary; retain the broader protocol | Prevents unsupported empirical claims |
| Open source appears as a future promise | Concrete release contents and acceptance gates | Makes the public contribution reviewable |

OWASP's [Agent Control Standard page](https://genai.owasp.org/resource/agent-control-standard-acs/) was published on 1 September 2026. The [2026 LLM Top 10 resource](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/) also exists, while the general LLM archive still displays the 2025 list. Use edition-specific links and verify exact ranking statements before citing them. The revised abstract uses the agentic edition without unnecessary ranking claims.

## Opening you can deliver without slides

“Imagine a student applying for support. A university agent reads the application, retrieves the rules, and prepares a recommendation. Now imagine that one uploaded document tells the agent to approve the case and send the student's records elsewhere. We can ask whether the model notices the attack. But the institution needs a second answer: if the model follows it, what can the system actually do?

“Our proposal starts at that boundary. The agent may prepare a case. A separate service checks the action. A named officer holds consequential authority. And the student has an explanation and a route to challenge the result. We want to make those obligations testable.”

This is an illustrative scenario. Do not describe it as an observed breach or an existing deployment.

## Talk lengths

**Present from [`docs/presentation/slides.html`](presentation/slides.html).** It is the maintained deck: 23 slides in about fourteen minutes, plus two backup slides for questions. Its figures are checked against `scripts/generate_results.py` by `tests/test_paper_alignment.py`, so a stale number on a slide fails the build. The matching timed script is [`presentation/speaker-script.md`](presentation/speaker-script.md), and its four timing paths are checked against the deck by the same test file. Press `⌘P` in the deck for a PDF to carry as the podium backup.

`docs/trust-by-construction-final.pptx` and its script `docs/speaker-script.md` are a **superseded v1.0.0-era pair**, kept for provenance. They contain no oversight ceiling, no second domain and no adversary corpus — that is, none of the three contributions this submission leads with. Do not rehearse from them.

The allocation paths live in the script rather than here, so there is one table to keep correct:

| Allocation | Slides | Delivery |
|---|---|---|
| 5 minutes | 1, 2, 5, 14, 15, 19, 20, 23 | The rule, the person, the contract, the oversight ceiling, the limits, the close |
| 8 minutes | 1, 2, 4, 5, 7, 12, 14, 15, 18, 19, 20, 23 | Add the architecture, the demonstration and the controlled comparison |
| 10 minutes | 1, 2, 4, 5, 6, 7, 8, 12, 14, 15, 18, 19, 20, 21, 22, 23 | Add privilege invariance, the counterfactual, the theme and the ask |
| 14 minutes | 1–23 | Complete narrative |

Slides 19, 20 and 23 are never cut, and slides 14 and 15 are the oversight argument that earns the panel slot.

For a discussion-only panel, use the opening above and three concrete examples: a changed action invalidates approval; an evidence outage pauses consequential automation; a student can request a correction. Avoid naming Kafka, Spark, or Iceberg unless the moderator asks about implementation.

## Demonstration: approval applies to an exact action

Use synthetic student S-104 and a fictional support unit, “Campus Support.” The mock tool writes only to a sandbox case register. A legitimate proposal changes the case status from `draft` to `ready_for_officer_review`; the agent may draft it but the demo policy requires officer approval to commit this change. A later award decision would be a distinct, separately authorized operation.

1. Show the original case and the exact proposed change. Explain the precondition: the case must still be at the reviewed version.
2. Show an authorized officer approving that exact proposal. The approval includes the action digest, officer identity, case version, expiry, and a unique identifier.
3. Change the target to a different student or change the requested status after approval. Attempt execution. The expected result is `APPROVAL_PAYLOAD_MISMATCH`, with no case mutation.
4. Execute the unchanged original while the approval is valid. The expected result is one recorded transition and a verifiable receipt.
5. Retry the same request. The expected result is the original execution result, with no second mutation. Reusing the approval under a different request identifier must fail.
6. Open the evidence bundle: exact proposal, policy version, reviewed record version, approval, execution receipt, and resulting state.

These behaviors are implemented and tested against synthetic records. A scripted malicious tool request tests the boundary reliably, but it does not prove that a live model succumbed to prompt injection. Report that distinction.

Keep the live segment below one minute. Rehearse on an offline machine and carry a recording of an actual run plus its release tag. Use the fixture denominators shown in the versioned result files; do not imply that they are field benchmarks.

## Questions to prepare for

**Is this just zero trust with an LLM added?**  
The security principles are established. The contribution is their integration into an education-specific control contract, with executable failure tests, evidence reconstruction, recovery ownership, and teaching materials. We will assess whether that integration improves containment at an acceptable operational cost.

**How is this different from OWASP ACS?**  
ACS describes portable hooks and runtime policy controls. This proposal can use such interfaces. It also specifies the institutional workflow, custody of decision evidence, reviewer responsibilities, recovery, deployment assumptions, and the empirical evaluation. Compatibility needs testing before we claim it.

**Why call it sovereign if the model comes from another country?**  
The working definition concerns effective institutional control and the ability to replace dependencies. Model origin alone does not settle data access, key custody, operator access, licensing, or service continuity. The release should disclose those dependencies.

**Does a local model prevent data leakage?**  
No. Disclosure can occur through allowed tools, user responses, logs, telemetry, operator access, and other paths. The proposed model is one component in an access-controlled workflow. Each output channel needs an explicit policy.

**Does the data diode stop prompt injection?**  
No. Hostile instructions can enter in text. A diode constrains direction on a particular link. It does not establish the truth of imported information or authorize actions, and it does not close every other interface.

**What if the policy service or administrator is compromised?**  
That reaches the stated trust assumptions. We must identify what authority that compromise grants and which separately administered controls remain effective. A teaching deployment sharing one host cannot claim resistance to that host's administrator.

**Is human approval just a rubber stamp?**  
It can become one. Review needs source evidence, a precise change description, workload limits, relevant expertise, and the power to refuse. We will assess misleading recommendations and reviewer effort, rather than treating the presence of an approval button as proof of effective oversight.

**Can the model still cause harm inside its permissions?**  
Yes. A formally authorized recommendation can be inaccurate or discriminatory. Domain checks, quality evaluation, restricted autonomy, staff responsibility, and accessible appeal remain necessary. Security tests alone cannot demonstrate educational benefit.

**Does fail-secure behavior deny students services?**  
It can if the service is designed poorly. An outage pauses the automated consequential action, while a separately governed manual route handles urgent cases. That route must record its own decisions and reconcile them before automation resumes.

**Can you reproduce the decision exactly?**  
We aim to reconstruct the evidence and recorded action. Exact regeneration of model text may fail because inference can be nondeterministic. Preserve the actual retrieved passages, inputs and outputs, and versions needed to examine the original decision.

**Will a laptop run it, and is local inference greener?**  
The teaching profile should support a deterministic stub and, optionally, a suitably sized local model. Actual hardware requirements must come from measurement. Energy comparisons must include utilization, hardware, and operational conditions; no environmental advantage has yet been established.

**What evidence do you have today?**  
The fixed v1.0.0 baseline contains 30 of 30 adversarial fixtures and completes six of six benign tasks, with eight control ablations, 240 bounded configurations, 25 conformance checks on two backend profiles and a single-process replay race. The current-source supplement adds independent-process races and abrupt-exit recovery. These are synthetic fixture observations. The repository publishes denominators, source fingerprints and limits. It does not demonstrate learner benefit or production readiness.

**What changed after v1.0.0, and which code should adopters use?**

The enhanced source binds every stored receipt to its full proposal digest, rejects conflicting request-ID reuse, and adds process/recovery checks. Use a reviewed source commit containing these changes rather than assuming the old tag includes them. Historical receipts without the digest require authorized reconciliation before automated replay. Preserve the baseline tag for reproducing the original figures.

## Recommended preparation schedule

These are proposed work milestones, not assertions that the work is underway or promises already made to the organizers.

| Date | Concrete deliverable |
|---|---|
| 9–14 September | Finalize use case, author information, scope, threat assumptions, and references |
| 15–18 September | Technical and education-domain review of the abstract; resolve comments |
| 19–20 September | Final word count and submission-format check; submit before the 21 September deadline |
| 22 September–11 October | Recruit independent reproduction and education-domain reviewers; run adapter qualification |
| 12–31 October | Evaluate realistic model attacks, human review, manual continuity and distributed failure modes |
| 1–15 November | Independent reproduction, reviewer exercise, documentation, and GitHub release candidate |
| 16–22 November | Freeze the demonstration, record the fallback, rehearse the confirmed speaking allocation |
| 25–26 November | Deliver the contribution with release status and results labeled accurately |

## Closing line

“For the next agent your institution adopts, ask for a failure test: show the action it must refuse, the evidence you will retain, and who restores the service. That is a concrete place to begin shared capacity.”

## Artwork

The cover uses a conceptual illustration of architectural boundaries, generated using the built-in image-generation tool. It does not depict a real installation. The asset is saved at `assets/trust-boundaries-cover.png` alongside these deliverables. The complete generation prompt is in `assets/cover-prompt.txt`.
