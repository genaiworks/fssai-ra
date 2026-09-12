"""Assisted review: throughput bought with independence, and refused without it.

``fssaira.oversight`` shows that a system can be perfectly accountable and
completely unreviewed. These tests cover the 2026 version of that failure, which
is worse because it looks like a solution: give the reviewer a model, lower the
deliberation floor, absorb the queue — and if that model is the proposer's
reasoning arriving a second time, the merit failures come back while every
runtime mechanism keeps passing.
"""
import json
import os

import pytest

from fssaira.assisted_review import (
    AssistanceMode,
    AssistedReviewCode,
    AssistedReviewerModel,
    AssistedReviewPolicy,
    ReviewAssistance,
    run_assisted_review_trial,
)
from fssaira.exact_action import ExecutionDenied
from fssaira.profiles import ApplicationProfile
from helpers import CONTRACT_DIR  # noqa: F401  (keeps the shared sys.path bootstrap)

PROFILE = os.path.join(os.path.dirname(CONTRACT_DIR), "profiles", "student_support.yaml")


@pytest.fixture(scope="module")
def profile():
    return ApplicationProfile.load(PROFILE)


@pytest.fixture(scope="module")
def trial(profile):
    return run_assisted_review_trial(profile)


def dependent(mode=AssistanceMode.RECOMMENDED):
    return ReviewAssistance(mode=mode, declared_by="student_services")


def independent(mode=AssistanceMode.RECOMMENDED):
    return ReviewAssistance(
        mode=mode, independent_model=True, independent_evidence=True,
        adversarial_posture=True, declared_by="student_services",
    )


# -- the declaration ------------------------------------------------------


def test_an_unaided_reader_is_trivially_independent_of_the_proposer():
    unaided = ReviewAssistance(mode=AssistanceMode.UNAIDED)
    assert unaided.is_independent
    assert unaided.floor_multiplier == 1.0


def test_independence_is_three_separate_declarations():
    partial = ReviewAssistance(
        mode=AssistanceMode.SUMMARISED, independent_model=True,
        declared_by="student_services",
    )
    assert partial.independence_score == 1
    assert not partial.is_independent
    assert 0.4 < partial.floor_multiplier < 1.0, (
        "partial independence should earn a partial reduction, not all or nothing"
    )


def test_a_fully_dependent_assistant_earns_no_reduction_at_all():
    assert dependent().floor_multiplier == 1.0


def test_a_fully_independent_assistant_earns_the_largest_reduction():
    assert independent().floor_multiplier == 0.2


# -- the configuration gate (AR-1) ----------------------------------------


def test_a_lowered_floor_without_declared_independence_is_refused():
    """The control, and the reason it binds at configuration time.

    At runtime a reviewer assisted by an independent model and one assisted by
    the proposer's own reasoning are indistinguishable: same identity, same
    interval, same signature. The difference exists only in the declaration.
    """
    gate = AssistedReviewPolicy(unaided_floor_seconds=45.0)
    with pytest.raises(ExecutionDenied) as denial:
        gate.check(dependent(), proposed_floor=10.0)
    assert denial.value.code == AssistedReviewCode.FLOOR_BELOW_DECLARED_INDEPENDENCE
    assert "45.0s" in str(denial.value), "the refusal must name the floor to raise to"


def test_the_same_floor_is_permitted_once_independence_is_declared():
    gate = AssistedReviewPolicy(unaided_floor_seconds=45.0)
    gate.check(independent(), proposed_floor=10.0)  # must not raise
    assert gate.permitted_floor(independent()) == 9.0


def test_assistance_in_use_with_no_accountable_declarer_is_refused():
    gate = AssistedReviewPolicy()
    undeclared = ReviewAssistance(mode=AssistanceMode.SUMMARISED, declared_by="")
    with pytest.raises(ExecutionDenied) as denial:
        gate.check(undeclared, proposed_floor=45.0)
    assert denial.value.code == AssistedReviewCode.ASSISTANCE_NOT_DECLARED


def test_an_unaided_deployment_is_unaffected_by_the_gate():
    """The control must be inert where it does not apply."""
    gate = AssistedReviewPolicy(unaided_floor_seconds=45.0)
    gate.check(ReviewAssistance(mode=AssistanceMode.UNAIDED), proposed_floor=45.0)
    with pytest.raises(ExecutionDenied):
        gate.check(ReviewAssistance(mode=AssistanceMode.UNAIDED), proposed_floor=5.0)


