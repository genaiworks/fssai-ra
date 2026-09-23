"""Durable, transactional state for the disclosure gate.

The gate's decisions depend on state that must outlive a process and must be
shared by every replica: which grants exist and which are revoked, who withdrew
consent, what each session has read, which outputs were issued and from what,
and which emergency accesses still await review. Holding that in a Python dict
makes a restart silently forget a revocation, and makes two replicas disagree
about whether a holder has already used their emergency access.

This module defines one interface and two implementations.

* :class:`MemoryDisclosureStore` keeps today's in-process behaviour for tests,
  reference runs, and single-process tools.
* :class:`SqlDisclosureStore` persists everything in SQLite or PostgreSQL. Every
  gate decision runs inside one database transaction, so the read of a
  revocation, the consent check, the break-glass count, and the write of the new
  session state commit together or not at all. Emergency-access limits lock a
  per-holder row, so concurrent replicas cannot both pass the count.

The store never holds protected record values. Sessions hold the keys of what
was released, values hold digests and labels, and redaction refetches values
from the record source when it needs them. Governed outputs are stored, because
releasing an output requires its content; that store is part of the trusted base
and inherits the pack's retention rule.
"""
from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class StoreUnavailable(RuntimeError):
    """The disclosure state could not be read or written; nothing is released."""


def _erased_output(body: dict) -> dict:
    return {**body, "content": "[erased]", "erased": True,
            "label": {**body.get("label", {}), "subjects": []}}


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class MemoryDisclosureStore:
    """In-process state behind one re-entrant lock."""

    kind = "memory"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ids = 0
        self._seq = 0
        self._revoked: dict[str, int] = {}
        self._withdrawn: set[tuple[str, str]] = set()
        self._sessions: dict[str, dict] = {}
        self._outputs: dict[str, dict] = {}
        self._expiry: dict[str, float] = {}
        self._break_glass: dict[str, dict] = {}
        self._values: dict[str, dict] = {}
        self._grants: dict[str, dict] = {}
        self._events: list[dict] = []

    @contextmanager
    def atomic(self) -> Iterator[MemoryDisclosureStore]:
        with self._lock:
            yield self

    # identifiers and ordering
    def next_id(self, prefix: str) -> str:
        self._ids += 1
        return f"{prefix}-{self._ids}"

    def tick(self) -> int:
        self._seq += 1
        return self._seq

    # grants
    def put_grant(self, grant_id: str, body: dict) -> None:
        self._grants[grant_id] = dict(body)

    def get_grant(self, grant_id: str) -> dict | None:
        body = self._grants.get(grant_id)
        return dict(body) if body is not None else None

    def grant_count(self) -> int:
        return len(self._grants)

    def revoke(self, grant_id: str, seq: int) -> None:
        self._revoked.setdefault(grant_id, seq)

    def is_revoked(self, grant_id: str) -> bool:
        return grant_id in self._revoked

    def set_grant_expiry(self, grant_id: str, expires_at: float) -> None:
        self._expiry[grant_id] = float(expires_at)

    def grant_expiry(self, grant_id: str) -> float | None:
        return self._expiry.get(grant_id)

    # consent
    def withdraw(self, subject: str, purpose: str) -> None:
        self._withdrawn.add((subject, purpose))

    def restore(self, subject: str, purpose: str) -> None:
        self._withdrawn.discard((subject, purpose))

    def consent_permits(self, subject: str, purpose: str) -> bool:
        return (subject, purpose) not in self._withdrawn

    # sessions, values, outputs
    def get_session(self, session_id: str) -> dict | None:
        body = self._sessions.get(session_id)
        return json.loads(json.dumps(body)) if body is not None else None

    def put_session(self, session_id: str, body: dict) -> None:
        self._sessions[session_id] = json.loads(json.dumps(body))

    def all_sessions(self) -> list[tuple[str, dict]]:
        return [(sid, json.loads(json.dumps(body))) for sid, body in self._sessions.items()]

    def put_value(self, value_id: str, body: dict) -> None:
        self._values[value_id] = dict(body)

    def get_value(self, value_id: str) -> dict | None:
        body = self._values.get(value_id)
        return dict(body) if body is not None else None

    def put_output(self, output_id: str, body: dict) -> None:
        self._outputs[output_id] = json.loads(json.dumps(body))

    def get_output(self, output_id: str) -> dict | None:
        body = self._outputs.get(output_id)
        return json.loads(json.dumps(body)) if body is not None else None

    def purge_subject_outputs(self, subject: str) -> int:
        """Erase the content of every stored output derived from ``subject``.

        Derived data inherits erasure: the output keeps its identifier so a later
        release fails closed as altered, but its content and label no longer exist.
        """
        purged = 0
        for output_id, body in self._outputs.items():
            if subject in body.get("label", {}).get("subjects", ()):
                self._outputs[output_id] = _erased_output(body)
                purged += 1
        return purged

    def output_bodies(self) -> list[dict]:
        return [json.loads(json.dumps(body)) for body in self._outputs.values()]

    # emergency access
    def lock_holder(self, holder: str) -> None:
        return None

    def break_glass_seen(self, grant_id: str) -> bool:
        return grant_id in self._break_glass

    def open_break_glass(self, grant_id: str, holder: str) -> None:
        self._break_glass[grant_id] = {"holder": holder, "open": True}

    def unreviewed_count(self, holder: str, exclude: str) -> int:
        return sum(1 for gid, row in self._break_glass.items()
                   if row["open"] and row["holder"] == holder and gid != exclude)

    def open_break_glass_holder(self, grant_id: str) -> str | None:
        row = self._break_glass.get(grant_id)
        return row["holder"] if row and row["open"] else None

    def close_break_glass(self, grant_id: str) -> None:
        if grant_id in self._break_glass:
            self._break_glass[grant_id]["open"] = False

    def open_break_glass_map(self) -> dict[str, str]:
        return {gid: row["holder"] for gid, row in self._break_glass.items() if row["open"]}

    # ordered events, for concurrency invariants
    def record_event(self, seq: int, kind: str, body: dict) -> None:
        self._events.append({"seq": seq, "kind": kind, **body})

    def events(self) -> list[dict]:
        return [dict(item) for item in self._events]


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_TABLES = {
    "disclosure_grants": "grant_id {text} PRIMARY KEY, body {text} NOT NULL",
    "disclosure_revoked": "grant_id {text} PRIMARY KEY, seq {big} NOT NULL",
    "disclosure_expiry": "grant_id {text} PRIMARY KEY, expires_at {text} NOT NULL",
    "disclosure_consent_withdrawn": "subject {text} NOT NULL, purpose {text} NOT NULL, "
                                    "PRIMARY KEY (subject, purpose)",
    "disclosure_sessions": "session_id {text} PRIMARY KEY, body {text} NOT NULL",
    "disclosure_values": "value_id {text} PRIMARY KEY, body {text} NOT NULL",
    "disclosure_outputs": "output_id {text} PRIMARY KEY, body {text} NOT NULL",
    "disclosure_break_glass": "grant_id {text} PRIMARY KEY, holder {text} NOT NULL, "
                              "is_open INTEGER NOT NULL",
    "disclosure_holder_locks": "holder {text} PRIMARY KEY",
    "disclosure_events": "seq {big} PRIMARY KEY, kind {text} NOT NULL, body {text} NOT NULL",
}


