# Domain packs: one security kernel, many governed-data contexts

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Choose a pack below, run `fssaira profiles`, then follow [`EXTENDING.md`](EXTENDING.md) to build and test your own.

FSSAI-RA is a secure **authority and data-governance kernel**, not an education
application. Education is one worked context. The reusable core controls who may
request an exact state change, who may authorize it, which evidence version was
reviewed, whether the resource changed meanwhile, whether a retry is a replay,
and which independently written records make the result reconstructable.

The kernel does not decide whether a corporate disclosure is wise, whether a
research use is ethical, or whether a healthcare purpose has a valid legal
basis. A domain pack supplies those facts and must carry its own evidence.

## Shipped domain packs

Run the inventory from the implementation directory:

```bash
fssaira profiles
fssaira profiles --verify --output /tmp/fssaira-domain-catalog.json
```

| Pack | Governed object | What it demonstrates | What it does not claim |
|---|---|---|---|
| [`student_support.yaml`](../profiles/student_support.yaml) | synthetic support case | simple two-state, one-role workflow | fairness, eligibility correctness, or handling of real student records |
| [`academic_record_correction.yaml`](../profiles/academic_record_correction.yaml) | synthetic academic record | multi-role workflow, appeal cycle, transfer test | institutional or legal adequacy |
| [`corporate_confidential_data.yaml`](../profiles/corporate_confidential_data.yaml) | dataset access/release request | classification, purpose-bound use, external release, revocation, legal hold | DLP, cloud IAM, records-law, or privacy compliance |
| [`financial_consumer_data.yaml`](../profiles/financial_consumer_data.yaml) | consumer credit request | credit-limit decisions, fraud holds, customer self-access, regulatory aggregates, bounded fraud break-glass | fair lending, credit reporting, adverse-action, or consumer-privacy compliance, or use of real customer data |
| [`government_benefits.yaml`](../profiles/government_benefits.yaml) | benefit eligibility case | eligibility, denial with appeal, retention-rule closure, statistical release, urgent-safeguarding break-glass, no sharing with enforcement | administrative-law, social-security, or public-sector data-protection compliance, or use of real applicant data |
| [`healthcare_record_access.yaml`](../profiles/healthcare_record_access.yaml) | health-record access request | treatment access, secondary-use review, revocation, break-glass review | diagnosis, treatment, clinical safety, HIPAA/GDPR compliance, or use of real patient data |

All six are teaching profiles over synthetic identifiers. The corporate, healthcare,
financial, and government packs broaden the implementation surface to the sectors
that hold the most sensitive consumer and citizen data; they are not deployment
evidence.

## What every pack declares

The executable `transitions` remain the allowlist enforced by the executor. The
`governance` block adds the context an adopter otherwise leaves implicit:

- `domain` and `purpose`: why this processing exists;
- `deployment_profile`: teaching, institutional pilot, or hardware-isolated;
- `data_classes`: the sensitivity categories present;
- `applicable_frameworks`: obligations to evaluate—not badges the code earns;
- `prohibited_uses`: purposes the pack explicitly refuses to authorize;
- `processing_basis`: the approved policy, consent, contract, duty, or other
  basis for processing;
- `data_minimization_rule`: the narrowest subjects, fields, recipients, purpose,
  and duration allowed;
- `retention_rule`, `deletion_rule`, and `residency_rule`: the declared lifecycle
  for source data, working copies, decisions, evidence, holds, and transfers;
- `incident_response`: containment, evidence preservation, notification,
  recovery, and service continuity;
- `owners`: separate data, privacy, and security accountability.

That metadata is returned by `/v1/profile`, included in the catalog, and
validated before startup. It does not replace the seven-field control contract.
A prohibited use still needs an enforcement point and a failure test wherever a
real interface could attempt it. The same is true of every lifecycle statement:
metadata makes an omission visible; only an adapter, policy engine, test, and
operational owner make the statement enforceable.

## Governing the read path

A pack may also declare a `disclosure` section. It names purposes, the class of
every field, the zone of every model endpoint, where each class may be processed,
recipients and their clearances, declassification rules, and emergency access.
The corporate, healthcare, financial, and government packs ship complete sections. The loader rejects a
section that references undeclared classes, purposes, or roles.

```bash
fssaira disclosure profiles/healthcare_record_access.yaml
fssaira disclosure profiles/corporate_confidential_data.yaml
fssaira disclosure profiles/financial_consumer_data.yaml
fssaira disclosure profiles/government_benefits.yaml
```

