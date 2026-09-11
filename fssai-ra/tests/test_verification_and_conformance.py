"""Machine-checked assurance: the model checker and the portable conformance suite.

These two exist for different readers. The model checker answers a question the
author cannot answer honestly by writing more tests ("what about the combination
I did not think of?"). The conformance suite answers a question the author
cannot answer at all ("does it still hold after you replaced my database with
yours?").
"""
import pytest

from fssaira.conformance import Bundle, ConformanceSuite, memory_bundle, run_conformance, sql_bundle
from fssaira.profiles import ApplicationProfile
from fssaira.sql_backend import open_sqlite
from fssaira.verification import APPROVAL_VARIANTS, INVARIANTS, ProfileVerifier, verify_profile


@pytest.fixture
def profile():
    return ApplicationProfile.load("profiles/student_support.yaml")


# --------------------------------------------------------------- model checking


def test_the_declared_authority_space_contains_no_violation(profile):
    report = verify_profile(profile)

    assert report.holds, [vars(v) for v in report.violations]
    assert report.states_explored > 200
    assert len(report.invariants) == len(INVARIANTS) == 5


def test_only_fully_authorized_configurations_mutate(profile):
    report = verify_profile(profile)

    # One mutation per consequential transition, and nothing else.
    consequential = sum(1 for rule in profile.transitions if rule.consequential)
    assert report.mutations_observed == consequential
    assert report.outcome_histogram["EXECUTED"] == consequential


def test_every_denial_control_is_actually_reached(profile):
    """A variant that is caught one check too early leaves a control untested.

    The suite originally tampered with signed fields, so the signature caught
    everything and the audience, expiry, and role checks were never exercised.
    These codes appearing in the histogram is what proves that is fixed.
    """
    histogram = verify_profile(profile).outcome_histogram

    for code in (
        "APPROVAL_EXPIRED",
        "APPROVAL_AUDIENCE_MISMATCH",
        "APPROVAL_PAYLOAD_MISMATCH",
        "APPROVAL_KEY_UNTRUSTED",
        "APPROVAL_SIGNATURE_INVALID",
        "APPROVER_ROLE_NOT_ALLOWED",
        "OPERATION_NOT_ALLOWED",
        "TRANSITION_NOT_ALLOWED",
        "CASE_VERSION_CONFLICT",
        "CASE_NOT_FOUND",
    ):
        assert histogram.get(code, 0) > 0, f"no configuration reached {code}"


def test_the_report_states_its_own_bounds(profile):
    bounds = verify_profile(profile).to_dict()["bounds"]

    assert "not a proof" in bounds["note"]
    assert bounds["concurrency"].startswith("single-threaded")
    assert set(bounds["approval_variants"]) == set(APPROVAL_VARIANTS)


def test_a_verifier_needs_a_profile_with_transitions():
    """A profile with nothing to enforce has nothing to verify, and says so.

    Loading such a profile is already refused; this covers the case where one is
    constructed directly, which a third-party adapter might do.
    """
    empty = ApplicationProfile(
        profile_id="x", version="1", title="X", resource_name="r",
        owner="o", manual_fallback="m", transitions=(),
    )

    with pytest.raises(ValueError, match="at least one transition"):
        ProfileVerifier(empty)


def test_the_checker_catches_an_executor_that_is_too_permissive(profile, monkeypatch):
    """A negative control: if the executor stops enforcing, the checker must notice."""
    verifier = ProfileVerifier(profile)
    # Claim every configuration is authorized. The reference predicate disagrees
    # with the executor for all the denial cases, so violations must appear.
    monkeypatch.setattr(verifier, "_authorized", lambda configuration: True)

    report = verifier.check()

    assert not report.holds
    assert len(report.violations) > 50


# ------------------------------------------------------------------ conformance


def test_the_reference_memory_bundle_conforms(profile):
    report = run_conformance(memory_bundle(profile))

    assert report.passed, [vars(check) for check in report.failures]
    assert len(report.executed) >= 20


def test_the_transactional_sql_bundle_conforms(profile):
    report = run_conformance(sql_bundle(profile=profile))

    assert report.passed, [vars(check) for check in report.failures]
    assert report.backends["executor"] == "atomic"


