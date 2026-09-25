"""The small-data evidence plane: the same guarantees as the big-data one, without a cluster.

The big-data tier moves imports through Kafka, archives evidence in Iceberg on
MinIO, and re-verifies the chain with Spark. Those tools earn their place when
volume, fan-out or retention outgrow one machine (see :mod:`fssaira.scale`).
For a single school, one department, or a pilot handling a few thousand records
a day, a broker plus a Spark cluster costs more to run and secure than the data
it carries. This module does the same jobs with SQLite files and the standard
library.

=====================  =======================  ======================================
Job                    Big-data tier            Small-data tier (this module)
=====================  =======================  ======================================
Inward import log      Kafka topic              :class:`SqliteImportLog`
Import sink            Spark Structured Stream  :func:`ingest_imports`
Evidence archive       Iceberg on MinIO         :class:`SqliteArchiveStore`
Archiver               ``archive_evidence``     the same function, unchanged
Independent verifier   Spark job                :func:`verify_archive`
=====================  =======================  ======================================

What does not change between tiers
----------------------------------
* The gateway signs every inward record with ``FSSAI_IMPORT_ENVELOPE_KEY``; the
  sink rejects a missing or wrong MAC and quarantines the position, never the
  content.
* A record whose ``content_hash`` does not match its text fails the whole
  batch; nothing is committed.
* Re-running the sink is idempotent on the record's position, and a different
  record at a stored position is refused (the log was reset or replaced).
* :func:`fssaira.iceberg_backend.archive_evidence` does the archiving in both
  tiers, with the same ``ARCHIVE_AHEAD_OF_LEDGER`` / ``ARCHIVE_DIVERGED`` refusals.
* :func:`fssaira.chain_verification.verify_rows` does the verification in both
  tiers, including the signed-checkpoint check.

What the small tier gives up
----------------------------
* One writer host. SQLite serialises writers; there is no replication.
* No independent consumers reading one shared log at their own pace. The import
  log is read by one sink.
* No time travel by snapshot *id* across engines. Each archive commit is
  recorded in ``archive_snapshots`` with its manifest, so a decision can still
  be bound to the archive state it saw.

Keep the archive file on different storage, under different administration,
from the control plane's database. An archive on the same disk, writable by the
same account, detects accidents, not an administrator.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .chain_verification import verify_rows
from .iceberg_backend import EVIDENCE_TABLE, _manifest

IMPORT_TABLE = "imported_evidence"
QUARANTINE_TABLE = "quarantined_imports"


def _connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), check_same_thread=False,
                                 isolation_level=None, timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _immediate(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One write transaction, taken before the first read so it cannot be upgraded late."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")


# ---------------------------------------------------------------------------
# Inward import log (Kafka's job in the big-data tier)
# ---------------------------------------------------------------------------


class SqliteImportLog:
    """An append-only, durable log of gateway envelopes.

    Implements the gateway's ``InwardPublisher`` protocol, so
    :func:`fssaira.import_api.create_import_app` uses it wherever it would use a
    Kafka publisher. Envelopes have the Kafka publisher's exact shape and MAC,
    so :func:`ingest_imports` checks them the way the Spark job does.

    ``append`` returns once the row is committed with ``synchronous=FULL``: the
    same "acknowledged means durable" contract as ``acks=all`` on one node.
    Offsets start at 0 and have no gaps, like one Kafka partition.

    ``generation`` plays the role of ``FSSAI_IMPORT_TOPIC_GENERATION``: it is
    stored in the file when the log is created, so a deleted and recreated log
    is recognised as a new generation rather than silently re-used positions.
    """

    name = "sqlite-import-log"

    def __init__(self, path: str | Path, *, mac_key: bytes | None = None,
                 topic: str = "fssaira.imports") -> None:
        self.path = str(path)
        self.topic = topic
        self.mac_key = mac_key
        self._lock = threading.Lock()
        self._db = _connect(self.path)
        with _immediate(self._db) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS import_log (
                              log_offset   INTEGER PRIMARY KEY,
                              event_key    TEXT NOT NULL,
                              envelope     TEXT NOT NULL,
                              appended_at  REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS log_meta (
                              name TEXT PRIMARY KEY, value TEXT NOT NULL)""")
            db.execute("INSERT OR IGNORE INTO log_meta VALUES ('generation', ?)",
                       (uuid.uuid4().hex,))

    @property
    def generation(self) -> str:
        return self._db.execute(
            "SELECT value FROM log_meta WHERE name = 'generation'").fetchone()[0]

    def append(self, value: dict, key: str = "", trace_id: str = "") -> int:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        trace = trace_id or hashlib.sha256(body.encode()).hexdigest()[:16]
        fields = {"value": value, "trace_id": trace, "published_at": time.time()}
        if self.mac_key:
            from .envelope_mac import sign

            fields["mac"] = sign(self.mac_key, value, trace)
        envelope = json.dumps(fields, sort_keys=True, default=str)
        with self._lock, _immediate(self._db) as db:
            offset = db.execute(
                "SELECT COALESCE(MAX(log_offset) + 1, 0) FROM import_log").fetchone()[0]
            db.execute("INSERT INTO import_log VALUES (?, ?, ?, ?)",
                       (offset, key, envelope, time.time()))
        return int(offset)

    def read(self, from_offset: int = 0, limit: int | None = None) -> list[dict]:
        sql = ("SELECT log_offset, event_key, envelope, appended_at FROM import_log "
               "WHERE log_offset >= ? ORDER BY log_offset")
        params: tuple = (from_offset,)
        if limit is not None:
            sql += " LIMIT ?"
            params += (limit,)
        return [dict(row) for row in self._db.execute(sql, params)]

    def __len__(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM import_log").fetchone()[0])

    def close(self) -> None:
        self._db.close()


# ---------------------------------------------------------------------------
# Evidence archive (Iceberg's job in the big-data tier)
# ---------------------------------------------------------------------------


class SqliteArchiveStore:
    """Evidence archive and import sink in one SQLite file.

    Duck-types the parts of :class:`fssaira.iceberg_backend.IcebergSnapshotStore`
    that :func:`~fssaira.iceberg_backend.archive_evidence` uses (``table``,
    ``archived_head``, ``commit``, ``current_id``), so archiving runs through the
    same function in both tiers.

    Unlike Iceberg appends, ``(ledger_id, seq)`` is a primary key here: two
    archivers racing on one ledger cannot both store the same record. The
    verifier still reports duplicates, so its verdict means the same thing in
    both tiers.
    """

    table = f"archive.{EVIDENCE_TABLE}"

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        self._db = _connect(self.path)
        with _immediate(self._db) as db:
            db.execute(f"""CREATE TABLE IF NOT EXISTS {EVIDENCE_TABLE} (
                               ledger_id    TEXT    NOT NULL,
                               seq          INTEGER NOT NULL,
                               ts           REAL    NOT NULL,
                               kind         TEXT    NOT NULL,
                               request_id   TEXT    NOT NULL,
                               payload_json TEXT    NOT NULL,
                               prev_hash    TEXT    NOT NULL,
                               hash         TEXT    NOT NULL,
                               archived_at  TEXT    NOT NULL,
                               snapshot_id  TEXT    NOT NULL,
                               PRIMARY KEY (ledger_id, seq))""")
            db.execute(f"""CREATE TABLE IF NOT EXISTS {IMPORT_TABLE} (
                               log_generation TEXT    NOT NULL,
                               log_offset     INTEGER NOT NULL,
                               source         TEXT    NOT NULL,
                               text           TEXT    NOT NULL,
                               stripped       TEXT    NOT NULL,
                               content_hash   TEXT    NOT NULL,
                               trace_id       TEXT    NOT NULL,
                               imported_at    REAL    NOT NULL,
                               snapshot_id    TEXT    NOT NULL,
                               PRIMARY KEY (log_generation, log_offset))""")
            db.execute(f"""CREATE TABLE IF NOT EXISTS {QUARANTINE_TABLE} (
                               log_generation TEXT    NOT NULL,
                               log_offset     INTEGER NOT NULL,
                               trace_id       TEXT    NOT NULL,
                               reason         TEXT    NOT NULL,
                               raw_sha256     TEXT    NOT NULL,
                               quarantined_at REAL    NOT NULL,
                               PRIMARY KEY (log_generation, log_offset))""")
            db.execute("""CREATE TABLE IF NOT EXISTS archive_snapshots (
                              seq          INTEGER PRIMARY KEY,
                              snapshot_id  TEXT NOT NULL UNIQUE,
                              parent_id    TEXT,
                              target       TEXT NOT NULL,
                              note         TEXT NOT NULL,
                              manifest     TEXT NOT NULL,
                              row_count    INTEGER NOT NULL,
                              committed_at REAL NOT NULL)""")

    # -- the IcebergSnapshotStore surface archive_evidence relies on ---------

    @property
    def current_id(self) -> str | None:
        row = self._db.execute(
            "SELECT snapshot_id FROM archive_snapshots ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def archived_head(self, ledger_id: str) -> tuple[int, str] | None:
        row = self._db.execute(
            f"SELECT seq, hash FROM {EVIDENCE_TABLE} WHERE ledger_id = ? "
            "ORDER BY seq DESC LIMIT 1", (ledger_id,)).fetchone()
        return (int(row[0]), row[1]) if row else None

    def commit(self, rows, parent: str | None = None, note: str = "") -> str:
        """Insert evidence rows and record the snapshot, in one transaction."""
        snapshot_id = uuid.uuid4().hex
        with self._lock, _immediate(self._db) as db:
            parent = parent or self.current_id
            db.executemany(
                f"INSERT INTO {EVIDENCE_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(r["ledger_id"], r["seq"], r["ts"], r["kind"], r["request_id"],
                  r["payload_json"], r["prev_hash"], r["hash"], str(r["archived_at"]),
                  snapshot_id) for r in rows])
            self._record_snapshot(db, snapshot_id, parent, EVIDENCE_TABLE, note, rows)
        return snapshot_id

    # -- reading -------------------------------------------------------------

    def evidence_rows(self, ledger_id: str = "primary", since_seq: int = 0) -> list[dict]:
        return [dict(row) for row in self._db.execute(
            f"SELECT seq, ts, kind, payload_json, prev_hash, hash FROM {EVIDENCE_TABLE} "
            "WHERE ledger_id = ? AND seq >= ? ORDER BY seq", (ledger_id, since_seq))]

    def history(self) -> list[dict]:
        return [dict(row) for row in self._db.execute(
            "SELECT snapshot_id, parent_id, target, note, manifest, row_count, committed_at "
            "FROM archive_snapshots ORDER BY seq")]

    def imports(self) -> list[dict]:
        return [dict(row) for row in self._db.execute(
            f"SELECT * FROM {IMPORT_TABLE} ORDER BY log_generation, log_offset")]

    def quarantined(self) -> list[dict]:
        return [dict(row) for row in self._db.execute(
            f"SELECT * FROM {QUARANTINE_TABLE} ORDER BY log_generation, log_offset")]

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _record_snapshot(db, snapshot_id, parent, target, note, rows) -> None:
        seq = db.execute("SELECT COALESCE(MAX(seq) + 1, 0) FROM archive_snapshots").fetchone()[0]
        db.execute("INSERT INTO archive_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (seq, snapshot_id, parent, target, note, _manifest(rows), len(rows),
                    time.time()))


