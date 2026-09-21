# Demonstration Tracks — design

**Date:** 2026-09-21
**Branch:** `feat/demonstration-tracks`
**Status:** design, awaiting review

## Problem

`conference/` was built for one audience (UNU Macau 2026, education, academic register).
Its own README already concedes the seam: *"This directory retains a historical name."*
We now need a second audience (AI Engineer CODE Summit SF 2026, practitioner engineers,
tech register) and want the Nth audience to be configuration rather than a fork.

The kernel is already audience-neutral. The pack schema (`governance`, `identity_fields`,
`disclosure`, `transitions`, `controls`, `model_manifests`, `review`, `delegation`) carries
no education assumptions. Six domain packs already ship. What is coupled is narrow and
identifiable:

| Coupling | Location | Nature |
|---|---|---|
| The cast | `src/fssaira/education_world.py` module constants `STUDENTS`, `PEOPLE`, `AGENTS`, `RESOURCES`, `SOURCE_KEYS` | data frozen into code |
| The pack path | `education_world.py:69` `PACK_PATH` | single hardcoded default |
| Layout | `conference/education/`, singular `conference/` | directory naming |
| Narrative and register | `conference/demos/DEMO_SCRIPT.md`, `docs/speaker-script.md` | prose, per-audience |
| Submission format | `paper/tbc-v27/source/build_v27.py` | per-version, should be per-track |

All ~20 `EducationWorld` methods (`grant`, `read`, `derive`, `release`, `propose`,
`review_and_approve`, `execute`, `checkpoint`, ...) are already domain-neutral.

## The abstraction

A **track** is the unit of reuse:

    track = venue x world x pack x narrative x evidence view x submission format

The framework's real product is a **rendering pipeline from one evidence base to many
audiences**. Evidence stays single-source (`scripts/conference_evidence.py`, which
`--check` already pins). Tracks are views over it. This is what keeps the method honest
across conferences: the same executed numbers, re-narrated, never re-typed.

Two registers are in scope now:

- `academic` — UNU Macau. Hedged, referenced, SDG-framed.
- `engineering` — AIE CODE. Declarative, numeric, runnable-first.

### `tracks/<id>/track.yaml`

```yaml
track_id: aie-code-2026
title: "Per-Hop Auth Caught 2 of 10 Agent Attacks. Whole-Chain Caught 10."
venue:
  name: AI Engineer CODE Summit
  city: San Francisco
  audience: practitioner-engineers
  register: engineering
world: worlds/devtools-agent.yaml
pack:  packs/devtools-agent-pack.yaml
narrative: narrative.md
demos:      [spawn-fanout, secret-to-slack, ablation, revocation-race]
falsifiers: [F04, F10, F13]
figures:    [delegation-evidence, ablation, composition]
submission:
  format: markdown
  fields:
    - {name: title,       cap_chars: 120}
    - {name: description, cap_chars: 2000}
export:
  enabled: true
  entrypoint: "python demo.py"
  budget_seconds: 60
```

## Decomposition

Each sub-project gets its own plan and lands independently.

| # | Sub-project | Delivers | Depends on |
|---|---|---|---|
| P0 | Freeze guardrails | Branch isolation; UNU submission untouched | — |
| P1 | `ScenarioWorld` extraction | `education_world.py` becomes cast-driven | P0 |
| P2 | Devtools pack + failure tests | The AIE domain | P1 |
| P3 | Track abstraction | `tracks/`, UNU wrapped, AIE authored | P1, P2 |
| P4 | Export + cold-clone CI | The "clone and break it" promise | P3 |
| P5 | Talk-kit surface | Scaffolder, authoring docs, external validation | P3 |

P1-P4 deliver the talk. P5 is the only part that makes it a product, and it has no second
author yet, so it lands last and the talk is never hostage to it.

## P0 — Freeze guardrails

Today (2026-09-21) is the UNU deadline. `generate_results.py --check` pins 126 figures and
`verify_v27.py` fails the release when prose and run disagree.

- All work on `feat/demonstration-tracks`, branched from `integrate/third-audit-hardening`.
- Nothing merges to that branch until UNU is submitted.
- Specs live at repo-root `docs/superpowers/specs/`, deliberately **outside** `fssai-ra/docs/`,
  because `tests/test_learning_paths.py` does `DOCS.rglob("*")` and requires every file under
  `fssai-ra/docs/` to be linked from `docs/README.md` with a nav header and a
  "Recommended next:" line.
- Before any code change: record the baseline. `pytest` (expected 1,445), and
  `scripts/generate_results.py --check`, and `scripts/conference_evidence.py --check` must
  all pass, and their output is committed as the pre-refactor witness.

## P1 — `ScenarioWorld` extraction

**Chosen approach: cast as a sibling `world.yaml`, pack schema untouched.**

Considered and rejected:

- *Cast as a new `cast:` section in the pack YAML.* One file per domain, but it changes the
  pack schema, so `pack_floor` and all six shipped packs must accept it. That is a2's
  territory and risks the floor check on the eve of a submission.
- *Python subclasses supplying the cast.* Most flexible, no YAML work, but a track author
  must then write Python, which defeats P5.

Design:

- New `src/fssaira/scenario_world.py` defines `ScenarioWorld(pack_path, world_path, controls=...)`,
  holding every method currently on `EducationWorld`. The cast is loaded from `world.yaml`.
- `world.yaml` carries `subjects`, `principals`, `agents`, `resources`, `source_keys`, and
  `injection_patterns` — exactly the constants currently frozen at
  `education_world.py:95-135`.
