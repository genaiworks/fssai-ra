"""Does the method work on a domain it was not designed against?

Every result elsewhere in this repository is measured on ``student_support``,
the profile the architecture was built around. That is the weakest possible
position from which to claim a *method*: a suite tuned to one shape will pass on
that shape whether or not anything general is happening.

So ``academic_record_correction`` was added through the documented extension
path — copy the template, declare the transitions, run the suite — and these
tests assert that the identical verifier, evaluator, and conformance suite hold
against it **with no change to library code**. That last clause is the whole
claim. A generalization that required editing the enforcement point to
accommodate the new domain would not be one.

It earned its place immediately. The second profile's first bounded model check
failed, and the defect was real: :attr:`ApplicationProfile.required_approval_roles`
was built only from *consequential* transitions, so a routine step that declared
an ``approval_role`` had it silently ignored. The field was mandatory in the
schema, present in the profile, visible to any reviewer reading it — and absent
at runtime. It was unreachable in ``student_support`` because every transition
there is consequential. One domain could not have found it; two did, on the
first run. ``test_a_declared_role_is_enforced_on_every_transition`` is its
regression.
"""
from fssaira.conformance import memory_bundle, run_conformance, sql_bundle
from fssaira.evaluation import EvaluationRunner
from fssaira.evidence import EvidenceLedger
from fssaira.exact_action import (
    ActionProposal,
    ApprovalAuthority,
    CaseRegister,
    ExecutionDenied,
)
from fssaira.packet_verifier import canonical_hash, inspect_packet
from fssaira.profiles import ApplicationProfile
from fssaira.verification import verify_profile

SECOND_DOMAIN = "profiles/academic_record_correction.yaml"
FIRST_DOMAIN = "profiles/student_support.yaml"
NOW = 1_000_000.0
TOKEN = "generalization-evidence-writer"


def second_domain() -> ApplicationProfile:
    return ApplicationProfile.load(SECOND_DOMAIN)


# -- the regression -------------------------------------------------------

def test_a_declared_role_is_enforced_on_every_transition():
    """The defect the second domain exposed, pinned.

    ``submit_correction_request`` is declared non-consequential and names
    ``records_clerk``. An authentic approval carrying any other role must be
    refused. Before the fix it executed.
    """
    profile = second_domain()
    register = CaseRegister({"record-1": {"status": "draft", "version": 1}})
    evidence = EvidenceLedger(TOKEN)
    executor = profile.make_executor(register, evidence, TOKEN)
    proposal = ActionProposal(
        request_id="generalization-1",
        requester="bounded-agent",
        operation="submit_correction_request",
        case_id="record-1",
        expected_version=1,
        from_status="draft",
        to_status="awaiting_instructor_confirmation",
        evidence_version="snapshot-1",
    )
    authority = ApprovalAuthority()
    wrong_role = authority.approve(
        proposal, approver="a-real-reviewer", approver_role="registrar", now=NOW,
    )

    try:
        executor.execute(proposal, wrong_role, now=NOW)
        raise AssertionError("a non-consequential transition accepted an undeclared role")
    except ExecutionDenied as denial:
        assert denial.code == "APPROVER_ROLE_NOT_ALLOWED"
    assert register.mutation_count == 0


def test_the_declared_role_still_authorizes_the_transition_it_is_declared_for():
    """The fix must not turn the routine step into one nobody can perform."""
    profile = second_domain()
    register = CaseRegister({"record-1": {"status": "draft", "version": 1}})
    evidence = EvidenceLedger(TOKEN)
    executor = profile.make_executor(register, evidence, TOKEN)
    proposal = ActionProposal(
        request_id="generalization-2",
        requester="bounded-agent",
        operation="submit_correction_request",
        case_id="record-1",
        expected_version=1,
        from_status="draft",
        to_status="awaiting_instructor_confirmation",
        evidence_version="snapshot-1",
    )
    approval = ApprovalAuthority().approve(
        proposal, approver="a-real-reviewer", approver_role="records_clerk", now=NOW,
    )

    result = executor.execute(proposal, approval, now=NOW)

    assert result.status == "awaiting_instructor_confirmation"
    assert register.mutation_count == 1


