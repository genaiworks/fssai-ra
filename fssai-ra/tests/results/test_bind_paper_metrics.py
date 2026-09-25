"""The full-paper binder catches unbound numbers and values that no longer match."""
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
PYTHON = sys.executable


def _load_script(name: str) -> Any:
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


binder = _load_script("bind_paper_metrics")

PAPER = """# Title

**Submission:** draft 2026.

## 1. Introduction

We ran 104,997 bounded attempts and found zero counterexamples.
The register reads 41, 3, 0 and eighteen of twenty-eight were prose.

| Strategy | A | B |
|---|---|---|
| Static | 0/40 | 40/40 |

See https://example.org/2024/42 for more.

## References

[1] Someone (1999). A paper. 12(3), 45-67.
"""

RESULTS = {
    "attempts": {"value": 104997, "denominator": None, "unit": "attempts", "source": "x#/a"},
    "counterexamples": {"value": 0, "denominator": None, "unit": "c", "source": "x#/c"},
    "mv": {"value": 41, "denominator": 44, "unit": "r", "source": "x#/m"},
    "at": {"value": 3, "denominator": 44, "unit": "r", "source": "x#/t"},
    "un": {"value": 0, "denominator": 44, "unit": "r", "source": "x#/u"},
    "prose": {"value": 18, "denominator": 28, "unit": "r", "source": "x#/p"},
    "a": {"value": 0, "denominator": 40, "unit": "e", "source": "x#/sa"},
    "b": {"value": 40, "denominator": 40, "unit": "e", "source": "x#/sb"},
}

BINDINGS = [
    {"quote": "**Submission:** draft 2026.", "kind": "specification", "justification": "venue year"},
    {"quote": "## 1. Introduction", "kind": "specification", "justification": "section number"},
    {"quote": "We ran 104,997 bounded attempts and found zero counterexamples", "kind": "result",
     "values": [{"pointer": "/attempts"}, {"pointer": "/counterexamples"}]},
    {"quote": "reads 41, 3, 0", "kind": "result",
     "values": [{"pointer": "/mv"}, {"pointer": "/at"}, {"pointer": "/un"}]},
    {"quote": "eighteen of twenty-eight", "kind": "result", "values": [{"pointer": "/prose", "as": "fraction"}]},
    {"quote": "| Static | 0/40 | 40/40 |", "kind": "result",
     "values": [{"pointer": "/a", "as": "fraction"}, {"pointer": "/b", "as": "fraction"}]},
]


def test_extraction_skips_references_urls_and_glued_identifiers() -> None:
    text = PAPER + ""
    tokens = [t.text for t in binder.extract_tokens(text)]
    assert "2024" not in tokens and "42" not in tokens and "1999" not in tokens
    assert tokens.count("104,997") == 1
    assert {"zero", "eighteen", "twenty-eight", "0", "40"} <= set(tokens)
    glued = [t.text for t in binder.extract_tokens("Ed25519 llama3.2:1b Fig. 4a `5c587c3` v 1.0.0 x")]
    assert glued == ["1.0.0"]
    assert [t.text for t in binder.extract_tokens("one reviewer, two mediators")] == ["two"]


def test_a_fully_bound_paper_passes() -> None:
    report = binder.bind(PAPER, BINDINGS, RESULTS)
    assert report.ok, binder.render_text(report)
    assert report.result_bindings == 4


def test_planted_unbound_number_is_reported() -> None:
    paper = PAPER.replace("were prose.", "were prose.\nWe also saw 777 widgets.")
    report = binder.bind(paper, BINDINGS, RESULTS)
    assert [u["token"] for u in report.unbound] == ["777"]
    assert report.unbound[0]["line"] == 9


def test_extra_number_inside_a_result_quote_is_not_silently_covered() -> None:
    paper = PAPER.replace("found zero counterexamples", "found zero counterexamples")
    bindings = [dict(b) for b in BINDINGS]
    bindings[3] = {"quote": "reads 41, 3, 0", "kind": "result", "values": [{"pointer": "/mv"}]}
    report = binder.bind(paper, bindings, RESULTS)
    assert sorted(u["token"] for u in report.unbound) == ["0", "3"]


def test_planted_mismatch_in_results_is_reported() -> None:
    results = json.loads(json.dumps(RESULTS))
    results["attempts"]["value"] = 104998
    results["b"]["denominator"] = 41
    report = binder.bind(PAPER, BINDINGS, results)
    problems = [(m["pointer"], m["problem"]) for m in report.mismatches]
    assert any(p == "/attempts" for p, _ in problems)
    assert any(p == "/b" and "40/41" in problem for p, problem in problems)


