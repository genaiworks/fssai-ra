"""Threat-inspired boundary tests; no claim of reproducing frontier-model propensity."""
import json
from dataclasses import replace

import pytest

from fssaira.tbc import AuthorityDenied, Guardian, TrustRuntime
from fssaira.tbc.client import SDKClient
from test_tbc_sdk import AUTHORITIES, declarations


@pytest.fixture
def rig(tmp_path):
    passport, task, identity = declarations()
    now = [1000]
    authorities = {**AUTHORITIES, 'monitor-key': ('safety-monitor', 'monitor')}
    r = TrustRuntime(tmp_path / 'state.db', passport, authorities=authorities, clock=lambda: now[0])
    root = r.create_task('operator-key', task, identity_scope=identity, model='offline-scripted', zone='local')
    c = SDKClient(r.dispatch, root['token'])
    c.request_capability()
    yield r, c, root, now, authorities
    r.close()


def queued(r, c, text='abcdefghij'):
    a = c.derive_artifact(text)['artifact']
    e = r.authorize_release('reviewer-key', a, 'recipient', declassify=True)
    return c.release_artifact(a, 'recipient', e)['receipt']


def test_stop_survives_reopen_denies_all_agents_and_requires_new_identity(rig):
    r, c, root, now, authorities = rig
    receipt = queued(r, c)
    assert r.emergency_stop('operator-key', reason='shutdown request')['stopped']
    for f in (lambda:
        c.derive_artifact('ignore shutdown'), lambda: r.collect_release('recipient-key', receipt),
              lambda: r.restore('operator-key', 'correction-1')):
        with pytest.raises(AuthorityDenied):
            f()
    filename = r.db.execute('PRAGMA database_list').fetchone()[2]
    other = TrustRuntime(filename, r.passport, authorities=authorities, clock=lambda: now[0])
    try:
        assert not other.dispatch(root['token'], '{"op":"request_capability"}')['ok']
        with pytest.raises(AuthorityDenied):
            other.resume_workload('monitor-key')
        other.resume_workload('operator-key')
        assert not other.dispatch(root['token'], '{"op":"request_capability"}')['ok']
        _, task, identity = declarations()
        fresh = other.create_task('operator-key', replace(task, task='recovered'), identity_scope=identity,
                                  model='offline-scripted', zone='local')
        client = SDKClient(other.dispatch, fresh['token'])
        client.request_capability()
        assert client.derive_artifact('legitimate recovery')['ok']
    finally:
        other.close()


def test_stop_stays_effective_when_evidence_writer_fails(rig, monkeypatch):
    r, c, _, _, _ = rig
    def broken(*args, **kwargs):
        raise OSError('evidence unavailable')
    monkeypatch.setattr(r.world, 'event', broken)
    assert r.emergency_stop('operator-key', reason='emergency') == {'stopped': True, 'evidence_recorded': False}
    with pytest.raises(AuthorityDenied):
        c.derive_artifact('cannot continue')


@pytest.mark.parametrize('change', ['revoke', 'contract', 'expiry', 'stop', 'source'])
def test_stream_reauthorizes_every_chunk_and_bulk_cannot_bypass(rig, change):
    r, c, root, now, _ = rig
    context = c.request_context('campus/s1')['context']
    source = r._get(context, 'artifact')['sources'][0]
    receipt = queued(r, c)
    assert r.collect_chunk('recipient-key', receipt, max_bytes=3)['bytes'] == b'abc'
    if change == 'revoke':
        Guardian(r).revoke(root['agent'])
    elif change == 'contract':
        Guardian(r).contract('correction-1', 'READ_ONLY')
    elif change == 'expiry':
        now[0] += 100
    elif change == 'stop':
        r.emergency_stop('operator-key', reason='emergency')
    else:
        r.invalidate_source('operator-key', source, reason='poisoned memory')
    with pytest.raises(AuthorityDenied):
        r.collect_chunk('recipient-key', receipt, max_bytes=3)
    with pytest.raises(AuthorityDenied):
        r.collect_release('recipient-key', receipt)
    assert r.db.execute('SELECT position FROM tbc_delivery WHERE id=?', (receipt,)).fetchone()[0] == 3


