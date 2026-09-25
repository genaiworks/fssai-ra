# Scale tiers: small data and big data

> **Documentation navigation:** [Documentation map](README.md) · [Deployment](DEPLOYMENT.md) · [Pipeline walkthrough](PIPELINE_WALKTHROUGH.md) · [Operations](OPERATIONS.md)
>
> **Recommended next:** Run `fssaira scale advise` with your own workload, then `make small-up` or `make big-up`.

The platform ships in two sizes. Both run the same decision plane, so every
control, refusal and approval rule behaves the same in each. They differ only in
the evidence plane: how imports arrive, how evidence is archived, and how the
archive is independently re-verified.

Kafka, Spark and Iceberg are the right tools when data outgrows one machine.
For a school, a department, or a pilot with a few thousand records a day, they
add more to run and secure than the data needs. So the small tier replaces them
with SQLite files and the standard library, and keeps the same guarantees.

## Which tier?

Ask the tool, with your own numbers:

```bash
fssaira scale advise --records-per-day 5000 --peak-writes-per-second 2
fssaira scale measure          # what this host's disk actually sustains
```

`advise` recommends **small** unless one of these is true:

| Need | Small-tier limit (default) | Why the big-data tier helps |
|---|---|---|
| Peak authoritative writes | 50 per second | SQLite serialises writers on one host; Postgres and Kafka partitions spread them |
| Records per day | 500,000 | Full-chain re-verification becomes a batch job; Spark parallelises it |
| Archive kept online | 50 GB | Iceberg on object storage handles snapshots, retention and time travel at size |
| Independent consumers of the event stream | 1 | Several systems replaying one ordered log at their own pace is what Kafka is for |
| Hosts that accept writes | 1 | SQLite has one writer host |
| Survive losing a host | no | Replicated Kafka and Postgres survive a host loss; one SQLite file does not |

The limits are deliberately far below what a single SSD sustains. On the
development laptop, `fssaira scale measure` recorded about 12,000 durable
evidence appends per second, over 200 times the peak limit. That figure is from
macOS, where SQLite's `fsync` does not flush the drive cache, so it overstates
durable throughput; the command prints that caveat. Measure your own host.

## What each tier runs

| Job | Big-data tier | Small-data tier |
|---|---|---|
| State, ledger, approvals | PostgreSQL | SQLite (`FSSAI_DATABASE_URL=sqlite:///…`), same single-transaction path |
| Lifecycle events | SQL outbox, relayed to Kafka | SQL outbox, kept locally |
| Inward imports | Kafka topic `fssaira.imports` | SQLite import log (`FSSAI_IMPORT_LOG_PATH`) |
| Import sink | Spark Structured Streaming (`jobs/kafka_to_iceberg.py`) | `fssaira small ingest` |
| Evidence archive | Iceberg on MinIO | SQLite archive file on its own volume |
| Archiver | `archive_evidence` | `archive_evidence`, the same function |
| Independent verifier | Spark (`jobs/verify_evidence_chain.py`) | `fssaira small verify`, the same `verify_rows` |
| Compose file | `deploy/compose.yaml --profile analytics` | `deploy/compose.small.yaml` |
| Services (without the model) | 11, two of them one-shot setup | 4: API, gateway, evidence worker, console |

## Measured cost of each tier

`scripts/measure_tiers.py` starts each stack as a throwaway Compose project, runs
the same complete workflows through the HTTP API (register, propose, review,
wait out the enforced 45-second deliberation floor, approve, execute), checks
the same invariants, then samples the footprint. One run on the development
laptop (Apple silicon, 14 CPUs, Docker 28.4), ten workflows per tier, recorded in
`audit/tier-footprint.json`:

| | Small | Big (with analytics) |
|---|---:|---:|
| Seconds from `up` to a healthy API | 6.1 | 16.9 |
| Running containers | 3 | 8 |
| Resident memory after the workload | 86 MiB | 1,087 MiB |
| Images on disk | 283 MiB | 3.0 GiB |
| Median workflow time beyond the review floor | 0.53 s | 0.70 s |
| Every workflow completed, moved once, one outcome each, chain valid | yes | yes |

The big stack uses about 12.6 times the memory and 10.6 times the image
storage for the same workload and the same invariants. The small tier's
evidence worker also archived and independently verified all 20 ledger records
(`INTACT`). The big tier's Spark archive job was running but not driven. These
figures are relative cost on one machine, not capacity; rerun the script on
your own host.

## What stays the same

These are not reimplemented in the small tier. They are the same code or the
same rule:

- The gateway signs every inward record with `FSSAI_IMPORT_ENVELOPE_KEY`. The
  sink quarantines a missing or wrong MAC by position and hash, never storing
  the content, and carries on with the next record.
- A record whose `content_hash` does not match its text fails the batch, and
  nothing is committed.
