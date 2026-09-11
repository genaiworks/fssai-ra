from fastapi.testclient import TestClient

from fssaira import ApplicationProfile, ControlPlane
from fssaira.api import create_app


def headers(identity="operator-1", role="platform_operator"):
    return {"X-FSSAI-Identity": identity, "X-FSSAI-Role": role}


def test_openapi_control_plane_workflow():
    plane = ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"))
    with TestClient(create_app(plane)) as client:
        assert client.get("/health").status_code == 200
        created = client.post(
            "/v1/resources", headers=headers(),
            json={"resource_id": "S-300", "status": "draft", "version": 1},
        )
        assert created.status_code == 201
        proposal = client.post(
            "/v1/proposals", headers=headers("agent-1", "bounded_agent"),
            json={
                "request_id": "req-300", "operation": "prepare_case_for_review",
                "resource_id": "S-300", "from_status": "draft",
                "to_status": "ready_for_officer_review", "evidence_version": "snapshot-300",
            },
        )
        assert proposal.status_code == 201
        approval = client.post(
            "/v1/proposals/req-300/approval",
            headers=headers("officer-1", "student_support_officer"), json={},
        )
        assert approval.status_code == 201
        executed = client.post(
            "/v1/proposals/req-300/execute", headers=headers("executor", "executor")
        )
        assert executed.status_code == 200
        assert executed.json()["status"] == "ready_for_officer_review"
        evidence = client.get(
            "/v1/proposals/req-300/evidence", headers=headers("auditor", "auditor")
        )
        assert len(evidence.json()["records"]) == 2


def test_api_denies_missing_identity_and_wrong_operator_role():
    plane = ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"))
    with TestClient(create_app(plane)) as client:
        assert client.post("/v1/resources", json={
            "resource_id": "S", "status": "draft", "version": 1
        }).status_code == 422
        assert client.post("/v1/resources", headers=headers("agent", "bounded_agent"), json={
            "resource_id": "S", "status": "draft", "version": 1
        }).status_code == 403
