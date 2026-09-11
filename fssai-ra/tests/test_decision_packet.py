"""Packet export, negative controls, privacy boundaries and independent inspection."""
import ast
import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fssaira.api import create_app
from fssaira.atomic_execution import AtomicExecutor, sql_evidence, sql_object_store, sql_register
from fssaira.control_plane import ControlPlane
from fssaira.decision_packet import export_decision_packet
from fssaira.exact_action import ExecutionDenied
from fssaira.packet_verifier import canonical_hash, inspect_packet, load_packet, main
from fssaira.profiles import ApplicationProfile
from fssaira.security import AuthConfig, Authenticator
from fssaira.sql_backend import open_sqlite


def record(plane, request_id="packet-1", resource="case-1"):
    plane.register_resource(resource, status="draft")
    plane.propose(request_id=request_id, requester="synthetic-agent", operation="prepare_case_for_review",
                  resource_id=resource, from_status="draft", to_status="ready_for_officer_review",
                  evidence_version="synthetic-evidence-1")
    plane.approve(request_id, approver="synthetic-officer", approver_role="student_support_officer")
    plane.execute(request_id)


@pytest.fixture
def plane():
    plane = ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"))
    record(plane)
    return plane


@pytest.fixture
def packet(plane):
    return export_decision_packet(plane, "packet-1")


def rehash(packet):
    packet["payload_sha256"] = canonical_hash({key: packet[key] for key in ("schema", "payload")})


def test_packet_requires_an_external_fingerprint_for_anchored_status(packet):
    report = inspect_packet(packet)
    assert report["status"] == "unanchored_consistent"
    assert report["external_fingerprint_matches"] is None
    assert not report["approval_signature_authenticated"]
    assert not report["evidence_content_available"]
    assert not report["full_ledger_completeness_checked"]
    anchored = inspect_packet(packet, packet["payload_sha256"])
    assert anchored["status"] == "anchored_consistent"
    assert not anchored["approval_signature_authenticated"]


@pytest.mark.parametrize("section,field,value,code", [
    ("proposal", "case_id", "other-case", "PROPOSAL_BINDING_MISMATCH"),
    ("proposal", "requester", "other-agent", "PROPOSAL_BINDING_MISMATCH"),
    ("approval", "approver", "someone-else", "INTENT_BINDING_MISMATCH"),
    ("approval", "expires_at", 1.0, "APPROVAL_EXPIRED_BEFORE_INTENT"),
    ("receipt", "version", 5, "RECEIPT_ACTION_MISMATCH"),
    ("receipt", "receipt_hash", "0" * 64, "RECEIPT_DIGEST_MISMATCH"),
])
def test_recomputing_outer_hash_does_not_hide_cross_record_changes(packet, section, field, value, code):
    packet["payload"][section][field] = value
    rehash(packet)
    assert code in inspect_packet(packet)["errors"]


@pytest.mark.parametrize("mutation", ["delete", "duplicate", "reverse", "change"])
def test_edited_record_sets_are_rejected(packet, mutation):
    records = packet["payload"]["records"]
    if mutation == "delete":
        records.pop()
    elif mutation == "duplicate":
        records.append(deepcopy(records[0]))
    elif mutation == "reverse":
        records.reverse()
    else:
        records[0]["payload"]["approver"] = "intruder"
    rehash(packet)
    assert not inspect_packet(packet)["consistent"]


def test_consistent_rewrite_still_fails_an_independent_fingerprint(packet):
    anchor = packet["payload_sha256"]
    packet["payload"]["review_context"]["profile"]["manual_fallback"] = "Contact a different office."
    rehash(packet)
    assert inspect_packet(packet)["status"] == "unanchored_consistent"
    assert "EXTERNAL_FINGERPRINT_MISMATCH" in inspect_packet(packet, anchor)["errors"]


@pytest.mark.parametrize("invalid", [None, [], {}, {"schema": "future"}, {"payload": float("nan")}])
def test_malformed_packets_produce_failures_not_acceptance(invalid):
    assert inspect_packet(invalid)["status"] == "inconsistent"


