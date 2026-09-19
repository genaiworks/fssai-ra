# TBC v13 — frontier-threat revision

`TBC_v13_Frontier_Threat_Revision.docx` is the current Word manuscript.
The preserved v11 and v12 sources remain unchanged. The reproducible
[`builder`](../../scripts/build_paper_revision.py) applies reviewed content from
[`revision-content.json`](revision-content.json). `implementation.json` binds
thirty-five prose anchors to executed tests and a source digest.

## Current revision

- Durable local workload stop, reauthorized artifact delivery and restrict-only monitor findings.
- Monitor snapshots expose at most 32 allowlisted event types, without protected text.
- Delivery evidence failure returns no bytes and preserves the delivery cursor.
- Measured host isolation: eight declared properties probed against the live host, with
  `not_measurable` never counted as success and production qualification refused without
  fresh, attributed, complete evidence.
- A qualified outbound transport that opens the socket: pinned literal address with no
  name-service lookup, verified hostname, public-key pinning, redirect refusal, framing
  checks and a wire-level byte ceiling, exercised against a real TLS handshake.
- Tool-server supply-chain controls: server-qualified names only, definition pinning
  against rug pulls, identity rotation withdrawal, description scanning before named
  approval, and untrusted call chains barred from privileged tools.
- At-most-once remote effects with reconciliation by idempotency key, cross-service
  attenuated grants, k-of-n witness attestation with fork detection, and an
  evidence-gated promotion decision that refuses this repository's own deployment.
- Measured monitor quality: no monitor -- oracle, blind or hostile -- changes a protected
  outcome, with adaptive evasion reported rather than minimised.
- A published preregistration for the institutional study, and an analysis that refuses
  conclusions from synthetic fixtures.
- Eleven research-paper references from 2025–2026, within the requested last three years.
- Concrete education workflow, comparison with related work, and explicit empirical limits.
- 1,375 passing regression tests, including 38 frontier-control cases; 31 executed
  capability contracts.

## Review and reproduce

See the [reviewer handoff](REVIEWER_GUIDE.md) for commands and submission limits.
Run `make all` from the repository root after installing development dependencies.
The Word file is byte-reproducible with `python scripts/build_paper_revision.py`
from `fssai-ra/`; `python scripts/check_paper_revision.py` checks the current file
against recorded execution evidence.

These results concern a local reference implementation. Measuring an assumption is
not supplying it: the isolation probe runs inside a cooperative process and the
transport peer is a loopback server, so neither establishes production isolation or
a qualified network peer, and the promotion gate refuses both as production evidence.
No live AI detector is measured, and no prevention of a real incident is demonstrated. The architecture register retains partial, deployment-dependent
and unimplemented requirements rather than claiming full production coverage.

The [follow-up security review](../../SECURITY_REVIEW.md) explains reproduced
defects, repairs, useful workflows and concrete acceptance criteria for remaining
deployment work. `make security-review` runs its focused regressions,
`make deployment-gaps` runs the seven suites covering the previously open gaps, and
`make qualify` measures this host and prints what it is actually allowed to be.
