# Security model, assumptions, and residual risk

**Claim.** Containment, not invulnerability. No single compromised file, model,
agent, user, or software layer should gain unchecked access, take a
consequential action, or erase the record without meeting an independent
control. Uncertainty in a required authorization control **fails secure**: the
automated action is denied and a defined manual path preserves service.

**Threat model.** Assumes hostile documents and a potentially compromised agent
process. Requires functioning enforcement services and protected administrative
credentials.

**Assurance profiles.** The included implementation has an in-memory teaching mode
and a distributed reference mode with Redis, Kafka, FastAPI, Spark, and Iceberg.
Its tests demonstrate specified software properties; the Compose smoke test also
exercises Redis persistence and Kafka publication. They do not establish production isolation,
comprehensive threat coverage, educational benefit, fairness, or certification.
The HMAC approval key included in source is intentionally public test material. It
demonstrates authenticated fields and trusted-key selection, not secret management,
non-repudiation, or production identity assurance.

**What is contained (see `tests/test_attacks.py`).**
- Prompt injection specimen - a recognizable malicious line is removed in the
  fixture; retrieved text is still treated as untrusted evidence; egress-capable
  tools are denied; the simulated diode exposes no outward method. Ordinary-language
  prompt injection is not assumed to be reliably detectable or removable.
- Poisoned data - lineage + snapshots let a poisoned state be identified and
  rolled back to the last approved snapshot.
- Hallucinated / wrong action - advice is separated from authority; consequential
  actions require a named human approver.
- Compromised model or update - signature-checked ingestion + quarantine; agents
  cannot self-escalate or edit policy.
- Insider record tampering - append-only hash chain makes silent edits detectable.
- Approval substitution and replay - a teaching-profile signature binds a human
  approval to the canonical proposal, evidence and case versions; altered fields,
  untrusted keys, expired payloads, and unallowlisted operations are denied. Retries
  create neither a second mutation nor duplicate intent and outcome evidence.
- Domain drift - a validated application profile constrains the executor to named
  operations and state transitions. An approved action outside that profile is denied.
- Outcome-evidence interruption - a completed mutation is reported as uncertain,
  retained in a pending-outcome store, and reconciled without a duplicate transition.
  Redis provides a durable reference store, but it is not transactionally coupled
  to an external target system.
- Inward import - authenticated source data is normalized and published to Kafka;
  invalid input is quarantined, and the gateway exposes no read-back HTTP route.

**Residual risks (not covered by structure alone).**
- Compromise of a shared host administrator, the signing authority, or multiple
  colluding control owners can defeat these assumptions.
- Separate containers on one host demonstrate logical separation, not
  independent administrative trust.
- A hardware data diode governs one link only; every other path (service ports,
  remote tools, removable media, wireless, power, staff) needs its own control.
- Tamper-evidence detects, it does not prevent; pair it with separation of
  duties and independent monitoring.
- Teaching mode loses in-memory state on restart. Distributed mode persists state in
  Redis, but production still needs HA, backup/restore tests, protected credentials,
  and a transactional relationship or reconciliation protocol with the real target.
- The demonstration `X-FSSAI-*` headers are spoofable. A production ingress must
  authenticate people and workloads and overwrite—not trust—caller-supplied headers.

**Standards alignment (not a claim of certification).** NIST SP 800-207
(zero trust), NIST AI 600-1 (GenAI profile), OWASP Top 10 for LLM Applications
and MITRE ATLAS (threats), ISO/IEC 42001 (management system).
