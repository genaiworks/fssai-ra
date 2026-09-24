<<<<<<< HEAD
# Paper and implementation reconciliation

The original TBC v11 is preserved in `paper/tbc-v11/`. The v12 engineering revision is preserved in `paper/tbc-v12/`. The current revision is `paper/tbc-v13/`, produced from the v12 source by `scripts/build_paper_revision.py` so that every prose change is reviewable as code, with its own claim manifest. Earlier revisions are never edited in place.

## Closed gaps

- Versioned strict ingress is connected to the actual SDK dispatch boundary.
- Persistent source quarantine prevents subsequent use of tracked source-derived memory, proposals and releases and survives reopening and fresh task creation.
- Eight-component model identity, frozen tool-manifest comparison and destination authorization exist as tested integration contracts.
- Seven-field capability contracts are bound to executed tests, with failed/skipped tests treated as unverified and source drift detected.
- The 109 architecture control IDs remain visible with source pages, related implementation files and explicit scope.
- Revocable delivery of approved bytes is reauthorized at every chunk boundary, and a durable workload stop and restrict-only AI-monitor interface are executed contracts.
- CI and `make all` check contract execution, v11 provenance, revised-paper bindings and fresh reproduction of the existing results.

## Paper changes

The revised paper describes the implemented SDK rather than calling it only a future build phase. It adds source quarantine, complete model configuration identity, strict integration contracts, executed-test evidence, a regression count with its own denominator, threats to validity and deployment qualifications. Captions distinguish an integration roadmap from tested implementation. Original experimental numbers remain unchanged.

The full synthetic regression run contains 1,117 passing cases. Ten capability contracts are executed against named tests; their cases are a subset of the full suite, not additional independent experiments. Existing generated results reproduce 126 reported quantities. The original Word source is unchanged.

## Open work

The architecture is not fully implemented or operationally qualified. The catalogue uses conservative whole-control statuses: 2 implemented locally, 88 partially covered, 8 requiring deployment evidence and 11 explicitly unimplemented. A partially covered family can contain substantial existing code; its status means the complete source requirement has not been established. These are traceability categories, not security scores.

Generic browser and external tool transports, full SBOM/dependency impact analysis, canary promotion, policy differential simulation, production training/promotion lifecycle and generic remote uncertain-outcome reconciliation remain software work. Host isolation, workload federation, independent witnesses, external kill paths, credential rotation and hardware-backed custody require a chosen deployment and target-specific evidence. No infrastructure was deployed or repository pushed.

The earlier milestone plan is retained as a roadmap. This revision completes the explicitly listed engineering changes; it does not claim all M0–M8 architecture ambitions or all 657 pages are implemented.

## v13 revision: frontier threat controls

Three controls were added and bound to executed contracts.

- `workload_stop` and `stop_without_evidence`: a durable operator stop that revokes every agent, quarantines every task and advances every epoch in one transaction, commits before the evidence write is attempted, survives service restart, and requires a fresh identity to resume. It stops declared authority, not operating-system processes.
- `revocable_delivery`: approved artifact bytes are delivered against a binding re-resolved at every chunk boundary, so revocation, contraction, expiry, an emergency stop or a source quarantine denies the remainder. Committed bytes are not recalled.
- `restricted_monitor`: an AI monitor receives task metadata and an evidence head, never protected text, and submits a fixed-vocabulary finding that can only contract authority. A clear verdict changes nothing. Forged, stale, replayed, wrong-role and field-injecting findings are rejected.

`audit/incident-map.json` assigns each reported stage of the public July 2026 agent-intrusion disclosure to a mediated control, a deployment requirement, or a platform property outside this architecture. `tests/test_incident_map.py` requires every mediated stage to name a test that exists, forbids an out-of-scope stage from implying local evidence, rejects prevention wording, and fails if no residual risk remains in the map. Five of the fourteen stages are not mediated locally: sandbox escape and pod metadata access are out of scope; key custody, network confinement and transport security are deployment work.

The paper claims no prevention of any real incident, and the frontier-control tests are deterministic local scenarios rather than reproductions of frontier-model propensities.

## Current v13 verification — 19 September 2026

The current manuscript is `paper/tbc-v13/TBC_v13_Frontier_Threat_Revision.docx`.
Its bibliography now contains nine research preprints from 2025–2026. Leader
commentary and incident disclosures remain supplementary context. Earlier counts
in this reconciliation document describe historical checkpoints.

The current run passes 1,120 regression cases, including 18 frontier-control cases.
Ten capability contracts execute successfully, and thirteen current manuscript
anchors are checked against test locators and recorded evidence. Monitor snapshots
now include bounded event metadata; delivery evidence failure is tested to return
no bytes and preserve the cursor. The paper builder and bibliography checks are
reproducible. No live detector performance or real-incident prevention is claimed.

