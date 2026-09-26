# Reviewed manuscript evidence map

This map covers the main numerical claims in the local V27 reviewed manuscript
and the subsequent editorial revision. It does **not** identify the submitted
PDF. The cited historical software commit is
`9bb35a190353a5e4f9bfce7d5b987667c5874a49`. The review started from
`88a65e70b76dbbf12c99b6255a1faf76f34cf7f7`; later fixes must be reported separately
from that historical snapshot. Manuscript files remain local-only.

## Numerical claims

Paths are relative to `fssai-ra/evaluation/results/`. The reproduction command,
from the application directory with development dependencies installed, is
`python scripts/generate_results.py --check`. It recomputes tracked numerical
figures, excluding timings and test count. It does not compare the entire
manuscript, authenticate the submitted file, or rerun an external benchmark.

| Manuscript location | Claim | Raw evidence location | Interpretation |
|---|---|---|---|
| Results, cross-domain paragraph | Six packs; 55,440 bounded configurations | `v1.0.0-summary.json`: `figures.domains_verified`, `figures.domain_pack_states_explored`; `domain_packs` has per-pack counts | Authored finite spaces; no unbounded proof |
| Results, cross-domain paragraph | 180/180 hostile scenarios contained; 58/58 benign workflows completed | Same file: `figures.domain_pack_scenarios_contained`, `domain_pack_scenarios_total`, `domain_pack_benign_completed`, `domain_pack_benign_total` | Shared scenario families, not 180 independent attacks |
| Results, delegation paragraph | Unguarded 0/10; immediate-delegator validation 2/10; whole-chain validation 10/10 | Same file: `figures.delegation_hostile_chains`, `delegation_contained_unguarded`, `delegation_contained_caller_checked`, `delegation_contained_this_architecture` | Authored baselines; not measurements of cited third-party systems |
| Results, ablation sentence | Nine removed controls each restore the associated violation | Same file: `figures.delegation_invariants_ablated`, `delegation_invariants_load_bearing` | Attribution within these fixtures, not completeness of the control set |
| Results, oversight paragraph | 40 cases; attention budgets 2, 4, 8, 16; harmful approvals 5, 5, 4, 3 without control | `v1.0.0-oversight-sweep.json`: `grid.arrivals`; `cells` selected by `attentive_until`; `harms_without_load_control` | Declared simulated behavior; no observed human performance |
| Revised oversight paragraph | At a 45-second floor, zero harmful approvals and 38, 36, 32, 24 manual deferrals | Same cells with `deliberation_floor_seconds == 45.0`: `harms_with_load_control`, `deferred_to_manual_fallback` | The model assumes 90-second careful and 3-second fatigued reviews; manual outcomes are unknown |

## Behavioral and architectural claims

| Claim | Evidence or status | Boundary |
|---|---|---|
| Approval binds the exact proposal and rejects replay conflicts | `tests/test_exact_action.py`, `tests/test_atomic_execution.py` | Reference memory and SQLite profiles |
| The executor independently rejects self-approval and invalid clock/expiry values | `tests/test_approval_boundary.py` | Added after the cited historical commit; tests both backends and HMAC/Ed25519 signatures for signed-field defects |
| Delegated authority cannot grow in tested chains | `tests/test_delegation.py` | Declared chain space and trusted verifier |
| SDK composition, budget and information restrictions | `tests/test_tbc_sdk.py` | Local reference implementation; not distributed performance evidence |
| Cross-domain profile reuse | `tests/test_generalization.py` and the `domain_packs` array | Synthetic domain policies; not regulatory compliance |
| Distributed swarm enforcement under partitions and external effects | Proposed composition contract | Requires adapter qualification, atomicity/fencing, reconciliation and independent deployment evidence |
| Effective human oversight and educational benefit | Unevaluated | Requires staff/student studies, waiting-time and manual-route outcomes |

## Reproduction record

For a new experiment, retain the full commit, working-tree diff, resolved
dependencies, inputs, commands, raw outputs and manuscript hash together.
`make reproduce` records the current public workflows in a fresh evidence bundle;
`make docker-verify` additionally runs the public suite and drift checks in the
pinned Docker environment. Neither command establishes the identity of the
submitted manuscript. Historical manuscript checks require their local archive.

See the [submission record](README.md) for unresolved artifact identity and the
[public verification guide](../../fssai-ra/docs/PUBLIC_VERIFICATION.md) for bundle
verification and deployment limits.