def _is_database_error(exc: BaseException) -> bool:
    module = type(exc).__module__ or ""
    return module.startswith(("sqlite3", "psycopg"))


class _SqlTx:
    """The store's operations bound to one open transaction."""

    def __init__(self, unit: Any) -> None:
        self._u = unit
        self._lock = unit.database.dialect.for_update

    def _t(self, name: str) -> str:
        return self._u.table(name)

    def _upsert(self, table: str, key: str, columns: dict) -> None:
        names = ", ".join(columns)
        marks = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{name} = EXCLUDED.{name}" for name in columns if name != key)
        self._u.execute(
            f"INSERT INTO {self._t(table)} ({names}) VALUES ({marks}) "
            f"ON CONFLICT ({key}) DO UPDATE SET {updates}",
            tuple(columns.values()),
        )

    def _body(self, table: str, key: str, value: str, *, lock: bool = False) -> dict | None:
        suffix = self._lock if lock else ""
        row = self._u.one(f"SELECT body FROM {self._t(table)} WHERE {key} = ?{suffix}", (value,))
        return json.loads(row[0]) if row else None

    def next_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex}"

    def tick(self) -> int:
        self._u.bump("disclosure_seq")
        return self._u.counter("disclosure_seq")

    def put_grant(self, grant_id: str, body: dict) -> None:
        self._upsert("disclosure_grants", "grant_id",
                     {"grant_id": grant_id, "body": json.dumps(body, sort_keys=True)})

    def get_grant(self, grant_id: str) -> dict | None:
        return self._body("disclosure_grants", "grant_id", grant_id)

    def grant_count(self) -> int:
        row = self._u.one(f"SELECT COUNT(*) FROM {self._t('disclosure_grants')}")
        return int(row[0]) if row else 0

    def revoke(self, grant_id: str, seq: int) -> None:
        self._u.execute(
            f"INSERT INTO {self._t('disclosure_revoked')} (grant_id, seq) VALUES (?, ?) "
            "ON CONFLICT (grant_id) DO NOTHING", (grant_id, seq))

    def is_revoked(self, grant_id: str) -> bool:
        return self._u.one(f"SELECT 1 FROM {self._t('disclosure_revoked')} WHERE grant_id = ?",
                           (grant_id,)) is not None

    def set_grant_expiry(self, grant_id: str, expires_at: float) -> None:
        self._upsert("disclosure_expiry", "grant_id",
                     {"grant_id": grant_id, "expires_at": repr(float(expires_at))})

    def grant_expiry(self, grant_id: str) -> float | None:
        row = self._u.one(f"SELECT expires_at FROM {self._t('disclosure_expiry')} WHERE grant_id = ?",
                          (grant_id,))
        return float(row[0]) if row else None

    def withdraw(self, subject: str, purpose: str) -> None:
        self._u.execute(
            f"INSERT INTO {self._t('disclosure_consent_withdrawn')} (subject, purpose) VALUES (?, ?) "
            "ON CONFLICT (subject, purpose) DO NOTHING", (subject, purpose))

    def restore(self, subject: str, purpose: str) -> None:
        self._u.execute(
            f"DELETE FROM {self._t('disclosure_consent_withdrawn')} WHERE subject = ? AND purpose = ?",
            (subject, purpose))

    def consent_permits(self, subject: str, purpose: str) -> bool:
        return self._u.one(
            f"SELECT 1 FROM {self._t('disclosure_consent_withdrawn')} WHERE subject = ? AND purpose = ?",
            (subject, purpose)) is None

    def get_session(self, session_id: str) -> dict | None:
        return self._body("disclosure_sessions", "session_id", session_id, lock=True)

    def put_session(self, session_id: str, body: dict) -> None:
        self._upsert("disclosure_sessions", "session_id",
                     {"session_id": session_id, "body": json.dumps(body, sort_keys=True)})

    def all_sessions(self) -> list[tuple[str, dict]]:
        rows = self._u.all(f"SELECT session_id, body FROM {self._t('disclosure_sessions')}")
        return [(row[0], json.loads(row[1])) for row in rows]

    def put_value(self, value_id: str, body: dict) -> None:
        self._u.execute(f"INSERT INTO {self._t('disclosure_values')} (value_id, body) VALUES (?, ?)",
                        (value_id, json.dumps(body, sort_keys=True)))

    def get_value(self, value_id: str) -> dict | None:
        return self._body("disclosure_values", "value_id", value_id)

    def put_output(self, output_id: str, body: dict) -> None:
        self._u.execute(f"INSERT INTO {self._t('disclosure_outputs')} (output_id, body) VALUES (?, ?)",
                        (output_id, json.dumps(body, sort_keys=True)))

    def get_output(self, output_id: str) -> dict | None:
        return self._body("disclosure_outputs", "output_id", output_id)

    def output_bodies(self) -> list[dict]:
        return [json.loads(row[0]) for row in
                self._u.all(f"SELECT body FROM {self._t('disclosure_outputs')}")]

    def purge_subject_outputs(self, subject: str) -> int:
        purged = 0
        for row in self._u.all(f"SELECT output_id, body FROM {self._t('disclosure_outputs')}"):
            body = json.loads(row[1])
            if subject in body.get("label", {}).get("subjects", ()):
                self._u.execute(
                    f"UPDATE {self._t('disclosure_outputs')} SET body = ? WHERE output_id = ?",
                    (json.dumps(_erased_output(body), sort_keys=True), row[0]))
                purged += 1
        return purged

    def lock_holder(self, holder: str) -> None:
        self._u.execute(f"INSERT INTO {self._t('disclosure_holder_locks')} (holder) VALUES (?) "
                        "ON CONFLICT (holder) DO NOTHING", (holder,))
        self._u.one(f"SELECT holder FROM {self._t('disclosure_holder_locks')} WHERE holder = ?"
                    f"{self._lock}", (holder,))

    def break_glass_seen(self, grant_id: str) -> bool:
        return self._u.one(f"SELECT 1 FROM {self._t('disclosure_break_glass')} WHERE grant_id = ?",
                           (grant_id,)) is not None

    def open_break_glass(self, grant_id: str, holder: str) -> None:
        self._u.execute(
            f"INSERT INTO {self._t('disclosure_break_glass')} (grant_id, holder, is_open) VALUES (?, ?, 1)",
            (grant_id, holder))

    def unreviewed_count(self, holder: str, exclude: str) -> int:
        row = self._u.one(
            f"SELECT COUNT(*) FROM {self._t('disclosure_break_glass')} "
            "WHERE holder = ? AND is_open = 1 AND grant_id <> ?", (holder, exclude))
        return int(row[0]) if row else 0

    def open_break_glass_holder(self, grant_id: str) -> str | None:
        row = self._u.one(
            f"SELECT holder FROM {self._t('disclosure_break_glass')} WHERE grant_id = ? AND is_open = 1"
            f"{self._lock}", (grant_id,))
        return row[0] if row else None

    def close_break_glass(self, grant_id: str) -> None:
        self._u.execute(f"UPDATE {self._t('disclosure_break_glass')} SET is_open = 0 WHERE grant_id = ?",
                        (grant_id,))

    def open_break_glass_map(self) -> dict[str, str]:
        rows = self._u.all(f"SELECT grant_id, holder FROM {self._t('disclosure_break_glass')} "
                           "WHERE is_open = 1")
        return {row[0]: row[1] for row in rows}

    def record_event(self, seq: int, kind: str, body: dict) -> None:
        self._u.execute(f"INSERT INTO {self._t('disclosure_events')} (seq, kind, body) VALUES (?, ?, ?)",
                        (seq, kind, json.dumps(body, sort_keys=True)))

    def events(self) -> list[dict]:
        rows = self._u.all(f"SELECT seq, kind, body FROM {self._t('disclosure_events')} ORDER BY seq")
        return [{"seq": int(row[0]), "kind": row[1], **json.loads(row[2])} for row in rows]


