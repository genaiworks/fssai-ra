# Community release and readiness

This package turns the three AIE proposals into reusable engineering material. It is prepared locally for review and sharing; no public release or conference submission was made in this work.

## Included

- **Three field-ready AIE proposals:** deployment approval, integration failures that passed the original tests, and a disclosure workshop. The separate AI Con proposal now points to the same take-home artifacts.
- **Workshop kit:** three editable TODOs, two recovery checkpoints, a reference solution, seven output checks, participant guide, answer explanations, and a 90-minute instructor plan.
- **Reusable evaluation code:** a standard-library effect oracle that catches a write followed by a refusal, plus a cached-receipt boundary example with an intentionally unsafe positive control.
- **Adoption worksheet:** caller identity, authority, approval, replay, reads, handoffs, release, independent observation, and legitimate-work checks.
- **Measured evidence:** a 36-case benign grid and descriptive read-call timings with environment and scope recorded in JSON.
- **Speaker materials:** two 20-minute stage plans, a two-minute recording script, reviewer questions, and an explicit claim-to-evidence map.
- **Offline reviewer capture:** four actual terminal runs, full readable transcript, and a self-contained HTML player. No model service is required to view or rerun them.
- **Release tooling:** pinned rehearsal constraints, source archive generation, SHA-256 manifest verification, and hosted CI on Python 3.10 and 3.14. The [security-systems workflow](https://github.com/genaiworks/fssai-ra/actions/workflows/security-systems.yml) runs lint, the full suite, the community checks and the rehearsal capture on every change; its first eight completed runs (to September 25, 2026) all passed.

## Validation

A source archive was extracted into a separate directory, installed with `--no-cache-dir` in a fresh virtual environment using the pinned constraints, and tested on Python 3.14.6 / macOS ARM64.

- **233 tests passed in 148.28 seconds**, including the original evidence regeneration checks and new community example/workshop regressions.
- **Ruff passed** across source, tests, examples, workshop, scripts, and benchmarks.
- **Workshop:** the intentionally incomplete starter releases the synthetic secret and passes 2/7; the solution passes 7/7 while preserving both legitimate releases.
- **Community demonstrations:** replay-boundary and effect-oracle experiments passed in the clean environment.
- **Benign grid:** 36/36 authored cases completed, including reviewed deployment replay without a repeated effect.
- **Timings:** 1,000 warm sequential reads per delegation depth; median 10.83 / 23.63 / 47.38 microseconds at depths 0 / 1 / 3 in the recorded local run. These include guard logging and are descriptive measurements, not production performance guarantees.
- **Offline viewer:** browser-checked selection and replay of the captured output, with a readable transcript fallback.
- **Archive:** file hashes verified after extraction; modification detection was also exercised.

Hosted Linux CI now runs on every change (above). No live model, Windows run, external security audit, or participant workshop pilot was performed. The clean install required network access for dependencies; the examples run locally after installation.

## What is still external work

1. **Public artifact access:** the source is public at `github.com/genaiworks/fssai-ra/tree/main/security_systems`, and anonymous access was checked on September 24, 2026. `scripts/publish_standalone.sh` publishes it, with history, as its own repository once an empty one is created.
2. **Speaker confirmation and recording:** confirm the biography and record `docs/RECORDING_SCRIPT.md` in the speaker's own voice; `scripts/record_demo.sh` drives the terminal. The automated terminal capture is supporting material, not a substitute for a human delivery sample.
3. **Participant pilot:** run the workshop with fresh participants using `workshop/PILOT.md`, measure checkpoint times and setup failures, and adjust the 90-minute plan. Machine execution cannot validate learner pacing.
4. **Independent empirical validation:** invite held-out attacks and test a real authenticated deployment before making broader security or research-paper claims. The current proposals explicitly stay within the reference evidence.

## Judge's reassessment

The deployment talk now has a focused live example and a reusable integration worksheet. The evaluation talk leads with a concrete failure investigation and ships a small oracle attendees can adapt. The workshop has an actual teaching kit and functioning recovery checkpoints. These close the local content and artifact gaps identified in the review.

They do not guarantee acceptance or “best in conference.” That depends on reviewer fit, competing submissions, delivery, and audience experience. The strongest defensible promise is that attendees can rerun the failures, inspect the repairs, and apply the evaluation method to one of their own tools.

## Generalization and submission revision — September 22, 2026

The current package adds `trustkernel.runtime.GuardedDispatcher`, the importable `trustkernel.evaluation` observer, and a domain-independent adapter example. Tools bind effective defaults before approval, reject duplicate names and invalid resource parameters, and protect cached receipts from caller mutation. The submission text now contains only the six requested fields per proposal and a short package introduction.

Verification: the expanded suite passed **248 tests**; after adding argument-map support for parameters named `resource` or `tool`, the targeted runtime and generalization run passed **16 tests**, including the additional collision regression. Lint and the three-adapter demo passed. The earlier fresh-install 233-test result above remains the record for the previous release, not the current suite count. See `GENERALIZED_RUNTIME.md` for compatibility changes and supported scope.
