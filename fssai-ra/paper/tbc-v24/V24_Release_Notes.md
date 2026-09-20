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
  the six figures remain in the document;
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

`python source/verify_v24.py` — 38 checks, all passing, including:

- the DOCX rebuilds byte-for-byte from `source/`;
- all four form fields are within their word ranges and character caps, with
  8, 92, 25 and 51 characters of headroom respectively;
- the reference field fits 1,500 characters, the tightest cap the form applies
  anywhere, because the reference field's own cap is not published;
- the three-arm comparison in Figure 5 re-runs from the kernel and still reports
  0, 2 and 10 of 10, and each of the nine ablated controls still restores its harm;
- the paste text carries no figure markers or captions, and every line of it
  appears in the single source;
- every citation resolves and every listed reference is cited;
- the quoted evidence is byte-identical to `evaluation/results/v1.0.0-domain-pack-matrix.json`,
  and the totals the manuscript quotes are recomputed from it;
- every BUILT row of Figure 4 names a test that exists in `tests/`;
- the released PDF matches its recorded page count.

Body text is 1,637 words across the four fields, against the form's 1,500 to 1,800.
The document runs to five pages and carries six figures.

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

## Second pass, 19 September 2026

The first V24 release passed every check it had. The checks did not cover whether
a reviewer could *see* the argument, and two things were invisible.

The three-arm delegation comparison was the paper's strongest evidence and it was
a sentence. It is now **Figure 5**, a live run of the kernel drawn as a matrix:
ten named risk classes, three architectures, the refusal code arm C returns for
each, and the benign chain completing in all three arms so the figure cannot be
read as a control that refuses everything. The numbers are not typed into the
build; `build_v24.py` imports `fssaira.delegation_eval`, runs the suite, writes
`source/delegation-comparison.json`, and refuses to build if the prose and the run
disagree. `verify_v24.py` re-runs it independently.

The worked registrar case was a dense paragraph. It is now **Figure 2**, seven
steps with what the assistant proposes on one side and what the gate decides on
the other, three of them refusals. It is the figure that makes the method legible
to a reader who is not a security engineer, which at an education conference is
most of the room.

Also in this pass:

| Gap | Change |
|---|---|
| The introduction never said what the contribution was; a reviewer had to infer it. | One sentence now names all three: ten patterns, a composition contract that survives agents spawning agents, and an offline evidence kit. |
| Six references, none covering agent identity or a public attack benchmark. | Added Chan et al. (2024) on visibility into AI agents, cited where per-agent identity is introduced, and AgentDojo (2024), cited in the evaluation plan. Both were checked against the arXiv API, not recalled. |
| "A majority of the risk classes pass straight through" named none of them. | The prose now names what arm B catches (a widened scope, an untrusted key) and what walks past it (confused deputies, bearer-chain reuse, unrooted chains, depth evasion). |
| Figure placement left a third of page 2 blank and pushed two references onto a sixth page. | Figure 3 now leads its section rather than trailing it, and the bibliography is set tighter. Five pages, six figures, no blank half-pages. |

Every character-cap trim above was taken out of redundancy, not out of a claim:
no statement of scope, limit or negative result was shortened away. The fields
ran to 8, 92, 25 and 51 characters of headroom. The introduction has almost none:
any further edit to it must be measured with `scripts/check_submission.py`, and
`build_v24.py` refuses to produce a release whose fields do not validate, so an
overrun cannot reach the form unnoticed.
