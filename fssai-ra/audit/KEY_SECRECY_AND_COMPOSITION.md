# Key secrecy and action/read composition — hardening pass

This note complements the pre-repair review in `ADVERSARIAL_REVIEW.md` and the
joined-workflow repairs. It records two further executed findings on the
*original* education path and an offline adaptive attacker with an independent
oracle. Every finding was executed against the real world on synthetic data and
judged from observed state, not denial messages. It does not restate A01–A06; it
adds what those did not cover.

## E1 — Rule 1 rested on a reconstructible signing key (fixed)

**Claim:** Rule 1 — a model may propose an action but cannot manufacture the
authority to execute it (paper §3.1; Fig 2 steps 6–7).

**Defect.** `AsymmetricApprovalAuthority` derived its default private key from
`sha256(key_id)`, and `key_id` is published alongside the public verification key;
`EducationWorld` additionally seeded the approval key from the constant
`b"approval-service"` baked into source. The threat model treats the model and
generated code — hence the repository source — as untrusted. So a party who read
the source, or merely knew the key id, could reconstruct the Ed25519 private key.

**Executed attack.** Reconstruct the key from `sha256(b"approval-service")`; sign
an approval for a wrong-student proposal (`stu-b7c2` MATH101 grade C→A) naming any
approver and role; call `world.execute`. **Result before fix: EXECUTED** — the
register moved `grade:C v1 → grade:A v2`, recorded in `register.write_log`, with a
signature the executor accepted as a valid human approval. This is distinct from
A03 (host isolation): here the *logical* signature check itself was defeated with
only public information, no OS-level bypass.

**Fix.** The default approval key is now random (`secrets.token_bytes(32)`), never
derivable from `key_id`; the education world generates a fresh approval key per
instance and the executor is handed only the matching public verification key.
The notary, publisher, and custody keys stay seeded because they are verification
keys that make the *evidence* reproducible, not the secret Rule 1 rests on.

**Regression:** `tests/test_composition_and_key_secrecy.py` forges from both the
old `b"approval-service"` seed and the `sha256(key_id)` seed and asserts refusal
(`APPROVAL_SIGNATURE_INVALID`), and asserts two worlds hold different keys.

**Residual.** Reproducible fixture keys are a property of the offline harness. In
deployment the private key must live in a signing service or HSM the model and
generated code cannot reach — a stated obligation the offline suite does not
verify.

## E2 — the earlier execution path did not recheck the read's live authority (fixed)

**Claim:** §3.5 — a proposal carries trusted references to the context it relied
on, and revocation of that context invalidates the approval (Fig 2 steps 7–8).

**Defect.** On the original `governed_request` execution path an approved grade
correction still executed after the grant behind its context read had been
revoked. The read path denied (`GRANT_REVOKED`) but the execution path bound only
the exact proposal, never the read's live authority. (The joined workflow, A06,
fixed the analogous gap on its own path; this closes it on the earlier path too.)

**Executed attack.** Grant → read → propose → registrar approves the exact
proposal → privacy officer revokes the grant → execute. **Result before fix:
EXECUTED** using a read authority that no longer existed.

**Fix.** `EducationWorld.execute` now calls `context_authority_live(grant)`, which
re-runs the disclosure gate's currency, consent, and scope checks over the grant
before the write and refuses with `CONTEXT_AUTHORITY_WITHDRAWN` if any now fails;
`governed_request` passes the context grant into `execute`.

**Regression:** `tests/test_composition_and_key_secrecy.py` (revoke,
consent-withdrawal, still-live happy path). Shown live as
`scripts/conference_demo.py --demo 10`; demo 11 exercises an authorized-but-wrong
decision reversed through an independent appeal, the point A05 raises.

## An offline adaptive attacker with an independent oracle

`src/fssaira/adaptive_attack.py` and `fssaira conference adaptive` add a
complement to the joined-workflow adaptive/Q-learning evaluation in `audit/`: an
attacker scored by an **independent effect oracle** (forbidden outcomes read from
world observations — what reached a model, what was released, whether the register
changed beyond a move's legitimate baseline — never denial logs), with three
tracks (static / random / epsilon-greedy **bandit search**, explicitly not a
trained neural policy) and a **positive control** that removes the execution
mediator to prove the attacker and oracle are not no-ops.

Result (budget 300/track, all controls on): static, random, and bandit each find
**0 forbidden outcomes**; the positive control drives the bandit to **300/300
unauthorized mutations**. Committed artifact `conference/evidence/adaptive-results.json`;
verify with `python scripts/adaptive_evidence.py --check`. A learning-based (the
joined-path tabular-Q attacker is the closest run) and a frontier-model attacker
remain future work; this bandit is below the state of the art for adaptive attacks
(paper refs [21], [22]).

## Reproduce

```
python -m pytest tests/test_composition_and_key_secrecy.py tests/test_adaptive_attack.py
fssaira conference adaptive --prove-attacker
python scripts/adaptive_evidence.py --check
python scripts/conference_demo.py --demo 10   # revoke-then-execute
python scripts/conference_demo.py --demo 11   # authorized-but-wrong + appeal
```
