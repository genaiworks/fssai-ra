"""SQL-backed ports with a genuinely transactional evidence path.

Why this module exists
----------------------
Release v0.5.0 could *detect* one failure it could not *prevent*: if the
authoritative mutation committed but the outcome-evidence append did not, the
executor raised ``OUTCOME_EVIDENCE_PENDING`` and waited for reconciliation. That
is honest, and it is the best a system can do when the register and the evidence
store are two different databases.

When they are the same database, the failure mode disappears. The mutation, the
execution receipt, the intent record, and the outcome record are written inside
one transaction: either all four are durable or none of them are. There is no
window in which a case moved without a record saying who moved it.

This module implements that once, against a small SQL surface, and runs it on
two dialects:

* **SQLite** -- no infrastructure, so continuous integration can prove the
  atomicity property on every commit rather than asserting it in prose.
* **PostgreSQL** -- the same code with ``SELECT ... FOR UPDATE`` row locking and
  ``SERIALIZABLE``-safe retry, for a deployment.

The claim boundary is unchanged for anything outside the database. If the real
side effect is in a third system (a payment, an email, a student record in a
vendor SIS), atomicity with that system is still impossible and the outbox +
reconciliation protocol still applies. What this removes is the *self-inflicted*
version of the problem.
"""
from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterator

from .evidence import GENESIS_HASH, EvidenceError, EvidenceRecord, _digest
from .exact_action import ActionProposal, ExecutionDenied, ExecutionResult, PendingOutcome, _canonical_digest


# ---------------------------------------------------------------------------
# Dialects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dialect:
    name: str
    placeholder: str           # "?" for sqlite, "%s" for postgres
    json_type: str
    text_type: str
    big_int: str
    for_update: str            # "" on sqlite, " FOR UPDATE" on postgres
    begin: str
    upsert_suffix: str
    retry_errors: tuple = ()

    def q(self, sql: str) -> str:
        """Rewrite ``?`` placeholders into the dialect's own style."""
        return sql if self.placeholder == "?" else sql.replace("?", self.placeholder)


SQLITE = Dialect(
    name="sqlite",
    placeholder="?",
    json_type="TEXT",
    text_type="TEXT",
    big_int="INTEGER",
    for_update="",
    begin="BEGIN IMMEDIATE",
    upsert_suffix="ON CONFLICT DO NOTHING",
)

