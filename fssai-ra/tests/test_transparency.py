"""Merkle proofs, the tree-head witness, witness quorum and split-view detection."""
import hashlib
import random

import pytest

from fssaira.evidence import EvidenceLedger
from fssaira.transparency import (
    MerkleRefused,
    MerkleWitness,
    TransparencyCode,
    TreeHeadSigner,
    WitnessIdentity,
    consistency_proof,
    detect_split_view,
    ed25519_head_verifier,
    inclusion_proof,
    leaf_hash,
    ledger_leaves,
    merkle_root,
    node_hash,
    verify_consistency,
    verify_inclusion,
    verify_quorum,
)


def reference_root(leaves):
    """MTH exactly as RFC 9162 writes it, recursively."""
    if not leaves:
        return hashlib.sha256(b'').digest()
    if len(leaves) == 1:
        return leaf_hash(leaves[0])
    k = 1
    while k << 1 < len(leaves):
        k <<= 1
    return node_hash(reference_root(leaves[:k]), reference_root(leaves[k:]))


LEAVES = [f'record-{i}'.encode() for i in range(33)]


def test_root_matches_the_rfc_definition_for_every_size():
    for n in range(len(LEAVES) + 1):
        assert merkle_root(LEAVES[:n]) == reference_root(LEAVES[:n])


def test_every_inclusion_proof_verifies_and_any_change_fails():
    for n in range(1, 20):
        tree, root = LEAVES[:n], merkle_root(LEAVES[:n])
        for i in range(n):
            proof = inclusion_proof(i, tree)
            assert len(proof) <= n.bit_length()
            assert verify_inclusion(tree[i], i, n, proof, root)
            assert not verify_inclusion(b'forged', i, n, proof, root)
            # Size is authenticated by the signed tree head, not the proof; a
            # proof for one position does not verify at another.
            if n > 1:
                assert not verify_inclusion(tree[i], (i + 1) % n, n, proof, root)
            if proof:
                assert not verify_inclusion(tree[i], i, n, proof[:-1], root)


def test_every_consistency_proof_verifies_and_a_rewrite_fails():
    for n in range(1, 20):
        for m in range(1, n + 1):
            proof = consistency_proof(m, LEAVES[:n])
            old, new = merkle_root(LEAVES[:m]), merkle_root(LEAVES[:n])
            assert verify_consistency(m, n, old, new, proof)
            rewritten = [b'rewritten'] + LEAVES[1:m]
            assert not verify_consistency(m, n, merkle_root(rewritten), new, proof)


def test_ledger_leaves_come_from_the_real_chain():
    ledger = EvidenceLedger('append-token')
    for i in range(5):
        ledger.append('decision', {'i': i}, token='append-token')
    rows = [{'seq': r.seq, 'hash': r.hash} for r in ledger]
    leaves = ledger_leaves(random.Random(1).sample(rows, len(rows)))
    assert len(leaves) == 5 and verify_inclusion(leaves[3], 3, 5, inclusion_proof(3, leaves),
                                                 merkle_root(leaves))
    with pytest.raises(ValueError):
        ledger_leaves(rows[1:])


def rig(tmp_path, name='w', domain='audit-office', seed=b'w' * 32):
    signer = TreeHeadSigner(seed=b's' * 32, clock=lambda: 10.0)
    witness = MerkleWitness(tmp_path / name, verify_head=ed25519_head_verifier(signer.public_keys),
                            domain=domain, key_id=name, seed=seed, clock=lambda: 11.0)
    return signer, witness


def test_witness_follows_growth_with_log_size_proofs_and_refuses_rewrites(tmp_path):
    signer, witness = rig(tmp_path)
    witness.cosign(signer.sign(LEAVES[:4]))
    grown = signer.sign(LEAVES[:20])
    witness.cosign(grown, consistency_proof(4, LEAVES[:20]))
    assert witness.state() == {'size': 20, 'root': grown.root}
    with pytest.raises(MerkleRefused) as refused:
        witness.cosign(signer.sign(LEAVES[:10]))
    assert refused.value.code == TransparencyCode.ROLLBACK
    fork = [b'x'] + LEAVES[1:20]
    with pytest.raises(MerkleRefused) as refused:
        witness.cosign(signer.sign(fork))
    assert refused.value.code == TransparencyCode.FORK
    longer_rewrite = fork + LEAVES[20:25]
    with pytest.raises(MerkleRefused) as refused:
        witness.cosign(signer.sign(longer_rewrite), consistency_proof(20, longer_rewrite))
    assert refused.value.code == TransparencyCode.CONSISTENCY_INVALID
    impostor = TreeHeadSigner(seed=b'i' * 32)
    with pytest.raises(MerkleRefused) as refused:
        witness.cosign(impostor.sign(LEAVES[:25]), consistency_proof(20, LEAVES[:25]))
    assert refused.value.code == TransparencyCode.HEAD_UNTRUSTED


def test_quorum_counts_distinct_domains_not_keys(tmp_path):
    signer = TreeHeadSigner(seed=b's' * 32)
    verify = ed25519_head_verifier(signer.public_keys)
    witnesses = {name: MerkleWitness(tmp_path / name, verify_head=verify, domain=domain,
                                     key_id=name, seed=name.encode().ljust(32, b'0'))
                 for name, domain in [('a1', 'regulator'), ('a2', 'regulator'),
                                      ('b', 'university-audit'), ('c', 'civil-society')]}
    registry = {n: WitnessIdentity(w.public_key, w.domain) for n, w in witnesses.items()}
    head = signer.sign(LEAVES[:8])
    same_org = [witnesses['a1'].cosign(head), witnesses['a2'].cosign(head)]
    assert not verify_quorum(head, same_org, registry, threshold=2)['met']
    both = same_org + [witnesses['b'].cosign(head)]
    result = verify_quorum(head, both, registry, threshold=2)
    assert result['met'] and result['distinct_domains'] == ['regulator', 'university-audit']
    other = signer.sign(LEAVES[:9])
    stray = witnesses['c'].cosign(other)
    assert verify_quorum(head, [stray], registry, threshold=1)['rejected'][0]['why'] == 'WITNESS_MISMATCH'
    assert verify_quorum(head, both, {}, threshold=1)['code'] == TransparencyCode.QUORUM_NOT_MET


def test_split_view_is_proven_by_two_signed_heads(tmp_path):
    signer = TreeHeadSigner(seed=b's' * 32)
    verify = ed25519_head_verifier(signer.public_keys)
    honest, shown_elsewhere = signer.sign(LEAVES[:6]), signer.sign([b'x'] + LEAVES[1:6])
    assert not detect_split_view([honest, signer.sign(LEAVES[:7])], verify)['split']
    found = detect_split_view([honest, shown_elsewhere], verify)
    assert found['code'] == TransparencyCode.SPLIT_VIEW and found['conflicts'][0]['size'] == 6
    forged = TreeHeadSigner(seed=b'f' * 32).sign([b'y'] + LEAVES[1:6])
    assert not detect_split_view([honest, forged], verify)['split']
