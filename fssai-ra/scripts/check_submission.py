#!/usr/bin/env python3
"""Validate the UNU Macau extended-abstract paste fields."""

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
        chars = len(body)
        ok = bool(body) and minimum <= words <= maximum and chars <= char_maximum
        report["sections"][name] = {
            "words": words,
            "word_minimum": minimum,
            "word_maximum": maximum,
            "characters": chars,
            "character_maximum": char_maximum,
            "valid": ok,
        }
        report["valid"] = bool(report["valid"] and ok)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path("paper/form-ready-abstract.md"))
    args = parser.parse_args()
    report = validate(args.path.read_text(encoding="utf-8"))
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
