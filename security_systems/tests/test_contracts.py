"""Pack-derived contract tests: the failure tests any domain pack may cite.

A pack's seven-field control contract names a ``failure_test`` that must exist, or the
kernel floor refuses to load the pack. These tests are written against *roles* and
against the pack's own declarations, never against a domain, so a new domain can
cite them and be governed with no Python written for it.

Each test runs for every world in ``worlds/``. Where a test rests on falsifiers, it
requires each one to hold with every control on, to hold again when restored, and to
have at least one ablation row where removing a control lets the harm through. A
contract whose attack nothing can make succeed would prove nothing.
"""
from __future__ import annotations

import pytest
from support import ablation, falsifiers

from trustkernel.delegation_eval import ablate_delegation, run_delegation_suite
from trustkernel.kernel.disclosure import DisclosureDenied
from trustkernel.kernel.evidence import EvidenceLedger
from trustkernel.kernel.exact_action import (
    AccountableExecutor,
    ActionProposal,
    AsymmetricApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
)
from trustkernel.world import ScenarioWorld, WorldSpec, available_worlds

WORLDS = available_worlds()


def _holds_and_bears(world: str, *ids: str) -> None:
    results = falsifiers(world)
    rows = ablation(world)
    for falsifier_id in ids:
        assert results[falsifier_id].held, f"{world}: {falsifier_id} violated with every control on"
        mine = [r for r in rows if r.falsifier == falsifier_id]
        assert mine, f"{falsifier_id} has no ablation rows"
        assert all(r.enabled == 0 and r.restored == 0 for r in mine)
        assert any(r.load_bearing for r in mine), f"{world}: no control is load-bearing for {falsifier_id}"


# ---------------------------------------------------------------------------
# Execution mediator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("world", WORLDS)
def test_consequential_transitions_need_their_declared_human_role(world):
    """Derived from the pack: every consequential transition, wrong role then right role, on a real executor.

    Execution with no approval at all is refused a layer earlier and covered by F01."""
    spec = WorldSpec.load(world)
    probe = ScenarioWorld(spec)
    profile = probe.profile
    held_roles = set(spec.principals.values())
    consequential = [t for t in profile.transitions if t.consequential]
    assert consequential, "a pack with no consequential transition governs nothing"
    for rule in consequential:
        assert rule.approval_role in held_roles, f"no principal can approve {rule.operation}"
        authority = AsymmetricApprovalAuthority(probe.audience, seed=b"\x05" * 32)
        register = CaseRegister({"r-1": {"status": rule.from_status, "version": 1}})
        executor = AccountableExecutor(register, EvidenceLedger("t"), "t", audience=probe.audience,
                                       approval_keys=authority.verification_keys,
                                       allowed_operations=profile.allowed_operations,
                                       transition_rules=profile.transition_rules,
                                       required_approval_roles=profile.required_approval_roles)
        proposal = ActionProposal("req-1", "agent-1", rule.operation, "r-1", 1, rule.from_status,
                                  rule.to_status, "e-1")
        wrong = authority.approve(proposal, approver="someone", approver_role="not-" + rule.approval_role,
                                  now=spec.now)
        with pytest.raises(ExecutionDenied) as role:
            executor.execute(proposal, wrong, now=spec.now + 1)
        assert role.value.code == "APPROVER_ROLE_NOT_ALLOWED"
        assert register.mutation_count == 0
        right = authority.approve(proposal, approver="human-1", approver_role=rule.approval_role, now=spec.now)
        assert executor.execute(proposal, right, now=spec.now + 1).status == rule.to_status


@pytest.mark.slow
@pytest.mark.parametrize("world", WORLDS)
def test_consequential_actions_bind_to_one_exact_human_approval(world):
    """No approval, forged approval, borrowed approval, replay, race, direct tool write."""
    _holds_and_bears(world, "F01", "F13", "F19", "F20", "F21")
    assert falsifiers(world)["F14"].held


# ---------------------------------------------------------------------------
# Context gate, release gate, delegation verifier
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("world", WORLDS)
def test_protected_reads_are_granted_minimal_and_purpose_bound(world):
    _holds_and_bears(world, "F02", "F06", "F07", "F08", "F10", "F11", "F12", "F22")


@pytest.mark.slow
@pytest.mark.parametrize("world", WORLDS)
def test_labelled_output_cannot_be_released_or_laundered(world):
    _holds_and_bears(world, "F03", "F23", "F24")


@pytest.mark.slow
@pytest.mark.parametrize("world", WORLDS)
def test_identity_reaches_models_only_as_tokens(world):
    _holds_and_bears(world, "F04", "F05")


@pytest.mark.slow
@pytest.mark.parametrize("world", WORLDS)
def test_delegated_authority_only_narrows(world):
    _holds_and_bears(world, "F09")
    assert run_delegation_suite(world=world).holds
    assert all(row["load_bearing"] for row in ablate_delegation(world=world))


