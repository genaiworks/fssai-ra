# Results — v1.0.0

Generated 2026-09-13T12:31:08.642236+00:00 on Python 3.14.6, macOS-26.5-arm64-arm-64bit-Mach-O.

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
| Conformance checks | `26` | passed on 2 independent backend profiles |
| Concurrent replay race | `1 mutation from 32 callers` | 31 replay responses, 1 distinct receipt; bounded to one process |
| Control-contract requirements | `44` | 7 fields each |
| Delegation — chains contained | `10/10` | unguarded arm contained 0; per-hop validation contained 2; the benign two-hop chain completes |
| Delegation — invariants load-bearing | `9/9` | each removed in turn; every removal restored its harm |
| Delegation — states explored | `768` | 5 invariants, 0 violations, over the declared chain space |
| Assisted review — merit failures | `5 → 1` | dependent then independent review assistant, identical lowered floor; every runtime mechanism passed in both |
| Assisted review — benign completed | `7 → 35` | unaided then assisted: assistance is worth 5.0x in completed legitimate work, which is why institutions will buy it |
| Contract coverage — machine-verified | `41/44` | 3 organizationally attested, 0 unverified; every requirement bound to a check that is itself checked to exist |
| Deterministic tests | `648` | no network, no model weights |
| Oversight — sustainable review | `2,640/day` | for a roster of 11, bound by the policy quota; declared capacity, not a measurement of reviewers |
| Oversight — merit failures executed | `4 → 0` | without load control, then with it, on a queue at 5.0x declared attentive capacity |
| Oversight — sensitivity sweep | `16/20` | cells where the control was load-bearing out of those where harm was possible; harm reached zero in 16; 4 did not bind (no deliberation floor configured); 5 had no harm to contain |
| Oversight — false-positive cost | `0` | deferrals across the whole sweep where there was no harm to contain; an attentive reviewer is not throttled by the shipped policy |
| Oversight — smallest floor that fully contains | `5s` | across every swept cell where harm was possible; the number an institution needs to set its own policy |
| Oversight — deferred to manual review | `32` | the cost of the control, and a measurement of demand against declared capacity |
| Domain packs — independently verified | `4` | 33,600 total bounded states; education, corporate confidential data, and healthcare record access; synthetic fixtures, not sector-compliance evidence |
| Domain packs — containment and utility | `120/120, 37/37` | separate denominators per pack; 0 unauthorized mutations |
| Governed disclosure — flows contained | `44/44` | across 2 packs; conventional access control contained 16, unguarded retrieval 0; 5/5 legitimate flows completed |
| Governed disclosure — checks load-bearing and states explored | `13/13, 6,900` | 0 violations; synthetic records, and redaction is not de-identification |
| Threat and alignment catalogue | `17 contained, 10 bounded, 5 residual` | of 32 failure classes, 12 of them alignment failures; every evidence locator is checked to exist; containment is a fixture observation, not a probability |
| Second domain — states explored | `4,800` | 0 violations; the identical suite, no library change |
| Second domain — containment and utility | `30/30, 9/9` | its own evidence, borrowed from no other domain; 26 conformance checks |
| Second domain — defects it exposed | `1` | a declared approval role ignored on non-consequential transitions; unreachable with one domain |
| Adversary corpus — contained | `7/7` | unguarded arm contained 0; contributed attacks, not a threat catalogue |
| Adversary corpus — externally contributed | `0` | the figure that matters; until it is non-zero the corpus samples the maintainers' imagination |

## Domain-pack matrix

Each row has its own denominator. These synthetic checks demonstrate reuse of the authority kernel, not sector compliance or production safety.

| Pack | Domain | States | Hostile scenarios | Benign tasks | Unauthorized mutations |
|---|---|---:|---:|---:|---:|
| `student-support` | education-support | 240 | 30/30 | 6/6 | 0 |
| `academic-record-correction` | education-records | 4,800 | 30/30 | 9/9 | 0 |
| `corporate-confidential-data` | corporate-data | 8,400 | 30/30 | 10/10 | 0 |
| `healthcare-record-access` | healthcare-data | 20,160 | 30/30 | 12/12 | 0 |

## Verdicts

- All declared scenarios contained: **True**
- Authority invariants hold under bounded model checking: **True**
- In-memory profile conformant: **True**
- Transactional SQL profile conformant: **True**
- Second domain conformant under the identical suite: **True**
- Second domain invariants hold: **True**
- All independently reported domain packs hold: **True**
- Review-load control is load-bearing: **True**
- The control never increased harm in any swept cell: **True**
- The shipped review policy is self-consistent: **True**
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
- the four domain packs test reuse of one authority kernel across synthetic workflow shapes; they do not establish sector compliance or operational safety, and each domain must carry its own evidence
- the adversary corpus is contributed attacks, not a threat catalogue, and no attack in it yet comes from outside this project
- the delegation results bound authority under composition, not the competence or intent of any hop; a fully attenuated chain can still carry a substantively wrong action, and no real multi-agent deployment was observed
- the proposer/assistant error correlation is a declared parameter, exactly like the reviewer degradation curve: no model was evaluated and no rate is claimed for any named system
- contract coverage measures that a control is exercised, never that it is adequate; an organizational attestation is a named role's word on a declared cadence and is counted separately from a test for that reason

These are fixture observations in a declared environment. They are not security probabilities, not a certification, and not evidence of production readiness. See [`docs/ASSURANCE.md`](../../docs/ASSURANCE.md) for the claim-by-claim boundary.
