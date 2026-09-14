"""Envelope encryption, per-subject keys, and cryptographic erasure on the education world."""
import pytest

from fssaira.disclosure import DisclosureDenied
from fssaira.education_world import STUDENTS, EducationWorld
from fssaira.key_custody import CustodyDenied


def test_ciphertext_moved_to_another_student_fails_authentication():
    world = EducationWorld()
    world.records._move_ciphertext(source="stu-a1f3", target="stu-b7c2", field_name="counselling_notes")
    moved = world.records._row("stu-b7c2", "counselling_notes")
    with pytest.raises(CustodyDenied) as refused:
        world.custody.decrypt(world._gate_key, moved, subject="stu-b7c2", field="counselling_notes")
    assert refused.value.code == "CUSTODY_CIPHERTEXT_BINDING_INVALID"


def test_the_intelligence_plane_holds_no_custody_credential():
    world = EducationWorld()
    row = world.records._row("stu-a1f3", "student_name")
    for credential in (None, "", "custody-" + "0" * 48, world._ingest):
        with pytest.raises(CustodyDenied):
            world.custody.decrypt(credential, row, subject="stu-a1f3", field="student_name")
    assert b"Mei Ling Chan" not in world.records.raw_bytes()


def test_erasure_reaches_backups_tokens_indexes_and_outputs():
    world = EducationWorld()
    fields = ("student_name", "support_plan")
    grant = world.grant(holder="support-agent", purpose="academic-support", subjects=["stu-a1f3"],
                        fields=fields)
    context = world.read(requester="support-agent", grant=grant, purpose="academic-support",
                         subjects=["stu-a1f3"], fields=fields, session_id="erase-1")
    world.derive(requester="support-agent", session_id="erase-1",
                 content="SUPPORT-PLAN-A1F3-TUTORING continues for Mei Ling Chan")
    snapshot = world.records.snapshot()
    key_backup = world.custody.backup(world._erase_key)
    assert context.tokens

    world.erasure.erase("stu-a1f3", erased_by="privacy-officer-ng", reason="synthetic erasure request")
    world.erasure.with_backup_credential(world._erase_key)
    report = world.erasure.verify("stu-a1f3", fields=list(STUDENTS["stu-a1f3"]),
                                  plaintexts=list(STUDENTS["stu-a1f3"].values()),
                                  snapshots=[snapshot],
                                  custody_backups=[(key_backup, world.custody.journal)],
                                  restore_credential=world._gate_key)
    body = report.to_dict()
    assert body["readable_locations"] == []
    statuses = {check["location"]: check["status"] for check in body["checks"]}
    assert statuses["primary_record_store"] == "unreadable"
    assert statuses[f"backup:{snapshot.snapshot_id}"] == "unreadable"
    assert statuses["key_backup_1_restored_with_journal"] == "unreadable"
    assert statuses["vector_index"] == "unreadable"
    assert statuses["derived_outputs_gate_1"] == "absent"
    with pytest.raises(DisclosureDenied):
        world.read(requester="support-agent", grant=grant, purpose="academic-support",
                   subjects=["stu-a1f3"], fields=fields, session_id="erase-2")

    # The verifier is not vacuous: an unerased student is reported readable.
    other = EducationWorld()
    other.erasure.with_backup_credential(other._erase_key)
    untouched = other.erasure.verify("stu-b7c2", fields=list(STUDENTS["stu-b7c2"]),
                                     plaintexts=list(STUDENTS["stu-b7c2"].values()),
                                     snapshots=[other.records.snapshot()])
    assert "primary_record_store" in untouched.to_dict()["readable_locations"]


def test_restoring_a_key_backup_without_the_journal_is_refused():
    world = EducationWorld()
    backup = world.custody.backup(world._erase_key)
    world.erasure.erase("stu-a1f3", erased_by="privacy-officer-ng", reason="synthetic")
    with pytest.raises(CustodyDenied):
        world.custody.restore(world._erase_key, backup, None)
    with pytest.raises(CustodyDenied):
        world.custody.restore(world._erase_key, backup, [])
