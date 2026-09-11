# Submission checklist — UNU Macau AI Conference 2026

**Deadline:** 21 September 2026
**Form:** https://go.unu.edu/VFbpL
**Conference:** *AI × Education: AI for Learning, Learning for AI* · 25–26 November 2026 · Macau SAR, China
**Track:** shortlisted panelist; the extended abstract informs the panel and feeds the
[UNU–Springer Book Series on Artificial Intelligence and Sustainable Development](https://unu.edu/macau/announcement/book-series-aisd).

---

## Before you open the form

- [ ] `pytest` passes and `python scripts/generate_results.py --check` reports no drift.
      **Do this first.** Every figure in the abstract comes from that run, and the
      abstract is not submittable if the repository disagrees with it.
- [ ] Word count is in range — see [`README.md`](README.md).
- [ ] Tag the release so the abstract's `v1.0.0` reference resolves:
      `git tag -a v1.0.0 -m "v1.0.0" && git push --tags`
- [ ] Confirm the repository is public, or remove the URL from the abstract.
      An abstract citing a private repository is worse than one citing none.
- [ ] Read the form's own guidance before pasting. It may ask for a structure
      different from the section headings here; the content transfers, the
      headings may not.

## What goes in the form

| Field it probably asks for | Where it is |
|---|---|
| Title | First line of [`extended-abstract.md`](extended-abstract.md) |
| Panel / theme fit | Metadata block, and §5 |
| Keywords | Metadata block |
| Abstract body | §§1–5 |
| Author affiliation and bio | Not in this repository — prepare separately |
| Conflicts, funding, ethics | Not in this repository — prepare separately |

## Three things a reviewer will look for

**A contribution, not a survey.** §2 names it in one sentence: the control
contract, and three ways to check it. If a reviewer reads only §2, they should
know what is new.

**Evidence with denominators.** §4 reports containment *and* the false-denial
rate, and §4's final paragraph lists what is not evidenced. A submission with a
results section and no limits section reads as unreviewed.

**Fit to both halves of the theme.** §5 answers *AI for Learning* and *Learning
for AI* separately. Many submissions will answer one.

## After submitting

- [ ] Archive the exact submitted text: `cp paper/extended-abstract.md paper/archive/submitted-2026-09-21.md`
- [ ] Record the commit hash that produced the figures, in the archive file's header.
- [ ] Note the submission date in [`CHANGELOG.md`](../CHANGELOG.md).

## If accepted

The panel materials are already in the repository:

- [`docs/presentation/slides.html`](../docs/presentation/slides.html) — 16 slides plus 2 backup, with speaker notes on screen (`n`) and print-to-PDF
- [`docs/presentation/speaker-script.md`](../docs/presentation/speaker-script.md) — timings for 5, 7, and 10 minute versions, and prepared answers to the nine questions most likely to come
- [`docs/worksheet/`](../docs/worksheet/) — the takeaway: one capability through the seven fields, in a browser, emitting runnable configuration

For the proceedings chapter, the extended abstract expands along its own
section structure. The material that did not fit — the full evaluation tables,
the model checker's bounds, the conformance check list, and the reproduction
record — is already written in [`docs/ASSURANCE.md`](../docs/ASSURANCE.md) and
[`evaluation/results/RESULTS.md`](../evaluation/results/RESULTS.md).
