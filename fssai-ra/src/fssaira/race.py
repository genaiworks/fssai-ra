"""Bounded concurrent replay test for accountable execution.

This is deliberately narrower than a distributed consistency claim. It asks one
important question an adopter can reproduce: if many callers race the same valid,
approved request through the transactional executor, does the governed resource
change exactly once and does one complete evidence pair survive?
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
import tempfile
import threading
import time

from .atomic_execution import AtomicExecutor
from .exact_action import ActionProposal, ApprovalAuthority
from .profiles import ApplicationProfile
from .sql_backend import open_sqlite


@dataclass(frozen=True)
class RaceReport:
    callers: int
    executions_returned: int
    replayed: int
    mutations: int
    distinct_receipts: int
    intent_records: int
    outcome_records: int
    evidence_valid: bool
    passed: bool
    bounds: str = (
        "one process, one transactional SQLite backend, one approved request; "
        "not a distributed linearizability proof"
    )

    def to_dict(self) -> dict:
        return asdict(self)


def run_replay_race(profile: ApplicationProfile, callers: int = 32) -> RaceReport:
    if callers < 2 or callers > 512:
        raise ValueError("callers must be between 2 and 512")
    token = "race-evidence-writer"
    with tempfile.TemporaryDirectory(prefix="fssaira-race-") as directory:
        database = open_sqlite(str(Path(directory) / "race.sqlite"), evidence_token=token)
        with database.transaction() as unit:
            unit.register.seed("RACE-1", status="draft", version=1)
        executor = AtomicExecutor(
            database,
            token,
            allowed_operations=profile.allowed_operations,
            transition_rules=profile.transition_rules,
            required_approval_roles=profile.required_approval_roles,
        )
        proposal = ActionProposal(
            request_id="race-request-1",
            requester="bounded-agent",
            operation="prepare_case_for_review",
            case_id="RACE-1",
            expected_version=1,
            from_status="draft",
            to_status="ready_for_officer_review",
            evidence_version="race-snapshot-1",
        )
        now = time.time()
        approval = ApprovalAuthority().approve(
            proposal,
            approver="race-reviewer",
            approver_role="student_support_officer",
            now=now,
            ttl_seconds=300,
        )
        gate = threading.Barrier(callers)

        def execute_once():
            gate.wait(timeout=10)
            return executor.execute(proposal, approval, now=now + 1)

        with ThreadPoolExecutor(max_workers=callers) as pool:
            results = list(pool.map(lambda _index: execute_once(), range(callers)))

        with database.transaction() as unit:
            records = unit.evidence.records()
            mutations = unit.register.mutation_count
            evidence_valid = unit.evidence.verify()
        intents = sum(record.kind == "action_intent" for record in records)
        outcomes = sum(record.kind == "action_outcome" for record in records)
        receipts = {result.receipt_hash for result in results}
        replayed = sum(result.replayed for result in results)
        passed = (
            len(results) == callers
            and replayed == callers - 1
            and mutations == 1
            and len(receipts) == 1
            and intents == 1
            and outcomes == 1
            and evidence_valid
        )
        return RaceReport(
            callers=callers,
            executions_returned=len(results),
            replayed=replayed,
            mutations=mutations,
            distinct_receipts=len(receipts),
            intent_records=intents,
            outcome_records=outcomes,
            evidence_valid=evidence_valid,
            passed=passed,
        )


__all__ = ["RaceReport", "run_replay_race"]