class SqlDisclosureStore:
    """Disclosure state in SQLite or PostgreSQL, one transaction per decision."""

    kind = "sql"

    def __init__(self, database: Any) -> None:
        self.database = database
        self._local = threading.local()
        dialect = database.dialect
        with database.transaction() as unit:
            for name, columns in _TABLES.items():
                unit.execute(f"CREATE TABLE IF NOT EXISTS {unit.table(name)} "
                             f"({columns.format(text=dialect.text_type, big=dialect.big_int)})")

    @contextmanager
    def atomic(self) -> Iterator[_SqlTx]:
        current = getattr(self._local, "tx", None)
        if current is not None:
            yield current
            return
        try:
            with self.database.transaction() as unit:
                tx = _SqlTx(unit)
                self._local.tx = tx
                try:
                    yield tx
                finally:
                    self._local.tx = None
        except Exception as exc:
            if _is_database_error(exc):
                raise StoreUnavailable(f"{type(exc).__name__}: {exc}") from exc
            raise


class StoreConsent:
    """Consent held in the disclosure store, so withdrawal survives restarts."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def permits(self, subject: str, purpose: str) -> bool:
        with self._store.atomic() as tx:
            return tx.consent_permits(subject, purpose)

    def withdraw(self, subject: str, purpose: str) -> None:
        with self._store.atomic() as tx:
            tx.withdraw(subject, purpose)

    def restore(self, subject: str, purpose: str) -> None:
        with self._store.atomic() as tx:
            tx.restore(subject, purpose)


def open_disclosure_store(url: str | None):
    """``memory``, ``sqlite:///path/to/file.db``, or a ``postgresql://`` DSN."""
    if not url or url == "memory":
        return MemoryDisclosureStore()
    from .sql_backend import open_postgres, open_sqlite

    if url.startswith("sqlite:///"):
        return SqlDisclosureStore(open_sqlite(url[len("sqlite:///"):]))
    if url.startswith(("postgresql://", "postgres://")):
        return SqlDisclosureStore(open_postgres(url))
    raise ValueError("disclosure store must be memory, sqlite:///PATH, or a postgresql:// DSN")


__all__ = [
    "MemoryDisclosureStore", "SqlDisclosureStore", "StoreConsent", "StoreUnavailable",
    "open_disclosure_store",
]
