"""Delegated authority: what a chain confers, and what it must refuse.

The single-agent controls answer *may this agent do this?* about one identity.
These answer the question that replaces it once an orchestrator spawns
sub-agents and sub-agents call tool servers: *what does this chain of grants
actually confer, and who is accountable for it?*

Every test here is deterministic and offline, like the rest of the suite.
"""
import json

import pytest

from trustkernel.delegation_eval import (
    ablate_delegation,
    run_delegation_suite,
)
from trustkernel.kernel.accountable_action import ActionClass
from trustkernel.kernel.delegation import (
    ANY,
    CHAIN_SCENARIOS,
    AuthorityScope,
    Delegation,
    DelegationAuthority,
    DelegationCode,
    DelegationPolicy,
    RootGrant,
    verify_delegation_space,
)
from trustkernel.kernel.exact_action import ExecutionDenied

NOW = 1_000.0
HOUR = 3_600.0


def scope(tools, *, resources=None, cls=ActionClass.REVERSIBLE, egress=False):
    return AuthorityScope(
        tools=frozenset(tools), operations=frozenset(tools),
        resources=frozenset(resources if resources is not None else {ANY}),
        max_action_class=cls, egress=egress,
    )


@pytest.fixture
def root():
    return RootGrant(
        "orchestrator", scope({"read", "draft"}, resources={"R-1", "R-2"}),
        "service_owner", NOW + 8 * HOUR,
    )


@pytest.fixture
def authority():
    return DelegationAuthority()


# -- the partial order ----------------------------------------------------


def test_a_bounded_scope_never_covers_an_unbounded_one():
    """The direction that matters. If ``{"R-1"}`` covered ``{ANY}``, a hop could
    widen a grant by claiming breadth and the whole order would be decorative."""
    bounded = scope({"read"}, resources={"R-1"})
    unbounded = scope({"read"}, resources={ANY})
    assert unbounded.covers(bounded)
    assert not bounded.covers(unbounded)


def test_consequence_and_egress_are_independent_axes():
    reversible_egress = scope({"notify"}, cls=ActionClass.REVERSIBLE, egress=True)
    consequential_internal = scope({"award"}, cls=ActionClass.HIGH_IMPACT, egress=False)
    assert not reversible_egress.covers(consequential_internal)
    assert not consequential_internal.covers(reversible_egress)


def test_intersection_takes_the_narrower_of_every_axis():
    a = scope({"read", "draft"}, resources={"R-1", "R-2"}, cls=ActionClass.HIGH_IMPACT, egress=True)
    b = scope({"read"}, resources={"R-2"}, cls=ActionClass.REVERSIBLE, egress=False)
    meet = a.intersect(b)
    assert meet.tools == frozenset({"read"})
    assert meet.resources == frozenset({"R-2"})
    assert meet.max_action_class is ActionClass.REVERSIBLE
    assert meet.egress is False


# -- the seven chain invariants -------------------------------------------


