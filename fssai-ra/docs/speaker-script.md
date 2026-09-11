# Speaker script

Eight-minute working allocation; confirm the actual panel slot. Main talk: slides 1–11. Technical backup: slides 12–14.

## 1. Trust by Construction

Timing: 20 seconds.
Trust by Construction asks a practical institutional question: what powers should we give an AI agent, and what happens when it gets something wrong? I will use one student-support case to explain a testable architecture and an open reference implementation with 187 deterministic tests, adversarial and utility fixtures, ablations, bounded model checking, backend conformance, and a single-process replay race.
Source: proposed contribution based on the supplied draft. Conference theme and dates: https://unu.edu/macau/news/unu-macau-ai-conference-2026-become-sponsor . The illustration is conceptual and does not depict a real installation.

## 2. A document can influence a decision

Timing: 45 seconds.
Imagine a student applying for support. The agent reads the application and retrieves the university's guidance. One uploaded document contains an instruction to approve the case and export the records. We can ask whether the model notices the attack. But the institution needs a second answer: if the model follows it, what can the system actually do? This synthetic scenario is our running example. We measure the resulting permissions and actions, not just whether the answer sounds safe.
Sources: illustrative scenario created for this proposal; risk context: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

## 3. The boundary of the security claim

Timing: 40 seconds.
Our proposed claim is deliberately bounded. A compromised agent should not obtain powers beyond its assigned case and tools while independent enforcement services remain intact. Local hosting alone does not establish this. We must protect the executor, identity configuration, keys, and evidence administration. A shared root administrator can defeat a single-host teaching setup. We also distinguish authorization from quality: a permitted action can still be based on an inaccurate recommendation.
Sources: proposed assurance scope; https://doi.org/10.6028/NIST.SP.800-207 and https://doi.org/10.6028/NIST.AI.600-1

## 4. Five domains, with explicit responsibilities

Timing: 50 seconds.
The five domains are responsibilities, not a mandatory product stack. Import controls what enters. Transport tracks accepted items through restart and replay. Evidence preserves the data and passages used. Bounded assistance gives the agent only its assigned case and tools. Accountable action puts a separate executor between a proposal and a state change. Identity, policy administration, keys, and evidence custody cross these domains. Their protection determines whether separation is real. A small teaching profile can demonstrate the contract before an institution invests in larger infrastructure.
Sources: original architectural synthesis; NIST zero trust https://doi.org/10.6028/NIST.SP.800-207 . Optional adapter documentation: https://kafka.apache.org/41/design/design/ and https://iceberg.apache.org/docs/latest/maintenance/

## 5. Approval applies to one exact action

Timing: 50 seconds.
The most useful implementation rule is simple: approval applies to an exact action. The officer must see the student case, the proposed change, the evidence, and its limitations. The executor checks the actual target and arguments against that approval, verifies its expiry and authority, and checks the record has not changed. Changing the target or the operation requires a new approval. The model's explanation cannot supply permission. A student's right to correction also needs a human process, because cryptographic approval does not make a policy fair.
Source: proposed authorization contract. Related runtime controls: https://genai.owasp.org/resource/agent-control-standard-acs/

## 6. A test the audience can inspect

Timing: 60 seconds.
Here is the demonstration we plan to publish. An officer approves moving synthetic case S-104 into a review-ready state. We then change the target after approval. The executor should reject the mismatch and leave the register untouched. With the unchanged proposal, it should commit once. Repeating the same execution should return the original outcome without another mutation. We then inspect the evidence. These are expected behaviors, not benchmark results. The final demonstration must show actual captured output from a named release. A scripted malicious request tests enforcement; a separate model experiment tests whether injection can induce that request.
Source: proposed synthetic demonstration protocol.

## 7. When automation must pause

Timing: 40 seconds.
Fail-secure behavior has a service consequence. If the required authorization or intent-evidence service is unavailable, the system must not start a consequential automated action. But a student should not lose access to support. A named manual route handles urgent cases with its own authority and records. If a failure occurs after a change may already have committed, we reconcile the outcome before retrying. We cannot assume every external action is reversible. Continuity and recovery are part of the design, not exceptions hidden in a runbook.
Source: proposed failure and continuity contract.

## 8. Evidence that supports a challenge

