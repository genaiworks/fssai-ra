"""Every shipped profile is at or above the kernel floor, and its failure tests run.

Each control contract in ``profiles/*.yaml`` names one of the functions below as
its ``failure_test``. Each function drives *every* consequential transition of its
profile through the real control plane and checks the four ways authority can be
faked: no approval, the wrong role, the proposer approving itself, and a proposal
changed after approval. The correct role then succeeds, so the refusals are not
an artefact of a broken fixture.
"""
from dataclasses import replace
from pathlib import Path

import pytest

from fssaira import ApplicationProfile, ControlPlane, ExecutionDenied
from fssaira.pack_floor import check_pack, load_governed_pack, read_pack

PROFILES = sorted(Path("profiles").glob("*.yaml"))


def _exercise_every_consequential_transition(path: str) -> int:
    profile = ApplicationProfile.load(path)
    checked = 0
    for index, rule in enumerate(profile.transitions):
        if not rule.consequential:
            continue
        roles = sorted(profile.required_approval_roles[(rule.operation, rule.from_status,
                                                        rule.to_status)])
        plane = ControlPlane(profile)
        resource = f"R-{index}"
        plane.register_resource(resource, status=rule.from_status)

        def propose(request_id, plane=plane, rule=rule, resource=resource):
            return plane.propose(
                request_id=request_id, requester="proposer-1", operation=rule.operation,
                resource_id=resource, from_status=rule.from_status, to_status=rule.to_status,
                evidence_version="floor-test")

        # 1. No approval at all.
        propose("no-approval")
        with pytest.raises(ExecutionDenied):
            plane.execute("no-approval")

        # 2. An approval from a role the profile does not name.
        propose("wrong-role")
        plane.approve("wrong-role", approver="someone", approver_role="not-an-approver")
        with pytest.raises(ExecutionDenied):
            plane.execute("wrong-role")

        # 3. The proposer approving its own proposal, whatever role it claims.
        propose("self-approval")
        with pytest.raises(ExecutionDenied):
            plane.approve("self-approval", approver="proposer-1", approver_role=roles[0])
            plane.execute("self-approval")

        # 4. A proposal changed after it was approved.
        original = propose("tampered")
        approval = plane.authority.approve(original, approver="officer-1", approver_role=roles[0])
        with pytest.raises(ExecutionDenied):
            plane.executor.execute(replace(original, evidence_version="swapped-after-review"),
                                   approval)

        # Positive control: the named role succeeds exactly once.
        assert plane.register.get(resource)["status"] == rule.from_status
        propose("correct")
        plane.approve("correct", approver="officer-1", approver_role=roles[0])
        result = plane.execute("correct")
        assert result.status == rule.to_status and not result.replayed
        assert plane.execute("correct").replayed
        checked += 1
    assert checked, f"{path} declares no consequential transition"
    return checked


def test_student_support_controls_refuse_unauthorized_execution():
    _exercise_every_consequential_transition("profiles/student_support.yaml")


def test_academic_record_correction_controls_refuse_unauthorized_execution():
    _exercise_every_consequential_transition("profiles/academic_record_correction.yaml")


def test_corporate_confidential_data_controls_refuse_unauthorized_execution():
    _exercise_every_consequential_transition("profiles/corporate_confidential_data.yaml")


def test_financial_consumer_data_controls_refuse_unauthorized_execution():
    _exercise_every_consequential_transition("profiles/financial_consumer_data.yaml")


def test_government_benefits_controls_refuse_unauthorized_execution():
    _exercise_every_consequential_transition("profiles/government_benefits.yaml")


def test_healthcare_record_access_controls_refuse_unauthorized_execution():
    _exercise_every_consequential_transition("profiles/healthcare_record_access.yaml")


def test_template_controls_refuse_unauthorized_execution():
    _exercise_every_consequential_transition("profiles/template.yaml")


@pytest.mark.parametrize("path", PROFILES, ids=[p.stem for p in PROFILES])
def test_every_shipped_profile_meets_the_kernel_floor(path):
    findings = check_pack(read_pack(path))
    assert not findings, "\n".join(f"{f.code} {f.where}: {f.detail}" for f in findings)
    assert load_governed_pack(path).controls


@pytest.mark.parametrize("path", PROFILES, ids=[p.stem for p in PROFILES])
def test_every_transition_control_names_its_own_profile_test(path):
    """Transition contracts point at this profile's test; data capabilities at the kernel's."""
    from fssaira.pack_floor import DATA_CAPABILITIES

    pack = load_governed_pack(path)
    expected = f"tests/test_profile_floor.py::test_{path.stem}_controls_refuse_unauthorized_execution"
    for name, contract in pack.controls.items():
        if name not in DATA_CAPABILITIES:
            assert contract["failure_test"] == expected, name


def test_the_runtime_refuses_to_start_with_a_weakened_pack(monkeypatch):
    from fssaira.pack_floor import PackRejected
    from fssaira.runtime_factory import build_control_plane

    monkeypatch.delenv("FSSAI_DATABASE_URL", raising=False)
    monkeypatch.delenv("FSSAI_REDIS_URL", raising=False)
    monkeypatch.delenv("FSSAI_KAFKA_BOOTSTRAP", raising=False)
    monkeypatch.setenv("FSSAI_MODEL", "deterministic")
    with pytest.raises(PackRejected):
        build_control_plane(profile_path="conference/attacks/malicious-domain-pack.yaml")
    assert build_control_plane(profile_path="profiles/student_support.yaml").profile


def test_a_deployed_image_checks_failure_tests_against_its_manifest(tmp_path, monkeypatch):
    """No tests/ directory at runtime: the build-time manifest is consulted instead."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "failure_test_manifest", Path("scripts/failure_test_manifest.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = tmp_path / "failure-tests.txt"
    manifest.write_text("\n".join(module.manifest(Path("tests"))))
    monkeypatch.setenv("FSSAI_FAILURE_TEST_MANIFEST", str(manifest))
    raw = read_pack("profiles/student_support.yaml")
    assert check_pack(raw, repo_root=tmp_path) == []          # found via the manifest
    manifest.write_text("")
    codes = {f.code for f in check_pack(raw, repo_root=tmp_path)}
    assert codes == {"PACK_FAILURE_TEST_MISSING"}              # and refused without it
