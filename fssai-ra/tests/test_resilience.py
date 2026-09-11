"""Independent processes, real abrupt exits and negative controls for the oracle."""
from copy import deepcopy

import pytest

from fssaira.profiles import ApplicationProfile
from fssaira.resilience import (
    CRASH_EXIT,
    CRASH_POINTS,
    _is_complete,
    _is_untouched,
    _proposal,
    run_resilience,
)


@pytest.fixture(scope="module")
def report():
    return run_resilience(ApplicationProfile.load("profiles/student_support.yaml"), callers=8)


def test_process_race_has_independent_connections_and_one_result(report):
    race = report.process_races[0]
    assert race["passed"]
    assert race["independent_processes"] == race["executions_returned"] == 8
    assert race["replayed"] == 7
    assert race["distinct_receipts"] == 1
    assert race["snapshot"]["approval_uses"] == 1


def test_competing_reviewed_versions_fail_without_partial_evidence(report):
    race = report.process_races[1]
    assert race["passed"]
    assert race["version_conflicts"] == 7
    assert race["executions_returned"] == 1
    assert race["replayed"] == 0
    assert race["snapshot"]["intent_records"] == race["snapshot"]["outcome_records"] == 1


@pytest.mark.parametrize("point", CRASH_POINTS)
def test_abrupt_exit_recovers_all_or_nothing_and_retry_is_safe(report, point):
    result = next(item for item in report.crash_recovery if item["checkpoint"] == point)
    assert result["exit_code"] == CRASH_EXIT, "the child must reach the actual crash checkpoint"
    assert result["passed"]
    assert result["retry_replayed"] == (point == "after_commit")
    assert result["after_retry"]["mutations"] == 1
    assert result["before_retry"]["mutations"] == int(point == "after_commit")


@pytest.mark.parametrize("field,value", [
    ("mutations", 2), ("intent_records", 2), ("outcome_records", 0),
    ("evidence_valid", False), ("complete_receipt_pair", False),
    ("approval_uses", 2), ("execution_results", 0), ("pending_outcomes", 1),
    ("state", {"status": "wrong", "version": 2}),
])
def test_oracle_rejects_partial_or_duplicate_commits(report, field, value):
    snapshot = deepcopy(report.process_races[0]["snapshot"])
    snapshot[field] = value
    proposal = _proposal(ApplicationProfile.load("profiles/student_support.yaml"))
    assert not _is_complete(snapshot, proposal)
    assert not _is_untouched(snapshot, proposal)


def test_custom_profile_needs_no_student_specific_names():
    report = run_resilience(ApplicationProfile.load("profiles/template.yaml"), callers=2)
    assert report.passed
    assert report.transition["operation"] == "prepare_for_human_review"
    assert report.transition["approval_role"] == "authorized_reviewer"
    assert report.profile_id == "replace-me"
    assert len(report.bounds) == 5


@pytest.mark.parametrize("callers", [0, 1, 33, True, 2.5, "8"])
def test_resilience_rejects_unbounded_or_non_integer_workers(callers):
    with pytest.raises(ValueError, match="integer between"):
        run_resilience(ApplicationProfile.load("profiles/template.yaml"), callers=callers)


def test_report_is_json_serializable_and_states_limits(report):
    import json

    payload = json.loads(json.dumps(report.to_dict()))
    assert payload["passed"]
    assert "power loss" in " ".join(payload["bounds"])
    assert "No PostgreSQL" in " ".join(payload["bounds"])
