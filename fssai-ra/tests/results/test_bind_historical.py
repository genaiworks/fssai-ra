"""A historical claim is bound only to a committed record that actually states it."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("bind_paper_metrics_historical", ROOT / "scripts" / "bind_paper_metrics.py")
binder = importlib.util.module_from_spec(_spec)
# Registered before execution: @dataclass resolves its module through sys.modules.
sys.modules[_spec.name] = binder
_spec.loader.exec_module(binder)  # type: ignore[union-attr]

PAPER = "# Paper\n\nThe audit executed 841 baseline tests successfully.\n\n## References\n"


def _bindings(tmp_path: Path, entry: dict) -> Path:
    path = tmp_path / "bindings.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "bindings": [entry]}))
    return path


def _entry(contains: str, source: str = "records/baseline.log") -> dict:
    return {"quote": "executed 841 baseline tests successfully", "kind": "historical",
            "justification": "baseline run", "evidence": {"source": source, "contains": contains}}


def test_a_historical_claim_backed_by_its_record_binds(tmp_path):
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "baseline.log").write_text("============ 841 passed in 53.52s ============\n")
    bindings = binder.load_bindings(_bindings(tmp_path, _entry("841 passed")))
    report = binder.bind(PAPER, bindings, {}, root=tmp_path)
    assert not report.mismatches
    assert not report.unbound


def test_a_record_that_does_not_state_the_claim_is_a_mismatch(tmp_path):
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "baseline.log").write_text("============ 840 passed ============\n")
    bindings = binder.load_bindings(_bindings(tmp_path, _entry("841 passed")))
    report = binder.bind(PAPER, bindings, {}, root=tmp_path)
    assert report.mismatches


def test_a_missing_record_is_a_mismatch(tmp_path):
    bindings = binder.load_bindings(_bindings(tmp_path, _entry("841 passed", source="records/absent.log")))
    report = binder.bind(PAPER, bindings, {}, root=tmp_path)
    assert report.mismatches


def test_a_historical_binding_without_evidence_is_refused(tmp_path):
    entry = _entry("841 passed")
    del entry["evidence"]
    with pytest.raises(ValueError, match="historical binding needs evidence"):
        binder.load_bindings(_bindings(tmp_path, entry))
