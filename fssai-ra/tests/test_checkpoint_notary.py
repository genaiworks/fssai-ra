"""The running system signs evidence checkpoints and detects a deleted tail."""
import json
import os
import secrets

import pytest
from fastapi.testclient import TestClient

from fssaira import ApplicationProfile, ControlPlane
from fssaira.checkpoint_notary import CheckpointNotary
from fssaira.evidence import EvidenceLedger


def key_file(tmp_path):
    path = tmp_path / "notary.key"
    path.write_text(secrets.token_hex(32))
    os.chmod(path, 0o600)
    return path


def ledger(count):
    led = EvidenceLedger("t")
    for i in range(count):
        led.append("decision", {"request_id": f"r-{i}"}, token="t")
    return led


def test_checkpoints_are_appended_and_survive_a_restart(tmp_path):
    notary = CheckpointNotary.from_files(key_file(tmp_path), tmp_path / "checkpoints")
    led = ledger(2)
    notary.sign(led)
    led.append("decision", {"request_id": "r-2"}, token="t")
    notary.sign(led)
    lines = (tmp_path / "checkpoints" / "checkpoints.jsonl").read_text().splitlines()
    assert [json.loads(line)["count"] for line in lines] == [2, 3]
    restarted = CheckpointNotary.from_files(tmp_path / "notary.key", tmp_path / "checkpoints")
    assert restarted.latest().count == 3
    assert restarted.verify(led)["valid"]


def test_a_deleted_tail_is_detected_against_the_latest_checkpoint(tmp_path):
    notary = CheckpointNotary.from_files(key_file(tmp_path), tmp_path / "cp")
    led = ledger(3)
    notary.sign(led)
    truncated = EvidenceLedger("t")
    truncated._records.extend(list(led)[:2])
    verdict = notary.verify(truncated)
    assert not verdict["valid"] and verdict["code"] == "LEDGER_TRUNCATED"


def test_a_forged_checkpoint_line_is_rejected(tmp_path):
    notary = CheckpointNotary.from_files(key_file(tmp_path), tmp_path / "cp")
    notary.sign(ledger(1))
    path = tmp_path / "cp" / "checkpoints.jsonl"
    row = json.loads(path.read_text())
    row["count"] = 0
    path.write_text(json.dumps(row) + "\n")
    verdict = notary.verify(ledger(1))
    assert verdict["valid"] is False and verdict["code"] == "CHECKPOINTS_FORGED"


def test_a_forged_high_count_line_cannot_hijack_verification(tmp_path):
    notary = CheckpointNotary.from_files(key_file(tmp_path), tmp_path / "cp")
    led = ledger(2)
    notary.sign(led)
    with open(tmp_path / "cp" / "checkpoints.jsonl", "a") as handle:
        handle.write(json.dumps({"count": 999, "head_hash": "0" * 64, "signed_at": 9e9,
                                 "key_id": "evidence-notary-1", "signature": "00" * 64}) + "\n")
    verdict = notary.verify(led)
    assert verdict["valid"] is True and verdict["forged_checkpoint_lines"] == 1


def test_no_checkpoint_yet_is_reported_not_passed(tmp_path):
    notary = CheckpointNotary.from_files(key_file(tmp_path), tmp_path / "cp")
    assert notary.verify(ledger(1)) == {"valid": None, "code": "NO_CHECKPOINT",
                                        "detail": "no signed checkpoint has been retained yet"}


def test_executions_are_checkpointed_and_exposed_over_http(tmp_path, monkeypatch):
    from fssaira.api import create_app
    from fssaira.security import Authenticator

    monkeypatch.setenv("FSSAI_AUTH_MODE", "token")
    notary = CheckpointNotary.from_files(key_file(tmp_path), tmp_path / "cp")
    plane = ControlPlane(ApplicationProfile.load("profiles/student_support.yaml"), notary=notary)
    plane.register_resource("S-1", status="draft")
    plane.propose(request_id="r-1", requester="agent-1", operation="prepare_case_for_review",
                  resource_id="S-1", from_status="draft", to_status="ready_for_officer_review",
                  evidence_version="v1")
    plane.approve("r-1", approver="officer-1", approver_role="student_support_officer")
    plane.execute("r-1")
    assert notary.latest().count == len(plane.evidence)

    client = TestClient(create_app(plane, authenticator=Authenticator()))
    token = {"Authorization": "Bearer dev-operator-token"}
    checkpoint = client.get("/v1/evidence/checkpoint", headers=token).json()
    assert checkpoint["checkpoint"]["count"] == len(plane.evidence)
    assert set(checkpoint["public_keys"]) == {notary.notary.key_id}
    verify = client.get("/v1/evidence/verify", headers=token).json()
    assert verify["checkpoint"]["valid"] is True


def test_the_highest_signed_count_is_authoritative_whatever_the_line_order(tmp_path):
    notary = CheckpointNotary.from_files(key_file(tmp_path), tmp_path / "cp")
    longer = ledger(3)
    notary.sign(longer)
    notary.sign(EvidenceLedger("t"))   # a late write from a slower thread, count 0
    assert notary.latest().count == 3
    truncated = EvidenceLedger("t")
    truncated._records.extend(list(longer)[:2])
    assert notary.verify(truncated)["code"] == "LEDGER_TRUNCATED"


def test_signing_uses_the_head_not_the_whole_ledger(tmp_path):
    class HeadOnly:
        def head(self):
            return 2, "ab" * 32

        def __iter__(self):
            raise AssertionError("the notary read the whole ledger")

    notary = CheckpointNotary.from_files(key_file(tmp_path), tmp_path / "cp")
    checkpoint = notary.sign(HeadOnly())
    assert checkpoint.count == 2 and checkpoint.head_hash == "ab" * 32


@pytest.mark.parametrize("backend", ["memory", "sql", "redis"])
def test_every_ledger_reports_its_head(tmp_path, backend):
    if backend == "memory":
        led = ledger(3)
    elif backend == "sql":
        from fssaira.atomic_execution import sql_evidence
        from fssaira.sql_backend import open_sqlite
        led = sql_evidence(open_sqlite(str(tmp_path / "h.sqlite"), evidence_token="t"))
        for i in range(3):
            led.append("decision", {"request_id": f"r-{i}"}, token="t")
    else:
        import fakeredis

        from fssaira.redis_backend import RedisEvidenceLedger
        led = RedisEvidenceLedger(fakeredis.FakeRedis(decode_responses=True), "t", "h")
        for i in range(3):
            led.append("decision", {"request_id": f"r-{i}"}, token="t")
    records = list(led)
    assert led.head() == (3, records[-1].hash)
