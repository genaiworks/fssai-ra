#!/usr/bin/env python3
"""Validate the UNU Macau extended-abstract paste fields.

Characters are counted as the browser submits them, not as the file stores
them. An HTML textarea normalises its value to CRLF on submission, so every
line break in a pasted field costs two characters rather than one. Counting
``len(body)`` understates a four-paragraph field by six characters, which is
the difference between a field that fits and a field the form silently
truncates. The stricter count is the one that decides whether the paste
survives, so it is the one that decides validity here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

LIMITS = {
    "Introduction": (200, 250, 1500),
    "Development Section 1 Methodology Core Argument and Case Context": (550, 650, 3900),
    "Development Section 2 Results Analysis and Impact": (550, 650, 3900),
    "Conclusion": (200, 250, 1500),
}


def extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            current = heading if heading in LIMITS else None
            if current:
                sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def validate(text: str) -> dict[str, object]:
    sections = extract_sections(text)
    report: dict[str, object] = {"valid": True, "sections": {}}
    for name, (minimum, maximum, char_maximum) in LIMITS.items():
        body = sections.get(name, "")
        words = len(body.split())
        chars = len(body.replace("\n", "\r\n"))
        ok = bool(body) and minimum <= words <= maximum and chars <= char_maximum
        report["sections"][name] = {
            "words": words,
            "word_minimum": minimum,
            "word_maximum": maximum,
            "characters": chars,
            "characters_stored": len(body),
            "character_maximum": char_maximum,
            "headroom": char_maximum - chars,
            "valid": ok,
        }
        report["valid"] = bool(report["valid"] and ok)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path("paper/form-ready-abstract.md"))
    parser.add_argument(
        "--full-paper", action="store_true",
        help="also bind every numeric claim in paper/trust-by-construction.md to "
             "audit/results.json via paper/metric_bindings.yaml (scripts/bind_paper_metrics.py)")
    args = parser.parse_args()
    report = validate(args.path.read_text(encoding="utf-8"))
    print(json.dumps(report, indent=2))
    if not args.full_paper:
        return 0 if report["valid"] else 1
    return full_paper_check(report["valid"])


def full_paper_check(form_valid: bool) -> int:
    """Run the full-paper metric binder after the form check; fail if either fails."""
    import sys

    scripts = Path(__file__).resolve().parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import bind_paper_metrics

    binding = bind_paper_metrics.main([])
    return 0 if form_valid and binding == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
