# Contributing

FSSAI-RA is meant to be extended into a secure baseline for your own systems.
The discipline is simple: **every control is a property with a test.** If you
cannot write a failing test that the control makes pass, it is not a control
yet.

Before editing code, read `docs/EXTENDING.md`. State whether the contribution
targets the teaching, institutional-pilot, or hardware-isolated profile. Passing
teaching-profile tests must not be presented as production assurance.

Before adding or renaming documentation, read `docs/README.md`. Every artifact
under `docs/` must be linked from that map. Every Markdown guide must carry the
common navigation block and a recommended next step. The documentation-link
tests fail if a file becomes orphaned or a local link breaks.

## Add a control
1. Add a requirement to the relevant `contract/*.yaml` with all seven fields
   (protected asset, permitted operation, enforcement point, owner, test,
   evidence artifact, failure response).
2. Implement the enforcement in the matching `src/fssaira/*.py` domain module.
3. Add an attack test in `tests/test_attacks.py` that fails without the control.
4. Add an ablation in `tests/test_ablations.py` showing the harm returns when
   the control is removed.
5. Add a benign-path test and record false denials or operational burden.
6. **Bind the requirement in `contract/bindings/`** to the check you just wrote,
   naming the mechanism and a locator. Run `fssaira coverage`: it must report
   **0 unverified**, and it resolves your locator against the real source, so a
   binding pointing at a test that does not exist fails the build.

   If the control genuinely cannot be proved in code — key custody, a signed
   interface inventory, a manual fallback a real person staffs — declare
   `verified_by: organizational` on the requirement with an `attested_by` role
   and an `attestation_cadence`. That is a weaker claim than a test and is
   counted separately for exactly that reason; the number of such entries is
   pinned so that growing it is a deliberate edit.

   This step exists because we skipped it ourselves. Eighteen of twenty-eight
   requirements described a failure test and were bound to nothing: the tests
   mostly existed, nothing connected them, and deleting one would have removed a
   governance claim in silence.

## Add a new application domain
Reuse the five domains; add tools to the registry, define a least-privilege
agent (allowed tools, permitted operations, data scope), and write the contract
entries and tests for the new consequential actions.

## Swap in production backends
Implement the adapter seam (see `adapters/`) so the property and its test still
hold. A backend is acceptable only if the domain's contract test passes against
it.

## Run checks
```
pip install -e ".[dev,privacy,api]"
pytest -q
python -m pytest tests/test_learning_paths.py -q
```

Pull requests should disclose assumptions, excluded paths, synthetic-data or data
license status, and any control that shares an administrator with the agent runtime.
Do not include secrets or identifiable student records.
