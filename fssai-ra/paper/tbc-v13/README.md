# TBC v13 — frontier-threat revision

`TBC_v13_Frontier_Threat_Revision.docx` is the current Word manuscript.
The preserved v11 and v12 sources remain unchanged. The reproducible
[`builder`](../../scripts/build_paper_revision.py) applies reviewed content from
[`revision-content.json`](revision-content.json). `implementation.json` binds
thirteen prose anchors to executed tests and a source digest.

## Current revision

- Durable local workload stop, reauthorized artifact delivery and restrict-only monitor findings.
- Monitor snapshots expose at most 32 allowlisted event types, without protected text.
- Delivery evidence failure returns no bytes and preserves the delivery cursor.
- Nine research-paper references from 2025–2026, within the requested last three years.
- Concrete education workflow, comparison with related work, and explicit empirical limits.
- 1,120 passing regression tests, including 18 frontier-control cases; ten executed capability contracts.

## Review and reproduce

See the [reviewer handoff](REVIEWER_GUIDE.md) for commands and submission limits.
Run `make all` from the repository root after installing development dependencies.
The Word file is byte-reproducible with `python scripts/build_paper_revision.py`
from `fssai-ra/`; `python scripts/check_paper_revision.py` checks the current file
against recorded execution evidence.

These results concern a local reference implementation. They do not measure a
live AI detector, establish process/network isolation, or demonstrate prevention
of a real incident. The architecture register retains partial, deployment-dependent
and unimplemented requirements rather than claiming full production coverage.
