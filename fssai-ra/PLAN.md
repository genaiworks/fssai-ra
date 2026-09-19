# Code build plan

The supplied build brief guides this implementation. The latest user request authorizes code enhancements and a revised TBC paper. Preserve the original v11 source and publish a revised Word copy with tested claims and explicit deployment gaps.

## Baseline and gaps

The working tree already passes 1,048 tests and contains two mediators, six action profiles across five sectors, four disclosure profiles, encrypted-record/tokenization components, signed manifests, conference evidence, seven SVG figure generators, the joined SQLite workflow, and adaptive/tabular-Q evaluation. Preserve these implementations and their public imports. The earlier TBC SDK is an additional reference path, not a replacement for every older interface.

Missing or incomplete relative to the brief: canonical seven-field contracts with executed-test evidence; a discoverable sector-neutral pack API with an enforced kernel floor; complete model-bundle version binding; strict versioned integration messages; authorized streaming; a seven-stage lifecycle CLI with freshness-aware promotion; consolidated audit/results.json and submission metric bindings; top-level offline make all; PNG figure generation; typed public architecture packages and honest backend qualification.

## Milestones

1. M0: preserve the tested starting point, specification hashes, this plan, target tree and decisions.
2. M1: test-first canonical control contracts, test locator validation, executed evidence and narrow public kernel interfaces.
3. M2: test-first typed mediation boundaries, no-rationale authority and explicit plane interfaces, preserving existing mediators.
4. M3: test-first declarative pack loader, five sector packs, template and per-pack evaluation over unchanged kernel.
5. M4: test-first strict integration schemas, full model bundles, protected retrieval and reauthorized streaming; qualified adapter registry.
6. M5: consolidate real generated experiments and executed contract tests into audit/results.json; generate SVG and PNG figures outside paper/.
7. M6: retain and rerun joined durable and adaptive/tabular-Q evidence with independent state/byte oracle and matched positive controls.
8. M7: test-first seven lifecycle commands, promotion/conformance gates, docs, offline make all and CI.
9. M8: run the full build and regenerate tables; classify discrepancies in RECONCILIATION.md. Revise the Word paper after evidence is regenerated; preserve the original.

Each implementation milestone ends with relevant passing tests and a local commit. No push or deployment. Broad existing suites run at integration gates; unsupported production paths stay explicitly unqualified.

## Target tree

```
fssai-ra/
  PLAN.md DECISIONS.md RECONCILIATION.md
  src/fssaira/
    kernel/       # canonical contract + pack engine, executed evidence, invariant/state APIs
    planes/       # explicit role contracts and existing implementation bindings
    mediators/    # stable executor and context-gate APIs
    integration/  # versioned messages, model bundles, retrieval, streams
    lifecycle/    # gated frame/contract/pack/bind/falsify/promote/operate
    adapters/     # named adapter factories and evidence-qualified backend selection
    tbc/          # retained v11 SDK and Guardian
  packs/          # five sector packs + template.pack.yaml
  contract/       # existing controls + canonical capability contracts in a subdirectory
  eval/           # consolidated experiment entry point and provenance
  figures/        # fig1 through fig7, SVG and PNG
  audit/          # results.json, tables, claims register, raw trajectories and executed tests
  scripts/        # existing generators, consolidated collector and submission checker
  tests/          # new contract/pack/integration/lifecycle regression suites
  deploy/         # explicit reference/operational gate profiles
  docs/           # authoring, architecture and deployment guides
```

## Acceptance

No fabricated result or pooled coverage percentage. Missing, skipped or failing failure tests never count as machine verified. A backend gets no qualification merely by naming an adapter. Model-generated authority fields are rejected. Operational promotion requires exact, fresh independently attributable deployment evidence; passing local fixtures permits only a teaching deployment. `make all` must execute tests, lint, scoped static typing, results, figures and submission checks offline after dependencies are installed.
