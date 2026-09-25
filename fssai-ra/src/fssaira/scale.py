"""Choose the data tier from the workload, not from habit.

The platform ships two tiers that give the same control guarantees:

``small``
    SQLite (or one Postgres) for state, the evidence ledger and the event
    outbox; a SQLite import log and archive; a standard-library verifier
    (:mod:`fssaira.small_data`). One host, no broker, no cluster.
``big``
    Postgres for state; Kafka for the shared, replayable event and import log;
    Iceberg on MinIO for the archive; Spark for independent verification
    (``deploy/compose.yaml`` with ``--profile analytics``).

The decision plane is identical in both. Only the evidence plane changes, and
the evidence plane never authorises anything, so choosing ``small`` cannot
weaken a control. It changes throughput, fan-out, availability and retention.

:func:`recommend` states each reason for its choice next to the threshold it was
compared with, so an operator can argue with a number instead of a label.
:func:`measure_sqlite` measures what this host's disk sustains, because the
single-writer ceiling is a property of the hardware, not of the code.

``FSSAI_SCALE`` declares the tier a deployment intends. :func:`tier_findings`
reports a configuration that contradicts that declaration.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

TIERS = ("small", "big")


@dataclass(frozen=True)
class Thresholds:
    """Where one SQLite writer host stops being the right tool.

    These are defaults, deliberately conservative: each sits well below what a
    commodity SSD sustains (run :func:`measure_sqlite` for this host) so that a
    small deployment has headroom for bursts, backups and verification scans.
    """

    #: Sustained authoritative writes per second at peak.
    peak_writes_per_second: float = 50.0
    #: Evidence and import records per day.
    records_per_day: int = 500_000
    #: Archive size kept online for re-verification and appeal.
    archive_gb: float = 50.0
    #: Systems that must read the event/import stream independently, at their own pace.
    independent_consumers: int = 1
    #: Hosts that must accept writes.
    writer_hosts: int = 1


@dataclass(frozen=True)
class Workload:
    peak_writes_per_second: float = 1.0
    records_per_day: int = 1_000
    archive_gb: float = 1.0
    independent_consumers: int = 1
    writer_hosts: int = 1
    #: Must the evidence plane survive the loss of one host without an outage?
    high_availability: bool = False


def recommend(workload: Workload, thresholds: Thresholds | None = None) -> dict:
    """``small`` unless one of the workload's needs exceeds what one SQLite host provides."""
    limits = thresholds or Thresholds()
    checks = [
        ("peak_writes_per_second", workload.peak_writes_per_second,
         limits.peak_writes_per_second,
         "SQLite serialises writers on one host; Kafka partitions and Postgres spread them"),
        ("records_per_day", workload.records_per_day, limits.records_per_day,
         "at this volume a full-chain re-verification is a batch job; Spark parallelises it"),
        ("archive_gb", workload.archive_gb, limits.archive_gb,
         "Iceberg on object storage keeps snapshots, retention and time travel "
         "without one file growing past what can be backed up and scanned"),
        ("independent_consumers", workload.independent_consumers,
         limits.independent_consumers,
         "several systems replaying one ordered log at their own pace is what Kafka is for"),
        ("writer_hosts", workload.writer_hosts, limits.writer_hosts,
         "SQLite has one writer host; more need Postgres and a broker"),
    ]
    reasons = []
    for name, value, limit, why in checks:
        exceeded = value > limit
        reasons.append({"criterion": name, "workload": value, "small_tier_limit": limit,
                        "exceeded": exceeded, "why_big_data_helps": why})
    if workload.high_availability:
        reasons.append({"criterion": "high_availability", "workload": True,
                        "small_tier_limit": False, "exceeded": True,
                        "why_big_data_helps": "replicated Kafka and Postgres survive a host "
                                              "loss; one SQLite file does not"})
    exceeded = [r["criterion"] for r in reasons if r["exceeded"]]
    tier = "big" if exceeded else "small"
    return {
        "tier": tier,
        "exceeded": exceeded,
        "reasons": reasons,
        "workload": asdict(workload),
        "thresholds": asdict(limits),
        "run": ("docker compose --env-file deploy/.env -f deploy/compose.small.yaml up -d"
                if tier == "small" else
                "docker compose --env-file deploy/.env -f deploy/compose.yaml "
                "--profile analytics up -d"),
        "note": ("the decision plane and every control are identical in both tiers; the "
                 "tier changes throughput, fan-out, availability and retention only"),
    }