## Follow-up v13 security review

The revised release passes 1,147 full regression cases, including 35 frontier
cases, with sixteen checked paper anchors and eleven recent research references.
The new focused suite reproduces fourteen failures against the preceding code
and passes all 58 cases after repair. This supersedes the earlier v13 checkpoint.
The architecture register continues to expose deployment and implementation
gaps; this review does not turn a local reference into production isolation.

## Second v13 review: deployment assumptions made measurable

The preceding review listed six open items with acceptance criteria. Five are now
implemented and bound to executed capability contracts; the sixth is published as
an instrument for a study that has not been run.

Closed as implemented and tested: process and network isolation is measured
against eight declared host properties, with `not_measurable` treated as an open
requirement rather than a pass; outbound transport is performed by a client that
pins the literal address without any name-service lookup, verifies the hostname,
pins the peer public key, refuses redirects and ambiguous framing, and enforces
the byte ceiling on the wire; monitor quality is measured over labelled held-out
trajectories with rates, intervals and an adaptive family; remote effects are
at-most-once with reconciliation by idempotency key and a first-class uncertain
state; cross-service authority, k-of-n witness attestation with fork detection
and an evidence-gated promotion decision are implemented; and the 2025-2026
tool-server threat classes -- description poisoning, rug pulls, cross-server
shadowing and confused-deputy chains -- are refused by definition pinning,
server-qualified naming, pre-approval scanning and permanent chain taint.

Not closed, and stated as acceptance criteria rather than future work: host
isolation must be exercised adversarially in the target deployment, because a
cooperative probe establishes the absence of a path from this process only;
transport must be qualified against the institution's real peer, because the
controlled peer here is a loopback server whose evidence the promotion gate
refuses; and the institutional utility and fairness study is not run, with the
analysis refusing conclusions from synthetic fixtures by construction.

One defect was found by the new monitor harness rather than by code review:
refusals raised before the request savepoint -- a revoked agent, a stopped
workload, an assurance failure -- wrote no evidence at all, so persistence after
an emergency stop was invisible in the chain. Blocked attempts are now recorded
outside the failed transaction without restoring any authority, and an unknown
token records nothing. A duplicate `adaptive` Makefile target, which silently
discarded one of two recipes, was renamed to `adaptive-search`.

The current run passes 1,375 regression cases with none skipped, executes 31
source-bound capability contracts, and checks 35 manuscript anchors against test
locators and recorded evidence. The 228 cases added by this revision are included
in that total and are not additional attack episodes. The architecture register
is unchanged at 109 controls with its conservative statuses intact. Measuring an
assumption is not supplying it, and `make qualify` prints `reference` for this
repository with every blocking reason named.

## V14 developer security revision

V14 derives from the preserved v13 artifact at commit 6d8f9e3. It adds verified
artifact bytes, per-transfer response buffers, strict framing, conservative
provider settlement and operation binding. The active build/check paths now use
`paper/tbc-v14/`. The developer example demonstrates useful completion and
failure handling without a model key or real records. Recorded current evidence
is bound through its implementation manifest; earlier counts remain historical.

## v14 addition: residual choice as a measured channel

Exact-byte release escrow was treated in every earlier revision as settling
exfiltration. It settles content and nothing else. The destination, path,
timing, size and count of an authorised release are choices the system hands the
model, and they carry information that no content check sees.

`fssaira.covert_channels` canonicalises the dimensions a task contract can
supply, charges the residual against a per-task bit budget, and escalates to a
named human when it is spent. `audit/covert-channels.json` records the measured
ablation over 65,536 sixteen-bit secrets against an adversarial encoder that
performs no unauthorised operation: 16.0 bits conveyed with no control, 1.0
canonicalised, 0.0 sealed, with an ordinary two-release workflow completing under
every policy and 98.4% of adversarial tasks escalating.

Four capability contracts bind these claims to executed tests. Two defects found
during construction were fixed: an unpadded size dimension built an invalid
accounting entry instead of reporting itself unbounded, and a sealed policy did
not enforce its own fixed release count, which would have reopened the count
channel.

The current run passes 1,445 regression cases with none skipped, executes 37
source-bound capability contracts, and checks 49 manuscript anchors. The measured
figure is an upper bound assuming a perfect observer and an optimal decoder,
covers one encoder, and bounds the mediated release path only.
=======
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
>>>>>>> 0a0f3fc (M3: domain packs over one kernel, pack floor, drift checks, architecture and deployment docs)
