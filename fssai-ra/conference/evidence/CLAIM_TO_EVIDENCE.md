# Claim-to-Evidence Register (Third Audit)

Each significant claim in "Trust by Construction" is mapped to the implementation
that realizes it, the executed experiment or command that tests it, the resulting
artifact, the assumptions the claim rests on, and an honest status. Status values:

- **verified-in-fixture** — demonstrated by an executed experiment on synthetic
  data under stated assumptions;
- **implemented-but-partially-tested** — mechanism exists and is exercised, but
  coverage does not span all backends/conditions;
- **proposed-mechanism** — specified and implemented as a design, not empirically
  validated for the strong reading;
- **open-empirical-question** — the strong claim requires evidence not yet
  gathered.

Statuses are kept consistent with the paper's own hedges. Where the paper states a
qualification (for example anonymity, complete copy inventory, external witness,
or exactly-once), the qualification is reproduced here.

| Claim | Where in the paper | Implementation module(s) | Executed experiment / command | Result artifact | Assumptions | Status |
|-------|--------------------|--------------------------|-------------------------------|-----------------|-------------|--------|
| Rule 1: exact-proposal approval — approval binds to the precise proposal digest; a different proposal is refused. | §3.1; Fig 2 steps 6–7 | `governed_request.py`, `authority_stateful.py` | `python -m pytest tests/test_composition_and_key_secrecy.py`; falsifier suite | `tests/test_composition_and_key_secrecy.py`; `conference/evidence/redteam-results.json` (`APPROVAL_PAYLOAD_MISMATCH`) | Executor is intact; approval verifier holds the correct public key. | verified-in-fixture |
| Rule 1: key secrecy (E1) — the approval private key is not derivable from source or from the public `key_id`; forged approvals are rejected. | §3.1; Fig 2 steps 6–7 | `authority_stateful.py` (random `secrets.token_bytes(32)`), `education_world.py` (fresh per-instance key) | `python -m pytest tests/test_composition_and_key_secrecy.py` (forges from `b"approval-service"` and `sha256(key_id)` seeds) | `tests/test_composition_and_key_secrecy.py`; register unchanged; `APPROVAL_SIGNATURE_INVALID` | Reproducible fixture keys are a harness property; in deployment the private key lives in a signing service/HSM the model cannot reach. | verified-in-fixture (deployment key custody: open-empirical-question) |
| Rule 2: disclosure gate — 14 checks over currency, consent, scope, purpose, recipient, and minimization. | §3.2 / §3.5 | `privacy_vault.py`, disclosure runtime | `fssaira conference` suites; falsifier attempts | `conference/evidence/data-flow-results.json`; `conformance-matrix.json` | Gate mediates explicit outputs only. | verified-in-fixture (explicit flows only) |
| Action/read composition (E2) — an approved action is refused if the context read's authority was revoked or consent withdrawn before execution. | §3.5; Fig 2 steps 7–8 | `education_world.py` (`context_authority_live`), `governed_request.py` | `python -m pytest tests/test_composition_and_key_secrecy.py`; `python scripts/conference_demo.py --demo 10` (and `--demo 11`) | `tests/test_composition_and_key_secrecy.py`; `CONTEXT_AUTHORITY_WITHDRAWN`; register `mutation_count` unchanged | Recheck is enforced in the education/action path; not proven on every backend. | implemented-but-partially-tested |
| Tokenization / identity-not-in-clear — student identity values do not appear in the model context or in evidence in clear form. | §4 (privacy) | `privacy_vault.py` | RECORD-step assertions in falsifier and evidence suites | `conference/evidence/data-flow-results.json` | This is pseudonymization/access control, **not anonymity**; quasi-identifiers and rare attributes can still re-identify (Sweeney; Narayanan–Shmatikov; Dwork). | verified-in-fixture (qualified: not anonymity) |
| Envelope encryption at rest — governed data is encrypted with per-record data keys under a wrapping key. | §4 (privacy) | `privacy_vault.py` | privacy/custody tests | `tests/test_privacy_custody.py` | Key-management assumptions per NIST SP 800-57. | implemented-but-partially-tested |
| Cryptographic erasure — destroying the key renders governed copies unrecoverable. | §4 (privacy) | `privacy_vault.py` | privacy/custody tests | `tests/test_privacy_custody.py` | Applies to **governed copies only**, not a complete copy inventory; erasure completeness depends on knowing every copy (NIST SP 800-88r2). | verified-in-fixture (qualified: governed copies only) |
| Evidence hash-chain tamper-evidence — the evidence ledger is an append-only hash chain that detects tampering. | §5 (evidence) | evidence store, `falsification.py` | evidence/security suites | `conference/evidence/security-results.json`; `lifecycle-traces.json` | **Detects, does not prevent**; tamper-evidence is relative to a trusted anchor and needs an **external witness** (Certificate Transparency; Crosby–Wallach). | verified-in-fixture (qualified: detects not prevents; external witness needed) |
| Delegation only narrows — a delegated authority can restrict but never escalate subjects, fields, or purpose. | §3.4 (delegation) | `authority_stateful.py`, delegation model | delegation model checker; falsifiers | `conference/evidence/delegation-results.json` (`DELEGATION_SUBJECTS_ESCALATION`, `DELEGATION_FIELDS_ESCALATION`) | Rootedness invariant asserted at depth 0 (empty chain is the root principal acting directly). | verified-in-fixture |
| Bounded model checking — exhaustive check of the reference profile over a bounded state space (240 states). | §7 (evidence) | delegation/composition model checker | model-checking run in the conference suite | `conference/evidence/` model-checking artifacts | Bounded scope; invariants only as stated. | verified-in-fixture (bounded) |
| Ablation is load-bearing — removing any single control produces at least one forbidden outcome. | §7 (evidence) | ablation harness | ablation run | `conference/evidence/ablation-results.json` | Ablation over the modeled controls and move space. | verified-in-fixture |
| Falsifier attempts — 104,997 adversarial attempts run, all refused or without forbidden effect. | §7 (evidence) | `falsification.py`, `redteam.py` | falsifier suite | `conference/evidence/redteam-results.json`; `summary.json` | Attempts are self-built; not an external benchmark (cf. AgentDojo, InjecAgent). | verified-in-fixture |
| Adaptive attacker — offline static/random/bandit search finds 0 forbidden outcomes with controls on; a mediator-removed positive control yields 300/300. | §7 (evidence) | `adaptive_attack.py`, `redteam.py` | `fssaira conference adaptive --prove-attacker`; `python scripts/adaptive_evidence.py` | `conference/evidence/adaptive-results.json` | Offline search, budget 300/track; independent observation-based oracle; **RL / frontier-model / live-Ollama attacker NOT RUN**; bandit is below the state of the art (Zhan; Nasr). | verified-in-fixture (search only); RL/frontier: open-empirical-question |
| Review-capacity simulation — approval-review throughput/latency under declared load. | §6 (review capacity) | review-capacity harness | review simulation | `conference/evidence/review-results.json` | **Declared parameters, not a human study**; does not model automation bias (Skitka; Goddard). | proposed-mechanism (declared parameters) |
| Cross-sector transfer — the same kernel and controls transfer across sectors (education reference world). | §2 / §8 (transfer) | `education_world.py` and the shared kernel | conference suites over the education world | `conference/evidence/summary.json`; `conformance-matrix.json` | Demonstrated on the education reference world; transfer is the claimed contribution, evidenced on one instantiated sector. | implemented-but-partially-tested |
| Distributed exactly-once — a dispatched external effect takes effect once. | §3.3 (failure states) | pending-outcome / idempotency logic | concurrency/resilience suites; `python scripts/check_resilience.py` | `conference/evidence/concurrency-results.json`; `resilience-student-support.json` | Guaranteed exactly-once is impossible over unreliable channels (Akkoyunlu; FLP); the honest reading is **effectively-once via idempotency keys** (Helland). The in-memory outcome store is non-durable. | proposed-mechanism (qualified: effectively-once) |

## Notes on honest status

- No row claims containment of an arbitrary model. Every "verified-in-fixture"
  status is conditioned on an intact trusted base (executor, gate, evidence store,
  key custody) and on the model being unable to reach it.
- Qualifications reproduced above (not anonymity; governed copies only; detects
  not prevents; declared parameters; effectively-once; RL/frontier attacker not
  run) match the paper's own hedges and the residual-risk register in
  `conference/limitations/RESIDUAL_RISKS.md`.
- The paper's Table 4 gap-closure obligations remain the stop conditions for
  upgrading the qualified and partially-tested statuses.
