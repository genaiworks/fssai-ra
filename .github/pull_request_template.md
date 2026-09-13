## Contribution

Describe the bounded workflow, consequential action, and assurance profile.

## Control contract

- Protected asset:
- Permitted operation:
- Independent enforcement point:
- Accountable owner:
- Failure test:
- Evidence artifact:
- Failure response and manual continuity:

## Composition

Answer both. "Not applicable" is a fine answer; "not considered" is not.

- Does anything act *on behalf of* this agent — a sub-agent, plugin, or tool
  server this project does not govern directly? If so, what bounds the chain?
- Does a model help the human reviewer decide? If so, is it independent of the
  proposing model — a different model, a different evidence path, an adversarial
  posture?

## Evidence

- [ ] Contract validation passes
- [ ] `fssaira coverage` reports **0 unverified** — every requirement I added is
      bound in `contract/bindings/` to a check that runs, or declared
      `verified_by: organizational` with a named role and a cadence
- [ ] Attack test inspects the real side effect
- [ ] Benign-path test is included
- [ ] Ablation is included or its omission is explained
- [ ] `pytest -q` passes
- [ ] `python scripts/generate_results.py --check` reports no drift, if I changed
      anything a published figure depends on
- [ ] No secrets or identifiable records are present

## Limits

State shared administrators, untested paths, excluded threats, data/model licenses,
and any reason the result should not be generalized beyond the declared profile.
