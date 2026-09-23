"""Regression checks for the actual new-reader failure modes."""
from pathlib import Path

from scripts.check_public_docs import anchors
from scripts.reproduce import reference_env, run_step


def test_documentation_anchors_handle_numbered_and_duplicate_headings(tmp_path):
    page = tmp_path / 'guide.md'
    page.write_text('# Guide\n## 2. First run\n## Repeat\n## Repeat\n```\n## Not a heading\n```\n')
    assert anchors(page) == {'guide', '2-first-run', 'repeat', 'repeat-1'}


def test_reproduction_does_not_inherit_live_services_or_pytest_overrides(monkeypatch):
    monkeypatch.setenv('FSSAI_DATABASE_URL', 'postgresql://private.example/db')
    monkeypatch.setenv('FSSAI_MODEL', 'openai-compatible')
    monkeypatch.setenv('PYTEST_ADDOPTS', '--ignore=tests')
    env = reference_env()
    assert 'FSSAI_DATABASE_URL' not in env
    assert env['FSSAI_MODEL'] == 'deterministic'
    assert 'PYTEST_ADDOPTS' not in env


def test_reproduction_records_an_unexpected_failure(tmp_path):
    result = run_step('failure', ['-c', 'raise SystemExit(3)'], 0, tmp_path, 10)
    assert result['passed'] is False
    assert result['exit_code'] == 3
    assert (tmp_path / result['log']).is_file()


def test_doctor_failure_is_not_accepted_without_readiness_evidence(tmp_path):
    (tmp_path / 'doctor.json').write_text('{"readiness": {"ready_for_pilot": true}}')
    result = run_step('doctor', ['-c', 'raise SystemExit(1)'], 1, tmp_path, 10)
    assert result['passed'] is False


def test_private_manuscript_check_remains_explicit():
    root = Path(__file__).resolve().parents[1]
    makefile = (root / 'Makefile').read_text()
    assert '--include-manuscripts -m manuscript' in makefile
    public = makefile.split('all:')[1].split('.PHONY: security-review')[0]
    assert 'check_paper_revision.py' not in public
    assert 'check_sdk_inventory.py' in public
