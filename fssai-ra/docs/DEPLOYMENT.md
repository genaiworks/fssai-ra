# Deployment: profiles, promotion gates and isolation obligations

> **Documentation navigation:** [Documentation map](README.md) · [Architecture in code](ARCHITECTURE.md) · [Operations](OPERATIONS.md) · [Security model](SECURITY.md) · [Diode deployment](DIODE_DEPLOYMENT.md)
>
> **Recommended next:** Read the [threat model](../deploy/THREAT_MODEL.md), then run `fssaira promote --profile deploy/profiles/teaching.yaml`.

The repository proves enforcement logic on synthetic data. A deployment has to
prove it can be relied on in its environment. This page states what that
takes, and which parts code checks rather than people.

## Prefer the smallest deployment that fits

A transactional store (SQLite or PostgreSQL) plus the two mediators is a complete
deployment. Kafka, PySpark, Iceberg, Redis, object storage, a hardware diode and
multiple models are optional integrations, each needing its own justification. A
backend inherits no assurance until the conformance suite passes on its exact
implementation (`fssaira.kernel.assurance`), so a reference stack cannot become a
vendor dependency presented as sovereignty.

## Deployment profiles

Profiles live in `deploy/profiles/` and are validated by
`fssaira.lifecycle.deploy`. A profile cannot make a consequential deployment
quietly weaker. The loader refuses a consequential profile that enables
ablation switches, drops process isolation or conformance, or omits a mandatory
gate.

| Profile | Stage | Consequential | Data | Ablation switches |
|---|---|---|---|---|
| `teaching` | Sandbox | No | Synthetic only | Lab only |
| `institutional` | Shadow pilot, then bounded operational pilot | Yes | Institutional, via mediators only | Forbidden |
| `hardware-isolated` | Bounded operational pilot | Yes | Institutional, via mediators only | Forbidden |

## Promotion gates

`fssaira promote` runs every gate the profile requires, from code:

| Gate | What runs |
|---|---|
| `contract_complete`, `failure_tests_exist`, `claims_register_no_unverified` | The contract stage: strict loader, AST test resolution, claims register |
| `pack_floor_passes` | Pack manifests load, agree with enforced configuration, and pass the kernel floor |
| `no_model_holds_a_key` | The bind stage: no untrusted component takes a credential, and no credential is reachable at any depth from the model object (attributes, containers, closures, bound methods). The agent wrapper's reference to the enforcement point is reported as an in-process limit |
| `falsifiers_zero_counterexamples`, `ablations_restore_harm` | Thesis and education falsifiers with a positive control, plus control ablation. **A consequential profile re-runs them during promotion and never trusts an artifact.** The teaching profile accepts an artifact only if it records a complete scope (every falsifier, ablation on) and matches the current governed digest. The digest covers all enforcement source, tests, scripts, deploy profiles, the threat catalogue and every pack source |
| `backend_conformance_current` | A passing conformance record exists for each configured backend's current implementation digest. Produce one per backend with `fssaira conformance --backend memory --record-out memory.json` (or `--backend sql --database-url ...` for sqlite/postgres), then `fssaira promote --records memory.json --records sqlite.json ...` (repeatable, one file per backend) |
| `evidence_matches_fresh_run` | `generate_results.py --check`, `conference_evidence.py --check`, `collect_results.py --check` |
| `table4_obligations_signed`, `interface_inventory_owned` | **Institutional evidence.** Code confirms a signed record exists and names an owner; it cannot confirm the obligation was met |

The last row is the honest boundary of automation. Code can refuse to promote
without the record. Only people can make the record true.

## Isolation obligations

- **Logical planes are not process isolation.** The executor and context gate need separate workload identities, least-privilege accounts and authenticated requests.
- **Model and worker containers hold nothing that grants power.** No credentials, privileged mounts, direct record ports, arbitrary outbound sockets or administrative APIs. Show denial from the actual model container, not from a unit test.
- **Generated code needs OS-level isolation.** `fssaira.integration.sandbox` runs code in a separate interpreter with an empty environment, a temporary directory, resource limits and a timeout. Its test also *executes* the limit: sandboxed code can still read a file its OS user can read. Use a container, VM or separate user for hostile code.
- **Evidence needs an outside witness.** Retain checkpoints outside the evidence writer's administrative boundary, or no rollback claim holds.
- **One-way transfer needs hardware to be one-way.** A Python interface cannot prove physical directionality. See [Diode deployment](DIODE_DEPLOYMENT.md).

## Operating a promoted capability

`fssaira operate --falsify-artifact <file>` fails when the governed
configuration has changed since a complete, passing falsification. Any edit to
enforcement code, a named test, a pack or a profile returns the capability to
stage 5.

In a running deployment, `fssaira.lifecycle.stages.operate` also receives the
live executor and oversight monitor. It fails on:

- any uncertain effect awaiting reconciliation;
- a saturated reviewer.

Offline, those two gates are reported as NOT RUN. The stage fails unless
`--allow-not-run` is given explicitly, and even then the gates are never
reported as passed.

## Stop conditions

Promotion stops, and the capability stays in its previous stage, when:

- a gate fails;
- a fresh evidence run does not match committed evidence;
- a backend's implementation changed since its conformance run;
- a model bundle changed since attestation;
- a Table 4 obligation has no named owner and versioned evidence.

During operation, the following trigger a scoped pause and manual service:

- policy drift;
- a harmful unexplained outcome;
- missing evidence;
- overdue emergency review;
- breached review capacity.

## What a deployment still cannot claim

- containment of a compromised mediator, administrator or signing key;
- prevention of inference from legitimately disclosed attributes;
- recall of bytes already released;
- anonymity from tokenization;
- correctness of an institutional policy that is enforced exactly as written.

The design aims at containment, not invulnerability.
