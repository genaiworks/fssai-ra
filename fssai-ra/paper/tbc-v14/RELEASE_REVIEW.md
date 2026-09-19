# v14 release review

This review updates the manuscript presentation and its reproducibility path.
Figure 4 now shows the implemented authority boundaries, the restrict-only AI
monitor, artifact-integrity and settlement components, and external deployment
obligations. Figure 6 replaces a proposed evaluation diagram with results read
from the committed experiment JSON, including the sample denominators and
synthetic-evaluation limits. The plot separates the three-arm comparison from
the six-domain experiment. The manuscript keeps its six figures; see the length
note below, which supersedes the page claim made when that review was written.

The figure manifest binds source data and rendered assets by SHA-256. Both the
paper builder and the release checker verify those bindings. Preserved earlier
Word revisions are unchanged.

## Residual-choice channel, added after that review

A later revision adds one runtime capability and one experiment. Exact-byte
release escrow fixes the bytes that leave; it does not fix the destination,
path, timing, size or count an agent selects around them, and those choices
carry information. `fssaira.covert_channels` canonicalises the dimensions a task
contract can supply, charges what remains against a per-task bit budget, and
escalates to a named human when it is spent. The measurement in
`audit/covert-channels.json` drives an adversarial encoder that performs no
unauthorised operation over all 65,536 sixteen-bit secrets and counts distinct
observable traces: 16.0 bits with no control, 1.0 canonicalised, 0.0 sealed,
with an ordinary two-release workflow completing under every policy and 98.4%
of adversarial tasks escalating. The manuscript gains two paragraphs and one
evidence-table row.

## Length

The body text is now 5,793 words, 626 more than preserved v13; the
residual-channel section accounts for 411 of those. **No page count was
measured.** No Word or LibreOffice renderer is available in this environment, and
the `docProps/app.xml` page field is inherited from the source rather than
recomputed, so any statement that the manuscript is still ten pages would be a
guess. Open it in Word and check the page count against the organizer's limit
before uploading. If it runs long, the residual-channel section is the newest
and most separable material: removing the `residual_channel` and
`residual_channel_measurement` entries from `revision-content.json`, the matching
insertion in `scripts/build_paper_v14.py`, and their claim anchors from
`implementation.json` reverts it cleanly and `make all` will still pass.

## Remaining release decisions

The intended event is UNU Macau AI Conference 2026. Checked against the
organizer's public material on 19 September 2026:

- **Confirmed.** The conference is 25-26 November 2026 in Macau SAR, China, under
  the theme "AI x Education: AI for Learning, Learning for AI"
  (https://unu.edu/macau/aiconf2026).
- **Not published.** The official conference page states no paper submission
  deadline, page or word limit, template, or anonymity policy. The material
  reachable from it is a call for panelists, not a call for papers. Enquiries go
  to AIConference@unu.edu.

So four of the five things a submission needs are still unverified, and this
repository cannot settle them. Before uploading, confirm with the organizers:
the submission deadline and channel, the page or word limit, the required
template, and whether review is anonymous. The current manuscript names its
author, which a blind-review track would require removing -- that is a change to
`revision-content.json` and a rebuild, not a hand edit of the Word file.

The reference implementation is not a production-qualified deployment. Host
isolation, independent key custody, real service peers, institutional studies
and live-model evaluation remain explicit obligations. Passing local tests does
not close those gaps. No upload, push or publication was performed by this review.

Official event information: https://unu.edu/macau
