# TBC v13 — frontier-threat revision

`TBC_v13_Frontier_Threat_Revision.docx` is the current Word manuscript. It is
built from the preserved v12 source by
[`../../scripts/build_paper_revision.py`](../../scripts/build_paper_revision.py),
so every prose change is reviewable as code and the file is byte-reproducible.
`implementation.json` binds twelve prose anchors to executed tests.

## What changed from v12

| Change | Where |
|---|---|
| Incident mechanics stated concretely and read as authority properties | Section 1 |
| Covert objectives, agentic misalignment and monitorability as design constraints | Section 1, new paragraph |
| Durable workload stop, reauthorized delivery, restrict-only AI monitoring | New Section 6 |
| Regression row updated; frontier-control row added | Table 1 |
| Non-replication, non-prevention and stop-scope caveats | Threats to validity |
| Five research and disclosure references | [21]–[25] |

Sections 6 and 7 of v12 are renumbered 7 and 8.

## How a reviewer checks it

```
python -m pytest                                  # 1,117 local cases
python scripts/verify_architecture.py             # ten executed capability contracts
python scripts/check_paper_revision.py            # prose anchors, test locators, recorded evidence
python -m pytest tests/test_incident_map.py       # the incident reading stays honest
python scripts/build_paper_revision.py            # rebuilds this file byte-for-byte
```

The manuscript claims no prevention of any real incident, and its added controls
are deterministic local scenarios rather than reproductions of frontier-model
behaviour. `../../docs/THREAT_MODEL_2026.md` states the residual risk.
