"""Can an institution actually *declare* the controls this project argues for?

Oversight capacity, delegation bounds, and review-assistant independence are the
three things this architecture asks an institution to state about itself. All
three were implemented, tested, measured, published — and unreachable from a
deployment, because nothing read them from the environment and the runtime
factory built its approval authority with no oversight monitor at all.

So the headline control held in the CLI trial and in the test suite, and was
absent from every real deployment the platform could build. That is the exact
failure the control contract exists to eliminate, and it survived three releases
because every test that exercised oversight constructed the monitor itself.

These tests close it from both ends: the policies are readable from the
environment, and the deployment the factory builds actually carries them.
"""
import os

import pytest

from fssaira.assisted_review import AssistanceMode, AssistedReviewPolicy, ReviewAssistance
from fssaira.delegation import DelegationPolicy
from fssaira.exact_action import ExecutionDenied
from fssaira.oversight import ReviewLoadPolicy
from fssaira.runtime_factory import build_control_plane, configuration_warnings


@pytest.fixture
def clean_env(monkeypatch):
    """Start from an environment that declares none of the three."""
    for name in list(os.environ):
        if name.startswith("FSSAI_"):
            monkeypatch.delenv(name, raising=False)
    return monkeypatch


# -- declaring review capacity --------------------------------------------


def test_an_undeclared_review_capacity_is_none_not_our_default():
    """Inheriting the reference quota would publish a number nobody agreed to.

    An institution's capacity figure is the one number in this project that has
    to come from the institution. A silent fallback to the shipped default would
    let a deployment publish "2,640 consequential actions per day" on the
    strength of a number we chose.
    """
    assert ReviewLoadPolicy.from_env({}) is None


def test_declaring_the_quota_switches_the_control_on():
    policy = ReviewLoadPolicy.from_env({
        "FSSAI_REVIEW_MAX_PER_WINDOW": "40",
        "FSSAI_REVIEW_DELIBERATION_FLOOR": "60",
        "FSSAI_REVIEW_SECONDS_PER_DAY": "7200",
    })
    assert policy is not None
    assert policy.max_approvals_per_window == 40
    assert policy.min_deliberation_seconds == 60.0
    assert policy.sustainable_actions_per_day(3)["sustainable_per_day"] > 0


def test_escalation_can_be_declared_off_in_words_an_operator_would_use():
    for value in ("none", "off", "disabled", ""):
        policy = ReviewLoadPolicy.from_env({
            "FSSAI_REVIEW_MAX_PER_WINDOW": "40",
            "FSSAI_REVIEW_SECOND_REVIEWER_AFTER": value,
        })
        assert policy.second_reviewer_after is None, value


def test_a_non_numeric_declaration_fails_loudly():
    with pytest.raises(ValueError, match="must be a number"):
        ReviewLoadPolicy.from_env({
            "FSSAI_REVIEW_MAX_PER_WINDOW": "40",
            "FSSAI_REVIEW_DELIBERATION_FLOOR": "about a minute",
        })


def test_a_non_integer_escalation_threshold_fails_loudly():
    with pytest.raises(ValueError, match="FSSAI_REVIEW_SECOND_REVIEWER_AFTER"):
        ReviewLoadPolicy.from_env({
            "FSSAI_REVIEW_MAX_PER_WINDOW": "60",
            "FSSAI_REVIEW_SECOND_REVIEWER_AFTER": "later",
        })


# -- the deployment actually carries it ------------------------------------


def test_a_deployment_with_no_declaration_enforces_no_review_ceiling(clean_env, tmp_path):
    """Stated explicitly so the absence is a decision, not an accident.

    This is the behaviour every release before this one had, and it was never
    written down anywhere. It is acceptable only because `fssaira doctor` now
    reports it as a finding.
    """
    plane = build_control_plane(profile_path="profiles/student_support.yaml")
    assert plane.authority._oversight is None


def test_a_declared_capacity_reaches_the_authority_the_deployment_uses(clean_env):
    """The regression test for the gap this file exists to close."""
    clean_env.setenv("FSSAI_REVIEW_MAX_PER_WINDOW", "2")
    clean_env.setenv("FSSAI_REVIEW_DELIBERATION_FLOOR", "0")

    plane = build_control_plane(profile_path="profiles/student_support.yaml")
    monitor = plane.authority._oversight
    assert monitor is not None, (
        "the deployment built its approval authority without the oversight monitor, "
        "so review capacity is enforced nowhere outside the CLI trial"
    )
    assert monitor.policy.max_approvals_per_window == 2


