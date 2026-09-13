"""The second rule at the HTTP boundary.

Identity comes from the authenticated principal, grants are held by the server,
and every read, output, declassification, and release is decided by the gate.
"""
import json

import pytest
from fastapi.testclient import TestClient

from fssaira.api import create_app
from fssaira.control_plane import ControlPlane
from fssaira.models.deterministic import DeterministicModel
from fssaira.profiles import ApplicationProfile
from fssaira.security import AuthConfig, Authenticator

HEALTH = "profiles/healthcare_record_access.yaml"
TOKENS = {
    "t-operator": ("platform.operator", ("platform_operator",)),
    "t-privacy": ("privacy.officer", ("healthcare_privacy_officer",)),
    "t-agent": ("clinical-assistant", ("proposer",)),
    "t-other": ("other-agent", ("proposer",)),
    "t-research": ("research.reviewer", ("research_review_authority",)),
    "t-er": ("er.reviewer", ("emergency_access_reviewer",)),
}
OPERATOR = {"Authorization": "Bearer t-operator"}
PRIVACY = {"Authorization": "Bearer t-privacy"}
AGENT = {"Authorization": "Bearer t-agent"}
OTHER = {"Authorization": "Bearer t-other"}
RESEARCH = {"Authorization": "Bearer t-research"}
ER = {"Authorization": "Bearer t-er"}
DIAGNOSIS = "SYNTHETIC-diagnosis-7f3a"


def build(profile_path=HEALTH, endpoint="on_premises_model"):
    plane = ControlPlane(ApplicationProfile.load(profile_path), model=DeterministicModel())
    app = create_app(plane, authenticator=Authenticator(AuthConfig(tokens=TOKENS)),
                     model_endpoint=endpoint)
    client = TestClient(app)
    if profile_path == HEALTH:
        for subject in ("patient-1", "patient-2"):
            loaded = client.post("/v1/disclosure/records", headers=OPERATOR, json={
                "subject": subject,
                "fields": {"diagnosis": f"{DIAGNOSIS}-{subject}",
                           "medications": f"SYNTHETIC-meds-{subject}",
                           "patient_name": f"SYNTHETIC-name-{subject}"},
            })
            assert loaded.status_code == 201, loaded.text
            assert DIAGNOSIS not in loaded.text
    return client, plane


def grant(client, headers=PRIVACY, **overrides):
    body = {"holder": "clinical-assistant", "purpose": "treatment",
            "subjects": ["patient-1"], "fields": ["diagnosis", "medications"]}
    body.update(overrides)
    return client.post("/v1/disclosure/grants", headers=headers, json=body)


def context(client, grant_id, headers=AGENT, **overrides):
    body = {"grant_id": grant_id, "session_id": "s-1", "purpose": "treatment",
            "subjects": ["patient-1"], "fields": ["diagnosis", "medications"]}
    body.update(overrides)
    return client.post("/v1/disclosure/context", headers=headers, json=body)


def test_governed_model_task_reads_only_what_the_grant_allows_and_labels_its_output():
    client, plane = build()
    assert grant(client, headers=AGENT).status_code == 403
    issued = grant(client)
    assert issued.status_code == 201, issued.text
    grant_id = issued.json()["grant_id"]

    released = context(client, grant_id)
    assert released.status_code == 200, released.text
    assert released.json()["values"]["patient-1.diagnosis"] == f"{DIAGNOSIS}-patient-1"
    assert "highly-restricted" in released.json()["label"]["classes"]

    wrong_patient = context(client, grant_id, subjects=["patient-2"])
    assert wrong_patient.status_code == 403
    assert wrong_patient.json()["error"] == "SUBJECT_OUT_OF_SCOPE"
    borrowed = context(client, grant_id, headers=OTHER, session_id="s-other")
    assert borrowed.json()["error"] == "GRANT_HOLDER_MISMATCH"

    task = client.post("/v1/propose-task", headers=AGENT, json={
        "task": "review case for patient-1",
        "governed_context": {"grant_id": grant_id, "session_id": "s-task",
                             "purpose": "treatment", "subjects": ["patient-1"],
                             "fields": ["diagnosis"]},
    })
    assert task.status_code == 200, task.text
    governed = task.json()["disclosure"]
    assert "highly-restricted" in governed["label"]["classes"]
    output_id = governed["output_id"]

    path = f"/v1/disclosure/outputs/{output_id}/release"
    assert client.post(path, headers=OTHER, json={
        "recipient": "treating_clinician", "purpose": "treatment"}).status_code == 403
    exfiltration = client.post(path, headers=AGENT, json={
        "recipient": "external_email", "purpose": "treatment"})
    assert exfiltration.status_code == 403
    assert exfiltration.json()["error"].startswith("RECIPIENT_")
    delivered = client.post(path, headers=AGENT, json={
        "recipient": "treating_clinician", "purpose": "treatment"})
    assert delivered.status_code == 200, delivered.text

    dump = json.dumps([record.payload for record in plane.evidence], default=str)
    assert DIAGNOSIS not in dump
    assert plane.evidence.verify()
    assert plane.evidence.find("disclosure_intent")
    assert plane.evidence.find("release_outcome")


