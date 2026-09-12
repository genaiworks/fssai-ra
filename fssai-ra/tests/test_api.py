"""HTTP contract tests for the control plane.

These cover the property that matters at the API layer: the three-step protocol
is the only way to change a governed resource, and the identity performing each
step is established by the server, not asserted by the caller.
"""
from fastapi.testclient import TestClient

from fssaira.api import create_app
from fssaira.control_plane import ControlPlane
from fssaira.profiles import ApplicationProfile
from fssaira.security import AuthConfig, Authenticator

OPERATOR = {"Authorization": "Bearer dev-operator-token"}
OFFICER = {"Authorization": "Bearer dev-officer-token"}
AGENT = {"Authorization": "Bearer dev-agent-token"}


def build_client() -> TestClient:
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    return TestClient(create_app(ControlPlane(profile), authenticator=Authenticator(AuthConfig())))


def test_openapi_control_plane_workflow():
    client = build_client()

    assert client.post(
        "/v1/resources",
        json={"resource_id": "S-104", "status": "draft", "version": 1},
        headers=OPERATOR,
    ).status_code == 201

    proposal = client.post("/v1/proposals", json={
        "operation": "prepare_case_for_review",
        "resource_id": "S-104",
        "from_status": "draft",
        "to_status": "ready_for_officer_review",
        "evidence_version": "snap-1",
    }, headers=AGENT)
    assert proposal.status_code == 201
    request_id = proposal.json()["request_id"]
    assert proposal.json()["requester"] == "bounded-agent-1"

    approval = client.post(
        f"/v1/proposals/{request_id}/approval", json={"ttl_seconds": 300}, headers=OFFICER
    )
    assert approval.status_code == 201
    # The role comes from the authenticated principal, never from the body.
    assert approval.json()["approver_role"] == "student_support_officer"

    executed = client.post(f"/v1/proposals/{request_id}/execute", headers=OFFICER)
    assert executed.status_code == 200
    assert executed.json()["status"] == "ready_for_officer_review"
    assert executed.json()["version"] == 2

    replay = client.post(f"/v1/proposals/{request_id}/execute", headers=OFFICER)
    assert replay.json()["receipt_hash"] == executed.json()["receipt_hash"]
    assert replay.json()["replayed"] is True

    evidence = client.get(f"/v1/proposals/{request_id}/evidence", headers=OFFICER).json()
    assert [record["kind"] for record in evidence["records"]] == ["action_intent", "action_outcome"]
    assert client.get("/v1/evidence/verify", headers=OFFICER).json()["chain_valid"] is True


def test_api_requires_authentication_and_the_operator_role():
    client = build_client()

    assert client.get("/v1/resources/S-104").status_code == 401
    assert client.get(
        "/v1/resources/S-104", headers={"Authorization": "Bearer forged"}
    ).status_code == 401
    assert client.post(
        "/v1/resources",
        json={"resource_id": "S-900", "status": "draft", "version": 1},
        headers=OFFICER,
    ).status_code == 403


def test_spoofable_headers_are_refused_unless_a_proxy_is_declared():
    """The v0.5.0 header adapter no longer works by accident."""
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    client = TestClient(create_app(
        ControlPlane(profile), authenticator=Authenticator(AuthConfig(mode="header"))
    ))
    response = client.get("/v1/resources/S-104", headers={
        "X-FSSAI-Identity": "attacker", "X-FSSAI-Role": "platform_operator"
    })
    assert response.status_code == 401
    assert "authenticating proxy" in response.json()["detail"]

    trusting = TestClient(create_app(
        ControlPlane(profile),
        authenticator=Authenticator(AuthConfig(mode="header", trust_proxy_headers=True)),
    ))
    assert trusting.get("/v1/resources/S-104", headers={
        "X-FSSAI-Identity": "ops", "X-FSSAI-Role": "platform_operator"
    }).status_code == 404  # authenticated; the resource simply does not exist


def test_health_reports_what_this_deployment_actually_is():
    body = build_client().get("/health").json()
    assert body["durability"] in ("volatile", "best-effort", "single-transaction")
    assert body["evidence_valid"] is True
    assert any("teaching" in warning.lower() for warning in body["configuration_warnings"])


