# Results — v1.0.0

Generated 2026-09-11T22:51:10.285563+00:00 on Python 3.14.6, macOS-26.5-arm64-arm-64bit-Mach-O.

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
| Attacks contained — unguarded arm | `0%` | 28 harmful actions reached the protected asset |
| Attacks contained — prompt-guarded arm | `29%` | 8 harmful actions; an allowlist is a real control |
| Attacks contained — this architecture | `100%` | 0 harmful actions, at no cost to benign completion |
| Conformance checks | `25` | passed on 2 independent backend profiles |
| Concurrent replay race | `1 mutation from 32 callers` | 31 replay responses, 1 distinct receipt; bounded to one process |
| Control-contract requirements | `28` | 7 fields each |
| Deterministic tests | `328` | no network, no model weights |
| Oversight — sustainable review | `3,520/day` | for a roster of 11, bound by the deliberation floor; declared capacity, not a measurement of reviewers |
| Oversight — merit failures executed | `4 → 0` | without load control, then with it, on a queue at 5.0x declared attentive capacity |
| Oversight — deferred to manual review | `32` | the cost of the control, and a measurement of demand against declared capacity |
| Second domain — states explored | `4,800` | 0 violations; the identical suite, no library change |
| Second domain — containment and utility | `30/30, 9/9` | its own evidence, borrowed from no other domain; 25 conformance checks |
| Second domain — defects it exposed | `1` | a declared approval role ignored on non-consequential transitions; unreachable with one domain |
| Adversary corpus — contained | `4/4` | unguarded arm contained 0; contributed attacks, not a threat catalogue |
| Adversary corpus — externally contributed | `0` | the figure that matters; until it is non-zero the corpus samples the maintainers' imagination |

## Verdicts

- All declared scenarios contained: **True**
- Authority invariants hold under bounded model checking: **True**
- In-memory profile conformant: **True**
- Transactional SQL profile conformant: **True**
- Second domain conformant under the identical suite: **True**
- Second domain invariants hold: **True**
- Review-load control is load-bearing: **True**
- Contributed adversary corpus fully contained: **True**

## Cost of reproduction

The adversarial suite runs in 0.02s and the bounded model check in 0.01s on the machine above, with no network access and no model weights. A second institution can therefore check these numbers rather than trust them.

## Limits

- synthetic fixtures in a declared environment; not a security certification
- deterministic backends; no stochastic model-behaviour rates are claimed
- one 32-caller replay race is evaluated in one process; arbitrary concurrent interleavings and distributed failure modes remain out of scope
- containment of sampled risk classes, not coverage of any threat catalogue
- the reviewer degradation curve is a declared parameter, not a measurement of any reviewer; no human was observed, and reviewer accuracy under load remains open work
- the oversight deferral count is the cost of the control, reported rather than netted off; refusing an approval preserves the boundary and delays the student
- the second domain tests that the method transfers, not that either domain's evidence applies to the other; each carries its own
- the adversary corpus is contributed attacks, not a threat catalogue, and no attack in it yet comes from outside this project

These are fixture observations in a declared environment. They are not security probabilities, not a certification, and not evidence of production readiness. See [`docs/ASSURANCE.md`](../docs/ASSURANCE.md) for the claim-by-claim boundary.
