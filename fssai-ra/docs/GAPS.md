# Evidence gaps and the work that closes them

The [pipeline walkthrough](PIPELINE_WALKTHROUGH.md#14-corrections-made-and-remaining-implementation-gaps) distinguishes implemented paths, newly tested SQL encryption examples and remaining distributed-integration gaps.


> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Convert the applicable rows into pilot exit criteria with [`ADOPTION.md`](ADOPTION.md), then attach the resulting evidence in [`ASSURANCE.md`](ASSURANCE.md).

This is the repository's **open-evidence register**. A green test suite closes
software regressions in the reference implementation. It does not close a field,
human-subject, hardware, organizational, or independent-assurance gap.

Use the table as a stopping rule. Do not relabel a row “closed” because a policy
was written, a component was installed, or a synthetic fixture passed. Close it
only with the evidence named in the final column, versioned to the deployment
that produced it.

| Open gap | Why it matters | What the repository does today | Evidence required to close it |
|---|---|---|---|
| **Institutional pilot** | A synthetic profile cannot show that the workflow fits a real service or that people can recover safely | Provides a bounded 30/60/90-day adoption path, manual fallbacks, decision packets, evidence-derived indicators (`fssaira pilot-report`), and a pilot protocol with outcome measures and stop criteria in [`PILOT_PROTOCOL.md`](PILOT_PROTOCOL.md) | Approved pilot protocol; deployment commit and configuration; incident and appeal log; exit-criteria report; named accountable owner |
| **Human review under load** | The oversight ceiling depends on how long careful review takes and how accuracy changes with load | Enforces a declared quota, deliberation floor, and escalation; the deployed server now enforces each pack's own review block (quota, 45-second floor, queue limit, timeout) instead of only reporting it; labels the degradation curve as declared, not observed | Ethics-approved, consented study or operational measurement with workload, accuracy, fatigue, subgroup, and uncertainty reporting |
| **Proposer/review-assistant correlation** | A dependent assistant can repeat the proposer's error while every runtime control remains green | Requires declared model, evidence-path, and adversarial independence before a lowered floor is accepted | Blinded evaluation across representative cases and model versions, including correlated-error rate and reviewer reliance |
| **Real delegated-agent deployment** | Constructed chains do not establish how an orchestrator, plugin, tool server, or sub-agent handles authority in production | Verifies rootedness, attenuation, cycles, expiry, leaf identity, human approval, and depth on fixtures | Adapter-specific conformance run; revocation and key-rotation tests; process-boundary traces; incident recovery exercise |
| **Distributed backend qualification** | In-memory and SQLite behavior does not prove a particular Redis, Kafka, PostgreSQL, Spark, or Iceberg deployment | Supplies adapters, Compose topology, conformance tests, and process-level resilience fixtures. Now also: a real-PostgreSQL multi-writer test (`tests/test_postgres_concurrency.py`, which found and fixed an evidence-sequence race), a fault drill (`scripts/fault_drill.py`: concurrent workflows while PostgreSQL restarts and Kafka stops, then `pg_dump`/restore comparison), and a TLS overlay for every data service. These are single-host results; they do not qualify multi-node failover, partitions or sustained production load | Qualification results for exact versions and topology; fault injection; backup/restore; failover; access-control review; sustained-load results |
| **Resource-level authorization and privacy** | A valid institutional role does not by itself establish which individual records that principal may inspect | Authenticates callers, prevents callers asserting their own role, restricts administrative and assurance operations, and keeps operational responses out of caches. A governed-disclosure kernel now enforces purpose-bound grants, subject and field scope, live consent, endpoint residency, session labels, exact-output declassification, and bounded break-glass on synthetic records, with ablations and a bounded model check; the reference HTTP API now routes grants, context assembly for model tasks, output labelling, declassification, release, and break-glass review through that gate. Grants, revocations, consent, sessions, outputs, and emergency-access obligations now persist in a transactional SQLite or PostgreSQL store; FHIR and SQL record sources, a live consent service, and grants signed by an institutional authorization server are implemented, fail closed, and are tested against local fixtures; value-level labels and thread and process races are tested. None has been qualified against a named institution's identity provider, consent system, record system, or production database under load | Domain-specific authorization policy; representative allow/deny tests at the HTTP and datastore layers; disclosure review; purpose and retention controls; access-log review |
| **Physical one-way boundary** | A software no-read-back interface cannot prove directionality against a compromised host | Defines the diode seam, transfer protocol, sequence checks, quarantine, and software emulator | Hardware-vendor evidence; independent installation inspection; reverse-channel and maintenance-path test; accreditation appropriate to the deployment |
| **Fairness, accessibility, and appeal quality** | Correct authority can still produce an unjust or inaccessible outcome | Preserves evidence and a manual/appeal path; makes no outcome-quality claim | Affected-community participation; accessibility testing; subgroup outcome analysis; appeal timeliness and correction-quality measures |
| **Cost, energy, and operational burden** | A technically bounded architecture may be unaffordable, carbon-intensive, or staff-intensive | Reports only narrow local performance measurements | Total-cost model; energy measurements; staffing and queue data; comparison against the current service and credible alternatives |
| **Independent security assurance** | Authors testing their own threat model cannot establish resistance to threats they missed | Publishes threat model, challenge corpus, property tests, model checking, and reproducible artifacts | Independent architecture review, penetration test/red team, remediation record, and—where needed—formal certification |
| **Educational effectiveness** | A well-designed lab is not evidence that participants learned or changed practice | Provides learning outcomes, exercises, and an assessment rubric | Pre/post protocol, cohort and denominator, scored artifacts, retention or transfer measure, limitations, and consent/privacy controls |
| **External adversary coverage** | An attack corpus written entirely by the project may share the authors' blind spots | Publishes a data-only contribution format and prints the external-contribution count | Reviewed external submissions from multiple domains, including failures the current design does not contain |

## Engineering gaps closed in code by the master-guide pass

[`MASTER_GUIDE.md`](MASTER_GUIDE.md) reviewed a draft list of eleven gaps against the code.
The rows below were **engineering** gaps: the code lacked the mechanism, so a test can now close
them. None of them closes a field row in the table above. Where a row says "your deployment",
the mechanism exists and a deployment still has to qualify it.

| Gap | Mechanism now in code | Test | Still needs, in your deployment |
|---|---|---|---|
| Trusted base size asserted, not measured | `trusted_base.py`, `fssaira assure trusted-base`: SLOC per component, CycloneDX SBOM, build measurement | `tests/test_master_guide_measures.py` | an attestation service pinning the measurement; independent review |
| Revocation across adapters unqualified | `revocation_chaos.py`, `fssaira assure chaos`: fenced commit clean under partition, loss, duplication, delay, skew; three ablations caught | `tests/test_revocation_chaos.py` | your store and adapters meeting the same invariants under fault injection |
| No sanctioned policy change; approvals not bound to rules | `TrustRuntime.migrate_policy`; policy-version pinning on proposals and approvals | `tests/test_approval_policy_pinning.py` | a policy-change runbook with named owners |
| Evidence proofs linear in ledger size; one witness domain | `transparency.py`: RFC 9162 inclusion and consistency proofs, tree-head witness, domain-distinct quorum, split-view detection | `tests/test_transparency.py` | witnesses actually run by separate organisations |
| Stolen key can backdate; clock is the enforcer's | `forward_secure.py`, `time_anchor.py` | `tests/test_forward_secure_and_time.py` | independent time servers; key erasure verified on the host |
| Covert channel bounded per task, not as a rate | `channel_slo.py` | `tests/test_master_guide_measures.py` | a signed-off bits-per-minute objective |
| Review floor without staffing arithmetic | `oversight_staffing.py`, `fssaira assure staffing` | `tests/test_master_guide_measures.py` | measured review-time distribution (the model assumes exponential) |
| No sector release table for education | `ferpa.py`: 34 CFR Part 99 paths with citations; stricter minors mandate | `tests/test_ferpa_pack.py` | registrar and counsel validation |
| Protocol qualified, deployment's own store and sink not | `adapter_qualification.py`: real store and sink in the chaos loop; concurrent linearization audit | `tests/test_adapter_qualification.py` | running it against your production database and external systems |
| Evidence controls verified one by one | `evidence_federation.py`: one publication step and one verdict; per-record inclusion proofs on the runtime ledger | `tests/test_evidence_federation.py` | publishing to parties outside the institution |
| No single reproducible assurance artefact | `assurance_report.py`, `fssaira assure report`: digest-stamped deterministic section | `tests/test_assurance_report.py` | a buyer reproducing the digest |
| Refusal codes not registered | `refusal_registry.py`, `docs/refusal_registry.json` | `tests/test_master_guide_measures.py` | none |

## What code can still improve without pretending these gaps are closed

- Keep deployment declarations visible in `fssaira doctor` and `/health`.
- Run every contract binding, conformance profile, recovery fixture, and public
  figure check in CI.
- Version profiles, dependencies, machine-readable results, and limitations
  together.
- Make negative and null results publishable: a failed conformance run or an
  uncontained external attack is evidence, not an embarrassment to delete.
- Provide adapters and schemas that let independent institutions contribute
  results without contributing personal data.

## Minimum evidence bundle for a pilot decision

Before consequential use, retain one bundle containing:

1. the exact repository commit, dependency lock or environment export, domain
   profile, contract, and contract bindings;
2. deployment topology, trust boundaries, identities, keys, data flows, egress
   paths, and the actual diode qualification where one is claimed;
3. conformance, resilience, negative-path, load, backup/restore, and incident
   exercise outputs;
4. declared review capacity and assistant/delegation posture, signed by the
   institutional owner rather than inherited from this repository;
5. impact, fairness, accessibility, appeal, cost, and energy measures with
   denominators and known exclusions; and
6. an independent review record with unresolved findings and an explicit
   go/no-go decision.

The bundle is deployment evidence, not a transferable badge. A new domain,
backend, model, reviewer regime, or authority chain changes the claim and must
regenerate the relevant evidence.

## Full-paper foundation audit

The expanded `paper/trust-by-construction.md` now makes the trusted substrate,
GenAI integration contract, cross-mediator composition, distributed semantics,
and promotion gates explicit. `paper/foundation-claims.json` separates runnable
fixture evidence from source-only components and unqualified deployment claims.
The optional in-memory privacy wrapper and strict registry now have HTTP
integration evidence in `tests/test_privacy_integration.py`. Persistent custody
(`SqlCustodyStore`), key-encryption keys held by a key service
(`VaultTransitKeyWrapper`, exercised against a real Vault), a deployed notary
(`CheckpointNotary`) and pack-floor deployment binding (the server refuses a pack
below the floor) now exist. Qualifying a hardware security module behind the key
service remains open. See `PRIVACY_REFERENCE.md`. The four-pack disclosure result is not an
education privacy evaluation or proof of the complete privacy pipeline.

The audit fixed predictable default keys in the model publisher and notary,
omitted-time expiry bypass, non-finite authorization time, overbroad erasure
completion reporting, and the inconsistent legitimate-delegation fixture. These
repairs do not close institutional, hardware, human-study, or deployment gaps.
