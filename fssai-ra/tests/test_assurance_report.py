"""The one-command assurance report: passes, reproduces, and fails when any part fails."""
from fssaira import assurance_report
from fssaira.assurance_report import build_report


def test_report_passes_and_its_digest_is_reproducible():
    first = build_report(seeds=20, qualification_seeds=4)
    second = build_report(seeds=20, qualification_seeds=4)
    assert first['verdict'] == 'PASS', first['deterministic']
    assert first['digest'] == second['digest'] and len(first['digest']) == 64
    sections = first['deterministic']['sections']
    assert set(sections) == {'revocation', 'adapter_qualification', 'evidence_federation',
                             'trusted_base', 'registry', 'specification_profile',
                             'framework_catalogue'}
    assert sections['evidence_federation']['rewrite']['code'] == 'WITNESS_QUORUM_NOT_MET'
    assert sections['revocation']['arms']['fenced']['stale_effects'] == 0
    assert 'seconds' in first['host'] and 'seconds' not in str(sections)


def test_any_failing_section_fails_the_report(monkeypatch):
    monkeypatch.setattr(assurance_report, '_registry', lambda: {'passed': False, 'codes': 0})
    report = build_report(seeds=5, qualification_seeds=2)
    assert report['verdict'] == 'FAIL'
