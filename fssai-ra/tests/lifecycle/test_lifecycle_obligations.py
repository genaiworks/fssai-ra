"""Table 4 obligations: promotion needs a current, owned, signed record for every hurdle."""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest
import yaml

from fssaira.lifecycle.obligations import HURDLES, check_obligations

TODAY = date(2026, 9, 15)


def _record(tmp_path: Path, **override) -> Path:
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("negative tests from the model container: all denied\n")
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    entries = []
    for hurdle in HURDLES:
        entry = {
            "hurdle": hurdle, "owner": "Security owner", "signed_by": "Independent assessor",
            "evidence": "evidence.txt", "evidence_sha256": digest,
            "date": "2026-09-01", "expires": "2027-03-01",
            "accepted_residual_risk": "insider collusion remains residual",
        }
        entry.update(override.get(hurdle, {}))
        entries.append(entry)
    path = tmp_path / "obligations.yaml"
    path.write_text(yaml.safe_dump({"profile": "institutional", "obligations": entries}))
    return path


def test_table_four_has_fourteen_hurdles():
    assert len(HURDLES) == len(set(HURDLES)) == 14


def test_a_complete_current_record_passes_but_never_claims_the_obligation_was_met(tmp_path):
    report = check_obligations(_record(tmp_path), today=TODAY)
    assert report.complete and report.present == report.denominator == 14
    assert "cannot confirm the obligations were met" in report.detail


def test_no_record_fails():
    report = check_obligations(None, today=TODAY)
    assert not report.complete and report.present == 0


@pytest.mark.parametrize("override,message", [
    ({"owner": ""}, "empty owner"),
    ({"accepted_residual_risk": " "}, "empty accepted_residual_risk"),
    ({"expires": "2026-09-10"}, "expired"),
    ({"date": "2026-12-01"}, "future"),
    ({"evidence_sha256": "0" * 64}, "digest does not match"),
    ({"evidence_sha256": "not-a-digest"}, "not a sha256"),
    ({"evidence": "missing.txt"}, "does not exist"),
    ({"signed_by": "Security owner"}, "same identity"),
])
def test_each_defect_in_one_obligation_fails_the_record(tmp_path, override, message):
    report = check_obligations(_record(tmp_path, bypass_and_common_mode=override), today=TODAY)
    assert not report.complete
    assert any(message in problem for problem in report.problems), report.problems


def test_a_missing_or_duplicated_hurdle_fails(tmp_path):
    path = _record(tmp_path)
    doc = yaml.safe_load(path.read_text())
    doc["obligations"] = doc["obligations"][1:] + [doc["obligations"][1]]
    path.write_text(yaml.safe_dump(doc))
    report = check_obligations(path, today=TODAY)
    assert not report.complete
    assert any("missing: bypass_and_common_mode" in p for p in report.problems)
    assert any("recorded twice" in p for p in report.problems)


def test_remote_evidence_is_accepted_by_digest_without_being_fetched(tmp_path):
    report = check_obligations(_record(tmp_path, memory_retrieval_modality={
        "evidence": "https://records.example.org/probe-2026-09.json"}), today=TODAY)
    assert report.complete
