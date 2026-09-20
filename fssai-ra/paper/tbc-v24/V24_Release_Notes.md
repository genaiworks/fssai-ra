# V24 — the release

V24 is the one version to release. It supersedes V22 and, more importantly, it
supersedes `paper/form-ready-abstract.md`, which was a different paper.

## The gap this release closes

The UNU submission is not a document upload. It is a Microsoft Form with four
pasted text fields and a separate reference field, each with its own word range
and character cap. The file that fed those fields, `paper/form-ready-abstract.md`,
still validated — but it was the September cross-sector paper, "A Cross-Sector
Reference Architecture for Governed Agentic AI". It contained none of the work the
V15 to V24 line had done: no swarm contract, no P1 to P10 catalogue, no separation
of what is built from what is proposed.

So two different papers were both called "the submission", and the polished one was
not the one the form would have received.

V24 removes the fork. `source/manuscript.md` is the single source. Its headings are
the form's own field labels, so the form fields and the document are the same text:

- `source/build_v24.py` emits the four paste files in `form-fields/`, the combined
  `Trust_by_Construction_V24_Form_Fields.md`, and the document as DOCX and PDF;
- the form has no image field, so the paste drops the figure markers and captions;
  the four figures remain in the document;
- the build imports the limits from `scripts/check_submission.py` rather than
  restating them, and refuses to produce a release whose fields do not validate.

## What else changed from V22

| Objection | Change |
|---|---|
| The paper read as a security paper submitted to an education conference; the abstract never used the word student. | The opening is the institutional stake: agents reading student records, changing school systems, delegating to other agents. |
| Every number was green. An all-green result from an author-written suite is the least persuasive evidence there is. | Three findings now carry the results section: local correctness does not cover composition (an unguarded chain contained 0 of 10 delegation attacks, per-hop validation 2, whole-chain verification 10); a stateful harness caught a summary drafted while access was valid but released after consent was withdrawn, which single-step enumeration had passed; and the academic-records profile exposed a declared approval role the runtime silently ignored. |
| Section 3 asserted a check-then-act race without evidence. | That race is the second finding above: caught, fixed and ablated. |
| The field is labelled "Methodology, Core Argument and Case Context" but the text had no case. | A worked registrar case: the lease naming one record, the write refused until the instructor confirms, the receipt bound to that exact draft, and the queued write failing after mid-task revocation. |
| The field is labelled "Results, Analysis and Impact" but impact sat only in the conclusion. | An impact paragraph for institutions: what procurement can require, what a regulator can check, and why a model or vendor change does not rebuild the safety case. |
| The build depended on an untracked `tbc-v19/`, still rendered a figure the paper had dropped, and the paste-ready markdown had broken image links. | The page system is vendored as `source/page-system.docx`; the dead figure and its alt text are gone; links resolve. |

## Verification

`python source/verify_v24.py` — 32 checks, all passing, including:

- the DOCX rebuilds byte-for-byte from `source/`;
- all four form fields are within their word ranges and character caps, with
  43, 156, 59 and 51 characters of headroom respectively;
- the paste text carries no figure markers or captions, and every line of it
  appears in the single source;
- every citation resolves and every listed reference is cited;
- the quoted evidence is byte-identical to `evaluation/results/v1.0.0-domain-pack-matrix.json`,
  and the totals the manuscript quotes are recomputed from it;
- every BUILT row of Figure 4 names a test that exists in `tests/`;
- the released PDF matches its recorded page count.

Body text is 1,621 words across the four fields, against the form's 1,500 to 1,800.
The document runs to five pages, the last holding the closing section and the
references.

Tests executed and passing: `tests/test_tbc_sdk.py`, `tests/test_frontier_controls.py`,
`tests/test_conference_falsification.py`, `tests/test_delegation.py`,
`tests/test_generalization.py`, `tests/test_domain_packs.py` and
`tests/test_profiles_and_evaluation.py`. The three-arm delegation figures quoted
above were read from a live run, not from a document.

No new experiments were run for this release and no new performance claims were made.

## Before the form is opened

1. Add author affiliation and contact address. The byline carries a name and a
   professional role only, and these are not invented here.
2. Paste from `form-fields/`, not from `paper/form-ready-abstract.md`.
3. Re-read the live form in case UNU has changed a requirement.
