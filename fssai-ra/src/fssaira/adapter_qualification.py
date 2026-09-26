"""Qualify a real authority store and effect sink against the revocation invariants.

:mod:`fssaira.revocation_chaos` shows that the *protocol* holds: fenced commit
is clean under partition, loss, duplication, delay and clock skew, and each weaker
discipline fails. A deployment needs more than that. It needs to know that *its*
store fences commits against the epoch and that *its* external system honours
idempotency keys. This module is the kit for that:

* :class:`SqlAuthorityStore` and :class:`SqlSink` are reference implementations
  on SQLite. Epoch check and commit happen in one ``BEGIN IMMEDIATE``
  transaction, and the sink deduplicates on a primary key. Port them to your
  database, or wrap your existing services behind the same four methods
  (``revoke``, ``epoch``, ``commit``, ``committed``) and one (``deliver``).
* :func:`qualify` drives any such pair through the seeded chaos campaign, using
  the real objects in place of the in-memory models. A store that forgets the
  epoch or a sink without an idempotency key fails here, not in production.
* :func:`concurrent_revocation_check` runs real threads that commit while
  another thread revokes. It then replays the store's own audit log in commit
  order and checks that no commit carries an epoch that was already superseded.
  The chaos campaign is deterministic and single-threaded; this is the check
  that the store's transactions linearize.

A pass qualifies the objects you passed in, on the host you ran it on. It says
nothing about a different database, isolation level or deployment topology.
"""
from __future__ import annotations

import random
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from pathlib import Path

from .revocation_chaos import ChaosConfig, run_once


class QualificationCode:
    QUALIFIED = "ADAPTER_QUALIFIED"
    NOT_QUALIFIED = "ADAPTER_NOT_QUALIFIED"
    LINEARIZABLE = "STORE_LINEARIZABLE"
    STALE_COMMIT = "STORE_STALE_COMMIT"


class SqlAuthorityStore:
    """Epochs and fenced commits in SQLite, one transaction per decision.

    Every revocation and commit is also appended to ``authority_log`` inside the
    same transaction, so the log order *is* the serialization order and can be
    audited afterwards without trusting the store's own verdicts.
    """

    def __init__(self, path: str | Path, tasks: int) -> None:
        self.path = str(path)
        self._local = threading.local()
        # executescript commits implicitly, so the schema is created outside
        # the transaction that seeds the epochs.
        self._db().executescript("""
            CREATE TABLE IF NOT EXISTS epochs(task INTEGER PRIMARY KEY, epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS commits(effect TEXT PRIMARY KEY, task INTEGER NOT NULL,
              epoch INTEGER NOT NULL, committed_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS authority_log(seq INTEGER PRIMARY KEY AUTOINCREMENT,
              kind TEXT NOT NULL, task INTEGER NOT NULL, epoch INTEGER NOT NULL, effect TEXT);
            """)
        with self._tx() as db:
            db.executemany("INSERT OR IGNORE INTO epochs VALUES(?,0)", [(t,) for t in range(tasks)])

    def _db(self) -> sqlite3.Connection:
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(self.path, isolation_level=None, timeout=30)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=30000")
            self._local.db = db
        return db

    @contextmanager
    def _tx(self):
        db = self._db()
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
        except BaseException:
            db.execute("ROLLBACK")
            raise
        db.execute("COMMIT")

    def revoke(self, task: int) -> None:
        with self._tx() as db:
            db.execute("UPDATE epochs SET epoch=epoch+1 WHERE task=?", (task,))
            (epoch,) = db.execute("SELECT epoch FROM epochs WHERE task=?", (task,)).fetchone()
            db.execute("INSERT INTO authority_log(kind,task,epoch,effect) VALUES('revoke',?,?,NULL)",
                       (task, epoch))

    def epoch(self, task: int) -> int:
        return self._db().execute("SELECT epoch FROM epochs WHERE task=?", (task,)).fetchone()[0]

    def commit(self, effect: str, task: int, epoch: int, now: float) -> float | None:
        with self._tx() as db:
            row = db.execute("SELECT committed_at FROM commits WHERE effect=?", (effect,)).fetchone()
            if row is not None:
                return row[0]                                # idempotent replay
            (current,) = db.execute("SELECT epoch FROM epochs WHERE task=?", (task,)).fetchone()
            if current != epoch:
                return None
            db.execute("INSERT INTO commits VALUES(?,?,?,?)", (effect, task, epoch, now))
            db.execute("INSERT INTO authority_log(kind,task,epoch,effect) VALUES('commit',?,?,?)",
                       (task, epoch, effect))
            return now

    def committed(self) -> dict[str, float]:
        return dict(self._db().execute("SELECT effect, committed_at FROM commits"))

    def audit_log(self) -> list[tuple[str, int, int, str | None]]:
        return [tuple(row) for row in self._db().execute(
            "SELECT kind,task,epoch,effect FROM authority_log ORDER BY seq")]

    def close(self) -> None:
        db = getattr(self._local, "db", None)
        if db is not None:
            db.close()
            self._local.db = None


