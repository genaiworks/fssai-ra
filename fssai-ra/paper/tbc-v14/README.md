# TBC v14 developer security revision

Current paper: `TBC_v14_Developer_Security_Revision.docx`.
V13 is preserved byte-for-byte as the source for this revision. The builder is
`../../scripts/build_paper_v14.py`; reviewed prose and twelve recent research
references are in `revision-content.json`. `implementation.json` binds the
manuscript hash and explicit claims to tests and source-bound execution evidence.

Start with [the developer guide](../../DEVELOPER_GUIDE.md) and
[security review](../../SECURITY_REVIEW.md). `make developer-demo` exercises
verified artifact delivery and remote settlement using local synthetic fixtures.
`make all` runs the release checks. No external model or production peer is
required. The paper describes 1,445 regression tests and 37 executed capability
contracts; regression counts are not attack success rates.

V14 adds exact-content verification before returning artifact bytes, isolated
concurrent response buffers, strict HTTP framing, conservative provider response
validation and operation-bound idempotency checks. It adds developer examples and
integration obligations, and discusses 2026 Silent Egress research without
claiming to replicate that study or match its results.

It also closes a channel exact-byte release does not: the information an agent
carries in the destination, path, timing, size and count it chooses for an
authorised release. Canonicalising what the task contract can supply, charging
the remainder against a per-task bit budget and escalating to a named human when
it is spent reduces a measured sixteen-bit leak to 1.0 bit, and to 0.0 bits when
the release count is fixed with indistinguishable cover, while an ordinary
workflow still completes. `make covert-channels` reproduces the measurement; the
cost is that 98.4% of adversarial tasks escalate, which the record reports.

The deployment remains a local reference. Host isolation, real peer qualification,
live-model accuracy, independent key custody and institutional outcomes still
require external evidence. No conference upload or remote push has been made.