def measure_sqlite(records: int = 500, directory: str | Path | None = None) -> dict:
    """Time real transactional evidence appends on this host's disk.

    Uses the production SQL evidence path (``synchronous=FULL``, one transaction
    per append), so the figure is what the small tier's ledger sustains here,
    not a synthetic ``INSERT`` benchmark.
    """
    from .atomic_execution import sql_evidence
    from .sql_backend import open_sqlite

    token = "scale-measurement"
    with tempfile.TemporaryDirectory(dir=directory) as root:
        database = open_sqlite(str(Path(root) / "measure.sqlite3"), evidence_token=token)
        ledger = sql_evidence(database)
        try:
            started = time.perf_counter()
            for index in range(records):
                ledger.append("measurement", {"request_id": f"m-{index}"}, token=token)
            elapsed = time.perf_counter() - started
            intact = ledger.verify()
        finally:
            database.close()
    rate = records / elapsed if elapsed else float("inf")
    caveat = ("macOS: SQLite's fsync does not flush the drive cache without "
              "PRAGMA fullfsync, so this figure overstates durable throughput"
              if sys.platform == "darwin" else None)
    return {
        "records": records,
        "seconds": round(elapsed, 3),
        "appends_per_second": round(rate, 1),
        "chain_intact": intact,
        "headroom_over_default_limit": round(rate / Thresholds().peak_writes_per_second, 1),
        "note": "one durable transaction per append on this host's disk; "
                "the small tier's limit should stay well below this figure",
        "platform_caveat": caveat,
    }


def declared_tier() -> str | None:
    value = os.getenv("FSSAI_SCALE", "").strip().lower()
    return value or None


def tier_findings() -> list[tuple[str, str, str, str]]:
    """``(severity, code, message, remedy)`` for a configuration that contradicts ``FSSAI_SCALE``."""
    tier = declared_tier()
    if tier is None:
        return []
    if tier not in TIERS:
        return [("blocking", "UNKNOWN_SCALE_TIER",
                 f"FSSAI_SCALE={tier!r} is not one of {', '.join(TIERS)}",
                 "set FSSAI_SCALE=small or FSSAI_SCALE=big, or unset it")]
    database = os.getenv("FSSAI_DATABASE_URL", "").strip().lower()
    kafka = bool(os.getenv("FSSAI_KAFKA_BOOTSTRAP"))
    findings = []
    if tier == "small":
        if kafka:
            findings.append((
                "info", "BROKER_IN_SMALL_TIER",
                "FSSAI_SCALE=small but events are also published to Kafka; the broker is "
                "operated and secured for a workload that does not need it",
                "unset FSSAI_KAFKA_BOOTSTRAP, or declare FSSAI_SCALE=big"))
        if os.getenv("FSSAI_REDIS_URL") and not database:
            findings.append((
                "info", "REDIS_IN_SMALL_TIER",
                "FSSAI_SCALE=small but state is in Redis, which is two stores and needs "
                "reconciliation; SQLite gives single-transaction durability with no server",
                "set FSSAI_DATABASE_URL=sqlite:///path and unset FSSAI_REDIS_URL"))
    else:
        if not kafka:
            findings.append((
                "medium", "BIG_TIER_WITHOUT_BROKER",
                "FSSAI_SCALE=big but no Kafka is configured, so no other system can replay "
                "the event stream",
                "set FSSAI_KAFKA_BOOTSTRAP, or declare FSSAI_SCALE=small"))
        if database.startswith("sqlite"):
            findings.append((
                "medium", "BIG_TIER_ON_SQLITE",
                "FSSAI_SCALE=big but state is in SQLite, which has one writer host",
                "set FSSAI_DATABASE_URL to a postgresql:// URL, or declare FSSAI_SCALE=small"))
    return findings


__all__ = [
    "TIERS", "Thresholds", "Workload", "declared_tier", "measure_sqlite", "recommend",
    "tier_findings",
]
