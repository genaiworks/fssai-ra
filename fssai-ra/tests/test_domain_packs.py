import json
from pathlib import Path

import pytest

from fssaira.cli import main
from fssaira.evaluation import EvaluationRunner
from fssaira.exact_action import ActionProposal, ExecutionResult, ResourceRegister
from fssaira.profiles import ApplicationProfile, ProfileError, discover_profiles
from fssaira.verification import verify_profile

PACKS = (
    "profiles/student_support.yaml",
    "profiles/academic_record_correction.yaml",
    "profiles/corporate_confidential_data.yaml",
    "profiles/healthcare_record_access.yaml",
    "profiles/financial_consumer_data.yaml",
    "profiles/government_benefits.yaml",
)


@pytest.mark.parametrize("path", PACKS)
def test_every_shipped_domain_pack_declares_governance_context(path):
    profile = ApplicationProfile.load(path)

    assert profile.governance is not None
    assert profile.governance.purpose
    assert profile.governance.data_classes
    assert profile.governance.applicable_frameworks
    assert profile.governance.prohibited_uses
    assert profile.governance.processing_basis
    assert profile.governance.data_minimization_rule
    assert profile.governance.retention_rule
    assert profile.governance.deletion_rule
    assert profile.governance.residency_rule
    assert profile.governance.incident_response
    assert profile.governance.data_owner
    assert profile.governance.privacy_owner
    assert profile.governance.security_owner


@pytest.mark.parametrize("path", PACKS[2:])
def test_the_same_authority_kernel_holds_outside_education(path):
    profile = ApplicationProfile.load(path)
    verification = verify_profile(profile)
    evaluation = EvaluationRunner(profile).run()

    assert verification.holds, [vars(item) for item in verification.violations]
    assert evaluation.all_contained
    assert evaluation.unauthorized_mutations == 0
    assert evaluation.benign_completed == len(evaluation.utility)
    completed = {item.task for item in evaluation.utility if item.completed}
    for rule in profile.transitions:
        expected = f"{rule.operation}_{rule.from_status}_to_{rule.to_status}"
        assert any(expected in item for item in completed), expected


def test_profile_catalog_validates_and_summarizes_every_pack():
    catalog = discover_profiles("profiles")

    assert {item["profile_id"] for item in catalog} == {
        "student-support", "academic-record-correction",
        "corporate-confidential-data", "healthcare-record-access",
        "financial-consumer-data", "government-benefits",
    }
    assert all(item["domain"] != "undeclared" for item in catalog)
    assert all(item["approval_roles"] for item in catalog)


def test_profile_catalog_fails_closed_for_missing_empty_or_duplicate_catalogs(tmp_path):
    with pytest.raises(ProfileError, match="does not exist"):
        discover_profiles(tmp_path / "missing")
    with pytest.raises(ProfileError, match="contains no domain packs"):
        discover_profiles(tmp_path)

    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(
        "profile_id: legacy\nversion: '1'\ntitle: Legacy\nresource_name: item\n"
        "owner: owner\nmanual_fallback: manual\ntransitions:\n"
        "  - operation: review\n    from_status: draft\n    to_status: reviewed\n"
        "    consequential: true\n    approval_role: reviewer\n",
        encoding="utf-8",
    )
    with pytest.raises(ProfileError, match="must declare a governance context"):
        discover_profiles(tmp_path)
    legacy.unlink()

    source = tmp_path / "one.yaml"
    source.write_text(Path(PACKS[0]).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "two.yaml").write_text(source.read_text(), encoding="utf-8")
    with pytest.raises(ProfileError, match="duplicate profile_id"):
        discover_profiles(tmp_path)


def test_profile_catalog_cli_has_machine_readable_cross_domain_evidence(tmp_path):
    output = tmp_path / "catalog.json"

    assert main(["profiles", "--verify", "--output", str(output)]) == 0
    report = json.loads(output.read_text())

    assert report["count"] == 6
    assert report["profiles"][0]["profile_id"]
    for profile in report["profiles"]:
        assert profile["assurance"]["invariants_hold"] is True
        assert profile["assurance"]["unauthorized_mutations"] == 0
        assert profile["assurance"]["scenarios_contained"] == profile["assurance"][
            "scenarios_total"
        ]
        assert profile["assurance"]["benign_completed"] == profile["assurance"][
            "benign_total"
        ]


def test_governance_context_rejects_empty_or_badly_shaped_declarations():
    raw = {
        "profile_id": "bad", "version": "1", "title": "Bad",
        "resource_name": "resource", "owner": "owner", "manual_fallback": "manual",
        "transitions": [{
            "operation": "review", "from_status": "draft", "to_status": "reviewed",
            "consequential": True, "approval_role": "reviewer",
        }],
        "governance": {
            "domain": "health", "purpose": "testing", "deployment_profile": "certified",
            "data_classes": ["restricted"], "applicable_frameworks": ["local policy"],
            "prohibited_uses": ["unapproved disclosure"],
            "processing_basis": "approved policy",
            "data_minimization_rule": "minimum fields",
            "retention_rule": "declared schedule",
            "deletion_rule": "delete after schedule",
            "residency_rule": "approved systems",
            "incident_response": "contain and notify",
            "owners": {"data": "data", "privacy": "privacy", "security": "security"},
        },
    }

    with pytest.raises(ProfileError, match="deployment_profile"):
        ApplicationProfile.from_dict(raw)


def test_domain_neutral_resource_alias_preserves_wire_compatibility():
    register = ResourceRegister({"asset-1": {"status": "draft", "version": 1}})
    proposal = ActionProposal(
        "request-1", "agent-1", "review", "asset-1", 1,
        "draft", "reviewed", "snapshot-1",
    )
    result = ExecutionResult("request-1", "asset-1", 2, "reviewed", "receipt")

    assert register.get("asset-1")["status"] == "draft"
    assert proposal.resource_id == "asset-1"
    assert result.resource_id == "asset-1"
