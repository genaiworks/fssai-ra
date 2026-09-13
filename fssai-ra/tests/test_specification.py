"""The specification is normative, so every test it cites must exist."""
import re
from pathlib import Path

from fssaira.threats import locator_exists

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "SPECIFICATION.md"
ROW = re.compile(r"^\|\s*([A-Z]-\d+)\s*\|\s*(MUST NOT|MUST|SHOULD|MAY)\s*\|(.+)\|(.+)\|\s*$", re.M)


def rows():
    return ROW.findall(SPEC.read_text(encoding="utf-8"))


def test_every_requirement_has_a_unique_id_a_level_and_an_evidence_kind():
    found = rows()
    ids = [row[0] for row in found]
    assert len(ids) >= 35
    assert len(set(ids)) == len(ids), "duplicate requirement ids"
    for rid, _level, _text, evidence in found:
        kind = evidence.strip().split(":", 1)[0]
        assert kind in {"test", "attestation", "measurement"}, f"{rid} names no evidence kind"


def test_every_cited_test_in_the_specification_exists():
    missing = []
    for rid, _level, _text, evidence in rows():
        if evidence.strip().startswith("test:"):
            locators = re.findall(r"`(tests/[^`]+)`", evidence)
            assert locators, f"{rid} claims test evidence but cites none"
            missing += [f"{rid}: {loc}" for loc in locators if not locator_exists(ROOT, loc)]
    assert not missing, missing


def test_every_conformance_class_has_mandatory_requirements():
    prefixes = {rid.split("-")[0] for rid, level, *_ in rows() if level.startswith("MUST")}
    assert prefixes >= {"T", "A", "D", "C", "E", "V"}


def test_most_mandatory_requirements_are_backed_by_tests_not_attestation():
    mandatory = [row for row in rows() if row[1].startswith("MUST")]
    tested = [row for row in mandatory if row[3].strip().startswith("test:")]
    assert len(tested) / len(mandatory) >= 0.9
