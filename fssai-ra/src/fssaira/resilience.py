"""Reproducible process-race and crash/restart fixtures for local SQLite.

Each worker uses spawn and opens its own connection. Crash workers exit without
Python cleanup at named transaction boundaries. No fault hooks are installed in
the API or production executor. These fixtures use synthetic data and teaching
keys, and never connect to a caller-supplied database.
"""
from __future__ import annotations

import multiprocessing
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .atomic_execution import AtomicExecutor
from .exact_action import ActionProposal, ApprovalAuthority, ExecutionDenied, _canonical_digest
from .profiles import ApplicationProfile
from .sql_backend import open_sqlite

TOKEN = "synthetic-resilience-writer"
NOW = 3_000_000.0
CRASH_EXIT = 86
CRASH_POINTS = ("after_intent", "after_mutation", "after_outcome", "after_commit")


@dataclass(frozen=True)
class ResilienceReport:
    profile_id: str
    profile_sha256: str
    implementation_sha256: str
    transition: dict
    process_races: tuple[dict, ...]
    crash_recovery: tuple[dict, ...]
    passed: bool
    schema_version: str = "1.0"
    bounds: tuple[str, ...] = (
        "Synthetic fixtures using one transition from the supplied profile and teaching keys.",
        "Independent spawned processes and connections on one local SQLite WAL database.",
        "Abrupt process exit skips cleanup; power loss, filesystem corruption and host failure are not tested.",
        "No PostgreSQL, Redis, Kafka, Spark, Iceberg or external side-effect qualification.",
        "Finite schedules are not a distributed linearizability proof or a security probability.",
    )

    def to_dict(self) -> dict:
        return asdict(self)


def _executor(database, profile):
    return AtomicExecutor(
        database, TOKEN,
        allowed_operations=profile.allowed_operations,
        transition_rules=profile.transition_rules,
        required_approval_roles=profile.required_approval_roles,
    )


def _proposal(profile):
    rule = profile.transitions[0]
    return ActionProposal(
        request_id="resilience-request", requester="synthetic-agent",
        operation=rule.operation, case_id="SYNTHETIC-1", expected_version=1,
        from_status=rule.from_status, to_status=rule.to_status,
        evidence_version="synthetic-snapshot-1",
    )


def _approve(profile, proposal):
    return ApprovalAuthority().approve(
        proposal, approver="synthetic-reviewer",
        approver_role=profile.transitions[0].approval_role, now=NOW,
    )


def _seed(path, proposal):
    database = open_sqlite(path, evidence_token=TOKEN)
    try:
        with database.transaction() as unit:
            unit.register.seed(proposal.case_id, status=proposal.from_status, version=1)
    finally:
        database.close()


def _snapshot(database, proposal):
    with database.transaction() as unit:
        records = unit.evidence.records()
        state = unit.register.get(proposal.case_id)
        # Verify a complete pair and its receipt, not only a syntactically valid chain.
        pair_valid = False
        if len(records) == 2 and [r.kind for r in records] == ["action_intent", "action_outcome"]:
            intent, outcome = (r.payload for r in records)
            receipt = unit.register.result_for(intent["request_id"])
            pair_valid = (
                receipt is not None
                and intent["request_id"] == outcome["request_id"] == receipt.request_id
                and outcome["receipt_hash"] == receipt.receipt_hash
                and outcome["case_id"] == receipt.case_id == proposal.case_id
                and outcome["version"] == receipt.version == state["version"]
                and outcome["status"] == receipt.status == state["status"]
                and intent["proposal_digest"] == replace(proposal, request_id=receipt.request_id).digest
                and receipt.proposal_digest == intent["proposal_digest"]
            )
        return {
            "state": state,
            "mutations": unit.register.mutation_count,
            "intent_records": sum(r.kind == "action_intent" for r in records),
            "outcome_records": sum(r.kind == "action_outcome" for r in records),
            "evidence_valid": unit.evidence.verify(),
            "complete_receipt_pair": pair_valid,
            "approval_uses": unit.one(f"SELECT COUNT(*) FROM {unit.table('approval_uses')}")[0],
            "execution_results": unit.one(f"SELECT COUNT(*) FROM {unit.table('execution_results')}")[0],
            "pending_outcomes": len(unit.outbox),
        }