def test_runtime_factory_honours_model_fallback_deny(clean_env, monkeypatch):
    """The final factory must not undo the backend selector's fail-closed choice."""
    from fssaira.models import ModelUnavailable
    from fssaira.models.ollama import OllamaModel

    clean_env.setenv("FSSAI_MODEL", "ollama")
    clean_env.setenv("FSSAI_MODEL_FALLBACK", "deny")
    monkeypatch.setattr(
        OllamaModel,
        "health",
        lambda self: {"reachable": False, "detail": "simulated outage"},
    )

    with pytest.raises(ModelUnavailable, match="FSSAI_MODEL_FALLBACK=deny"):
        build_control_plane(profile_path="profiles/student_support.yaml")


def test_the_declared_ceiling_actually_refuses_the_next_approval(clean_env):
    """Wiring it in is only worth anything if it binds on the real path."""
    clean_env.setenv("FSSAI_REVIEW_MAX_PER_WINDOW", "1")
    clean_env.setenv("FSSAI_REVIEW_DELIBERATION_FLOOR", "0")

    plane = build_control_plane(profile_path="profiles/student_support.yaml")
    rule = next(r for r in plane.profile.transitions if r.consequential)

    from fssaira.exact_action import ActionProposal

    def proposal(index: int) -> ActionProposal:
        return ActionProposal(
            request_id=f"req-{index}", requester="agent-1", operation=rule.operation,
            case_id=f"case-{index}", expected_version=1,
            from_status=rule.from_status, to_status=rule.to_status,
            evidence_version="snap-1",
        )

    now = 1_000_000.0
    plane.authority.approve(
        proposal(0), approver="officer-1", approver_role=rule.approval_role,
        now=now, presented_at=now - 100,
    )
    with pytest.raises(ExecutionDenied) as denial:
        plane.authority.approve(
            proposal(1), approver="officer-1", approver_role=rule.approval_role,
            now=now + 1, presented_at=now - 100,
        )
    assert denial.value.code == "REVIEW_CAPACITY_EXCEEDED"


# -- declaring delegation bounds -------------------------------------------


def test_an_undeclared_delegation_bound_is_none():
    assert DelegationPolicy.from_env({}) is None


def test_declaring_a_depth_switches_the_bound_on():
    policy = DelegationPolicy.from_env({"FSSAI_MAX_DELEGATION_DEPTH": "2"})
    assert policy.max_depth == 2
    assert policy.allow_machine_delegated_consequence is False, (
        "a machine passing on authority a human had to grant must stay opt-in"
    )


def test_machine_delegated_consequence_must_be_opted_into_explicitly():
    on = DelegationPolicy.from_env({
        "FSSAI_MAX_DELEGATION_DEPTH": "3",
        "FSSAI_ALLOW_MACHINE_DELEGATED_CONSEQUENCE": "true",
    })
    assert on.allow_machine_delegated_consequence is True


def test_a_non_integer_depth_fails_loudly():
    with pytest.raises(ValueError, match="must be an integer"):
        DelegationPolicy.from_env({"FSSAI_MAX_DELEGATION_DEPTH": "deep"})


def test_an_ambiguous_delegation_boolean_fails_loudly():
    with pytest.raises(ValueError, match="must be a boolean"):
        DelegationPolicy.from_env({
            "FSSAI_MAX_DELEGATION_DEPTH": "3",
            "FSSAI_ALLOW_MACHINE_DELEGATED_CONSEQUENCE": "sometimes",
        })


# -- declaring assistance ---------------------------------------------------


def test_declaring_nothing_means_the_reviewer_is_unaided():
    """Not declaring assistance is itself a declaration, and the strict one."""
    assistance = ReviewAssistance.from_env({})
    assert assistance.mode is AssistanceMode.UNAIDED
    assert assistance.floor_multiplier == 1.0


def test_an_unknown_assistance_mode_names_the_valid_ones():
    with pytest.raises(ValueError, match="unaided, summarised, recommended"):
        ReviewAssistance.from_env({"FSSAI_REVIEW_ASSISTANCE_MODE": "helpful"})


def test_an_ambiguous_assistance_boolean_fails_loudly():
    with pytest.raises(ValueError, match="must be a boolean"):
        ReviewAssistance.from_env({
            "FSSAI_REVIEW_ASSISTANCE_MODE": "recommended",
            "FSSAI_REVIEW_ASSISTANT_INDEPENDENT_MODEL": "perhaps",
        })