def test_thousands_separator_is_required() -> None:
    paper = PAPER.replace("104,997", "104997")
    bindings = [dict(b) for b in BINDINGS]
    bindings[2] = {**BINDINGS[2], "quote": "We ran 104997 bounded attempts and found zero counterexamples"}
    report = binder.bind(paper, bindings, RESULTS)
    assert [m["pointer"] for m in report.mismatches] == ["/attempts"]


def test_quote_edited_out_of_the_paper_is_a_mismatch_and_its_number_unbound() -> None:
    paper = PAPER.replace("reads 41, 3, 0", "reads 42, 3, 0")
    report = binder.bind(paper, BINDINGS, RESULTS)
    assert any(m["problem"] == "quote not found in the paper" for m in report.mismatches)
    assert {"42", "3", "0"} <= {u["token"] for u in report.unbound}


def test_structural_validation_requires_values_or_justification(tmp_path: Path) -> None:
    path = tmp_path / "b.yaml"
    path.write_text("bindings:\n  - quote: 'x 1'\n    kind: specification\n", encoding="utf-8")
    with pytest.raises(ValueError, match="justification"):
        binder.load_bindings(path)
    path.write_text("bindings:\n  - quote: 'x 1'\n    kind: result\n", encoding="utf-8")
    with pytest.raises(ValueError, match="values"):
        binder.load_bindings(path)


def test_parameter_evidence_must_contain_the_declared_text(tmp_path: Path) -> None:
    (tmp_path / "cfg.json").write_text(json.dumps({"learning": "alpha=.4 gamma=.9"}), encoding="utf-8")
    paper = "# T\n\n## 1. X\n\nlearning rate 0.4\n"
    binding = {"quote": "learning rate 0.4", "kind": "parameter", "justification": "declared",
               "evidence": {"source": "cfg.json#/learning", "contains": "alpha=.4"}}
    spec = {"quote": "## 1. X", "kind": "specification", "justification": "section"}
    assert binder.bind(paper, [spec, binding], {}, tmp_path).ok
    binding["evidence"]["contains"] = "alpha=.5"
    assert not binder.bind(paper, [spec, binding], {}, tmp_path).ok


# -- the real paper, in tmp copies ------------------------------------------

def _copy_real(tmp_path: Path) -> tuple[Path, Path, Path]:
    paper = tmp_path / "paper.md"
    bindings = tmp_path / "bindings.yaml"
    results = tmp_path / "results.json"
    shutil.copyfile(ROOT / "paper" / "trust-by-construction.md", paper)
    shutil.copyfile(ROOT / "paper" / "metric_bindings.yaml", bindings)
    shutil.copyfile(ROOT / "audit" / "results.json", results)
    return paper, bindings, results


@pytest.mark.manuscript
def test_real_bindings_quote_the_paper_and_resolve(tmp_path: Path) -> None:
    report = binder.run()
    assert not [m for m in report.mismatches if m["problem"] == "quote not found in the paper"]
    assert not [m for m in report.mismatches if "does not resolve" in m["problem"]]
    assert report.result_bindings > 40


@pytest.mark.manuscript
def test_real_paper_planted_unbound_and_mismatch_are_caught(tmp_path: Path) -> None:
    paper, bindings, results = _copy_real(tmp_path)
    baseline = binder.run(paper, bindings, results)
    text = paper.read_text(encoding="utf-8").replace(
        "## 8. Education as the dissemination mechanism",
        "## 8. Education as the dissemination mechanism\n\nA planted 9,876 widgets claim.")
    paper.write_text(text, encoding="utf-8")
    data = json.loads(results.read_text(encoding="utf-8"))
    data["reference_profile"]["scenarios"]["value"] = 29
    results.write_text(json.dumps(data), encoding="utf-8")
    report = binder.run(paper, bindings, results)
    new_unbound = {u["token"] for u in report.unbound} - {u["token"] for u in baseline.unbound}
    assert "9,876" in new_unbound
    assert any(m.get("pointer") == "/reference_profile/scenarios" for m in report.mismatches)
    completed = subprocess.run([PYTHON, "scripts/bind_paper_metrics.py", "--paper", str(paper),
                                "--bindings", str(bindings), "--results", str(results)],
                               cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 1
    assert "9,876" in completed.stdout


@pytest.mark.manuscript
def test_check_submission_default_is_unchanged_and_full_paper_runs_the_binder() -> None:
    default = subprocess.run([PYTHON, "scripts/check_submission.py"], cwd=ROOT,
                             capture_output=True, text=True, timeout=120)
    report = json.loads(default.stdout)
    assert set(report) == {"valid", "sections"}
    assert "paper metric binding" not in default.stdout
    full = subprocess.run([PYTHON, "scripts/check_submission.py", "--full-paper"], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    assert "paper metric binding" in full.stdout
    expected = 0 if (default.returncode == 0 and binder.run().ok) else 1
    assert full.returncode == expected
