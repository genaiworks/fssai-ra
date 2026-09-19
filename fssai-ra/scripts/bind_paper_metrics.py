#!/usr/bin/env python3
"""Bind every number in the full paper to a result, a specification or a citation.

``paper/metric_bindings.yaml`` quotes substrings of ``paper/trust-by-construction.md``
exactly and says what each number inside them is:

* ``kind: result`` -- ``values`` name JSON pointers into ``audit/results.json``.
  Each bound value must appear, correctly formatted, inside the quote. Only
  tokens a value consumes are covered, so an extra number slipped into a result
  sentence is still reported.
* ``kind: parameter`` -- a declared setting (learning rate, episode cap). It
  points at the source that sets it when one exists, either through ``values``
  or through ``evidence: {source: "<relpath>#<pointer>", contains: "<text>"}``.
* ``kind: historical`` -- a past observation that no run regenerates (an earlier
  test count, a defect found and fixed). It must name the committed record that
  states it: ``evidence: {source: "<relpath>", contains: "<text>"}``; the record
  must contain the text, or the binding is a mismatch.
* ``kind: specification`` / ``kind: citation`` -- not a result (section numbers,
  "seven fields", reference years); covers every token in the quote and needs a
  ``justification``.

Extraction covers the whole paper except the References section and URLs,
including tables and captions. A number-bearing token is a digit sequence (with
thousands separators, decimals or a dotted version) not glued to letters, or a
cardinal word from "zero" upward excluding "one", which in this prose is almost
always an article-like determiner. Ordinals ("fifth") are not extracted.

The binder exits non-zero listing (a) unbound numeric tokens and (b) mismatches:
a value absent or misformatted in its quote, a pointer that does not resolve, or
a quote no longer present in the paper. Passing is not semantic review.

    python scripts/bind_paper_metrics.py [--paper P] [--bindings B] [--results R] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from collect_results import resolve_pointer, split_source  # noqa: E402

PAPER = ROOT / "paper" / "trust-by-construction.md"
BINDINGS = ROOT / "paper" / "metric_bindings.yaml"
RESULTS = ROOT / "audit" / "results.json"
KINDS = ("result", "parameter", "specification", "citation", "historical")

_UNITS = {"zero": 0, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9}
_TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
          "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_ONES_FOR_COMPOUND = {"one": 1, **{k: v for k, v in _UNITS.items() if v}}
WORD_NUMBERS: dict[str, int] = {**_UNITS, **_TEENS, **_TENS, "hundred": 100, "thousand": 1000}
for _tens, _base in _TENS.items():
    for _unit, _add in _ONES_FOR_COMPOUND.items():
        WORD_NUMBERS[f"{_tens}-{_unit}"] = _base + _add

DIGIT_TOKEN = re.compile(
    r"(?<![\w.])(?:\d+(?:\.\d+){2,}|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?!\.?\w)")
WORD_TOKEN = re.compile(
    r"\b(?:" + "|".join(sorted((re.escape(w) for w in WORD_NUMBERS), key=len, reverse=True))
    + r")\b", re.IGNORECASE)
URL = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class Token:
    """One number-bearing token in the paper."""

    start: int
    end: int
    text: str
    line: int

    @property
    def is_word(self) -> bool:
        """True for a spelled-out cardinal."""
        return not self.text[0].isdigit()

    @property
    def number(self) -> float | None:
        """Numeric value, or ``None`` for a dotted version string."""
        if self.is_word:
            return float(WORD_NUMBERS[self.text.lower()])
        if self.text.count(".") > 1:
            return None
        return float(self.text.replace(",", ""))


@dataclass
class Report:
    """Outcome of binding a paper to its results."""

    tokens: int = 0
    bindings: int = 0
    result_bindings: int = 0
    bound_values: int = 0
    unbound: list[dict[str, Any]] = field(default_factory=list)
    mismatches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing is unbound and nothing mismatches."""
        return not self.unbound and not self.mismatches

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form."""
        return {"ok": self.ok, "tokens": self.tokens, "bindings": self.bindings,
                "result_bindings": self.result_bindings, "bound_values": self.bound_values,
                "unbound": self.unbound, "mismatches": self.mismatches}


def body_end(text: str) -> int:
    """Offset where the References section starts (or the end of the text)."""
    match = re.search(r"^## References\s*$", text, re.MULTILINE)
    return match.start() if match else len(text)


def extract_tokens(text: str) -> list[Token]:
    """Every number-bearing token outside References and URLs, in order."""
    end = body_end(text)
    masked = URL.sub(lambda m: " " * len(m.group(0)), text[:end])
    found = [(m.start(), m.end()) for m in DIGIT_TOKEN.finditer(masked)]
    found += [(m.start(), m.end()) for m in WORD_TOKEN.finditer(masked)]
    return [Token(s, e, text[s:e], text.count("\n", 0, s) + 1) for s, e in sorted(found)]


def _line_text(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    stop = text.find("\n", offset)
    return text[start: stop if stop != -1 else len(text)]


def _context(text: str, token: Token, width: int = 70) -> str:
    line = _line_text(text, token.start)
    column = token.start - (text.rfind("\n", 0, token.start) + 1)
    left = max(0, column - width)
    right = min(len(line), column + len(token.text) + width)
    return ("..." if left else "") + line[left:right] + ("..." if right < len(line) else "")


def _formatted_ok(token: Token, value: Any) -> bool:
    """Whether ``token`` states ``value`` in an acceptable format."""
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, str):
        return token.text == value
    number = token.number
    if number is None or not isinstance(value, (int, float)) or number != float(value):
        return False
    if token.is_word:
        return True
    if float(value).is_integer() and abs(value) >= 1000:
        return token.text == f"{int(value):,}"
    return True


def _resolve_value(results: dict[str, Any], entry: dict[str, Any]) -> tuple[Any, Any]:
    target = resolve_pointer(results, entry["pointer"])
    if isinstance(target, dict) and "value" in target:
        return target["value"], target.get("denominator")
    return target, None


def load_bindings(path: Path) -> list[dict[str, Any]]:
    """Load and structurally validate the bindings file."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    bindings = document.get("bindings", []) if isinstance(document, dict) else []
    for index, binding in enumerate(bindings):
        where = f"binding {index} ({binding.get('quote')!r})"
        if not isinstance(binding.get("quote"), str) or not binding["quote"]:
            raise ValueError(f"{where}: quote must be a non-empty string")
        if binding.get("kind") not in KINDS:
            raise ValueError(f"{where}: kind must be one of {KINDS}")
        if binding["kind"] == "result" and not binding.get("values"):
            raise ValueError(f"{where}: a result binding needs values")
        if binding["kind"] != "result" and not binding.get("justification"):
            raise ValueError(f"{where}: a {binding['kind']} binding needs a justification")
        if binding["kind"] == "historical":
            evidence = binding.get("evidence") or {}
            if not evidence.get("source") or not evidence.get("contains"):
                raise ValueError(f"{where}: a historical binding needs evidence.source and evidence.contains")
    return bindings


