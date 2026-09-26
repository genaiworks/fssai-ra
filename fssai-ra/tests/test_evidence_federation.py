"""Publishing evidence through every control at once, and verifying it in one call."""
import dataclasses
import json

import pytest

from fssaira.evidence_federation import (
    EvidenceFederation,
    FederationCode,
    fs_head_verifier,
    prove_record,
    runtime_leaves,
    verify_federated,
    verify_record,
)
from fssaira.forward_secure import ForwardSecureSigner
from fssaira.time_anchor import TimeServer
from fssaira.transparency import MerkleWitness, WitnessIdentity
from test_tbc_composition_controls import make

LEAVES = [f'h{i}'.encode() for i in range(40)]


def federation(tmp_path, now):
    signer = ForwardSecureSigner(key_id='evidence-fs', start=0, period_seconds=3600, periods=48,
                                 seed=b'fs')
    verify = fs_head_verifier({'evidence-fs': signer.root_public})
    witnesses = [MerkleWitness(tmp_path / name, verify_head=verify, domain=domain, key_id=name,
                               seed=name.encode().ljust(32, b'.'), clock=lambda: now[0])
                 for name, domain in [('regulator-w', 'regulator'), ('audit-w', 'internal-audit'),
                                      ('ngo-w', 'civil-society')]]
    servers = [TimeServer(f't{i}', radius=2.0, seed=bytes([i + 7]) * 32,
                          clock=lambda i=i: now[0] + 0.3 * i) for i in range(3)]
    fed = EvidenceFederation(signer=signer, time_servers=servers, witnesses=witnesses,
                             clock=lambda: now[0])
    trust = {'fs_roots': {'evidence-fs': signer.root_public},
             'witnesses': {w.key_id: WitnessIdentity(w.public_key, w.domain) for w in witnesses},
             'time_keys': {k: v for s in servers for k, v in s.public_keys.items()}}
    return fed, signer, trust


def test_published_checkpoints_verify_end_to_end_as_the_log_grows(tmp_path):
    now = [1000.0]
    fed, _, trust = federation(tmp_path, now)
    first = fed.publish(LEAVES[:10])
    assert verify_federated(first, threshold=3, leaves=LEAVES[:10], **trust)['valid']
    now[0] = 9000.0                                   # two periods later
    second = fed.publish(LEAVES)
    result = verify_federated(second, threshold=3, leaves=LEAVES, **trust)
    assert result['code'] == FederationCode.VALID and not result['witness_refusals']
    assert result['distinct_domains'] == ['civil-society', 'internal-audit', 'regulator']
    record = prove_record(LEAVES, 17)
    assert verify_record(record, second)['included']
    assert verify_record({**record, 'leaf': 'forged'}, second)['code'] == \
        FederationCode.RECORD_NOT_INCLUDED


def test_a_rewritten_history_is_refused_by_witnesses_and_fails_quorum(tmp_path):
    now = [1000.0]
    fed, _, trust = federation(tmp_path, now)
    fed.publish(LEAVES[:10])
    now[0] = 2000.0
    rewritten = [b'x'] + LEAVES[1:20]
    forged = fed.publish(rewritten)
    assert {r['code'] for r in forged.refusals} == {'MERKLE_CONSISTENCY_INVALID'}
    assert verify_federated(forged, threshold=2, **trust)['code'] == 'WITNESS_QUORUM_NOT_MET'


def test_a_stolen_key_cannot_backdate_and_a_bad_root_is_caught(tmp_path):
    now = [1000.0]
    fed, signer, trust = federation(tmp_path, now)
    good = fed.publish(LEAVES[:5])
    now[0] = 20000.0
    fed.publish(LEAVES[:6])                           # signer is now in period 5
    backdated = dataclasses.replace(good.head, root='00' * 32)
    signature = signer.sign(backdated.payload())
    forged = dataclasses.replace(good, head=dataclasses.replace(
        backdated, signature=json.dumps(signature.to_dict())))
    assert verify_federated(forged, threshold=1, **trust)['checks']['forward_secure'] == \
        'FS_WRONG_PERIOD'
    assert verify_federated(good, threshold=3, leaves=LEAVES[:6], **trust)['code'] == \
        FederationCode.ROOT_MISMATCH


def test_a_checkpoint_claiming_a_time_outside_the_anchor_fails(tmp_path):
    now = [1000.0]
    fed, _, trust = federation(tmp_path, now)
    checkpoint = fed.publish(LEAVES[:5])
    moved = dataclasses.replace(checkpoint, head=dataclasses.replace(checkpoint.head,
                                                                     signed_at=1500.0))
    assert verify_federated(moved, threshold=1, **trust)['checks']['time'] != 'TIME_ANCHORED'


def test_the_real_runtime_ledger_publishes_and_proves_a_receipt(tmp_path):
    r, c, _, _ = make(tmp_path)
    try:
        c.request_context('campus/s1')
        leaves = runtime_leaves(r.db)
    finally:
        r.close()
    now = [1000.0]
    fed, _, trust = federation(tmp_path / 'fed', now)
    checkpoint = fed.publish(leaves)
    assert verify_federated(checkpoint, threshold=3, leaves=leaves, **trust)['valid']
    assert verify_record(prove_record(leaves, len(leaves) - 1), checkpoint)['included']


def test_federation_needs_witnesses_and_time():
    signer = ForwardSecureSigner(key_id='k', start=0, period_seconds=1, periods=1)
    with pytest.raises(ValueError):
        EvidenceFederation(signer=signer, time_servers=[], witnesses=[])