# -- the reviewer model ---------------------------------------------------


def test_an_independent_assistant_extends_effective_attention():
    model = AssistedReviewerModel(assistance=independent())
    assert model.effective_attention > model.attentive_until


def test_a_dependent_assistant_replaces_reading_with_ratifying():
    """It does not extend attention. It makes each decision cheaper, which is
    not the same activity and must not be scored as if it were."""
    model = AssistedReviewerModel(assistance=dependent())
    assert model.effective_attention == model.attentive_until


def test_a_dependent_assistant_endorses_the_proposals_it_should_refuse():
    model = AssistedReviewerModel(assistance=dependent())
    approves, seconds = model.review(should_refuse=True, index=0)
    assert approves, "the assistant inherited the proposer's error and the reviewer ratified"
    assert seconds == model.assisted_seconds


def test_an_independent_assistant_still_refuses_on_merit_while_attentive():
    model = AssistedReviewerModel(assistance=independent())
    approves, _ = model.review(should_refuse=True, index=0)
    assert not approves


# -- the trial (AR-2, AR-3) -----------------------------------------------


def test_a_dependent_assistant_reintroduces_merit_failures(trial):
    summary = trial["summary"]
    assert summary["merit_failures_assisted_dependent"] > 0
    assert summary["merit_failures_assisted_dependent"] > summary[
        "merit_failures_assisted_independent"
    ]
    assert summary["dependent_assistance_reintroduced_harm"]


def test_every_runtime_mechanism_passes_in_the_harmful_arm(trial):
    """The finding. There is no runtime signal to alert on.

    The evidence chain is intact, the reviewer is inside quota, every approval
    clears the configured deliberation floor, and no oversight refusal fires.
    An operator watching the dashboard sees a well-run deployment.
    """
    assert trial["summary"]["every_mechanism_passed_in_the_harmful_arm"]
    harmful = trial["arms"]["assisted_dependent_lowered_floor"]
    assert harmful["evidence_chain_valid"]
    assert harmful["oversight"]["refusals_by_code"] == {}
    assert harmful["harmful_executed"] > 0


def test_the_configuration_gate_refuses_the_harmful_deployment(trial):
    refused = trial["arms"]["assisted_dependent_floor_refused"]
    assert refused["refused_at_configuration"] is True
    assert refused["started"] is False
    assert refused["code"] == AssistedReviewCode.FLOOR_BELOW_DECLARED_INDEPENDENCE


def test_assistance_genuinely_buys_throughput(trial):
    """Reported because a control that only ever costs is not a trade-off.

    The unaided arm contains every merit failure and defers most of the queue to
    do it. Assistance is not a mistake; buying it without independence is.
    """
    summary = trial["summary"]
    assert summary["benign_completed_assisted_independent"] > summary[
        "benign_completed_unaided"
    ]
    assert summary["deferred_to_manual_assisted"] < summary["deferred_to_manual_unaided"]


def test_independence_moves_the_ceiling_rather_than_removing_it(trial):
    """AR-3, and the result that keeps the claim honest.

    The independent arm does not reach zero. Independence multiplies a
    reviewer's effective attention; it does not make attention unbounded. An
    institution that buys an assistant has bought a larger ceiling to compute,
    not permission to stop computing one.
    """
    assert trial["summary"]["independence_bounds_harm_without_removing_it"], (
        "if the independent arm reached zero harm, the trial would be claiming "
        "assistance removes the oversight ceiling, which is the error this "
        "whole module exists to refuse"
    )


def test_the_unaided_baseline_still_contains_everything(trial):
    """The existing oversight control is unchanged and still works."""
    assert trial["summary"]["merit_failures_unaided"] == 0


def test_the_trial_is_json_serializable_and_states_its_limits(trial):
    json.dumps(trial)
    assert trial["limits"]
    assert any("declared parameter" in line for line in trial["limits"])
    assert any("no model was evaluated" in line for line in trial["limits"])


def test_the_declaration_states_that_it_is_not_a_measurement():
    payload = independent().to_dict()
    assert "not a measurement" in payload["status"]
