# Threat model and trusted computing base

This is the deployment-facing form of paper §3.4, Table 2 and Table 4. The
repository's offline suites test enforcement *logic*. Nothing in this file is
established by those suites. These are obligations a deployment must meet and
evidence it must produce.

## Adversary

The adversary may control:

- the model, planner and router;
- retrieved documents, tool responses and generated code;
- colluding delegated agents.

It may fabricate authorization text, request other subjects' records, replay
approvals, poison retrieved evidence, relabel a consequential action as harmless,
or try to export protected outputs.

The claim holds only while these function correctly: authenticated identities,
policy distribution, enforcement code, key custody, and the substrate that
isolates them. A compromised trusted mediator breaks an assumption. It is not an
attack the design contains, and it requires incident response.

## Trusted computing base

- the executor and context gate, and their policy inputs;
- the approval, grant and manifest signing keys, and key custody;
- the evidence store and its checkpoint witness;
- the identity provider and reviewer authentication;
- the JSON parser and canonicalizer, the Python, SQLite or PostgreSQL runtimes, the OS, the filesystem and CI;
- source and policy administrators.

The model is **outside** the TCB. Its serving process, host and network
isolation can still be trusted dependencies for confidentiality.

**Logical planes are not process isolation.** Python object boundaries in one
process do not contain hostile Python execution. `fssaira.integration.sandbox`
is process-level containment. It does not stop code running as the same OS user
from reading that user's files or opening sockets.

## Table 2 — Required trust boundaries

| Trusted dependency | Required separation | Failure consequence and response |
|---|---|---|
| Executor and context/release gate | Separate workload identities, least-privilege accounts, authenticated requests; no model-controlled policy input | Compromise can authorize harm. Disable affected automation, revoke credentials, restore from a reviewed build |
| Policy, identity and grant issuers | Versioned policy, two-person promotion for privilege expansion, protected signing keys | A validly signed bad policy remains bad. Independent policy review and rollback |
| Host, network, tool adapters and key service | No model credentials, privileged mounts, direct record ports, arbitrary outbound sockets, or administrative APIs | Bypass defeats complete mediation. Demonstrate denial from the actual model container and every worker |
| Evidence notary and checkpoint witness | Writer cannot replace pinned witness state or signing keys | A recomputed or rolled-back chain can appear valid. Compare externally retained sequence and head hash |
| Administrators and reviewers | Named powers, separation of duties, time-bounded emergency access, independently reviewed changes | Insider collusion and mistaken approvals remain residual. Contain scope and preserve redress |

Two mediators are two enforcement responsibilities, not two independent security
domains. Shared policy, hosts, administrators or credentials create common-mode
failures.

## Table 4 — Gap-closure obligations

Each row needs a named institutional owner and versioned evidence before
promotion. The `institutional` and `hardware-isolated` profiles list them under
the gate `table4_obligations_signed`.

| Hurdle | Required mechanism and accountable role | Closure evidence and stop condition |
|---|---|---|
| Bypass and common-mode compromise | Security owner isolates mediator identities, ports, storage, keys, workers and control plane | Negative tests from actual model and worker containers; any direct governed read/write blocks promotion |
| Policy and domain-pack escalation | Policy owner signs versioned packs; schema validation plus immutable kernel floor; peer review of privilege expansion | Malicious-pack and rollback tests against the instantiated runtime; unknown or stale policy denies |
| Tenant, beneficiary and delegation scope | Identity owner binds authenticated actor and beneficiary; intersects rooted grants and tenant/resource scope | Cross-tenant, sibling-agent, purpose, expiry and ancestor-revocation tests |
| Label and action composition | Data owner binds proposal to context receipts and propagates restrictions across every interface | End-to-end wrong-subject, stale-context, changed-proposal and release tests; missing provenance denies |
| Memory, retrieval and modality coverage | Data owner inventories caches, vectors, summaries, streams, OCR and handoffs; labels and invalidation follow derivation | Seeded sensitive-record probes across all paths, including cache hits; unknown lineage quarantines |
| Declassification and inference risk | Privacy owner approves exact outputs; reviews quasi-identifiers, small cohorts and repeated-query inference | Re-identification and differencing tests; tokens are not anonymity |
| Erasure and evidence retention | Records owner inventories keys and copies, propagates deletion and legal hold | Restore from every supported backup and attempt decryption independently |
| Model and tool supply chain | Platform owner pins approved bundles, endpoint identities, dependencies and credentials | Substitution, lying-runtime, redirect and malicious-tool tests |
| Distributed and external effects | Service owner uses transactional state/evidence, outbox, idempotency and reconciliation | Revoke/dispatch races, crash-at-each-boundary, duplicate delivery, stale version, backup restore |
| Evidence integrity and privacy | Assurance owner retains externally witnessed checkpoints; restricts and encrypts evidence access | Rewrite, truncation, rollback, key rotation and unauthorized-inspection tests |
| Review overload and correlated errors | Service owner declares measured capacity, queue deadlines, escalation and manual staffing | Workload and reviewer study; overload never auto-approves |
| Correctness, fairness and redress | Domain owner validates policy and source quality with affected users; independent appeal officer | Blinded merit assessment, subgroup analysis, completed appeal exercises |
| Availability, cost and sustainability | Operations owner measures budgets, fallback capacity, recovery objectives, cost and energy | Sustained-load and outage drills at declared targets |
| Transfer and external assurance | Adopting institution qualifies exact model, backend, domain, reviewer regime and administrative boundaries | Independent review, signed limitations and go/no-go record |

## Residual risks stated, not solved

- Covert channels and inference from rare or legitimately disclosed attributes.
- A compromised administrator, mediator or signing key.
- Substantively wrong institutional policy that is correctly enforced.
- Bytes already released before a revocation.
- Hostile generated code without OS-level isolation.

Tokenization is not anonymity. Containment, not invulnerability.