def test_other_cases_and_credentials_are_not_in_the_export(plane):
    record(plane, "private-other-request", "private-other-case")
    packet = export_decision_packet(plane, "packet-1")
    encoded = json.dumps(packet)
    assert "private-other" not in encoded
    assert "non-secret-demo-key-replace-in-production" not in encoded
    assert "teaching-evidence-writer" not in encoded
    assert len(packet["payload"]["records"]) == 2


def test_replaced_approval_makes_export_fail_closed(plane):
    plane.approve("packet-1", approver="new-officer", approver_role="student_support_officer")
    with pytest.raises(ExecutionDenied, match="PACKET_INCONSISTENT"):
        export_decision_packet(plane, "packet-1")


def test_export_requires_a_completed_outcome(plane):
    plane.register_resource("pending", status="draft")
    plane.propose(request_id="pending-request", requester="agent", operation="prepare_case_for_review",
                  resource_id="pending", from_status="draft", to_status="ready_for_officer_review", evidence_version="v1")
    plane.approve("pending-request", approver="officer", approver_role="student_support_officer")
    with pytest.raises(ExecutionDenied, match="PACKET_OUTCOME_MISSING"):
        export_decision_packet(plane, "pending-request")


def test_packet_export_works_on_transactional_sql(tmp_path):
    profile = ApplicationProfile.load("profiles/student_support.yaml")
    database = open_sqlite(str(tmp_path / "packet.sqlite"), evidence_token="test")
    try:
        executor = AtomicExecutor(database, "test", allowed_operations=profile.allowed_operations,
                                  transition_rules=profile.transition_rules,
                                  required_approval_roles=profile.required_approval_roles)
        plane = ControlPlane(profile, register=sql_register(database), evidence=sql_evidence(database),
                             objects=sql_object_store(database), executor=executor)
        record(plane)
        packet = export_decision_packet(plane, "packet-1")
        assert inspect_packet(packet, packet["payload_sha256"])["consistent"]
    finally:
        database.close()


def test_api_export_is_private_operator_only(plane):
    client = TestClient(create_app(plane, authenticator=Authenticator(AuthConfig())))
    url = "/v1/proposals/packet-1/packet"
    assert client.get(url).status_code == 401
    for token in ("dev-agent-token", "dev-officer-token"):
        assert client.get(url, headers={"Authorization": f"Bearer {token}"}).status_code == 403
    response = client.get(url, headers={"Authorization": "Bearer dev-operator-token"})
    assert response.status_code == 200
    assert inspect_packet(response.json())["consistent"]


def test_duplicate_json_fields_and_oversized_files_are_refused(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema": "a", "schema": "b"}')
    with pytest.raises(ValueError, match="duplicate"):
        load_packet(path)
    path.write_bytes(b" " * 2_000_001)
    with pytest.raises(ValueError, match="2 MB"):
        load_packet(path)


def test_cli_exit_codes_distinguish_missing_anchor_from_failed_check(packet, tmp_path, capsys):
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet))
    assert main([str(path)]) == 2
    assert main([str(path), "--expected-sha256", packet["payload_sha256"]]) == 0
    assert main([str(path), "--expected-sha256", "0" * 64]) == 1
    assert main([str(tmp_path / "absent")]) == 1


def test_verifier_runs_without_importing_the_framework(packet, tmp_path):
    source = Path("src/fssaira/packet_verifier.py").resolve()
    imports = [node for node in ast.walk(ast.parse(source.read_text())) if isinstance(node, ast.ImportFrom)]
    assert all(node.level == 0 for node in imports)
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(packet))
    result = subprocess.run([sys.executable, "-I", str(source), str(path), "--expected-sha256",
                             packet["payload_sha256"]], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["status"] == "anchored_consistent"


def test_legacy_receipt_is_not_exported_as_verified(plane):
    prior = plane.register._results["packet-1"]
    plane.register._results["packet-1"] = replace(prior, proposal_digest="")
    with pytest.raises(ExecutionDenied, match="PACKET_INCONSISTENT"):
        export_decision_packet(plane, "packet-1")