@pytest.mark.parametrize("endpoint,code", [
    ("public_model_api", "RESIDENCY_VIOLATION"),
    ("", "ENDPOINT_UNDECLARED"),
])
def test_an_unapproved_or_undeclared_model_endpoint_receives_nothing(endpoint, code):
    client, _plane = build(endpoint=endpoint)
    grant_id = grant(client).json()["grant_id"]
    refused = context(client, grant_id)
    assert refused.status_code == 403
    assert refused.json()["error"] == code
    summary = client.get("/v1/disclosure", headers=AGENT).json()
    assert summary["model_endpoint_zone"] == ({"public_model_api": "external"}.get(endpoint))


def test_consent_withdrawal_and_revocation_apply_at_the_next_http_read():
    client, _plane = build()
    grant_id = grant(client).json()["grant_id"]
    assert context(client, grant_id).status_code == 200

    assert client.post("/v1/disclosure/consent/withdrawals", headers=AGENT, json={
        "subject": "patient-1", "purpose": "treatment"}).status_code == 403
    assert client.post("/v1/disclosure/consent/withdrawals", headers=PRIVACY, json={
        "subject": "patient-1", "purpose": "treatment"}).status_code == 201
    assert context(client, grant_id).json()["error"] == "CONSENT_WITHDRAWN"

    other = grant(client, subjects=["patient-2"]).json()["grant_id"]
    assert client.post(f"/v1/disclosure/grants/{other}/revoke", headers=PRIVACY,
                       json={"reason": "treatment ended"}).status_code == 200
    revoked = context(client, other, subjects=["patient-2"], session_id="s-2")
    assert revoked.json()["error"] == "GRANT_REVOKED"


def test_declassification_needs_the_declared_role_and_redacts_before_release():
    client, _plane = build()
    grant_id = grant(client, purpose="research", fields=["diagnosis"]).json()["grant_id"]
    read = context(client, grant_id, purpose="research", fields=["diagnosis"], session_id="r-1")
    assert read.status_code == 200, read.text
    output = client.post("/v1/disclosure/outputs", headers=AGENT, json={
        "session_id": "r-1", "content": f"patient-1 has {DIAGNOSIS}-patient-1"}).json()

    path = f"/v1/disclosure/outputs/{output['output_id']}"
    assert client.post(f"{path}/release", headers=AGENT, json={
        "recipient": "research_team", "purpose": "research"}).status_code == 403
    assert client.post(f"{path}/declassify", headers=AGENT,
                       json={"rule": "deidentify_for_research"}).status_code == 403
    lowered = client.post(f"{path}/declassify", headers=RESEARCH,
                          json={"rule": "deidentify_for_research"})
    assert lowered.status_code == 201, lowered.text
    body = lowered.json()
    assert DIAGNOSIS not in body["content"] and "patient-1" not in body["content"]
    assert body["label"]["classes"] == ["de-identified"]
    released = client.post(f"/v1/disclosure/outputs/{body['output_id']}/release", headers=AGENT,
                           json={"recipient": "research_team", "purpose": "research"})
    assert released.status_code == 200, released.text


def test_break_glass_is_self_declared_bounded_and_blocked_until_independently_reviewed():
    client, _plane = build()
    emergency = {"holder": "clinical-assistant", "purpose": "emergency-treatment",
                 "break_glass": True, "ttl_seconds": 600,
                 "justification": "synthetic: patient unresponsive"}
    assert grant(client, headers=AGENT, **{**emergency, "holder": "other-agent"}).status_code == 403
    first = grant(client, headers=AGENT, **emergency).json()["grant_id"]
    assert context(client, first, purpose="emergency-treatment", session_id="e-1").status_code == 200
    assert client.get("/v1/disclosure", headers=ER).json()["open_break_glass_reviews"] == [first]

    second = grant(client, headers=AGENT, **emergency).json()["grant_id"]
    overdue = context(client, second, purpose="emergency-treatment", session_id="e-2")
    assert overdue.json()["error"] == "BREAK_GLASS_REVIEW_OVERDUE"

    review = f"/v1/disclosure/break-glass/{first}/review"
    assert client.post(review, headers=AGENT, json={"finding": "fine"}).status_code == 403
    assert client.post(review, headers=ER, json={"finding": "justified"}).status_code == 200
    assert context(client, second, purpose="emergency-treatment", session_id="e-2").status_code == 200


def test_undeclared_fields_are_refused_and_packs_without_a_policy_have_no_disclosure_routes():
    client, _plane = build()
    refused = client.post("/v1/disclosure/records", headers=OPERATOR, json={
        "subject": "patient-3", "fields": {"credit_card": "x"}})
    assert refused.status_code == 403
    assert refused.json()["error"] == "FIELD_UNDECLARED"
    assert grant(client, fields=["credit_card"]).status_code == 422

    plain, _ = build("profiles/student_support.yaml")
    agent = {"Authorization": "Bearer t-agent"}
    assert plain.get("/v1/disclosure", headers=agent).status_code == 404
    assert plain.post("/v1/propose-task", headers=agent, json={
        "task": "review case", "governed_context": {
            "grant_id": "g", "session_id": "s", "purpose": "p",
            "subjects": ["x"], "fields": ["y"]}}).status_code == 404
