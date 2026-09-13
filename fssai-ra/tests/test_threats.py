"""The alignment-independence claim is a catalogue whose evidence must run."""
import json
from pathlib import Path

import pytest

from fssaira.cli import main
from fssaira.threats import (
    FAMILIES,
    ThreatCatalogueError,
    check_catalogue,
    load_catalogue,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "threats" / "catalogue.yaml"


def test_every_evidence_locator_in_the_threat_catalogue_exists():
    report = check_catalogue(CATALOGUE, ROOT)
    assert report.holds, report.missing_locators


def test_the_catalogue_covers_every_family_and_states_residuals():
    threats = load_catalogue(CATALOGUE)
    assert {t.family for t in threats} == set(FAMILIES)
    residual_families = {t.family for t in threats if t.status == "residual"}
    assert {"alignment", "security", "data", "systemic"} <= residual_families
    assert len({t.id for t in threats}) == len(threats)


def _write(tmp_path, body: str) -> Path:
    path = tmp_path / "catalogue.yaml"
    path.write_text(body, encoding="utf-8")
    return path


BASE = """threats:
  - id: R-1
    family: systemic
    title: remains
    threat: something remains
    controls: [none]
    status: residual
    residual: stated
"""


@pytest.mark.parametrize("entry,message", [
    ("""  - id: X-1
    family: alignment
    title: t
    threat: t
    controls: [c]
    status: contained
""", "with no evidence"),
    ("""  - id: X-1
    family: alignment
    title: t
    threat: t
    controls: [c]
    status: bounded
    evidence: [tests/test_threats.py::test_the_catalogue_covers_every_family_and_states_residuals]
""", "does not say what remains"),
    ("""  - id: X-1
    family: vibes
    title: t
    threat: t
    controls: [c]
    status: residual
    residual: r
""", "family must be"),
    ("""  - id: R-1
    family: systemic
    title: t
    threat: t
    controls: [c]
    status: residual
    residual: r
""", "duplicate threat id"),
])
def test_the_catalogue_refuses_unsupported_or_malformed_claims(tmp_path, entry, message):
    with pytest.raises(ThreatCatalogueError, match=message):
        load_catalogue(_write(tmp_path, BASE + entry))


def test_a_catalogue_with_no_residuals_is_refused(tmp_path):
    body = """threats:
  - id: X-1
    family: alignment
    title: t
    threat: t
    controls: [c]
    status: contained
    evidence: [tests/test_threats.py::test_a_catalogue_with_no_residuals_is_refused]
"""
    with pytest.raises(ThreatCatalogueError, match="marketing document"):
        load_catalogue(_write(tmp_path, body))


def test_a_locator_naming_a_test_that_does_not_exist_is_reported(tmp_path):
    body = BASE + """  - id: X-1
    family: alignment
    title: t
    threat: t
    controls: [c]
    status: contained
    evidence: [tests/test_threats.py::test_that_was_deleted]
"""
    report = check_catalogue(_write(tmp_path, body), ROOT)
    assert not report.holds
    assert report.missing_locators == ("X-1: tests/test_threats.py::test_that_was_deleted",)


def test_threats_cli_writes_machine_readable_report(tmp_path):
    output = tmp_path / "threats.json"
    assert main(["threats", "--output", str(output)]) == 0
    summary = json.loads(output.read_text())["summary"]
    assert summary["holds"] is True
    assert summary["residual"] >= 4
    assert summary["contained"] + summary["bounded"] + summary["residual"] == summary["threats"]
