"""Concurrent revocation, release, and emergency access against shared state.

Two properties fail only under concurrency, so they are measured here rather than
asserted.

**Revocation is linearizable with release.** Once a revocation commits, no later
release of an output that the revoked grant fed may commit. Each release and each
revocation takes a sequence number from the store inside its own transaction, so
the store's event log orders them, and any release after the revocation is a
counterexample.

**Emergency-access limits hold under contention.** When many workers open
break-glass access for one holder at the same moment, no more than the declared
number of unreviewed accesses may be granted. The SQL store locks a per-holder row
for the count and the insert.

Both are run with threads against the memory and SQL stores, and with independent
spawned processes, each with its own database connection, against one SQLite file.
The bounds are stated in every report: a finite schedule on one host is evidence,
not a proof of linearizability for every database, network, or failover.
"""
from __future__ import annotations

import multiprocessing
import tempfile
import threading
import time
from pathlib import Path

TOKEN = "concurrency-evidence-writer"


def _gate(policy, store, fx):
    from .disclosure import DisclosureGate
    from .evidence import EvidenceLedger

    return DisclosureGate(policy, fx.records, EvidenceLedger(TOKEN), TOKEN,
                          grant_keys=fx.authority.trusted_keys,
                          declassification_keys=fx.declassifier.trusted_keys, store=store)


def _events(store) -> list:
    with store.atomic() as tx:
        return tx.events()


def releases_after_revocation(events: list, grant_id: str) -> tuple[int, int]:
    """Releases fed by ``grant_id``, and how many committed after it was revoked."""
    revokes = [item["seq"] for item in events
               if item["kind"] == "revoke" and item.get("grant_id") == grant_id]
    releases = [item for item in events
                if item["kind"] == "release" and grant_id in item.get("grants", [])]
    if not revokes:
        return len(releases), 0
    first = min(revokes)
    return len(releases), sum(1 for item in releases if item["seq"] > first)


def run_thread_race(policy, *, store=None, threads: int = 8, successes_before_revoke: int = 12,
                    break_glass_threads: int = 8) -> dict:
    from .disclosure import DisclosureDenied
    from .disclosure_eval import AGENT, NOW, DisclosureFixture
    from .disclosure_store import MemoryDisclosureStore

    fx = DisclosureFixture(policy)
    store = store if store is not None else MemoryDisclosureStore()
    gate = _gate(policy, store, fx)
    grant = fx.grant()
    fx.read(gate, grant)
    output = gate.derive_output(requester=AGENT, session_id="session-1",
                                content="summary for the release race")

    lock = threading.Lock()
    enough, revoked, stop = threading.Event(), threading.Event(), threading.Event()
    counts = {"attempts": 0, "succeeded": 0, "refused_after_revocation": 0}

    def releaser() -> None:
        while not stop.is_set():
            try:
                gate.release(output, recipient=fx.cleared_recipient, purpose=fx.purpose,
                             now=NOW + 2)
                ok = True
            except DisclosureDenied:
                ok = False
            with lock:
                counts["attempts"] += 1
                counts["succeeded"] += ok
                if not ok and revoked.is_set():
                    counts["refused_after_revocation"] += 1
                if counts["succeeded"] >= successes_before_revoke:
                    enough.set()

    def revoker() -> None:
        enough.wait(timeout=30)
        gate.revoke_grant(grant.grant_id, by="data-owner", reason="concurrency race")
        revoked.set()
        time.sleep(0.05)
        stop.set()

    workers = [threading.Thread(target=releaser) for _ in range(threads)]
    workers.append(threading.Thread(target=revoker))
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=60)

    fed, after = releases_after_revocation(_events(store), grant.grant_id)

    break_glass = None
    rule = policy.break_glass
    if rule is not None:
        barrier = threading.Barrier(break_glass_threads)
        opened = {"count": 0}

        def emergency(index: int) -> None:
            emergency_grant = fx.break_glass_grant(f"race-bg-{index}")
            barrier.wait(timeout=30)
            try:
                fx.read(gate, emergency_grant, purpose=emergency_grant.purpose,
                        session_id=f"race-bg-session-{index}")
                ok = True
            except DisclosureDenied:
                ok = False
            with lock:
                opened["count"] += ok

        racers = [threading.Thread(target=emergency, args=(i,)) for i in range(break_glass_threads)]
        for racer in racers:
            racer.start()
        for racer in racers:
            racer.join(timeout=60)
        open_now = sum(1 for holder in gate.open_break_glass.values() if holder == AGENT)
        break_glass = {"attempts": break_glass_threads, "opened": opened["count"],
                       "open_in_store": open_now, "limit": rule.max_unreviewed_per_holder}

    violations = after
    if break_glass:
        violations += max(0, break_glass["opened"] - break_glass["limit"])
        violations += max(0, break_glass["open_in_store"] - break_glass["limit"])
    return {
        "kind": "disclosure-thread-race", "store": store.kind, "threads": threads,
        "release": {**counts, "releases_fed_by_revoked_grant": fed,
                    "committed_after_revocation": after},
        "break_glass": break_glass, "violations": violations, "holds": violations == 0,
        "bounds": ["threads in one process", "one output, one revocation, one holder",
                   "finite schedule; not a linearizability proof"],
    }


# ---------------------------------------------------------------------------
# Independent processes on one SQLite file
# ---------------------------------------------------------------------------