def test_stream_positive_exact_bytes_recipient_isolation_and_no_replay(rig):
    r, c, _, _, _ = rig
    receipt = queued(r, c, 'hello λ')
    with pytest.raises(AuthorityDenied):
        r.collect_chunk('other-key', receipt, max_bytes=2)
    chunks = []
    while True:
        part = r.collect_chunk('recipient-key', receipt, max_bytes=2)
        chunks.append(part['bytes'])
        if part['done']:
            break
    assert b''.join(chunks) == 'hello λ'.encode()
    with pytest.raises(AuthorityDenied):
        r.collect_chunk('recipient-key', receipt, max_bytes=2)
    with pytest.raises(AuthorityDenied):
        r.collect_release('recipient-key', receipt)


def finding(r, verdict):
    snapshot = r.monitor_snapshot('monitor-key', 'correction-1')
    return json.dumps({'snapshot': snapshot['snapshot'], 'verdict': verdict, 'reason': 'behavioral_anomaly'})


def test_ai_monitor_can_contract_but_clear_never_grants_or_restores(rig):
    r, c, _, _, _ = rig
    before = r.census('operator-key', 'correction-1')
    assert r.apply_monitor_finding('monitor-key', finding(r, 'clear'))['state'] == 'NORMAL'
    assert c.derive_artifact('benign')['ok']
    assert r.apply_monitor_finding('monitor-key', finding(r, 'uncertain'))['state'] == 'READ_ONLY'
    after = r.census('operator-key', 'correction-1')
    assert after['epoch'] > before['epoch']
    assert r.apply_monitor_finding('monitor-key', finding(r, 'clear'))['state'] == 'READ_ONLY'
    with pytest.raises(AuthorityDenied):
        c.derive_artifact('monitor approved this')
    with pytest.raises(AuthorityDenied):
        r.restore('monitor-key', 'correction-1')
    r.restore('operator-key', 'correction-1')
    c.request_capability()
    assert c.derive_artifact('authorized recovery')['ok']


@pytest.mark.parametrize('attack', ['replay', 'stale', 'forged', 'grant', 'wrong_role', 'extra', 'unknown'])
def test_monitor_advice_cannot_forge_authority_or_replay_evidence(rig, attack):
    r, c, _, _, _ = rig
    raw = finding(r, 'clear')
    token = 'monitor-key'
    if attack == 'replay':
        r.apply_monitor_finding(token, raw)
    elif attack == 'stale':
        c.derive_artifact('new event')
    elif attack == 'wrong_role':
        token = 'recipient-key'
    else:
        q = json.loads(raw)
        if attack == 'forged':
            q['snapshot'] = 'fabricated'
        elif attack == 'grant':
            q['verdict'] = 'grant'
        elif attack == 'extra':
            q['approved'] = True
        else:
            q['reason'] = 'execute code from monitor'
        raw = json.dumps(q)
    with pytest.raises((AuthorityDenied, ValueError)):
        r.apply_monitor_finding(token, raw)
    assert r.census('operator-key', 'correction-1')['state'] == 'NORMAL'
    assert c.derive_artifact('benign remains possible')['ok']


def test_monitor_gets_bounded_event_types_without_protected_text(rig):
    r, c, _, _, _ = rig
    for _ in range(40):
        c.derive_artifact('PRIVATE STUDENT DETAIL')
    snapshot = r.monitor_snapshot('monitor-key', 'correction-1')
    assert 0 < len(snapshot['events']) <= 32
    assert 'tbc_derive_artifact' in {e['kind'] for e in snapshot['events']}
    assert all(set(e) == {'sequence', 'kind'} for e in snapshot['events'])
    assert 'PRIVATE STUDENT DETAIL' not in json.dumps(snapshot)
    result = r.apply_monitor_finding('monitor-key', json.dumps({
        'snapshot': snapshot['snapshot'], 'verdict': 'suspicious', 'reason': 'behavioral_anomaly'}))
    assert result == {'state': 'QUARANTINED', 'authority_granted': False}


def test_failed_delivery_evidence_returns_no_bytes_and_preserves_cursor(rig, monkeypatch):
    r, c, _, _, _ = rig
    receipt = queued(r, c)
    original = r.world.event
    def broken(*args, **kwargs):
        raise OSError('evidence unavailable')
    monkeypatch.setattr(r.world, 'event', broken)
    with pytest.raises(OSError):
        r.collect_chunk('recipient-key', receipt, max_bytes=3)
    assert r.db.execute('SELECT position FROM tbc_delivery WHERE id=?', (receipt,)).fetchone()[0] == 0
    monkeypatch.setattr(r.world, 'event', original)
    assert r.collect_chunk('recipient-key', receipt, max_bytes=3)['bytes'] == b'abc'


