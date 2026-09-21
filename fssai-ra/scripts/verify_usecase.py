"""Evaluate a custom domain and retain an evidence bundle; all checks must pass.

Run from the application directory. Tests must exercise the user's actual domain
and effects. Generic reference scenarios alone do not establish domain safety.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reproduce import artifact_hashes, provenance, run_step


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--contract', required=True, type=Path)
    parser.add_argument('--tests', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    for name in ('profile', 'contract', 'tests'):
        path = getattr(args, name).resolve()
        if not path.exists():
            parser.error(f'{name} does not exist: {path}')
        setattr(args, name, path)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    output = args.output.resolve()
    if output.exists():
        parser.error('output exists; choose a fresh evidence directory')
    output.mkdir(parents=True)
    cli = ['-m', 'fssaira.cli']
    p = str(args.profile)
    specs = [
        ('profile', cli + ['validate-profile', p]),
        ('contract', cli + ['validate-contract', str(args.contract)]),
        ('verify', cli + ['verify', p, '--output', str(output / 'verify.json')]),
        ('evaluate', cli + ['evaluate', p, '--output', str(output / 'evaluate.json')]),
        ('memory', cli + ['conformance', '--profile', p, '--backend', 'memory', '--output', str(output / 'memory.json')]),
        ('sql', cli + ['conformance', '--profile', p, '--backend', 'sql', '--output', str(output / 'sql.json')]),
        ('domain-tests', ['-m', 'pytest', str(args.tests), '--junitxml=' + str(output / 'domain-tests.xml')]),
    ]
    inputs = {}
    for path in (args.profile, args.contract, args.tests):
        for item in ([path] if path.is_file() else sorted(path.rglob('*'))):
            if item.is_file() and item.suffix in {'.py', '.yaml', '.yml', '.json'}:
                inputs[str(item)] = hashlib.sha256(item.read_bytes()).hexdigest()
    report = {'scope': 'Custom profile, generic reference checks and user-supplied tests; not deployment certification',
              'provenance': provenance(), 'custom_inputs_sha256': inputs, 'steps': [], 'passed': False}
    try:
        for name, command in specs:
            print(f'Running {name} ...', flush=True)
            result = run_step(name, command, 0, output, args.timeout)
            report['steps'].append(result)
            if not result['passed']:
                print(f'FAIL: inspect {output / result["log"]}')
                return 1
        report['passed'] = True
        print(f'PASS: {output / "report.json"}')
        return 0
    finally:
        report['artifacts_sha256'] = artifact_hashes(output)
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
