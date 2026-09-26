# Master guide: secure agent swarms by construction

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Specification](SPECIFICATION.md) · [Glossary and acronyms](GLOSSARY.md#acronyms-in-plain-language)
>
> **Recommended next:** Start from the framework's front door, [`FRAMEWORK.md`](FRAMEWORK.md): `fssaira framework init`, then `fssaira framework assess --roadmap`. This guide is the reasoning behind it.
>
> **Who this is for:** CIOs, CISOs, enterprise architects, risk, legal and data-protection
> officers, and the engineers who will build and run the system. Each section says who acts on it.

**The promise.** An organisation can add agents, models and vendors without silently adding
authority. A swarm running under this guide cannot exceed its mandate, launder data through a
chain of agents, multiply its budget by spawning workers, turn agreement between agents into
permission, or rewrite its own history. Each of these is a refusal that a buyer can rerun,
not a property a vendor asks you to believe. The promise holds inside the trusted base that
you declare and measure (§6). The conformance run in your own deployment is what proves it.

**The rule everything follows.** The model proposes. Separate trusted software decides. A
named person answers for the decision. Evidence that anyone can recompute shows what happened.

---

## 1. How to use this guide

| If you are… | Read | Then run |
|---|---|---|
| Executive sponsor | §2, §3, §12 | nothing; ask for the §11 evidence bundle and the `fssaira assure report` digest |
| CISO / architect | §4–§8 | `fssaira assure report` (every check below, one digest) |
| Risk, legal, DPO | §3, §9, §11 | the sector pack tests (`tests/test_ferpa_pack.py` for education) |
| Engineering lead | §4–§8 | the full conformance suite, `make test` |
| Operations | §8, §10 | `fssaira assure staffing`, `fssaira small verify` |
| Procurement | §11 | the vendor demonstration script in §11 |

Every control below names **where it is implemented**, **the test that fails if it is
removed**, and **the refusal code an auditor searches for**. The registry of all codes
(470 at the time of writing) is generated from the source into
[`refusal_registry.json`](refusal_registry.json). A test fails if a code is added without being
registered.

---

## 2. Critical review of the draft guide

The draft this guide replaces had the right spine. Read critically, it also made claims that
could not be verified, cited artefacts that do not exist, and missed attacks a hostile reviewer
would raise first. A master guide that survives review has to correct these, so they are listed
here with their fixes.

### 2.1 Claims that were wrong or unverifiable

| Draft said | Problem | Correction in this guide |
|---|---|---|
| Contract clauses returning `EPOCH_STALE`, `RELEASE_RECIPIENT_NOT_CLEARED`, `EFFECT_CREDENTIALS_NOT_PERMITTED`, `SELF_APPROVAL_NOT_PERMITTED` | None of these codes exists. A contract that tests for a non-existent code passes vacuously. | §11 clauses cite registered codes only (`STALE_PROPOSAL`, `FRESHNESS_UNPROVEN`, `DESTINATION_DENIED`, `INDEPENDENT_CONFIRMATION_REQUIRED`, …). A test keeps the registry current. |
| Rego rule using `foreach(labels, func(l) …)` | Not Rego. It also allowed an **unlabelled** artefact to go to any recipient. | §7.2 gives valid OPA v1 syntax that refuses empty label sets. |
| Kubernetes NetworkPolicy `{ role: enforcement-gateway: "true" }` | Invalid YAML. It had no ingress deny and no DNS rule. Worst of all, it left the pod's **service-account token** mounted, which is an ambient credential inside a "credentialless" cell. | §7.3 gives a working policy and pod spec with `automountServiceAccountToken: false`. |
| "Verifier recompute ≈195k records/s" | No script in the repository produces this figure. | Measure your own host with `fssaira scale measure`. Figures in this guide come only from commands you can run. |
| "OWASP Agent Control Standard", "NIST 6001" | The first is not a published standard. The second is a mis-citation. | §13 maps to OWASP Top 10 for LLM Applications, OWASP Agentic AI Threats and Mitigations, NIST AI RMF (AI 100-1) and its Generative AI Profile (NIST AI 600-1), and ISO/IEC 42001. |
| Cron jobs calling `/opt/verifier/verify_incremental` | A fictional binary. | §10 uses `fssaira small verify --mode incremental` and `--mode full`. |
| "Cannot exceed its mandate … at any scale and with any vendor" | This is an unconditional claim, and a reviewer should reject it. | The promise is stated inside the declared, measured trusted base, and proven per deployment. |

### 2.2 "Gaps" in the draft that were already closed

Four of the draft's eleven gaps described work that already existed. Presenting them as open
would have understated the system.

| Draft gap | Already in place |
|---|---|
| C. Collapse error taxonomy | `TrustRuntime.dispatch` returns only `DENIED` to an agent. The specific code goes to the decision receipt. A refusal also reveals nothing about whether a record exists (spec D-11). |
| C. Egress shaping | `covert_channels.py` already makes destination, path, schedule, size and count canonical, and charges the residual bits against a per-task budget (`CHANNEL_BUDGET_EXHAUSTED`). |
| G. Tier thresholds | `scale.py` and `fssaira scale advise`. See [`SCALE_TIERS.md`](SCALE_TIERS.md). |
| §12 (enhancements). Agent dossier | `TrustRuntime.agent_dossier` answers who the agent is, what it may do, what it did, what stopped it and what it could still leak. |

### 2.3 Gaps the draft missed

These came out of reviewing the code against the draft. Each is now closed in code (§5).

1. **There was no sanctioned way to change policy.** Any change to the passport counted as
   drift and quarantined the workload. So the draft's gap J ("approval continuity") was worse
   than stated: no policy migration was possible at all. `migrate_policy` now supplies one.
2. **Retries duplicate effects even on a perfect network.** The chaos harness found this. An
   adapter whose retry fires while the first reply is still in flight applies the effect twice
   unless it holds an idempotency key. Nothing has to fail for this to happen.
3. **Split view.** A compromised log can show one history to the regulator and another to the
   auditor. Individual witnesses cannot see this. Only witnesses that compare signed heads can
   (`detect_split_view`).
4. **Backdating with a stolen key.** A stolen notary key signs "last month" as easily as "now".
   Forward-secure keys and multi-source time anchors remove that ability.
5. **Witnesses from one organisation are one witness.** A quorum must count distinct
   administrative domains, as registered by the verifier, not as claimed by the witness.
6. **Staffing is part of the control.** A review floor with too few reviewers either queues
   forever or tempts someone to lower it. The guide now calculates the headcount the floor
   needs.
7. **The size of the trusted base was asserted, not measured.** It is now measured, with a
   build digest an attestation service can pin.

---

## 3. Five commitments (state these before anything is built)

1. **Untrusted intelligence.** Every model and agent is an untrusted proposer, whoever
   supplies it.
2. **Proof before power.** No read, write, delegation or release runs until the gate has
   checked identity, current state, intersected rights and the exact operation, and committed
   the decision atomically.
3. **Whole-chain safety.** Constraints travel with the work across every handoff. Checking
   each hop against its own delegator contained 2 of 10 delegation risk classes; verifying the
   whole chain contained 10 of 10 (`tests/test_delegation.py`, see
   [`ASSURANCE.md`](ASSURANCE.md)).
4. **Independent evidence.** Recompute; never trust stored verdicts. The enforcer is never its
   own witness. A quorum of witnesses from different domains co-signs.
5. **Visibility without surveillance.** Monitors see counters, refusal codes and evidence
   heads, never protected content. A monitor can slow or stop work but never grant it.

---

## 4. Reference architecture

```
 ┌──────────────── untrusted ────────────────┐
 │  Agent cells (one per workload)            │  no credentials, default-deny egress,
 │  model + tools as proposals only           │  immutable code, no metadata service
 └───────────────┬────────────────────────────┘
                 │ SDK primitives only (UNDECLARED_INTERFACE otherwise)
 ┌───────────────▼──────────────── trusted base (measured, §6) ─────────────────┐
 │ Decision plane: task contract · shared budget · declared task graph ·          │
 │   typed effects · digest- and policy-bound approval · sealed release ·         │
 │   epoch revocation · freshness proofs · covert-channel budget                  │
 │ Adapters: fenced commit (epoch + idempotency key) · reconciler                 │
 │ Evidence plane: intent-before-effect ledger · notary · Merkle tree heads ·     │
 │   forward-secure keys · time anchors                                           │
 └───────┬────────────────────────────────────────────────┬───────────────────────┘
         │ checkpoints, tree heads                         │ counters, codes, heads
 ┌───────▼──────── other administrators ─────────┐  ┌──────▼──── observation ────────┐
 │ Witness quorum (N of M domains) · verifier     │  │ metadata-only dashboards,      │
 │ recomputes · split-view gossip                 │  │ agent dossier, receipts        │
 └────────────────────────────────────────────────┘  └────────────────────────────────┘
```

There are two tiers and both give the same verdicts. The **small** tier (SQLite, standard
library) suits pilots and low volume. The **big** tier (PostgreSQL, Kafka, Iceberg, Spark)
adds throughput and independent consumers. `fssaira scale advise` picks between them from
your workload. On one development-laptop measurement the big stack used about 12.6× the memory
([`SCALE_TIERS.md`](SCALE_TIERS.md)).

---

## 5. Control catalogue

**Mandatory for every deployment.** The "Remove it and…" column states the harm that
returns when the control is removed. The named test demonstrates that harm.

| # | Control | Implemented in | Remove it and… | Proven by | Auditor searches for |
|---|---|---|---|---|---|
| 1 | Credential-less agents | `tbc/runtime.py`, `agent_cell.py` | model output reaches the record store | `tests/test_privilege_invariance.py`, `tests/test_agent_cell.py` | `ENVELOPE_DENIED` |
| 2 | Task contract, exact scope, expiry | `tbc/contracts.py` | wildcard reads | `tests/test_tbc_sdk.py` | `CONTEXT_SCOPE_DENIED`, `TASK_EXPIRED` |
| 3 | Shared swarm budget, atomic reservation | `TrustRuntime.reserve_budget` | spawning multiplies spend | `tests/test_tbc_composition_controls.py` | `AGGREGATE_BUDGET_EXHAUSTED`, `CALL_BUDGET_EXHAUSTED` |
| 4 | Typed effects, independent confirmation | `approve_effect` | proposer approves itself | `tests/test_tbc_composition_controls.py` | `INDEPENDENT_CONFIRMATION_REQUIRED` |
| 5 | Digest-bound approval | `exact_action.py` | approve X, execute Y | `tests/test_exact_action.py` | `EXACT_APPROVAL_REQUIRED`, `ARTIFACT_DIGEST_MISMATCH` |
| 6 | **Policy-bound approval and migration** *(new)* | `TrustRuntime.migrate_policy` | approve under old rules, execute under new | `tests/test_approval_policy_pinning.py` | `POLICY_VERSION_CHANGED` |
| 7 | Sealed release, label inheritance | `disclosure.py`, `authorize_release` | reader → summariser → publisher leak | `tests/test_disclosure.py` | `DESTINATION_DENIED`, `DECLASSIFICATION_REQUIRED` |
| 8 | Revocation epoch and freshness | `revoke_task`, `check_freshness` | queued work survives consent withdrawal | `tests/test_tbc_composition_controls.py` | `STALE_PROPOSAL`, `FRESHNESS_UNPROVEN` |
| 9 | **Fenced commit under chaos** *(new)* | `revocation_chaos.py` | stale effects under partition or skew; duplicate effects on retry | `tests/test_revocation_chaos.py` | invariant counts (§8) |
| 9b | **Adapter qualification kit** *(new)* | `adapter_qualification.py` | a store that ignores the epoch or a sink without keys reaches production | `tests/test_adapter_qualification.py` | `ADAPTER_NOT_QUALIFIED`, `STORE_STALE_COMMIT` |
| 10 | Declared task graph | `admit_graph` | undeclared spawn or edge | `tests/test_tbc_composition_controls.py` | `GRAPH_NOT_DECLARED`, `NODE_NOT_ADMITTED` |
| 11 | Restricting monitor | `apply_monitor_finding`, `Guardian` | monitor grants authority | `tests/test_behaviour_watch.py` | `STALE_MONITOR_EVIDENCE`, `MONITOR_REPLAY` |
| 12 | Contained agent cell | `agent_cell.verify_cell` | ambient credentials reachable | `tests/test_agent_cell.py` | `CellNotIsolated` (exception) |
| 13 | Intent before effect, witnessed checkpoints | `evidence_notary.py`, `witness.py` | silent rewrite or truncation | `tests/test_witness.py` | `WITNESS_FORK`, `LEDGER_HISTORY_REWRITTEN` |
| 14 | **Merkle proofs and domain quorum** *(new)* | `transparency.py` | proofs grow with the ledger; one organisation is every witness | `tests/test_transparency.py` | `MERKLE_FORK`, `WITNESS_QUORUM_NOT_MET`, `EVIDENCE_SPLIT_VIEW` |
| 14b | **Federated checkpoint publication** *(new)* | `evidence_federation.py` | each evidence control checked separately, or not at all | `tests/test_evidence_federation.py` | `EVIDENCE_FEDERATED_VALID`, `EVIDENCE_ROOT_MISMATCH`, `EVIDENCE_RECORD_INCLUDED` |
| 15 | **Forward-secure keys, time anchors** *(new)* | `forward_secure.py`, `time_anchor.py` | a stolen key backdates history | `tests/test_forward_secure_and_time.py` | `FS_WRONG_PERIOD`, `TIME_SOURCES_DISAGREE`, `CHECKPOINT_TIME_UNANCHORED` |
| 16 | Covert-channel budget and **rate SLO** *(new)* | `covert_channels.py`, `channel_slo.py` | allowed choices become a signal | `tests/test_channel_budget.py`, `tests/test_master_guide_measures.py` | `CHANNEL_BUDGET_EXHAUSTED`, `CHANNEL_SLO_EXCEEDED` |
| 17 | Review floor, capacity and **staffing** *(new)* | `approve_effect`, `oversight_staffing.py` | rubber-stamping | `tests/test_oversight.py`, `tests/test_master_guide_measures.py` | `REVIEW_DEFERRED_TO_MANUAL` |
| 18 | Metadata-only visibility | `monitor_snapshot`, `decision_receipts` | observability leaks payloads | `tests/test_tbc_composition_controls.py` | receipts carry digests, never text |

**Sector pack (education).** Row 19 applies wherever student records are in scope.

| # | Control | Implemented in | Remove it and… | Proven by | Auditor searches for |
|---|---|---|---|---|---|
| 19 | **FERPA and minors pack** *(new)* | `ferpa.py` | release outside 34 CFR Part 99 | `tests/test_ferpa_pack.py` | `FERPA_CONSENT_REQUIRED`, `FERPA_STATEMENT_MISSING`, `MINOR_DUAL_APPROVAL_REQUIRED` |

---

## 6. Trusted base: measured, not asserted

Run `fssaira assure trusted-base`. It reports four things:

- **Size.** SLOC for each trusted component, and the trusted fraction of the package. In
  this repository today: 7,974 of 32,805 SLOC (24%), in five components (kernel, decision
  plane, evidence plane, key custody, containment). There is no native code in the package.
- **Build measurement.** A SHA-256 over every trusted file. Your attestation service pins
  this digest (TPM quote, confidential-computing report, or signed deployment manifest). A
  changed enforcer produces a different digest and is refused.
- **SBOM.** A CycloneDX 1.5 software bill of materials covering the enforcer's installed
  dependencies, for your supply-chain scanner.
- **Refusal registry size.** How many refusal codes the build can emit.

`TRUSTED_COMPONENTS` in `trusted_base.py` is the architectural claim. Anything added to the
enforcement path (an OPA engine, an API gateway, a KMS client) must be added to that list and
re-measured. Hardening that belongs to the deployment, not the code: signing and witness keys
in an HSM or KMS (`kms_vault.py` is the seam), separate administrators for the model runtime
and for evidence custody (spec T-4), and dual control on consequential typed effects.

---

## 7. Build it: phase by phase

Each phase has an exit test. Do not start the next phase until the current one passes in
**your** environment.

### 7.1 Phases

| Phase | Build | Exit test |
|---|---|---|
| 1. Keys out, contract in | agent cells without credentials, task contracts, the gate | `tests/test_privilege_invariance.py`, `tests/test_agent_cell.py` pass; `fssaira doctor` is clean |
| 2. Budget and scope | shared budgets, exact IDs, declared task graph | composition tests pass; no double spend under parallel spawn |
| 3. Typed effects | independent confirmation, digest-bound and policy-bound approval, objection window | `tests/test_exact_action.py`, `tests/test_approval_policy_pinning.py` |
| 4. Sealed release | labels, declassification rules, sector pack | `tests/test_disclosure.py`, the sector pack tests |
| 5. Evidence plane | ledger, notary, **witness quorum across domains**, verifier cadence | `tests/test_witness.py`, `tests/test_transparency.py`; `fssaira small verify` is INTACT |
| 6. Distributed revocation | fenced adapters with idempotency keys, reconciler | `fssaira assure chaos` exits 0; your own adapters meet the same invariants (§8) |
| 7. Containment and visibility | measured cells, metadata-only dashboards, dossier | unqualified hosts refused; receipts contain no payloads |

### 7.2 Policy as code (if you use OPA)

The reference gate is Python. If you put policy in OPA, the engine becomes part of the
trusted base, so add it to §6. Write the release rule so that an **unlabelled** artefact is
refused, never released to everyone:

```rego
package release

import rego.v1

default allow := false

allow if {
	count(input.artifact.labels) > 0
	every label in input.artifact.labels {
		label in data.clearances[input.recipient]
	}
}
```

### 7.3 Agent-cell isolation on Kubernetes

A cell is credential-less only if the platform does not hand it a token. The Kubernetes
service-account token is exactly such an ambient credential.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: agent-cell
  namespace: agents
  labels: {role: agent-cell}
spec:
  automountServiceAccountToken: false   # no ambient Kubernetes credential
  containers:
    - name: agent
      image: registry.example/agent@sha256:<pinned digest>
      securityContext:
        readOnlyRootFilesystem: true
        allowPrivilegeEscalation: false
        runAsNonRoot: true
        capabilities: {drop: ["ALL"]}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-cell-isolation
  namespace: agents
spec:
  podSelector:
    matchLabels: {role: agent-cell}
  policyTypes: ["Ingress", "Egress"]
  ingress: []                            # nothing calls into a cell
  egress:
    - to:
        - namespaceSelector:
            matchLabels: {kubernetes.io/metadata.name: enforcement}
          podSelector:
            matchLabels: {role: enforcement-gateway}
      ports: [{protocol: TCP, port: 8443}]
```

The cell reaches the gateway by address, injected at deploy time, so no DNS egress rule is
needed. If you must resolve names, add a rule for your cluster DNS only. Also block the cloud
metadata endpoint at the node (for example, an IMDSv2 hop limit of 1, or workload identity
disabled for this namespace). Then prove the result on the running cell: `probe_cell` in
`agent_cell.py` checks it from inside, and `verify_cell` refuses a cell it cannot confirm is
isolated.

### 7.4 Task contract (the job ticket)

`profiles/tbc/education-task.json` is a complete example. Its seven fields are task, purpose,
subject, tenant, exact scope, shared budget and expiry. Scope has no wildcards. An unknown
identifier is refused; it is never treated as a match.

---

## 8. Distributed revocation: the invariants your adapters must meet

In one process, revocation is a transaction. Across adapters it becomes a distributed-systems
claim, and `fssaira assure chaos` tests that claim. It runs 200 seeded runs per discipline,
with partitions, lost and duplicated messages, delay and clock skew. Latest run:

| Discipline | Stale effects | Duplicate effects | Verdict |
|---|---|---|---|
| **fenced** (design): the store commits (effect, epoch) atomically; the adapter applies only committed effects, once per idempotency key | **0** | **0** | holds |
| check-then-act: read the epoch, apply later | 271 | 0 | ablation caught |
| local-clock lease: judge proof age by the adapter's own clock | 187 | 0 | ablation caught |
| no idempotency key | 0 | 7,674 | ablation caught |

These are simulation counts from `fssaira.revocation_chaos`, which models the protocol, not
your database. Your adapters qualify by meeting the same three invariants against your real
store and systems:

1. **No stale effect.** No effect's point of no return comes after the revocation of the
   epoch it was authorised under.
2. **Exactly once.** Every external effect carries an idempotency key, and the external
   system honours it.
3. **Reconciled.** After the reconciler replays committed but undelivered effects, the set of
   committed effects equals the set of applied effects.

### 8.1 Qualify your own store and sink

`fssaira.adapter_qualification` turns the simulation into a qualification of your own code.
Wrap your authority store behind four methods (`revoke`, `epoch`, `commit`, `committed`) and
your external system behind one (`deliver`). `qualify(store_factory, sink_factory)` then drives
the real objects through the same seeded fault campaign. `concurrent_revocation_check` races real
threads committing against a revoking thread, then replays the store's own ordered log to show
that no commit carries a superseded epoch. The reference `SqlAuthorityStore` and `SqlSink`
qualify. The kit's own tests include two deliberately broken versions, a store that trusts the
adapter's epoch and a sink without keys, and both fail qualification. That is how you know the
kit can catch what it claims to catch.

```python
from fssaira.adapter_qualification import qualify, concurrent_revocation_check
result = qualify(lambda seed, tasks: MyStore(dsn, tasks), lambda seed: MySink(endpoint))
assert result["code"] == "ADAPTER_QUALIFIED"
```

A partitioned adapter that cannot reach the store **holds** the effect. It never decides
alone. An effect committed before the revocation may still be delivered after it; the
harness reports the worst delivery lag. For irreversible effects (email, payment), use the
objection window (`effect_delay_seconds`) so that revocation can still cancel them.

---

### 8.2 Evidence: one publication step, one verdict

`EvidenceFederation.publish(leaves)` commits the ledger to a Merkle root, signs the tree head
with the forward-secure key for the current period, anchors its time with chained queries to
several time servers, and collects co-signatures from witnesses in different domains. Each
witness is given a logarithmic consistency proof, not the records themselves.
`verify_federated` checks all of it, plus the recomputed root when you hold the leaves, and
reports the first failure by code. `prove_record` and `verify_record` let an appeal or a spot
check confirm that one receipt is in a published checkpoint without revealing the rest of the
ledger. `runtime_leaves` reads the runtime's own evidence table, so this works on the live log.

## 9. Human oversight as capacity

The review floor refuses approvals faster than careful reading allows, and sends them to the
manual route. That is correct, but it raises an operational question: how many reviewers are
needed. `fssaira assure staffing` answers with the Erlang C queueing model. The floor is the
minimum service time, and a low-risk lane loads reviewers only through its post-audit sample.

```
fssaira assure staffing --arrivals-per-hour 40 --mean-review-seconds 60 \
    --floor-seconds 180 --target-wait-seconds 900 --on-shift 2
  effective review time 180.0 s (the floor binds)
  reviewers needed: 3  (utilisation 0.6667, service level 0.997)
  ✗ understaffed: 6.0 items/h go to the manual route; do not lower the floor
```

**Operating rule:** understaffing is fixed with staff, batching or a low-risk lane with audit
sampling, never by lowering the floor. The model assumes exponential review times, and real
review times have a heavier tail. Treat the number as a floor on headcount, and recalibrate
from measured times (`review_calibration.py`).

---

## 10. Operate it: owners, KPIs, cadence

### 10.1 Who owns what

| Role | Owns | Must not also hold |
|---|---|---|
| Workflow owner | task contracts, approvers, review capacity | evidence custody |
| Risk / legal / DPO | policy versions (`migrate_policy` reason text), sector pack table | operator keys |
| Enforcer operations | gateway, epochs, budgets, adapters, cell qualification | witness keys |
| Evidence auditor | one witness domain, verifier runs, evidence reports | the notary key |
| Approvers | typed-effect approvals within their floor | the proposal they approve |
| Appeals owner | receipts-based appeals | protected content beyond the case |

### 10.2 KPIs, each computed by a command

| KPI | Target | Source |
|---|---|---|
| Refusals by class (purpose, self-approval, release, stale) | trend reviewed weekly | `decision_receipts` |
| Revocation cut-through | 0 stale effects; worst delivery lag within the objection window | `fssaira assure chaos`, adapter qualification |
| Budget integrity | 0 double spend | reservation settlement report (`reservations`) |
| Witness health | quorum met on every checkpoint; 0 split views | `verify_quorum`, `detect_split_view` |
| Verifier cadence | hourly incremental, daily full recompute | `fssaira small verify --mode incremental` / `--mode full` |
| Oversight honesty | rubber-stamp rate 0; queue stable | `manual_queue`, `fssaira assure staffing` |
| Channel rate | at or below the declared bits-per-minute SLO | `channel_slo.check_slo` |
| Trusted-base drift | build measurement equals the attested digest | `fssaira assure trusted-base` |

```
# verifier cadence (crontab)
0 * * * *  fssaira small verify --archive /evidence/archive.db --mode incremental --checkpoint /evidence/checkpoint.json --public-keys /evidence/notary-keys.json
30 2 * * * fssaira small verify --archive /evidence/archive.db --mode full        --checkpoint /evidence/checkpoint.json --public-keys /evidence/notary-keys.json
```

### 10.3 Policy change runbook

1. Legal or the DPO approves the new policy text. Bump `policy_version`.
2. The operator runs `migrate_policy(token, new_passport, reason=…)`. The version must
   increase (`POLICY_VERSION_NOT_INCREASING`) and the workload must stay the same
   (`POLICY_WORKLOAD_MISMATCH`).
3. The runtime quarantines any task the new policy no longer covers, and cancels held effects,
   sending them to re-review (`policy_changed_rereview`).
4. Approvals and proposals made under the old version refuse with `POLICY_VERSION_CHANGED`.
   The work is proposed again under the new rules.
5. The `tbc_policy_migrated` evidence event records both passport digests, the operator, and
   what was contracted and rerouted.

---

## 11. Procurement: trust as a contract deliverable

### 11.1 Clauses (use as written)

- **Credentials.** Agent processes SHALL hold no credential for any record store or external
  system. All effects SHALL pass through the enforcement gateway. The supplier SHALL
  demonstrate `ENVELOPE_DENIED` for an undeclared operation and `UNDECLARED_INTERFACE` for an
  undeclared primitive.
- **Exact approval.** A consequential effect SHALL execute only with an approval bound to the
  proposal digest **and the policy version** in force. It SHALL refuse with
  `EXACT_APPROVAL_REQUIRED` or `POLICY_VERSION_CHANGED` otherwise. The proposer SHALL NOT
  confirm its own proposal (`INDEPENDENT_CONFIRMATION_REQUIRED`).
- **Revocation.** Revocation SHALL raise the task epoch. Queued effects SHALL refuse with
  `STALE_PROPOSAL`, and adapters SHALL refuse unfresh proofs with `FRESHNESS_UNPROVEN`. The
  supplier SHALL meet the three invariants of §8 under fault injection in the buyer's
  environment.
- **Release.** Outputs SHALL inherit every label they were built from, and SHALL be released
  only to cleared destinations (`DESTINATION_DENIED`). Declassification SHALL be approved by
  someone other than the output's holder (`DECLASSIFICATION_SELF_APPROVED` otherwise).
- **Evidence.** Checkpoints SHALL be co-signed by witnesses in at least two administrative
  domains outside the supplier (`WITNESS_QUORUM_NOT_MET` otherwise). The buyer SHALL be able
  to recompute the archive independently. Evidence SHALL contain no protected values.
- **Trusted base.** The supplier SHALL deliver a trusted-component list, SLOC per component,
  a CycloneDX SBOM, and a build measurement that the buyer's attestation pins. A changed
  measurement is a changed product and requires the demonstration to be run again.
- **Rerun.** The demonstration below SHALL be run again after every model, vendor, policy or
  enforcer change.

### 11.2 Vendor demonstration script (run live, before signature)

1. Show an agent cell failing isolation, and the production refusal that follows.
2. Propose, confirm, approve and execute one effect. Show the receipt, and show that it has
   digests and no text.
3. Approve, run `migrate_policy`, then execute. Show `POLICY_VERSION_CHANGED`.
4. Approve, revoke, execute. Show `STALE_PROPOSAL`.
5. Release to an uncleared destination. Show `DESTINATION_DENIED`.
6. Rewrite one archived record. Show the verifier failing and the witness refusing
   (`WITNESS_FORK`).
7. Run `fssaira assure report --output report.json`, and hand over the JSON and its digest.
   The buyer runs the same command on the same commit and compares digests.

### 11.3 Evidence bundle required before go-live

Use the minimum bundle in [`GAPS.md`](GAPS.md#minimum-evidence-bundle-for-a-pilot-decision),
together with the outputs of §6, §8 and §9 and the witness-quorum configuration.

---

## 12. What you can claim, and the evidence behind each claim

| You can claim | Because |
|---|---|
| The swarm cannot act beyond its contract | gate refusals, tested and registered |
| Spawning agents does not multiply authority or spend | shared budget, atomic reservation |
| Agreement among agents is not permission | independent confirmation and approval |
| Approvals do not survive a change of rules | policy-bound approval and migration |
| Revocation holds across adapters under faults | the fenced-commit invariants, in your own qualification run |
| History cannot be quietly rewritten, forked or backdated | witness quorum, split-view detection, forward-secure keys, time anchors |
| The enforcer is small and is the one that was reviewed | measured SLOC, SBOM, build measurement |
| Oversight is real, not rubber-stamped | floor, capacity, staffing calculation |

Some claims can only be made with evidence from your own deployment. These are the field
rows in [`GAPS.md`](GAPS.md): institutional pilot, reviewer accuracy under load, qualification
of your specific backends and identity provider, a physical one-way link where one is used,
independent security review, and fairness and appeal outcomes. The code gives you the
instruments for each of them. The measurements are yours to produce.

---

## 13. Standards map

| Framework | Where it lands here |
|---|---|
| OWASP Top 10 for LLM Applications (2025): prompt injection, excessive agency, sensitive information disclosure | A-1/A-3 (proposal ≠ authority), D-1…D-13 (governed disclosure), control 7 |
| OWASP Agentic AI Threats and Mitigations: tool misuse, privilege compromise, memory poisoning, cascading hallucination, rogue agents | controls 1–4, 10, 11; memory namespaces bound to epoch and retention |
| NIST AI RMF (AI 100-1): Govern, Map, Measure, Manage | §10 ownership (Govern); contracts and packs (Map); KPIs, chaos, staffing (Measure); revocation, migration, manual route (Manage) |
| NIST AI 600-1 (Generative AI Profile) | information security, information integrity, human–AI configuration: controls 13–17 |
| ISO/IEC 42001 (AI management system) | policy versioning and migration, roles (§10.1), monitoring (§10.2), evidence of operation (§5) |
| FERPA, 34 CFR Part 99 | `ferpa.py`, every decision cites its section |

The normative text is in [`SPECIFICATION.md`](SPECIFICATION.md). Requirements added with this
guide are in the companion [`SPECIFICATION_SWARM_PROFILE.md`](SPECIFICATION_SWARM_PROFILE.md)
(SW-T-6, SW-A-7 to SW-A-9, SW-C-8, SW-D-14, SW-D-15, SW-E-7 to SW-E-11, SW-V-13, SW-V-14).

---

## 14. One-page checklist

- [ ] Agents hold no credentials; the service-account token is not mounted; the metadata
      endpoint is blocked; `verify_cell` passes.
- [ ] Every job has a task contract with exact IDs, a shared budget and an expiry.
- [ ] Approvals are bound to the digest **and** the policy version. Policy changes go only
      through `migrate_policy`.
- [ ] Sealed release; unlabelled outputs are refused; the sector pack is validated by the
      registrar and counsel.
- [ ] Revocation: your store and sink return `ADAPTER_QUALIFIED` and `STORE_LINEARIZABLE`
      (§8.1); irreversible effects wait out the objection window.
- [ ] `fssaira assure report` is PASS, and its digest is recorded with the release.
- [ ] Evidence: a witness quorum across at least two outside domains; split-view gossip;
      forward-secure keys; time-anchored checkpoints; hourly and daily verification.
- [ ] Trusted base measured, SBOM delivered, build digest attested.
- [ ] Review floor staffed to `fssaira assure staffing`; rubber-stamp rate 0.
- [ ] The vendor demonstration (§11.2) is run again after every model, vendor, policy or
      enforcer change.
- [ ] Appeals are answered from receipts, without reading protected content.
