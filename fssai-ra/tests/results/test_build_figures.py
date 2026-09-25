"""``figures/`` regenerates from committed results and plots what ``audit/results.json`` says."""
from __future__ import annotations

import html
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "figures"


def _load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


figures_script = _load_script("build_figures")


@pytest.fixture(scope="module")
def results() -> dict[str, Any]:
    return json.loads((ROOT / "audit" / "results.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def svgs() -> dict[str, str]:
    return {f["generator_stem"]: f["svg_text"] for f in figures_script.render()}


def _titles(content: str) -> list[str]:
    return [html.unescape(t) for t in re.findall(r"<title>([^<]*)</title>", content)][1:]


def test_seven_figures_in_paper_order() -> None:
    ids = [figure_id for figure_id, _, _ in figures_script.FIGURE_MAP]
    assert ids == [f"fig{n}" for n in range(1, 8)]
    assert figures_script.FIGURE_MAP[0][2] == "fig1-architecture"
    assert figures_script.FIGURE_MAP[-1][2] == "fig7-evidence"


def test_committed_figures_pass_check() -> None:
    assert figures_script.check() == []


@pytest.mark.manuscript
def test_svgs_are_the_paper_generators_bytes_and_leave_paper_figures_alone(svgs: dict[str, str]) -> None:
    for stem, content in svgs.items():
        assert (ROOT / "paper" / "figures" / f"{stem}.svg").read_text(encoding="utf-8") == content


def test_manifest_records_svg_digests_and_data_sources() -> None:
    manifest = json.loads((FIGURES / "manifest.json").read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in manifest["figures"]}
    for entry in by_id.values():
        assert figures_script._sha256((FIGURES / entry["svg"]).read_bytes()) == entry["svg_sha256"]
        for rel, digest in entry["data_sources"].items():
            assert figures_script._sha256((ROOT / rel).read_bytes()) == digest
    assert "evaluation/results/v1.0.0-architecture-comparison.json" in by_id["fig4"]["data_sources"]
    assert "evaluation/results/v1.0.0-oversight.json" in by_id["fig5"]["data_sources"]
    assert "evaluation/results/v1.0.0-domain-pack-matrix.json" in by_id["fig6"]["data_sources"]
    assert "evaluation/results/v1.0.0-mediation-thesis.json" in by_id["fig7"]["data_sources"]


def test_pngs_marked_made_are_real_pngs_and_never_placeholders() -> None:
    manifest = json.loads((FIGURES / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["figures"]:
        png = FIGURES / entry["svg"].replace(".svg", ".png")
        if entry["png"].startswith("NOT RUN"):
            assert not png.exists()
        else:
            data = png.read_bytes()
            assert data[:8] == figures_script.PNG_MAGIC
            assert figures_script._sha256(data) == entry["png_sha256"]


def test_no_png_build_in_tmp_records_not_run_and_check_catches_a_changed_svg(tmp_path: Path) -> None:
    manifest = figures_script.build(tmp_path, png=False)
    assert all(entry["png"].startswith("NOT RUN") for entry in manifest["figures"])
    assert not list(tmp_path.glob("*.png"))
    assert figures_script.check(tmp_path) == []
    target = tmp_path / "fig6-transfer.svg"
    target.write_text(target.read_text(encoding="utf-8").replace("55,440", "55,441"), encoding="utf-8")
    assert any("fig6-transfer.svg" in problem for problem in figures_script.check(tmp_path))


def test_check_catches_a_png_recorded_as_made_but_invalid(tmp_path: Path) -> None:
    figures_script.build(tmp_path, png=False)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["figures"][0]["png"] = "fig1-architecture.png"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "fig1-architecture.png").write_bytes(b"not a png")
    assert any("not a PNG" in problem for problem in figures_script.check(tmp_path))


# -- plotted numbers equal audit/results.json -------------------------------

def test_fig4_containment_bars_equal_results(svgs: dict[str, str], results: dict[str, Any]) -> None:
    plotted = [(int(c), int(t)) for c, t in
               (re.search(r": (\d+) of (\d+) contained$", title).groups()
                for title in _titles(svgs["containment"]))]
    arms = results["comparison_arms"]
    expected = [(a["attacks_succeeded"]["denominator"] - a["attacks_succeeded"]["value"],
                 a["attacks_succeeded"]["denominator"]) for a in arms["actions"]["arms"]]
    expected += [(a["contained"]["value"], a["contained"]["denominator"])
                 for a in arms["disclosure_flows"]["arms"]]
    expected += [(a["contained"]["value"], a["contained"]["denominator"])
                 for a in arms["delegation_chains"]["arms"]]
    assert plotted == expected


def test_fig5_review_capacity_bars_equal_results(svgs: dict[str, str], results: dict[str, Any]) -> None:
    titles = _titles(svgs["oversight"])
    harmful = [int(re.search(r": (\d+)$", t).group(1)) for t in titles[:4]]
    benign = [int(re.search(r": (\d+)", t).group(1)) for t in titles[4:]]
    review = results["review_capacity"]
    queue = {arm["arm"]: arm for arm in review["queue_arms"]}
    assisted = {arm["arm"]: arm for arm in review["assisted_arms"]}
    rows = [queue["no_load_control"], queue["declared_load_control"],
            assisted["assisted_dependent_lowered_floor"], assisted["assisted_independent_lowered_floor"]]
    assert harmful == [row["harmful_executed"]["value"] for row in rows]
    assert benign == [row["benign_executed"]["value"] for row in rows]


def test_fig6_transfer_equals_per_pack_results(svgs: dict[str, str], results: dict[str, Any]) -> None:
    content = svgs["domain-packs"]
    plotted = [int(n.replace(",", "")) for n in
               re.findall(r": ([\d,]+) configurations", "\n".join(_titles(content)))]
    packs = results["transfer"]["packs"]
    assert plotted == [pack["configurations"]["value"] for pack in packs]
    texts = re.findall(r">([^<]*)</text>", content)
    for pack in packs:
        assert f"{pack['scenarios']['value']}/{pack['scenarios']['denominator']}" in texts
        assert f"{pack['benign_tasks']['value']}/{pack['benign_tasks']['denominator']}" in texts
    totals = results["transfer"]["reported_totals"]
    assert f"{totals['configurations']['value']:,} configurations" in texts
    assert f"{totals['scenarios']['value']}/{totals['scenarios']['denominator']}" in texts


def test_fig7_safety_case_equals_results(svgs: dict[str, str], results: dict[str, Any]) -> None:
    titles = _titles(svgs["evidence"])
    safety = results["safety_case"]
    families = {
        (family, status): leaf["value"]
        for family, statuses in safety["threat_classes"]["by_family"].items()
        for status, leaf in statuses.items() if leaf["value"]
    }
    plotted_families = {(m.group(1), m.group(3)): int(m.group(2)) for m in
                        (re.fullmatch(r"(\w+): (\d+) (contained|bounded|residual)", t) for t in titles) if m}
    assert plotted_families == families
    plotted_falsifiers = [(m.group(1), int(m.group(2).replace(",", "")), int(m.group(3))) for m in
                          (re.fullmatch(r"(F\d): ([\d,]+) attempts, (\d+) counterexamples", t)
                           for t in titles) if m]
    assert plotted_falsifiers == [(f["id"], f["attempts"]["value"], f["counterexamples"]["value"])
                                  for f in safety["falsifiers"]["per_falsifier"]]
