# Consolidation record: one framework from many manuscripts

Trust by Construction was written up in several manuscript versions (V11–V28).
Each version was a publication view of the framework at a point in time, and
they did not all use the same numbering, labels or scope. This record explains
how those versions became one canonical definition. It also records which
choices were made when versions disagreed.

**The canonical source is `fssai-ra/src/fssaira/framework_catalogue.yaml`
(catalogue version 1.1).** Both [PATTERNS.md](../fssai-ra/docs/framework/PATTERNS.md)
and [CONTROLS.md](../fssai-ra/docs/framework/CONTROLS.md) are generated from it
by `fssaira framework render`. `tests/test_framework.py` fails the build if any
entry cites a module, test or refusal code that does not exist. If a manuscript
and the catalogue disagree, the catalogue wins.

## What was merged

| Source | Contributed | Canonical form |
|---|---|---|
| V27 (reviewed; the submitted paper) | The decision and composition core | P1–P10, unchanged in identity and order |
| V28 (post-submission full paper) | Evidence and lifecycle, containment and visibility, correctness and consequence | P11–P34 |
| Catalogue 1.0 | 50 operational controls in nine domains, with owners, dependencies and assessment questions | Kept with the same identifiers |
| V28 patterns with no catalogue control | Nine controls recovered: GOV-5, GOV-6, IDN-5, AUT-6, DAT-7, EVD-9, EVD-10, ASR-8, ASR-9 | Catalogue 1.1, 59 controls |

The result has **34 patterns and 59 operational controls**. Patterns and
controls are two views of the same requirements. A pattern states a design
rule. A control gives that rule an owner, a place in the dependency order and
an assessment question. Every pattern maps to at least one control.

| Pattern family | Patterns | Count |
|---|---|---|
| Decision and composition | P1–P10 | 10 |
| Evidence and lifecycle | P11–P22 | 12 |
| Containment and visibility | P23–P28 | 6 |
| Correctness and consequence | P29–P34 | 6 |

| Control domain | GOV | IDN | AUT | DAT | SWM | EFF | EVD | OVS | ASR |
|---|---|---|---|---|---|---|---|---|---|
| Controls | 6 | 5 | 6 | 7 | 8 | 3 | 10 | 5 | 9 |

## Conflicts and how they were resolved

1. **Two maturity scales.** V28 gave levels 3–5 different labels from the
   catalogue. The catalogue's single scale is canonical: 1 access-controlled,
   2 authority-bound, 3 disclosure-governed, 4 composition-safe, 5 evidenced.
   Level 0 is a baseline, not a tier. V28's other labels are superseded.
2. **Claims restated as requirements.** Four V28 pattern rules described
   results. They now state obligations, so that no pattern claims more than its
   evidence shows:
   * P23 Contained agent cell: qualify each deployed cell *from inside its
     actual host boundary*, and refuse requirements that are unmet or cannot be
     measured.
   * P27 Measured covert channels: compute capacity for the *explicitly
     modelled* release choices, and report the dimensions that are unmodelled.
   * P28 Self-describing deployment: publish both declared and undeclared
     limits, and derive dossiers from mediated state and integrity-checked
     receipts.
   * P33 Reviewer canaries: restrict review authority *under the configured
     calibration model*.
3. **Evidence scope made explicit.** Each pattern now has exactly one scope:
   * **local-reference** (14 patterns): the reference implementation
     demonstrates the pattern in a local run.
   * **deployment-dependent** (12): the guarantee depends on how and where it
     is deployed, for example independent administration or a real container
     boundary.
   * **bounded-mitigation** (8): the pattern reduces a risk but does not remove
     it. Examples are monitors, canaries and covert-channel budgets.

   Each pattern also carries a one-sentence residual limit in the catalogue.
4. **Refusal codes versus observations.** Some manuscripts listed exception
   names or prose as if they were codes. The catalogue lists a code only if it
   appears in the generated registry (`fssai-ra/docs/refusal_registry.json`).
   A test regenerates that registry and fails on any difference.
5. **Companion profiles.** `security_systems/trustkernel` is a companion
   demonstration for coding agents. It does not inherit the P1–P34 guarantees,
   and reusing a concept is not the same as interoperating on the wire. Any
   adapter or companion profile must show evidence for each control it claims.

## What did not change

* P1–P10 and every catalogue 1.0 control identifier kept their meaning.
  Existing assessments and citations still resolve.
* The figures quoted in the paper bindings and conference evidence are
  unchanged: 49 specification requirements and 104,997 thesis attempts. Normative requirements added
  later go in profile documents such as
  [SPECIFICATION_SWARM_PROFILE.md](../fssai-ra/docs/SPECIFICATION_SWARM_PROFILE.md),
  not in the core specification tables. The paper figures are generated from
  those tables.

## How to change the framework

Edit the catalogue, run `fssaira framework render`, and run
`tests/test_framework.py`. A new pattern needs a test and a registered refusal
code (or an explicit observation) before it is listed. Do not renumber
existing patterns or controls. Add new ones at the end of their family or
domain.