class SqlSink:
    """An external system that honours idempotency keys: a primary key on the key."""

    def __init__(self, path: str | Path) -> None:
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.execute("CREATE TABLE IF NOT EXISTS deliveries(key TEXT PRIMARY KEY, at REAL)")

    def deliver(self, effect: str) -> bool:
        cursor = self.db.execute("INSERT OR IGNORE INTO deliveries VALUES(?,?)",
                                 (effect, time.time()))
        return cursor.rowcount == 1

    def close(self) -> None:
        self.db.close()


def qualify(store_factory: Callable[[int, int], object], sink_factory: Callable[[int], object],
            *, seeds: int = 50, config: ChaosConfig | None = None) -> dict:
    """Run the fenced discipline with *your* store and sink in the loop.

    ``store_factory(seed, tasks)`` and ``sink_factory(seed)`` return fresh
    objects for each seeded run.
    """
    config = config or ChaosConfig()
    totals = {"stale_effects": 0, "duplicate_applications": 0, "unreconciled": 0,
              "applied": 0, "refused_stale": 0}
    failing_seeds = []
    for seed in range(seeds):
        store, sink = store_factory(seed, config.tasks), sink_factory(seed)
        try:
            run = run_once("fenced", seed, config, store=store, sink=sink)
        finally:
            for obj in (store, sink):
                close = getattr(obj, "close", None)
                if close:
                    close()
        for key in totals:
            totals[key] += run[key] or 0
        if run["stale_effects"] or run["duplicate_applications"] or run["unreconciled"]:
            failing_seeds.append(seed)
    ok = not failing_seeds
    return {"code": QualificationCode.QUALIFIED if ok else QualificationCode.NOT_QUALIFIED,
            "qualified": ok, "runs": seeds, **totals, "failing_seeds": failing_seeds[:20]}


def audit_linearization(log: Iterable[tuple[str, int, int, str | None]]) -> list[dict]:
    """Replay an authority log in order; report every commit at a superseded epoch."""
    current: dict[int, int] = {}
    violations = []
    for position, (kind, task, epoch, effect) in enumerate(log):
        if kind == "revoke":
            current[task] = epoch
        elif kind == "commit" and epoch != current.get(task, 0):
            violations.append({"position": position, "effect": effect, "task": task,
                               "epoch": epoch, "current": current.get(task, 0)})
    return violations


def concurrent_revocation_check(store: SqlAuthorityStore, *, tasks: int, workers: int = 8,
                                commits_per_worker: int = 60, revocations: int = 12,
                                seed: int = 0) -> dict:
    """Real threads race commits against revocations; the log must linearize."""
    errors: list[BaseException] = []

    def worker(w: int) -> None:
        rng = random.Random(seed * 1000 + w)
        try:
            for i in range(commits_per_worker):
                task = rng.randrange(tasks)
                # A deliberately stale-prone read: the epoch may move before commit.
                store.commit(f"w{w}-{i}", task, store.epoch(task), time.monotonic())
        except BaseException as error:              # surfaced below, never swallowed
            errors.append(error)

    def revoker() -> None:
        rng = random.Random(seed)
        try:
            for _ in range(revocations):
                store.revoke(rng.randrange(tasks))
                time.sleep(0.001)
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(workers)]
    threads.append(threading.Thread(target=revoker))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if errors:
        raise errors[0]
    log = store.audit_log()
    violations = audit_linearization(log)
    return {"code": QualificationCode.STALE_COMMIT if violations else QualificationCode.LINEARIZABLE,
            "linearizable": not violations,
            "commits": sum(1 for kind, *_ in log if kind == "commit"),
            "revocations": sum(1 for kind, *_ in log if kind == "revoke"),
            "violations": violations[:20]}


__all__ = ["QualificationCode", "SqlAuthorityStore", "SqlSink", "audit_linearization",
           "concurrent_revocation_check", "qualify"]
