#!/usr/bin/env python3
"""Build ``figures/fig1..fig7`` (SVG and, where Chrome exists, PNG) with a manifest.

The rendering is not reimplemented. Every SVG is produced by the builder
functions in ``scripts/generate_paper_figures.py``, which read the committed
results in ``evaluation/results/``; this script only writes the same bytes under
stable ``figN-*`` names, records which result files each builder actually read
(by observing its ``_load`` calls), and rasterizes each SVG with the headless
Chrome that ``scripts/build_paper.py`` already discovers. ``paper/figures/`` and
its captions are left exactly as that generator writes them.

No Python raster library is assumed. If Chrome is unavailable the SVGs are still
written and the manifest records ``png: "NOT RUN: <reason>"``; a placeholder PNG
is never written.

    python scripts/build_figures.py            # write figures/ (PNG if Chrome is found)
    python scripts/build_figures.py --no-png   # SVG and manifest only
    python scripts/build_figures.py --check    # SVGs byte-identical; PNGs present and valid
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import generate_paper_figures as paper_figures  # noqa: E402

FIGURES_DIR = ROOT / "figures"
MANIFEST = "manifest.json"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
SUMMARY = "evaluation/results/v1.0.0-summary.json"

#: (figure id, generator stem, published file stem), in paper order.
FIGURE_MAP: tuple[tuple[str, str, str], ...] = (
    ("fig1", "architecture", "fig1-architecture"),
    ("fig2", "request-steps", "fig2-request-steps"),
    ("fig3", "lifecycle", "fig3-lifecycle"),
    ("fig4", "containment", "fig4-containment"),
    ("fig5", "oversight", "fig5-review-capacity"),
    ("fig6", "domain-packs", "fig6-transfer"),
    ("fig7", "evidence", "fig7-evidence"),
)
#: Fields that depend on the local Chrome build and are excluded from ``--check``.
RASTER_FIELDS = ("png", "png_sha256")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render() -> list[dict[str, Any]]:
    """Render every figure with the paper generator, recording the files it reads."""
    builders = dict(paper_figures.FIGURE_BUILDERS)
    if [stem for _, stem, _ in FIGURE_MAP] != [stem for stem, _ in paper_figures.FIGURE_BUILDERS]:
        raise SystemExit("figure map no longer matches generate_paper_figures.FIGURE_BUILDERS")
    summary = json.loads((ROOT / SUMMARY).read_text(encoding="utf-8"))["figures"]
    original_load = paper_figures._load
    rendered = []
    try:
        for figure_id, stem, name in FIGURE_MAP:
            loaded: list[str] = []

            def recording_load(result: str, _seen: list[str] = loaded) -> dict:
                _seen.append(f"evaluation/results/v1.0.0-{result}.json")
                return original_load(result)

            paper_figures._load = recording_load
            content, caption = builders[stem](summary)
            sources = [SUMMARY, *dict.fromkeys(loaded)]
            rendered.append({"id": figure_id, "generator_stem": stem, "name": name,
                             "svg_text": content, "caption": caption, "sources": sources})
    finally:
        paper_figures._load = original_load
    return rendered


def manifest_for(rendered: list[dict[str, Any]], png: dict[str, dict[str, str]]) -> dict[str, Any]:
    """The manifest document for ``rendered`` figures and their raster outcomes."""
    return {
        "generated_by": "scripts/build_figures.py",
        "renderer": "scripts/generate_paper_figures.py",
        "note": "SVGs are byte-identical to the paper generator's output; PNGs are Chrome "
                "screenshots and excluded from byte comparison",
        "figures": [
            {
                "id": figure["id"],
                "generator_stem": figure["generator_stem"],
                "svg": f"{figure['name']}.svg",
                "svg_sha256": _sha256(figure["svg_text"].encode("utf-8")),
                **png[figure["id"]],
                "caption": figure["caption"],
                "data_sources": {rel: _sha256((ROOT / rel).read_bytes()) for rel in figure["sources"]},
            }
            for figure in rendered
        ],
    }


def svg_size(content: str) -> tuple[int, int]:
    """Pixel width and height declared on the root ``<svg>`` element."""
    match = re.search(r'<svg[^>]*\swidth="([\d.]+)"[^>]*\sheight="([\d.]+)"', content)
    if not match:
        raise ValueError("SVG declares no width and height")
    return math.ceil(float(match.group(1))), math.ceil(float(match.group(2)))


def chrome_path() -> str | None:
    """The Chrome or Chromium binary ``scripts/build_paper.py`` would use."""
    from build_paper import _chrome

    return _chrome()


def rasterize(svg_path: Path, png_path: Path, chrome: str, *, scale: int = 2,
              timeout: float = 60.0) -> bool:
    """Screenshot ``svg_path`` to ``png_path`` with headless Chrome; True if a valid PNG."""
    width, height = svg_size(svg_path.read_text(encoding="utf-8"))
    png_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        # As in build_paper.print_pdf: headless Chrome on macOS can finish writing
        # and never exit, so wait for the file to stop growing, then stop it.
        process = subprocess.Popen(
            [chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
             f"--user-data-dir={profile}", f"--force-device-scale-factor={scale}",
             "--default-background-color=ffffffff", f"--window-size={width},{height}",
             f"--screenshot={png_path}", svg_path.resolve().as_uri()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + timeout
        size = -1
        try:
            while time.monotonic() < deadline and process.poll() is None:
                current = png_path.stat().st_size if png_path.exists() else -1
                if current > 0 and current == size:
                    break
                size = current
                time.sleep(0.5)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
    if png_path.exists() and png_path.read_bytes()[:8] == PNG_MAGIC:
        return True
    png_path.unlink(missing_ok=True)
    return False


def build(out_dir: Path = FIGURES_DIR, *, png: bool = True) -> dict[str, Any]:
    """Write SVGs, optional PNGs and the manifest into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered = render()
    chrome = chrome_path() if png else None
    outcomes: dict[str, dict[str, str]] = {}
    for figure in rendered:
        svg_path = out_dir / f"{figure['name']}.svg"
        svg_path.write_text(figure["svg_text"], encoding="utf-8")
        png_path = out_dir / f"{figure['name']}.png"
        if not png:
            png_path.unlink(missing_ok=True)
            outcomes[figure["id"]] = {"png": "NOT RUN: --no-png requested"}
        elif chrome is None:
            png_path.unlink(missing_ok=True)
            outcomes[figure["id"]] = {"png": "NOT RUN: no Chrome or Chromium found (set CHROME=...)"}
        elif rasterize(svg_path, png_path, chrome):
            outcomes[figure["id"]] = {"png": png_path.name,
                                      "png_sha256": _sha256(png_path.read_bytes())}
        else:
            outcomes[figure["id"]] = {"png": f"NOT RUN: Chrome at {chrome} produced no valid PNG"}
    manifest = manifest_for(rendered, outcomes)
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    not_run = [f["id"] for f in manifest["figures"] if f["png"].startswith("NOT RUN")]
    if png and not_run:
        print(f"warning: PNG not produced for {', '.join(not_run)}: "
              f"{manifest['figures'][0]['png']}", file=sys.stderr)
    return manifest


