"""Delayed commitment: an approved effect waits out a window in which authority may change its mind."""
import pytest

from fssaira.tbc import AuthorityDenied, Guardian, TrustRuntime
from fssaira.tbc.client import SDKClient
from test_tbc_sdk import AUTHORITIES, declarations

DELAY = 60


@pytest.fixture
def held(tmp_path):
    passport, task, identity = declarations()
    now = [1000]
    runtime = TrustRuntime(tmp_path / 'tbc.db', passport, authorities=AUTHORITIES,
                           clock=lambda: now[0], effect_delay_seconds=DELAY)
    root = runtime.create_task('operator-key', task, identity_scope=identity,
                               model='offline-scripted', zone='local')
    client = SDKClient(runtime.dispatch, root['token'])
    client.request_capability()
    yield runtime, client, root, now
    runtime.close()


def approved_effect(r, c):
    context = c.request_context('campus/s1')['context']
    proposal = c.propose_effect(context, 'correct_transcript', 'B', 'recipient')['proposal']
    approval = r.approve_effect('reviewer-key', proposal, r.confirm_effect('source-key', proposal))
    return proposal, approval


def value(r):
    return r.world.record('campus', 's1')['value']


def test_an_approved_effect_is_held_and_the_record_is_untouched(held):
    r, c, _, _ = held
    before = value(r)
    proposal, approval = approved_effect(r, c)
    scheduled = c.execute_effect(proposal, approval)
    assert scheduled['state'] == 'pending' and scheduled['not_before'] == 1000 + DELAY
    assert value(r) == before
    assert c.execute_effect(proposal, approval)['replayed'] is True  # idempotent, one hold


def test_without_objection_it_commits_once_after_the_window(held):
    r, c, _, now = held
    proposal, approval = approved_effect(r, c)
    scheduled = c.execute_effect(proposal, approval)['scheduled']
    assert r.commit_due('operator-key') == []  # window still open
    now[0] += DELAY
    assert r.commit_due('operator-key') == [{'scheduled': scheduled, 'state': 'committed'}]
    assert value(r) == 'B'
    assert r.commit_due('operator-key') == []  # never twice
    assert r.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 1


def test_an_objection_inside_the_window_cancels_the_effect(held):
    r, c, _, now = held
    before = value(r)
    proposal, approval = approved_effect(r, c)
    scheduled = c.execute_effect(proposal, approval)['scheduled']
    assert r.object_effect('source-key', scheduled, reason='student appealed')['state'] == 'cancelled'
    now[0] += DELAY
    assert r.commit_due('operator-key') == []
    assert value(r) == before


def test_an_objection_after_the_window_is_refused(held):
    r, c, _, now = held
    proposal, approval = approved_effect(r, c)
    scheduled = c.execute_effect(proposal, approval)['scheduled']
    now[0] += DELAY
    with pytest.raises(AuthorityDenied, match='OBJECTION_WINDOW_CLOSED'):
        r.object_effect('reviewer-key', scheduled, reason='too late')


def test_revoking_the_task_during_the_window_cancels_at_commit(held):
    r, c, _, now = held
    before = value(r)
    proposal, approval = approved_effect(r, c)
    scheduled = c.execute_effect(proposal, approval)['scheduled']
    r.revoke_task('operator-key', 'correction-1', reason='mandate withdrawn')
    now[0] += DELAY
    [outcome] = r.commit_due('operator-key')
    assert outcome['state'] == 'cancelled' and outcome['scheduled'] == scheduled
    assert value(r) == before


def test_revoking_the_agent_during_the_window_cancels_at_commit(held):
    r, c, root, now = held
    proposal, approval = approved_effect(r, c)
    c.execute_effect(proposal, approval)
    Guardian(r).revoke(root['agent'])
    now[0] += DELAY
    [outcome] = r.commit_due('operator-key')
    assert (outcome['state'], outcome['code']) == ('cancelled', 'AGENT_REVOKED_OR_EXPIRED')
    receipts = r.decision_receipts('operator-key', 'correction-1')
    assert receipts[-1]['outcome'] == 'DENIED' and receipts[-1]['code'] == 'AGENT_REVOKED_OR_EXPIRED'


def test_only_named_authorities_may_object_or_commit(held):
    r, c, root, _ = held
    proposal, approval = approved_effect(r, c)
    scheduled = c.execute_effect(proposal, approval)['scheduled']
    for token in ('recipient-key', root['token']):
        with pytest.raises(AuthorityDenied):
            r.object_effect(token, scheduled, reason='not mine to stop')
    with pytest.raises(AuthorityDenied):
        r.commit_due('reviewer-key')
    with pytest.raises(AuthorityDenied, match='REASON_REQUIRED'):
        r.object_effect('source-key', scheduled, reason=' ')
