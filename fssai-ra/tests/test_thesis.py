"""The Mediation Thesis is falsifiable, and the falsifiers can fail."""
import json

import pytest

from fssaira.cli import main
from fssaira.disclosure import ALL_CHECKS
from fssaira.thesis import (
    ROOT,
    TRUSTED_BASE,
    _packs,
    falsify_disclosure,
    run_thesis,
)


@pytest.fixture(scope="module")
def report():
    return run_thesis()


def test_the_thesis_is_not_falsified_within_stated_bounds(report):
    assert [f.id for f in report.falsifiers] == ["F1", "F2", "F3", "F4", "F5", "F6"]
    for falsifier in report.falsifiers:
        assert falsifier.attempts > 0, falsifier.id
        assert falsifier.scope, falsifier.id
    refuted = {f.id: f.detail for f in report.falsifiers if f.refuted}
    assert report.holds, refuted
    assert report.attempts > 50_000


def test_the_report_names_what_it_cannot_cover(report):
    payload = report.to_dict()
    assert payload["summary"]["verdict"] == "not refuted within the stated bounds"
    assert len(payload["residuals"]) >= 5
    assert payload["trusted_base"] == list(TRUSTED_BASE)
    assert any("not a proof" in line for line in payload["reading"])


@pytest.mark.parametrize("removed", ["release_recheck", "session_taint", "recipient_clearance"])
def test_the_falsifiers_find_counterexamples_when_one_mediator_check_is_removed(removed):
    """A suite that cannot fail proves nothing."""
    packs = [p for p in _packs(ROOT) if p.disclosure is not None][:1]
    _read, release = falsify_disclosure(packs, enforce=set(ALL_CHECKS) - {removed})
    assert release.counterexamples > 0, f"removing {removed} went unnoticed"


def test_phantom_evidence_is_detected(tmp_path):
    import shutil

    from fssaira.thesis import falsify_phantom_evidence

    for name in ("contract", "threats", "docs", "tests", "src"):
        shutil.copytree(ROOT / name, tmp_path / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.docx", "*.pptx"))
    spec = tmp_path / "docs" / "SPECIFICATION.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace(
        "tests/test_exact_action.py::test_requester_cannot_approve_own_proposal",
        "tests/test_exact_action.py::test_that_was_deleted"), encoding="utf-8")
    result = falsify_phantom_evidence(tmp_path)
    assert result.counterexamples == 1
    assert "test_that_was_deleted" in result.detail["missing"][0]


def test_thesis_cli_reports_the_verdict(tmp_path):
    output = tmp_path / "thesis.json"
    assert main(["thesis", "--output", str(output)]) == 0
    summary = json.loads(output.read_text())["summary"]
    assert summary["holds"] is True and summary["counterexamples"] == 0
