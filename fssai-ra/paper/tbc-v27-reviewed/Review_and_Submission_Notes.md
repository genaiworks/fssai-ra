# V27 review and submission notes

Reviewed 20 September 2026. Recommendation: submit the revised four-section abstract as an architecture and synthetic-evaluation contribution. Its main argument is clear and relevant to the conference. The revised body is 1,558 words. The illustrated Word document retains all twelve figures and the implementation appendix. Use that longer document only if the submission permits figures and supporting material; the paste fields contain the abstract alone, with references in a separate field.

The original Desktop repository and V27 release have not been modified. The reviewed files are separate editorial deliverables, not a new code release.

## Changes that matter

- Corrected the budget dimensions to match `tbc/contracts.py`: calls, context bytes, memory bytes, traffic bytes, compute units and cost. The previous prose named record counts and consequential-effect counts instead.
- Replaced “known operators” with the actual trust assumption, trusted operators. Clarified that approval binds the exact draft.
- Qualified the relationship between passing regression tests and general security claims. Bounded synthetic success does not establish correctness for every input, distributed enforcement or operational safety.
- Explained that the academic-records approval-role defect was fixed and is covered by both refusal and valid-approval tests.
- Defined the oversight simulation's attention parameter as the number of initially attentive cases. Explicitly stated that outcomes after referral to manual review were not evaluated.
- Replaced universal-sounding traceability and utility wording with claims the evidence supports. Model or vendor substitution requires fresh adapter checks.
- Corrected the cross-sector caption and appendix: adapting the workflow also requires domain policies, approval roles and qualified adapters.
- Removed the appendix's V27 verifier command because that file is absent from the cited public commit. Added the development extra to the installation command so the test dependencies are installed.
- Preserved the title, author block, main contribution, results, education focus, twelve figures and overall page design. The source comparison is recorded in `editorial-changes.json`.

## Submission counts

Counts exclude the title, author block, headings, captions, references and appendix. Characters include CRLF-normalized paragraph breaks under the repository's saved checker.

| Field | Words | Saved word range | Characters | Saved cap |
|---|---:|---:|---:|---:|
| Introduction | 223 | 200–250 | 1,453 | 1,500 |
| Development 1 | 575 | 550–650 | 3,829 | 3,900 |
| Development 2 | 553 | 550–650 | 3,872 | 3,900 |
| Conclusion | 207 | 200–250 | 1,470 | 1,500 |
| Body total | 1,558 | Approximately 1,500 | — | — |

All four fields pass. Development 2 has 28 characters of headroom under the saved rule. Paste only the field content, without its heading or additional formatting. No live submission form URL was supplied during this review, so these are saved requirements, not a fresh certification of the portal. The references field has no independently verified cap. The deadline in the invitation is 21 September 2026; its cutoff timezone is unspecified.

## Verification completed

The original V27 verifier passed against local commit `28f3a09d978922338a1c091103a0af11e06ce607`. Its source, tests and evaluation results have no Git diff against cited snapshot `9bb35a190353a5e4f9bfce7d5b987667c5874a49`.

Fresh checks reproduced 55,440 bounded configurations with zero violations, the delegation comparison of 0/10, 2/10 and 10/10 contained hostile chains, all nine control ablations, the oversight sweep, and benign completion in the comparison arms. The 180/180 hostile and 58/58 benign six-domain totals were checked against the stored result artifact; they were not independently rerun as a six-domain attack study in this review.

Targeted execution passed 18 test cases: seven named SDK regressions including parameterized authority axes, the stateful falsification regression, and two academic-record approval-role regressions. Two initial test invocations failed to find relative profile paths from the task directory; rerunning them from the repository root passed. This was a working-directory issue, not a code defect. The complete 1,445-test suite reported in the original release notes was not rerun in this review.

The revised Word text and paste fields match paragraph by paragraph; all twelve embedded figures are retained. All nine rendered pages were visually inspected. No clipped text, overlapping figures, missing captions or broken references were identified.

## Sources and remaining publication details

The public [UNU conference announcement](https://unu.edu/macau/news/unu-macau-ai-conference-2026-become-sponsor) confirms the education theme and 25–26 November dates. The [UNU–Springer series page](https://unu.edu/macau/announcement/book-series-aisd) supports the governance and sustainable-development positioning; it does not establish acceptance of this contribution.

The six research-paper references were checked against their arXiv records. UNESCO's [framework page](https://www.unesco.org/en/articles/ai-competency-framework-students) supports reference [8]. Public unauthenticated retrieval succeeded for the cited snapshot's [domain results](https://raw.githubusercontent.com/genaiworks/fssai-ra/9bb35a1/fssai-ra/evaluation/results/v1.0.0-domain-pack-matrix.json), [SDK tests](https://raw.githubusercontent.com/genaiworks/fssai-ra/9bb35a1/fssai-ra/tests/test_tbc_sdk.py) and [approval-role tests](https://raw.githubusercontent.com/genaiworks/fssai-ra/9bb35a1/fssai-ra/tests/test_generalization.py).

Local Git refs show the cited snapshot is retained by `integrate/third-audit-hardening` and its remote-tracking branch, with no containing tag. A durable tagged or archived release would strengthen the proceedings citation. No tag was created or pushed. No submission or message to the organizers was sent.
