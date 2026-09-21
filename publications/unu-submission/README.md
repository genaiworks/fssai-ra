# UNU submission: verification record

Status: **submitted**, as reported by the repository owner. Acceptance and
publication are not asserted. This record supports independent verification of
the software without altering submitted manuscript bytes.

## Artifact identity remains unconfirmed

The exact uploaded PDF, its SHA-256, submission date, manuscript version, and
software commit used for its reported experiments have not yet been confirmed.
Multiple local drafts exist. None is silently selected as the submitted paper.
The public repository deliberately excludes those drafts.

Before claiming complete reproduction of the submitted paper, record:

1. Submitted title/version, venue/track, submission date, and exact PDF SHA-256.
2. An approved public PDF or immutable archive URL, if sharing is permitted.
3. Full software commit and archived experiment inputs/environment.
4. A row for **each** numerical or empirical paper claim: page/table, exact claim,
   raw result key, command, parameters/seed/bounds, observed result, and limitations.
5. Claims that are analytical, cited from other work, attested, or unavailable,
   distinguished from results reproduced by executing this repository.

## Current executable evidence map

The [public verification guide](../../fssai-ra/docs/PUBLIC_VERIFICATION.md) provides
the Docker commands, evidence retention, custom-domain workflow and scope.

| Claim family | Public evidence | Reproduction command (inside application directory) |
|---|---|---|
| Containment, benign utility, control ablation, bounded authority, six-domain transfer, disclosure, delegation and oversight simulations | [Main results](../../fssai-ra/evaluation/results/RESULTS.md) | `python scripts/generate_results.py --check` |
| Education falsifiers, identity custody and release controls | [Education scorecard](../../fssai-ra/conference/evidence/SCORECARD.md) | `python scripts/conference_evidence.py --check` |
| Concurrency and crash recovery | [Resilience record](../../fssai-ra/evaluation/results/resilience-student-support.json) | `python scripts/check_resilience.py` |
| Covert release channels | Experiment implementation and committed measurement | `python scripts/measure_covert_channels.py --check` |
| SDK, joined workflow and evidence receipts | Fresh bundle `sdk/` and `joined/` | `python scripts/reproduce.py --full --timeout 1800` |
| Architecture capability bindings | Fresh bundle `architecture/` | Included in the full reproduction |

This is a **claim-family index**, not yet a page-by-page attestation of the submitted
paper. A passing public run must not be described as validation of an unidentified
PDF. Empirical claims remain bounded by synthetic fixtures, declared reviewer
assumptions, the exercised attacker and trusted computing base. Physical isolation,
production safety, regulatory compliance and real human effectiveness require
independent evidence outside this software suite.

Return to the [publication register](../README.md).