The suite is generated from the pack itself, so a new pack receives the same
hostile flows, per-check ablations, and bounded model check. See
[`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md).

The healthcare pack previously declared a break-glass review transition that no
transition could reach. It now declares `declare_break_glass_access`, and
`tests/test_disclosure.py` checks that every status in every pack is reachable.

## The sector-independent architecture

| Duty | Small/offline implementation | Distributed seam | Invariant that must survive replacement |
|---|---|---|---|
| Controlled import | signed validation + software one-way channel | gateway, Kafka, certified diode seam | rejected content is not delivered; accepted content leaves intent/outcome evidence; no read-back route |
| Governed state | memory or SQLite resource register | PostgreSQL or an institutional system of record | exact operation, resource, prior state, version, and request identity are checked atomically where possible |
| Fast coordination | in-process object store | Redis alternative profile | replay and first-writer bindings cannot be overwritten |
| Model reasoning | deterministic fixture or local model | institution-operated model endpoint | model output is a proposal; retrieved data never grants authority |
| Reproducible data | lineage hashes and snapshots | Kafka → PySpark → Apache Iceberg | source offsets de-duplicate, transformations are attributable, reviewed snapshots remain recoverable |
| Consequential action | signed exact-action approval | separately governed approval/execution services | requester, primary reviewer, second reviewer, role, digest, audience, expiry, and current resource state are rechecked |
| Assurance | tests, ablations, bounded verification | deployment qualification and independent review | claims name their environment, denominator, limitations, and unresolved evidence |

## Corporate confidential-data use

The corporate pack governs **authorization state around a dataset**, not the
bytes themselves. An enterprise adapter would connect `authorize_internal_use`,
`authorize_external_release`, revocation, and legal-hold transitions to real IAM,
DLP, catalog, and records systems. The adapter must preserve exact recipient,
purpose, dataset, fields, duration, and version in the proposal digest. A generic
“approved for sharing” status is too broad for production.

Required domain tests include cross-tenant access, purpose substitution, field
and recipient changes after review, bulk export through indirect tools, legal
hold bypass, stale classification, revoked access, and privileged administrator
bypass. The reference profile demonstrates none of those real integrations.

## Financial consumer-data use

The financial pack governs **credit-limit decisions and fraud operations**. An AI
assistant may read identity, balance, income, and credit-bureau fields for a credit
decision, but transaction history and fraud signals are reserved for fraud
investigation. Customer data never reaches a marketing partner, and regulatory
reporting receives only aggregates approved by the compliance officer. Emergency
fraud access is bounded to thirty minutes and must be reviewed.

Required domain tests include adverse decisions without a named officer and
reasons, protected-characteristic proxies, purpose substitution between servicing,
credit, and marketing, cross-customer access, stale bureau data, and fraud holds
that are never released or reviewed.

## Government benefits use

The government pack governs **eligibility, denial, appeal, and case closure**. A
denial cannot be automated: a named benefit approver decides, an appeals clerk can
reopen it, and an independent appeals officer decides again. Immigration status is
visible to the applicant but not to eligibility or appeals officers, and nothing is
releasable to an enforcement agency. Official statistics receive only aggregates
approved by the data protection officer. Urgent safeguarding access is bounded and
reviewed by the data protection officer.

Required domain tests include automated denial, sharing with enforcement or
immigration functions, profiling on protected characteristics, appeal decided by
the original decision maker, and retention-rule closure without data-protection
approval.

## Healthcare record-access use

The healthcare pack is intentionally limited to **access and disclosure
governance**. It prohibits diagnosis, treatment recommendation, triage,
prescribing, and clinical-record alteration. A healthcare deployment must add
jurisdiction-specific privacy, consent, minimum-necessary, research-review,
patient-access, emergency-access, audit-retention, and clinical-safety controls.

Required domain tests include wrong-patient and wrong-tenant access, purpose and
legal-basis substitution, excessive fields or duration, research access without
the required review, concealed break-glass use, revocation races, downstream
copying, and patient correction/appeal handling. Use synthetic data until the
institution has approved the complete pilot evidence bundle.

## Build another pack

```bash
fssaira init domains/my-domain \
  --domain-id my-domain \
  --title "My Governed Data Workflow" \
  --owner accountable_service_owner \
  --resource governed_request

fssaira validate-profile domains/my-domain/profile.yaml
fssaira validate-contract domains/my-domain
fssaira coverage --dir domains/my-domain
fssaira verify domains/my-domain/profile.yaml
fssaira evaluate domains/my-domain/profile.yaml
pytest domains/my-domain
```

The generated attack test fails on purpose. Replace it with the real misuse
case before describing the pack as implemented. Then add a benign case, an
adapter conformance run, recovery evidence, and a limitation statement. The
framework generalizes by preserving invariants and regenerating evidence—not by
copying the headline numbers from another domain.
