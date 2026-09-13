"""Governed disclosure: a model may request information, it cannot manufacture
the entitlement to see it, and it cannot launder what it saw.

These tests run the same generated suite against every domain pack that declares
a ``disclosure`` section, then pin the individual properties an adopter is most
likely to weaken by accident.
"""
import json
from dataclasses import replace

import pytest

from fssaira.cli import main
from fssaira.disclosure import (
    ALL_CHECKS,
    DataLabel,
    DisclosureCode,
    DisclosureDenied,
    DisclosurePolicy,
    DisclosurePolicyError,
)
from fssaira.disclosure_eval import (
    AGENT,
    ARMS,
    NOW,
    REVIEWER,
    SUBJECT_A,
    DisclosureFixture,
    run_disclosure_suite,
    verify_disclosure_space,
)
from fssaira.evidence import EvidenceError, EvidenceLedger
from fssaira.exact_action import ActionProposal, ApprovalAuthority, CaseRegister
from fssaira.profiles import ApplicationProfile, ProfileError

PACKS = (
    "profiles/healthcare_record_access.yaml",
    "profiles/corporate_confidential_data.yaml",
)


def _policy(path: str = PACKS[0]) -> DisclosurePolicy:
    return ApplicationProfile.load(path).disclosure


@pytest.fixture(scope="module", params=PACKS)
def suite(request):
    profile = ApplicationProfile.load(request.param)
    return run_disclosure_suite(profile.disclosure, profile_id=profile.profile_id)


def test_every_hostile_disclosure_scenario_is_contained_in_every_pack(suite):
    assert suite.hostile_total >= 20
    assert suite.contained("this_architecture") == suite.hostile_total
    assert suite.benign_completed == len(suite.benign) >= 2
    assert suite.holds


def test_conventional_access_control_leaves_harms_this_architecture_contains(suite):
    """The comparison is the argument: signed, class-cleared grants are not enough."""
    assert suite.contained("unguarded") == 0
    assert suite.contained("access_controlled") < suite.hostile_total
    leaked = {name for name, row in suite.arms["access_controlled"].items() if row["reached"]}
    for expected in ("summary_laundering_with_self_label", "purpose_switch_on_valid_grant",
                     "consent_withdrawn_after_grant", "restricted_data_to_disallowed_endpoint",
                     "release_after_consent_withdrawn", "release_after_grant_revoked"):
        assert expected in leaked


def test_every_disclosure_check_is_load_bearing(suite):
    assert [row["check"] for row in suite.ablations] == list(ALL_CHECKS)
    assert all(row["load_bearing"] for row in suite.ablations), [
        row["check"] for row in suite.ablations if not row["load_bearing"]
    ]


@pytest.mark.parametrize("path", PACKS)
def test_disclosure_bounded_model_check_holds(path):
    report = verify_disclosure_space(_policy(path), profile_id=path)
    assert report.holds, report.to_dict()["violations"][:5]
    assert report.read_states >= 2000
    assert report.release_states > 0
    assert report.released >= 1


def test_evidence_never_contains_protected_values(suite):
    assert suite.evidence_minimized
    assert suite.evidence_chain_valid


def test_model_claimed_label_cannot_launder_a_summary():
    fx = DisclosureFixture(_policy())
    gate = fx.gate(ARMS["this_architecture"])
    fx.read(gate, fx.grant())
    output = gate.derive_output(requester=AGENT, session_id="session-1",
                                content="an innocuous-looking summary",
                                claimed_label=DataLabel.bottom(fx.policy))
    assert output.label.classes == fx.honest_label().classes
    assert gate._evidence.find("output_labelled")[-1].payload["claimed_downgrade_attempt"]

    recipient, purpose = fx.laundering_recipient()
    with pytest.raises(DisclosureDenied):
        gate.release(output, recipient=recipient, purpose=purpose, now=NOW + 2)
    forged = replace(output, label=DataLabel.bottom(fx.policy))
    with pytest.raises(DisclosureDenied) as denied:
        gate.release(forged, recipient=recipient, purpose=purpose, now=NOW + 2)
    assert denied.value.code == DisclosureCode.OUTPUT_UNKNOWN


