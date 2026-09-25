"""Swarm agreement is counted by independent failure classes, from receipts, and grants nothing."""
import json

import pytest

from fssaira.tbc import AuthorityDenied
from fssaira.tbc.client import SDKClient
from test_tbc_sdk import declarations, rig  # noqa: F401  (fixture)


def swarm_summaries(r, c, workers):
    """Several workers read the same record and produce the same summary."""
    digests = set()
    for _ in range(workers):
        child = c.request('spawn_agent', scope=declarations()[2].to_dict(),
                          model='offline-scripted', zone='local', ttl=100)
        worker = SDKClient(r.dispatch, child['token'])
        worker.request_capability()
        context = worker.request_context('campus/s1')['context']
        worker.invoke_tool('summarize', context)
    for row in r.db.execute("SELECT body FROM tbc_receipts"):
        body = json.loads(row[0])
        if body.get('operation') == 'invoke_tool' and body.get('outcome') == 'ALLOWED':
            digests.add(body['artifact_digest'])
    return digests


def test_three_agreeing_workers_on_one_model_and_one_source_are_one_confirmation(rig):  # noqa: F811
    r, c, root, _ = rig
    digests = swarm_summaries(r, c, 3)
    assert len(digests) == 1
    result = r.independent_agreement('reviewer-key', 'correction-1', digests.pop(), required=2)
    assert (result['producers'], result['independent'], result['meets_required']) == (3, 1, False)
    assert all({'same model', 'shared source'} <= set(c['correlated_by'])
               for c in result['correlations'])
    assert result['authority'].startswith('none')


def register(r, agent_id, *, model, sources, parent=None):
    """A registered agent whose provenance differs; its receipt goes through the real chain."""
    task = r._task('correction-1')
    with r.transaction():
        r.db.execute("INSERT INTO tbc_agents(id,token,task,parent,scope,model,zone,expires,revoked,"
                     "labels,sources) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     (agent_id, f'token-{agent_id}', 'correction-1', parent, '{}', model, 'local',
                      10**9, 0, '[]', json.dumps(sources)))
        r._record_receipt(task, {'id': agent_id}, {'op': 'invoke_tool'},
                          {'digest': 'claim-digest'}, 'ALLOWED')


def test_only_agents_that_cannot_fail_together_count_separately(rig):  # noqa: F811
    r, _c, _root, _ = rig
    register(r, 'a', model='model-x', sources=['campus/s1'])
    register(r, 'b', model='model-y', sources=['campus/s2'])
    register(r, 'c', model='model-z', sources=['campus/s3'])
    register(r, 'd', model='model-x', sources=['campus/s4'])        # same model as a
    register(r, 'e', model='model-w', sources=['campus/s5'], parent='c')  # delegated from c
    result = r.independent_agreement('operator-key', 'correction-1', 'claim-digest', required=3)
    assert result['producers'] == 5
    assert result['groups'] == [['a', 'd'], ['b'], ['c', 'e']]
    assert (result['independent'], result['meets_required']) == (3, True)


def test_agreement_is_read_from_receipts_not_from_what_agents_claim(rig):  # noqa: F811
    r, _c, _root, _ = rig
    register(r, 'a', model='model-x', sources=['campus/s1'])
    task = r._task('correction-1')
    with r.transaction():  # a refused attempt to produce the same artifact is not agreement
        r._record_receipt(task, {'id': 'b'}, {'op': 'invoke_tool'}, {'digest': 'claim-digest'},
                          'DENIED')
    assert r.independent_agreement('operator-key', 'correction-1', 'claim-digest')['producers'] == 1


def test_a_tampered_receipt_chain_is_refused(rig):  # noqa: F811
    r, c, _root, _ = rig
    digest = swarm_summaries(r, c, 2).pop()
    seq, body = r.db.execute("SELECT seq, body FROM tbc_receipts ORDER BY seq DESC LIMIT 1").fetchone()
    r.db.execute('UPDATE tbc_receipts SET body=? WHERE seq=?', (body.replace('ALLOWED', 'ACCEPTED'), seq))
    with pytest.raises(AuthorityDenied, match='INTEGRITY_FAILURE'):
        r.independent_agreement('operator-key', 'correction-1', digest)


def test_agents_cannot_assess_their_own_agreement(rig):  # noqa: F811
    r, _c, root, _ = rig
    with pytest.raises(AuthorityDenied):
        r.independent_agreement(root['token'], 'correction-1', 'claim-digest')
