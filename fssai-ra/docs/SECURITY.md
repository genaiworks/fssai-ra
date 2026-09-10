# Security model, assumptions, and residual risk

**Claim.** Containment, not invulnerability. No single compromised file, model,
agent, user, or software layer should gain unchecked access, take a
consequential action, or erase the record without meeting an independent
control. Uncertainty in a required authorization control **fails secure**: the
automated action is denied and a defined manual path preserves service.

**Threat model.** Assumes hostile documents and a potentially compromised agent
process. Requires functioning enforcement services and protected administrative
credentials.

**Assurance profile.** The included implementation is a teaching profile with
in-memory components and synthetic cases. Its tests demonstrate specified software
properties in that environment. They do not establish production isolation,
comprehensive threat coverage, educational benefit, fairness, or certification.

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
- Approval substitution and replay - a human approval is bound to the canonical
  proposal, evidence and case versions; altered or expired payloads are denied and
  retries do not create a second mutation.

**Residual risks (not covered by structure alone).**
- Compromise of a shared host administrator, the signing authority, or multiple
  colluding control owners can defeat these assumptions.
- Separate containers on one host demonstrate logical separation, not
  independent administrative trust.
- A hardware data diode governs one link only; every other path (service ports,
  remote tools, removable media, wireless, power, staff) needs its own control.
- Tamper-evidence detects, it does not prevent; pair it with separation of
  duties and independent monitoring.

**Standards alignment (not a claim of certification).** NIST SP 800-207
(zero trust), NIST AI 600-1 (GenAI profile), OWASP Top 10 for LLM Applications
and MITRE ATLAS (threats), ISO/IEC 42001 (management system).
