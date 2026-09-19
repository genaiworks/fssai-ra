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
| R7 | §3.1 and Abstract, Rule 2: a model "cannot ... launder what it saw"; §6.1 "A new session cannot wash away restrictions by importing an old summary" | Unqualified | Holds for content imported through `integration.memory`, which re-reads sources through the gate. `DisclosureGate` has no lineage for content that bypasses governed memory: text pasted into a fresh session is labelled at the bottom and was released to a recipient the original was refused for (executed in `tests/integration/test_integration_memory.py`). Output screening catches verbatim reuse, not paraphrase | `integration/memory.py`; DECISIONS D15 | a2 is fixing this in the gate: `derive_output` and `derive_from_values` will join the labels of any session whose protected values (8 characters or more) appear verbatim in the output. Paper wording is held until that lands; the expected honest scope is "verbatim copies are caught; paraphrase and encoding are not" | Fix in progress (a2); wording held |
| R8 | §4 steps 3–4 and §6.3 "a digest supplied by the model itself is not evidence of loaded weights" | Stated as enforced | `integration.bundle.BundleRegistry` enforces it (a runtime self-report is refused even when it matches). The older `ModelRegistry.attest` still accepts a runtime-reported digest, as its docstring admits | `integration/bundle.py`; `model_registry.py` | State that the bundle registry enforces independent measurement and that the legacy manifest registry compares against a runtime report | Pending: to a2 |
| R9 | §6.1 "Retrieval is a protected read ... Preserve provenance through chunking and ranking" | Stated as a requirement | **Fixed.** `integration.retrieval.GovernedRetriever` restricts candidates to the authenticated tenant, then reads exclusively through `DisclosureGate.assemble_context` — the gate authorizes, reads, evidences and labels. `RetrievedContext.label` is always `GovernedContext.label`; nothing in the orchestrator computes a label. `RetrievedContext.value_ids` names the gate-issued values so an output is labelled with `gate.derive_from_values(sources=context.value_ids.values())`, never a value the orchestrator invented. A cache hit is served only when the gate's fresh read of the same values is byte-identical, and only after that fresh read (so revocation and consent withdrawal are always rechecked) | `integration/retrieval.py`; `tests/integration/test_integration_retrieval.py` (7 tests, incl. one asserting the output's label equals the retrieved context's label) | None: a2's design defect is closed in code, not wording | Fixed |

| R10 | §7.5, §7.8, §7.9, §9.2: "five contract bindings named functions that did not exist", "eighteen of twenty-eight were prose bound to nothing", "841 baseline tests", "Five synthetic rationale variants", "two defects" | Unbound: no machine-written result | Each is a past observation that no run regenerates. It is bound as `kind: historical` to the committed record that states it: `CHANGELOG.md` ("The first run refuted the repository's own contract: five"; "18 of 28 requirements"), `audit/baseline-tests.log` ("841 passed"), `tests/test_joined_workflow.py` (the five-entry rationale parametrization), and `audit/KEY_SECRECY_AND_COMPOSITION.md` (E1, E2). The binder fails if a record stops containing the text | `paper/metric_bindings.yaml`; `scripts/bind_paper_metrics.py` | None: backed by record, labelled as not regenerable | Agrees |
| R11 | §7.5 "reading 41, 3, 0 in the baseline contract register" | 41 / 3 / 0 | Legacy contract rows are still 41 / 3 / 0. The full register, which adds 15 seven-field capability contracts, is 56 / 3 / 0 of 59 | `paper/claims_register.yaml` (`fssaira contract contract --gate`) | None; optional sentence on the capability contracts | Agrees |

## Self-review findings (2026-09-18, second self-review pass)

Two real gaps found and closed while reviewing this branch's own work, plus
one honestly-scoped-open item:

| # | Finding | Fix |
|---|---|---|
| S1 | `register_promote()` was fully written and unit-tested via `stages.promote()` directly, but never called from `register()` — `fssaira promote` was unreachable from the CLI despite being "done" | Wired into `register()`; added `test_promote_is_reachable_from_the_cli_...` (a regression test that would have caught this) |
| S2 | The brief requires "ruff and mypy clean"; mypy was never installed, configured, or run | Installed mypy; added `[tool.mypy]` + per-module overrides to `pyproject.toml` (strict on `kernel/mediators/planes/integration/lifecycle`, the packages this build owns); fixed the 5 real findings that surfaced (missing annotations, one lazy-import typed as `Any`); wired `make typecheck` and a CI step. `mypy src/fssaira`: 0 issues |
| S4 | `kernel.assurance.run_and_record` and `fssaira promote --records` were both built and tested, but no CLI command could produce the record file promotion needs — only calling Python directly, as tests do | `fssaira conformance --record-out PATH` now also writes a `ConformanceRecord` JSON list from the same run. Verified end-to-end: its output satisfies `require_assurance` unmodified (DECISIONS D26) |
| S3 (open, scoped) | Running mypy against the full pre-existing 78-module tree (not built by this branch) found 134 real type errors across 28 files | Deliberately out of scope: those modules are owned by concurrent sessions on this repository, and fixing them risks conflicting with work already in flight. `ignore_errors = true` on that surface is a documented boundary (DECISIONS D25), not a suppressed claim of cleanliness |

## Full-paper binding result

`python scripts/check_submission.py --full-paper` (2026-09-15, branch `feat/kernel-packs`):

- 360 numeric tokens in the paper body; References and URLs are excluded.
- 214 bindings: 60 result bindings covering 114 bound values, plus parameter,
  specification, citation and historical bindings.
- **0 unbound, 0 mismatches.**

Passing is not semantic review. It shows only that every number in the paper
is traceable to a machine-written result or a named committed record.

Paper wording deltas R1, R2, R7, R8 and R9 were sent to `united-nations-a2` on
2026-09-15. No paper number needs changing.
