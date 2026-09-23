#!/usr/bin/env python3
"""Record which failure tests the shipped domain packs rely on, and that they pass.

    python scripts/failure_test_manifest.py --run profiles > contract/failure-tests.txt

``--run`` collects every ``failure_test`` named by ``profiles/*.yaml``, runs those
tests, and prints only the ones that **passed**. It exits non-zero, printing the
reason to stderr, if any referenced test fails, errors, is skipped or does not
exist. The image build runs it, so an image whose packs cite a failing test is
never built, and a deployed server (which has no tests/ directory) checks each
``failure_test`` against a list of tests that passed in the source it was built
from.

Without ``--run`` it lists every test function in a directory (existence only).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def manifest(tests_dir: Path) -> list[str]:
    entries = []
    for path in sorted(tests_dir.glob("test_*.py")):
        for name in re.findall(r"^def (test_\w+)\(", path.read_text(encoding="utf-8"), re.MULTILINE):
            entries.append(f"tests/{path.name}::{name}")
    return entries


def referenced(profiles_dir: Path) -> set[str]:
    import yaml

    found: set[str] = set()
    for path in sorted(profiles_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for contract in (raw.get("controls") or {}).values():
            if isinstance(contract, dict) and contract.get("failure_test"):
                found.add(str(contract["failure_test"]))
    return found


def run(tests: set[str]) -> tuple[set[str], dict[str, str]]:
    """Run ``tests``; return those that passed and the outcome of those that did not."""
    with tempfile.TemporaryDirectory() as work:
        report = Path(work) / "junit.xml"
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "-o", "addopts=", f"--junitxml={report}", *sorted(tests)],
                       check=False, stdout=sys.stderr, stderr=sys.stderr)
        outcomes: dict[str, str] = {}
        if report.exists():
            for case in ET.parse(report).iter("testcase"):
                test_id = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name')}"
                children = {child.tag for child in case}
                outcomes[test_id] = next((tag for tag in ("failure", "error", "skipped")
                                          if tag in children), "passed")
    passed = {t for t in tests if outcomes.get(t) == "passed"}
    problems = {t: outcomes.get(t, "not collected") for t in tests if t not in passed}
    return passed, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", type=Path, nargs="?", default=Path("tests"),
                        help="tests/ (existence mode) or profiles/ (with --run)")
    parser.add_argument("--run", action="store_true",
                        help="run the failure tests the packs in DIRECTORY reference")
    args = parser.parse_args()
    if not args.run:
        print("\n".join(manifest(args.directory)))
        return 0
    tests = referenced(args.directory)
    passed, problems = run(tests)
    if problems:
        for test, outcome in sorted(problems.items()):
            print(f"failure test {outcome}: {test}", file=sys.stderr)
        return 1
    print("\n".join(sorted(passed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
