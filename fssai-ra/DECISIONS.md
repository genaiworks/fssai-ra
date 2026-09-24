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

## D9 — Lifecycle stage 2 is `fssaira contract --gate`, not a new command

**Decision.** `fssaira contract` already shows the contract, and the README
documents `fssaira contract --output contract.json`. Registering a second
`contract` parser raised `conflicting subparser`. Stage 2 is therefore an opt-in
`--gate` flag on the existing command. Without it the command is unchanged,
which a test asserts. The other stages are new top-level commands: `frame`,
`pack`, `bind`, `falsify`, `promote`, `operate`.

## D10 — The ablation gate does not demand that every single control be load-bearing

**Decision.** `ablations_restore_harm` requires three things. Every ablation row
must show no harm with controls enabled and after restoring them. Every
falsifier must have at least one load-bearing control or declared control pair.
And the rows where another control independently stopped the attack are
reported as defence in depth.

**Why.** In the education suite, some single-control rows are honestly "NO":
the router attack needs residency and model attestation removed together, and
replay needs digest binding and single-use approval removed together. Requiring
every single row to be load-bearing would push someone to delete a redundant
control to pass a gate. A redundant defence need not become dispensable to
qualify (paper §6, stage 5).

## D11 — A pack manifest references enforced configuration and must match it exactly

**Decision.** `packs/*.pack.yaml` carries no enforcement. It references
`profiles/*.yaml` (and, for education, the governed-learning pack). `load_pack`
fails on any mismatch between what the manifest declares and what the profiles
enforce, in either direction: purposes, classes and zones, recipients,
transitions and approvers, declassification, emergency access.

**Why.** Two copies of a policy drift. A manifest claiming more than the runtime
enforces is exactly the failure this project exists to prevent.

**Reopen when.** Profiles and pack manifests merge into one format.

## D12 — Floor rules that cannot apply to action profiles are reported, not skipped

**Decision.** `PACK_CONTROL_CONTRACT_MISSING` and `PACK_REVIEW_OVERLOAD_FAILS_OPEN`
are recorded in each pack's `floor_exemptions` only when the profile has no
`controls` or `review` key. Kernel capability contracts stand in for
per-operation controls: CAP-ACT-1, 2, 3 and CAP-EVI-1, plus CAP-DIS-1 and 2 when
disclosure is declared. **Nothing stands in for review capacity.** Every pack's
`limits` says so, and the promotion gate reports it.

**Reopen when.** The action-profile format gains a `review` section.

## D13 — `evaluate_pack` covers what the published matrix covers, nothing more

**Decision.** It runs `verify_profile`, `EvaluationRunner` and
`run_disclosure_suite` for each referenced profile, and returns separate figures
with named units and no pooled total. The governed-learning pack is checked
against the floor at load time but is not evaluated. It is listed in
`not_evaluated`, so education has no disclosure figures, consistent with Table 3.
A transfer test proves a new sector built only in a temporary directory loads,
passes the floor and evaluates, with kernel and mediator source hashes unchanged.

## D14 — Server-derived security fields in model JSON are rejected, not stripped

**Decision.** `integration.typed` refuses a proposal or context request that
carries principal, tenant, policy version, label or classification, role,
authority or approval. The name can be in any case, full-width form or
Unicode normalization, and at any depth. Each such refusal gets its own code.
These values come only from the authenticated `CallerContext`.

**Why.** Silently dropping an attempted self-authorization hides both attacks
and integration bugs. Refusal makes the attempt visible in evidence.

## D15 — Importing a memory artifact is a new disclosure

**Decision.** `integration.memory` makes a summary, cache entry, vector entry
or agent handoff usable in a new session only after two things. The artifact's
sources are re-read through the real `DisclosureGate`, under the importing
session's own grant. And the gate labels the session with them before the
content is handed over. Invalidation follows the derivation graph when a source
version, grant or consent changes. An artifact with no recorded lineage is
quarantined.

**Residual (stated in RECONCILIATION R7).** The gate has no lineage for content
that bypasses governed memory. Text pasted into a fresh session is labelled at
the bottom. Output screening catches verbatim reuse, not paraphrase. Rule 2's
"cannot launder what it saw" holds only for content that flows through the
gate and governed memory.

