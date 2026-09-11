# Changelog

## 0.5.0 2026-09-10

- Add an application-neutral FastAPI control plane and generated OpenAPI contract.
- Add Redis-backed resources, proposals, approvals, replay protection, pending
  outcomes, and hash-chained evidence using optimistic transactions.
- Add an idempotent Kafka event publisher and inward-only import gateway with
  HMAC verification, quarantine, sanitization, and no read-back route.
- Add a checkpointed PySpark Structured Streaming job that preserves Kafka lineage
  while appending normalized events to Apache Iceberg v2 tables.
- Add a Docker Compose reference stack, random local-secret bootstrapper, full-stack
  smoke test, operations runbook, and physical data-diode integration guide.
- Expand the deterministic suite to 42 tests and publish the v0.5.0 evaluation result.

## 0.4.0 2026-09-10

- Add validated YAML application profiles and an extensible profile template.
- Enforce profile-specific operation and state-transition allowlists.
- Add `fssaira` CLI commands for profile/contract validation and adversarial evaluation.
- Add a machine-readable eight-scenario evaluation report.
- Add outcome-evidence interruption signaling and idempotent reconciliation through
  a teaching-profile pending-outcome store.
- Expand the suite to 32 tests.

## 0.3.0 2026-09-10

- Authenticated every approval field with a trusted-key teaching-profile HMAC.
- Rejected unknown approval keys, modified approvals, and unallowlisted operations.
- Made successful retries return the stored receipt without duplicate evidence.
- Expanded the deterministic suite from 18 to 23 tests.

## 0.2.0 2026-09-10

- Added exact-action approval bound to target, arguments, evidence, and case version.
- Added expiry, stale-state, separation-of-duties, and idempotent-retry tests.
- Added intent and outcome evidence to the synthetic case transition.
- Clarified teaching-profile assurance and residual risks.
- Added extension guidance and machine-readable citation metadata.
- Added continuous integration across Python 3.10 through 3.13.

## 0.1.0 2026-09-09

- Added the five-domain teaching implementation, control-contract YAML, synthetic
  student-support example, adversarial specimens, and initial ablations.