def bind(paper_text: str, bindings: list[dict[str, Any]], results: dict[str, Any],
         root: Path = ROOT) -> Report:
    """Bind ``paper_text`` to ``results`` through ``bindings``."""
    tokens = extract_tokens(paper_text)
    by_start = {token.start: token for token in tokens}
    covered: set[int] = set()
    end = body_end(paper_text)
    report = Report(tokens=len(tokens), bindings=len(bindings))

    for binding in bindings:
        quote, kind = binding["quote"], binding["kind"]
        occurrences = [m.start() for m in re.finditer(re.escape(quote), paper_text[:end])]
        if not occurrences:
            report.mismatches.append({"quote": quote, "problem": "quote not found in the paper"})
            continue
        first_line = paper_text.count("\n", 0, occurrences[0]) + 1
        spans = [[t for t in tokens if at <= t.start and t.end <= at + len(quote)] for at in occurrences]
        relative = spans[0]
        consumed: set[int] = set()
        if kind == "result":
            report.result_bindings += 1

        for entry in binding.get("values", []) or []:
            try:
                value, denominator = _resolve_value(results, entry)
            except KeyError as exc:
                report.mismatches.append({"line": first_line, "quote": quote,
                                          "pointer": entry.get("pointer"),
                                          "problem": f"pointer does not resolve: {exc}"})
                continue
            mode = entry.get("as", "value")
            wanted = [value, denominator] if mode == "fraction" else [
                denominator if mode == "denominator" else value]
            if mode == "fraction":
                indices = _find_fraction(quote, relative, consumed, occurrences[0], value, denominator)
            else:
                indices = _find_single(relative, consumed, wanted[0])
            if indices is None:
                shown = f"{value}/{denominator}" if mode == "fraction" else repr(wanted[0])
                report.mismatches.append({"line": first_line, "quote": quote,
                                          "pointer": entry["pointer"], "as": mode,
                                          "problem": f"bound value {shown} does not appear correctly "
                                                     "formatted in the quote"})
                continue
            consumed.update(indices)
            report.bound_values += 1

        evidence = binding.get("evidence")
        if evidence:
            try:
                if "#" in evidence["source"] or evidence["source"].endswith(".json"):
                    rel, json_pointer = split_source(evidence["source"])
                    target = resolve_pointer(json.loads((root / rel).read_text(encoding="utf-8")), json_pointer)
                else:  # a committed text record (a log, a test, an audit note), matched by substring
                    target = (root / evidence["source"]).read_text(encoding="utf-8")
            except (OSError, KeyError, ValueError) as exc:
                report.mismatches.append({"line": first_line, "quote": quote,
                                          "problem": f"evidence does not resolve: {exc}"})
            else:
                if "contains" in evidence and evidence["contains"] not in str(target):
                    report.mismatches.append({"line": first_line, "quote": quote,
                                              "problem": f"evidence {evidence['source']} does not "
                                                         f"contain {evidence['contains']!r}"})

        for span in spans:
            for index, token in enumerate(span):
                if kind != "result" or index in consumed:
                    covered.add(token.start)

    for start, token in sorted(by_start.items()):
        if start not in covered:
            report.unbound.append({"line": token.line, "token": token.text,
                                   "context": _context(paper_text, token)})
    return report


