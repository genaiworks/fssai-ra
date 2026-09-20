# Trust by Construction — completion report

Completed 14 September 2026. The revised 24-page paper and runnable reference artifact are delivered. The revision addresses the identified design gaps with concrete controls, tested repairs, and explicit acceptance gates. It does not claim to solve every possible rogue-AI behavior.

## Final verification

| Check | Executed result |
|---|---|
| Full pytest suite | **963 passed; 0 failures, errors or skips**, 92.06 seconds |
| Ruff: src, tests, scripts, jobs, adapters | Passed |
| Fresh result generation | All 126 figures matched committed results |
| Final paper/conference alignment plus contemporary regressions | 146 passed |
| Contemporary mechanism regressions | 18 passed, including 16 denial cases with successful legitimate follow-through |
| Final PDF | 24 pages rendered and visually inspected |

Logs and JUnit records are under `audit/latest-*`; individual contemporary cases are in `audit/modern-threats.json`. Historical baseline and earlier experiment results retain their original dates, counts and limitations in `audit/FINAL_REPORT.md`. Full-suite execution does not establish that every optional real infrastructure integration was exercised. Newly supplied GitHub CI was not executed remotely.

## What changed

The initial audit found an unassigned-student correction/release and an unsupported grade correction accepted by the demonstration driver. Repairs deny both and add a durable authenticated SQLite workflow: scoped context, independent source confirmation, exact approval, current execution and release, shared delegation budgets, evidence, revocation, reconciliation and appeal. Their regression tests check records and sink bytes. Intervening author commits also repaired private-key construction and execution-time context checks; those changes were preserved.

The paper now incorporates ten additional recent primary sources, distinguishes incident disclosures from laboratory studies, and adds twelve secure design patterns. These cover scoped authority, process separation, destination-bound egress, source provenance, tool integrity, memory labels, shared agent budgets, atomic effects, independent shutdown, publication approval, protected evaluation infrastructure, and privacy/redress. Statements about identities, evidence, erasure, exactly-once execution and stronger future models are qualified to match actual evidence. Reasoning and monitor claims never substitute for authorization.

The runnable education and benefits demonstrations include actual state and receipts, control enabled/disabled/restored comparisons, and recovery. The package includes static/random/adaptive search and genuine tabular-Q evaluation, with 1,200 training episodes and 480 evaluation episodes. This is small-policy learning, not language-model reinforcement learning. Four live local-model probes include a legitimate-task JSON failure; that failure remains reported. Deny-all and competent server-authorization baselines expose utility and semantic-correctness differences.

## Separate verdicts

1. **Repository and demo reproducibility: PASS within the tested local environment.** Clean no-install standalone demo and adaptive reproduction were executed earlier; current full-suite, lint, paper-alignment and result checks pass. Setup and commands are in `audit/QUICKSTART.md`.
2. **Security properties: verified only within executed boundaries.** Tested scoped authorization, version binding, source confirmation, replay, budgets and release checks survived bounded regressions. The new incident-inspired cases test the typed interface; they do not reproduce external incidents or establish network isolation.
3. **Institutional deployment: NOT READY.** The same-user direct database probe succeeded. Production identities, hostile-code isolation, complete deployed-route mediation, external effects, streaming/memory integration, independent witnesses, substantive decision quality and human studies remain qualification gates.

Authentic but wrong source evidence and mistaken or colluding authorized reviewers can still cause harm. A local appeal repairs the demonstrated record, not every consequence. No experiment proves immunity to future attacks, inference, compromised trusted infrastructure or arbitrary frontier-model behavior. Missing applicable evidence blocks promotion rather than being counted as a passing result.

## Package and provenance

`trust-by-construction-revised.md` and the compiled PDF are the final paper. The ZIP contains the complete revised source tree, editable figures, tests, scripts, demonstrations, raw evidence, teaching material and risk registers. `revision.patch` and `change-index.json` compare the combined delivered snapshot with the preserved initial filesystem snapshot; they include intervening author changes and are not an assertion of sole authorship. `latest-paper.patch` isolates the latest paper update from its preserved pre-update source. No changes were pushed or published. The original supplied PDF remains unchanged.

Within the package, start with `fssai-ra/audit/QUICKSTART.md`, `COMPLETION_REPORT.md`, `FINAL_REPORT.md`, `ADVERSARIAL_REVIEW.md`, `LATEST_THREATS_UPDATE.md`, `RESIDUAL_RISKS.md`, `claim-evidence.json`, and `manifest.json`. The manifest is a local integrity inventory, not an independently signed witness.
