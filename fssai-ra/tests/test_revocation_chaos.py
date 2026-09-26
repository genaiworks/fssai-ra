"""Distributed revocation: the design is clean under chaos and every ablation is caught."""
import pytest

from fssaira.revocation_chaos import DISCIPLINES, ChaosConfig, run_campaign, run_once


def test_fenced_commit_holds_every_invariant_and_each_ablation_breaks_one():
    result = run_campaign(seeds=120)
    fenced = result['arms']['fenced']
    assert result['design_holds']
    assert fenced['stale_effects'] == fenced['duplicate_applications'] == fenced['unreconciled'] == 0
    assert fenced['refused_stale'] > 0 and fenced['applied'] > 0
    assert result['ablations_detected'] == {'check_then_act': True, 'local_clock_lease': True,
                                            'no_idempotency': True}
    assert result['arms']['check_then_act']['stale_effects'] > 0
    assert result['arms']['local_clock_lease']['stale_effects'] > 0
    assert result['arms']['no_idempotency']['duplicate_applications'] > 0
    assert result['arms']['no_idempotency']['stale_effects'] == 0


def test_runs_are_deterministic_per_seed():
    assert run_once('fenced', 7) == run_once('fenced', 7)
    assert run_once('check_then_act', 7) != run_once('check_then_act', 8)


def test_harsher_networks_still_leave_the_design_clean():
    harsh = ChaosConfig(duplicate_rate=0.5, loss_rate=0.3, partitions_per_adapter=6,
                        max_partition=20.0, max_skew=30.0, max_delay=6.0)
    result = run_campaign(seeds=60, config=harsh, disciplines=('fenced',))
    assert result['design_holds']


def test_on_a_calm_network_only_missing_idempotency_still_fails():
    calm = ChaosConfig(duplicate_rate=0, loss_rate=0, partitions_per_adapter=0, max_skew=0,
                       revoked_fraction=0)
    for discipline in DISCIPLINES:
        r = run_once(discipline, 1, calm)
        assert r['stale_effects'] == 0 and r['applied'] == r['effects']
        # A retry that fires while the first reply is in flight is ordinary
        # at-least-once delivery, not a network fault: without an idempotency
        # key it applies the effect twice even when nothing goes wrong.
        assert (r['duplicate_applications'] > 0) == (discipline == 'no_idempotency')


def test_unknown_discipline_is_refused():
    with pytest.raises(ValueError):
        run_once('optimistic', 1)