Timing: 45 seconds.
An audit record should help someone understand and challenge a result. We retain the actual sources and passages used, the recorded recommendation, the policy decision, the exact approval, and the action receipt. A hash is only useful if the referenced content remains available. We also need independent checks for missing or truncated history. Reconstruction is different from generating identical text again. Protect the evidence itself, because excessive logging can create another collection of sensitive student information. A human correction should become part of the case history.
Sources: proposed evidence specification; snapshot retention context: https://iceberg.apache.org/docs/latest/maintenance/

## 9. Testing containment and useful assistance

Timing: 50 seconds.
We will compare model-only guardrails, the complete declared configuration, and variants that remove one control. The same tasks and attack inputs will run in a synthetic sandbox. We count prohibited actions and disclosures, but also legitimate completion, false denials, evidence reconstruction, approval delay, and staff effort. A system that refuses everything is not a useful success. We will publish denominators, configurations, and uncertainty. Zero observed violations only describes the tested sample. We report no completed benchmark in this abstract.
Sources: proposed evaluation design; risk context https://doi.org/10.6028/NIST.AI.600-1 and https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

## 10. An open testbed for shared capacity

Timing: 55 seconds.
The public GitHub release joins the contract, synthetic workflow, executable tests, assurance matrix, domain-profile template, command-line evaluator, and extension instructions. Its exact-action path authenticates approval fields, accepts only trusted teaching keys and profile-allowed transitions, returns the original receipt on retry, and surfaces interrupted outcome evidence for reconciliation. Institutions can start with one service and one accountable owner. The laptop profile teaches the boundaries; a pilot needs durable stores, stronger administrative separation, and local operational review. Students and staff can identify a trust boundary, test it, inspect the evidence, and compare machine-readable results. That connects AI for Learning with Learning for AI. Institutions can share tests and improvements without sharing student records. Costs, reviewer burden, and energy use must be measured locally.
Sources: proposed release plan; conference theme https://unu.edu/macau/news/unu-macau-ai-conference-2026-become-sponsor ; capacity context https://www.unesco.org/en/articles/ai-competency-framework-teachers and https://www.un.org/pact-for-the-future/en/annex-i-global-digital-compact

## 11. A concrete request for your next AI pilot

Timing: 25 seconds.
For the next agent your institution adopts, ask for a failure test. Show the action it must refuse, the evidence you will retain, and who restores the service. That is a concrete place to begin shared capacity. Our proposed open testbed gives institutions a way to practice and compare those obligations. Thank you.
Source: author's proposed institutional adoption criterion.

## 12. Trusted components and remaining risks

Backup slide.
The specified attacker can control an input document or the agent process. The assurance depends on intact enforcement and protected control-plane administration. Shared-host root access, compromised identity/key administration, or colluding control owners can defeat these assumptions. Formal authorization does not ensure the truth of evidence or the fairness of eligibility policy. Manual continuity must not become an unlogged administrative bypass. A release report should identify control dependencies and deployment-specific exclusions.
Sources: proposed threat model; https://doi.org/10.6028/NIST.SP.800-207 and https://doi.org/10.6028/NIST.AI.600-1

## 13. Deployment profiles carry different assurance

Backup slide.
The teaching profile uses synthetic data and may share a host. It must disclose that weakness. The institutional profile separates operational roles, credentials, policy administration, and evidence custody and requires recovery exercises. A hardware-isolated profile adds an import gateway where justified. Its physical directionality concerns the specified link only; all other paths still need control. Kafka, Spark, and Iceberg are optional adapters when scale requires them. Passing a smaller profile does not establish the larger profile's guarantees.
Source: proposed deployment profiles; adapter references https://kafka.apache.org/41/design/design/ and https://iceberg.apache.org/docs/latest/maintenance/

## 14. Positioning within existing work

Backup slide.
This contribution applies established principles. NIST supplies risk and authorization foundations. OWASP supplies agent threat guidance and portable runtime control work. Our proposed contribution connects these to one educational workflow, testable authority boundaries, evidence reconstruction, human review, and recovery ownership. We do not claim first-of-kind architecture, OWASP ACS compatibility, certification, or measured results. Any ACS adapter would need conformance testing.
Sources: NIST SP 800-207 https://doi.org/10.6028/NIST.SP.800-207 ; NIST AI 600-1 https://doi.org/10.6028/NIST.AI.600-1 ; OWASP Agentic Top 10 https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/ ; OWASP ACS, resource page published 1 September 2026, https://genai.owasp.org/resource/agent-control-standard-acs/
