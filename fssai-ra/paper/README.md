# Paper

| File | What it is |
|---|---|
| [`trust-by-construction.md`](trust-by-construction.md) | **Expanded foundation paper.** Audited threat model, GenAI integration contract, distributed semantics, evidence limits, and deployment gates. HTML/PDF are built with `scripts/build_paper.py`. |
| [`foundation-claims.json`](foundation-claims.json) | Scoped claims and implementation/evidence gaps from the full-paper audit. |
| [`extended-abstract.md`](extended-abstract.md) | **The proceedings version.** The full argument for the UNU Macau AI Conference 2026 and its UNU–Springer proceedings. |
| [`form-ready-abstract.md`](form-ready-abstract.md) | **What goes in the form.** Written to the submission form's four capped fields, validated by `scripts/check_submission.py`, and plain ASCII so it pastes without mojibake. |
| [`composition-supplement.md`](composition-supplement.md) | Delegated authority and assisted review in full — the two contributions the abstract states in compressed form. |
| [`empirical-supplement.md`](empirical-supplement.md) | Recovery and replay identity: process races and abrupt-exit recovery after the `v1.0.0` baseline. |
| [`SUBMISSION.md`](SUBMISSION.md) | Checklist, deadline, what to paste where, and the order to cut in if a hard word cap applies. |
| [`archive/`](archive/) | Superseded versions, kept for provenance. Do not cite these. |

Both supplements are held to the same standard as the abstract: their figures are
generated, and `tests/test_paper_alignment.py` fails the build if the prose and a
fresh run disagree. A supplement is where detail goes, not where checking stops.

## The alignment guarantee

Every figure the abstract quotes is produced by
[`scripts/generate_results.py`](../scripts/generate_results.py) and checked
against the prose by [`tests/test_paper_alignment.py`](../tests/test_paper_alignment.py).
The same applies to the conference deck in [`docs/presentation/`](../docs/presentation/).

If a number in the paper stops matching a fresh run, the build fails. Alignment
is a test here, not a promise — which matters, because this project has already
had one drift incident: release `v0.5.0` reported eight scenarios and forty-two
tests, and a sentence quoting those figures would have survived unnoticed into
the proceedings.

```bash
python scripts/generate_results.py          # regenerate every figure
python scripts/generate_results.py --check  # confirm nothing has drifted
pytest tests/test_paper_alignment.py        # confirm the prose still matches
```

## Word count

The call asks for approximately 1,500 words. The body — every numbered section,
excluding the metadata header and the references — is checked to stay between
1,300 and **1,900** by `test_the_word_count_fits_the_submission_guidance`.

The upper bound was 1,650 while the abstract argued three contributions. It was
raised deliberately when three more were added — the contract's own coverage,
assisted review, and delegated authority — and the reason is recorded in that
test's docstring rather than here, so it travels with the assertion. The existing
sections were compressed to pay for most of the increase.

`form-ready-abstract.md` is the artifact written to the form's caps and is
unaffected. If a hard cap must be met on the proceedings version too,
[`SUBMISSION.md`](SUBMISSION.md) names the cut order; the limits section is never
what gets cut.

```bash
python scripts/check_submission.py            # the form fields still fit
pytest tests/test_paper_alignment.py -k word  # the body is inside the bound
```