def _is_complete(snapshot, proposal):
    return (
        snapshot["state"] == {"status": proposal.to_status, "version": 2}
        and snapshot["mutations"] == snapshot["intent_records"] == snapshot["outcome_records"] == 1
        and snapshot["approval_uses"] == snapshot["execution_results"] == 1
        and snapshot["pending_outcomes"] == 0
        and snapshot["evidence_valid"] and snapshot["complete_receipt_pair"]
    )


def _is_untouched(snapshot, proposal):
    return (
        snapshot["state"] == {"status": proposal.from_status, "version": 1}
        and all(snapshot[key] == 0 for key in (
            "mutations", "intent_records", "outcome_records", "approval_uses",
            "execution_results", "pending_outcomes",
        ))
        and snapshot["evidence_valid"]
    )


def _race_worker(path, profile, proposal, approval, gate, sender):
    database = None
    try:
        database = open_sqlite(path, evidence_token=TOKEN)
        gate.wait(timeout=20)
        result = _executor(database, profile).execute(proposal, approval, now=NOW + 1)
        sender.send({"code": "EXECUTED", "result": asdict(result), "pid": os.getpid()})
    except ExecutionDenied as exc:
        sender.send({"code": exc.code, "pid": os.getpid()})
    except Exception as exc:
        sender.send({"code": "WORKER_ERROR", "error": type(exc).__name__, "pid": os.getpid()})
    finally:
        if database is not None:
            database.close()
        sender.close()


def _stop_workers(processes):
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)


def _run_race(context, path, profile, callers, distinct):
    proposal = _proposal(profile)
    approval = _approve(profile, proposal)
    _seed(path, proposal)
    gate = context.Barrier(callers)
    processes, receivers = [], []
    observations = []
    try:
        for index in range(callers):
            item = replace(proposal, request_id=f"request-{index}") if distinct else proposal
            permission = _approve(profile, item) if distinct else approval
            receiver, sender = context.Pipe(duplex=False)
            process = context.Process(
                target=_race_worker, args=(path, profile, item, permission, gate, sender),
            )
            process.start()
            sender.close()
            processes.append(process)
            receivers.append(receiver)
        deadline = time.monotonic() + 35
        for process in processes:
            process.join(timeout=max(0, deadline - time.monotonic()))
        for receiver in receivers:
            try:
                observations.append(receiver.recv() if receiver.poll() else {"code": "WORKER_TIMEOUT"})
            except EOFError:
                observations.append({"code": "WORKER_EXITED_WITHOUT_RESULT"})
        exits = [process.exitcode for process in processes]
    finally:
        _stop_workers(processes)
        for receiver in receivers:
            receiver.close()
    database = open_sqlite(path, evidence_token=TOKEN)
    try:
        snapshot = _snapshot(database, proposal)
    finally:
        database.close()
    completed = [item["result"] for item in observations if item["code"] == "EXECUTED"]
    replayed = sum(item["replayed"] for item in completed)
    conflicts = sum(item["code"] == "CASE_VERSION_CONFLICT" for item in observations)
    receipts = len({item["receipt_hash"] for item in completed})
    independent = len({item.get("pid") for item in observations if item.get("pid")})
    expected = (len(completed) == 1 and conflicts == callers - 1 and replayed == 0) if distinct else (
        len(completed) == callers and replayed == callers - 1 and conflicts == 0
    )
    return {
        "scenario": "competing_versions" if distinct else "duplicate_request",
        "callers": callers, "independent_processes": independent,
        "executions_returned": len(completed), "replayed": replayed,
        "version_conflicts": conflicts, "distinct_receipts": receipts,
        "unexpected_codes": [item["code"] for item in observations
                             if item["code"] not in {"EXECUTED", "CASE_VERSION_CONFLICT"}],
        "exit_codes": exits, "snapshot": snapshot,
        "passed": expected and receipts == 1 and independent == callers
                  and all(code == 0 for code in exits) and _is_complete(snapshot, proposal),
    }


