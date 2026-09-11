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
