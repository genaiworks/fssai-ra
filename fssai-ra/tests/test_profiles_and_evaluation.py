import json

import pytest

from fssaira import (
    ActionProposal,
    ApplicationProfile,
    ApprovalAuthority,
    CaseRegister,
    EvidenceLedger,
    EvaluationRunner,
    ExecutionDenied,
    ProfileError,
)
from fssaira.cli import main


def test_student_support_profile_loads_and_builds_enforcing_executor():
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    assert profile.profile_id == "student-support"
    assert profile.allowed_operations == {
        "prepare_case_for_review", "return_case_for_correction"
    }
    register = CaseRegister({"S-1": {"status": "draft", "version": 1}})
    ledger = EvidenceLedger("token")
    executor = profile.make_executor(register, ledger, "token")
    proposal = ActionProposal(
        "req", "agent", "prepare_case_for_review", "S-1", 1,
        "draft", "not-in-profile", "snapshot",
    )
    approval = ApprovalAuthority().approve(proposal, approver="officer", now=1000)
    with pytest.raises(ExecutionDenied) as exc:
        executor.execute(proposal, approval, now=1001)
    assert exc.value.code == "TRANSITION_NOT_ALLOWED"


def test_profile_requires_the_authenticated_approval_role():
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    register = CaseRegister({"S-1": {"status": "draft", "version": 1}})
    ledger = EvidenceLedger("token")
    executor = profile.make_executor(register, ledger, "token")
    proposal = ActionProposal(
        "req-role", "agent", "prepare_case_for_review", "S-1", 1,
        "draft", "ready_for_officer_review", "snapshot",
    )
    approval = ApprovalAuthority().approve(
        proposal, approver="reviewer", approver_role="unauthorized_role", now=1000
    )
    with pytest.raises(ExecutionDenied) as exc:
        executor.execute(proposal, approval, now=1001)
    assert exc.value.code == "APPROVER_ROLE_NOT_ALLOWED"
    assert register.mutation_count == 0


@pytest.mark.parametrize(
    "raw, phrase",
    [
        ({}, "missing required fields"),
        ({
            "profile_id": "x", "version": "1", "title": "X",
            "resource_name": "item", "owner": "owner", "manual_fallback": "manual",
            "transitions": "not-a-list",
        }, "transitions must be a list"),
    ],
)
def test_invalid_profiles_fail_closed(raw, phrase):
    with pytest.raises(ProfileError, match=phrase):
        ApplicationProfile.from_dict(raw)


def test_evaluation_runner_contains_every_declared_scenario():
    report = EvaluationRunner(ApplicationProfile.load("profiles/student_support.yaml")).run()
    assert report.total == 8
    assert report.passed == 8
    assert report.all_contained
    assert all(item.evidence_valid for item in report.scenarios)


def test_cli_writes_machine_readable_report(tmp_path):
    destination = tmp_path / "report.json"
    assert main([
        "evaluate", "profiles/student_support.yaml", "--output", str(destination)
    ]) == 0
    report = json.loads(destination.read_text())
    assert report["summary"] == {"passed": 8, "total": 8, "all_contained": True}


def test_cli_validates_profile_and_control_contract(capsys):
    assert main(["validate-profile", "profiles/student_support.yaml"]) == 0
    assert "valid profile" in capsys.readouterr().out
    assert main(["validate-contract", "contract"]) == 0
    assert "valid contract" in capsys.readouterr().out
