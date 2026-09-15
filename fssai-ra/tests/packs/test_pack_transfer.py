"""Kernel-unchanged transfer: one kernel, many domains, and nothing borrowed between them.

(a) all five shipped packs load and evaluate through the same kernel functions;
(b) a sector that exists only in a temporary directory loads, passes the floor, and
    evaluates without a single byte of the kernel or mediators changing;
(c) the per-pack denominators the kernel reports agree with the committed matrices.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from fssaira.kernel import packs as kernel_packs
from fssaira.kernel.packs import evaluate_pack, load_pack

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "packs"
SECTORS = ("healthcare", "corporate", "finance", "benefits", "education")
MATRIX = ROOT / "evaluation" / "results" / "v1.0.0-domain-pack-matrix.json"
DISCLOSURE_MATRIX = ROOT / "evaluation" / "results" / "v1.0.0-governed-disclosure.json"


def _tree_digest(*directories: Path) -> str:
    digest = hashlib.sha256()
    for directory in directories:
        for path in sorted(directory.rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture(scope="module")
def evaluations():
    return {sector: evaluate_pack(load_pack(PACKS / f"{sector}.pack.yaml", root=ROOT))
            for sector in SECTORS}


def test_all_five_packs_evaluate_through_the_same_kernel_functions(evaluations, monkeypatch):
    calls: list[str] = []
    original = kernel_packs.verify_profile

    def spy(profile):
        calls.append(profile.profile_id)
        return original(profile)

    monkeypatch.setattr(kernel_packs, "verify_profile", spy)
    for sector in SECTORS:
        pack = load_pack(PACKS / f"{sector}.pack.yaml", root=ROOT)
        evaluate_pack(pack)
    assert sorted(calls) == sorted(
        entry.profile_id for result in evaluations.values() for entry in result.action)
    for sector, result in evaluations.items():
        assert result.sector == sector
        assert result.action, sector
        assert all(entry.invariants_hold for entry in result.action), sector
        assert all(entry.unauthorized_mutations.value == 0 for entry in result.action), sector
    assert {s for s, r in evaluations.items() if r.disclosure} == {"healthcare", "corporate", "finance", "benefits"}


def _municipal_profile() -> dict:
    profile = yaml.safe_load((ROOT / "profiles" / "template.yaml").read_text(encoding="utf-8"))
    profile.update(
        profile_id="municipal-building-permits",
        title="Municipal Building Permits",
        resource_name="permit_application",
        owner="permits_service_owner",
        manual_fallback="Leave the application unchanged and route it to the permits counter for staffed review.",
    )
    profile["governance"].update(
        domain="municipal-permits",
        purpose="Route synthetic building-permit applications to named municipal authority.",
        data_classes=["applicant-identity", "site-plans", "public-register-entry"],
    )
    profile["disclosure"] = {
        "subject_kind": "applicant",
        "purposes": ["permit-review", "public-register"],
        "fields": {
            "applicant_name": {"class": "applicant-identity"},
            "site_plan": {"class": "site-plans"},
        },
        "model_endpoints": {"city_model": "city-private", "public_model_api": "external"},
        "class_zones": {
            "applicant-identity": ["city-private"],
            "site-plans": ["city-private"],
            "public-register-entry": ["city-private", "external"],
        },
        "recipients": {
            "plan_examiner": {"classes": ["applicant-identity", "site-plans"],
                              "purposes": ["permit-review"], "zone": "city-private"},
            "public_register": {"classes": ["public-register-entry"],
                                "purposes": ["public-register"], "zone": "external"},
        },
        "declassification": [{
            "name": "publish_register_entry", "from_classes": ["site-plans"],
            "to_class": "public-register-entry", "purposes": ["public-register"],
            "approval_role": "chief_building_official", "removes_subject_identity": True,
        }],
    }
    profile["transitions"] = [
        {"operation": "accept_application", "from_status": "submitted", "to_status": "under_review",
         "consequential": False, "approval_role": "permits_clerk"},
        {"operation": "approve_permit", "from_status": "under_review", "to_status": "approved",
         "consequential": True, "approval_role": "chief_building_official"},
        {"operation": "refuse_permit", "from_status": "under_review", "to_status": "refused",
         "consequential": True, "approval_role": "chief_building_official"},
    ]
    return profile


def _municipal_manifest(profile_path: Path) -> dict:
    return {
        "schema_version": "1.0",
        "sector": "municipal-permits",
        "title": "Municipal building permits (synthetic, created only for the transfer test)",
        "sources": {"profiles": [profile_path.name]},
        "capabilities": ["CAP-ACT-1", "CAP-ACT-2", "CAP-ACT-3", "CAP-EVI-1", "CAP-DIS-1", "CAP-DIS-2"],
        "purposes": ["permit-review", "public-register"],
        "data_classes": {
            "applicant-identity": ["city-private"],
            "site-plans": ["city-private"],
            "public-register-entry": ["city-private", "external"],
        },
        "recipients": {
            "plan_examiner": {"classes": ["applicant-identity", "site-plans"],
                              "purposes": ["permit-review"], "zone": "city-private"},
            "public_register": {"classes": ["public-register-entry"],
                                "purposes": ["public-register"], "zone": "external"},
        },
        "transitions": {
            "accept_application": {"approver_roles": ["permits_clerk"], "consequential": False},
            "approve_permit": {"approver_roles": ["chief_building_official"], "consequential": True},
            "refuse_permit": {"approver_roles": ["chief_building_official"], "consequential": True},
        },
        "declassification": {
            "publish_register_entry": {
                "from_classes": ["site-plans"], "to_class": "public-register-entry",
                "purposes": ["public-register"], "approval_role": "chief_building_official",
                "removes_subject_identity": True,
            },
        },
        "emergency_access": [],
        "fallback": "Leave the application unchanged and route it to the permits counter.",
        "tests": ["tests/packs/test_pack_transfer.py::test_a_new_sector_transfers_without_changing_the_kernel"],
        "limits": ["Synthetic sector created in a temporary directory; no municipal evidence is claimed."],
    }


def test_a_new_sector_transfers_without_changing_the_kernel(tmp_path):
    guarded = (ROOT / "src" / "fssaira" / "kernel", ROOT / "src" / "fssaira" / "mediators")
    before = _tree_digest(*guarded)

    profile_path = tmp_path / "municipal_building_permits.yaml"
    profile_path.write_text(yaml.safe_dump(_municipal_profile(), sort_keys=False), encoding="utf-8")
    manifest_path = tmp_path / "municipal.pack.yaml"
    manifest_path.write_text(yaml.safe_dump(_municipal_manifest(profile_path), sort_keys=False),
                             encoding="utf-8")

    pack = load_pack(manifest_path, root=ROOT)
    result = evaluate_pack(pack)

    assert pack.sector == "municipal-permits"
    (action,) = result.action
    assert action.profile_id == "municipal-building-permits"
    assert action.invariants_hold and action.states_explored.value > 0
    assert action.scenarios.numerator == action.scenarios.denominator > 0
    assert action.unauthorized_mutations.value == 0
    (disclosure,) = result.disclosure
    assert disclosure.hostile.numerator == disclosure.hostile.denominator > 0
    assert disclosure.holds
    assert _tree_digest(*guarded) == before, "transfer to a new sector changed the kernel"


def test_a_new_sector_is_still_held_to_the_floor(tmp_path):
    profile = _municipal_profile()
    profile["disclosure"]["class_zones"]["site-plans"].append("external")
    profile_path = tmp_path / "municipal_building_permits.yaml"
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    manifest = _municipal_manifest(profile_path)
    manifest["data_classes"]["site-plans"].append("external")
    manifest_path = tmp_path / "municipal.pack.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    with pytest.raises(kernel_packs.PackError) as excinfo:
        load_pack(manifest_path, root=ROOT)
    assert kernel_packs.PackCode.PUBLIC_ZONE_UNDECLASSIFIED in {f.code for f in excinfo.value.findings}


def test_pack_action_denominators_agree_with_the_committed_matrix(evaluations):
    committed = {entry["profile_id"]: entry for entry in json.loads(MATRIX.read_text())["profiles"]}
    seen: list[str] = []
    for sector, result in evaluations.items():
        for entry in result.action:
            seen.append(entry.profile_id)
            row = committed[entry.profile_id]
            observed = {
                "states_explored": entry.states_explored.value,
                "violations": entry.violations.value,
                "scenarios_total": entry.scenarios.denominator,
                "scenarios_contained": entry.scenarios.numerator,
                "unauthorized_mutations": entry.unauthorized_mutations.value,
                "benign_total": entry.benign.denominator,
                "benign_completed": entry.benign.numerator,
                "invariants_hold": entry.invariants_hold,
            }
            expected = {key: row[key] for key in observed}
            assert observed == expected, (sector, entry.profile_id)
    assert sorted(seen) == sorted(committed), "each committed profile belongs to exactly one pack"


def test_pack_disclosure_denominators_agree_with_the_committed_matrix(evaluations):
    committed = {entry["profile_id"]: entry for entry in json.loads(DISCLOSURE_MATRIX.read_text())["profiles"]}
    seen: list[str] = []
    for result in evaluations.values():
        for entry in result.disclosure:
            seen.append(entry.profile_id)
            row = committed[entry.profile_id]
            summary = row["summary"]
            assert (entry.hostile.numerator, entry.hostile.denominator) == (
                summary["contained_by_arm"]["this_architecture"], summary["hostile_scenarios"])
            assert (entry.benign.numerator, entry.benign.denominator) == (
                summary["benign_completed"], summary["benign_total"])
            assert (entry.checks.numerator, entry.checks.denominator) == (
                summary["checks_load_bearing"], summary["checks_ablated"])
            assert entry.states_explored.value == row["verification"]["summary"]["states_explored"]
            assert entry.violations.value == row["verification"]["summary"]["violations"]
    assert sorted(seen) == sorted(committed)
