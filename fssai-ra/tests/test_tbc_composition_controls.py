"""Regressions for the V27 composition mechanisms: receipts, reservations, the
declared task graph, the fan-in gate, task revocation, freshness and the
minimum review time. Each test checks a refusal, not only a success."""
import json

import pytest

from fssaira.joined_workflow import canonical
from fssaira.tbc import AuthorityDenied, Guardian, TrustRuntime
from fssaira.tbc.client import SDKClient
from test_tbc_sdk import AUTHORITIES, declarations

AUTHORITIES = {**AUTHORITIES, 'monitor-key': ('monitor-dana', 'monitor')}


def make(tmp_path, **options):
    passport, task, identity = declarations()
    now = [1000]
    runtime = TrustRuntime(tmp_path / 'tbc.db', passport, authorities=AUTHORITIES,
                           clock=lambda: now[0], **options)
    root = runtime.create_task('operator-key', task, identity_scope=identity,
                               model='offline-scripted', zone='local')
    client = SDKClient(runtime.dispatch, root['token'])
    client.request_capability()
    return runtime, client, root, now


@pytest.fixture
def rig(tmp_path):
    runtime, client, root, now = make(tmp_path)
    yield runtime, client, root, now
    runtime.close()


def spawn(c, r):
    child = c.request('spawn_agent', scope=declarations()[2].to_dict(), model='offline-scripted',
                      zone='local', ttl=100)
    return child, SDKClient(r.dispatch, child['token'])


def remaining(r):
    return json.loads(r.db.execute("SELECT remaining FROM tbc_tasks WHERE id='correction-1'").fetchone()[0])


def approved_proposal(r, c):
    context = c.request_context('campus/s1')['context']
    p = c.propose_effect(context, 'correct_transcript', 'B', 'recipient')['proposal']
    return p, r.confirm_effect('source-key', p)


# Decision receipts -----------------------------------------------------------

def test_receipts_bind_policy_epoch_lineage_digest_recipient_and_outcome(rig):
    r, c, _, _ = rig
    summary = c.invoke_tool('summarize', c.request_context('campus/s1')['artifact'])['artifact']
    escrow = r.authorize_release('reviewer-key', summary, 'recipient', declassify=True)
    released = c.release_artifact(summary, 'recipient', escrow)
    with pytest.raises(AuthorityDenied):
        c.request_context('campus/s2')
    receipts = r.decision_receipts('monitor-key', 'correction-1')
    release = next(x for x in receipts if x['operation'] == 'release_artifact')
    assert release['outcome'] == 'ALLOWED'
    assert release['artifact_digest'] == released['digest']
    assert release['recipient'] == 'recipient'
    assert release['epoch'] == 1 and release['policy_version'] == r.passport.policy_version
    assert release['source_lineage']
    denied = receipts[-1]
    assert denied['outcome'] == 'DENIED' and denied['code'] == 'CONTEXT_SCOPE_DENIED'
    # Receipts carry digests and identifiers, never the record text.
    assert all('"supported"' not in json.dumps(x) for x in receipts)


def test_receipts_need_independent_authority_detect_tampering_and_expire(tmp_path):
    r, c, _, now = make(tmp_path, receipt_retention_seconds=60)
    try:
        c.request_context('campus/s1')
        for token in ('recipient-key', 'reviewer-key', 'not-a-key'):
            with pytest.raises(AuthorityDenied):
                r.decision_receipts(token, 'correction-1')
        seq, body = r.db.execute('SELECT seq,body FROM tbc_receipts ORDER BY seq DESC LIMIT 1').fetchone()
        r.db.execute('UPDATE tbc_receipts SET body=? WHERE seq=?', (body.replace('ALLOWED', 'DENIED'), seq))
        with pytest.raises(AuthorityDenied, match='INTEGRITY_FAILURE'):
            r.decision_receipts('operator-key', 'correction-1')
        # Pruning verifies first, so it cannot launder a tampered prefix away.
        now[0] += 61
        with pytest.raises(AuthorityDenied, match='INTEGRITY_FAILURE'):
            r.prune_receipts('operator-key')
    finally:
        r.close()


