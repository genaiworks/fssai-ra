# PLAN — Trust by Construction kernel, mediators, and domain packs

Branch `feat/kernel-packs` (worktree `/Users/genai/Desktop/OMS/fssai-ra-kernel`),
based on `77aaed8`. The authoritative specification is
`paper/trust-by-construction.md` (mirrored by `paper/trust-by-construction.pdf`).

## Starting point (M0 audit, 2026-09-14)

The build brief assumed a small first-generation package with five domains and
11 tests. The tree actually audited is much larger:

| Measure                                                             | Observed                                                                                                            |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Modules in `src/fssaira`                                            | 78, 26,551 lines                                                                                                    |
| Tests collected and passing                                         | 945, 0 failures (`pytest -q`, project venv)                                                                         |
| Committed paper figures reproducing (`generate_results.py --check`) | 126 of 126                                                                                                          |
| Control-contract requirements (`contract/*.yaml`)                   | 44; register 41 machine-verified / 3 attested / 0 unverified                                                        |
| Sector profiles                                                     | 6 action packs + `template.yaml`; 4 carry a `disclosure:` pack; 1 governed-learning pack in `conference/education/` |

**Consequence:** this plan is **additive**. New subpackages expose the kernel,
planes, mediators, integration contract and lifecycle as enforced interfaces over
the existing enforcement code. They do not move it. Moving 78 modules a week
before the 21 September submission would invalidate 126 pinned figures, the F6
citation falsifier (`contract/bindings/core.yaml`, `threats/catalogue.yaml`,
`docs/SPECIFICATION.md`), and concurrent sessions' work. See `DECISIONS.md` D1.

## Gap list (brief vs code)

Status: **E** = exists, **P** = partial, **M** = missing. The milestone column
says where each gap closes.

| #   | Requirement                                                                                     | Status | Gap                                                                                                                            | Milestone |
| --- | ----------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------ | --------- |
| G1  | Seven-field contract, exact field names                                                         | P      | `contract/*.yaml` uses `owner`/`test` (prose); only `pack_floor` uses `failure_test`                                           | M1        |
| G2  | Named failure test resolved and checked to exist                                                | P      | Check is pytest-only and loose: substring match, column-0 `def`, skips `CF-*` IDs; CLI does not enforce it                     | M1        |
| G3  | Claims register `machine_verified / attested / unverified`                                      | P      | Exists as `organizationally_attested` in `coverage.py`; no `paper/claims_register.yaml`                                        | M1, M8    |
| G4  | Resilience state machine (9 states, legal transitions only)                                     | M      | States scattered; "compensated" unimplemented                                                                                  | M1        |
| G5  | Executor: identical refusal regardless of rationale                                             | P      | Asserted only in `joined_workflow`; not a property of `AccountableExecutor`                                                    | M2        |
| G6  | Planes with declared must-NOT lists                                                             | M      | Responsibilities exist only in prose                                                                                           | M2        |
| G7  | Kernel floor applied to every sector pack                                                       | P      | Floor applies only to the conference education pack; two pack formats                                                          | M3        |
| G8  | `packs/` for five sectors + `template.pack.yaml` + authoring guide                              | P      | Profiles exist; no pack manifest, no `PACK_AUTHORING.md`                                                                       | M3        |
| G9  | Strict typed proposal/context-request interface                                                 | P      | Duplicate keys, non-finite and size checks only in `joined_workflow.strict_json`; no schema-version, depth or destination gate | M4        |
| G10 | Retrieval as protected read; labels + retention through memory, cache, summary, vector, handoff | M      | Session taint only; nothing tests that a new session can't wash labels                                                         | M4        |
| G11 | Model change = versioned, re-attested bundle                                                    | P      | `ModelManifest` has one `artifact_digest`                                                                                      | M4        |
| G12 | Streaming as a sequence of disclosures                                                          | M      | All adapters `stream: False`                                                                                                   | M4        |
| G13 | Isolated generated-code runner + explicit non-isolation statement                               | M      | P0 residual risk in `audit/RESIDUAL_RISKS.md` only                                                                             | M4        |
| G14 | Backend inherits no assurance until conformance passes, enforced in code                        | M      | Conformance on demand; runtime starts on warnings                                                                              | M4        |
| G15 | Single machine-written `audit/results.json` with denominators                                   | M      | Results spread over `evaluation/results`, `conference/evidence`, `audit`                                                       | M5        |
| G16 | Figures regenerable as SVG **and** PNG, fig1–fig7                                               | P      | SVG only; no test runs `--check`                                                                                               | M5        |
| G17 | Adaptive/tabular-Q results bound to the paper                                                   | P      | `audit/adaptive-results.json` is not bound by any test                                                                         | M6        |
| G18 | Lifecycle CLI `frame/contract/pack/bind/falsify/promote/operate` with gates                     | M      | None of these stages exist (only `conference falsify`)                                                                         | M7        |
| G19 | `check_submission.py` binds every metric quoted in the full paper                               | P      | Checks form-field caps only; e.g. "41, 3, 0", "841", "55,440", "104,997" unbound                                               | M7        |
| G20 | `docs/ARCHITECTURE.md`, `DEPLOYMENT.md`, `PACK_AUTHORING.md`; deploy profiles; CI; mypy         | M      | Only a Dockerfile + compose; CI lives at repo-root `.github/`                                                                  | M7        |
| G21 | `RECONCILIATION.md`                                                                             | M      | —                                                                                                                              | M8        |

