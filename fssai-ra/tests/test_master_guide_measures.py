"""Staffing, trusted-base size, SBOM, the refusal registry and the channel SLO."""
import json
from pathlib import Path

import pytest

from fssaira.channel_slo import check_slo, rate_bound
from fssaira.covert_channels import EgressPolicy, canonical_policy, sealed_policy
from fssaira.oversight_staffing import ReviewDemand, erlang_c, staffing
from fssaira.refusal_registry import render, scan
from fssaira.trusted_base import build_measurement, measure_size, sbom, sloc

ROOT = Path(__file__).resolve().parents[1]


def test_erlang_c_matches_known_values():
    assert erlang_c(1, 0.5) == pytest.approx(0.5)
    assert erlang_c(2, 1.0) == pytest.approx(1 / 3)
    assert erlang_c(3, 3.0) == 1.0 and erlang_c(3, 0) == 0.0


def test_staffing_honours_the_floor_and_reports_understaffing():
    demand = ReviewDemand(arrivals_per_hour=40, mean_review_seconds=60, floor_seconds=180,
                          target_wait_seconds=900)
    report = staffing(demand, on_shift=1)
    assert report['floor_binds'] and report['effective_review_seconds'] == 180
    assert report['reviewers_needed'] >= 3
    assert report['at_needed']['utilisation'] <= 0.85
    assert report['at_needed']['service_level'] >= 0.8
    assert report['verdict'] == 'UNDERSTAFFED_DEFER_NOT_LOWER_FLOOR'
    assert report['deferred_per_hour'] > 0
    assert staffing(demand, on_shift=report['reviewers_needed'])['verdict'] == 'STAFFED'


def test_low_risk_lane_loads_reviewers_only_through_its_audit_sample():
    base = {'arrivals_per_hour': 10, 'mean_review_seconds': 120, 'floor_seconds': 45}
    sampled = staffing(ReviewDemand(**base, low_risk_per_hour=200, audit_rate=0.05))
    assert sampled['reviewed_items_per_hour'] == 20
    with pytest.raises(ValueError):
        ReviewDemand(**base, audit_rate=1.5)


def test_sloc_ignores_comments_blank_lines_and_docstrings():
    source = '"""Module doc."""\n\n# comment\ndef f():\n    """Doc\n    more."""\n    return 1\n'
    assert sloc(source) == 2


def test_trusted_base_is_measured_and_a_minority_of_the_package():
    size = measure_size()
    assert set(size['components']) == {'kernel', 'decision plane', 'evidence plane',
                                       'key custody', 'containment'}
    assert 0 < size['trusted_sloc'] < size['package_sloc']
    assert size['trusted_fraction'] < 0.5
    assert size['native_code_in_package'] == []
    first, second = build_measurement(), build_measurement()
    assert first['measurement'] == second['measurement'] and len(first['measurement']) == 64


def test_sbom_is_cyclonedx_and_deterministic():
    one, two = sbom(), sbom()
    assert one == two and one['bomFormat'] == 'CycloneDX' and one['specVersion'] == '1.5'
    assert all(c['purl'].startswith('pkg:pypi/') for c in one['components'])
    assert 'pyyaml' in {c['name'] for c in one['components']}


def test_refusal_registry_is_current_with_the_code():
    published = json.loads((ROOT / 'docs/refusal_registry.json').read_text())
    assert render(scan()) == (ROOT / 'docs/refusal_registry.json').read_text(), (
        'regenerate: python -c "from fssaira.refusal_registry import scan, render; '
        'open(\'docs/refusal_registry.json\',\'w\').write(render(scan()))"')
    for code in ('POLICY_VERSION_CHANGED', 'STALE_PROPOSAL', 'MERKLE_FORK', 'FS_WRONG_PERIOD',
                 'TIME_SOURCES_DISAGREE', 'FERPA_CONSENT_REQUIRED', 'MINOR_DUAL_APPROVAL_REQUIRED',
                 'WITNESS_FORK', 'CHANNEL_BUDGET_EXHAUSTED'):
        assert code in published['codes'], code


def test_channel_slo_is_a_rate_and_fails_when_unbounded():
    dests, paths = ('registrar', 'archive'), ('/out',)
    canonical = canonical_policy(dests, paths, contract_destination='registrar',
                                 contract_path='/out')
    bound = rate_bound(canonical, concurrent_tasks=10)
    assert bound['bounded'] and bound['bits_per_minute'] > 0
    assert check_slo(canonical, slo_bits_per_minute=10.0, concurrent_tasks=10)['met']
    assert not check_slo(canonical, slo_bits_per_minute=0.01, concurrent_tasks=10)['met']
    sealed = sealed_policy(dests, paths, contract_destination='registrar', contract_path='/out')
    assert rate_bound(sealed)['bits_per_minute'] <= bound['bits_per_minute']
    open_policy = EgressPolicy(approved_destinations=dests, approved_paths=paths)
    assert check_slo(open_policy, slo_bits_per_minute=1e9)['code'] == 'CHANNEL_SLO_EXCEEDED'