def test_receipt_chain_detects_deletion_and_survives_pruning(tmp_path):
    r, c, _, now = make(tmp_path, receipt_retention_seconds=60)
    try:
        c.request_context('campus/s1')
        c.derive_artifact('note')
        assert r.verify_receipts('monitor-key')['receipts'] == 3
        now[0] += 61
        c.derive_artifact('later note')
        assert r.prune_receipts('operator-key')['removed'] == 3
        chain = r.verify_receipts('operator-key')
        assert chain['receipts'] == 1 and chain['anchor']
        assert [x['operation'] for x in r.decision_receipts('operator-key', 'correction-1')] == ['derive_artifact']
        c.derive_artifact('third')
        c.derive_artifact('fourth')
        middle = r.db.execute('SELECT seq FROM tbc_receipts ORDER BY seq LIMIT 1 OFFSET 1').fetchone()[0]
        r.db.execute('DELETE FROM tbc_receipts WHERE seq=?', (middle,))
        with pytest.raises(AuthorityDenied, match='INTEGRITY_FAILURE'):
            r.verify_receipts('operator-key')
    finally:
        r.close()


def test_denied_receipts_never_store_untrusted_destination_text(rig):
    r, c, _, _ = rig
    smuggled = 'student s1 grade B ' * 4
    summary = c.derive_artifact('x')['artifact']
    with pytest.raises(AuthorityDenied):
        c.request('release_artifact', artifact=summary, destination=smuggled, escrow='forged')
    denied = r.decision_receipts('operator-key', 'correction-1')[-1]
    assert denied['outcome'] == 'DENIED' and denied['recipient'] is None and denied['request_digest']
    assert 'grade' not in r.db.execute('SELECT group_concat(body) FROM tbc_receipts').fetchone()[0]


def test_blocked_and_guardian_refusals_are_receipted(rig):
    r, c, root, _ = rig
    Guardian(r).revoke(root['agent'])
    assert not r.dispatch(root['token'], '{"op":"request_capability"}')['ok']
    blocked = r.decision_receipts('operator-key', 'correction-1')[-1]
    assert blocked['outcome'] == 'BLOCKED' and blocked['code'] == 'AGENT_REVOKED_OR_EXPIRED'


# Shared budget reservations ----------------------------------------------------

