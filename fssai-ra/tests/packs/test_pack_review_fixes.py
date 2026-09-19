"""Review finding M4: a governed pack cannot shed its floor by being listed as a profile."""
from __future__ import annotations

from pathlib import Path

import yaml

from fssaira.kernel.packs import _load_profile_source

ROOT = Path(__file__).resolve().parents[2]
GOVERNED = ROOT / "conference" / "education" / "governed-learning-pack.yaml"


def test_m4_a_governed_pack_without_controls_is_not_exempted(tmp_path):
    doc = yaml.safe_load(GOVERNED.read_text())
    del doc["controls"]
    stripped = tmp_path / "stripped.yaml"
    stripped.write_text(yaml.safe_dump(doc))
    findings, exemptions = [], []
    _load_profile_source(stripped, ROOT, findings, exemptions)
    assert exemptions == []
    assert any("CONTRACT" in f.code for f in findings), [f.code for f in findings]


def test_m4_a_genuine_action_profile_still_reports_its_exemptions():
    findings, exemptions = [], []
    profile = _load_profile_source(ROOT / "profiles" / "corporate_confidential_data.yaml", ROOT, findings, exemptions)
    assert profile is not None and findings == []
    assert any("REVIEW" in e.upper() for e in exemptions)