@pytest.mark.parametrize('field', ['snapshot', 'verdict', 'reason'])
@pytest.mark.parametrize('value', [[], {}, None, 1, True])
def test_monitor_malformed_values_are_controlled_denials(rig, field, value):
    r, c, _, _, _ = rig
    request = json.loads(finding(r, 'suspicious'))
    request[field] = value
    with pytest.raises(AuthorityDenied):
        r.apply_monitor_finding('monitor-key', json.dumps(request))
    assert r.census('operator-key', 'correction-1')['state'] == 'NORMAL'
    assert c.derive_artifact('still available')['ok']


def test_other_task_traffic_cannot_hide_history_or_starve_monitor(rig):
    r, c, _, _, _ = rig
    c.derive_artifact('protected original task text')
    request = finding(r, 'suspicious')
    _, task, scope = declarations()
    root = r.create_task('operator-key', replace(task, task='other-task'), identity_scope=scope,
                         model='offline-scripted', zone='local')
    other = SDKClient(r.dispatch, root['token'])
    other.request_capability()
    for _ in range(140):
        assert other.derive_artifact('unrelated activity')['ok']
    snapshot = r.monitor_snapshot('monitor-key', 'correction-1')
    assert 'tbc_derive_artifact' in {e['kind'] for e in snapshot['events']}
    assert r.apply_monitor_finding('monitor-key', request)['state'] == 'QUARANTINED'
    assert other.derive_artifact('unaffected legitimate workflow')['ok']


def test_global_source_invalidation_stales_monitor_evidence(rig):
    r, c, _, _, _ = rig
    context = c.request_context('campus/s1')['context']
    source = r._get(context, 'artifact')['sources'][0]
    request = finding(r, 'clear')
    r.invalidate_source('operator-key', source, reason='poisoned source')
    with pytest.raises(AuthorityDenied, match='STALE_MONITOR_EVIDENCE'):
        r.apply_monitor_finding('monitor-key', request)


def test_attempts_after_a_stop_are_recorded_rather_than_silently_refused(rig):
    """A stopped workload that keeps trying is the signal an operator needs.

    Refusals raised before the request savepoint -- a revoked agent, a stopped
    workload, an assurance failure -- previously returned DENIED and wrote
    nothing at all, so persistence after a stop left no trace in the chain.
    """
    r, c, root, _, _ = rig
    assert r.emergency_stop('operator-key', reason='shutdown request')['stopped']
    before = r.db.execute('SELECT count(*) FROM evidence').fetchone()[0]
    for _ in range(3):
        assert not r.dispatch(root['token'], '{"op":"request_capability"}')['ok']
    rows = r.db.execute("""SELECT body FROM evidence
        WHERE json_extract(body, '$.kind')='tbc_blocked_attempt' ORDER BY seq""").fetchall()
    assert len(rows) == 3
    recorded = json.loads(rows[0][0])['data']
    assert recorded['task'] == 'correction-1'
    assert recorded['code'] == 'AGENT_REVOKED_OR_EXPIRED'
    assert r.db.execute('SELECT count(*) FROM evidence').fetchone()[0] == before + 3
    # Recording an attempt grants nothing back.
    assert not r.dispatch(root['token'], '{"op":"request_context","resource":"campus/s1",'
                          '"capability":"x"}')['ok']


def test_an_unknown_token_cannot_grow_the_evidence_chain(rig):
    """Anonymous traffic must not be a write primitive against the audit log."""
    r, _, _, _, _ = rig
    before = r.db.execute('SELECT count(*) FROM evidence').fetchone()[0]
    for _ in range(25):
        assert not r.dispatch('not-a-real-token', '{"op":"request_capability"}')['ok']
    assert r.db.execute('SELECT count(*) FROM evidence').fetchone()[0] == before


def test_a_blocked_attempt_is_visible_to_the_monitor_snapshot(rig):
    """The monitor can see that a revoked agent is still being driven.

    A contracted-but-live task already produced a ``tbc_denied`` event inside
    the request savepoint. The gap was the revoked agent, which never reaches
    that savepoint at all.
    """
    r, c, root, _, _ = rig
    Guardian(r).revoke(root['agent'])
    assert not r.dispatch(root['token'], '{"op":"request_capability"}')['ok']
    snapshot = r.monitor_snapshot('monitor-key', 'correction-1')
    assert 'tbc_blocked_attempt' in [event['kind'] for event in snapshot['events']]
