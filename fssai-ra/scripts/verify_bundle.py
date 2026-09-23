"""Check a reproduction bundle's recorded outcome and artifact integrity.

This detects changes relative to report.json, not a forged report. Preserve the
report's SHA-256 through an independent archive when publishing evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def verify(directory: Path) -> list[str]:
    directory = directory.resolve()
    report = json.loads((directory / 'report.json').read_text())
    errors = []
    if report.get('passed') is not True:
        errors.append('run did not pass')
    steps = report.get('steps', [])
    if not steps or any(s.get('passed') is not True for s in steps):
        errors.append('missing or unsuccessful steps')
    artifacts = report.get('artifacts_sha256', {})
    if not artifacts:
        errors.append('no artifact hashes recorded')
    for relative, expected in artifacts.items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory):
            errors.append(f'path leaves bundle: {relative}')
        elif not path.is_file():
            errors.append(f'missing: {relative}')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f'changed: {relative}')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*')
              if p.is_file() and p != directory / 'report.json'}
    errors.extend(f'unrecorded: {name}' for name in sorted(actual - artifacts.keys()))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    try:
        errors = verify(args.bundle)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors = [f'invalid bundle: {exc}']
    for error in errors:
        print(error)
    print('FAIL' if errors else 'PASS: recorded run and artifact hashes verified')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
