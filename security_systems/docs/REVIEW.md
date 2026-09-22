# Conference judge and adversarial code review

Reviewed September 21, 2026. Scope: `security_systems`, including the two conference proposals, public guard, evaluation design, evidence, and presentation run sheet. This is a focused review and hardening pass, not an exhaustive independent security audit.

## Recommendation

Present this as a reproducible engineering experience report. The artifact and live failure demonstrations support a practitioner talk. The current evidence does not support a broad claim that the system solves agent security, outperforms RBAC generally, or is production-ready across regulated industries. A research-paper claim would need stronger baselines, external attacks, realistic benign workloads, and deployment measurements.

The AIE package now contains three distinct submissions at the author’s request: deployment approval, security evaluation, and a disclosure workshop. Each has its own audience outcome and can stand alone. The AI Con proposal remains a separate, longer evaluation session.

## Judge's critique and changes

| Concern | Why a reviewer would object | Revision |
|---|---|---|
| “Per-hop auth caught 2/10” as a universal headline | The baseline intentionally implements fewer checks; it is not a general RBAC benchmark | Use an engineering problem as the title and name the authored baseline in the abstract |
| Too many mechanisms for one talk | Nine invariants, cryptography, four domains, attacks, and governance cannot all receive depth in 20 minutes | AIE follows one software-delivery workflow; AI Con gets the evaluation method |
| Unclear novelty | Delegation attenuation and information-flow labels have extensive prior art | Position executable integration and failure analysis as the contribution; add primary references |
| Four domains presented as independent validation | All reuse the kernel and attack cases | Describe policy parameterization, not field validation |
| “Exactly once” without a failure boundary | In-memory callback receipts do not survive process loss or coordinate arbitrary external effects | State single-instance replay semantics and reconciliation requirements |
| Correct kernel equated with secure integration | New attacks defeated the public wrapper while the original suite passed | Add wrapper regressions, fix the bypasses, and feature this lesson in both talks |
| Ablation denominator ambiguous | 29 includes two paired removals; not all are single-control experiments | Explicitly report 27 single removals plus two pairs, with 25 harmful configurations |
| Unverified credentials and readiness claims | A test count, academic submission, public repo, and demo time can become stale or unverifiable | Remove unverified publication and timing claims; keep evidence and author checklist separate |

## Code changes and evidence

`src/trustkernel/guard.py` now validates issued context handles, checks replayed approvals before returning cached data, binds strict JSON arguments using full SHA-256, snapshots mutable arguments, rejects high-impact registrations without an approval role, generates instance-specific delegation secrets, and labels declared reads before callbacks execute.

A new adversarial test file initially produced **10 failing cases and one passing concurrency control** against the original wrapper. After fixes and additional coverage, the wrapper tests pass. The existing unrooted-context test now expects refusal at spawn, where the forged parent is rejected earlier.

Validation in an isolated Python 3.14.6 environment:

- Original suite: **203 passed**.
- Expanded suite: **218 passed**, including all four evidence-regeneration comparisons and whole-demo tests.
- Ruff: **all checks passed**.
- Offline seven-scene demo and guarded-agent example: executed successfully.

Installed review dependencies: PyYAML 6.0.3, cryptography 50.0.1, pytest 9.1.1, Ruff 0.16.8. This review did not run the suite on every advertised Python version or against a real model service. No benchmark numbers were changed by hand.

## Remaining limits that must be stated accurately

The guard is trusted in-process code, not a sandbox or a ready-made authenticated service. Administrative issuance methods remain privileged. Context registry checks reject modified handles but cannot authenticate whoever presents a valid stolen handle. The dispatcher must bind an authenticated caller to the server-side context.

Approval identity and role inputs are stand-ins for an authenticated human service. HMAC delegation in one guard does not establish per-principal private-key custody. The full reference worlds exercise controls that the decorator does not expose, including read-grant revalidation at write time and signed evidence checkpoints.

Labels rely on trusted `reads` metadata and explicit handoff propagation. Raw network access and uninstrumented logs are outside the guard. Callback execution, receipt storage, and external state are not one durable transaction. Memory retention, restart recovery, and multi-process coordination need deployment design.

The measured attackers use a fixed grammar and authored fixtures. One legitimate delegation chain is too little to estimate false denials. No latency distribution, independent stronger comparator, held-out attack corpus, or production deployment study was added. Do not substitute the test count for those missing experiments.

## Submission readiness

The three AIE proposals and separate AI Con proposal are drafted and mapped to their intended audiences. The AIE document follows the supplied fields exactly: Session Title, Description, Session format, Special Flags, Speaker/Session Pitch, and Possible Tracks. Track names are suggestions until matched to the actual dropdown.

Before sending, the author needs to confirm the biography and add an anonymously accessible artifact/release URL. A short demo recording would strengthen the application. No submission, publication, or message to organizers was made during this work.

The official [AIE CFP](https://sessionize.com/aiecode26/) lists 15–20-minute stage talks and an October 11, 2026 closing date. [TechWell's speaker guidance](https://www.techwell.com/software-conferences/be-a-speaker) lists AI Con's October 18, 2026 deadline and standard one-hour sessions including ten minutes of questions. The revised outlines follow those limits.