def _find_single(relative: list[Token], consumed: set[int], value: Any) -> list[int] | None:
    for index, token in enumerate(relative):
        if index not in consumed and _formatted_ok(token, value):
            return [index]
    return None


def _find_fraction(quote: str, relative: list[Token], consumed: set[int], offset: int,
                   value: Any, denominator: Any) -> list[int] | None:
    for index in range(len(relative) - 1):
        first, second = relative[index], relative[index + 1]
        if index in consumed or index + 1 in consumed:
            continue
        between = quote[first.end - offset: second.start - offset]
        if between in ("/", " of ") and _formatted_ok(first, value) and _formatted_ok(second, denominator):
            return [index, index + 1]
    return None


def render_text(report: Report) -> str:
    """Human-readable report."""
    lines = [f"paper metric binding: {report.tokens} numeric tokens, {report.bindings} bindings "
             f"({report.result_bindings} result bindings, {report.bound_values} bound values)"]
    if report.unbound:
        lines.append(f"\n(a) UNBOUND numeric claims: {len(report.unbound)}")
        lines += [f"  line {u['line']}: {u['token']!r} in: {u['context']}" for u in report.unbound]
    if report.mismatches:
        lines.append(f"\n(b) MISMATCHES: {len(report.mismatches)}")
        lines += [f"  line {m.get('line', '?')}: {m['problem']} [{m.get('pointer', '')}] quote: {m['quote']!r}"
                  for m in report.mismatches]
    lines.append("\nOK" if report.ok else "\nFAILED")
    return "\n".join(lines)


def run(paper: Path = PAPER, bindings: Path = BINDINGS, results: Path = RESULTS,
        root: Path = ROOT) -> Report:
    """Bind the files at the given paths."""
    return bind(paper.read_text(encoding="utf-8"), load_bindings(bindings),
                json.loads(results.read_text(encoding="utf-8")), root)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--paper", type=Path, default=PAPER)
    parser.add_argument("--bindings", type=Path, default=BINDINGS)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    report = run(args.paper, args.bindings, args.results, args.root)
    print(json.dumps(report.to_dict(), indent=2) if args.json else render_text(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
