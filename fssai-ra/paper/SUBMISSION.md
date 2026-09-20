# Submission checklist — UNU Macau AI Conference 2026

**Deadline:** 21 September 2026

**Form:** https://go.unu.edu/VFbpL

**Conference:** *AI × Education: AI for Learning, Learning for AI* · 25–26 November 2026 · Macau SAR, China

**Proceedings:** selected contributions appear in the UNU–Springer Book Series on
Artificial Intelligence and Sustainable Development.

## Submit this version

Use **V27**: [`tbc-v27/form-fields/`](tbc-v27/form-fields/). Paste each numbered
file into the matching form field. The Microsoft Form requires four separate paste
fields and a separate reference field, and has no image field, so the twelve figures
do not travel with the paste; they live in the V27 document, which is the copy to
attach or send if anyone asks for one.

V27 is the only version to release. `tbc-v27/source/manuscript.md` is the single
source of the four submitted fields: `source/build_v27.py` renders it both as the
paste fields and as `Trust_by_Construction_V27_Extended_Abstract.docx`/`.pdf`, so
the two cannot drift. `source/appendix.md` is an implementation appendix carried by
the document only; the build never pastes it, and the verifier fails if any of its
paragraphs leaks into a paste field.

The illustrated document is nine pages with twelve figures. The four pasted
sections are 1,563 words, which is what "approximately 1,500 words" is being read
to mean; the invitation does not say whether captions, references or an appendix
count, so do not assume they are free.

> **Superseded:** [`tbc-v26/`](tbc-v26/) and [`tbc-v24/`](tbc-v24/) are previous
> releases, and [`form-ready-abstract.md`](form-ready-abstract.md) and
> [`extended-abstract.md`](extended-abstract.md) are the September cross-sector
> paper. All of them still validate, which makes them easy to paste by mistake. Do
> not submit them. There is also an earlier text-only V27 package; the illustrated
> V27 release supersedes it.

| Paste field | Required words | Form character cap | V27 words | Headroom (chars) |
|---|---:|---:|---:|---:|
| Introduction | 200–250 | 1,500 | 218 | 76 |
| Development Section 1 | 550–650 | 3,900 | 580 | 41 |
| Development Section 2 | 550–650 | 3,900 | 558 | 31 |
| Conclusion | 200–250 | 1,500 | 207 | 39 |

Headroom is small and characters bind before words. Measure any edit with
`check_submission.py` before keeping it; the character count there is the CRLF
count a browser actually submits, not the count the file stores.

Before opening the form:

- [ ] Byline is set: **Rachna Srivastava**, Enterprise Architect | AI Systems
  Researcher, *Independent work, in a personal capacity*, genaiworks@gmail.com.
  No employer is named anywhere, by intent — give the form the same details.
- [ ] Run `python scripts/check_submission.py paper/tbc-v27/Trust_by_Construction_V27_Form_Fields.md`; every field must report `valid: true`.
- [ ] Run `python paper/tbc-v27/source/verify_v27.py --repo .`; it must print `"status": "PASS"`. It re-runs the kernel rather than quoting it, so a prose number that has drifted from the code fails the release.
- [ ] Run `pytest` and `python scripts/generate_results.py --check`.
- [ ] Paste references into the separate reference field using the supplied style.
- [ ] Re-read the live form in case UNU changes a requirement after this release.

## Before the chapter is typeset

Reference [6] cites repository snapshot `9bb35a1`. The repository is public and
the snapshot tree and all three cited paths resolve over an unauthenticated
request, so a reviewer can open it today. But that commit is reachable only from
the branch `integrate/third-audit-hardening`: it is not on `main` and carries no
tag. Delete or prune that branch and the commit eventually becomes unreachable
and the citation rots.

- [ ] Tag the commit and push the tag, so the citation is anchored to a ref that
  is not a moving branch:
  `git tag -a paper-v27 9bb35a1 -m "Snapshot cited by the V27 extended abstract" && git push origin paper-v27`
- [ ] Confirm the tagged tree resolves in a signed-out browser.

## Reviewer test

The submission should remain clear if a reviewer reads only four elements:

1. **Problem:** an agent must not turn its own proposal into authority, and the
   safety case must not depend on the model being aligned. The harder half is
   composition: permitted steps combine into an outcome no one allowed, and no
   single agent misbehaves.
2. **Contribution:** ten patterns stated as executable refusals, a composition
   contract that holds task-wide authority, budget and revocation across
   delegated work, and an offline evidence kit that runs without model weights
   or a GPU.
3. **Evidence:** 55,440 bounded configurations with no violation across six
   synthetic packs; 0, 2 and 10 of 10 hostile delegation chains contained under
   unguarded, per-hop and whole-chain checking; nine control ablations that each
   restore their violation; a stateful harness that caught a release after
   consent withdrawal which step-testing passed; a second domain that exposed an
   ignored approval role; and a declared oversight simulation.
4. **Boundary:** fixture results on authored synthetic packs are neither
   certification nor evidence of educational benefit, latency or cost; the
   distributed bound is specified, not evaluated; and **no reviewer was
   observed**, so the oversight curve is a declared parameter throughout.

## If the form enforces a hard 1,500 words

The four V27 fields already sit inside the form's own word bands, so the form as
written will accept them. A hard 1,500-word total would bind about 63 words
tighter than the current 1,563.

Cut in this order, stopping as soon as it fits:

1. **Section 2's information-composition paragraph** — down to its rule
   ("outputs inherit restrictions from all exposed context") plus the
   over-restriction trade. The composition supplement carries the method.
2. **Section 2's spawning paragraph** — down to the attenuation rule and
   per-agent identity, dropping the replanning and task-graph sentences.
3. **Section 3's third finding** — the second-domain defect — to one sentence.

Never cut the falsifiable design hypothesis in section 2, the first and fourth
findings in section 3, or the conditionality paragraph that begins "Security
stays conditional". The hypothesis is what makes this a claim rather than a
description; the first finding is the result the panel slot is for; and the
conditionality paragraph is what earns a reviewer's trust. A paper that applies
a diagnostic to everyone else and not to itself invites exactly one question, and
it should arrive already answered.

The submission addresses both halves of the theme. *AI for Learning* is the grade
correction workflow with governed action and redress. *Learning for AI* is the
offline lab in which learners inspect a forged approval, poisoned memory and a
colluding agent chain, then observe which boundary refuses each action.

## After submitting

- [ ] Archive the exact pasted fields and references under `paper/archive/`.
- [ ] Record the release tag, commit hash, and submission date in that archive.
- [ ] Preserve the generated JSON results cited by the text.

## If accepted

- Present from [`docs/presentation/slides.html`](../docs/presentation/slides.html)
  with [its script](../docs/presentation/speaker-script.md). Press `⌘P` for a PDF
  to carry as the podium backup. The deck predates V27's pattern framing — 
  reconcile it against `tbc-v27/source/manuscript.md` before presenting.
- `docs/trust-by-construction-final.pptx` is a **superseded v1.0.0-era deck**. It
  predates the oversight ceiling, the second domain, and the adversary corpus, so
  it cannot make the argument this submission is on the panel to make. Do not
  present from it.
- Rehearse the live synthetic demo and carry a recording.
- Use `docs/worksheet/` as the audience takeaway and extension entry point.
- For the Springer chapter, expand with reviewer, fairness, accessibility, cost,
  energy, and independent pilot evidence, and run the distributed evaluation the
  abstract names as the next step.
