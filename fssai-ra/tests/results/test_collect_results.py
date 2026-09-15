"""``audit/results.json`` is read from committed results, never typed.

Every leaf must resolve, through its own source pointer, to exactly the value it
carries; every ratio must keep a denominator no smaller than its value; every
source file must still hash to the digest recorded; and ``--check`` must notice
when a source changes.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "audit" / "results.json"
PYTHON = sys.executable


def _load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


collector = _load_script("collect_results")


@pytest.fixture(scope="module")
def results() -> dict[str, Any]:
    assert RESULTS.exists(), "run scripts/collect_results.py"
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def _resolve(source: str) -> Any:
    rel, pointer = collector.split_source(source)
    document = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    return collector.resolve_pointer(document, pointer)


def _check_value(leaf: dict[str, Any], value_key: str, source_key: str,
                 derivation_key: str, cross_key: str) -> None:
    derivation = leaf.get(derivation_key)
    source = leaf[source_key]
    expected = leaf[value_key]
    if derivation is None:
        assert _resolve(source) == expected, source
        assert type(_resolve(source)) is type(expected), source
    elif derivation["op"] == "key_name":
        _resolve(source)  # the member exists
        assert collector.key_name_number(collector.split_source(source)[1]) == expected
    elif derivation["op"] == "claims_register":
        counts = collector.claims_register_counts(ROOT)
        assert counts[derivation["row_source"]][derivation["class"]] == expected
    else:
        assert collector.apply_derivation(_resolve(source), derivation) == expected, source
        if cross_key in leaf:
            assert _resolve(leaf[cross_key]) == expected, leaf[cross_key]


def test_results_file_has_the_brief_suites(results: dict[str, Any]) -> None:
    for suite in ("comparison_arms", "reference_profile", "disclosure", "delegation",
                  "review_capacity", "transfer", "safety_case", "self_application",
                  "education_demo", "joined_workflow", "sources"):
        assert suite in results, suite
    assert results["generated_by"] == "scripts/collect_results.py"


def test_every_leaf_has_the_four_fields(results: dict[str, Any]) -> None:
    leaves = collector.iter_leaves(results)
    assert len(leaves) > 150
    for path, leaf in leaves:
        assert {"value", "denominator", "unit", "source"} <= set(leaf), path
        assert isinstance(leaf["unit"], str) and leaf["unit"], path


def test_every_leaf_source_pointer_resolves_to_that_exact_value(results: dict[str, Any]) -> None:
    for _, leaf in collector.iter_leaves(results):
        _check_value(leaf, "value", "source", "derivation", "cross_check")


def test_every_ratio_keeps_a_resolvable_denominator_no_smaller_than_its_value(
        results: dict[str, Any]) -> None:
    ratios = [(p, leaf) for p, leaf in collector.iter_leaves(results) if leaf["denominator"] is not None]
    assert len(ratios) > 60
    for path, leaf in ratios:
        assert leaf["denominator"] >= leaf["value"], path
        assert "denominator_source" in leaf, path
        _check_value(leaf, "denominator", "denominator_source", "denominator_derivation",
                     "denominator_cross_check")


def test_recorded_sha256_match_the_source_files(results: dict[str, Any]) -> None:
    for rel, digest in results["sources"].items():
        assert collector.sha256_file(ROOT / rel) == digest, rel
    cited = {collector.split_source(leaf["source"])[0] for _, leaf in collector.iter_leaves(results)}
    assert {rel for rel in cited if not rel.endswith("/")} <= set(results["sources"])


def test_file_is_deterministic_and_carries_no_timestamps(results: dict[str, Any]) -> None:
    text = RESULTS.read_text(encoding="utf-8")
    assert "generated_at" not in text
    assert collector.encode(collector.collect()) == text


def test_units_are_never_pooled_and_headlines_keep_denominators(results: dict[str, Any]) -> None:
    ref = results["reference_profile"]
    assert (ref["scenarios"]["value"], ref["scenarios"]["denominator"]) == (30, 30)
    arms = results["comparison_arms"]
    assert set(arms["actions"]) >= {"unit", "arms"}
    assert arms["actions"]["unit"] != arms["disclosure_flows"]["unit"] != arms["delegation_chains"]["unit"]
    labels = [arm["arm"] for arm in arms["actions"]["arms"]]
    committed = json.loads((ROOT / "evaluation/results/v1.0.0-architecture-comparison.json").read_text())
    assert labels == [arm["arm"] for arm in committed["arms"]]


def test_self_application_register_agrees_with_legacy_counts(results: dict[str, Any]) -> None:
    self_app = results["self_application"]
    register = self_app["claims_register"]["contract"]
    legacy = self_app["legacy_contract_counts"]
    assert {k: v["value"] for k, v in register.items()} == {k: v["value"] for k, v in legacy.items()}


def test_table5_is_counted_from_raw_episodes(results: dict[str, Any]) -> None:
    joined = results["joined_workflow"]
    assert "raw per-episode records" in joined["method"]
    cells = joined["table5"]["cells"]
    assert len(cells) == len(joined["arms"]) * len(joined["strategies"])
    for cell in cells:
        leaf = cell["unsupported_corrections"]
        assert leaf["derivation"]["op"] == "count_where_positive"
        assert leaf["denominator"] == 40


def test_check_mode_passes_on_the_committed_file() -> None:
    completed = subprocess.run([PYTHON, "scripts/collect_results.py", "--check"], cwd=ROOT,
                               capture_output=True, text=True, timeout=300)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _copy_sources(tmp_path: Path, results: dict[str, Any]) -> Path:
    root = tmp_path / "repo"
    for rel in results["sources"]:
        if rel.startswith("contract/"):
            continue
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    (root / "audit").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RESULTS, root / "audit" / "results.json")
    return root


def test_check_fails_when_a_copied_source_is_mutated(tmp_path: Path, results: dict[str, Any]) -> None:
    root = _copy_sources(tmp_path, results)
    assert collector.check(root, register_root=ROOT) == []

    summary = root / "evaluation/results/v1.0.0-summary.json"
    data = json.loads(summary.read_text(encoding="utf-8"))
    data["figures"]["distinct_denial_codes"] += 1
    summary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    drift = collector.check(root, register_root=ROOT)
    assert "reference_profile differs" in drift
    assert "sources differs" in drift


def test_check_fails_on_a_byte_only_change(tmp_path: Path, results: dict[str, Any]) -> None:
    root = _copy_sources(tmp_path, results)
    adaptive = root / "audit/adaptive-results.json"
    adaptive.write_text(adaptive.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert collector.check(root, register_root=ROOT) == ["sources differs"]


def test_collector_refuses_a_raw_count_that_disagrees_with_its_summary(
        tmp_path: Path, results: dict[str, Any]) -> None:
    root = _copy_sources(tmp_path, results)
    adaptive = root / "audit/adaptive-results.json"
    data = json.loads(adaptive.read_text(encoding="utf-8"))
    data["rows"][0]["runs"][0]["outcome"]["unsupported_correction"] = 1
    adaptive.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(collector.CollectionError, match="unsupported_corrections"):
        collector.collect(root, register_root=ROOT)