def test_declassification_requires_exact_independent_approval():
    fx = DisclosureFixture(_policy())
    rule, recipient, purpose, fields, endpoint = fx.declassification_path()
    gate = fx.gate(ARMS["this_architecture"])
    grant = fx.grant(purpose=purpose, fields=fields,
                     classes={fx.policy.field_classes[f] for f in fields})
    context = fx.read(gate, grant, purpose=purpose, fields=fields, model_endpoint=endpoint)
    output = gate.derive_output(requester=AGENT, session_id="session-1",
                                content=f"{SUBJECT_A} " + " ".join(context.values.values()))

    self_approval = fx.declassifier.approve(output, rule=rule.name, approver=AGENT,
                                            approver_role=rule.approval_role, now=NOW)
    with pytest.raises(DisclosureDenied) as denied:
        gate.declassify(output, rule=rule.name, approval=self_approval, now=NOW + 1)
    assert denied.value.code == DisclosureCode.DECLASSIFICATION_SELF_APPROVED

    approval = fx.declassifier.approve(output, rule=rule.name, approver=REVIEWER,
                                       approver_role=rule.approval_role, now=NOW)
    lowered = gate.declassify(output, rule=rule.name, approval=approval, now=NOW + 1)
    assert lowered.label.classes == {rule.to_class}
    assert not lowered.label.subjects
    assert SUBJECT_A not in lowered.content
    assert not any(value in lowered.content for value in context.values.values())
    assert gate.release(lowered, recipient=recipient, purpose=purpose, now=NOW + 2)

    # The approval named one exact output. Reusing it on another output fails.
    other = gate.derive_output(requester=AGENT, session_id="session-1", content="different")
    with pytest.raises(DisclosureDenied) as denied:
        gate.declassify(other, rule=rule.name, approval=approval, now=NOW + 1)
    assert denied.value.code == DisclosureCode.DECLASSIFICATION_WRONG_OUTPUT


def test_break_glass_opens_review_obligation_and_blocks_repeat():
    fx = DisclosureFixture(_policy())
    rule = fx.policy.break_glass
    gate = fx.gate(ARMS["this_architecture"])
    first = fx.break_glass_grant("bg-1")
    fx.read(gate, first, purpose=first.purpose)
    assert gate.open_break_glass == {"bg-1": AGENT}
    assert len(gate._evidence.find("break_glass_review_due")) == 1

    second = fx.break_glass_grant("bg-2")
    with pytest.raises(DisclosureDenied) as denied:
        fx.read(gate, second, purpose=second.purpose, session_id="s2")
    assert denied.value.code == DisclosureCode.BREAK_GLASS_REVIEW_OVERDUE

    with pytest.raises(DisclosureDenied):
        gate.record_break_glass_review("bg-1", reviewer=AGENT, reviewer_role=rule.review_role,
                                       finding="I reviewed myself")
    gate.record_break_glass_review("bg-1", reviewer=REVIEWER, reviewer_role=rule.review_role,
                                   finding="justified")
    assert fx.read(gate, second, purpose=second.purpose, session_id="s2")


def test_consent_withdrawal_and_revocation_take_effect_at_next_read():
    fx = DisclosureFixture(_policy(PACKS[1]))
    gate = fx.gate(ARMS["this_architecture"])
    grant = fx.grant()
    assert fx.read(gate, grant)

    gate.withdraw_consent(SUBJECT_A, fx.purpose, recorded_by="privacy-office")
    with pytest.raises(DisclosureDenied) as denied:
        fx.read(gate, grant)
    assert denied.value.code == DisclosureCode.CONSENT_WITHDRAWN

    gate.consent.restore(SUBJECT_A, fx.purpose)
    gate.revoke_grant(grant.grant_id, by="data-owner", reason="project closed")
    with pytest.raises(DisclosureDenied) as denied:
        fx.read(gate, grant)
    assert denied.value.code == DisclosureCode.GRANT_REVOKED