## D16 — Model evidence must come from outside the model

**Decision.** `integration.bundle` digests eight components: weights, adapter,
tokenizer, runtime, system template, decoding configuration, tool catalogue and
retrieval configuration. It signs the bundle manifest. A change to any component
suspends the bundle until two things exist: a new signed manifest, and a fresh
measurement taken by a callable independent of the runtime. Reverting the bytes
does not restore trust. A runtime's self-reported digest is refused even when it
matches.

The older `ModelRegistry.attest` still accepts a runtime-reported digest. It is
left unchanged for compatibility and recorded as RECONCILIATION R8.

## D17 — Backend assurance is bound to the code on disk; enforced in pilot/production only

**Decision.** A `ConformanceRecord` binds a backend name, a digest of that
backend's module sources, and a suite id that includes the conformance suite's
own digest. `runtime_factory.build_control_plane` refuses to start a pilot or
production deployment unless every backend in use has a current passing record
(`FSSAI_CONFORMANCE_RECORDS`). The teaching profile records the status
(`NOT_REQUIRED_TEACHING`) and never refuses.

**Why.** Enforcing it in teaching would break every demonstration. A
consequential profile is where "a backend inherits no assurance" matters.

**Residual.** A record is a local JSON file, not a notarized attestation. An
attacker who can replace both code and record defeats it, which is the same
trusted-host limit as the evidence manifest.

## D18 — `strict_json` rejects overflowing float literals

**Decision.** `joined_workflow.strict_json` adds a `parse_float` hook that
rejects non-finite results. `tests/test_joined_strict_json.py` pins `1e999`,
`-1e999`, `1E400`, nested cases and finite controls.

**Why.** `parse_constant` sees only the `NaN` and `Infinity` literals. `1e999`
reached `float()` and became `inf`, contradicting §6.1's "reject non-finite
numbers". Found by the M4 integration work.

## D19 — Only three values in audit/results.json are derived at collection time

**Decision.** Every other leaf is read verbatim from a committed
machine-written file. The three derived values:

- the claims register, a pure function of the contract files;
- Table 5 counts, taken from raw per-episode records and refused if they
  disagree with the committed summary;
- denominators that exist only as key names in their source.

Each carries a `derivation` field, and tests re-run it. Because the collector
hashes `contract/**/*.yaml`, adding a capability contract requires re-running
`collect_results.py`, or `--check` fails as intended.

## D20 — The binder reads word numbers and binds quotes, not bare numbers

**Decision.** The binder extracts both digit tokens and spelled-out cardinals,
from "zero" up. It skips "one", which works as an article in this prose, and
ordinals.

A binding quotes an exact paper substring and covers only the tokens its bound
values match. A number inserted into an already-bound sentence is therefore
still reported.

## D21 — figures/ reuses the paper renderer; PNG is never faked

**Decision.** `figures/fig1..fig7.svg` come from the renderer in
`generate_paper_figures.py` and are byte-identical to `paper/figures/`.

PNGs are headless-Chrome screenshots. They are excluded from the byte check,
because rasters vary across Chrome versions. When Chrome is absent, the manifest
records `png: "NOT RUN: <reason>"` rather than a placeholder file.

## D22 — An unrecognised FSSAI_DEPLOYMENT_PROFILE refuses to start

**Decision.** `runtime_factory` accepts exactly `teaching`, `pilot` and
`production`.

**Why.** Previously any other value, such as `prod` or `staging`, fell through
to teaching behaviour. It skipped both the teaching-defaults refusal and the
backend-assurance refusal: a fail-open found while reviewing the M4 wiring.

## D7 — Backend assurance is a signed-off record, checked at construction

**Decision.** `kernel/assurance.py` refuses to hand out a backend unless a
conformance record exists for that backend's implementation digest, with every
check passing. A changed implementation digest invalidates the record.

**Why.** It encodes "a backend inherits no assurance until the same conformance
and falsifier suites pass on it" as a constructor precondition rather than a
warning.
