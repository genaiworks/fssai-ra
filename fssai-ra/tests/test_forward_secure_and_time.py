"""Forward-secure signing and multi-source time anchoring for the evidence plane."""
import dataclasses

import pytest

from fssaira.evidence_notary import _canonical
from fssaira.forward_secure import (
    ForwardSecureCode,
    ForwardSecureSigner,
    KeyErased,
    verify_forward_secure,
)
from fssaira.time_anchor import TimeCode, TimeServer, anchor, verify_anchor


def signer():
    return ForwardSecureSigner(key_id='notary-fs', start=0.0, period_seconds=3600.0, periods=24,
                               seed=b'seed')


def test_a_key_stolen_today_cannot_sign_yesterday():
    s = signer()
    roots = {'notary-fs': s.root_public}
    yesterday = s.sign(b'checkpoint at 00:30')
    assert verify_forward_secure(roots, b'checkpoint at 00:30', yesterday, at=1800) == \
        ForwardSecureCode.VALID
    s.advance_to_time(5 * 3600 + 10)
    assert s.retained_periods() == list(range(5, 24))
    # Everything a thief could copy now: no period before 5 exists anywhere.
    with pytest.raises(ValueError):
        s.advance(4)
    backdated = s.sign(b'rewritten checkpoint at 00:30')
    assert verify_forward_secure(roots, b'rewritten checkpoint at 00:30', backdated, at=1800) == \
        ForwardSecureCode.WRONG_PERIOD
    # Relabelling the signature as period 0 breaks the root's certificate.
    relabelled = dataclasses.replace(backdated, period=0)
    assert verify_forward_secure(roots, b'rewritten checkpoint at 00:30', relabelled) == \
        ForwardSecureCode.PERIOD_CERT_INVALID
    # The genuine old signature still verifies after the key is gone.
    assert verify_forward_secure(roots, b'checkpoint at 00:30', yesterday, at=1800) == \
        ForwardSecureCode.VALID


def test_verification_refuses_forgery_foreign_roots_and_bad_schedules():
    s = signer()
    sig = s.sign(b'x')
    assert verify_forward_secure({'notary-fs': s.root_public}, b'y', sig) == \
        ForwardSecureCode.SIGNATURE_INVALID
    assert verify_forward_secure({}, b'x', sig) == ForwardSecureCode.ROOT_UNTRUSTED
    other = ForwardSecureSigner(key_id='notary-fs', start=0, period_seconds=60, periods=2)
    assert verify_forward_secure({'notary-fs': other.root_public}, b'x', sig) != \
        ForwardSecureCode.VALID
    stretched = dataclasses.replace(sig, schedule=dataclasses.replace(sig.schedule,
                                                                      period_seconds=7200.0))
    assert verify_forward_secure({'notary-fs': s.root_public}, b'x', stretched) == \
        ForwardSecureCode.SCHEDULE_INVALID
    s.advance(24)
    with pytest.raises(KeyErased):
        s.sign(b'x')


def servers(*offsets, radius=1.0):
    return [TimeServer(f'time-{i}', radius=radius, seed=bytes([i + 1]) * 32,
                       clock=lambda o=o: 1000.0 + o) for i, o in enumerate(offsets)]


def keys(ss):
    return {k: v for s in ss for k, v in s.public_keys.items()}


def test_honest_servers_anchor_a_checkpoint_and_its_claimed_time():
    ss = servers(0.0, 0.4, -0.3)
    subject = _canonical({'count': 7, 'head_hash': 'ab', 'signed_at': 1000.2})
    a = anchor(subject, ss)
    result = verify_anchor(a, keys(ss), min_servers=3, claimed_time=1000.2, subject=subject)
    assert result['code'] == TimeCode.ANCHORED and result['earliest'] <= 1000.2 <= result['latest']
    backdated = verify_anchor(a, keys(ss), claimed_time=900.0)
    assert backdated['code'] == TimeCode.CLAIM_OUTSIDE
    assert verify_anchor(a, keys(ss), subject=b'other')['code'] == TimeCode.CHAIN_BROKEN


def test_a_lying_server_is_caught_by_the_chain():
    ss = servers(0.0, -600.0)                # the second server's clock is ten minutes slow
    a = anchor(b'checkpoint', ss)
    result = verify_anchor(a, keys(ss), min_servers=2)
    assert result['code'] == TimeCode.SOURCES_DISAGREE and result['misbehaviour']


def test_quorum_signatures_and_chain_are_enforced():
    ss = servers(0.0, 0.1)
    a = anchor(b'checkpoint', ss)
    assert verify_anchor(a, keys(ss), min_servers=3)['code'] == TimeCode.QUORUM_NOT_MET
    assert verify_anchor(a, keys(ss[:1]), min_servers=1)['code'] == TimeCode.SIGNATURE_INVALID
    reordered = dataclasses.replace(a, responses=a.responses[::-1])
    assert verify_anchor(reordered, keys(ss))['code'] == TimeCode.CHAIN_BROKEN
    lie = dataclasses.replace(a.responses[1], midpoint=5000.0)
    tampered = dataclasses.replace(a, responses=(a.responses[0], lie))
    assert verify_anchor(tampered, keys(ss))['code'] == TimeCode.SIGNATURE_INVALID