def _open(profile_path: str, db_path: str):
    from .disclosure_eval import DisclosureFixture
    from .disclosure_store import SqlDisclosureStore
    from .profiles import ApplicationProfile
    from .sql_backend import open_sqlite

    policy = ApplicationProfile.load(profile_path).disclosure
    fx = DisclosureFixture(policy)
    store = SqlDisclosureStore(open_sqlite(db_path))
    return policy, fx, store, _gate(policy, store, fx)


def _release_worker(profile_path, db_path, output_id, start, revoked, results, ready,
                    released) -> None:
    from .disclosure import DisclosureDenied
    from .disclosure_eval import NOW

    _policy, fx, _store, gate = _open(profile_path, db_path)
    output = gate.output(output_id)
    ready.release()
    start.wait(30)
    attempts = succeeded = after = 0
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            gate.release(output, recipient=fx.cleared_recipient, purpose=fx.purpose, now=NOW + 2)
            succeeded += 1
            released.set()
        except DisclosureDenied:
            pass
        attempts += 1
        if revoked.is_set():
            after += 1
            if after >= 5:
                break
    results.put({"role": "release", "attempts": attempts, "succeeded": succeeded})


def _break_glass_worker(profile_path, db_path, index, start, results, ready) -> None:
    from .disclosure import DisclosureDenied

    _policy, fx, _store, gate = _open(profile_path, db_path)
    emergency = fx.break_glass_grant(f"proc-bg-{index}")
    ready.release()
    start.wait(30)
    try:
        fx.read(gate, emergency, purpose=emergency.purpose, session_id=f"proc-bg-{index}")
        opened = True
    except DisclosureDenied:
        opened = False
    results.put({"role": "break_glass", "opened": opened})


def run_process_race(profile_path: str, *, processes: int = 4, db_path: str | None = None) -> dict:
    """Spawned workers with separate connections share one SQLite disclosure store."""
    from .disclosure_eval import AGENT

    if not isinstance(processes, int) or not 2 <= processes <= 32:
        raise ValueError("processes must be an integer from 2 to 32")
    context = multiprocessing.get_context("spawn")
    with tempfile.TemporaryDirectory() as scratch:
        path = db_path or str(Path(scratch) / "disclosure-race.db")
        policy, fx, store, gate = _open(profile_path, path)
        grant = fx.grant()
        fx.read(gate, grant)
        output = gate.derive_output(requester=AGENT, session_id="session-1",
                                    content="summary for the process race")
        start, revoked, results = context.Event(), context.Event(), context.Queue()
        ready, released = context.Semaphore(0), context.Event()
        workers = [context.Process(target=_release_worker,
                                   args=(profile_path, path, output.output_id, start, revoked,
                                         results, ready, released))
                   for _ in range(processes)]
        if policy.break_glass is not None:
            workers += [context.Process(target=_break_glass_worker,
                                        args=(profile_path, path, index, start, results, ready))
                        for index in range(processes)]
        for worker in workers:
            worker.start()
        # Spawned workers import and open the store before they can race; on a
        # slow runner that exceeds any fixed sleep, and revoking first would leave
        # nothing to race against. Start only once every worker is ready, and
        # revoke only once a release has committed under the live grant.
        ready_deadline = time.time() + 60
        for _ in workers:
            ready.acquire(timeout=max(0.0, ready_deadline - time.time()))
        start.set()
        time.sleep(1.0)
        released.wait(30)
        gate.revoke_grant(grant.grant_id, by="data-owner", reason="process race")
        revoked.set()
        collected = []
        deadline = time.time() + 120
        while len(collected) < len(workers) and time.time() < deadline:
            try:
                collected.append(results.get(timeout=5))
            except Exception:  # pragma: no cover - reported as incomplete below
                continue
        for worker in workers:
            worker.join(timeout=30)
            if worker.is_alive():  # pragma: no cover
                worker.terminate()

        fed, after = releases_after_revocation(_events(store), grant.grant_id)
        releases = [item for item in collected if item["role"] == "release"]
        emergencies = [item for item in collected if item["role"] == "break_glass"]
        limit = policy.break_glass.max_unreviewed_per_holder if policy.break_glass else None
        opened = sum(1 for item in emergencies if item["opened"])
        open_now = sum(1 for holder in gate.open_break_glass.values() if holder == AGENT)
        violations = after + (max(0, opened - limit) + max(0, open_now - limit) if limit else 0)
        complete = len(collected) == len(workers)
        store.database.close()
    return {
        "kind": "disclosure-process-race", "processes": processes, "complete": complete,
        "release": {"attempts": sum(i["attempts"] for i in releases),
                    "succeeded": sum(i["succeeded"] for i in releases),
                    "releases_fed_by_revoked_grant": fed, "committed_after_revocation": after},
        "break_glass": ({"attempts": len(emergencies), "opened": opened,
                         "open_in_store": open_now, "limit": limit} if limit else None),
        "violations": violations, "holds": complete and violations == 0,
        "bounds": ["spawned processes with separate connections on one local SQLite WAL file",
                   "PostgreSQL row locking is implemented but not exercised by this fixture",
                   "finite schedule; not a distributed linearizability proof"],
    }


__all__ = ["releases_after_revocation", "run_process_race", "run_thread_race"]
