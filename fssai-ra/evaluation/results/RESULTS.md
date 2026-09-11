# Results — v1.0.0

Generated 2026-09-11T01:43:33.299952+00:00 on Python 3.14.6, macOS-26.5-arm64-arm-64bit-Mach-O.

Regenerate with `python scripts/generate_results.py`. Every figure the paper quotes comes from this table, and `tests/test_paper_alignment.py` fails the build if the two disagree.

| Measure | Result | What it does and does not mean |
|---|---|---|
| Adversarial scenarios contained | `30/30` | containment of sampled risk classes, not coverage of a threat catalogue |
| Unauthorized mutations | `0` | across every denial scenario |
| Benign tasks completed | `6/6` | the denominator that makes a containment rate meaningful |
| False-denial rate | `0.0` | a system that denies everything scores perfectly on containment |
| Authority coverage | `1.0` | 8/8 controls restored their harm when removed |
| States explored (model check) | `240` | 5 invariants, 0 violations |
| Distinct denial controls reached | `11` | each one exercised by at least one configuration |
| Conformance checks | `25` | passed on 2 independent backend profiles |
| Control-contract requirements | `25` | 7 fields each |
| Deterministic tests | `149` | no network, no model weights |

## Verdicts

- All declared scenarios contained: **True**
- Authority invariants hold under bounded model checking: **True**
- In-memory profile conformant: **True**
- Transactional SQL profile conformant: **True**

## Cost of reproduction

The adversarial suite runs in 0.02s and the bounded model check in 0.01s on the machine above, with no network access and no model weights. A second institution can therefore check these numbers rather than trust them.

## Limits

- synthetic fixtures in a declared environment; not a security certification
- deterministic backends; no stochastic model-behaviour rates are claimed
- single process; concurrent interleavings are not evaluated here
- containment of sampled risk classes, not coverage of any threat catalogue

These are fixture observations in a declared environment. They are not security probabilities, not a certification, and not evidence of production readiness. See [`docs/ASSURANCE.md`](../docs/ASSURANCE.md) for the claim-by-claim boundary.
