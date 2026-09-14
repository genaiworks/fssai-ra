# Foundation paper review and revision

The paper has been revised in the repository and exported as a 16-page PDF, editable Markdown, and self-contained HTML. The supplied master prompt was treated as review material; the user's request to enhance the paper and address framework gaps determined the work. No conference submission or external publication was performed.

## What changed in the paper

- Replaced unconditional privacy, mediator independence, erasure, and model-attestation claims with explicit assumptions and evidence boundaries.
- Added the trusted computing base and common-mode failure analysis, exact-purpose semantics, authority intersection, and cross-mediator composition requirements.
- Added GenAI retrieval, memory, cache, vector, handoff, generated-code, multimodal, streaming, tool-server, endpoint, and model-update requirements.
- Specified transactional replay identity, external-effect outbox/idempotency, reconciliation, compensation, revocation ordering, stale-use bounds, budgets, overload and emergency obligations.
- Added rigorous experiment interpretation, matched ablation requirements, utility measures, performance evaluation, education privacy scenarios, an educational study protocol, and operational redress.
- Added 14 grouped closure obligations with accountable roles, evidence and stop conditions; distinguished teaching, shadow and operational pilots.
- Added a 22-entry claims register. No overall implementation percentage is reported because a valid architecture-wide denominator and deployment evidence do not exist.
- Corrected the form-ready abstract's privacy claims while retaining all four field limits. Clarified figure captions as target design, and updated the sanitization reference to NIST SP 800-88 Rev. 2.

The expanded manuscript is a foundation draft. It is not asserted to fit the conference's eventual full-paper page limit. The existing capped submission abstract remains a separate artifact.

## Concrete defects repaired

Severity below is an audit assessment, not an externally assigned vulnerability score. Runtime impact depends on which optional components an adopter uses.

| Severity | Finding | Repair and validation |
|---|---|---|
| High | Model-publisher and evidence-notary default private keys were derivable from public key IDs | Defaults now use cryptographic randomness. Explicit seeds remain available for fixtures. Tests verify keys differ across instances and from the publicly derivable value |
| High | Omitting `now` skipped model-expiry enforcement; non-finite times could bypass comparisons | Omitted time uses the clock; non-finite authorization timestamps deny. Tests cover omitted time, exact expiry, valid use, NaN and infinities |
| High | Erasure verification returned `complete` even with unverified residual locations or no checks | Completion requires nonempty, exclusively absent/unreadable checks; reports explicitly scope results to supplied locations and list unverified locations |
| Medium | The legitimate delegation fixture changed purpose between hops, violating the exact-purpose rule | The fixture now uses one purpose identifier while narrowing actual tool/resource scope. The enforcement rule remains intact |
| Medium | Full-paper metrics lacked the alignment protection claimed by the renderer | Added checks for central full-paper metrics and claims-register evidence paths; broader semantic review remains necessary |
| Low | PDF generation referenced `time` without importing it; the documented privacy extra did not exist | Fixed the import and declared `cryptography` in the privacy extra; built and visually checked the PDF |
| Low | Figure builder omitted strict cardinality checks for parallel lists | Added explicit strict zip checks and verified unchanged generated figures |

No credential was sent externally. Fresh default keys still require production persistence, rotation, and protected custody; randomness alone does not implement a signing service.

## Verification

The baseline suite produced **721 passed and 4 failed**. After repairs and 20 additional checks, the complete suite produced **745 passed, 0 failed, 0 errors, 0 skipped** in 46.40 seconds (pytest console). The JUnit XML is included. Fifteen new cases target security regressions; five target paper evidence alignment.

A separate regeneration check confirmed **126 reported figures** match a fresh run; all **7 paper figures** match their generator. The submission checker accepted all four fields. Lint passed for modified Python files, and `git diff --check` passed. All 16 PDF pages were rendered and inspected, including detailed review of dense tables.

The main synthetic results remain 180/180 hostile action scenarios contained with 58/58 benign tasks, 106/106 hostile disclosure flows contained with 15/15 benign flows, and 104,997 bounded falsification attempts with no counterexample in the declared search spaces. The delegation utility failure has been repaired, not hidden by changing its expected result. Counts of configurations are not independent trials or probabilities of future safety.

## Remaining work that cannot honestly be called solved

The newer privacy wrapper, registry, notary and pack-floor components require explicit binding and end-to-end qualification on the deployed API path. Their presence in source does not establish that every request uses them. Action-delegation and disclosure revocation require separate qualification. The in-process token vault retains sensitive forward-lookup state; neither this revision nor its scoped erasure checker demonstrates memory zeroization or deletion of independently retained key backups. The vector index is a demonstration, not production RAG qualification.

The next implementation gate is a joined education workflow: minimum-necessary student context, registered model selection, exact transcript proposal, authorized mutation, labelled release, evidence and appeal, with negative tests crossing every interface. Before consequential use, complete actual isolation, stale-revocation, crash/retry, backup-restore, tool/egress and independent-checkpoint exercises. Hardware attestation, independent security review, reviewer and learner studies, fairness/accessibility, and institutional cost/energy measurements remain external evidence obligations.

These gaps have concrete design resolutions and acceptance criteria in the revised paper. They have not been relabelled as implemented or empirically closed.

## Reproduction

From the `fssai-ra` directory, using the existing environment:

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/generate_results.py --check
.venv/bin/python scripts/check_submission.py
.venv/bin/python scripts/generate_paper_figures.py --check
.venv/bin/python scripts/build_paper.py
```

The PDF builder requires Chrome or Chromium. Fresh environments can use the documented developer setup and the newly declared privacy extra. This audit used the repository's existing environment; it did not qualify a clean installation on every platform.

For a short demonstration, first show an authorized transcript correction and the exact approval, then a changed-target denial, the delegation comparison, the healthcare disclosure comparison, the ablation results, and the evidence/appeal explanation. Use synthetic fixtures throughout; describe education privacy composition as the next integration requirement rather than a completed live feature.

## Reference correction

The paper now cites [NIST SP 800-88 Rev. 2](https://csrc.nist.gov/pubs/sp/800/88/r2/final), published September 2025, which supersedes Rev. 1. The updated scope avoids equating one deletion API or a successful probe with complete media sanitization.
