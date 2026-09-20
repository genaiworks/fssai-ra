"""State-observing regressions for the second audit of the joined boundary."""
import json

import pytest

from fssaira.joined_workflow import Workflow, call


@pytest.fixture
def w(tmp_path):
    world = Workflow(tmp_path / 'review.db')
    yield world
    world.close()


def approved(w):
    context = call(w, op='read')['context']
    proposal = call(w, op='propose', context=context, value='B',
                    operation='correct_transcript', recipient='recipient')['proposal']
    confirmation = call(w, 'demo-instructor', op='confirm', proposal=proposal)['confirmation']
    approval = call(w, 'demo-registrar', op='approve', proposal=proposal,
                    confirmation=confirmation)['approval']
    return proposal, approval


def revoke_restore(w):
    for value in (0, 1):
        assert call(w, 'demo-admin', op='change', kind='consent', value=value)['ok']


def test_consent_restore_does_not_resurrect_approval(w):
    p, a = approved(w)
    revoke_restore(w)
    assert not call(w, op='execute', proposal=p, approval=a)['ok']
    assert w.record('campus', 's1')['value'] == 'C'
    assert w.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 0
    p, a = approved(w)
    assert call(w, op='execute', proposal=p, approval=a)['ok']
    assert call(w, 'demo-recipient', op='release', proposal=p)['ok']


def test_consent_restore_does_not_release_cached_result(w):
    p, a = approved(w)
    assert call(w, op='execute', proposal=p, approval=a)['ok']
    revoke_restore(w)
    assert not call(w, 'demo-recipient', op='release', proposal=p)['ok']
    assert w.db.execute('SELECT count(*) FROM sinks').fetchone()[0] == 0


@pytest.mark.parametrize('kind,value', [('consent', 0), ('clock', 101),
                                        ('policy', 2), ('recipient_version', 2)])
@pytest.mark.parametrize('operation', ['execute', 'reconcile'])
def test_cached_status_obeys_current_disclosure_authority(w, kind, value, operation):
    p, a = approved(w)
    assert call(w, op='execute', proposal=p, approval=a)['ok']
    assert call(w, 'demo-admin', op='change', kind=kind, value=value)['ok']
    q = {'op': operation, 'proposal': p}
    if operation == 'execute':
        q['approval'] = a
    assert call(w, **q) == {'ok': False, 'code': 'DENIED'}
    assert w.db.execute('SELECT count(*) FROM effects').fetchone()[0] == 1
    assert call(w, 'demo-registrar', op='reconcile', proposal=p)['state'] == 'committed'


def test_deep_json_returns_generic_denial_and_preserves_availability(w):
    raw = '{"op":"read","subject":' + '[' * 2000 + '0' + ']' * 2000 + '}'
    assert w.dispatch('demo-advisor', raw) == {'ok': False, 'code': 'DENIED'}
    assert call(w, op='read')['ok']


@pytest.mark.parametrize('witness', [{'seq': 0, 'head': '0' * 64},
                                      {'seq': True, 'head': 'bad'}, {},
                                      {'seq': '1', 'head': 'bad'}])
def test_invalid_checkpoint_is_not_accepted_or_raised(w, witness):
    assert w.verify(witness) is False
    assert w.verify(w.checkpoint()) is True


def test_cli_bounded_input_contract():
    # CLI process coverage lives here because dispatch limits alone cannot bound stdin buffering.
    import os
    import subprocess
    import sys
    import tempfile
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'joined_request.py'
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run([sys.executable, str(script), '--database', tmp + '/cli.db'],
                                input=' ' * 20000, text=True, capture_output=True,
                                env={**os.environ, 'FSSAI_DEMO_TOKEN': 'demo-advisor'}, timeout=10)
        assert result.returncode == 0
        assert json.loads(result.stdout) == {'ok': False, 'code': 'DENIED'}


def test_existing_store_upgrade_invalidates_old_context(w):
    p, a = approved(w)
    # Reproduce the previous schema's absence of an authorization epoch.
    body = w.get(p, 'proposal')
    del body['binding']['consent_version']
    w.db.execute('UPDATE objects SET body=? WHERE id=?', (json.dumps(body), p))
    w.db.execute("DELETE FROM meta WHERE k='consent_version'")
    path = w.path
    w.close()
    w.db = Workflow(path).db
    assert not call(w, op='execute', proposal=p, approval=a)['ok']
    fresh, approval = approved(w)
    assert call(w, op='execute', proposal=fresh, approval=approval)['ok']


def test_checkpoint_sequence_cannot_skip_missing_anchor(w):
    assert call(w, op='read')['ok']
    checkpoint = w.checkpoint()
    w.db.execute('UPDATE evidence SET seq=seq+10')
    assert w.verify(checkpoint) is False


def test_concurrent_store_initialization_has_one_seed(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    path = tmp_path / 'shared.db'
    barrier = Barrier(4)

    def open_store(_):
        barrier.wait(timeout=10)
        world = Workflow(path)
        try:
            return world.db.execute('SELECT count(*) FROM records').fetchone()[0]
        finally:
            world.close()

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(open_store, range(4))) == [3] * 4
    world = Workflow(path)
    try:
        assert world.db.execute('SELECT count(*) FROM evidence').fetchone()[0] == 1
    finally:
        world.close()