def test_sibling_reservations_share_one_balance_and_settle_once(rig):
    r, _, _, _ = rig
    start = remaining(r)['compute_units']
    first = r.reserve_budget('operator-key', 'correction-1', compute_units=start // 2)
    second = r.reserve_budget('operator-key', 'correction-1', compute_units=start - start // 2)
    with pytest.raises(AuthorityDenied, match='AGGREGATE_BUDGET_EXHAUSTED'):
        r.reserve_budget('operator-key', 'correction-1', compute_units=1)
    assert r.settle_reservation('operator-key', first['reservation'], compute_units=10)['state'] == 'settled'
    assert remaining(r)['compute_units'] == start // 2 - 10
    for close in (lambda: r.settle_reservation('operator-key', first['reservation']),
                  lambda: r.cancel_reservation('operator-key', first['reservation'])):
        with pytest.raises(AuthorityDenied, match='RESERVATION_ALREADY_SETTLED'):
            close()
    with pytest.raises(AuthorityDenied, match='SETTLEMENT_EXCEEDS_RESERVATION'):
        r.settle_reservation('operator-key', second['reservation'], compute_units=start)
    r.cancel_reservation('operator-key', second['reservation'])
    assert remaining(r)['compute_units'] == start - 10


def test_bound_reservation_meters_the_worker_and_charges_once(rig):
    r, c, _, _ = rig
    child, worker = spawn(c, r)
    start = remaining(r)['calls']
    held = r.reserve_budget('operator-key', 'correction-1', agent=child['agent'], calls=3)
    assert remaining(r)['calls'] == start - 3
    worker.request_capability()
    worker.derive_artifact('one')
    # The worker's calls draw on its reservation, not a second time on the task.
    assert remaining(r)['calls'] == start - 3
    worker.derive_artifact('two')
    assert not r.dispatch(child['token'], canonical({'op': 'derive_artifact', 'capability': worker.capability,
                                                      'text': 'four'}))['ok']
    with pytest.raises(AuthorityDenied, match='RESERVATION_ALREADY_BOUND'):
        r.reserve_budget('operator-key', 'correction-1', agent=child['agent'], calls=1)
    with pytest.raises(AuthorityDenied, match='SETTLEMENT_IS_METERED'):
        r.settle_reservation('operator-key', held['reservation'], calls=0)
    listed = r.reservations('monitor-key', 'correction-1')
    assert listed[0]['agent'] == child['agent'] and listed[0]['remaining'] == {'calls': 0}
    assert r.settle_reservation('operator-key', held['reservation'])['used'] == {'calls': 3}
    assert remaining(r)['calls'] == start - 3


def test_cancelling_a_metered_reservation_keeps_spent_budget_spent(rig):
    r, c, _, _ = rig
    child, worker = spawn(c, r)
    start = remaining(r)['calls']
    held = r.reserve_budget('operator-key', 'correction-1', agent=child['agent'], calls=5)
    worker.request_capability()
    assert r.cancel_reservation('operator-key', held['reservation'])['used'] == {'calls': 1}
    assert remaining(r)['calls'] == start - 1


def test_reservations_require_operator_and_an_unrestricted_task(rig):
    r, _, _, _ = rig
    with pytest.raises(AuthorityDenied):
        r.reserve_budget('reviewer-key', 'correction-1', calls=1)
    with pytest.raises(AuthorityDenied, match='UNKNOWN_BUDGET'):
        r.reserve_budget('operator-key', 'correction-1', gpu_hours=1)
    Guardian(r).contract('correction-1', 'READ_ONLY')
    with pytest.raises(AuthorityDenied, match='RESERVATION_RESTRICTED'):
        r.reserve_budget('operator-key', 'correction-1', calls=1)


# Declared task graph -----------------------------------------------------------

def test_declared_graph_admits_each_node_and_edge_before_use(rig):
    r, c, root, _ = rig
    child, worker = spawn(c, r)
    a = c.request_context('campus/s1')['artifact']
    r.admit_graph('operator-key', 'correction-1', nodes=[root['agent']])
    # The spawned worker exists but has not been admitted: it cannot act.
    with pytest.raises(AuthorityDenied):
        worker.request_capability()
    # An admitted node still cannot use an undeclared edge.
    r.admit_graph('operator-key', 'correction-1', nodes=[child['agent']])
    worker.request_capability()
    with pytest.raises(AuthorityDenied):
        c.request('send_message', recipient=child['agent'], channel='internal', artifact=a)
    # Replanning is an explicit admission by trusted authority.
    graph = r.admit_graph('operator-key', 'correction-1', edges=[(root['agent'], child['agent'], 'internal')])
    assert graph['edges'] == [[root['agent'], child['agent'], 'internal']]
    mid = c.request('send_message', recipient=child['agent'], channel='internal', artifact=a)['message']
    assert worker.request('receive_message', message=mid)['labels'] == ['synthetic-academic']


def test_retracting_an_edge_stops_messages_already_queued_on_it(rig):
    r, c, root, _ = rig
    child, worker = spawn(c, r)
    r.admit_graph('operator-key', 'correction-1', nodes=[root['agent'], child['agent']],
                  edges=[(root['agent'], child['agent'], 'internal')])
    worker.request_capability()
    a = c.request_context('campus/s1')['artifact']
    mid = c.request('send_message', recipient=child['agent'], channel='internal', artifact=a)['message']
    graph = r.retract_graph('operator-key', 'correction-1', edges=[(root['agent'], child['agent'], 'internal')])
    assert graph['edges'] == [] and graph['declared']
    with pytest.raises(AuthorityDenied):
        worker.request('receive_message', message=mid)
    r.retract_graph('operator-key', 'correction-1', nodes=[child['agent']])
    with pytest.raises(AuthorityDenied):
        worker.request_capability()
    kinds = {e['kind'] for e in r.monitor_snapshot('monitor-key', 'correction-1')['events']}
    assert {'tbc_graph_admitted', 'tbc_graph_retracted'} <= kinds


def test_graph_admission_cannot_reference_unknown_nodes_or_channels(rig):
    r, c, root, _ = rig
    child, _ = spawn(c, r)
    r.admit_graph('operator-key', 'correction-1', nodes=[root['agent']])
    with pytest.raises(AuthorityDenied, match='NODE_NOT_ADMITTED'):
        r.admit_graph('operator-key', 'correction-1', edges=[(root['agent'], child['agent'], 'internal')])
    r.admit_graph('operator-key', 'correction-1', nodes=[child['agent']])
    with pytest.raises(AuthorityDenied, match='AIRLOCK_CHANNEL_DENIED'):
        r.admit_graph('operator-key', 'correction-1', edges=[(root['agent'], child['agent'], 'external')])
    with pytest.raises(AuthorityDenied):
        r.admit_graph('monitor-key', 'correction-1', nodes=[child['agent']])


def test_tasks_without_a_declared_graph_keep_existing_behaviour(rig):
    r, c, _, _ = rig
    child, worker = spawn(c, r)
    worker.request_capability()
    a = c.request_context('campus/s1')['artifact']
    assert c.request('send_message', recipient=child['agent'], channel='internal', artifact=a)['message']
    assert r.task_graph('operator-key', 'correction-1')['declared'] is False


# Fan-in gate -----------------------------------------------------------------------

def test_fan_in_checks_identity_provenance_epoch_and_destination(rig):
    r, c, root, _ = rig
    _, worker = spawn(c, r)
    worker.request_capability()
    worker.request_context('campus/s1')
    result = worker.derive_artifact('draft grade note')['artifact']
    good = r._get(result, 'artifact')['digest']
    with pytest.raises(AuthorityDenied, match='ARTIFACT_IDENTITY_MISMATCH'):
        r.accept_result('operator-key', result, coordinator=root['agent'], expected_digest='0' * 64,
                        destination='recipient')
    with pytest.raises(AuthorityDenied, match='DESTINATION_DENIED'):
        r.accept_result('operator-key', result, coordinator=root['agent'], expected_digest=good,
                        destination='public')
    accepted = r.accept_result('operator-key', result, coordinator=root['agent'], expected_digest=good,
                               destination='recipient')
    assert accepted['digest'] == good
    assert r._get(accepted['artifact'], 'artifact')['audience'] == [root['agent']]
    assert r.decision_receipts('operator-key', 'correction-1')[-1]['outcome'] == 'ACCEPTED'
    Guardian(r).revoke_task('correction-1')
    with pytest.raises(AuthorityDenied, match='STALE_RESULT'):
        r.accept_result('operator-key', result, coordinator=root['agent'], expected_digest=good,
                        destination='recipient')


def test_fan_in_is_charged_and_refusals_are_receipted(rig):
    r, c, root, _ = rig
    _, worker = spawn(c, r)
    worker.request_capability()
    result = worker.derive_artifact('x' * 500)['artifact']
    good = r._get(result, 'artifact')['digest']
    before = remaining(r)['context_bytes']
    r.accept_result('operator-key', result, coordinator=root['agent'], expected_digest=good,
                    destination='recipient')
    assert remaining(r)['context_bytes'] == before - 500
    with pytest.raises(AuthorityDenied):
        r.accept_result('operator-key', result, coordinator=root['agent'], expected_digest='bad',
                        destination='recipient')
    denied = r.decision_receipts('operator-key', 'correction-1')[-1]
    assert (denied['operation'], denied['outcome'], denied['code']) == ('fan_in', 'DENIED',
                                                                         'ARTIFACT_IDENTITY_MISMATCH')


def test_fan_in_requires_a_coordinator_that_may_receive(rig):
    r, c, root, _ = rig
    from dataclasses import replace
    scope = replace(declarations()[2], operations=frozenset({'request_capability', 'derive_artifact'}))
    child = c.request('spawn_agent', scope=scope.to_dict(), model='offline-scripted', zone='local', ttl=100)
    result = c.derive_artifact('for a mute coordinator')['artifact']
    with pytest.raises(AuthorityDenied, match='AIRLOCK_RECIPIENT_DENIED'):
        r.accept_result('operator-key', result, coordinator=child['agent'],
                        expected_digest=r._get(result, 'artifact')['digest'], destination='recipient')


def test_fan_in_refuses_results_without_provenance_or_from_revoked_workers(rig):
    r, c, root, _ = rig
    child, worker = spawn(c, r)
    worker.request_capability()
    result = worker.derive_artifact('worker output')['artifact']
    good = r._get(result, 'artifact')['digest']
    Guardian(r).revoke(child['agent'])
    with pytest.raises(AuthorityDenied, match='AGENT_REVOKED_OR_EXPIRED'):
        r.accept_result('operator-key', result, coordinator=root['agent'], expected_digest=good,
                        destination='recipient')
    # A legacy artifact with no producer cannot be attributed, so it is refused.
    legacy = r._put('artifact', {k: v for k, v in r._get(c.derive_artifact('x')['artifact'], 'artifact').items()
                                 if k != 'producer'})
    with pytest.raises(AuthorityDenied, match='PROVENANCE_REQUIRED'):
        r.accept_result('operator-key', legacy, coordinator=root['agent'],
                        expected_digest=r._get(legacy, 'artifact')['digest'], destination='recipient')


# Task revocation epoch ------------------------------------------------------------

def test_task_revocation_fails_queued_writes_and_later_release_chunks(rig):
    r, c, _, _ = rig
    p, confirmation = approved_proposal(r, c)
    approval = r.approve_effect('reviewer-key', p, confirmation)
    summary = c.derive_artifact('release me')['artifact']
    escrow = r.authorize_release('reviewer-key', summary, 'recipient', declassify=True)
    receipt = c.release_artifact(summary, 'recipient', escrow)['receipt']
    assert r.collect_chunk('recipient-key', receipt, max_bytes=2)['bytes']
    Guardian(r).revoke_task('correction-1', reason='consent withdrawn')
    with pytest.raises(AuthorityDenied):
        r.collect_chunk('recipient-key', receipt, max_bytes=2)
    c.request_capability()
    with pytest.raises(AuthorityDenied):
        c.execute_effect(p, approval)
    assert r.world.record('campus', 's1')['value'] != 'B'


def test_operator_revocation_is_named_and_needs_a_reason(rig):
    r, c, _, _ = rig
    p, confirmation = approved_proposal(r, c)
    approval = r.approve_effect('reviewer-key', p, confirmation)
    with pytest.raises(AuthorityDenied, match='REASON_REQUIRED'):
        r.revoke_task('operator-key', 'correction-1', reason=' ')
    with pytest.raises(AuthorityDenied):
        r.revoke_task('reviewer-key', 'correction-1', reason='not mine')
    assert r.revoke_task('operator-key', 'correction-1', reason='consent withdrawn')['epoch'] == 2
    c.request_capability()
    with pytest.raises(AuthorityDenied):
        c.execute_effect(p, approval)
    assert 'tbc_revoke' in {e['kind'] for e in r.monitor_snapshot('monitor-key', 'correction-1')['events']}


# Freshness ------------------------------------------------------------------------------

def test_freshness_proof_fails_on_epoch_change_age_stop_or_forgery(rig):
    r, _, _, now = rig
    proof = r.issue_freshness('operator-key', 'correction-1')
    assert r.check_freshness(proof['proof'], max_age=30)['epoch'] == 1
    now[0] += 31
    with pytest.raises(AuthorityDenied, match='FRESHNESS_UNPROVEN'):
        r.check_freshness(proof['proof'], max_age=30)
    proof = r.issue_freshness('operator-key', 'correction-1')
    Guardian(r).revoke_task('correction-1')
    with pytest.raises(AuthorityDenied, match='FRESHNESS_UNPROVEN'):
        r.check_freshness(proof['proof'], max_age=30)
    body = json.loads(r.db.execute('SELECT body FROM tbc_objects WHERE id=?', (proof['proof'],)).fetchone()[0])
    r.db.execute('UPDATE tbc_objects SET body=? WHERE id=?', (canonical({**body, 'epoch': 2}), proof['proof']))
    with pytest.raises(AuthorityDenied, match='FRESHNESS_UNPROVEN'):
        r.check_freshness(proof['proof'], max_age=30)
    proof = r.issue_freshness('operator-key', 'correction-1')
    r.emergency_stop('operator-key', reason='partition')
    with pytest.raises(AuthorityDenied, match='FRESHNESS_UNPROVEN'):
        r.check_freshness(proof['proof'], max_age=30)
    with pytest.raises(AuthorityDenied):
        r.issue_freshness('reviewer-key', 'correction-1')


# Minimum review time ------------------------------------------------------------------

def test_minimum_review_time_defers_fast_approvals_to_the_manual_route(tmp_path):
    r, c, _, now = make(tmp_path, min_deliberation_seconds=30)
    try:
        p, confirmation = approved_proposal(r, c)
        with pytest.raises(AuthorityDenied, match='REVIEW_DEFERRED_TO_MANUAL'):
            r.approve_effect('reviewer-key', p, confirmation)
        queued = r.manual_queue('operator-key')
        assert [q['proposal'] for q in queued] == [p]
        assert queued[0]['reason'] == 'below_minimum_review_time'
        now[0] += 30
        c.request_capability()
        approval = r.approve_effect('reviewer-key', p, confirmation)
        assert not c.execute_effect(p, approval)['replayed']
        # A valid approval resolves the deferred entry.
        assert r.manual_queue('reviewer-key') == []
    finally:
        r.close()


def test_default_runtime_has_no_review_floor(rig):
    r, c, _, _ = rig
    p, confirmation = approved_proposal(r, c)
    assert r.approve_effect('reviewer-key', p, confirmation)
    assert r.manual_queue('reviewer-key') == []


def test_sdk_client_helpers_cover_spawn_send_and_receive(rig):
    r, c, _, _ = rig
    child = c.spawn_agent(declarations()[2], model='offline-scripted', zone='local', ttl=100)
    worker = SDKClient(r.dispatch, child['token'])
    worker.request_capability()
    a = c.request_context('campus/s1')['artifact']
    mid = c.send_message(child['agent'], 'internal', a)['message']
    assert worker.receive_message(mid)['labels'] == ['synthetic-academic']