- Re-running the sink is idempotent. A different record at a stored position is
  refused, a truncated log or a record deleted before import stops the sink
  (as Spark's `failOnDataLoss` does), and a recreated log is a new generation.
- Archiving goes through `fssaira.iceberg_backend.archive_evidence`, with its
  `ARCHIVE_AHEAD_OF_LEDGER` and `ARCHIVE_DIVERGED` refusals.
- Verification goes through `fssaira.chain_verification.verify_rows`, including
  the signed-checkpoint check that detects a deleted tail.

`tests/test_small_data.py` checks each of these on the small tier.
`tests/test_tier_equivalence.py` runs the same attacks against a real Iceberg
table and the SQLite archive and requires identical verdicts; CI runs it with
pyiceberg installed and fails if the Iceberg half is skipped. The one
difference it records: two archivers racing on one ledger can both append in
Iceberg, where the verifier reports the duplicate, while SQLite's primary key
refuses the second copy at write time.

## How a pass scales with history

A pass does work in proportion to what is new, not to the whole history:

- **Archiving** reads only the records after the archived head, 50,000 at a
  time, and checks that they chain from that head and recompute. The records
  before the head are already in the archive, where the verifier checks them.
- **Verification** (`--mode auto`, the default) recomputes the whole archive on
  every pass while it holds at most 1,000,000 records, so tampering anywhere is
  caught on the next pass. Above that, a pass first confirms that the last
  verified record is still archived with the same hash, then checks only the
  records after it. A full recomputation still runs at least once a day.

Measured on the development laptop with `scripts/measure_verification.py`
(recorded in `audit/verification-throughput.json`): a full pass recomputes about
195,000 records a second (1,000,000 in about five seconds), and an incremental
pass over 100 new records takes under a millisecond.

An incremental pass cannot see an already-verified record rewritten in place
together with every later hash. The daily full pass sees it, and so does a
signed checkpoint. `tests/test_small_data.py::test_what_only_the_full_pass_sees`
pins that boundary. Someone able to do that can equally rewrite the whole
archive consistently, which in either tier only a checkpoint held elsewhere
detects.

## What the small tier gives up

- **One writer host, no replication.** Back up the SQLite files (for example with
  `sqlite3 control.sqlite3 ".backup …"`) on a schedule your recovery objective
  allows.
- **No shared event stream.** Other systems cannot subscribe to lifecycle events.
  If one needs to, set `FSSAI_KAFKA_BOOTSTRAP`: the outbox relays to it with no
  other change.
- **Snapshot history, not engine-level time travel.** Every archive commit is
  recorded in `archive_snapshots` with its manifest, so a decision can still be
  bound to the archive state it saw.

## Running the small tier

```bash
make small-up        # or: docker compose --env-file deploy/.env -f deploy/compose.small.yaml up -d
```

The evidence worker has no network. It reads the control database and the
import log from their volumes and writes only the archive, every
`FSSAI_SMALL_INTERVAL_SECONDS` (default 60). Any verdict other than `INTACT` or
`EMPTY` is printed as `EVIDENCE VERIFICATION FAILED`.

Without Docker, the same pass runs from cron:

```bash
fssaira small run --archive /srv/archive/evidence.sqlite3 \
    --log /srv/low-side/import-log.sqlite3 \
    --database sqlite:////srv/control/control.sqlite3 \
    --checkpoint checkpoint.json --public-keys notary-keys.json
```

**Keep the archive apart.** Put the archive file on storage administered by
someone other than the operator of the control plane. An archive the same
account can rewrite detects accidents, not an administrator. That is equally
true of the Iceberg archive in the big tier.

## Declaring the tier

Set `FSSAI_SCALE=small` or `FSSAI_SCALE=big`. `/health`, `fssaira doctor` and
`readiness()` then report configurations that contradict the declaration:

| Code | Severity | Meaning |
|---|---|---|
| `BROKER_IN_SMALL_TIER` | info | small declared, Kafka still configured |
| `REDIS_IN_SMALL_TIER` | info | small declared, state in Redis rather than SQLite |
| `BIG_TIER_WITHOUT_BROKER` | medium | big declared, no Kafka |
| `BIG_TIER_ON_SQLITE` | medium | big declared, state in SQLite |
| `UNKNOWN_SCALE_TIER` | blocking | a value other than `small` or `big`; pilot and production refuse to start |
| `LOCAL_EVENTS` | info | SQL state without Kafka: events are durable in the outbox but not fanned out |

## Moving from small to big

Nothing in the decision plane changes. Move state to PostgreSQL (there is no
automated SQLite-to-PostgreSQL copy yet; start the new ledger fresh), set
`FSSAI_KAFKA_BOOTSTRAP` (the outbox relays pending events), point the gateway at
Kafka instead of `FSSAI_IMPORT_LOG_PATH`, and start the analytics profile. The
old SQLite archive stays verifiable with `fssaira small verify`. Archive into
Iceberg from the new ledger under a new `ledger_id` or after a signed checkpoint,
so the two archives do not overlap silently.