def _crash_worker(path, profile, proposal, approval, point):
    database = open_sqlite(path, evidence_token=TOKEN)
    original_transaction = database.transaction

    @contextmanager
    def crashing_transaction():
        with original_transaction() as unit:
            append = unit.evidence.append
            transition = unit.register.transition

            def crash_append(kind, payload, *, token):
                result = append(kind, payload, token=token)
                if (point, kind) in {("after_intent", "action_intent"), ("after_outcome", "action_outcome")}:
                    os._exit(CRASH_EXIT)
                return result

            def crash_transition(item):
                result = transition(item)
                if point == "after_mutation":
                    os._exit(CRASH_EXIT)
                return result

            unit.evidence.append = crash_append
            unit.register.transition = crash_transition
            yield unit
        if point == "after_commit":
            os._exit(CRASH_EXIT)

    # Fault injection is private to this synthetic child, never a runtime feature.
    database.transaction = crashing_transaction
    _executor(database, profile).execute(proposal, approval, now=NOW + 1)
    database.close()
    raise RuntimeError("crash checkpoint was not reached")


def _run_crash(context, path, profile, point):
    proposal = _proposal(profile)
    approval = _approve(profile, proposal)
    _seed(path, proposal)
    process = context.Process(target=_crash_worker, args=(path, profile, proposal, approval, point))
    process.start()
    try:
        process.join(timeout=30)
        exit_code = process.exitcode
    finally:
        _stop_workers([process])
    database = open_sqlite(path, evidence_token=TOKEN)
    try:
        before_retry = _snapshot(database, proposal)
        expected_commit = point == "after_commit"
        recovered = _is_complete(before_retry, proposal) if expected_commit else _is_untouched(before_retry, proposal)
        result = _executor(database, profile).execute(proposal, approval, now=NOW + 2)
        after_retry = _snapshot(database, proposal)
    finally:
        database.close()
    return {
        "checkpoint": point, "exit_code": exit_code,
        "before_retry": before_retry, "after_retry": after_retry,
        "retry_replayed": result.replayed,
        "passed": exit_code == CRASH_EXIT and recovered
                  and result.replayed == expected_commit and _is_complete(after_retry, proposal),
    }


def run_resilience(profile: ApplicationProfile, callers: int = 8) -> ResilienceReport:
    """Run two process races and four abrupt-exit recovery scenarios.

    CLI entry points are safe under spawn. Python callers must use the usual
    ``if __name__ == '__main__'`` guard. Only the first transition is exercised;
    passing this suite does not qualify every transition in a custom profile.
    """
    if isinstance(callers, bool) or not isinstance(callers, int) or not 2 <= callers <= 32:
        raise ValueError("callers must be an integer between 2 and 32")
    if not profile.transitions:
        raise ValueError("profile must declare at least one transition")
    context = multiprocessing.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="fssaira-resilience-") as directory:
        root = Path(directory)
        races = tuple(_run_race(context, str(root / f"race-{distinct}.sqlite"), profile, callers, distinct)
                      for distinct in (False, True))
        crashes = tuple(_run_crash(context, str(root / f"{point}.sqlite"), profile, point)
                        for point in CRASH_POINTS)
    return ResilienceReport(
        profile_id=profile.profile_id, profile_sha256=_canonical_digest(asdict(profile)),
        implementation_sha256=_canonical_digest({
            name: (Path(__file__).parent / name).read_text(encoding="utf-8")
            for name in ("resilience.py", "atomic_execution.py", "sql_backend.py",
                         "exact_action.py", "profiles.py", "evidence.py")
        }),
        transition=asdict(profile.transitions[0]),
        process_races=races, crash_recovery=crashes,
        passed=all(item["passed"] for item in (*races, *crashes)),
    )