@pytest.mark.parametrize("path", PACKS)
def test_random_operation_sequences_agree_with_the_reference_model(path):
    """Sequences expose what single-step enumeration cannot: state changing between steps."""
    from fssaira.disclosure_stateful import run_stateful

    report = run_stateful(_policy(path), sequences=120, steps=40)
    assert report.holds, report.to_dict()["first_disagreements"][:2]
    assert report.released["read"] > 0 and report.released["release"] > 0


@pytest.mark.parametrize("mutate,code", [
    (lambda gate, fx, grant: gate.withdraw_consent(SUBJECT_A, fx.purpose, recorded_by="p"),
     DisclosureCode.RELEASE_CONSENT_WITHDRAWN),
    (lambda gate, fx, grant: gate.revoke_grant(grant.grant_id, by="owner", reason="ended"),
     DisclosureCode.RELEASE_GRANT_NO_LONGER_CURRENT),
])
def test_release_rechecks_consent_and_revocation_after_the_read(mutate, code):
    """The defect the stateful harness found on its first run, kept as a regression."""
    fx = DisclosureFixture(_policy())
    gate = fx.gate(ARMS["this_architecture"])
    grant = fx.grant()
    fx.read(gate, grant)
    output = gate.derive_output(requester=AGENT, session_id="session-1", content="summary")
    mutate(gate, fx, grant)
    with pytest.raises(DisclosureDenied) as denied:
        gate.release(output, recipient=fx.cleared_recipient, purpose=fx.purpose, now=NOW + 2)
    assert denied.value.code == code


def test_release_after_grant_expiry_is_refused():
    fx = DisclosureFixture(_policy(PACKS[1]))
    gate = fx.gate(ARMS["this_architecture"])
    grant = fx.grant()
    fx.read(gate, grant)
    output = gate.derive_output(requester=AGENT, session_id="session-1", content="summary")
    with pytest.raises(DisclosureDenied) as denied:
        gate.release(output, recipient=fx.cleared_recipient, purpose=fx.purpose,
                     now=grant.expires_at + 1)
    assert denied.value.code == DisclosureCode.RELEASE_GRANT_NO_LONGER_CURRENT


def test_intent_evidence_failure_releases_nothing():
    class Unavailable(EvidenceLedger):
        def append(self, kind, payload, *, token):
            raise EvidenceError("down")

    fx = DisclosureFixture(_policy())
    gate = fx.gate(ARMS["this_architecture"], ledger=Unavailable("disclosure-evidence-writer"))
    with pytest.raises(DisclosureDenied) as denied:
        fx.read(gate, fx.grant())
    assert denied.value.code == DisclosureCode.EVIDENCE_UNAVAILABLE
    assert not gate._sessions


def test_requests_must_name_subjects_and_fields_and_endpoints_must_be_declared():
    fx = DisclosureFixture(_policy())
    gate = fx.gate(ARMS["this_architecture"])
    with pytest.raises(DisclosureDenied) as denied:
        fx.read(gate, fx.grant(), fields=[])
    assert denied.value.code == DisclosureCode.FIELD_NOT_MINIMUM_NECESSARY
    with pytest.raises(DisclosureDenied) as denied:
        fx.read(gate, fx.grant(), model_endpoint="shadow-it-endpoint")
    assert denied.value.code == DisclosureCode.ENDPOINT_UNDECLARED


