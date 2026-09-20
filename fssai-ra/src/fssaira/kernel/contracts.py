"""Canonical seven-field contracts backed by executed, non-skipped failure tests."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml


class UniqueLoader(yaml.SafeLoader):
    """Do not let duplicate YAML keys replace security declarations."""


def _mapping(loader: UniqueLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 262144:
        raise ValueError('declaration exceeds size limit')
    raw = yaml.load(path.read_text(), Loader=UniqueLoader)
    if not isinstance(raw, dict):
        raise ValueError('declaration must be a mapping')
    return raw


def resolve_test(locator: str, root: Path) -> Path:
    """Resolve a pytest function without executing user-supplied Python or paths."""
    if not isinstance(locator, str) or not re.fullmatch(r'tests/[\w/]+\.py::test_\w+', locator):
        raise ValueError('failure_test must name tests/path.py::test_function')
    path, name = locator.split('::')
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError(f'missing failure test: {locator}')
    if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
               for n in ast.parse(target.read_text()).body):
        raise ValueError(f'missing failure test: {locator}')
    return target


@dataclass(frozen=True)
class CapabilityContract:
    protected_asset: str
    permitted_operation: str
    enforcement_point: str
    accountable_owner: str
    failure_test: str
    evidence_artifact: str
    failure_response: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any], root: Path) -> CapabilityContract:
        if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(cls)}:
            raise ValueError('control contract must have exactly seven canonical fields')
        if any(not isinstance(v, str) or not v.strip() for v in raw.values()):
            raise ValueError('empty field is an open governance decision')
        resolve_test(raw['failure_test'], root)
        artifact = Path(raw['evidence_artifact'])
        if artifact.is_absolute() or '..' in artifact.parts:
            raise ValueError('evidence_artifact must be a repository-relative path')
        return cls(**raw)


def load_contracts(path: Path, root: Path) -> dict[str, CapabilityContract]:
    raw = load_yaml(path)
    if set(raw) != {'capabilities'} or not isinstance(raw['capabilities'], dict) or not raw['capabilities']:
        raise ValueError('capabilities must be a nonempty mapping')
    return {name: CapabilityContract.from_dict(value, root) for name, value in raw['capabilities'].items()}


def source_digest(root: Path) -> str:
    """Bind executable evidence to the actual kernel and test sources, not a Git label."""
    h = hashlib.sha256()
    for directory in ('src', 'tests'):
        for path in sorted((root / directory).rglob('*.py')):
            h.update(path.relative_to(root).as_posix().encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def execute_contracts(contracts: dict[str, CapabilityContract], root: Path, output: Path) -> dict[str, Any]:
    """Run the bound tests. Collection, failure, skip and xfail cannot verify a claim.

    The evidence is a local CI observation, not an independently signed deployment
    attestation. The runner and its source/outputs belong to the assurance boundary.
    """
    output.mkdir(parents=True, exist_ok=True)
    locators = sorted({c.failure_test for c in contracts.values()})
    for locator in locators:
        resolve_test(locator, root)
    before = source_digest(root)
    junit = output.resolve() / 'executed-tests.xml'
    if junit.exists():
        junit.unlink()  # Never allow an old successful report to survive a failed run.
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '--strict-markers',
                          '-o', 'junit_family=xunit1', f'--junitxml={junit}', *locators],
                         cwd=root, text=True, capture_output=True, timeout=600)
    (output / 'pytest.log').write_text(run.stdout + run.stderr)
    cases = list(ET.parse(junit).getroot().iter('testcase')) if junit.exists() else []
    claims = []
    stable = before == source_digest(root)
    for name, control in contracts.items():
        path, function = control.failure_test.split('::')
        expected_class = path.removesuffix('.py').replace('/', '.')
        matches = [c for c in cases if c.attrib.get('classname') == expected_class
                   and c.attrib.get('name', '').split('[', 1)[0] == function]
        passed = bool(matches) and all(not any(c.find(tag) is not None for tag in ('failure', 'error', 'skipped')) for c in matches)
        status = 'machine_verified' if passed and run.returncode == 0 and stable else 'unverified'
        claims.append({'capability': name, **asdict(control), 'status': status,
                       'executed_cases': len(matches), 'evidence': str(junit), 'source_sha256': before})
    report = {'schema_version': 1, 'source_sha256': before, 'source_stable': stable,
              'exit_code': run.returncode, 'claims': claims,
              'passed': bool(claims) and all(c['status'] == 'machine_verified' for c in claims),
              'counts': {s: sum(c['status'] == s for c in claims)
                         for s in ('machine_verified', 'attested', 'unverified')}}
    (output / 'claims-register.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