def _without_raster(manifest: dict[str, Any]) -> dict[str, Any]:
    return {**manifest, "figures": [{k: v for k, v in figure.items() if k not in RASTER_FIELDS}
                                    for figure in manifest.get("figures", [])]}


def check(out_dir: Path = FIGURES_DIR) -> list[str]:
    """Problems with the committed figures (empty when they regenerate exactly)."""
    problems: list[str] = []
    manifest_path = out_dir / MANIFEST
    if not manifest_path.exists():
        return [f"missing {manifest_path}"]
    committed = json.loads(manifest_path.read_text(encoding="utf-8"))
    rendered = render()
    for figure in rendered:
        path = out_dir / f"{figure['name']}.svg"
        if not path.exists() or path.read_text(encoding="utf-8") != figure["svg_text"]:
            problems.append(f"{path.name} does not regenerate byte-identically")
    placeholder = {f["id"]: {"png": "NOT RUN"} for f in rendered}
    if _without_raster(manifest_for(rendered, placeholder)) != _without_raster(committed):
        problems.append("manifest.json differs from a fresh render")
    for entry in committed.get("figures", []):
        status = entry.get("png", "")
        if status.startswith("NOT RUN"):
            continue
        png_path = out_dir / status
        if not png_path.exists() or png_path.read_bytes()[:8] != PNG_MAGIC:
            problems.append(f"{status} is recorded as made but is missing or not a PNG")
    expected = {f"{f['name']}.{ext}" for f in rendered for ext in ("svg", "png")} | {MANIFEST}
    problems += [f"{p.name} is not generated" for p in sorted(out_dir.iterdir()) if p.name not in expected]
    return problems


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify committed figures")
    parser.add_argument("--no-png", action="store_true", help="skip rasterization")
    args = parser.parse_args()
    if args.check:
        problems = check()
        if problems:
            print("figures/ has drifted: " + "; ".join(problems)
                  + "\nregenerate with: python scripts/build_figures.py")
            return 1
        print(f"figures/ matches a fresh render ({len(FIGURE_MAP)} figures)")
        return 0
    manifest = build(png=not args.no_png)
    print(json.dumps({f["id"]: {"svg": f["svg"], "png": f["png"]} for f in manifest["figures"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