def test_missing_backends_are_skipped_not_silently_passed():
    report = run_conformance(Bundle())

    skipped = [check.id for check in report.checks if check.skipped]
    assert skipped, "a bundle with nothing supplied must report skips"
    summary = report.to_dict()["summary"]
    assert summary["checks_skipped"] == len(skipped)


def test_an_evidence_store_without_a_write_guard_fails_conformance():
    """The check that caught a real defect in this repository's SQL backend."""
    database = open_sqlite()  # note: no evidence_token, so the guard is disabled
    bundle = sql_bundle(database)

    report = run_conformance(bundle)

    failures = {check.id for check in report.failures}
    assert "CF-AA-01" in failures
    assert report.passed is False


def test_a_channel_with_a_return_path_fails_conformance(profile):
    class LeakyChannel:
        def connect(self, handler):
            self._handler = handler

        def send_inward(self, item):
            self._handler(item)

        def receive(self):  # the return path
            return {}

    bundle = memory_bundle(profile)
    bundle.inward = LeakyChannel()

    report = run_conformance(bundle)

    failures = {check.id for check in report.failures}
    assert "CF-IB-01" in failures


def test_the_report_refuses_to_overclaim(profile):
    payload = run_conformance(memory_bundle(profile)).to_dict()

    assert payload["kind"] == "conformance"
    assert any("not a penetration test" in limit for limit in payload["limits"])
    for check in payload["checks"]:
        assert check["requirement"], f"{check['id']} names no control-contract requirement"


def test_every_conformance_check_maps_to_a_contract_requirement(profile):
    """A check that cannot name the governance claim it defends is noise."""
    from fssaira.contract import ControlContract

    contract = ControlContract.load("contract")
    known = {requirement.id for requirement in contract}

    for check in ConformanceSuite(memory_bundle(profile)).run().checks:
        assert check.requirement in known, (
            f"{check.id} cites {check.requirement!r}, which is not in the control contract"
        )


# ------------------------------------------------- controlled architecture comparison


def test_the_comparison_puts_the_same_attacks_to_every_arm():
    """A comparison in which the arms face different adversaries proves nothing."""
    from fssaira.experiment import ATTACKS, BENIGN_TASKS, run_comparison

    report = run_comparison()

    assert len(report["arms"]) == 3
    for arm in report["arms"]:
        assert arm["attacks_attempted"] == len(ATTACKS)
        assert arm["benign_attempted"] == len(BENIGN_TASKS)


def test_the_baseline_is_not_a_strawman():
    """Arm B must actually stop some attacks, or the comparison is rigged."""
    from fssaira.experiment import run_comparison

    unguarded, prompt_guarded, ours = run_comparison()["arms"]

    assert unguarded["containment_rate"] == 0.0, "the unguarded arm should stop nothing"
    assert 0 < prompt_guarded["containment_rate"] < 1.0, (
        "a tool allowlist is a real control; a baseline that stops nothing is a strawman"
    )
    assert sum(prompt_guarded["harms"].values()) < sum(unguarded["harms"].values())
    assert ours["containment_rate"] == 1.0
    assert sum(ours["harms"].values()) == 0


def test_containment_is_not_bought_with_utility():
    """The finding that makes the containment figure worth reporting."""
    from fssaira.experiment import run_comparison

    arms = run_comparison()["arms"]

    assert all(arm["benign_completion_rate"] == 1.0 for arm in arms), (
        "every arm must complete the legitimate work; otherwise containment is "
        "just refusal and the comparison says nothing"
    )


def test_only_this_architecture_produces_a_record_the_agent_cannot_write():
    from fssaira.experiment import run_comparison

    unguarded, prompt_guarded, ours = run_comparison()["arms"]

    assert unguarded["evidence_records"] == 0
    assert prompt_guarded["evidence_records"] == 0
    assert ours["evidence_records"] > 0
    assert ours["agent_can_write_evidence"] is False
    assert ours["human_in_the_loop"] is True


def test_the_comparison_states_what_it_does_not_establish():
    from fssaira.experiment import run_comparison

    report = run_comparison()

    assert any("not field rates" in limit for limit in report["limits"])
    assert any("not any particular product" in limit for limit in report["limits"])
    assert any("not exhaustive" in limit for limit in report["limits"])
