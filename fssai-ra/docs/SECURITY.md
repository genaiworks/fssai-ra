# Security model, assumptions, and residual risk

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Policy leader → [`ASSURANCE.md`](ASSURANCE.md) · engineer → [`DIODE_DEPLOYMENT.md`](DIODE_DEPLOYMENT.md)

**Claim.** Containment, not invulnerability. No single compromised file, model,
agent, user, or software layer should gain unchecked access, take a
consequential action, or erase the record without meeting an independent
control. Uncertainty in a required authorization control **fails secure**: the
automated action is denied and a defined manual path preserves service.

**Threat model.** Assumes hostile documents and a potentially compromised agent
process. Requires functioning enforcement services and protected administrative
credentials.

Two assumptions that earlier versions made silently are now named, because both
are false in an ordinary 2026 deployment and each is its own risk class. First,
**an agent does not act alone**: it delegates to sub-agents and calls tool
servers nobody here wrote, so authority composes across hops that are each
individually correct. Second, **the reviewer is not necessarily unaided**: once a
model helps them decide, the deliberation floor that stood behind substantively
wrong proposals is calibrated for an activity the reviewer is no longer doing.
Neither is a model failure. A perfectly aligned model at every hop produces both.

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
- Delegated-authority composition (see `tests/test_delegation.py`) - a chain is
  verified from an institutional root grant downward on every call, and confers
  the *intersection* of every grant along it rather than the last hop's
  declaration. Contained: a hop widening its delegator's scope; a chain
  descending from no institutional grant; a principal appearing twice and
  laundering a scope back to itself; a delegation outliving the grant it
  descends from; a chain longer than the declared depth; consequential authority
  passed onward by a machine; a hop signed by an untrusted key; a sibling's chain
  presented as one's own; and work done for another principal executing under the
  actor's wider grant. Nine invariants, all load-bearing under ablation, 768
  enumerated chain shapes with zero violations.
- Bearer reuse of an authority chain - a chain authorises the principal it names
  and no other. This one is listed because the checker **did not** contain it on
  its first run: every invariant held on a chain that simply was not the
  requester's. An authority object bound to nobody is a bearer token.
- Undisclosed beneficiary - an actor that will not name whose work it is doing is
  refused rather than resolved in its own favour.
- Review assistance that is not independent of the proposer (see
  `tests/test_assisted_review.py`) - refused at **configuration** time, not at
  runtime, because at runtime a dependent assistant and an independent one are
  indistinguishable: same reviewer identity, same interval, same signature, same
  evidence. A deployment lowering its deliberation floor while declaring an
  assistant that shares the proposer's model and evidence path does not start.

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
- The reference API provides coarse role checks, not domain-specific row-level
  authorization. An institutional adapter must enforce tenant, assignment,
  cohort, and purpose-of-use policy before exposing real records; authentication
  alone is not permission to inspect every resource or evidence entry.
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
- **Revocation propagation is out of scope.** The chain verifier refuses a
  delegation that outlives its delegator's grant and refuses an expired
  ancestor, both checked at use time. It does not push a revocation to
  already-issued descendants, and nothing here bounds the window between
  revoking a grant and the last descendant failing to use it.
- Key compromise at an intermediate hop defeats chain provenance exactly as
  compromise of the approval signing authority defeats exact-action approval. The
  delegation signatures are HMAC over published demonstration key material and
  are subject to the same `XC-2` custody requirement as everything else.
- Delegation bounds **authority**, never competence or intent. A fully
  attenuated, correctly rooted, authentically signed chain can still carry a
  substantively wrong action; that class is the oversight controls' problem and
  is bounded rather than removed.
- **No real multi-agent deployment was observed.** The delegation results are
  constructed chains in a declared environment, on the same footing as every
  other fixture observation here.
- **The proposer/assistant error correlation is a declared parameter.** No model
  was evaluated, no assistant was measured, and no rate is claimed for any named
  system. An institution that declares a lower correlation than ours buys more
  throughput on its own authority, and the arithmetic is the same.
- Independence of review assistance is *declared*, not verified. Nothing here
  inspects which model a deployment actually calls; the control refuses a
  configuration, and the declaration itself is an `XC`-class attestation.

**Independent verification.** Self-reported integrity is not integrity. The
evidence chain is re-verifiable by a separate process with separate credentials
(`jobs/verify_evidence_chain.py`), which recomputes every hash **and** checks for
sequence gaps — because a hash chain makes an edit obvious while a truncation is
only obvious if someone is counting.

**Standards alignment (not a claim of certification).** NIST SP 800-207
(zero trust), NIST AI 600-1 (GenAI profile), OWASP Top 10 for LLM Applications
and MITRE ATLAS (threats), ISO/IEC 42001 (management system).
