# Claim-to-evidence map for reviewers and speakers

| Claim allowed on stage | Reproduction / evidence | Boundary |
|---|---|---|
| Original suite passed 203 tests before added wrapper regressions | Historical review in `REVIEW.md`; original tests and new `test_guard_adversarial.py` are inspectable | A recorded review result, not proof of security or a current test count |
| Forged approval cannot retrieve a cached receipt through the repaired wrapper | `python examples/replay_boundary.py`; `tests/test_guard_adversarial.py` | Unsafe cache branch is an explicit miniature of the failure pattern |
| Successful concurrent replay executes one callback | `test_concurrent_replays_run_one_callback` | 32 threads, one in-memory guard; no crash guarantee |
| Refusal can coexist with harmful state change | `python examples/effect_oracle.py` | Standard-library synthetic record, not a model attack-rate experiment |
| Starter leaks; repaired handoff path blocks the supplied disclosure cases | `python -m workshop.check --implementation starter` and `--implementation solution` | 2/7 versus 7/7, seven authored cases |
| Legitimate work is preserved in a broader declared grid | `python benchmarks/guard_workloads.py`; `evidence/guard-workloads.json` | 36 authored cases, not estimated real-world false-denial rate |
| Local warm read latency was measured | Same script and JSON, including machine/dependency metadata | 1,000 samples per depth in one run; no network, model, contention, or signing |
| 25 falsifiers hold; harm appears in 25/29 ablation configurations | `evidence/{devtools,healthcare,finance,government}.json`; regeneration tests | 27 singles plus two pairs; correlated synthetic worlds |
| New community examples run without a model API after installation | `make community` and terminal rehearsal captures | Installation downloads dependencies unless prepared offline |

Do not claim an independent audit, external replication, production deployment, universal attack coverage, comparative superiority to commercial frameworks, accepted publication, or a human rehearsal that has not occurred. Do not call four parameterized worlds four independent studies.

The source archive's SHA-256 manifest verifies unchanged contents after extraction. It is not a signature, publisher identity proof, or security attestation. CI configuration declares future checks; only an actual run establishes its result.