def test_each_independence_property_is_declared_separately():
    assistance = ReviewAssistance.from_env({
        "FSSAI_REVIEW_ASSISTANCE_MODE": "recommended",
        "FSSAI_REVIEW_ASSISTANT_INDEPENDENT_MODEL": "true",
        "FSSAI_REVIEW_ASSISTANT_INDEPENDENT_EVIDENCE": "true",
        "FSSAI_REVIEW_ASSISTANT_ADVERSARIAL": "true",
        "FSSAI_REVIEW_ASSISTANCE_DECLARED_BY": "student_services",
    })
    assert assistance.independence_score == 3
    assert assistance.is_independent
    AssistedReviewPolicy().check(assistance, proposed_floor=10.0)  # must not raise


# -- what the operator is told ---------------------------------------------


def test_doctor_reports_an_undeclared_review_capacity(clean_env):
    codes = {item.code for item in configuration_warnings()}
    assert "NO_DECLARED_REVIEW_CAPACITY" in codes, (
        "a deployment that enforces no review ceiling must say so; that was the "
        "silent default for three releases"
    )
    assert "NO_DECLARED_DELEGATION_BOUND" in codes


def test_doctor_blocks_a_lowered_floor_the_declaration_does_not_earn(clean_env):
    """The configuration gate, surfaced where an operator actually looks."""
    clean_env.setenv("FSSAI_REVIEW_MAX_PER_WINDOW", "60")
    clean_env.setenv("FSSAI_REVIEW_DELIBERATION_FLOOR", "10")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_MODE", "recommended")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_DECLARED_BY", "student_services")

    findings = {item.code: item for item in configuration_warnings()}
    assert "FLOOR_BELOW_DECLARED_INDEPENDENCE" in findings
    assert findings["FLOOR_BELOW_DECLARED_INDEPENDENCE"].severity == "blocking"
    assert "45.0s" in findings["FLOOR_BELOW_DECLARED_INDEPENDENCE"].message, (
        "the finding must name the floor the deployment would have to raise to"
    )
    assert findings["DEPENDENT_REVIEW_ASSISTANT"].severity == "high"


def test_doctor_blocks_assistance_that_names_no_accountable_owner(clean_env):
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_MODE", "summarised")
    findings = {item.code: item for item in configuration_warnings()}
    assert findings["ASSISTANCE_NOT_DECLARED"].severity == "blocking"


def test_deployment_refuses_a_lowered_floor_with_dependent_assistance(clean_env):
    clean_env.setenv("FSSAI_REVIEW_MAX_PER_WINDOW", "60")
    clean_env.setenv("FSSAI_REVIEW_DELIBERATION_FLOOR", "10")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_MODE", "recommended")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_DECLARED_BY", "student_services")

    with pytest.raises(ExecutionDenied) as denial:
        build_control_plane(profile_path="profiles/student_support.yaml")
    assert denial.value.code == "FLOOR_BELOW_DECLARED_INDEPENDENCE"


def test_deployment_refuses_assistance_without_an_accountable_owner(clean_env):
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_MODE", "summarised")

    with pytest.raises(ExecutionDenied) as denial:
        build_control_plane(profile_path="profiles/student_support.yaml")
    assert denial.value.code == "ASSISTANCE_NOT_DECLARED"


def test_an_independent_declaration_clears_the_gate(clean_env):
    clean_env.setenv("FSSAI_REVIEW_MAX_PER_WINDOW", "60")
    clean_env.setenv("FSSAI_REVIEW_DELIBERATION_FLOOR", "10")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_MODE", "recommended")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_DECLARED_BY", "student_services")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANT_INDEPENDENT_MODEL", "true")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANT_INDEPENDENT_EVIDENCE", "true")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANT_ADVERSARIAL", "true")

    codes = {item.code for item in configuration_warnings()}
    assert "FLOOR_BELOW_DECLARED_INDEPENDENCE" not in codes
    assert "DEPENDENT_REVIEW_ASSISTANT" not in codes


def test_doctor_reports_a_self_contradicting_review_policy(clean_env):
    """The defect the sensitivity sweep found in our own defaults, as a check."""
    clean_env.setenv("FSSAI_REVIEW_MAX_PER_WINDOW", "5")
    clean_env.setenv("FSSAI_REVIEW_DELIBERATION_FLOOR", "45")
    findings = {item.code for item in configuration_warnings()}
    assert "INCOHERENT_REVIEW_POLICY" in findings, (
        "a quota of 5 against a floor permitting 80 throttles reviewers who are reading"
    )