# ---------------------------------------------------------------------------
# Import sink (the Spark streaming job's job in the big-data tier)
# ---------------------------------------------------------------------------


def _authentic(key: bytes, envelope: dict) -> bool:
    try:
        body = json.dumps({"trace_id": envelope.get("trace_id", ""), "value": envelope["value"]},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          default=str).encode("utf-8")
        mac = envelope.get("mac")
        return isinstance(mac, str) and hmac.compare_digest(
            hmac.new(key, body, hashlib.sha256).hexdigest(), mac)
    except (TypeError, ValueError, KeyError, AttributeError):
        return False


def ingest_imports(log: SqliteImportLog, archive: SqliteArchiveStore,
                   *, mac_key: bytes | None, allow_unsigned: bool = False,
                   batch_size: int = 10_000) -> dict:
    """Move new log records into the archive's import table. Safe to re-run.

    Mirrors ``jobs/kafka_to_iceberg.py``: unsigned or forged envelopes are
    quarantined by position and hash, not content; a malformed record or a
    content-hash mismatch fails the batch with nothing committed; a stored
    position holding a different record is refused.
    """
    if mac_key is None and not allow_unsigned:
        raise RuntimeError(
            "no import envelope key: the sink cannot tell gateway imports from records "
            "written straight to the log. Set FSSAI_IMPORT_ENVELOPE_KEY (the gateway's), "
            "or pass allow_unsigned to accept that risk explicitly")
    generation = log.generation
    db = archive._db
    done = db.execute(
        f"SELECT MAX(o) FROM (SELECT MAX(log_offset) AS o FROM {IMPORT_TABLE} "
        f"WHERE log_generation = ? UNION ALL SELECT MAX(log_offset) FROM {QUARANTINE_TABLE} "
        "WHERE log_generation = ?)", (generation, generation)).fetchone()[0]
    if done is not None and int(done) >= len(log):
        raise RuntimeError(
            f"the archive holds offset {done} for generation {generation} but the log has "
            f"{len(log)} record(s): the log was truncated. Nothing was written")
    # Resume after the highest position already imported or quarantined.
    entries = log.read(0 if done is None else int(done) + 1, limit=batch_size)

    accepted, rejected = [], []
    for entry in entries:
        raw = entry["envelope"]
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            envelope = {}
        if mac_key is not None and not _authentic(mac_key, envelope):
            rejected.append((generation, entry["log_offset"], str(envelope.get("trace_id", "")),
                             "envelope MAC missing or invalid",
                             hashlib.sha256(raw.encode()).hexdigest(), time.time()))
            continue
        value = envelope.get("value") if isinstance(envelope, dict) else None
        if not isinstance(value, dict) or not all(
                isinstance(value.get(f), str) for f in ("source", "text", "content_hash")) \
                or not envelope.get("trace_id"):
            raise ValueError("invalid import envelope; batch not committed")
        if hashlib.sha256(value["text"].encode()).hexdigest() != value["content_hash"]:
            raise ValueError("invalid import envelope or content hash; batch not committed")
        accepted.append({
            "log_generation": generation, "log_offset": entry["log_offset"],
            "source": value["source"], "text": value["text"],
            "stripped": json.dumps(value.get("stripped") or []),
            "content_hash": value["content_hash"], "trace_id": str(envelope["trace_id"]),
            "imported_at": entry["appended_at"],
        })

    snapshot_id = uuid.uuid4().hex
    with archive._lock, _immediate(db):
        for row in accepted:
            stored = db.execute(
                f"SELECT trace_id, content_hash FROM {IMPORT_TABLE} "
                "WHERE log_generation = ? AND log_offset = ?",
                (generation, row["log_offset"])).fetchone()
            if stored is not None and (stored[0], stored[1]) != (row["trace_id"],
                                                                 row["content_hash"]):
                raise ValueError(
                    "log positions already hold different records: the import log was "
                    "replaced. Nothing was written")
        new = [row for row in accepted if db.execute(
            f"SELECT 1 FROM {IMPORT_TABLE} WHERE log_generation = ? AND log_offset = ?",
            (row["log_generation"], row["log_offset"])).fetchone() is None]
        db.executemany(
            f"INSERT INTO {IMPORT_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(r["log_generation"], r["log_offset"], r["source"], r["text"], r["stripped"],
              r["content_hash"], r["trace_id"], r["imported_at"], snapshot_id) for r in new])
        db.executemany(f"INSERT OR IGNORE INTO {QUARANTINE_TABLE} VALUES (?, ?, ?, ?, ?, ?)",
                       rejected)
        if new:
            archive._record_snapshot(db, snapshot_id, archive.current_id, IMPORT_TABLE,
                                     f"imports generation {generation}", new)
    return {
        "log_generation": generation,
        "read": len(entries),
        "imported": len(new),
        "quarantined": len(rejected),
        "snapshot_id": snapshot_id if new else None,
        "more": len(entries) == batch_size,
    }


