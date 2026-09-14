# Planes, mediators, and trust boundaries

## Where power and data can go

```text
                 ┌──────────────────────────────────────────────┐
                 │  UNTRUSTED: models · agents · router · tools  │
                 │  local or cloud, honest or malicious          │
                 └───────────┬──────────────────────┬───────────┘
                    request  │                      │  proposal
               (names fields,│                      │(names one exact
                  purpose)   │                      │  transition)
   ══════════════════════════╪══════ TRUST BOUNDARY ╪═══════════════════════
                 ┌───────────▼───────────┐  ┌───────▼────────────────┐
                 │     CONTEXT GATE      │  │   EXECUTION MEDIATOR    │
                 │  data mediator        │  │   power mediator        │
                 │  grant · purpose ·    │  │   Ed25519 approval ·    │
                 │  consent · residency ·│  │   exact digest · role · │
                 │  attestation · tokens │  │   version · single use  │
                 │  holds: decrypt cred. │  │   holds: write cred.    │
                 └───────────┬───────────┘  └───────┬────────────────┘
               tokens, labels│                      │ one write, one receipt
                 ┌───────────▼──────────────────────▼────────────────┐
                 │  INSTITUTION: encrypted records · register ·       │
                 │  key custody · signed evidence · human review      │
                 └────────────────────────────────────────────────────┘
```

Neither mediator trusts the other or the model. The model holds no credential for either.

## The seven planes, as implemented

| Plane | Responsibility | Implementation | Adversarial evidence |
|---|---|---|---|
| Boundary | authenticate sources, carry injected text as data | `EducationWorld.admit_document`, `import_boundary.py` | F12, F25 |
| Data | encrypted records, stable surrogate IDs, snapshots, erasure | `key_custody.py`, `encrypted_records.py` | erasure verification, custody tests |
| Intelligence | models, router, retrieval — no credentials | `education_models.py`, `semantic_router.py` | F10, F11, F18 |
| Authority | grants, approvals, delegation, purpose, expiry, revocation | `disclosure.py` grants, `exact_action.py` approvals, `grant_delegation.py`, `delegation.py` | F06–F09, F19 |
| Execution | recheck everything, one write | `exact_action.AccountableExecutor`, `CredentialedRegister` | F01, F13, F14, F20, F21 |
| Evidence | intent before outcome, signed checkpoints and receipts | `evidence.py`, `evidence_notary.py` | F15 |
| Resilience | fail closed, reconcile, revoke, manual fallback, bounded review | `review_queue.py`, `resilience.py`, trace step 10 | F17, F23, stateful P4/P5 |

## The ten-step governed request

`fssaira conference trace` prints a real run; `conference/evidence/lifecycle-traces.json` holds five.

```text
 1 ADMIT      boundary          caller known? source signed? injection carried as text
 2 PROTECT    data              fields classified; records AES-GCM under per-student keys
 3 ROUTE      intelligence      router suggests an endpoint (advisory only)
 4 ENTITLE    context gate      model attested for purpose and classes; grant covers request; tokens out
 5 REASON     intelligence      model proposes over tokens (untrusted)
 6 AUTHORIZE  authority         named human with the right role approves the exact digest
 7 EXECUTE    execution         executor rechecks signature, digest, role, version, single use; writes once
 8 RELEASE    release gate      recipient dominates label; identity restored only if entitled
 9 RECORD     evidence          checkpoint signed; no identity values in evidence
10 RECOVER    resilience        revoke and confirm refusal, or fail closed to the manual fallback
```

## The privacy pipeline

```text
raw record → classification → authorization → decryption under custody → tokenization
  → minimum necessary → attested model → labelled output (identity re-tokenized)
  → release authorization → identity restoration (entitled recipients only)
```

## The seven-field control contract

Every consequential capability in the education pack declares protected asset, permitted
operation, enforcement point (one of the kernel's mediators), accountable owner, failure test
(a test that must exist), evidence artifact, and failure response (which must not fail open).
`pack_floor.check_pack` refuses to load a pack where any field is missing, the enforcement
point is not a mediator, the test does not exist, or the response continues on failure.
