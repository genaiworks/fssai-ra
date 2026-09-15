"""Domain-pack manifests: strict schema, drift against enforced config, and the kernel floor.

A manifest is what a policy leader reads. The profile and disclosure policy are what the
runtime enforces. These tests hold the two together: a manifest that claims a purpose,
recipient, zone, approver, or emergency bound the runtime does not enforce fails to load,
and so does any pack, however well-formed, that sits below the kernel floor.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fssaira.kernel.packs import (
    KERNEL_CAPABILITIES,
    PackCode,
    PackError,
    PackManifest,
    evaluate_pack,
    load_pack,
)
from fssaira.pack_floor import FloorCode

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "packs"
SECTORS = ("healthcare", "corporate", "finance", "benefits", "education")
MALICIOUS = ROOT / "conference" / "attacks" / "malicious-domain-pack.yaml"


def _raw(sector: str) -> dict:
    return yaml.safe_load((PACKS / f"{sector}.pack.yaml").read_text(encoding="utf-8"))


def _absolute_sources(raw: dict) -> dict:
    """Rewrite a shipped manifest's relative sources so a tmp copy still finds them."""
    sources = raw["sources"]
    sources["profiles"] = [str((PACKS / p).resolve()) for p in sources["profiles"]]
    if sources.get("governed_learning_pack"):
        sources["governed_learning_pack"] = str((PACKS / sources["governed_learning_pack"]).resolve())
    return raw