@pytest.mark.parametrize("world", WORLDS)
def test_erasure_reaches_every_governed_copy(world):
    w = ScenarioWorld(world)
    fx = w.spec.fixture
    subject, other = fx("subject"), next(s for s in w.spec.subjects if s != fx("subject"))
    fields = (w.spec.field("identity"), w.spec.field("routine"))
    grant = w.grant(holder=fx("agent"), purpose=fx("purpose"), subjects=[subject], fields=fields)
    context = w.read(requester=fx("agent"), grant=grant, purpose=fx("purpose"), subjects=[subject],
                     fields=fields, session_id="erase-1")
    w.derive(requester=fx("agent"), session_id="erase-1", content=f"summary: {w.value(subject, fields[1])}")
    snapshot, backup = w.records.snapshot(), w.custody.backup(w._erase_key)
    assert context.tokens
    w.erasure.erase(subject, erased_by=fx("data_officer"), reason="synthetic erasure request")
    w.erasure.with_backup_credential(w._erase_key)
    report = w.erasure.verify(subject, fields=list(w.spec.subjects[subject]),
                              plaintexts=list(w.spec.subjects[subject].values()), snapshots=[snapshot],
                              custody_backups=[(backup, w.custody.journal)], restore_credential=w._gate_key)
    body = report.to_dict()
    assert body["readable_locations"] == []
    statuses = {check["location"]: check["status"] for check in body["checks"]}
    assert statuses["primary_record_store"] == statuses[f"backup:{snapshot.snapshot_id}"] == "unreadable"
    assert statuses["derived_outputs_gate_1"] == "absent"
    with pytest.raises(DisclosureDenied):
        w.read(requester=fx("agent"), grant=grant, purpose=fx("purpose"), subjects=[subject], fields=fields,
               session_id="erase-2")
    # Not vacuous: a subject nobody erased is reported readable.
    live = ScenarioWorld(world)
    live.erasure.with_backup_credential(live._erase_key)
    untouched = live.erasure.verify(other, fields=list(live.spec.subjects[other]),
                                    plaintexts=list(live.spec.subjects[other].values()),
                                    snapshots=[live.records.snapshot()])
    assert "primary_record_store" in untouched.to_dict()["readable_locations"]


@pytest.mark.parametrize("world", WORLDS)
def test_break_glass_opens_a_review_obligation(world):
    """Derived from the pack's break_glass block: bounded, and never self-reviewed."""
    w = ScenarioWorld(world)
    glass = w.pack.raw["disclosure"].get("break_glass")
    if not glass:
        pytest.skip("this pack declares no emergency access")
    role = glass["review_role"]
    holder = next(p for p, r in w.spec.principals.items() if r == role)
    field, subject = w.spec.field("sensitive"), w.spec.fixture("subject")

    def emergency(grant_id):
        grant = w.grants.issue(grant_id=grant_id, holder=holder, purpose=glass["purposes"][0], subjects=[subject],
                               fields=[field], classes=[w.policy.field_classes[field]], issued_by=holder,
                               now=w.now, ttl_seconds=min(900, glass["max_ttl_seconds"]), break_glass=True,
                               justification="synthetic emergency")
        return w.read(requester=holder, grant=grant, purpose=glass["purposes"][0], subjects=[subject],
                      fields=[field], session_id=grant_id)

    for index in range(glass["max_unreviewed_per_holder"]):
        emergency(f"glass-{index}")
    assert "glass-0" in w.gate.open_break_glass
    with pytest.raises(DisclosureDenied) as overdue:
        emergency("glass-over")
    assert overdue.value.code == "BREAK_GLASS_REVIEW_OVERDUE"
    with pytest.raises(DisclosureDenied):
        w.gate.record_break_glass_review("glass-0", reviewer=holder, reviewer_role=role, finding="self-review")


@pytest.mark.parametrize("world", WORLDS)
def test_declassification_needs_exact_approval(world):
    """Derived from the pack's first declassification rule."""
    w = ScenarioWorld(world)
    rules = w.pack.raw["disclosure"].get("declassification") or []
    if not rules:
        pytest.skip("this pack declares no declassification")
    rule = rules[0]
    purpose = rule["purposes"][0]
    field = next(f for f, c in w.policy.field_classes.items() if c in rule["from_classes"]
                 and f not in w.pack.identity_fields)
    recipient = next(name for name, spec in w.pack.raw["disclosure"]["recipients"].items()
                     if rule["to_class"] in spec["classes"] and purpose in spec["purposes"])
    subject, agent = w.spec.fixture("subject"), w.spec.fixture("agent")
    grant = w.grant(holder=agent, purpose=purpose, subjects=[subject], fields=[field])
    w.read(requester=agent, grant=grant, purpose=purpose, subjects=[subject], fields=[field], session_id="dc-1")
    draft = w.derive(requester=agent, session_id="dc-1", content=f"aggregate note: {w.value(subject, field)}")
    with pytest.raises(DisclosureDenied) as uncleared:
        w.release(draft, recipient=recipient, purpose=purpose)
    assert uncleared.value.code == "RECIPIENT_CLASS_NOT_CLEARED"
    with pytest.raises(DisclosureDenied) as unapproved:
        w.gate.declassify(draft, rule=rule["name"], approval=None, now=w.now)
    assert unapproved.value.code == "DECLASSIFICATION_NOT_APPROVED"
    approver = next(p for p, r in w.spec.principals.items() if r == rule["approval_role"])
    approval = w.declassifier.approve(draft, rule=rule["name"], approver=approver,
                                      approver_role=rule["approval_role"], now=w.now)
    released = w.release(w.gate.declassify(draft, rule=rule["name"], approval=approval, now=w.now),
                         recipient=recipient, purpose=purpose)
    if rule["removes_subject_identity"]:
        assert subject not in released.content
