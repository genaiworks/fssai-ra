"""The swarm profile is normative too: every test it cites must exist."""
import re
from pathlib import Path

from fssaira.threats import locator_exists

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "docs" / "SPECIFICATION_SWARM_PROFILE.md"
ROW = re.compile(r"^\|\s*(SW-[A-Z]-\d+)\s*\|\s*(MUST NOT|MUST|SHOULD|MAY)\s*\|(.+)\|(.+)\|\s*$", re.M)


def test_profile_requirements_are_unique_and_cite_existing_tests():
    found = ROW.findall(PROFILE.read_text(encoding="utf-8"))
    ids = [row[0] for row in found]
    assert len(ids) == 11 and len(set(ids)) == len(ids)
    missing = []
    for rid, _level, _text, evidence in found:
        assert evidence.strip().startswith("test:"), f"{rid} names no test"
        locators = re.findall(r"`(tests/[^`]+)`", evidence)
        assert locators, rid
        missing += [f"{rid}: {loc}" for loc in locators if not locator_exists(ROOT, loc)]
    assert not missing, missing


def test_profile_ids_do_not_collide_with_the_core_specification():
    core = set(re.findall(r"^\|\s*([A-Z]-\d+)\s*\|", (ROOT / "docs" / "SPECIFICATION.md")
                          .read_text(encoding="utf-8"), re.M))
    profile = {rid[3:] for rid, *_ in ROW.findall(PROFILE.read_text(encoding="utf-8"))}
    assert not core & profile
