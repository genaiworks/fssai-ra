#!/usr/bin/env python3
"""Build the camera-ready proceedings paper from its Markdown source.

``paper/trust-by-construction.md`` is the single source of the full paper's
prose, guarded by the alignment tests. This script typesets that prose with the
generated figures from ``paper/figures/`` into a self-contained HTML file, then
prints it to PDF with a headless Chrome or Chromium if one is installed.

A figure is placed after the first paragraph that cites it ("Fig. 2b" places
Figure 2), so moving a citation moves the figure, and a figure nothing cites is
an error rather than an ornament. The Markdown subset is deliberately small:
headings, paragraphs, numbered lists, pipe tables with a "**Table N.**" caption
paragraph above them, bold, italic, code spans, and bare URLs.

    python scripts/build_paper.py            # HTML and, if Chrome is found, PDF
    python scripts/build_paper.py --html     # HTML only
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_paper_figures import FIGURE_BUILDERS, FIGURES  # noqa: E402

SOURCE = ROOT / "paper" / "trust-by-construction.md"
CITATION = ROOT.parent / "CITATION.cff"
HTML_OUT = ROOT / "paper" / "trust-by-construction.html"
PDF_OUT = ROOT / "paper" / "trust-by-construction.pdf"
FIG_CITE = re.compile(r"Figs?\.\s*(\d+)")
META_KEYS = ("Submission", "Proposed panel", "Keywords", "Reference implementation")

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
)

CSS = """
@page { size: A4; margin: 21mm 20mm 22mm 20mm;
  @bottom-center { content: counter(page); font: 8pt Helvetica, Arial, sans-serif; color: #555; }
}
:root { color-scheme: light; }
html { background: #ffffff; }
body { margin: 0 auto; max-width: 170mm; padding-block: 12mm; padding-inline: 16px;
  background: #ffffff; color: #111111;
  font: 10.3pt/1.42 "Times New Roman", Times, "Nimbus Roman", "Liberation Serif", serif;
  hyphens: auto; -webkit-hyphens: auto; }
@media print { body { padding: 0; max-width: none; } }
h1 { font: 700 17pt/1.2 "Helvetica Neue", Helvetica, Arial, sans-serif;
  margin: 0 0 6pt; letter-spacing: -.01em; }
.byline { font-size: 11pt; margin: 0 0 2pt; }
.meta { font-size: 8.8pt; color: #444; margin: 0 0 1.5pt; text-align: left; }
.meta a { color: inherit; }
.abstract { margin: 12pt 0 10pt; padding: 8pt 11pt; border-block: 0.8pt solid #999; }
.abstract h2 { margin: 0 0 3pt; font-size: 9.5pt; text-transform: uppercase;
  letter-spacing: .06em; }
.abstract p { margin: 0 0 4pt; font-size: 9.7pt; }
h2 { font: 700 11.6pt/1.25 "Helvetica Neue", Helvetica, Arial, sans-serif;
  margin: 14pt 0 4pt; break-after: avoid; }
h3 { font: 700 10.2pt/1.25 "Helvetica Neue", Helvetica, Arial, sans-serif;
  margin: 10pt 0 3pt; break-after: avoid; }
p { margin: 0 0 6pt; text-align: justify; orphans: 3; widows: 3; }
ol { margin: 0 0 6pt; padding-left: 18pt; }
li { margin-bottom: 2.5pt; text-align: justify; }
code { font: 8.6pt "SFMono-Regular", Menlo, Consolas, monospace; }
a { color: #184f95; text-decoration: none; overflow-wrap: anywhere; }
figure { margin: 10pt 0 11pt; break-inside: avoid; page-break-inside: avoid; }
figure svg { display: block; width: 100%; height: auto; max-width: 100%; }
figcaption, .table-caption { font-size: 8.8pt; line-height: 1.35; text-align: justify; }
figcaption { margin-top: 5pt; }
figcaption b, .table-caption b { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; }
.table-caption { margin: 10pt 0 4pt; break-after: avoid; }
.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; margin: 0 0 11pt; font-size: 8.4pt;
  line-height: 1.3; break-inside: auto; page-break-inside: auto; }
th { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 8pt;
  text-align: left; vertical-align: bottom; border-bottom: 0.9pt solid #555;
  padding: 3pt 4pt; }
tr { break-inside: avoid; page-break-inside: avoid; }
td { vertical-align: top; padding: 3pt 4pt; border-bottom: 0.5pt solid #d6d5cf; }
td:first-child { font-weight: 700; }
.references p { font-size: 8.6pt; line-height: 1.3; margin: 0 0 2.5pt;
  padding-left: 16pt; text-indent: -16pt; text-align: left; }
.note { font-size: 8.8pt; color: #444; }
"""


def inline(markdown: str) -> str:
    """Bold, italic, code spans, and bare URLs; everything else is escaped."""
    spans: list[str] = []

    def keep(fragment: str) -> str:
        spans.append(fragment)
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{html.escape(m.group(1))}</code>"),
                  markdown)
    text = re.sub(r"https?://[^\s)|]+[^\s).,;|]",
                  lambda m: keep(f'<a href="{html.escape(m.group(0))}">'
                                 f"{html.escape(m.group(0))}</a>"), text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def _author() -> str:
    source = CITATION.read_text(encoding="utf-8") if CITATION.exists() else ""
    block = source[source.find("preferred-citation:"):] or source
    family = re.search(r"family-names:\s*(.+)", block)
    given = re.search(r"given-names:\s*(.+)", block)
    if not (family and given):
        raise SystemExit("CITATION.cff names no author; the paper will not invent one")
    return f"{given.group(1).strip()} {family.group(1).strip()}"


def _figure(number: int, stem: str, captions: dict[str, str]) -> str:
    content = (FIGURES / f"{stem}.svg").read_text(encoding="utf-8")
    return (f'<figure id="fig{number}"><div class="scroll">{content}</div>'
            f"<figcaption><b>Fig. {number}.</b> {html.escape(captions[stem])}"
            "</figcaption></figure>")


def _table(block: str) -> str:
    rows = [[cell.strip() for cell in row.strip().strip("|").split("|")]
            for row in block.splitlines() if row.strip()]
    if len(rows) < 2 or not re.fullmatch(r"[\s:|-]+", block.splitlines()[1]):
        raise SystemExit(f"malformed table:\n{block}")
    head = "".join(f"<th>{inline(cell)}</th>" for cell in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>"
                   for row in rows[2:])
    return (f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def render(markdown: str) -> str:
    captions = json.loads((FIGURES / "captions.json").read_text(encoding="utf-8"))
    stems = [stem for stem, _ in FIGURE_BUILDERS]
    title = markdown.splitlines()[0].removeprefix("# ").strip()
    meta = {m.group(1): m.group(2).strip()
            for m in re.finditer(r"^\*\*([^*:]+):\*\*\s*(.+)$", markdown, re.M)}

    out = [
        f"<title>{html.escape(title)}</title>",
        f"<style>{CSS}</style>",
        f"<h1>{html.escape(title)}</h1>",
        f'<p class="byline">{html.escape(_author())}</p>',
    ]
    out += [f'<p class="meta"><b>{html.escape(key)}:</b> {inline(meta[key])}</p>'
            for key in META_KEYS if key in meta]

    body = markdown[markdown.index("\n## "):]
    placed: set[int] = set()
    section = ""
    open_section = False
    for block in (b.strip("\n") for b in body.split("\n\n")):
        if not block.strip():
            continue
        if block.startswith("## ") or block.startswith("### "):
            level = 2 if block.startswith("## ") else 3
            heading = block.splitlines()[0][level + 1:].strip()
            if level == 2:
                if open_section:
                    out.append("</section>")
                section = heading
                css = {"Abstract": "abstract", "References": "references"}.get(heading)
                out.append(f'<section class="{css}">' if css else "<section>")
                open_section = True
            out.append(f"<h{level}>{inline(heading)}</h{level}>")
            block = "\n".join(block.splitlines()[1:]).strip()
            if not block:
                continue
        if block.lstrip().startswith("|"):
            out.append(_table(block))
        elif re.match(r"^\d+\.\s", block):
            items = re.split(r"\n(?=\d+\.\s)", block)
            out.append("<ol>" + "".join(
                "<li>" + inline(" ".join(re.sub(r"^\d+\.\s+", "", item).split())) + "</li>"
                for item in items) + "</ol>")
        elif block.startswith("**Table"):
            out.append(f'<p class="table-caption">{inline(" ".join(block.split()))}</p>')
        elif block.startswith("*") and block.endswith("*") and not block.startswith("**"):
            out.append(f'<p class="note">{inline(" ".join(block.split()))}</p>')
        else:
            out.append(f"<p>{inline(' '.join(block.split()))}</p>")
        if section in ("Abstract", "References"):
            continue
        for cited in dict.fromkeys(int(n) for n in FIG_CITE.findall(block)):
            if cited in placed:
                continue
            if not 1 <= cited <= len(stems):
                raise SystemExit(f"the paper cites Fig. {cited}, which does not exist")
            # Keep figures in numeric order even if a later one is cited first.
            for number in range(1, cited + 1):
                if number not in placed:
                    out.append(_figure(number, stems[number - 1], captions))
                    placed.add(number)
    if open_section:
        out.append("</section>")
    unplaced = sorted(set(range(1, len(stems) + 1)) - placed)
    if unplaced:
        raise SystemExit(f"figure(s) {unplaced} are generated but never cited in the paper")
    return "\n".join(out) + "\n"


def _chrome() -> str | None:
    override = os.environ.get("CHROME")
    for candidate in ((override,) if override else ()) + CHROME_CANDIDATES:
        path = candidate if os.path.isabs(candidate) else shutil.which(candidate)
        if path and os.path.exists(path):
            return path
    return None


def print_pdf(source: Path, target: Path) -> bool:
    chrome = _chrome()
    if not chrome:
        print("no Chrome or Chromium found (set CHROME=...); wrote HTML only")
        return False
    target.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        # Headless Chrome on macOS can write the PDF and then never exit, so wait
        # for the file to stop growing rather than for the process.
        process = subprocess.Popen(
            [chrome, "--headless=new", "--disable-gpu", "--no-first-run",
             f"--user-data-dir={profile}", "--no-pdf-header-footer",
             f"--print-to-pdf={target}", source.resolve().as_uri()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 120
        size = -1
        try:
            while time.monotonic() < deadline and process.poll() is None:
                current = target.stat().st_size if target.exists() else -1
                if current > 0 and current == size:
                    break
                size = current
                time.sleep(1.0)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
    return target.exists() and target.stat().st_size > 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--html", action="store_true", help="write HTML only")
    args = parser.parse_args()
    HTML_OUT.write_text(render(SOURCE.read_text(encoding="utf-8")), encoding="utf-8")
    report = {"html": str(HTML_OUT.relative_to(ROOT))}
    if not args.html and print_pdf(HTML_OUT, PDF_OUT):
        report["pdf"] = str(PDF_OUT.relative_to(ROOT))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
