# Empirical supplement: recovery and replay identity

This supplement records work after the fixed v1.0.0 baseline cited in the extended
abstract. It supports discussion and a future full paper. It is not an additional
field to paste into the conference form, and it does not change the denominators
of the earlier containment experiment.

## Research question

When an independently authorized action races another request, or the executor
process exits abruptly around commit, does the institution retain an attributable,
single state transition and a safe retry path?

## Method

The executable artifact uses synthetic records in a local SQLite WAL database.
Two process races use eight spawned workers, each opening its own database
connection. The duplicate-request race repeats one proposal and approval. The
competing-version race uses distinct approved request IDs against the same target
at version one. A barrier releases the callers together, without claiming to
enumerate every scheduler interleaving.

Four additional workers exit via `os._exit` after intent append, after register
mutation, after outcome append, or after database commit. This bypasses application
cleanup. A parent process reopens the database, inspects committed state, and
retries the original request. A passing observation requires the expected process
exit as well as the expected database state. The oracle checks mutations, receipt
identity, evidence pairing and hashes, resource version, approval uses and outbox
state. Regression tests deliberately corrupt oracle inputs to check rejection.

## Results

The duplicate-request race returned eight results representing one mutation and
one receipt, with seven replay responses. The competing-version race committed
one mutation and rejected seven stale requests without leaving their intent or
approval-use records committed. All four abrupt-exit fixtures recovered the
expected all-or-nothing state. Retrying after the pre-commit exits committed
once; retrying after the post-commit exit returned the existing receipt.

Review of the retry path also revealed a request-identity weakness: a previously
used request ID could retrieve an earlier result without checking that it belonged
to the same complete proposal. The revised implementation stores the canonical
proposal digest with each result and denies conflicting reuse, even with a fresh,
valid approval. Tests cover changed targets, evidence versions, requesters and
reviewed resource versions in memory, SQLite and a Redis fixture. Historical
receipts lacking this binding require explicit reconciliation.

## Interpretation and validity

The new evidence strengthens the claim about one local transactional executor.
It is not a measured security probability, an evaluation of model susceptibility
to prompt injection, or a distributed consistency proof. Abrupt process exit does
not simulate loss of power, disk corruption or failure of the whole host. The
PostgreSQL adapter and live Redis require their own concurrency and recovery
qualification. External effects remain outside the SQLite transaction.

The fixture exercises the first transition in a supplied domain profile. It also
runs against the generic template to check portability of the mechanism, but it
does not validate all institutional policies. Both fixture design and analysis
come from the artifact's authors. Independent reproduction, adversarial workload
design and education-domain review remain important threats-to-validity remedies.

No learner outcomes, appeal-resolution times, reviewer burden, accessibility
benefits, energy savings or cost advantages are inferred from these tests. A
stronger education paper should evaluate those separately with an approved study
protocol, appropriate participant protections, declared baselines and uncertainty.

## Artifact provenance

Reproduce with `python scripts/check_resilience.py` from the Python project
directory. The [committed report](../evaluation/results/resilience-student-support.json)
fingerprints the tested modules and effective profile. Publish the report with the
exact source commit used for any cited run. Keep the [v1.0.0 baseline](../evaluation/results/v1.0.0-summary.json)
separate from this supplement. The [recovery guide](../docs/RESILIENCE.md) documents
the cases, upgrade caveat and qualification limits.
