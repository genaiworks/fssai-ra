# Paper and implementation reconciliation

The original TBC v11 is preserved in `paper/tbc-v11/`. The revised engineering paper is in `paper/tbc-v12/`, with a separate claim manifest. The user's latest instruction authorized this revision; earlier code-only restrictions no longer apply.

## Closed gaps

- Versioned strict ingress is connected to the actual SDK dispatch boundary.
- Persistent source quarantine prevents subsequent use of tracked source-derived memory, proposals and releases and survives reopening and fresh task creation.
- Eight-component model identity, frozen tool-manifest comparison and destination authorization exist as tested integration contracts.
- Seven-field capability contracts are bound to executed tests, with failed/skipped tests treated as unverified and source drift detected.
- The 109 architecture control IDs remain visible with source pages, related implementation files and explicit scope.
- CI and `make all` check contract execution, v11 provenance, revised-paper bindings and fresh reproduction of the existing results.

## Paper changes

The revised paper describes the implemented SDK rather than calling it only a future build phase. It adds source quarantine, complete model configuration identity, strict integration contracts, executed-test evidence, a regression count with its own denominator, threats to validity and deployment qualifications. Captions distinguish an integration roadmap from tested implementation. Original experimental numbers remain unchanged.

The full synthetic regression run contains 1,069 passing cases. The six new capability contracts execute 14 cases (the destination test is parameterized); these cases are a subset of the full suite, not additional independent experiments. Existing generated results reproduce 126 reported quantities. The original Word source is unchanged.

## Open work

The architecture is not fully implemented or operationally qualified. The catalogue uses conservative whole-control statuses: 2 implemented locally, 88 partially covered, 8 requiring deployment evidence and 11 explicitly unimplemented. A partially covered family can contain substantial existing code; its status means the complete source requirement has not been established. These are traceability categories, not security scores.

Revocable streaming, generic browser and external tool transports, full SBOM/dependency impact analysis, canary promotion, policy differential simulation, production training/promotion lifecycle and generic remote uncertain-outcome reconciliation remain software work. Host isolation, workload federation, independent witnesses, external kill paths, credential rotation and hardware-backed custody require a chosen deployment and target-specific evidence. No infrastructure was deployed or repository pushed.

The earlier milestone plan is retained as a roadmap. This revision completes the explicitly listed engineering changes; it does not claim all M0–M8 architecture ambitions or all 657 pages are implemented.