def test_the_offline_packet_checker_agrees_with_the_executor_on_routine_steps():
    """A checker that cleared what the executor refuses is the worst disagreement.

    Built from a genuine export rather than hand-assembled JSON, then altered in
    the one way that leaves the packet internally consistent: the declared role
    in the exported profile no longer matches the role that actually approved.
    That models an exporter whose configuration drifted away from the approval,
    and it must be caught on a routine step exactly as on a consequential one.
    """
    from fssaira.control_plane import ControlPlane
    from fssaira.decision_packet import export_decision_packet

    profile = second_domain()
    plane = ControlPlane(profile)
    plane.register_resource("record-1", status="draft")
    proposal = plane.propose(
        requester="bounded-agent", operation="submit_correction_request",
        resource_id="record-1", from_status="draft",
        to_status="awaiting_instructor_confirmation", evidence_version="snapshot-1",
    )
    plane.approve(proposal.request_id, approver="a-real-reviewer",
                  approver_role="records_clerk")
    plane.execute(proposal.request_id)

    packet = export_decision_packet(plane, proposal.request_id)
    assert inspect_packet(packet)["consistent"], "the genuine export must verify"

    body = {"schema": packet["schema"], "payload": packet["payload"]}
    for rule in body["payload"]["review_context"]["profile"]["transitions"]:
        if rule["operation"] == "submit_correction_request":
            rule["approval_role"] = "registrar"  # drifted away from the approval
    drifted = {**body, "payload_sha256": canonical_hash(body)}

    report = inspect_packet(drifted)

    assert "EXPORT_PROFILE_ROLE_MISMATCH" in report["errors"]


# -- the generalization claim ---------------------------------------------

def test_the_unchanged_model_checker_holds_on_a_second_domain():
    report = verify_profile(second_domain())

    assert report.holds
    assert not report.violations
    # A structurally larger domain: more transitions, more roles, a cycle.
    assert report.states_explored > verify_profile(
        ApplicationProfile.load(FIRST_DOMAIN)
    ).states_explored


def test_the_unchanged_evaluation_suite_holds_on_a_second_domain():
    report = EvaluationRunner(second_domain()).run()

    assert report.all_contained
    assert report.unauthorized_mutations == 0
    assert report.benign_completed == len(report.utility)
    assert report.coverage.authority_coverage == 1.0


def test_every_declared_transition_of_the_second_domain_is_exercised_benignly():
    """Containment on a domain whose legitimate work never runs proves nothing."""
    report = EvaluationRunner(second_domain()).run()
    completed = {item.task for item in report.utility if item.completed}

    for rule in second_domain().transitions:
        marker = f"{rule.operation}_{rule.from_status}_to_{rule.to_status}"
        assert any(marker in task for task in completed), f"{marker} never completed"


def test_the_unchanged_conformance_suite_holds_on_a_second_domain_and_two_backends():
    profile = second_domain()

    for bundle in (memory_bundle(profile), sql_bundle(profile=profile)):
        report = run_conformance(bundle)
        assert report.passed, [check.id for check in report.failures]
        assert len(report.executed) == 25


def test_the_second_domain_carries_its_own_evidence_and_borrows_none():
    """The extension guide forbids inheriting another domain's results.

    Both profiles score 1.0 on authority coverage, and that is only meaningful
    because each figure was produced by running the suite against that profile.
    This asserts the reports are genuinely distinct objects, not a shared one.
    """
    first = EvaluationRunner(ApplicationProfile.load(FIRST_DOMAIN)).run()
    second = EvaluationRunner(second_domain()).run()

    assert first.profile_id != second.profile_id
    assert second.profile_id == "academic-record-correction"
    # The second domain declares more legitimate work, so the denominators differ.
    assert len(second.utility) > len(first.utility)
