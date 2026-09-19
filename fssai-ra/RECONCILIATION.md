# Paper and implementation reconciliation

The original TBC v11 is preserved in `paper/tbc-v11/`. The v12 engineering revision is preserved in `paper/tbc-v12/`. The current revision is `paper/tbc-v13/`, produced from the v12 source by `scripts/build_paper_revision.py` so that every prose change is reviewable as code, with its own claim manifest. Earlier revisions are never edited in place.

## Closed gaps

- Versioned strict ingress is connected to the actual SDK dispatch boundary.
- Persistent source quarantine prevents subsequent use of tracked source-derived memory, proposals and releases and survives reopening and fresh task creation.
- Eight-component model identity, frozen tool-manifest comparison and destination authorization exist as tested integration contracts.
- Seven-field capability contracts are bound to executed tests, with failed/skipped tests treated as unverified and source drift detected.
- The 109 architecture control IDs remain visible with source pages, related implementation files and explicit scope.
- Revocable delivery of approved bytes is reauthorized at every chunk boundary, and a durable workload stop and restrict-only AI-monitor interface are executed contracts.
- CI and `make all` check contract execution, v11 provenance, revised-paper bindings and fresh reproduction of the existing results.

## Paper changes

The revised paper describes the implemented SDK rather than calling it only a future build phase. It adds source quarantine, complete model configuration identity, strict integration contracts, executed-test evidence, a regression count with its own denominator, threats to validity and deployment qualifications. Captions distinguish an integration roadmap from tested implementation. Original experimental numbers remain unchanged.

The full synthetic regression run contains 1,117 passing cases. Ten capability contracts are executed against named tests; their cases are a subset of the full suite, not additional independent experiments. Existing generated results reproduce 126 reported quantities. The original Word source is unchanged.

## Open work

The architecture is not fully implemented or operationally qualified. The catalogue uses conservative whole-control statuses: 2 implemented locally, 88 partially covered, 8 requiring deployment evidence and 11 explicitly unimplemented. A partially covered family can contain substantial existing code; its status means the complete source requirement has not been established. These are traceability categories, not security scores.

Generic browser and external tool transports, full SBOM/dependency impact analysis, canary promotion, policy differential simulation, production training/promotion lifecycle and generic remote uncertain-outcome reconciliation remain software work. Host isolation, workload federation, independent witnesses, external kill paths, credential rotation and hardware-backed custody require a chosen deployment and target-specific evidence. No infrastructure was deployed or repository pushed.

The earlier milestone plan is retained as a roadmap. This revision completes the explicitly listed engineering changes; it does not claim all M0–M8 architecture ambitions or all 657 pages are implemented.

## v13 revision: frontier threat controls

Three controls were added and bound to executed contracts.

- `workload_stop` and `stop_without_evidence`: a durable operator stop that revokes every agent, quarantines every task and advances every epoch in one transaction, commits before the evidence write is attempted, survives service restart, and requires a fresh identity to resume. It stops declared authority, not operating-system processes.
- `revocable_delivery`: approved artifact bytes are delivered against a binding re-resolved at every chunk boundary, so revocation, contraction, expiry, an emergency stop or a source quarantine denies the remainder. Committed bytes are not recalled.
- `restricted_monitor`: an AI monitor receives task metadata and an evidence head, never protected text, and submits a fixed-vocabulary finding that can only contract authority. A clear verdict changes nothing. Forged, stale, replayed, wrong-role and field-injecting findings are rejected.

`audit/incident-map.json` assigns each reported stage of the public July 2026 agent-intrusion disclosure to a mediated control, a deployment requirement, or a platform property outside this architecture. `tests/test_incident_map.py` requires every mediated stage to name a test that exists, forbids an out-of-scope stage from implying local evidence, rejects prevention wording, and fails if no residual risk remains in the map. Five of the fourteen stages are not mediated locally: sandbox escape and pod metadata access are out of scope; key custody, network confinement and transport security are deployment work.

The paper claims no prevention of any real incident, and the frontier-control tests are deterministic local scenarios rather than reproductions of frontier-model propensities.
