"""Approval continuity across policy changes (master guide gap J).

A digest pins the artifact; these tests pin the rules. Before this, the only
reaction to a changed policy was drift quarantine: there was no sanctioned way
to move to new rules, and nothing bound an approval to the rules it was given
under. ``migrate_policy`` is the sanctioned path, and every approval, proposal
and held effect is pinned to its policy version."""
import dataclasses
import json

import pytest

from fssaira.tbc import AuthorityDenied, TrustRuntime
from test_tbc_composition_controls import AUTHORITIES, approved_proposal, make


def next_policy(r, **changes):
    return dataclasses.replace(r.passport, policy_version=r.passport.policy_version + 1, **changes)


def last_code(r):
    return r.decision_receipts('monitor-key', 'correction-1')[-1]['code']


def test_approval_under_old_policy_does_not_execute_under_new(tmp_path):
    r, c, _, _ = make(tmp_path)
    try:
        p, confirmation = approved_proposal(r, c)
        approval = r.approve_effect('reviewer-key', p, confirmation)
        r.migrate_policy('operator-key', next_policy(r), reason='retention table revised')
        with pytest.raises(AuthorityDenied):
            c.execute_effect(p, approval)
        assert last_code(r) == 'POLICY_VERSION_CHANGED'
        assert r.world.record('campus', 's1')['value'] != 'B'
        # Drafted under the old rules, so it is proposed again under the new ones.
        with pytest.raises(AuthorityDenied, match='POLICY_VERSION_CHANGED'):
            r.approve_effect('reviewer-key', p, confirmation)
        fresh, fresh_confirmation = approved_proposal(r, c)
        assert c.execute_effect(fresh, r.approve_effect('reviewer-key', fresh, fresh_confirmation))
        assert r.world.record('campus', 's1')['value'] == 'B'
        receipt = r.decision_receipts('monitor-key', 'correction-1')[-1]
        assert receipt['policy_version'] == r.passport.policy_version
    finally:
        r.close()


def test_migration_reroutes_held_effects_to_rereview(tmp_path):
    r, c, _, now = make(tmp_path, effect_delay_seconds=10)
    try:
        p, confirmation = approved_proposal(r, c)
        assert c.execute_effect(p, r.approve_effect('reviewer-key', p, confirmation))['state'] == 'pending'
        moved = r.migrate_policy('operator-key', next_policy(r), reason='new consent rules')
        assert len(moved['rerouted']) == 1 and moved['contracted'] == []
        assert [(q['proposal'], q['reason']) for q in r.manual_queue('operator-key')] == [
            (p, 'policy_changed_rereview')]
        now[0] += 11
        assert r.commit_due('operator-key') == []
        assert r.world.record('campus', 's1')['value'] != 'B'
        [migrated] = [json.loads(b)['data'] for (b,) in r.db.execute(
            "SELECT body FROM evidence WHERE json_extract(body,'$.kind')='tbc_policy_migrated'")]
        assert migrated['from_version'] + 1 == migrated['to_version'] == r.passport.policy_version
        assert migrated['rerouted'] == moved['rerouted'] and migrated['from_digest'] != migrated['to_digest']
    finally:
        r.close()


def test_commit_recheck_is_defence_in_depth_against_an_unsanctioned_swap(tmp_path):
    r, c, _, now = make(tmp_path, effect_delay_seconds=10)
    try:
        p, confirmation = approved_proposal(r, c)
        c.execute_effect(p, r.approve_effect('reviewer-key', p, confirmation))
        r.passport = next_policy(r)           # bypasses migrate_policy
        now[0] += 11
        [outcome] = r.commit_due('operator-key')
        assert outcome == {'scheduled': outcome['scheduled'], 'state': 'cancelled',
                           'code': 'POLICY_VERSION_CHANGED'}
        assert r.manual_queue('operator-key')[0]['reason'] == 'policy_changed_rereview'
    finally:
        r.close()


def test_migration_contracts_tasks_the_new_policy_no_longer_covers(tmp_path):
    r, c, _, _ = make(tmp_path)
    try:
        narrowed = dataclasses.replace(r.passport.scope, destinations=frozenset())
        moved = r.migrate_policy('operator-key', next_policy(r, scope=narrowed), reason='narrowed')
        assert moved['contracted'] == ['correction-1']
        with pytest.raises(AuthorityDenied):
            c.request_context('campus/s1')
    finally:
        r.close()


def test_migration_is_named_monotonic_and_survives_restart(tmp_path):
    r, _, _, now = make(tmp_path)
    try:
        new = next_policy(r)
        with pytest.raises(AuthorityDenied, match='REASON_REQUIRED'):
            r.migrate_policy('operator-key', new, reason=' ')
        for token in ('reviewer-key', 'monitor-key', 'not-a-key'):
            with pytest.raises(AuthorityDenied):
                r.migrate_policy(token, new, reason='x')
        with pytest.raises(AuthorityDenied, match='POLICY_VERSION_NOT_INCREASING'):
            r.migrate_policy('operator-key', r.passport, reason='same')
        with pytest.raises(AuthorityDenied, match='POLICY_WORKLOAD_MISMATCH'):
            r.migrate_policy('operator-key', dataclasses.replace(new, workload='other'), reason='x')
        old = r.passport
        r.migrate_policy('operator-key', new, reason='annual review')
        assert r.passport.policy_version == old.policy_version + 1
    finally:
        r.close()
    path = tmp_path / 'tbc.db'
    reopened = TrustRuntime(path, new, authorities=AUTHORITIES, clock=lambda: now[0])
    reopened.close()
    with pytest.raises(AuthorityDenied, match='PASSPORT_DRIFT'):
        TrustRuntime(path, old, authorities=AUTHORITIES, clock=lambda: now[0])
