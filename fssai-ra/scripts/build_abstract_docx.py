#!/usr/bin/env python3
"""Rebuild docs/extended-abstract.docx from paper/form-ready-abstract.md.

The Word file is the formatted copy of the text pasted into the conference form.
It drifted once, keeping an older draft's body under a corrected title, because
nothing regenerated it. This script rebuilds the body from the Markdown source
using the document's own paragraph styles, so no Word library is required, and
refuses to write a file whose fields fail the submission checker.

    python scripts/build_abstract_docx.py
"""
from __future__ import annotations

import re
import shutil
import sys
import xml.dom.minidom
from html import unescape
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_submission import LIMITS, extract_sections, validate  # noqa: E402

SOURCE = ROOT / "paper" / "form-ready-abstract.md"
TARGET = ROOT / "docs" / "extended-abstract.docx"


def _run(text: str) -> str:
    return f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _body(text: str) -> str:
    return f"<w:p><w:pPr/>{_run(text)}</w:p>"


def _label(text: str) -> str:
    return ('<w:p><w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/><w:b/><w:i w:val="0"/>'
            f'<w:color w:val="000000"/><w:sz w:val="18"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')


def _plain(text: str) -> str:
    return f"<w:p>{_run(text)}</w:p>"


def _styled(style: str, text: str) -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{_run(text)}</w:p>'


def build(source: Path = SOURCE, target: Path = TARGET) -> dict:
    markdown = source.read_text(encoding="utf-8")
    report = validate(markdown)
    if not report["valid"]:
        raise SystemExit("form-ready abstract fails the submission checker; not writing Word file")
    sections = extract_sections(markdown)
    title = markdown.splitlines()[0].removeprefix("# ").strip()

    def meta(label: str) -> str:
        match = re.search(rf"^\*\*{re.escape(label)}:\*\*\s*(.+)$", markdown, re.M)
        if not match:
            raise SystemExit(f"form-ready abstract has no {label!r} line")
        return match.group(1).strip()

    references = [
        line.strip()
        for line in markdown[markdown.index("## References"):].split("\n", 1)[1].splitlines()
        if line.strip()
    ]

    parts = [
        f'<w:p><w:pPr><w:pStyle w:val="Title"/><w:jc w:val="left"/></w:pPr>{_run(title)}</w:p>',
        '<w:p><w:pPr><w:spacing w:after="200"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Arial" '
        'w:hAnsi="Arial"/><w:b w:val="0"/><w:i/><w:color w:val="000000"/><w:sz w:val="22"/>'
        "</w:rPr><w:t>Extended abstract for the UNU Macau AI Conference 2026</w:t></w:r></w:p>",
        _label("Proposed panel"), _plain(meta("Proposed panel")),
        _label("Keywords"), _plain(meta("Keywords")),
        _label("Reference implementation"), _plain(meta("Reference implementation")),
        '<w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p>',
    ]
    for name, (low, high, _chars) in LIMITS.items():
        words = report["sections"][name]["words"]
        parts.append(_styled("Heading1", name))
        parts.append(_styled("Sectionnote",
                             f"Official limit {low} to {high} words  |  Draft count {words} words"))
        for paragraph in (p.strip() for p in sections[name].split("\n\n")):
            if paragraph:
                parts.append(_body(" ".join(paragraph.split())))
    parts.append(_styled("Heading1", "References"))
    parts.extend(_body(reference) for reference in references)

    temporary = target.with_suffix(".docx.tmp")
    with ZipFile(target) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
        head = document[:document.index("<w:body>") + len("<w:body>")]
        tail = document[document.rindex("<w:sectPr"):]
        rebuilt = head + "".join(parts) + tail
        xml.dom.minidom.parseString(rebuilt)
        total = sum(section["words"] for section in report["sections"].values())
        with ZipFile(temporary, "w", ZIP_DEFLATED) as output:
            for item in archive.infolist():
                data = archive.read(item.filename)
                if item.filename == "word/document.xml":
                    data = rebuilt.encode("utf-8")
                elif item.filename == "docProps/app.xml":
                    data = re.sub(r"<Words>\d+</Words>", f"<Words>{total}</Words>",
                                  data.decode("utf-8")).encode("utf-8")
                output.writestr(item, data)
    shutil.move(temporary, target)

    text = unescape(" ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", rebuilt)))
    for name in LIMITS:
        opening = " ".join(sections[name].split("\n\n")[0].split())[:120]
        if opening not in text:
            raise SystemExit(f"rebuilt Word file is missing the opening of {name}")
    return {"title": title, "words": {k: v["words"] for k, v in report["sections"].items()}}


if __name__ == "__main__":
    print(build())