def _write(tmp_path: Path, name: str, document: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _mutated_manifest(tmp_path: Path, sector: str, mutate) -> Path:
    raw = _absolute_sources(_raw(sector))
    mutate(raw)
    return _write(tmp_path, f"{sector}.pack.yaml", raw)


def _mutated_profile(tmp_path: Path, sector: str, mutate_profile, mutate_manifest=None) -> Path:
    """Copy the sector's first profile, weaken it, and point a manifest copy at it."""
    raw = _absolute_sources(_raw(sector))
    source = Path(raw["sources"]["profiles"][0])
    profile = yaml.safe_load(source.read_text(encoding="utf-8"))
    mutate_profile(profile)
    raw["sources"]["profiles"][0] = str(_write(tmp_path, source.name, profile))
    if mutate_manifest:
        mutate_manifest(raw)
    return _write(tmp_path, f"{sector}.pack.yaml", raw)


def _codes(excinfo) -> set[str]:
    return {finding.code for finding in excinfo.value.findings}


# ---------------------------------------------------------------------------
# Shipped packs load through the kernel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sector", SECTORS)
def test_every_shipped_pack_loads_through_the_kernel(sector):
    pack = load_pack(PACKS / f"{sector}.pack.yaml", root=ROOT)
    assert isinstance(pack, PackManifest)
    assert pack.sector == sector
    assert pack.profiles, "a pack must reference at least one enforced profile"
    assert set(KERNEL_CAPABILITIES) <= {c.id for c in pack.capabilities}
    assert pack.tests and pack.limits and pack.fallback


def test_education_pack_binds_two_action_profiles_and_the_governed_learning_pack():
    pack = load_pack(PACKS / "education.pack.yaml", root=ROOT)
    assert {p.profile_id for p in pack.profiles} == {"student-support", "academic-record-correction"}
    assert pack.governed_pack is not None
    assert pack.governed_pack.profile.profile_id == "governed-learning-education"
    assert not any(p.disclosure for p in pack.profiles)
    assert any("disclosure" in limit.lower() for limit in pack.limits)


# ---------------------------------------------------------------------------
# Strict schema
# ---------------------------------------------------------------------------


def test_unknown_manifest_key_is_rejected(tmp_path):
    path = _mutated_manifest(tmp_path, "healthcare", lambda raw: raw.update(floor="off"))
    with pytest.raises(PackError, match="unknown key 'floor'"):
        load_pack(path, root=ROOT)


def test_unknown_nested_key_is_rejected(tmp_path):
    def mutate(raw):
        raw["recipients"]["treating_clinician"]["trusted"] = True

    with pytest.raises(PackError, match="unknown key 'trusted'"):
        load_pack(_mutated_manifest(tmp_path, "healthcare", mutate), root=ROOT)


@pytest.mark.parametrize("key, value", [
    ("sector", ""),
    ("title", "   "),
    ("fallback", ""),
    ("tests", []),
    ("limits", []),
    ("capabilities", []),
    ("transitions", {}),
    ("data_classes", {}),
])
def test_empty_required_field_is_an_open_governance_decision(tmp_path, key, value):
    path = _mutated_manifest(tmp_path, "corporate", lambda raw: raw.update({key: value}))
    with pytest.raises(PackError, match=key):
        load_pack(path, root=ROOT)


@pytest.mark.parametrize("key", ["purposes", "recipients", "declassification", "emergency_access"])
def test_omitting_a_declarable_section_is_not_silently_empty(tmp_path, key):
    path = _mutated_manifest(tmp_path, "corporate", lambda raw: raw.pop(key))
    with pytest.raises(PackError, match=f"missing required key '{key}'"):
        load_pack(path, root=ROOT)


def test_a_named_test_that_does_not_exist_fails_the_pack(tmp_path):
    def mutate(raw):
        raw["tests"].append("tests/test_disclosure.py::test_this_test_was_never_written")

    with pytest.raises(PackError) as excinfo:
        load_pack(_mutated_manifest(tmp_path, "healthcare", mutate), root=ROOT)
    assert PackCode.TEST_MISSING in _codes(excinfo)


def test_a_test_named_only_in_a_comment_does_not_exist(tmp_path):
    def mutate(raw):
        raw["tests"] = ["tests/test_disclosure.py::PACKS"]

    with pytest.raises(PackError) as excinfo:
        load_pack(_mutated_manifest(tmp_path, "healthcare", mutate), root=ROOT)
    assert PackCode.TEST_MISSING in _codes(excinfo)


def test_an_unknown_capability_contract_fails_the_pack(tmp_path):
    path = _mutated_manifest(tmp_path, "finance", lambda raw: raw["capabilities"].append("CAP-NOPE-9"))
    with pytest.raises(PackError) as excinfo:
        load_pack(path, root=ROOT)
    assert PackCode.CAPABILITY_UNKNOWN in _codes(excinfo)


def test_unfilled_placeholders_do_not_load():
    with pytest.raises(PackError) as excinfo:
        load_pack(PACKS / "template.pack.yaml", root=ROOT)
    assert PackCode.PLACEHOLDER in _codes(excinfo)


# ---------------------------------------------------------------------------
# Drift: the manifest can never claim what the runtime does not enforce
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sector, mutate, where", [
    ("healthcare", lambda raw: raw["purposes"].append("marketing"), "purposes"),
    ("healthcare", lambda raw: raw["purposes"].remove("research"), "purposes"),
    ("corporate", lambda raw: raw["recipients"].pop("personal_email"), "recipients"),
    ("corporate", lambda raw: raw["recipients"]["finance_analyst"]["classes"].append("restricted"),
     "recipients.finance_analyst"),
    ("healthcare", lambda raw: raw["data_classes"].update({"highly-restricted": ["on-premises", "approved-cloud"]}),
     "data_classes.highly-restricted"),
    ("finance", lambda raw: raw["transitions"]["approve_credit_limit_change"].update(
        approver_roles=["credit_analyst"]), "transitions.approve_credit_limit_change"),
    ("benefits", lambda raw: raw["transitions"]["open_appeal"].update(consequential=True),
     "transitions.open_appeal"),
    ("benefits", lambda raw: raw["transitions"].update(
        {"auto_grant": {"approver_roles": ["benefit_approver"], "consequential": True}}), "transitions"),
    ("finance", lambda raw: raw["emergency_access"][0].update(max_ttl_seconds=900), "emergency_access"),
    ("corporate", lambda raw: raw["emergency_access"].append({
        "purposes": ["legal-review"], "max_ttl_seconds": 60, "max_unreviewed_per_holder": 1,
        "review_role": "legal_counsel"}), "emergency_access"),
    ("healthcare", lambda raw: raw["declassification"]["deidentify_for_research"].update(
        approval_role="healthcare_privacy_officer"), "declassification"),
    ("education", lambda raw: raw["data_classes"].pop("student-health"), "data_classes"),
])
def test_manifest_drift_from_enforced_configuration_fails(tmp_path, sector, mutate, where):
    with pytest.raises(PackError) as excinfo:
        load_pack(_mutated_manifest(tmp_path, sector, mutate), root=ROOT)
    drift = [f for f in excinfo.value.findings if f.code == PackCode.DRIFT]
    assert drift, excinfo.value.findings
    assert any(f.where.startswith(where) for f in drift), [f.where for f in drift]


