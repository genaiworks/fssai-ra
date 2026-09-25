"""Visibility: any observer can answer five questions about any agent from mediated state."""
import json

import pytest

from fssaira.joined_workflow import canonical
from fssaira.tbc import AuthorityDenied, Guardian
from fssaira.tbc.client import SDKClient
from test_tbc_sdk import declarations, rig  # noqa: F401  (fixture)


def act(r, c, token):
    """One allowed read, one out-of-scope read, one forbidden operation."""
    context = c.request_context('campus/s1')['context']
    c.invoke_tool('summarize', context)
    with pytest.raises(AuthorityDenied):
        c.request_context('campus/s2')
    assert not r.dispatch(token, canonical({'op': 'shell', 'code': 'cat state.db'}))['ok']


def test_the_five_questions_are_answered_for_an_agent(rig):  # noqa: F811
    r, c, root, _ = rig
    act(r, c, root['token'])
    dossier = r.agent_dossier('operator-key', root['agent'])

    assert dossier['who']['agent'] == root['agent'] and dossier['who']['active'] is True
    assert 'request_context' in dossier['may']['effective_scope']['operations']
    assert {'request_context', 'invoke_tool'} <= {d['operation'] for d in dossier['did']}
    assert sum(dossier['stopped']['by_code'].values()) >= 2
    assert dossier['could_leak']['declared'] is False
    assert dossier['integrity']['receipt_chain_verified'] is True


def test_the_dossier_holds_no_protected_content(rig):  # noqa: F811
    r, c, root, _ = rig
    act(r, c, root['token'])
    text = json.dumps(r.agent_dossier('operator-key', root['agent']))
    record = json.dumps(r.world.record('campus', 's1'))
    assert r.world.record('campus', 's1')['value'] not in {None, ''}
    assert '"supported"' not in text and record not in text


def test_a_child_is_answered_with_its_lineage_and_its_own_history(rig):  # noqa: F811
    r, c, root, _ = rig
    child = c.request('spawn_agent', scope=declarations()[2].to_dict(), model='offline-scripted',
                      zone='local', ttl=100)
    child_client = SDKClient(r.dispatch, child['token'])
    child_client.request_capability()
    child_client.request_context('campus/s1')
    dossier = r.agent_dossier('operator-key', child['agent'])
    assert dossier['who']['parent'] == root['agent']
    assert dossier['who']['lineage'] == [root['agent']]
    assert [d['operation'] for d in dossier['did']].count('request_context') == 1


def test_a_revoked_agent_stays_visible_and_says_why(rig):  # noqa: F811
    r, c, root, _ = rig
    act(r, c, root['token'])
    Guardian(r).revoke(root['agent'])
    dossier = r.agent_dossier('operator-key', root['agent'])
    assert dossier['who']['active'] is False
    assert dossier['who']['inactive_because'] == 'AGENT_REVOKED_OR_EXPIRED'
    assert dossier['did']  # history survives revocation


def test_only_operator_or_monitor_authority_may_ask(rig):  # noqa: F811
    r, _c, root, _ = rig
    for token in ('recipient-key', root['token'], 'nobody'):
        with pytest.raises(AuthorityDenied):
            r.agent_dossier(token, root['agent'])


def test_a_tampered_receipt_chain_is_refused_rather_than_reported(rig):  # noqa: F811
    r, c, root, _ = rig
    act(r, c, root['token'])
    seq, body = r.db.execute("SELECT seq, body FROM tbc_receipts WHERE body LIKE '%DENIED%' "
                             "ORDER BY seq LIMIT 1").fetchone()
    r.db.execute('UPDATE tbc_receipts SET body=? WHERE seq=?', (body.replace('DENIED', 'ALLOWED'), seq))
    with pytest.raises(AuthorityDenied, match='INTEGRITY_FAILURE'):
        r.agent_dossier('operator-key', root['agent'])


def test_a_declared_channel_capacity_is_reported_and_validated(rig):  # noqa: F811
    r, _c, root, _ = rig
    assert r.agent_dossier('operator-key', root['agent'], channel_capacity_bits=0.5)['could_leak'] == {
        'declared': True, 'bits_per_release': 0.5,
        'note': 'declared capacity of every choice left open to the agent'}
    for bad in (-1, float('nan'), True, 'lots'):
        with pytest.raises(AuthorityDenied):
            r.agent_dossier('operator-key', root['agent'], channel_capacity_bits=bad)


def test_an_unknown_agent_is_refused(rig):  # noqa: F811
    r, _c, _root, _ = rig
    with pytest.raises(AuthorityDenied, match='UNKNOWN_AGENT'):
        r.agent_dossier('operator-key', 'no-such-agent')
