"""Reproduce public onboarding workflows and retain commands, logs and evidence.

Run with the installed development environment, from any working directory.
No package installation, model-provider call, or external service is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def reference_env():
    # Reproduction is explicitly of the default local reference configuration.
    # Never inherit a caller's live databases, provider endpoints, or credentials.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('FSSAI_') and k not in {'PYTHONPATH', 'PYTEST_ADDOPTS'}}
    env['PYTHONPATH'] = str(APP / 'src')
    env['NO_COLOR'] = '1'
    env['FSSAI_MODEL'] = 'deterministic'
    env['FSSAI_MODEL_FALLBACK'] = 'deny'
    return env


def steps(output: Path):
    p = 'profiles/student_support.yaml'
    cli = ['-m', 'fssaira.cli']
    specs = [
        ('joined', ['scripts/joined_demo.py', '--output', str(output / 'joined')], 0),
        ('component-demo', ['scripts/demo.py', '--fast'], 0),
        ('sdk', ['scripts/tbc_demo.py', '--output', str(output / 'sdk')], 0),
        ('developer', ['scripts/developer_security_demo.py'], 0),
        ('inventory', ['scripts/check_sdk_inventory.py'], 0),
        ('api', ['scripts/api_walkthrough.py', '--self-test', '--output', str(output / 'api.json')], 0),
    ]
    for name, args in [
        ('profiles', ['profiles', '--verify']),
        ('profile', ['validate-profile', p]),
        ('contract', ['validate-contract', 'contract']),
        ('verify', ['verify', p]),
        ('evaluate', ['evaluate', p]),
        ('memory', ['conformance', '--backend', 'memory']),
        ('sql', ['conformance', '--backend', 'sql']),
        ('disclosure', ['disclosure', 'profiles/healthcare_record_access.yaml']),
        ('oversight', ['oversight', p, '--sweep']),
        ('assisted-review', ['assisted-review', p]),
        ('delegation', ['delegation']),
        ('coverage', ['coverage']),
        ('challenge', ['challenge']),
        ('threats', ['threats']),
        ('thesis', ['thesis']),
        ('doctor', ['doctor']),
    ]:
        if name not in {'profile', 'contract'}:
            args += ['--output', str(output / f'{name}.json')]
        specs.append((name, cli + args, 1 if name == 'doctor' else 0))
    domain = str(output / 'my-domain')
    specs += [
        ('scaffold', cli + ['init', domain, '--domain-id', 'my-domain', '--title', 'My governed workflow'], 0),
        ('scaffold-profile', cli + ['validate-profile', domain + '/profile.yaml'], 0),
        ('scaffold-contract', cli + ['validate-contract', domain], 0),
        ('scaffold-verify', cli + ['verify', domain + '/profile.yaml'], 0),
        ('scaffold-evaluate', cli + ['evaluate', domain + '/profile.yaml'], 0),
        ('scaffold-tests', ['-m', 'pytest', domain, '--junitxml=' + str(output / 'scaffold-tests.xml')], 1),
    ]
    return specs


def run_step(name, args, expected, output, timeout):
    command = [sys.executable, *args]
    log = output / f'{name}.log'
    start = time.monotonic()
    reason = None
    with log.open('w', encoding='utf-8') as stream:
        try:
            result = subprocess.run(command, cwd=APP, env=reference_env(),
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = None
            reason = f'exceeded {timeout} seconds'
    passed = code == expected
    if passed and name == 'doctor':
        state = json.loads((output / 'doctor.json').read_text())
        passed = state.get('readiness', {}).get('ready_for_pilot') is False
    if passed and name == 'scaffold-tests':
        from xml.etree import ElementTree as ET
        cases = ET.parse(output / 'scaffold-tests.xml').findall('.//testcase')
        failures = [case for case in cases if case.find('failure') is not None]
        passed = (len(failures) == 1 and not any(case.find('error') is not None for case in cases)
                  and failures[0].get('name') == 'test_replace_me_with_the_attack_that_matters_in_your_domain')
    return {'name': name, 'command': command, 'cwd': str(APP), 'exit_code': code,
            'expected_exit_code': expected, 'passed': passed,
            'seconds': round(time.monotonic() - start, 3), 'log': log.name, 'error': reason}


def provenance():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=APP, text=True).strip()
    inputs = {}
    for directory in ('src', 'profiles', 'contract', 'scripts'):
        for path in sorted((APP / directory).rglob('*')):
            if path.is_file() and path.suffix in {'.py', '.yaml', '.json'} and '__pycache__' not in path.parts:
                inputs[path.relative_to(APP).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'commit': git('rev-parse', 'HEAD'), 'git_status': git('status', '--short'),
            'python': sys.version, 'os': platform.platform(), 'sqlite': sqlite3.sqlite_version,
            'dependencies': dict(sorted((d.metadata['Name'], d.version)
                                       for d in importlib.metadata.distributions() if d.metadata['Name'])),
            'input_sha256': inputs,
            'configuration': 'Local reference with deterministic model; inherited FSSAI_* variables removed from child processes'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new bundle directory; default: APP/work/reproduction-<unique-id>')
    parser.add_argument('--timeout', type=int, default=180, help='maximum seconds per step (default 180)')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = (args.output or APP / 'work' / f'reproduction-{stamp}-{uuid.uuid4().hex[:8]}').resolve()
    if output.exists():
        parser.error('output already exists; choose a new directory to preserve prior evidence')
    output.mkdir(parents=True)
    report = {'scope': 'Synthetic local reference workflows; not live services or private manuscripts',
              'started_utc': stamp, 'provenance': provenance(), 'steps': [], 'passed': False}
    print(f'Evidence bundle: {output}', flush=True)
    try:
        for name, command, expected in steps(output):
            print(f'Running {name} (expected exit {expected}) ...', flush=True)
            result = run_step(name, command, expected, output, args.timeout)
            report['steps'].append(result)
            (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            if not result['passed']:
                print(f'FAILED: {name}; inspect {output / result["log"]}', flush=True)
                return 1
        report['passed'] = True
        print('PASS: all public workflows reproduced. doctor and the scaffold placeholder fail as expected.')
        print(f'Open {output / "joined/viewer.html"} and {output / "report.json"}')
        return 0
    finally:
        report['artifacts_sha256'] = {
            p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'report.json'
        }
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
