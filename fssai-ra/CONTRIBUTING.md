# Contributing

FSSAI-RA is meant to be extended into a secure baseline for your own systems.
The discipline is simple: **every control is a property with a test.** If you
cannot write a failing test that the control makes pass, it is not a control
yet.

## Add a control
1. Add a requirement to the relevant `contract/*.yaml` with all seven fields
   (protected asset, permitted operation, enforcement point, owner, test,
   evidence artifact, failure response).
2. Implement the enforcement in the matching `src/fssaira/*.py` domain module.
3. Add an attack test in `tests/test_attacks.py` that fails without the control.
4. Add an ablation in `tests/test_ablations.py` showing the harm returns when
   the control is removed.

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
pip install -e ".[dev]"
pytest -q
```