def test_label_join_only_tightens():
    policy = _policy()
    bottom = DataLabel.bottom(policy)
    a = DataLabel(frozenset({"highly-restricted"}), frozenset({"p1"}),
                  frozenset({"treatment"}), frozenset({"on-premises"}))
    b = DataLabel(frozenset({"synthetic-health-record"}), frozenset({"p2"}),
                  frozenset({"treatment", "research"}), frozenset({"on-premises", "approved-cloud"}))
    joined = a.join(b)
    for part in (bottom, a, b):
        assert joined.dominates(part)
        assert part.join(bottom) == part
    assert joined == b.join(a)


def _raw(path=PACKS[0]):
    import yaml
    return yaml.safe_load(open(path, encoding="utf-8"))


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d["disclosure"]["fields"].update({"x": {"class": "undeclared-class"}}),
     "does not declare"),
    (lambda d: d["disclosure"]["break_glass"].update({"review_role": "nobody"}),
     "not declared by any transition"),
    (lambda d: d["disclosure"]["declassification"][0].update({"approval_role": "nobody"}),
     "no transition declares"),
    (lambda d: d["disclosure"]["class_zones"].pop("highly-restricted"),
     "missing: highly-restricted"),
    (lambda d: d["disclosure"]["recipients"]["research_team"].update({"purposes": ["marketing"]}),
     "undeclared purposes"),
])
def test_policy_rejects_undeclared_classes_roles_and_zones(mutate, message):
    raw = _raw()
    mutate(raw)
    with pytest.raises(ProfileError, match=message):
        ApplicationProfile.from_dict(raw)
    with pytest.raises(DisclosurePolicyError):
        DisclosurePolicy.from_dict(raw["disclosure"], data_classes=[], approval_roles=[])


def test_disclosure_requires_governance_context():
    raw = _raw()
    raw.pop("governance")
    with pytest.raises(ProfileError, match="requires a governance context"):
        ApplicationProfile.from_dict(raw)


def test_healthcare_break_glass_review_state_is_reachable():
    """The review transition existed before any transition could reach it."""
    profile = ApplicationProfile.load(PACKS[0])
    reachable = {"draft"}
    changed = True
    while changed:
        changed = False
        for rule in profile.transitions:
            if rule.from_status in reachable and rule.to_status not in reachable:
                reachable.add(rule.to_status)
                changed = True
    assert "emergency_access_pending_review" in reachable
    assert "emergency_access_reviewed" in reachable

    register = CaseRegister({"r": {"status": "identity_verified", "version": 1}})
    executor = profile.make_executor(register, EvidenceLedger("t"), "t")
    proposal = ActionProposal("req", "agent", "declare_break_glass_access", "r", 1,
                              "identity_verified", "emergency_access_pending_review", "snap")
    approval = ApprovalAuthority().approve(proposal, approver="clinician",
                                           approver_role="emergency_access_clinician")
    executor.execute(proposal, approval)
    assert register.get("r")["status"] == "emergency_access_pending_review"


def test_every_domain_pack_reaches_every_declared_status_from_its_start():
    """A status no transition can reach is a control that exists only on paper."""
    from fssaira.profiles import discover_profiles

    for summary in discover_profiles("profiles"):
        profile = ApplicationProfile.load(summary["path"])
        reachable = {profile.transitions[0].from_status}
        changed = True
        while changed:
            changed = False
            for rule in profile.transitions:
                if rule.from_status in reachable and rule.to_status not in reachable:
                    reachable.add(rule.to_status)
                    changed = True
        declared = {r.from_status for r in profile.transitions} | {
            r.to_status for r in profile.transitions}
        assert declared == reachable, (
            f"{profile.profile_id} declares unreachable statuses: {sorted(declared - reachable)}"
        )


def test_disclosure_cli_reports_and_refuses_packs_without_a_policy(tmp_path, capsys):
    output = tmp_path / "disclosure.json"
    assert main(["disclosure", PACKS[0], "--output", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["summary"]["holds"] is True
    assert report["verification"]["summary"]["violations"] == 0

    assert main(["disclosure", "profiles/student_support.yaml"]) == 2
    assert "declares no disclosure section" in capsys.readouterr().out