# ---------------------------------------------------------------------------
# Kernel floor: a pack cannot weaken it
# ---------------------------------------------------------------------------


def test_the_malicious_domain_pack_cannot_enter_as_a_governed_source(tmp_path):
    def mutate(raw):
        raw["sources"]["governed_learning_pack"] = str(MALICIOUS)

    with pytest.raises(PackError) as excinfo:
        load_pack(_mutated_manifest(tmp_path, "education", mutate), root=ROOT)
    codes = _codes(excinfo)
    for expected in (FloorCode.WEAKENING_KEY, FloorCode.NON_HUMAN_APPROVER,
                     FloorCode.PROTECTED_CLASS_EXTERNAL, FloorCode.BREAK_GLASS_UNBOUNDED,
                     FloorCode.REVIEW_FAILS_OPEN, FloorCode.FALLBACK_MISSING):
        assert expected in codes, expected


def test_the_malicious_domain_pack_cannot_enter_as_a_profile_source(tmp_path):
    def mutate(raw):
        raw["sources"]["profiles"] = [str(MALICIOUS)]

    with pytest.raises(PackError) as excinfo:
        load_pack(_mutated_manifest(tmp_path, "education", mutate), root=ROOT)
    codes = _codes(excinfo)
    assert FloorCode.WEAKENING_KEY in codes
    assert FloorCode.NON_HUMAN_APPROVER in codes
    assert FloorCode.UNKNOWN_KEY in codes


def test_a_manifest_cannot_drop_a_kernel_capability(tmp_path):
    path = _mutated_manifest(tmp_path, "healthcare", lambda raw: raw["capabilities"].remove("CAP-ACT-2"))
    with pytest.raises(PackError) as excinfo:
        load_pack(path, root=ROOT)
    assert PackCode.KERNEL_CAPABILITY_MISSING in _codes(excinfo)


def test_a_disclosure_pack_must_bind_the_disclosure_capabilities(tmp_path):
    path = _mutated_manifest(tmp_path, "benefits", lambda raw: raw["capabilities"].remove("CAP-DIS-2"))
    with pytest.raises(PackError) as excinfo:
        load_pack(path, root=ROOT)
    assert PackCode.KERNEL_CAPABILITY_MISSING in _codes(excinfo)


def _approval_by_model(profile):
    profile["transitions"][1]["approval_role"] = "model"


def _no_fallback(profile):
    profile["manual_fallback"] = "none"


def _unbounded_break_glass(profile):
    profile["disclosure"]["break_glass"]["max_ttl_seconds"] = 10_000_000


def _restricted_in_public_zone(profile):
    profile["disclosure"]["class_zones"]["highly-restricted"].append("external")


def _confidential_in_public_zone(profile):
    profile["disclosure"]["class_zones"]["confidential"].append("external")


def _declassifier_receives_output(profile):
    profile["disclosure"]["recipients"]["data_protection_officer"] = {
        "classes": ["approved-aggregate"], "purposes": ["external-release"], "zone": "corporate-private"}


def _reviewer_is_emergency_holder(profile):
    profile["disclosure"]["break_glass"]["review_role"] = "fraud_investigator"


def _review_not_consequential(profile):
    for rule in profile["transitions"]:
        if rule["operation"] == "record_break_glass_review":
            rule["consequential"] = False


