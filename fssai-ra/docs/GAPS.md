# Evidence gaps and the work that closes them

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
| **Institutional pilot** | A synthetic profile cannot show that the workflow fits a real service or that people can recover safely | Provides a bounded 30/60/90-day adoption path, manual fallbacks, and decision packets | Approved pilot protocol; deployment commit and configuration; incident and appeal log; exit-criteria report; named accountable owner |
| **Human review under load** | The oversight ceiling depends on how long careful review takes and how accuracy changes with load | Enforces a declared quota, deliberation floor, and escalation; labels the degradation curve as declared, not observed | Ethics-approved, consented study or operational measurement with workload, accuracy, fatigue, subgroup, and uncertainty reporting |
| **Proposer/review-assistant correlation** | A dependent assistant can repeat the proposer's error while every runtime control remains green | Requires declared model, evidence-path, and adversarial independence before a lowered floor is accepted | Blinded evaluation across representative cases and model versions, including correlated-error rate and reviewer reliance |
| **Real delegated-agent deployment** | Constructed chains do not establish how an orchestrator, plugin, tool server, or sub-agent handles authority in production | Verifies rootedness, attenuation, cycles, expiry, leaf identity, human approval, and depth on fixtures | Adapter-specific conformance run; revocation and key-rotation tests; process-boundary traces; incident recovery exercise |
| **Distributed backend qualification** | In-memory and SQLite behavior does not prove a particular Redis, Kafka, PostgreSQL, Spark, or Iceberg deployment | Supplies adapters, Compose topology, conformance tests, and process-level resilience fixtures | Qualification results for exact versions and topology; fault injection; backup/restore; failover; access-control review; sustained-load results |
| **Physical one-way boundary** | A software no-read-back interface cannot prove directionality against a compromised host | Defines the diode seam, transfer protocol, sequence checks, quarantine, and software emulator | Hardware-vendor evidence; independent installation inspection; reverse-channel and maintenance-path test; accreditation appropriate to the deployment |
| **Fairness, accessibility, and appeal quality** | Correct authority can still produce an unjust or inaccessible outcome | Preserves evidence and a manual/appeal path; makes no outcome-quality claim | Affected-community participation; accessibility testing; subgroup outcome analysis; appeal timeliness and correction-quality measures |
| **Cost, energy, and operational burden** | A technically bounded architecture may be unaffordable, carbon-intensive, or staff-intensive | Reports only narrow local performance measurements | Total-cost model; energy measurements; staffing and queue data; comparison against the current service and credible alternatives |
| **Independent security assurance** | Authors testing their own threat model cannot establish resistance to threats they missed | Publishes threat model, challenge corpus, property tests, model checking, and reproducible artifacts | Independent architecture review, penetration test/red team, remediation record, and—where needed—formal certification |
| **Educational effectiveness** | A well-designed lab is not evidence that participants learned or changed practice | Provides learning outcomes, exercises, and an assessment rubric | Pre/post protocol, cohort and denominator, scored artifacts, retention or transfer measure, limitations, and consent/privacy controls |
| **External adversary coverage** | An attack corpus written entirely by the project may share the authors' blind spots | Publishes a data-only contribution format and prints the external-contribution count | Reviewed external submissions from multiple domains, including failures the current design does not contain |

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
