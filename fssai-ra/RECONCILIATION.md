# RECONCILIATION — paper claims vs regenerated evidence

Every delta between `paper/trust-by-construction.md` and a value computed by
running enforcement code is logged here. Integrity rule: when they differ, the
paper and the claims register change to the computed value. Code is never
adjusted to reproduce a number.

Paper edits go through session `united-nations-a2`, which owns paper and figure
alignment. Each row records whether the delta has been sent and applied.

## Baseline (2026-09-14, commit 77aaed8, rebased onto 59794bf)

| Check | Result |
|---|---|
| `pytest` | 945 passed |
| `scripts/generate_results.py --check` | 126 of 126 committed figures match a fresh run |
| Committed results after M1–M3 (1102+ tests) | 126 of 126 still match; no pinned figure moved |

## Method

1. `scripts/collect_results.py` reads committed machine-written results into
   `audit/results.json`, keeping each unit and denominator and recording the
   source file digest. It never recomputes them.
2. `paper/metric_bindings.yaml` binds each quantitative claim, as an exact
   substring of the paper, to a pointer in `audit/results.json`.
   Non-results (section numbers, parameters, citations) are declared as such.
3. `scripts/check_submission.py --full-paper` fails on any numeric claim with no
   binding, and on any binding whose value does not match the quoted text.

## Deltas and findings

| # | Paper location | Paper says | Computed / enforced | Source | Action | Status |
|---|---|---|---|---|---|---|
| R1 | Table 3, Education, "Declared purposes" | student-support casework, academic record correction | No enforced source declares these as purposes. The machine-enforced education purposes are the governed-learning pack's six disclosure purposes | `packs/education.pack.yaml` drift check; `conference/education/governed-learning-pack.yaml` | Reword the cell to name the enforced purposes, or mark the two as workflow names rather than declared purposes | Pending: to a2 |
| R2 | §6 stage 7 ("watch review capacity") and §7.3 | Review capacity is declared with a deliberation floor, escalation and fallback | True for the governed-learning pack and the oversight monitor. **No action-profile pack (healthcare, corporate, finance, benefits, student support, academic record) declares a review section**, so the pack floor records `PACK_REVIEW_OVERLOAD_FAILS_OPEN` as an exemption | `kernel/packs.py` `floor_exemptions`; DECISIONS D12 | Add one scoping clause: review-capacity enforcement is demonstrated in the education pack and oversight simulation, not declared in the five sector action profiles | Pending: to a2 |
| R3 | §7.4 Transfer | "6 independently reported domain packs cover 55,440 bounded configurations, 180 of 180 hostile scenarios contained, 58 of 58 benign tasks completed" | `evaluate_pack` over the six action profiles: states 20,160 + 8,400 + 8,400 + 13,440 + 240 + 4,800 = 55,440; scenarios 6 × 30/30; benign 12 + 10 + 10 + 11 + 6 + 9 = 58 | `evaluation/results/v1.0.0-domain-pack-matrix.json`, recomputed by `evaluate_pack` | None: agrees | Agrees |
| R4 | §7.2 Reads | "106 of 106 hostile data flows", "15 of 15 legitimate flows", "All 14 checks" | Four disclosure packs: 27 + 25 + 27 + 27 = 106 hostile contained; 4 + 3 + 4 + 4 = 15 benign; 14/14 load-bearing in each | `evaluation/results/v1.0.0-governed-disclosure.json`, recomputed by `evaluate_pack` | None: agrees | Agrees |
| R5 | Planes (§3.3) and the intelligence plane's "no credential or key" | The intelligence plane holds no credential | Before this branch, `FSSAIRAPipeline.make_agent` passed the evidence write credential to `BoundedAgent`, which stored it unused. Fixed (DECISIONS D8); a live-object test and `fssaira bind` now enforce it | `tests/planes/test_planes.py`, `fssaira bind` | Paper claim now true by test. Optionally mention in §9.2 as a defect found by the new bind gate | Pending: to a2 (optional) |

| R6 | §6.1 "must reject ... non-finite numbers"; §7.8 joined JSON interface | The JSON interface rejects non-finite numbers | `joined_workflow.strict_json` accepted `1e999` as `inf`. Fixed with a `parse_float` hook (DECISIONS D18); regression tests added | `tests/test_joined_strict_json.py` | Paper claim now true by test. Optionally cite as a defect found in §9.2 | Fixed; optional mention to a2 |
| R7 | §3.1 and Abstract, Rule 2: a model "cannot ... launder what it saw"; §6.1 "A new session cannot wash away restrictions by importing an old summary" | Unqualified | Holds for content imported through `integration.memory`, which re-reads sources through the gate. `DisclosureGate` has no lineage for content that bypasses governed memory: text pasted into a fresh session is labelled at the bottom and was released to a recipient the original was refused for (executed in `tests/integration/test_integration_memory.py`). Output screening catches verbatim reuse, not paraphrase | `integration/memory.py`; DECISIONS D15 | Add a scoping clause: label accumulation holds for content that flows through the gate and governed memory; content copied around the gate by a trusted orchestrator or a human is outside it | Pending: to a2 |
| R8 | §4 steps 3–4 and §6.3 "a digest supplied by the model itself is not evidence of loaded weights" | Stated as enforced | `integration.bundle.BundleRegistry` enforces it (a runtime self-report is refused even when it matches). The older `ModelRegistry.attest` still accepts a runtime-reported digest, as its docstring admits | `integration/bundle.py`; `model_registry.py` | State that the bundle registry enforces independent measurement and that the legacy manifest registry compares against a runtime report | Pending: to a2 |
| R9 | §6.1 "Retrieval is a protected read ... Preserve provenance through chunking and ranking" | Stated as a requirement | Implemented in `integration.retrieval`: `authorize_only` runs before any candidate is scored, and provenance and labels survive chunking and ranking. `authorize_only` opens no gate session, so an output built from retrieved chunks carries `RetrievedContext.label` only if the orchestrator attaches it | `integration/retrieval.py` | Describe as implemented with that obligation on the orchestrator | Pending: to a2 |

Rows from the full-paper binder are added when `check_submission.py --full-paper`
first runs.
