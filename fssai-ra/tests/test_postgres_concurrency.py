"""Many writers against one real PostgreSQL: every change once, one valid chain.

Runs only when ``FSSAI_TEST_POSTGRES_URL`` points at a disposable database, e.g.
``postgresql://postgres:pw@127.0.0.1:55441/conc``. SQLite serializes every
transaction and cannot show these races.
"""
import os
import threading
import uuid

import pytest

from fssaira import ApplicationProfile, ControlPlane
from fssaira.atomic_execution import AtomicExecutor, sql_evidence, sql_object_store, sql_register
from fssaira.event_outbox import SqlEventOutbox

URL = os.getenv("FSSAI_TEST_POSTGRES_URL")
pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not URL, reason="set FSSAI_TEST_POSTGRES_URL to a disposable database")]
TOKEN = "concurrency-evidence-writer"


def plane_for(schema):
    from fssaira.sql_backend import open_postgres

    database = open_postgres(URL, schema, evidence_token=TOKEN)
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    return ControlPlane(
        profile, register=sql_register(database), evidence=sql_evidence(database),
        evidence_token=TOKEN, objects=sql_object_store(database),
        events=SqlEventOutbox(database),
        executor=AtomicExecutor(database, TOKEN, allowed_operations=profile.allowed_operations,
                                transition_rules=profile.transition_rules,
                                required_approval_roles=profile.required_approval_roles),
    ), database


def prepare(plane, count):
    ids = []
    for i in range(count):
        plane.register_resource(f"S-{i}", status="draft")
        plane.propose(request_id=f"r-{i}", requester="agent-1", operation="prepare_case_for_review",
                      resource_id=f"S-{i}", from_status="draft",
                      to_status="ready_for_officer_review", evidence_version="v1")
        plane.approve(f"r-{i}", approver="officer-1", approver_role="student_support_officer")
        ids.append(f"r-{i}")
    return ids


def run_parallel(jobs):
    errors = []

    def wrap(job):
        try:
            job()
        except Exception as exc:  # collected and asserted below
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=wrap, args=(job,)) for job in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    return errors


def test_many_writers_on_different_resources_keep_one_valid_chain():
    plane, database = plane_for("conc_" + uuid.uuid4().hex[:8])
    ids = prepare(plane, 64)
    errors = run_parallel([lambda r=r: plane.execute(r) for r in ids])
    assert errors == []
    assert plane.register.mutation_count == 64
    assert plane.evidence.verify()
    with database.transaction() as unit:
        assert unit.events.count() == len(ids) * 4


def test_many_writers_racing_on_one_request_change_it_once():
    plane, _database = plane_for("conc_" + uuid.uuid4().hex[:8])
    [request] = prepare(plane, 1)
    results = []
    errors = run_parallel([lambda: results.append(plane.execute(request)) for _ in range(16)])
    assert errors == []
    assert sum(not r.replayed for r in results) == 1
    assert {r.receipt_hash for r in results} == {results[0].receipt_hash}
    assert plane.get_resource("S-0")["version"] == 2
    assert plane.evidence.verify()


def test_complete_workflows_in_parallel():
    plane, database = plane_for("conc_" + uuid.uuid4().hex[:8])

    def workflow(i):
        plane.register_resource(f"W-{i}", status="draft")
        plane.propose(request_id=f"w-{i}", requester="agent-1", operation="prepare_case_for_review",
                      resource_id=f"W-{i}", from_status="draft",
                      to_status="ready_for_officer_review", evidence_version="v1")
        plane.approve(f"w-{i}", approver="officer-1", approver_role="student_support_officer")
        assert not plane.execute(f"w-{i}").replayed
        assert plane.execute(f"w-{i}").replayed

    errors = run_parallel([lambda i=i: workflow(i) for i in range(32)])
    assert errors == []
    assert plane.register.mutation_count == 32 and plane.evidence.verify()
    with database.transaction() as unit:
        rows = unit.events.all()
    assert len(rows) == 32 * 4 and len({r["seq"] for r in rows}) == len(rows)
