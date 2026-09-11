# Changelog

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
