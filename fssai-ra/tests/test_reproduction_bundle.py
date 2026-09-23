"""An evidence bundle must not remain green after its artifacts are changed."""
import hashlib
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify_bundle.py'
spec = importlib.util.spec_from_file_location('verify_bundle', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def bundle(tmp_path):
    (tmp_path / 'evidence.json').write_text('{}')
    report = {'passed': True, 'steps': [{'passed': True}],
              'artifacts_sha256': {'evidence.json': hashlib.sha256(b'{}').hexdigest()}}
    (tmp_path / 'report.json').write_text(json.dumps(report))
    return report


def test_changed_or_missing_evidence_fails(tmp_path):
    bundle(tmp_path)
    assert module.verify(tmp_path) == []
    (tmp_path / 'evidence.json').write_text('{"forged": true}')
    assert module.verify(tmp_path) == ['changed: evidence.json']
    (tmp_path / 'evidence.json').unlink()
    assert module.verify(tmp_path) == ['missing: evidence.json']


def test_failed_run_and_unrecorded_evidence_fail(tmp_path):
    report = bundle(tmp_path)
    report['passed'] = False
    (tmp_path / 'report.json').write_text(json.dumps(report))
    (tmp_path / 'extra.json').write_text('{}')
    assert module.verify(tmp_path) == ['run did not pass', 'unrecorded: extra.json']


def test_paths_outside_bundle_are_rejected(tmp_path):
    report = bundle(tmp_path)
    report['artifacts_sha256']['../outside'] = 'irrelevant'
    (tmp_path / 'report.json').write_text(json.dumps(report))
    assert module.verify(tmp_path) == ['path leaves bundle: ../outside']


def test_custom_suite_cannot_pass_by_skipping_every_case(tmp_path):
    """Pytest returns zero for all-skipped suites; that is not verification."""
    import sys

    scripts = SCRIPT.parent
    sys.path.insert(0, str(scripts))
    try:
        from reproduce import run_step

        suite = tmp_path / 'test_empty_assurance.py'
        suite.write_text('import pytest\ndef test_claim():\n    pytest.skip("not measured")\n')
        result = run_step('domain-tests', ['-m', 'pytest', str(suite),
                          '--junitxml=' + str(tmp_path / 'domain-tests.xml')], 0, tmp_path, 30)
        assert result['exit_code'] == 0
        assert result['passed'] is False
        assert result['error'] == 'no test cases actually executed'
    finally:
        sys.path.remove(str(scripts))


def test_nested_reports_are_hashed(tmp_path):
    import sys

    scripts = SCRIPT.parent
    sys.path.insert(0, str(scripts))
    try:
        from reproduce import artifact_hashes

        (tmp_path / 'sdk').mkdir()
        (tmp_path / 'sdk/report.json').write_text('{}')
        (tmp_path / 'report.json').write_text('{}')
        assert artifact_hashes(tmp_path) == {
            'sdk/report.json': hashlib.sha256(b'{}').hexdigest(),
        }
    finally:
        sys.path.remove(str(scripts))
