# TBC v13 reviewer handoff

Use `TBC_v13_Frontier_Threat_Revision.docx` as the current manuscript. Earlier
versions remain preserved. The paper's contribution is a compositional local
reference for institutional authority, with executable failure evidence; it is
not a solution to model alignment or a production security certification.

## Reproduce

After installing the repository's development dependencies, run from its root:

```sh
make all
```

For a focused review, run from `fssai-ra/`:

```sh
.venv/bin/python -m pytest tests/test_frontier_controls.py tests/test_paper_revision_build.py
.venv/bin/python scripts/verify_architecture.py
.venv/bin/python scripts/check_paper_revision.py
.venv/bin/python scripts/generate_results.py --check
```

Inspect the effect register, returned byte sequences, delivery cursor, revoked
identities and evidence chain in the tests. A model's claim of success is not the
outcome oracle. The 35 frontier-control cases are deterministic local scenarios;
they are part of the full regression suite and must not be added to its count.

## Research and scope

The bibliography contains eleven research papers published in 2025–2026, within
the requested trailing three-year window. It includes 2026 sabotage evaluation
and 2025 work on technical safety, prompt injection, scheming, monitorability,
reward hacking and safer non-agentic designs. All are labelled research preprints.
Leader essays and incident disclosures remain in supplementary repository
context rather than masquerading as research papers.

The monitor can reduce availability through false alarms and can miss intent.
It cannot approve business actions. The workload stop revokes local authority;
it is not an OS process-kill mechanism. Chunk delivery reauthorizes preapproved
bytes; it is not live token streaming. Previously released bytes cannot be recalled.

## Submission status

This is a reviewed manuscript and reproducible artifact handoff. It has not been
uploaded, submitted, deployed or pushed. Conference-specific page/template,
anonymization and submission-field requirements must be applied against the
actual submission instructions. The existing form-ready abstract is a separate
historical artifact; do not submit it as if it automatically tracks this revision.

## Follow-up security review

Run the focused regression suite from `fssai-ra/`:

```sh
.venv/bin/python -m pytest tests/test_frontier_controls.py tests/test_integration_contract.py
```

The 58 cases include 27 added cases. Against the previous implementation at
`3f65aae`, 14 cases fail; against the revised implementation, all pass. The
regressions address monitor history starvation, malformed monitor fields and
ambiguous URL paths. These results measure local boundary behavior, not model
attack success rates. All cases are included in the full regression total.

To inspect the change, compare the current commit against `3f65aae` in
`src/fssaira/tbc/runtime.py`, `src/fssaira/integration/network.py` and their tests.
The reviewed manuscript remains v13; preserved v11/v12 sources are unchanged.