@pytest.mark.parametrize("sector, weaken, code", [
    ("healthcare", _approval_by_model, FloorCode.NON_HUMAN_APPROVER),
    ("corporate", _no_fallback, FloorCode.FALLBACK_MISSING),
    ("healthcare", _unbounded_break_glass, FloorCode.BREAK_GLASS_UNBOUNDED),
    ("healthcare", _restricted_in_public_zone, FloorCode.PROTECTED_CLASS_EXTERNAL),
    ("corporate", _confidential_in_public_zone, PackCode.PUBLIC_ZONE_UNDECLASSIFIED),
    ("corporate", _declassifier_receives_output, PackCode.DECLASSIFIER_NOT_INDEPENDENT),
    ("finance", _reviewer_is_emergency_holder, PackCode.EMERGENCY_REVIEWER_NOT_INDEPENDENT),
    ("healthcare", _review_not_consequential, PackCode.EMERGENCY_REVIEW_NOT_ENFORCED),
])
def test_a_weakened_copy_of_a_real_pack_is_below_the_floor(tmp_path, sector, weaken, code):
    """The floor fires even when the manifest is updated to match the weakened profile.

    Drift detection alone is not enough: an author who edits both files consistently has
    produced an honest manifest of a weak policy. Only the floor stops that.
    """
    path = _mutated_profile(tmp_path, sector, weaken)
    with pytest.raises(PackError) as excinfo:
        load_pack(path, root=ROOT)
    assert code in _codes(excinfo), excinfo.value.findings


def test_floor_findings_are_reported_all_at_once(tmp_path):
    def weaken(profile):
        _approval_by_model(profile)
        _no_fallback(profile)
        _unbounded_break_glass(profile)

    with pytest.raises(PackError) as excinfo:
        load_pack(_mutated_profile(tmp_path, "healthcare", weaken), root=ROOT)
    assert {FloorCode.NON_HUMAN_APPROVER, FloorCode.FALLBACK_MISSING,
            FloorCode.BREAK_GLASS_UNBOUNDED} <= _codes(excinfo)


# ---------------------------------------------------------------------------
# Evaluation keeps units apart
# ---------------------------------------------------------------------------


def test_evaluate_pack_names_units_and_never_pools_profiles():
    pack = load_pack(PACKS / "education.pack.yaml", root=ROOT)
    result = evaluate_pack(pack)
    assert [a.profile_id for a in result.action] == ["student-support", "academic-record-correction"]
    assert result.disclosure == ()
    body = result.to_dict()
    assert body["sector"] == "education"
    for entry in body["action"]:
        for measure in ("states_explored", "scenarios", "benign", "unauthorized_mutations", "violations"):
            assert entry[measure]["unit"], measure
    assert not {"total", "sum", "pooled"} & set(body)


def test_evaluate_pack_runs_disclosure_suite_for_disclosure_profiles():
    pack = load_pack(PACKS / "healthcare.pack.yaml", root=ROOT)
    result = evaluate_pack(pack)
    assert len(result.action) == 1 and len(result.disclosure) == 1
    disclosure = result.disclosure[0]
    assert disclosure.hostile.unit != result.action[0].scenarios.unit
    assert disclosure.hostile.numerator == disclosure.hostile.denominator
    assert disclosure.holds


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

FILLED = {
    "REPLACE_ME_SECTOR": "template-sector",
    "REPLACE_ME_TITLE": "Filled template pack",
    "REPLACE_ME_FALLBACK": "Route the unchanged request to the accountable service owner for staffed handling.",
    "REPLACE_ME_TEST_LOCATOR": "tests/test_profiles_and_evaluation.py::test_evaluation_runner_contains_every_declared_scenario",
    "REPLACE_ME_LIMIT": "Synthetic template only; no sector evidence is claimed.",
}


def test_template_pack_loads_when_placeholders_are_filled(tmp_path):
    text = (PACKS / "template.pack.yaml").read_text(encoding="utf-8")
    assert all(token in text for token in FILLED)
    for token, value in FILLED.items():
        text = text.replace(token, value)
    text = text.replace("REPLACE_ME_PROFILE_PATH", str(ROOT / "profiles" / "template.yaml"))
    values = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    assert not any("REPLACE_ME" in line for line in values)
    path = tmp_path / "filled.pack.yaml"
    path.write_text(text, encoding="utf-8")

    pack = load_pack(path, root=ROOT)
    assert pack.sector == "template-sector"
    assert [p.profile_id for p in pack.profiles] == ["replace-me"]
    result = evaluate_pack(pack)
    assert result.action[0].invariants_hold


def test_every_template_key_is_explained():
    """A template comment precedes every top-level key, so an author never guesses."""
    lines = (PACKS / "template.pack.yaml").read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line and not line.startswith(("#", " ", "-")):
            assert index > 0 and lines[index - 1].lstrip().startswith("#"), line
