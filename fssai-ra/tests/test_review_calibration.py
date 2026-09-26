"""Reviewer canaries measure oversight in operation and can only reduce a reviewer's capacity."""
from fssaira.oversight import ReviewLoadPolicy
from fssaira.review_calibration import LOW, ReviewerCalibration, wilson_lower

POLICY = ReviewLoadPolicy()


def queue(calibration, n=100):
    items = [{"id": f"real-{i}", "operation": "correct_transcript"} for i in range(n)]
    return calibration.plant(items, lambda i: {"id": f"canary-{i}", "operation": "correct_transcript"})


def review(calibration, reviewer, items, *, approves_canaries):
    for item in items:
        approved = approves_canaries if calibration.is_canary(item["id"]) else True
        calibration.record(reviewer, item["id"], approved)


def test_canaries_are_planted_at_the_declared_rate_in_the_same_shape():
    calibration = ReviewerCalibration(POLICY, canary_rate=0.1, seed=7)
    items = queue(calibration)
    canaries = [item for item in items if calibration.is_canary(item["id"])]
    assert len(items) == 110 and len(canaries) == 10
    assert {tuple(sorted(item)) for item in items} == {("id", "operation")}
    assert [item["id"] for item in queue(ReviewerCalibration(POLICY, seed=7))] == [i["id"] for i in items]


def test_an_attentive_reviewer_keeps_the_declared_capacity():
    calibration = ReviewerCalibration(POLICY, floor=0.7, min_canaries=10)
    review(calibration, "carol", queue(calibration), approves_canaries=False)
    assessment = calibration.assessment("carol")
    assert (assessment["caught"], assessment["below_floor"]) == (10, False)
    assert calibration.policy_for("carol") == POLICY


def test_a_reviewer_who_approves_canaries_loses_capacity_and_gains_a_second_reviewer():
    calibration = ReviewerCalibration(POLICY, min_canaries=10)
    review(calibration, "dave", queue(calibration), approves_canaries=True)
    assessment = calibration.assessment("dave")
    assert (assessment["caught"], assessment["code"]) == (0, LOW)
    reduced = calibration.policy_for("dave")
    assert reduced.max_approvals_per_window == POLICY.max_approvals_per_window // 2
    assert reduced.min_deliberation_seconds == POLICY.min_deliberation_seconds * 1.5
    assert reduced.second_reviewer_after == POLICY.second_reviewer_after // 2


def test_too_few_canaries_decide_nothing():
    calibration = ReviewerCalibration(POLICY, min_canaries=10)
    items = queue(calibration, n=20)  # two canaries
    review(calibration, "erin", items, approves_canaries=True)
    assert calibration.assessment("erin")["judged"] is False
    assert calibration.policy_for("erin") == POLICY


def test_a_canary_never_executes_whatever_the_reviewer_decides():
    calibration = ReviewerCalibration(POLICY)
    items = queue(calibration)
    review(calibration, "dave", items, approves_canaries=True)
    assert all(calibration.executable(i["id"]) != calibration.is_canary(i["id"]) for i in items)


def test_the_cost_of_measurement_is_reported():
    calibration = ReviewerCalibration(POLICY)
    review(calibration, "carol", queue(calibration), approves_canaries=False)
    assert calibration.cost("carol") == {"canaries_reviewed": 10,
                                         "seconds_at_floor": 10 * POLICY.min_deliberation_seconds}


def test_the_wilson_bound_is_conservative():
    assert wilson_lower(0, 0) == 0.0
    assert wilson_lower(10, 10) < 1.0
    assert wilson_lower(9, 10) < 0.9


def test_the_defaults_pass_a_perfect_reviewer_and_catch_a_careless_one():
    """Floor and minimum sample are consistent: judging is possible at the minimum."""
    perfect, careless = ReviewerCalibration(POLICY), ReviewerCalibration(POLICY)
    review(perfect, "carol", queue(perfect), approves_canaries=False)
    assert perfect.assessment("carol")["below_floor"] is False
    items = queue(careless)
    for index, item in enumerate(i for i in items if careless.is_canary(i["id"])):
        careless.record("dave", item["id"], approved=index < 2)  # misses two of ten
    assert careless.assessment("dave")["below_floor"] is True
