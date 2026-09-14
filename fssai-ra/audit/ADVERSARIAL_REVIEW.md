# Pre-repair adversarial review — 2026-09-14

Baseline: 5c587c361cf114125e39344caa6802efd4eaff11 plus preserved author working changes. Original archive and diff were captured before edits. The supplied PDF describes an older base (89fa5af); it is not the current implementation.

The strongest fair objection is that exact signatures authenticate a decision, not its factual basis; separate gates do not establish their composition; and a process that owns its own signing keys, records and ablation switches cannot contain hostile code. Fixture counts can be perfectly reproducible while omitting the path a real caller uses. The education workflow currently conflates a request with an independent case record. Its scripted reviewer checks whether a proposal matches caller-selected values, rather than checking instructor-confirmed evidence. This defeats the claimed educational example without forging any signature. A reference-monitor integration method remains useful, but universal mediation, semantic correctness and deployment isolation are not established by these tests.

## Executed before repair

A01 — implementation defect / unsupported composition claim (paper 3.5, 4, 8.1). Prerequisite: invoke the education orchestration entry point as the nominal support-agent. Sequence: call run_governed_request(student='stu-b7c2'), leaving all controls enabled. Expected forbidden outcome under the paper's assigned-student requirement: another student's context, correction and release. Observed: COMPLETED; register write_log records transcript:stu-b7c2:MATH101 -> grade:B; model input contains that student's grades and attendance; release contains Tomás Ferreira. The implementation has no independently configured assignment at this entry point, so this is a missing policy requirement, not a bypass of an existing assignment check. Fix: authenticate at the joined interface and enforce independently seeded subject scope. Regression: state and sink bytes remain unchanged for wrong subject.

A02 — implementation defect / inadequate experiment (4, 8.1). Sequence: run_governed_request(target_grade='grade:A'). Observed: registrar signature, actual grade:A write and identified release, with no instructor confirmation. The supported marking error exists only as scripted prose. Fix: trusted source reference/version and separate instructor confirmation bound into approval. Regression: false rationale and fabricated source cannot obtain confirmation. Remaining limit: an authorized instructor can confirm a wrong fact.

A03 — trusted-substrate assumption violation (3.4). Source inspection: EducationWorld exposes deterministic credentials, signing services and mutable controls in the same Python process. Generated code with that process's authority can bypass logical checks. Do not classify this as contained. Isolation and real worker identity probes are separate qualification requirements.

A04 — unsupported claim (figures 1–2). Identifiers in tasks, unstructured source text, metadata and rare attributes are not comprehensively anonymized; evidence stores identifiers and operation metadata. Key deletion cannot establish deletion of unknown copies. Repair prose and figures together; do not manufacture an anonymity or erasure result.

A05 — policy-authorized substantive harm (3.5, 7.3). An authentic mistaken instructor and registrar can authorize a bad grade. This is not unauthorized execution. Demonstrate independently observed wrong state and an independently authorized appeal and correction; report semantic harm separately.

## Hypotheses, not baseline exploit results

Stale source/policy/recipient approvals; cross-session cache laundering; shared sibling budgets; duplicate JSON fields; tool redirects; trace/log disclosure; evidence rollback; delayed jobs and streaming revocation. Each needs an executed regression or an explicit exclusion. Monitoring model explanations is neither authentication nor a correctness oracle. Synthetic rationales are not hidden chain-of-thought or a human study.

## Additional executed findings and repairs

A06 — implementation defect in the newly joined reconciliation path (7.8). A committed effect could be queried by the proposing advisor after root revocation because status reconciliation checked holder identity but not current grant. Fixed by rechecking rooted grant, consent and expiry before advisor reconciliation; registrar/appeal roles retain explicit recovery access. Regression extends the cached-revocation test and checks both denial and privileged recovery. Previously released content cannot be recalled.

A03 execution update: a separately spawned process with the mediator's OS user read grade C directly from the synthetic SQLite database. `audit/host-isolation-probe.json` records exit code and returned value. This confirms a trust-assumption violation can bypass the JSON interface; it is not reported as contained. Separate actual production model/worker identities do not exist in this teaching slice.

All named new regressions execute against real local register/SQLite state and controlled sink contents. Unsupported network, code, tool, memory and stream requests are JSON denials; they are not network packet-capture experiments or arbitrary-code sandbox tests. The attack classes listed as unrun in RESIDUAL_RISKS remain qualification gaps.
