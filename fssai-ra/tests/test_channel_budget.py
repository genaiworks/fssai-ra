"""Collusion through allowed choices: every release is charged its declared bits against a task budget."""
import pytest

from fssaira.tbc import AuthorityDenied, TrustRuntime
from fssaira.tbc.client import SDKClient
from test_tbc_sdk import AUTHORITIES, declarations


def rig(tmp_path, **channel):
    passport, task, identity = declarations()
    runtime = TrustRuntime(tmp_path / 'tbc.db', passport, authorities=AUTHORITIES, clock=lambda: 1000,
                           **channel)
    root = runtime.create_task('operator-key', task, identity_scope=identity,
                               model='offline-scripted', zone='local')
    client = SDKClient(runtime.dispatch, root['token'])
    client.request_capability()
    return runtime, client, root


def summary(c):
    return c.invoke_tool('summarize', c.request_context('campus/s1')['context'])['artifact']


def test_releases_past_the_channel_budget_go_to_a_person(tmp_path):
    r, c, root = rig(tmp_path, channel_bits_per_release=3, channel_budget_bits=6)
    for _ in range(2):
        assert r.authorize_release('reviewer-key', summary(c), 'recipient', declassify=True)
    with pytest.raises(AuthorityDenied, match='CHANNEL_BUDGET_EXHAUSTED'):
        r.authorize_release('reviewer-key', summary(c), 'recipient', declassify=True)
    assert [row[0] for row in r.db.execute('SELECT reason FROM tbc_manual_queue')] == [
        'channel_budget_exhausted']
    leak = r.agent_dossier('operator-key', root['agent'])['could_leak']
    assert (leak['declared'], leak['task_bits_spent'], leak['task_budget_bits']) == (True, 6, 6)
    r.close()


def test_a_refused_release_does_not_consume_budget(tmp_path):
    r, c, _root = rig(tmp_path, channel_bits_per_release=3, channel_budget_bits=3)
    with pytest.raises(AuthorityDenied, match='DESTINATION_DENIED'):
        r.authorize_release('reviewer-key', summary(c), 'nowhere', declassify=True)
    assert r.authorize_release('reviewer-key', summary(c), 'recipient', declassify=True)
    r.close()


def test_a_channel_policy_must_be_complete_and_valid(tmp_path):
    for bad in ({'channel_bits_per_release': 3}, {'channel_budget_bits': 6},
                {'channel_bits_per_release': -1, 'channel_budget_bits': 6},
                {'channel_bits_per_release': float('nan'), 'channel_budget_bits': 6}):
        with pytest.raises(AuthorityDenied):
            rig(tmp_path / str(len(str(bad))), **bad)


def test_without_a_channel_policy_releases_are_unmetered(tmp_path):
    r, c, root = rig(tmp_path)
    for _ in range(5):
        assert r.authorize_release('reviewer-key', summary(c), 'recipient', declassify=True)
    assert r.agent_dossier('operator-key', root['agent'])['could_leak']['declared'] is False
    r.close()
