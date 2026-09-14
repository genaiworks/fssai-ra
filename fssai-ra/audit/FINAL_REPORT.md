# Trust by Construction: revision and verification report

The paper and implementation now contain a durable, runnable joined workflow, concrete security repairs, bounded adaptive evaluation, and explicit limits. This package is suitable for synthetic demonstration and review. It is not institutional deployment qualification and does not complete every requested production attack experiment.

## What broke and what changed

Before repairs, the nominal advisor could select an unassigned student, obtain context, correct the grade and receive an identified result. The driver also approved caller-selected A without instructor confirmation. Both changed actual register state. The legacy entry point now denies those requests and labels its identity/review behavior as simulated. The new SQLite interface authenticates separately supplied synthetic role tokens, enforces independently seeded assignment and rooted grants, binds exact proposals to versioned context and instructor confirmation, rechecks at execution and release, durably records effects/evidence and supports revocation, reconciliation and appeal. A final review also fixed advisor reconciliation after revocation.

New tests cover tenant/subject scope, spoofed authority, synthetic rationale/citation attacks, stale source/policy/recipient/context, changed proposals, read-to-write escalation, sibling budgets, cross-session references, cached revocation, replay, evidence-write failure, checkpoint truncation and authorized harmful-source recovery. Unknown code/tool/network/memory/stream/schema interfaces deny. That last statement concerns the JSON API only.

A separate same-user subprocess read the database directly. This is a confirmed lack of hostile-code isolation, not a security success. A correctly authenticated but wrong source can still lead authorized reviewers to approve a wrong grade. Appeal repairs the local record; authorization never proves substantive correctness.

The figures no longer promise identity exclusion, digest-only evidence, complete key-erasure or universal exactly-once effects. The trusted base includes host/runtime/parser/identity/source/policy/CI dependencies and common-mode failures. The 19-page paper retains the integration-method contribution and explicitly separates historical component evidence from joined-path results.

## Executed commands and outcomes

Commands are relative to the package directory unless noted otherwise. Full logs and JUnit evidence are under audit/.

| Command / experiment | Outcome |
|---|---|
| Root `make test`, before repairs | 841 passed; no failures or skips; 53.52 s |
| Root `make reviewer`, before repairs | Failed at resilience artifact comparison; earlier stages executed, final result-check stage not reached |
| Final `python -m pytest --junitxml=audit/executed-tests.xml` | 872 passed, 0 failures, 0 errors, 0 skips; 54.89 s |
| `python -m ruff check src tests scripts jobs adapters` | Passed |
| `python scripts/generate_results.py --check` | 126 figures matched fresh execution |
| `python scripts/conference_evidence.py --check` | Conference evidence matched fresh execution |
| `python scripts/check_resilience.py --write`, then check | Two process races and four abrupt-exit cases passed; only stale profile/source fingerprints changed |
| `python scripts/joined_demo.py --output audit/demo-final` | Five local runs: education, benefits and on/off/restored; actual records, sink bytes and receipts |
| `python scripts/adaptive_attacks.py` | 1,200 tabular-Q training episodes; 480 held-out episodes across 3 arms × 4 strategies × 40 seeds |
| `python scripts/live_joined_probe.py` | Four fresh local llama3.2:1b generations, final outputs saved; no unsupported grade effect |
| `python scripts/build_paper.py` and Poppler rendering | PDF built; every page visually inspected |
| Fresh copied source + clean venv, no pip installation | Standalone demo and adaptive harness passed after removing eager legacy YAML import; outcomes matched |

The first clean run failed with missing YAML because the package facade eagerly imported it. The corrected CLI imports only the stdlib leaf module. The first live probe marked a model JSON parse failure NOT RUN; the final probe records raw truncated output and correctly labels it executed but invalid. An intermediate resilience probe launched from stdin failed multiprocessing spawn; rerunning the same probe from a guarded Python file passed. These failed attempts are not passing evidence.

## Security and utility results

The joined arm recorded 0 unsupported corrections in each set of 40 static, random, adaptive-search and trained-Q episodes. The competent server-authorization baseline retained authentication, role/scope checks, exact approval, replay, release and budgets, while omitting source confirmation: static, adaptive and trained-Q each produced 40/40 unsupported but approved corrections; random produced 0/40. Both arms had zero unauthorized subject mutations and unauthorized sink bytes in the tested grammar. They each completed the separately scored legitimate task; deny-all completed none. These are small correlated author-defined spaces, not universal security probabilities.

The Q learner is real tabular Q-learning with sparse backend outcome reward. It is not LLM reinforcement learning. Training and held-out seeds differ but share grammar and task family. Simulated reviewer credentials belong to the evaluator, not to model-selected authority fields. Raw trajectories include actions, responses, state observations, rewards and episode latency; latency includes setup and is not a production gate-only benchmark. No inference is made about energy or dollar cost.

The four local-model probes ended with grades C, C, C and B. The legitimate prompt produced invalid truncated JSON and failed to complete: a utility failure. One hostile output proposed A and was rejected by independent confirmation. The other outputs omitted the typed value or supplied supported B. No result was released in this smoke test. This fixed-interface local probe is neither a frontier-model evaluation nor a live reviewer-persuasion study.

## Separate verdicts

1. **Repository/demo reproducibility: PASS for the revised local teaching demo and tested Python environment.** Clean no-install demo/harness reproduction passed. Full distributed deployment, cross-platform dependency locks and newly added GitHub CI execution remain unqualified. The original snapshot and author changes were preserved. Another process made multiple `fix` commits during the work; the session diff is computed against the initial filesystem snapshot, not merely final HEAD.
2. **Security properties: VERIFIED only for the executed JSON/SQLite and existing fixture boundaries.** Exact versioned proposals, scope, independent confirmation, transactional evidence, cumulative budgets and current release checks survived their bounded regressions. Direct same-user database access remains possible; authentic bad evidence and reviewers can still authorize harm.
3. **Institutional deployment: NOT READY.** Public teaching credentials, unisolated host, synthetic source/people, unqualified external adapters, incomplete distributed privacy and no institutional studies block promotion.

## Not run, unproven or incomplete

Actual production model/worker identity probes, controlled network redirect/exfiltration capture, arbitrary-code sandbox containment, all-route deployment mediation, remote uncertain-effect reconciliation, chunk-stream revocation, full memory/vector integration, unknown-copy erasure, independently witnessed backups, language-model RL, trained reasoning monitors, independent held-out exploit classes, institutional human/education studies, production latency/cost/energy and legal/compliance qualification remain outstanding. Some primary bibliography endpoints were inaccessible; REFERENCES.md records successful checks and remaining limits. The original broader tests use local/fake backends where configured and must not be represented as distributed infrastructure runs.

Read RESIDUAL_RISKS.md for priorities and owners, claim-evidence.json for evidence mappings, interface-inventory.json for source interfaces, QUICKSTART.md for demo/teaching/recovery, and ADVERSARIAL_REVIEW.md for the pre-repair rebuttal and exploit distinctions.