POSTGRES = Dialect(
    name="postgres",
    placeholder="%s",
    json_type="JSONB",
    text_type="TEXT",
    big_int="BIGINT",
    for_update=" FOR UPDATE",
    begin="BEGIN",
    upsert_suffix="ON CONFLICT DO NOTHING",
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def schema_statements(dialect: Dialect, schema: str = "fssaira") -> list[str]:
    """DDL for every table the control plane needs. Idempotent."""
    prefix = "" if dialect is SQLITE else f"{schema}."
    statements: list[str] = []
    if dialect is POSTGRES:
        statements.append(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    statements += [
        f"""CREATE TABLE IF NOT EXISTS {prefix}resources (
                resource_id {dialect.text_type} PRIMARY KEY,
                status      {dialect.text_type} NOT NULL,
                version     {dialect.big_int}   NOT NULL,
                updated_at  DOUBLE PRECISION    NOT NULL
            )""".replace("DOUBLE PRECISION", "REAL" if dialect is SQLITE else "DOUBLE PRECISION"),
        f"""CREATE TABLE IF NOT EXISTS {prefix}execution_results (
                request_id   {dialect.text_type} PRIMARY KEY,
                resource_id  {dialect.text_type} NOT NULL,
                version      {dialect.big_int}   NOT NULL,
                status       {dialect.text_type} NOT NULL,
                receipt_hash {dialect.text_type} NOT NULL,
                created_at   {'REAL' if dialect is SQLITE else 'DOUBLE PRECISION'} NOT NULL
            )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}evidence (
                seq       {dialect.big_int} PRIMARY KEY,
                ts        {'REAL' if dialect is SQLITE else 'DOUBLE PRECISION'} NOT NULL,
                kind      {dialect.text_type} NOT NULL,
                payload   {dialect.json_type} NOT NULL,
                prev_hash {dialect.text_type} NOT NULL,
                hash      {dialect.text_type} NOT NULL UNIQUE
            )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}objects (
                namespace {dialect.text_type} NOT NULL,
                key       {dialect.text_type} NOT NULL,
                value     {dialect.json_type} NOT NULL,
                PRIMARY KEY (namespace, key)
            )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}approval_uses (
                approval_id {dialect.text_type} PRIMARY KEY,
                request_id  {dialect.text_type} NOT NULL,
                bound_at    {'REAL' if dialect is SQLITE else 'DOUBLE PRECISION'} NOT NULL
            )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}pending_outcomes (
                request_id {dialect.text_type} PRIMARY KEY,
                payload    {dialect.json_type} NOT NULL,
                created_at {'REAL' if dialect is SQLITE else 'DOUBLE PRECISION'} NOT NULL
            )""",
        f"""CREATE TABLE IF NOT EXISTS {prefix}counters (
                name  {dialect.text_type} PRIMARY KEY,
                value {dialect.big_int} NOT NULL
            )""",
        f"CREATE INDEX IF NOT EXISTS fssaira_evidence_kind ON {prefix}evidence (kind)",
    ]
    return statements


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------


class SqlDatabase:
    """A connection factory plus the DDL bootstrap, shared by every SQL port."""

    def __init__(self, connect: Callable[[], Any], dialect: Dialect, schema: str = "fssaira",
                 *, evidence_token: str | None = None) -> None:
        self._connect = connect
        self.dialect = dialect
        self.schema = schema
        #: The credential required to append evidence. Held by the evidence
        #: service, never by an agent. ``None`` disables the guard, which is
        #: only acceptable in a throwaway fixture -- the conformance suite
        #: fails a deployment that leaves it unset.
        self.evidence_token = evidence_token
        self._lock = threading.RLock()
        self._shared: Any | None = None

    # -- lifecycle ---------------------------------------------------------
    def connection(self):
        if self.dialect is SQLITE:
            with self._lock:
                if self._shared is None:
                    self._shared = self._connect()
                return self._shared
        return self._connect()

    def table(self, name: str) -> str:
        return name if self.dialect is SQLITE else f"{self.schema}.{name}"

    def create_schema(self) -> None:
        connection = self.connection()
        try:
            cursor = connection.cursor()
            for statement in schema_statements(self.dialect, self.schema):
                cursor.execute(statement)
            connection.commit()
        finally:
            if self.dialect is not SQLITE:
                connection.close()

    @contextmanager
    def transaction(self) -> Iterator["SqlUnitOfWork"]:
        """One database transaction exposing every port bound to it.

        Everything written inside the block commits together or not at all.
        This is the atomicity the accountable-action domain depends on.
        """
        acquired = self.dialect is SQLITE
        if acquired:
            self._lock.acquire()
        connection = self.connection()
        try:
            cursor = connection.cursor()
            if self.dialect is SQLITE:
                cursor.execute("BEGIN IMMEDIATE")
            unit = SqlUnitOfWork(self, connection, cursor)
            yield unit
            connection.commit()
        except BaseException:
            try:
                connection.rollback()
            except Exception:  # pragma: no cover - connection already dead
                pass
            raise
        finally:
            if self.dialect is not SQLITE:
                connection.close()
            if acquired:
                self._lock.release()

    @contextmanager
    def _auto(self) -> Iterator[tuple[Any, Any]]:
        """A short autocommitting transaction for single-statement ports."""
        with self.transaction() as unit:
            yield unit.connection, unit.cursor

    # -- helpers -----------------------------------------------------------
    def loads(self, value: Any) -> Any:
        return json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value

    def dumps(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, default=str)


def open_sqlite(path: str = ":memory:", schema: str = "fssaira",
                *, evidence_token: str | None = None) -> SqlDatabase:
    """Zero-infrastructure SQL profile. Used by the atomicity tests."""
    import sqlite3

    def connect():
        connection = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    database = SqlDatabase(connect, SQLITE, schema, evidence_token=evidence_token)
    database.create_schema()
    return database


def open_postgres(dsn: str, schema: str = "fssaira",
                  *, evidence_token: str | None = None) -> SqlDatabase:
    """Production SQL profile. Requires the ``postgres`` extra (``psycopg``)."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "The PostgreSQL backend requires the 'postgres' extra: pip install 'fssaira[postgres]'"
        ) from exc

    def connect():
        connection = psycopg.connect(dsn, autocommit=False)
        return connection

    database = SqlDatabase(connect, POSTGRES, schema, evidence_token=evidence_token)
    database.create_schema()
    return database


# ---------------------------------------------------------------------------
# Transaction-bound ports
# ---------------------------------------------------------------------------


class SqlUnitOfWork:
    """Every port, bound to one open transaction.

    ``unit.register``, ``unit.evidence``, ``unit.objects``, ``unit.approvals``
    and ``unit.outbox`` all write through the same cursor, so a caller that uses
    them inside one ``with database.transaction()`` block gets all-or-nothing
    semantics without knowing anything about SQL.
    """

    def __init__(self, database: SqlDatabase, connection: Any, cursor: Any) -> None:
        self.database = database
        self.connection = connection
        self.cursor = cursor
        self.register = _TxRegister(self)
        self.evidence = _TxEvidence(self)
        self.evidence.token = database.evidence_token
        self.objects = _TxObjects(self)
        self.approvals = _TxApprovalUses(self)
        self.outbox = _TxOutbox(self)

    # -- low level ---------------------------------------------------------
    def execute(self, sql: str, params: tuple = ()) -> Any:
        self.cursor.execute(self.database.dialect.q(sql), params)
        return self.cursor

    def one(self, sql: str, params: tuple = ()) -> tuple | None:
        return self.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple = ()) -> list:
        return self.execute(sql, params).fetchall()

    def table(self, name: str) -> str:
        return self.database.table(name)

    def bump(self, counter: str, amount: int = 1) -> None:
        table = self.table("counters")
        self.execute(
            f"INSERT INTO {table} (name, value) VALUES (?, ?) "
            f"ON CONFLICT (name) DO UPDATE SET value = {table}.value + ?",
            (counter, amount, amount),
        )

    def counter(self, name: str) -> int:
        row = self.one(f"SELECT value FROM {self.table('counters')} WHERE name = ?", (name,))
        return int(row[0]) if row else 0


class _TxRegister:
    """The authoritative register, inside a transaction."""

    def __init__(self, unit: SqlUnitOfWork) -> None:
        self._u = unit

    def seed(self, case_id: str, *, status: str, version: int = 1) -> bool:
        existing = self._u.one(
            f"SELECT 1 FROM {self._u.table('resources')} WHERE resource_id = ?", (case_id,)
        )
        if existing:
            return False
        self._u.execute(
            f"INSERT INTO {self._u.table('resources')} (resource_id, status, version, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (case_id, status, version, time.time()),
        )
        return True

    def get(self, case_id: str) -> dict:
        row = self._u.one(
            f"SELECT status, version FROM {self._u.table('resources')} WHERE resource_id = ?", (case_id,)
        )
        if row is None:
            raise KeyError(case_id)
        return {"status": row[0], "version": int(row[1])}

    def result_for(self, request_id: str) -> ExecutionResult | None:
        row = self._u.one(
            f"SELECT request_id, resource_id, version, status, receipt_hash "
            f"FROM {self._u.table('execution_results')} WHERE request_id = ?",
            (request_id,),
        )
        if row is None:
            return None
        return ExecutionResult(row[0], row[1], int(row[2]), row[3], row[4])

    @property
    def mutation_count(self) -> int:
        return self._u.counter("mutations")

    def transition(self, proposal: ActionProposal) -> ExecutionResult:
        prior = self.result_for(proposal.request_id)
        if prior is not None:
            return ExecutionResult(**{**asdict(prior), "replayed": True})

        lock = self._u.database.dialect.for_update
        row = self._u.one(
            f"SELECT status, version FROM {self._u.table('resources')} "
            f"WHERE resource_id = ?{lock}",
            (proposal.case_id,),
        )
        if row is None:
            raise ExecutionDenied("CASE_NOT_FOUND", "the target resource does not exist")
        status, version = row[0], int(row[1])
        if version != proposal.expected_version:
            raise ExecutionDenied("CASE_VERSION_CONFLICT", "the reviewed resource version is no longer current")
        if status != proposal.from_status:
            raise ExecutionDenied("CASE_STATE_CONFLICT", "the reviewed starting state is no longer current")

        new_version = version + 1
        self._u.execute(
            f"UPDATE {self._u.table('resources')} SET status = ?, version = ?, updated_at = ? "
            "WHERE resource_id = ?",
            (proposal.to_status, new_version, time.time(), proposal.case_id),
        )
        receipt = _canonical_digest({
            "request_id": proposal.request_id,
            "case_id": proposal.case_id,
            "version": new_version,
            "status": proposal.to_status,
        })
        self._u.execute(
            f"INSERT INTO {self._u.table('execution_results')} "
            "(request_id, resource_id, version, status, receipt_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (proposal.request_id, proposal.case_id, new_version,
             proposal.to_status, receipt, time.time()),
        )
        self._u.bump("mutations")
        return ExecutionResult(
            proposal.request_id, proposal.case_id, new_version, proposal.to_status, receipt
        )


class _TxEvidence:
    """Hash-chained evidence, appended under the transaction's row lock."""

    def __init__(self, unit: SqlUnitOfWork) -> None:
        self._u = unit
        self.token: str | None = None

    def append(self, kind: str, payload: dict, *, token: str) -> EvidenceRecord:
        if self.token is not None and token != self.token:
            raise EvidenceError("no evidence write authority")
        lock = self._u.database.dialect.for_update
        row = self._u.one(
            f"SELECT seq, hash FROM {self._u.table('evidence')} ORDER BY seq DESC LIMIT 1{lock}"
        )
        seq = 0 if row is None else int(row[0]) + 1
        prev = GENESIS_HASH if row is None else row[1]
        ts = time.time()
        digest = _digest(seq, ts, kind, payload, prev)
        self._u.execute(
            f"INSERT INTO {self._u.table('evidence')} (seq, ts, kind, payload, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (seq, ts, kind, self._u.database.dumps(payload), prev, digest),
        )
        return EvidenceRecord(seq, ts, kind, payload, prev, digest)

    def records(self) -> list[EvidenceRecord]:
        rows = self._u.all(
            f"SELECT seq, ts, kind, payload, prev_hash, hash FROM {self._u.table('evidence')} ORDER BY seq"
        )
        return [
            EvidenceRecord(int(r[0]), float(r[1]), r[2], self._u.database.loads(r[3]), r[4], r[5])
            for r in rows
        ]

    def verify(self) -> bool:
        prev = GENESIS_HASH
        for index, record in enumerate(self.records()):
            if record.seq != index or record.prev_hash != prev:
                return False
            if _digest(record.seq, record.ts, record.kind, record.payload, record.prev_hash) != record.hash:
                return False
            prev = record.hash
        return True

    def find(self, kind: str | None = None, **match: Any) -> list[EvidenceRecord]:
        return [
            record for record in self.records()
            if (kind is None or record.kind == kind)
            and all(record.payload.get(key) == value for key, value in match.items())
        ]


class _TxObjects:
    def __init__(self, unit: SqlUnitOfWork) -> None:
        self._u = unit

    def put(self, namespace: str, key: str, value: dict) -> None:
        table = self._u.table("objects")
        self._u.execute(
            f"INSERT INTO {table} (namespace, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT (namespace, key) DO UPDATE SET value = EXCLUDED.value",
            (namespace, key, self._u.database.dumps(value)),
        )

    def get(self, namespace: str, key: str) -> dict | None:
        row = self._u.one(
            f"SELECT value FROM {self._u.table('objects')} WHERE namespace = ? AND key = ?",
            (namespace, key),
        )
        return None if row is None else self._u.database.loads(row[0])


class _TxApprovalUses:
    """First-writer-wins approval binding.

    ``INSERT ... ON CONFLICT DO NOTHING RETURNING`` tells us, in one atomic
    statement, whether *this* transaction created the binding. That is the
    difference between "your retry of the same request" (return the stored
    receipt) and "someone replaying an approval against a new request" (deny).
    """

    def __init__(self, unit: SqlUnitOfWork) -> None:
        self._u = unit

    def bind(self, approval_id: str, request_id: str) -> tuple[str, bool]:
        table = self._u.table("approval_uses")
        inserted = self._u.one(
            f"INSERT INTO {table} (approval_id, request_id, bound_at) VALUES (?, ?, ?) "
            "ON CONFLICT (approval_id) DO NOTHING RETURNING request_id",
            (approval_id, request_id, time.time()),
        )
        if inserted is not None:
            return request_id, True
        row = self._u.one(f"SELECT request_id FROM {table} WHERE approval_id = ?", (approval_id,))
        return (row[0] if row else request_id), False


class _TxOutbox:
    def __init__(self, unit: SqlUnitOfWork) -> None:
        self._u = unit

    def put(self, outcome: PendingOutcome) -> None:
        table = self._u.table("pending_outcomes")
        self._u.execute(
            f"INSERT INTO {table} (request_id, payload, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT (request_id) DO UPDATE SET payload = EXCLUDED.payload",
            (outcome.request_id, self._u.database.dumps(outcome.payload), time.time()),
        )

    def remove(self, request_id: str) -> None:
        self._u.execute(
            f"DELETE FROM {self._u.table('pending_outcomes')} WHERE request_id = ?", (request_id,)
        )

    def get(self, request_id: str) -> PendingOutcome | None:
        row = self._u.one(
            f"SELECT payload FROM {self._u.table('pending_outcomes')} WHERE request_id = ?", (request_id,)
        )
        return None if row is None else PendingOutcome(request_id, self._u.database.loads(row[0]))

    def values(self) -> tuple[PendingOutcome, ...]:
        rows = self._u.all(
            f"SELECT request_id, payload FROM {self._u.table('pending_outcomes')} ORDER BY created_at"
        )
        return tuple(PendingOutcome(r[0], self._u.database.loads(r[1])) for r in rows)

    def __len__(self) -> int:
        row = self._u.one(f"SELECT COUNT(*) FROM {self._u.table('pending_outcomes')}")
        return int(row[0]) if row else 0


__all__ = [
    "Dialect", "POSTGRES", "SQLITE", "SqlDatabase", "SqlUnitOfWork",
    "open_postgres", "open_sqlite", "schema_statements",
]
