#!/usr/bin/env python3
"""List every test function as ``tests/<file>.py::<name>``, one per line.

The image build runs this over the source tree it was built from and ships the
result as ``contract/failure-tests.txt``. A deployed server has no ``tests/``
directory, so the kernel floor checks each pack's ``failure_test`` against this
manifest instead. The tests themselves run in CI, not in the container.

    python scripts/failure_test_manifest.py tests > contract/failure-tests.txt
"""
import re
import sys
from pathlib import Path


def manifest(tests_dir: Path) -> list[str]:
    entries = []
    for path in sorted(tests_dir.glob("test_*.py")):
        for name in re.findall(r"^def (test_\w+)\(", path.read_text(encoding="utf-8"), re.MULTILINE):
            entries.append(f"tests/{path.name}::{name}")
    return entries


if __name__ == "__main__":
    print("\n".join(manifest(Path(sys.argv[1] if len(sys.argv) > 1 else "tests"))))