# ---------------------------------------------------------------------------
# Archiving and independent verification
# ---------------------------------------------------------------------------


def archive_ledger(database_url: str, archive: SqliteArchiveStore, *,
                   ledger_id: str = "primary", evidence_token: str | None = None) -> dict:
    """Archive the control plane's SQL ledger, through the big-data tier's archiver."""
    from .atomic_execution import sql_evidence
    from .iceberg_backend import archive_evidence
    from .postgres_backend import database_from_env

    database = database_from_env(database_url, evidence_token=evidence_token)
    try:
        return archive_evidence(sql_evidence(database), archive, ledger_id=ledger_id)
    finally:
        close = getattr(database, "close", None)
        if close is not None:
            close()


def verify_archive(archive: SqliteArchiveStore, *, ledger_id: str = "primary",
                   since_seq: int = 0, checkpoint: dict | None = None,
                   public_keys: dict[str, str] | None = None) -> dict:
    """Recompute the archived chain; the Spark verifier's checks on the SQLite archive."""
    verdict = verify_rows(archive.evidence_rows(ledger_id, since_seq), since_seq=since_seq,
                          checkpoint=checkpoint, public_keys=public_keys)
    return {"archive": archive.path, "ledger_id": ledger_id, **verdict}


__all__ = [
    "IMPORT_TABLE", "QUARANTINE_TABLE", "SqliteArchiveStore", "SqliteImportLog",
    "archive_ledger", "ingest_imports", "verify_archive",
]
