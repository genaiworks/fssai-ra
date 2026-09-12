# Process isolation, recovery and request identity

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Continue the engineering route → [`OPERATIONS.md`](OPERATIONS.md)

This is supplemental evidence on the current source tree. The published `v1.0.0`
tag and its baseline figures are unchanged. These additions are not included in
that tag. Use a reviewed commit containing this document for the enhanced code.

## Reproduce

From the Python project directory:

```bash
python -m pip install -e '.[dev]'
fssaira resilience profiles/student_support.yaml --callers 8 --output resilience.json
python scripts/check_resilience.py
pytest tests/test_resilience.py tests/test_request_identity.py
```

The command only creates synthetic records in temporary local SQLite databases.
It does not accept a production database URL. Each worker uses Python's `spawn`
process start method and opens an independent connection. No model, Docker,
external service or GPU is required after installation. Python scripts calling
`run_resilience` must use an `if __name__ == '__main__'` guard.

The committed [report](../evaluation/results/resilience-student-support.json)
contains a SHA-256 fingerprint of the tested source modules and effective
profile. `check_resilience.py` reruns the fixtures and compares the complete
report, including those fingerprints. A changed implementation requires review
before regenerating it with `--write`. The report is not a signed attestation.

## Observed fixtures

| Scenario | Observed result | Failure that would reject the run |
|---|---|---|
| Eight processes retry one approved request | One mutation, one receipt, seven replay responses | Duplicate mutation, missing response, duplicate evidence or conflicting receipt |
| Eight independently approved requests target version 1 | One mutation, seven version conflicts | Two mutations or evidence left by a rolled-back loser |
| Exit after intent append | No committed mutation, approval use or evidence; retry commits once | Partial durable record |
| Exit after mutation, before outcome | No committed mutation, approval use or evidence; retry commits once | A changed record without a complete transaction |
| Exit after outcome, before commit | No committed mutation, approval use or evidence; retry commits once | A partially committed transaction |
| Exit after commit, before returning a response | Complete record survives; retry returns the stored receipt | Duplicate mutation or a missing original outcome |

Crash workers call `os._exit(86)` at the named checkpoint, bypassing Python
cleanup and rollback handlers. The parent requires that exit code, reopens the
database, checks its state, and retries the original approval. The oracle checks
resource version, mutation count, approval-use count, stored receipt, intent and
outcome counts, proposal digest, evidence hashes, and absence of pending outcomes.
Negative tests alter individual oracle inputs to confirm that partial or duplicate
state cannot pass merely because the hash chain is valid.

Only the first declared transition is tested. Operation, states and approval role
come from the supplied profile. The template profile is also tested to catch
student-specific assumptions. Extend this harness with domain-specific transitions
and workloads before relying on it for another institution.

## Request identity is part of safe retry

A valid new approval is not permission to reuse a request ID for a different
proposal. Stored execution results now retain the canonical proposal digest.
Memory, SQLite and the Redis register check it before returning a replay:

- Identical proposal and a valid approval: return the original receipt.
- Same request ID with a different target, requester, evidence version or other
  proposal field: deny with `REQUEST_ID_CONFLICT`.
- Legacy receipt with no stored digest: deny with `REPLAY_IDENTITY_UNVERIFIABLE`.

SQLite stores the digest in the existing objects table in the same transaction
as the mutation and receipt. Redis stores it in the result written by its
WATCH/MULTI/EXEC transaction. Redis regression tests use fakeredis; they do not
qualify live Redis failover or the non-atomic evidence path.

### Upgrade and recovery warning

The new optional `proposal_digest` result field is an API response addition.
Clients validating exact response schemas should update them. Old SQLite and
Redis receipts are readable, but automated replay of a digest-less receipt is
blocked. Do not delete receipts, issue replacement request IDs, or reconstruct
the digest from incomplete fields to bypass this check. Pause the affected
workflow. An authorized operator must reconcile the original complete proposal,
receipt and external state under the institution's recovery procedure. Automated
backfill is deliberately not provided because historical evidence may be absent.

## Boundaries and outstanding qualification

These observations concern a single-host local SQLite WAL database. They do not
demonstrate power-loss durability, damaged storage recovery, replicated database
consistency, distributed linearizability, physical diode isolation, or service
availability under load. The clock and signing keys are teaching fixtures.

The PostgreSQL adapter uses a different locking mechanism. Its multi-writer
ledger behavior and serialization-failure handling require separate integration
tests. There is no implemented automatic serialization retry in the SQL module.
SQLite results must not be used to advertise PostgreSQL concurrency guarantees.

Email, payments, Kafka publication and foreign record systems remain outside
the local database transaction. They require their own idempotency, durable
outbox, reconciliation and failure tests. Kafka, PySpark, Iceberg and a physical
diode each need a deployment-specific acceptance suite. A correct authority
boundary also does not establish educational benefit, fair policy, effective
human review, accessibility, lower cost or lower energy use.