Already present and reused, not rebuilt: action executor (`exact_action.py`),
disclosure gate (`disclosure.py`), delegation (`delegation.py`), evidence chain
and notary, bounded verification, conformance suite, comparison arms, thesis
falsifiers F1–F6 with positive control, threat catalogue, review-capacity model,
joined workflow, tabular-Q attacker, conference evidence.

## Target file tree (new = `+`, existing wrapped = `~`)

```
fssai-ra/
  PLAN.md  DECISIONS.md  RECONCILIATION.md                    +
  paper/
    trust-by-construction.{md,pdf}                             ~ spec (edits via a2)
    claims_register.yaml                                       + generated
  src/fssaira/
    kernel/                                                    +
      __init__.py
      contract.py        # seven-field schema, strict loader, test resolver (AST)
      claims.py          # machine_verified | attested | unverified register
      invariants.py      # facade over verification.INVARIANTS
      evidence.py        # facade over EvidenceLedger + EvidenceNotary
      state_machine.py   # pending→…→committed|uncertain|reconciled|compensated|denied|expired
      assurance.py       # backend assurance: no conformance record, no use
      packs.py           # pack manifest loader + kernel floor over profiles
    mediators/                                                 +
      executor.py        # Rule 1 facade; rationale-independence property
      context_gate.py    # Rule 2 facade over disclosure.DisclosureGate (no fork)
    planes/                                                    +
      base.py            # Plane protocol: RESPONSIBILITY, MUST_NOT, enforcing symbols
      boundary.py data.py intelligence.py authority.py
      execution.py context_gate.py evidence.py resilience.py
    integration/                                               +
      typed.py           # strict proposal / context-request parsing
      retrieval.py       # protected read, provenance through chunk/rank
      memory.py          # labelled memory/cache/summary/vector/handoff + retention
      bundle.py          # versioned model bundle + re-attestation
      streaming.py       # per-chunk authorized disclosure, stop on revocation
      sandbox.py         # isolated subprocess runner, no inherited secrets
    lifecycle/                                                 +
      stages.py cli.py   # frame|contract|pack|bind|falsify|promote|operate
    <78 existing modules>                                      ~ unchanged
  packs/                                                       +
    healthcare.pack.yaml corporate.pack.yaml finance.pack.yaml
    benefits.pack.yaml education.pack.yaml template.pack.yaml
  contract/
    capabilities/*.yaml  # seven exact fields, failure_test = pytest locator   +
    *.yaml bindings/core.yaml                                  ~ unchanged
  scripts/
    collect_results.py   # reads evaluation/results + conference/evidence + audit → audit/results.json  +
    check_submission.py  # + --full-paper metric binding                        ~
    generate_paper_figures.py  # + PNG output                                   ~
  audit/results.json                                           + generated
  figures/fig1..fig7.{svg,png}                                 + generated
  deploy/profiles/{teaching,institutional,hardware-isolated}.yaml, THREAT_MODEL.md  +
  docs/ARCHITECTURE.md DEPLOYMENT.md PACK_AUTHORING.md         +
  tests/kernel/ tests/mediators/ tests/planes/ tests/integration/ tests/lifecycle/  +
  Makefile                                                     ~ results/figures/check-submission/all
```

## Milestones (each ends green and committed)

| M   | Deliverable                                                                                                     | Exit gate                                                                                                                                                                                 |
| --- | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M0  | This plan, `DECISIONS.md`, gap list                                                                             | Baseline 945 pass, 126/126 figures reproduce                                                                                                                                              |
| M1  | `kernel/contract.py`, `claims.py`, `state_machine.py`, `evidence.py`, `invariants.py`; `contract/capabilities/` | An empty field fails the build; a named but missing test fails the build; illegal transitions raise                                                                                       |
| M2  | `mediators/`, `planes/`                                                                                         | Rationale-independence property over the real executor; every plane declares must-NOT symbols that exist                                                                                  |
| M3  | `kernel/packs.py`, `packs/*.pack.yaml`, `docs/PACK_AUTHORING.md`                                                | All 5 sector packs load through one kernel with a floor; kernel source hash unchanged across packs; malicious pack refused                                                                |
| M4  | `integration/*`, `kernel/assurance.py`                                                                          | Strict-parser rejection matrix; label wash refused; bundle change requires re-attestation; stream stops on revocation; sandbox strips env and bounds resources; unassured backend refused |
| M5  | `collect_results.py`, `audit/results.json`, PNG figures                                                         | `collect_results --check` reproduces; every figure has a denominator                                                                                                                      |
| M6  | Bind joined workflow + tabular-Q Table 5 into `audit/results.json`                                              | Table 5 cells are read from `audit/adaptive-results.json`, not hand-typed                                                                                                                 |
| M7  | Lifecycle CLI, docs, deploy profiles, `check_submission --full-paper`, Makefile, CI                             | `make all` green offline; `bind` fails if a model holds a key; `promote` refuses stale evidence                                                                                           |
| M8  | `RECONCILIATION.md`, `paper/claims_register.yaml`; figure deltas sent to a2                                     | `check_submission.py --full-paper` passes; no unbacked metric                                                                                                                             |

## Coordination constraints (from session united-nations-a2)

1. Never rename or move a function or test cited by bindings, the threat catalogue or the specification (F6).
2. Wrap `disclosure*.py`; never fork it.
3. Every `docs/` file is linked from `docs/README.md` with a navigation header and a "Recommended next:" line.
4. `test_count` is a pinned figure quoted in `docs/REVIEWERS.md`; regenerate only in coordination.
5. Concurrency figures report violations and limits only.
6. An empty `EvidenceLedger` is falsy: never `ledger or EvidenceLedger()`.
7. `audit/results.json` reads committed results; it never recomputes them.
