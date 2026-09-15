# DECISIONS

Non-obvious choices, newest last. Each entry gives the decision, why it was
made, and what would reopen it.

## D1 — Wrap, don't move (2026-09-14)

**Decision.** The `kernel/`, `mediators/`, `planes/`, `integration/` and
`lifecycle/` subpackages are new enforced interfaces over the existing flat
modules. Existing modules are not relocated or renamed.

**Why.** The audited tree has 78 modules, 945 passing tests and 126 figures
pinned by `generate_results.py --check`. The thesis falsifier F6 fails the build
when a binding, the threat catalogue or `docs/SPECIFICATION.md` cites a function
or test that no longer exists. Other sessions commit to the same files. A move
would convert a working, falsifiable system into an unverified one for the sake
of a directory layout.

**Reopen when.** After submission, a move can be done mechanically with
compatibility re-exports and a citation rewrite, gated by F6.

## D2 — New seven-field capability contracts sit beside the legacy contract

**Decision.** `contract/capabilities/*.yaml` uses the exact field names
`protected_asset, permitted_operation, enforcement_point, accountable_owner,
failure_test, evidence_artifact, failure_response`. Here `failure_test` is a
machine-resolvable pytest locator (`tests/path.py::name`), not prose. The legacy
`contract/*.yaml` (keys `owner`, `test`) and `bindings/core.yaml` stay
authoritative for the published 41/3/0 register. The kernel loader reads both;
legacy entries resolve tests through their bindings.

**Why.** Renaming keys in the legacy contract would change the register the
paper quotes. A prose `test:` cannot be checked to exist.

## D3 — Test existence is resolved by AST, not substring

**Decision.** A **test** locator resolves only if the file parses and defines
that exact pytest node (`tests/f.py::test_x` or `tests/f.py::TestC::test_x`). The
final name must start with `test` and any class with `Test`. A **source**
locator (`src/f.py::name`) resolves to that exact path, or to exactly one
definition carrying the name (`file::method` shorthand); two candidates make it
ambiguous and unresolved. Comments and strings never count. A named-but-missing
test raises `ContractError`, which fails `pytest` and every lifecycle gate. A
separate test runs `pytest --collect-only` on every capability failure test, so
existence in source is also checked against collection.

**Why.** The audit found that the existing check accepted a symbol appearing
anywhere as a substring and matched only column-0 `def`. The first strict run
flagged four legacy bindings (IB-1, RD-1, BI-1, AA-3) naming
`src/fssaira/evaluation.py::<method>`. These are real methods of the evaluation
runner written without their class, not missing checks. The shorthand is
therefore accepted for source locators only when unambiguous, and
`contract/bindings/core.yaml` is left unchanged (F6 citations).

## D4 — `audit/results.json` is a collector, not a recomputation

**Decision.** `scripts/collect_results.py` reads committed JSON from
`evaluation/results/`, `conference/evidence/` and `audit/`, keeps each unit and
denominator separate, and records the source file digest of every value. The
regeneration that proves those files are real stays in `generate_results.py
--check`, `conference_evidence.py --check` and `adaptive_evidence.py`, which
`make results` runs first.

**Why.** Two computations of the same figure can diverge; one source per figure
cannot. (Constraint from session a2.)

## D5 — Rule-1 rationale independence is tested as a property of the real executor

**Decision.** The executor facade has no rationale parameter that reaches the
decision. The test drives `AccountableExecutor` with the same proposal under
absent, reassuring, fabricated-authority, false-citation and misleading
rationale. It asserts byte-identical decisions and error codes, and uses a
positive control that feeds the rationale into a deliberately broken decider,
proving the test can fail.

## D6 — Generated-code sandbox is process-level containment, not a security boundary

**Decision.** `integration/sandbox.py` runs code in a separate interpreter with
an empty environment, `-I` isolated mode, a temporary working directory, POSIX
rlimits (CPU, address space, file size, open files) and a wall-clock timeout.
Its docstring and `docs/DEPLOYMENT.md` state that this does not isolate hostile
code from the same OS user's files or network. The executed host-isolation
probe in `audit/host-isolation-probe.json` stays the honest result. A container,
VM or separate user is a deployment obligation.

## D8 — The untrusted agent no longer receives the evidence write credential

**Decision.** `BoundedAgent.__init__` drops its `evidence` and `append_token`
parameters, and `FSSAIRAPipeline.make_agent` stops passing them. This is a
constructor signature change to a public class. The pipeline was the only caller
in the repository.

**Why.** The first run of `tests/planes/test_planes.py` found that the pipeline
handed `BoundedAgent`, an intelligence-plane component, the same
`EVIDENCE_TOKEN` the ledger and enforcement point use. The agent stored it and
never used it. The model interface (`propose(task, evidence_items)`) gave the
model no path to it. But planes in one process are not isolation, and "the
intelligence plane holds no key, token map or write credential" was true only by
convention. Removing an unused credential costs nothing and makes the rule
checkable. The instance-level test now asserts the credential value appears in
no attribute of a live agent.

**Reopen when.** An agent needs to write evidence. It should not: evidence is
written by the enforcement point.

## D7 — Backend assurance is a signed-off record, checked at construction

**Decision.** `kernel/assurance.py` refuses to hand out a backend unless a
conformance record exists for that backend's implementation digest, with every
check passing. A changed implementation digest invalidates the record.

**Why.** It encodes "a backend inherits no assurance until the same conformance
and falsifier suites pass on it" as a constructor precondition rather than a
warning.
