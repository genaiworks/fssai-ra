# Specification profile: agent swarms

> **Documentation navigation:** [Documentation map](README.md) · [Core specification](SPECIFICATION.md) · [Master guide](MASTER_GUIDE.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Run the tests cited below in your own deployment, then assemble the evidence bundle in [`MASTER_GUIDE.md`](MASTER_GUIDE.md#113-evidence-bundle-required-before-go-live).

**Status:** draft 1.0 for public comment · **Extends:** [`SPECIFICATION.md`](SPECIFICATION.md)
· **Required when:** a deployment runs cooperating agents, external effect adapters, or
evidence witnesses outside one process.

This profile adds requirements to the core conformance classes. Each ID is the class
letter and number the requirement would take in the core, prefixed `SW-`. The key words
**MUST**, **MUST NOT**, **SHOULD** and **MAY** are used as in RFC 2119 and RFC 8174. A system
claiming this profile also claims the core classes it depends on. As in the core, evidence
does not transfer between deployments, and
[`tests/test_specification_swarm_profile.py`](../tests/test_specification_swarm_profile.py)
fails the build if a cited test stops existing.

## Trusted base

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| SW-T-6 | MUST | Measure the trusted base rather than assert it: source lines per trusted component, a software bill of materials, and a build measurement that deployment attestation pins. A changed measurement is a changed enforcer. | test: `tests/test_master_guide_measures.py::test_trusted_base_is_measured_and_a_minority_of_the_package` |

## Authority

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| SW-A-7 | MUST | Bind every proposal and approval to the policy version in force, and refuse execution under any other version. Change policy only through a named, reasoned, monotonic migration that contracts tasks the new policy no longer covers and sends held effects to re-review. | test: `tests/test_approval_policy_pinning.py::test_approval_under_old_policy_does_not_execute_under_new` |
| SW-A-8 | MUST | Commit every external effect in one linearizable step against the current epoch, carry an idempotency key the external system honours, and hold (never decide locally) when the authority store is unreachable. Qualify adapters against no-stale-effect, exactly-once and reconciled invariants under partition, loss, duplication, delay and clock skew. | test: `tests/test_revocation_chaos.py::test_fenced_commit_holds_every_invariant_and_each_ablation_breaks_one` |

## Governed disclosure

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| SW-D-14 | MUST | Where sector law defines release rules, encode them as a decision table in which every answer cites its legal or institutional basis, and refuse any disclosure path the table does not model. | test: `tests/test_ferpa_pack.py::test_consent_must_match_holder_records_recipient_and_purpose` |
| SW-D-15 | SHOULD | Declare a covert-channel objective as a rate (bits per minute across concurrent tasks); a dimension left unbounded fails the objective. | test: `tests/test_master_guide_measures.py::test_channel_slo_is_a_rate_and_fails_when_unbounded` |

## Composition and oversight

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| SW-C-8 | SHOULD | Staff review to the declared floor from arrival rate and review time; when understaffed, defer to the manual route and never lower the floor. | test: `tests/test_master_guide_measures.py::test_staffing_honours_the_floor_and_reports_understaffing` |

## Evidence and recovery

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| SW-E-7 | SHOULD | Commit evidence in a Merkle tree so inclusion and append-only consistency are provable in logarithmic size, and let witnesses co-sign growth from consistency proofs. | test: `tests/test_transparency.py::test_every_consistency_proof_verifies_and_a_rewrite_fails` |
| SW-E-8 | SHOULD | Require checkpoint co-signatures from a quorum of distinct administrative domains, counted by the verifier's registry, and exchange signed heads to detect split views. | test: `tests/test_transparency.py::test_quorum_counts_distinct_domains_not_keys` |
| SW-E-9 | SHOULD | Sign checkpoints with forward-secure keys so a key compromised in one period cannot sign for an earlier one. | test: `tests/test_forward_secure_and_time.py::test_a_key_stolen_today_cannot_sign_yesterday` |
| SW-E-10 | SHOULD | Anchor checkpoint time to several independent, chained time sources and refuse a checkpoint whose claimed time falls outside the anchored interval. | test: `tests/test_forward_secure_and_time.py::test_a_lying_server_is_caught_by_the_chain` |

## Verification

| ID | Level | Requirement | Evidence in this repository |
|---|---|---|---|
| SW-V-13 | MUST | Publish a registry of every refusal code the build can emit, generated from source, and fail the build when it drifts. | test: `tests/test_master_guide_measures.py::test_refusal_registry_is_current_with_the_code` |
