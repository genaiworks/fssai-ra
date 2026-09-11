# Security model, assumptions, and residual risk

**Claim.** Containment, not invulnerability. No single compromised file, model,
agent, user, or software layer should gain unchecked access, take a
consequential action, or erase the record without meeting an independent
control. Uncertainty in a required authorization control **fails secure**: the
automated action is denied and a defined manual path preserves service.

**Threat model.** Assumes hostile documents and a potentially compromised agent
process. Requires functioning enforcement services and protected administrative
credentials.

**Assurance profiles.** Three, and the deployment reports which one is active on
`/health`: an in-memory teaching mode; a durable mode on Redis where an
interrupted outcome is detected and reconciled; and a **single-transaction** mode
on PostgreSQL or SQLite where the mutation and its evidence commit together, so a
resource moving with no record of who moved it is unreachable rather than merely
detectable. Atomicity with a *foreign* system remains impossible; an external side
effect still needs the outbox, an idempotency key, and reconciliation.

Tests demonstrate specified software properties. They do not establish production
isolation, comprehensive threat coverage, educational benefit, fairness, or
certification. The HMAC approval key in source is intentionally public test
material: it demonstrates authenticated fields and trusted-key selection, not
secret management, non-repudiation, or production identity assurance. Running with
it active is reported as a **blocking** finding by `fssaira doctor`.

**Evidence of the controls' necessity.** Each declared control is ablated and the
harm measured; all 8 restore their harm when removed. The same seven attacks are
also put to an unguarded runtime and to a prompt-plus-allowlist baseline, which
contain 0% and 29% respectively — see `src/fssaira/experiment.py`. A control
nobody has shown to be load-bearing should not appear in a threat model.

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
- Approval substitution and replay - a signature binds a human approval to the
  canonical proposal, evidence and case versions; altered fields, untrusted keys,
  expired payloads, and unallowlisted operations are denied. Retries create neither
  a second mutation nor duplicate evidence. Note the distinction the bounded model
  checker forced: a *tampered* approval is caught by the signature, while a
  *genuine* approval pointed at the wrong proposal, executor, role, or time is
  caught by the digest, audience, role, and expiry checks behind it. Both classes
  are now exercised.
- Privilege downgrade - the action class of any call is read from the capability
  catalogue, never from the call. An agent that labels a consequential operation
  "reversible" is reclassified, still requires a named human, and the attempt is
  recorded as its own evidence.
- Runaway or looping agents - a call budget enforced by the policy, not the
  agent's own loop.
- Arguments carrying an outward destination on a tool not classed as egress. This
  is a cheap layer, not the control: a determined encoder can evade a regular
  expression.
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
- The `X-FSSAI-*` header adapter is spoofable and is now **refused** unless an
  operator explicitly declares an authenticating proxy
  (`FSSAI_TRUST_PROXY_HEADERS`). Bearer tokens are the default; OIDC is available.
  A production ingress must still authenticate people and workloads and
  overwrite—not trust—caller-supplied headers.
- Concurrency and distributed failure modes are not evaluated. The bounded model
  checker is single-threaded and states so in its own `bounds` field.
- Randomised property testing covers ~6,800 generated calls against the
  enforcement point. That is broader than a hand-written suite and is still not a
  proof.

**Independent verification.** Self-reported integrity is not integrity. The
evidence chain is re-verifiable by a separate process with separate credentials
(`jobs/verify_evidence_chain.py`), which recomputes every hash **and** checks for
sequence gaps — because a hash chain makes an edit obvious while a truncation is
only obvious if someone is counting.

**Standards alignment (not a claim of certification).** NIST SP 800-207
(zero trust), NIST AI 600-1 (GenAI profile), OWASP Top 10 for LLM Applications
and MITRE ATLAS (threats), ISO/IEC 42001 (management system).
