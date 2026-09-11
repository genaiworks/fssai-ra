# Paper

| File | What it is |
|---|---|
| [`extended-abstract.md`](extended-abstract.md) | **The submission.** ~1,500 words for the UNU Macau AI Conference 2026 and its UNU–Springer proceedings. |
| [`SUBMISSION.md`](SUBMISSION.md) | Checklist, deadline, and what to paste where. |
| [`archive/`](archive/) | Superseded versions, kept for provenance. Do not cite these. |

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

The call asks for approximately 1,500 words. The body (sections 1–5, excluding
the metadata header and the closing note) is checked to stay between 1,300 and
1,600 by `test_the_word_count_fits_the_submission_guidance`.

```bash
python - <<'PY'
import re, pathlib
text = pathlib.Path("paper/extended-abstract.md").read_text()
body = text[text.index("## 1."):text.index("---\n\n*Full paper")]
print(len(re.findall(r"[A-Za-z0-9'’\-]+", body)), "words")
PY
```