def test_metrics_endpoint_exposes_named_counters():
    body = build_client().get("/metrics").text
    assert "fssaira_evidence_chain_valid" in body
    assert 'profile="student-support"' in body


def test_assurance_endpoints_run_on_the_configured_backends():
    client = build_client()
    verification = client.get("/v1/verification", headers=OPERATOR).json()
    assert verification["summary"]["holds"] is True
    assert verification["summary"]["states_explored"] > 0

    conformance = client.get("/v1/conformance", headers=OPERATOR).json()
    assert conformance["summary"]["conformant"] is True


def test_the_composition_assurance_endpoints_publish_their_own_figures():
    """Coverage, delegation and assisted review are published like conformance.

    An operator replacing a component needs the same three answers about the
    newer controls that they already get about the older ones: does it hold, on
    what, and what does it not establish.
    """
    client = build_client()

    coverage = client.get("/v1/coverage", headers=OPERATOR).json()
    assert coverage["totals"]["unverified"] == 0, (
        "a requirement describing a failure test and binding it to nothing "
        "should be visible on the deployment's own assurance endpoint"
    )
    assert coverage["totals"]["machine_verified"] > 0
    assert coverage["limits"]

    delegation = client.get("/v1/delegation", headers=OPERATOR).json()
    arms = delegation["arms"]
    assert arms["this_architecture"]["contained"] == delegation["hostile_chains"]
    assert arms["this_architecture"]["benign_chain_completed"] is True
    assert arms["caller_checked"]["contained"] < arms["this_architecture"]["contained"]
    assert delegation["verification"]["holds"] is True
    assert all(row["load_bearing"] for row in delegation["ablations"])

    assisted = client.get("/v1/assisted-review", headers=OPERATOR).json()
    summary = assisted["summary"]
    assert summary["configuration_gate_refused_the_harmful_arm"] is True
    assert summary["dependent_assistance_reintroduced_harm"] is True
    assert any("declared parameter" in line for line in assisted["limits"]), (
        "the endpoint must carry the caveat that no model was evaluated"
    )


def test_the_composition_endpoints_require_the_operator_role():
    """They run real checks and publish deployment posture; they are not public."""
    client = build_client()
    for path in ("/v1/coverage", "/v1/delegation", "/v1/assisted-review"):
        assert client.get(path).status_code == 401, f"{path} is reachable unauthenticated"


def test_health_publishes_what_this_deployment_has_declared():
    """An unenforced oversight ceiling is invisible from every other observable.

    A deployment with no declared capacity looks exactly like one running inside
    its capacity, right up to the moment it is not. `/health` therefore states
    the declarations — and states their absence explicitly, because `null` here
    is a posture rather than an omission.
    """
    body = build_client().get("/health").json()
    declared = body["declared_controls"]

    assert declared["review_capacity"] is None
    assert "unbounded" in declared["review_capacity_note"]
    assert declared["review_assistance"]["mode"] == "unaided"
    assert declared["delegation"] is None
    assert declared["limits"], "declarations must not be mistaken for measurements"
    assert any("not measurements" in line for line in declared["limits"])


def test_health_reports_a_declared_capacity_once_one_is_configured(monkeypatch):
    monkeypatch.setenv("FSSAI_REVIEW_MAX_PER_WINDOW", "30")
    monkeypatch.setenv("FSSAI_REVIEW_DELIBERATION_FLOOR", "45")

    from fssaira.oversight import OversightMonitor, ReviewLoadPolicy

    profile = ApplicationProfile.load("profiles/student_support.yaml")
    plane = ControlPlane(profile, oversight=OversightMonitor(ReviewLoadPolicy.from_env()))
    client = TestClient(create_app(plane, authenticator=Authenticator(AuthConfig())))

    declared = client.get("/health").json()["declared_controls"]
    assert declared["review_capacity"]["max_approvals_per_window"] == 30
    assert "enforced" in declared["review_capacity_note"]