def test_doctor_reports_malformed_declarations_without_a_traceback(clean_env):
    clean_env.setenv("FSSAI_REVIEW_MAX_PER_WINDOW", "many")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANCE_MODE", "recommended")
    clean_env.setenv("FSSAI_REVIEW_ASSISTANT_INDEPENDENT_MODEL", "perhaps")
    clean_env.setenv("FSSAI_MAX_DELEGATION_DEPTH", "deep")

    findings = {item.code: item for item in configuration_warnings()}
    assert findings["INVALID_REVIEW_POLICY"].severity == "blocking"
    assert findings["INVALID_REVIEW_ASSISTANCE"].severity == "blocking"
    assert findings["INVALID_DELEGATION_POLICY"].severity == "blocking"


def test_doctor_reports_malformed_authentication_without_a_traceback(clean_env):
    clean_env.setenv("FSSAI_AUTH_TOKENS_JSON", '{"token":{"roles":"operator"}}')

    findings = [item for item in configuration_warnings() if item.code == "AUTHENTICATION"]

    assert findings and findings[0].severity == "blocking"
    assert "invalid authentication configuration" in findings[0].message


# -- the documentation and the code must name the same variables ------------


def test_every_variable_the_example_documents_is_actually_read():
    """`.env.example` is the only place most operators will learn these names.

    A variable renamed in code leaves the example documenting something that
    does nothing, and the operator's deployment silently keeps the default they
    were trying to change. Nothing caught that before this test: the example was
    prose, and prose is exactly what this project refuses to trust everywhere
    else.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    example = (root / "deploy" / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*(FSSAI_[A-Z0-9_]+)=", example, re.M))
    assert documented, "the example documents no FSSAI_ variables"

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "src" / "fssaira").rglob("*.py")
    )
    # Host port settings are consumed by Compose itself, not application Python.
    # Restrict this exception to actual port bindings; merely mentioning a
    # variable in Compose must not conceal an unread application setting.
    import yaml

    compose = yaml.safe_load((root / "deploy" / "compose.yaml").read_text())
    port_variables = {
        name
        for service in compose['services'].values()
        for binding in service.get('ports', [])
        for name in re.findall(r"\$\{(FSSAI_[A-Z0-9_]+)(?=[:}])", binding)
    }
    unread = sorted(name for name in documented if name not in source and name not in port_variables)
    assert not unread, (
        "deploy/.env.example documents variables no code reads: "
        + ", ".join(unread)
    )


def test_every_declared_policy_variable_is_documented_for_operators():
    """The reverse direction: a control nobody can find is a control nobody uses.

    These three policies are the ones an institution has to declare about
    itself. If one is readable from the environment and absent from the example,
    it is discoverable only by reading the source, which is not a reasonable ask
    of the registrar who has to sign off on the capacity figure.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    example = (root / "deploy" / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*(FSSAI_[A-Z0-9_]+)=", example, re.M))

    required = {
        "FSSAI_REVIEW_MAX_PER_WINDOW",
        "FSSAI_REVIEW_WINDOW_SECONDS",
        "FSSAI_REVIEW_DELIBERATION_FLOOR",
        "FSSAI_REVIEW_SECOND_REVIEWER_AFTER",
        "FSSAI_REVIEW_SECONDS_PER_DAY",
        "FSSAI_REVIEW_ASSISTANCE_MODE",
        "FSSAI_REVIEW_ASSISTANCE_DECLARED_BY",
        "FSSAI_REVIEW_ASSISTANT_INDEPENDENT_MODEL",
        "FSSAI_REVIEW_ASSISTANT_INDEPENDENT_EVIDENCE",
        "FSSAI_REVIEW_ASSISTANT_ADVERSARIAL",
        "FSSAI_MAX_DELEGATION_DEPTH",
        "FSSAI_HUMAN_APPROVAL_BELOW_DEPTH",
        "FSSAI_ALLOW_MACHINE_DELEGATED_CONSEQUENCE",
    }
    missing = sorted(required - documented)
    assert not missing, (
        "these declarable controls are unreachable from deploy/.env.example: "
        + ", ".join(missing)
    )


def test_the_example_says_what_happens_when_nothing_is_declared():
    """The absence of a declaration is the default, so it has to be stated."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    example = (root / "deploy" / ".env.example").read_text(encoding="utf-8")
    assert "enforces no review ceiling" in example
    assert "reviewers are treated as" in example
