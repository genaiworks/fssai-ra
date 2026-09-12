# Submission checklist — UNU Macau AI Conference 2026

**Deadline:** 21 September 2026

**Form:** https://go.unu.edu/VFbpL

**Conference:** *AI × Education: AI for Learning, Learning for AI* · 25–26 November 2026 · Macau SAR, China

## Submit this version

Use [`form-ready-abstract.md`](form-ready-abstract.md), not the longer
proceedings-style [`extended-abstract.md`](extended-abstract.md). The Microsoft
Form requires four separate paste fields and a separate reference field.

| Paste field | Required words | Form character cap |
|---|---:|---:|
| Introduction | 200–250 | 1,500 |
| Development Section 1 | 550–650 | 3,900 |
| Development Section 2 | 550–650 | 3,900 |
| Conclusion | 200–250 | 1,500 |

Before opening the form:

- [ ] Add author name, affiliation, email, and professional role; these are not
  invented in the repository.
- [ ] Run `python scripts/check_submission.py`; every field must report `valid: true`.
- [ ] Run `pytest` and `python scripts/generate_results.py --check`.
- [ ] Confirm that release `v1.0.0` and its result files resolve in a signed-out browser.
- [ ] Paste references into the separate reference field using the supplied style.
- [ ] Re-read the live form in case UNU changes a requirement after this release.

## Reviewer test

The submission should remain clear if a reviewer reads only four elements:

1. **Problem:** an agent must not turn its own proposal into authority.
2. **Contribution:** a seven-field executable control contract.
3. **Evidence:** comparative attacks, utility, ablations, bounded model checking,
   conformance, a narrowly stated replay race, a queue-pressure trial of review
   capacity, and a second domain carrying its own evidence.
4. **Boundary:** fixture results are neither certification nor proof of educational
   benefit, hardware isolation, or distributed linearizability — and **no reviewer
   was observed**, so the oversight curve is a declared parameter throughout.

## If the form enforces a hard 1,500 words

`form-ready-abstract.md` is written to the form's four capped fields and already
validates. `extended-abstract.md` is the proceedings-style version and runs to
about 1,580 words of body text.

If a hard cap must be met there, cut **§4, "Does the method travel?"** — the
second-domain section — down to two sentences inside §5, keeping the figures and
the defect it exposed. That is the right cut because the generalization claim is
supported by the repository whether or not the abstract argues it, while §3
(oversight) is the contribution that earns the panel slot and §7 (limits) is the
section that earns a reviewer's trust. Never cut §3 or §7.

The submission addresses both halves of the theme. *AI for Learning* is the
student-support workflow with governed action and redress. *Learning for AI* is
the reusable lab in which learners remove controls, observe harms, inspect
evidence, and restore service.

## After submitting

- [ ] Archive the exact pasted fields and references under `paper/archive/`.
- [ ] Record the release tag, commit hash, and submission date in that archive.
- [ ] Preserve the generated JSON results cited by the text.

## If accepted

- Present from [`docs/presentation/slides.html`](../docs/presentation/slides.html)
  with [its script](../docs/presentation/speaker-script.md). Press `⌘P` for a PDF
  to carry as the podium backup.
- `docs/trust-by-construction-final.pptx` is a **superseded v1.0.0-era deck**. It
  predates the oversight ceiling, the second domain, and the adversary corpus, so
  it cannot make the argument this submission is on the panel to make. Do not
  present from it.
- Rehearse the live synthetic demo and carry a recording.
- Use `docs/worksheet/` as the audience takeaway and extension entry point.
- Expand the longer abstract with reviewer, fairness, accessibility, cost, energy,
  and independent pilot evidence for the proceedings chapter.