def test_a_narrowing_chain_is_admitted_and_confers_the_intersection(root, authority):
    first = authority.issue(
        delegator="orchestrator", delegate="agent-a",
        scope=scope({"read", "draft"}, resources={"R-1"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    second = authority.issue(
        delegator="agent-a", delegate="agent-b",
        scope=scope({"read"}, resources={"R-1"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    verdict = authority.admit_strict(
        (first, second), root, now=NOW + 10, requester="agent-b",
        tool="read", operation="read", resource="R-1",
    )
    assert verdict.admitted
    assert verdict.effective_scope.tools == frozenset({"read"})
    assert verdict.principals == ("orchestrator", "agent-a", "agent-b")


def test_a_hop_cannot_pass_on_authority_it_does_not_hold(root, authority):
    narrow = authority.issue(
        delegator="orchestrator", delegate="agent-a",
        scope=scope({"read"}, resources={"R-1"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    widened = authority.issue(
        delegator="agent-a", delegate="agent-b",
        scope=scope({"read", "draft"}, resources={"R-1", "R-2"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict((narrow, widened), root, now=NOW + 10, requester="agent-b")
    assert denial.value.code == DelegationCode.SCOPE_NOT_ATTENUATED


def test_a_chain_descending_from_no_institutional_grant_is_refused(root, authority):
    orphan = authority.issue(
        delegator="some-other-service", delegate="agent-a",
        scope=scope({"read"}), issued_at=NOW, expires_at=NOW + HOUR,
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict((orphan,), root, now=NOW + 10, requester="agent-a")
    assert denial.value.code == DelegationCode.CHAIN_NOT_ROOTED


def test_a_principal_cannot_appear_twice(root, authority):
    hops = (
        authority.issue(delegator="orchestrator", delegate="agent-a",
                        scope=scope({"read"}, resources={"R-1"}),
                        issued_at=NOW, expires_at=NOW + HOUR),
        authority.issue(delegator="agent-a", delegate="agent-b",
                        scope=scope({"read"}, resources={"R-1"}),
                        issued_at=NOW, expires_at=NOW + HOUR),
        authority.issue(delegator="agent-b", delegate="agent-a",
                        scope=scope({"read"}, resources={"R-1"}),
                        issued_at=NOW, expires_at=NOW + HOUR),
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict(hops, root, now=NOW + 10, requester="agent-a")
    assert denial.value.code == DelegationCode.CHAIN_CYCLE


def test_a_delegation_may_not_outlive_the_authority_it_descends_from(root, authority):
    bounded = scope({"read"}, resources={"R-1"})
    short = authority.issue(
        delegator="orchestrator", delegate="agent-a", scope=bounded,
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    longer = authority.issue(
        delegator="agent-a", delegate="agent-b", scope=bounded,
        issued_at=NOW, expires_at=NOW + 6 * HOUR,
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict((short, longer), root, now=NOW + 10, requester="agent-b")
    assert denial.value.code == DelegationCode.DELEGATION_OUTLIVES_DELEGATOR


def test_an_expired_ancestor_stops_its_descendants(root, authority):
    bounded = scope({"read"}, resources={"R-1"})
    hops = (
        authority.issue(delegator="orchestrator", delegate="agent-a",
                        scope=bounded, issued_at=NOW, expires_at=NOW + HOUR),
        authority.issue(delegator="agent-a", delegate="agent-b",
                        scope=bounded, issued_at=NOW, expires_at=NOW + HOUR),
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict(hops, root, now=NOW + 2 * HOUR, requester="agent-b")
    assert denial.value.code == DelegationCode.DELEGATION_EXPIRED


def test_a_chain_longer_than_the_declared_depth_is_refused(root):
    authority = DelegationAuthority(policy=DelegationPolicy(max_depth=2))
    names = ["orchestrator", "a", "b", "c"]
    hops = tuple(
        authority.issue(delegator=names[i], delegate=names[i + 1],
                        scope=scope({"read"}, resources={"R-1"}),
                        issued_at=NOW, expires_at=NOW + HOUR)
        for i in range(3)
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict(hops, root, now=NOW + 10, requester="c")
    assert denial.value.code == DelegationCode.DEPTH_EXCEEDED


def test_a_hop_signed_by_an_untrusted_key_is_refused_before_any_scope_check(root, authority):
    """Order matters: an inauthentic hop must not reach the authority questions."""
    forged = Delegation(
        delegator="orchestrator", delegate="agent-a",
        scope=scope({"read"}, resources={"R-1"}), issued_at=NOW, expires_at=NOW + HOUR,
        key_id="rogue-key", signature="deadbeef",
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict((forged,), root, now=NOW + 10, requester="agent-a")
    assert denial.value.code == DelegationCode.DELEGATION_KEY_UNTRUSTED


def test_tampering_with_a_signed_field_invalidates_the_hop(root, authority):
    from dataclasses import replace

    hop = authority.issue(
        delegator="orchestrator", delegate="agent-a",
        scope=scope({"read"}, resources={"R-1"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    widened = replace(hop, scope=scope({"read", "draft"}, resources={"R-1"}))
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict((widened,), root, now=NOW + 10, requester="agent-a")
    assert denial.value.code == DelegationCode.DELEGATION_SIGNATURE_INVALID


def test_a_machine_may_not_pass_consequential_authority_onward(root, authority):
    consequential = scope({"read"}, resources={"R-1"}, cls=ActionClass.HIGH_IMPACT)
    grant = RootGrant("orchestrator", consequential, "service_owner", NOW + 8 * HOUR)
    hops = (
        authority.issue(delegator="orchestrator", delegate="agent-a", scope=consequential,
                        issued_at=NOW, expires_at=NOW + HOUR, human_approved=True),
        authority.issue(delegator="agent-a", delegate="agent-b", scope=consequential,
                        issued_at=NOW, expires_at=NOW + HOUR, human_approved=False),
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict(hops, grant, now=NOW + 10, requester="agent-b")
    assert denial.value.code == DelegationCode.CONSEQUENCE_NOT_DELEGABLE


def test_a_human_approving_the_hop_permits_consequential_delegation(root, authority):
    consequential = scope({"read"}, resources={"R-1"}, cls=ActionClass.HIGH_IMPACT)
    grant = RootGrant("orchestrator", consequential, "service_owner", NOW + 8 * HOUR)
    hops = (
        authority.issue(delegator="orchestrator", delegate="agent-a", scope=consequential,
                        issued_at=NOW, expires_at=NOW + HOUR, human_approved=True),
        authority.issue(delegator="agent-a", delegate="agent-b", scope=consequential,
                        issued_at=NOW, expires_at=NOW + HOUR, human_approved=True),
    )
    verdict = authority.admit_strict(hops, grant, now=NOW + 10, requester="agent-b")
    assert verdict.admitted


# -- D8: the defect the suite found on its first run ----------------------


def test_a_chain_is_bound_to_the_principal_it_names(root, authority):
    """The confused-deputy defect, as a regression test.

    Every other invariant holds on this chain. It is authentic, rooted,
    attenuated, unexpired, acyclic, and within depth. It is simply not the
    requester's chain, and admitting it would make delegated authority a bearer
    token.
    """
    hop = authority.issue(
        delegator="orchestrator", delegate="assistant-broad",
        scope=scope({"read", "draft"}, resources={"R-1", "R-2"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict((hop,), root, now=NOW + 10, requester="assistant-narrow")
    assert denial.value.code == DelegationCode.REQUESTER_NOT_CHAIN_LEAF


def test_acting_for_another_principal_uses_that_principal_s_authority(root, authority):
    """Doing a job for someone does not lend them your grant."""
    broad = authority.issue(
        delegator="orchestrator", delegate="assistant-broad",
        scope=scope({"read", "draft"}, resources={"R-1", "R-2"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    narrow = authority.issue(
        delegator="orchestrator", delegate="assistant-narrow",
        scope=scope({"read"}, resources={"R-1"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict(
            (broad,), root, now=NOW + 10, requester="assistant-broad",
            on_behalf_of="assistant-narrow", beneficiary_chain=(narrow,),
            tool="draft", operation="draft", resource="R-2",
        )
    assert denial.value.code == DelegationCode.OUT_OF_EFFECTIVE_SCOPE


def test_the_same_work_inside_the_beneficiary_s_scope_is_admitted(root, authority):
    """The control must not refuse legitimate delegation on someone's behalf."""
    broad = authority.issue(
        delegator="orchestrator", delegate="assistant-broad",
        scope=scope({"read", "draft"}, resources={"R-1", "R-2"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    narrow = authority.issue(
        delegator="orchestrator", delegate="assistant-narrow",
        scope=scope({"read"}, resources={"R-1"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    verdict = authority.admit_strict(
        (broad,), root, now=NOW + 10, requester="assistant-broad",
        on_behalf_of="assistant-narrow", beneficiary_chain=(narrow,),
        tool="read", operation="read", resource="R-1",
    )
    assert verdict.admitted


def test_an_actor_that_will_not_name_the_beneficiary_is_refused(root, authority):
    broad = authority.issue(
        delegator="orchestrator", delegate="assistant-broad",
        scope=scope({"read", "draft"}, resources={"R-1", "R-2"}),
        issued_at=NOW, expires_at=NOW + HOUR,
    )
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict(
            (broad,), root, now=NOW + 10, requester="assistant-broad",
            on_behalf_of="assistant-narrow", beneficiary_chain=None,
            tool="read", operation="read", resource="R-1",
        )
    assert denial.value.code == DelegationCode.BENEFICIARY_SCOPE_EXCEEDED


def test_the_root_principal_acting_directly_needs_no_chain(root, authority):
    """The single-agent case the rest of the architecture already governs."""
    verdict = authority.admit_strict(
        (), root, now=NOW + 10, requester="orchestrator",
        tool="read", operation="read", resource="R-1",
    )
    assert verdict.admitted and verdict.depth == 0


# -- the suite, the ablations, and the model check -------------------------


def test_every_hostile_chain_is_contained_and_the_benign_one_completes():
    report = run_delegation_suite()
    assert report.contained("this_architecture") == report.hostile_total
    assert report.benign_completed("this_architecture")
    assert report.holds


def test_each_scenario_is_refused_with_the_code_it_declares():
    report = run_delegation_suite()
    by_name = {
        outcome.scenario: outcome
        for outcome in report.outcomes if outcome.arm == "this_architecture"
    }
    for scenario in CHAIN_SCENARIOS:
        assert by_name[scenario.name].code == scenario.expected_code, (
            f"{scenario.name} was refused with {by_name[scenario.name].code}, "
            f"not the declared {scenario.expected_code}"
        )


def test_checking_each_hop_against_its_delegator_is_not_checking_the_chain():
    """The finding that makes this domain worth a separate control.

    Arm B is a real control, correctly implemented, and it is what a careful
    engineer builds. It stops re-amplification at the hop where it happens. It
    cannot see the root, the principal sequence, or the policy, so a majority of
    the risk classes pass straight through it.
    """
    report = run_delegation_suite()
    assert report.contained("unguarded") == 0
    local = report.contained("caller_checked")
    whole = report.contained("this_architecture")
    assert 0 < local < whole, (
        "local per-hop validation should catch something and miss more; "
        f"caught {local} of {report.hostile_total}, chain verification caught {whole}"
    )


def test_every_delegation_invariant_is_load_bearing():
    for row in ablate_delegation():
        assert row["load_bearing"], (
            f"removing {row['control']} did not restore the harm in "
            f"{row['scenario']}: {row['with_control']} vs {row['without_control']}"
        )


def test_the_declared_delegation_space_holds_under_bounded_model_checking():
    report = verify_delegation_space()
    assert report.states_explored > 500
    assert report.holds, [v.detail for v in report.violations]
    assert report.admitted > 0, "a checker that admits nothing proves nothing"


def test_every_refusal_in_the_space_carries_a_declared_code():
    report = verify_delegation_space()
    declared = {
        value for name, value in vars(DelegationCode).items()
        if not name.startswith("_") and isinstance(value, str)
    }
    assert set(report.to_dict()["outcome_histogram"]) <= declared


def test_the_reports_are_json_serializable_and_state_their_limits():
    for payload in (
        run_delegation_suite().to_dict(),
        verify_delegation_space().to_dict(),
        DelegationAuthority().report(),
    ):
        json.dumps(payload)
        assert payload["limits"]


def test_an_invalid_delegation_policy_is_refused():
    with pytest.raises(ValueError):
        DelegationPolicy(max_depth=0)


# -- defects found by probing the module after it shipped -------------------


def test_an_unnamed_principal_cannot_hold_authority(root, authority):
    """An empty identifier passes every other check in the module.

    It signs, it attenuates, it matches a requester of the same empty string.
    What it cannot do is answer the question the chain exists to answer. This
    was admitted until it was probed for.
    """
    with pytest.raises(ExecutionDenied) as denial:
        authority.issue(
            delegator="root-principal", delegate="", scope=scope({"read"}),
            issued_at=NOW, expires_at=NOW + HOUR,
        )
    assert denial.value.code == DelegationCode.PRINCIPAL_NOT_NAMED


def test_a_hand_built_chain_cannot_smuggle_an_unnamed_principal(root, authority):
    """Refusing at issue time is not enough; chains arrive from the wire."""
    from trustkernel.kernel.delegation import DELEGATION_SIGNING_KEY

    hop = Delegation(
        "orchestrator", "   ", scope({"read"}, resources={"R-1"}), NOW, NOW + HOUR,
    ).signed_with(DELEGATION_SIGNING_KEY)
    with pytest.raises(ExecutionDenied) as denial:
        authority.admit_strict((hop,), root, now=NOW + 10, requester="   ")
    assert denial.value.code == DelegationCode.PRINCIPAL_NOT_NAMED


def test_a_root_grant_must_name_a_principal_and_an_accountable_owner():
    """The owner is the point of the type: it is what makes a chain attributable
    to an institution rather than merely internally consistent."""
    good = scope({"read"}, resources={"R-1"})
    with pytest.raises(ValueError, match="name the principal"):
        RootGrant("", good, "service_owner", NOW + HOUR)
    with pytest.raises(ValueError, match="accountable owner"):
        RootGrant("orchestrator", good, "  ", NOW + HOUR)