- **`education_world.py` keeps its module name, its public names, and its behaviour.**
  `EducationWorld` becomes a thin subclass pinned to the education pack and a new
  `conference/education/world.yaml` extracted verbatim from today's constants.
  `ALL_CONTROLS`, `MEDIATOR_OF`, `NOW`, `action_root` stay exported from the same module.
  This satisfies a2 constraint 1: nothing cited by `fssaira thesis` F6 in
  `contract/bindings/core.yaml`, `threats/catalogue.yaml` or `docs/SPECIFICATION.md` moves
  or is renamed.
- Escape hatch: a world may declare `effects_module:` naming a Python hook for
  domain-specific effect semantics. Used only where a domain needs an effect education
  does not have.

**Acceptance:** the full suite passes unchanged at 1,445 tests, and
`conference_evidence.py --check` and `generate_results.py --check` still pass. P1 is a
pure refactor: if any figure moves, the refactor is wrong.

## P2 — Devtools pack, world, and failure tests

The AIE world is the abstract's opening paragraph made runnable.

| Element | Value |
|---|---|
| Subjects | `repo/acme-api`, `secrets/prod-db-url`, `customers.csv`, `incident-4412` |
| Data classes | `source-code`, `credentials`, `customer-pii`, `internal-incident`, `public` |
| Principals | `eng-oncall`, `security-reviewer`, `release-manager` |
| Agents | `coordinator`, `reader-agent`, `summarizer-agent`, `publisher-agent`, `rogue-agent` |
| Effects | `merge_pr`, `trigger_deploy`, `post_message`, `spawn_worker` |

Headline demo — **the chain leaks a credential into `#general`.** Reader, summarizer and
publisher each hold a soundly-scoped tool list. The composition forms a path from
`secrets/prod-db-url` to a public channel. No agent misbehaves; the chain does. This is the
existing composition claim, re-cast into a world the audience works in.

Second demo — the three arms behind the title: unguarded chain, per-hop validation against
the immediate delegator, whole-chain verification. Generalises `conference_demo.py` demo 5.

Delegation machinery is expected to be reusable, not new: `education_world.py:123` already
carries `sub-agent-b`, `sub-agent-c`, `rogue-agent`, and `src/fssaira/grant_delegation.py`
exists. P2 should confirm this before authoring anything.

**Known blocker, requires coordination.** `pack_floor` refuses a pack whose declared
`controls` name failure tests that do not exist, so the devtools pack forces new tests. But
a2 constraint 4 says `test_count` is one of the 126 pinned figures and is quoted in
`docs/REVIEWERS.md`. P2 therefore cannot land without a figure regeneration coordinated
with session a2. This is a handoff, not a code problem, and it is the likeliest thing to
stall the work. Raise it with a2 at the start of P2, not the end.

## P3 — Track abstraction

- New top-level `tracks/` with `unu-macau-2026/` and `aie-code-2026/`.
- UNU is **wrapped, not moved**: its `track.yaml` points at the existing
  `conference/education/` pack and the extracted world. No existing path changes, so no
  cited path breaks.
- `fssaira track list | show | run | validate`.
- `scripts/conference_evidence.py` gains a `--track` filter; it stays the sole figure
  source.
- Submission builder generalises from per-version to per-track: `build_v27.py` keeps
  working, and its field-cap and CRLF-counting logic (`check_submission.py`) becomes a
  reusable `submission:` renderer driven by `track.yaml`. This also retires the
  `tbc-v11 ... v27` directory sprawl for future papers.

## P4 — Export and the cold-clone guarantee

The abstract promises the audience can clone it and try to break it during the talk. That
is a testable claim, so it gets a test.

- `scripts/export_track_repo.py` generates a thin standalone repo from a track: kernel
  subset, one world, one pack, the selected demos, a README whose first screen is one
  command. **Generated, never hand-edited** — a publish target, not a fork.
- CI job: cold clone into a clean container, no network after clone, no API key, no GPU,
  assert a successful result inside `export.budget_seconds` (60s).
- The export carries its own provenance line naming the source commit, so a stale export is
  visible rather than silent.

## P5 — Talk-kit surface

- `fssaira track new <id>` scaffolder emitting a valid skeleton track.
- `track.yaml` JSON Schema plus `fssaira track validate` with useful errors.
- Authoring guide. Note it must live under `fssai-ra/docs/`, so it needs a `docs/README.md`
  link, a nav header, and a "Recommended next:" line, or `test_learning_paths.py` fails.
- External world/pack validation reusing `pack_floor`, so a third-party track cannot weaken
  the kernel — the same guarantee the malicious pack already tests.

## Risks

| Risk | Mitigation |
|---|---|
| Refactor destabilises the UNU submission on deadline day | P0 branch isolation; nothing merges until submitted |
| `test_count` figure churn blocks P2 | Raise with a2 at P2 start |
| Extracted cast silently changes a figure | P1 acceptance is byte-identical figures |
| Export drifts from kernel | Generated only; provenance line; cold-clone CI |
| P5 built for an audience of one | Sequenced last; P1-P4 deliver the talk without it |

## Out of scope

Distributed evaluation of the swarm bound, live-model demos as a default path, any change
to `src/fssaira/disclosure*.py` (a2 owns it; wrap, never fork), and any edit to
`paper/`, `generate_results.py`, `test_paper_alignment.py`, slides, `SPECIFICATION.md`, or
sector profiles without messaging a2 first.
