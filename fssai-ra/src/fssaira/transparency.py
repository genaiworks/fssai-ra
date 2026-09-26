"""Merkle proofs and a witness quorum for the evidence plane.

The hash-chained ledger (:mod:`fssaira.evidence`) and the checkpoint witness
(:mod:`fssaira.witness`) already make a rewritten or forked history detectable.
They have two costs this module removes.

**Proof size.** To show that a new head extends an old one, the chain witness
needs every record in between, and to show that one record is in the ledger an
auditor needs the whole ledger. A Merkle tree over the same record hashes,
built exactly as Certificate Transparency builds one (RFC 9162, section 2.1),
turns both into proofs of ``O(log n)`` hashes:

* an **inclusion proof** shows one record (a receipt shown to a student, say) is
  in a tree of ``n`` records, with nothing else from the ledger;
* a **consistency proof** shows a tree of ``n`` records is an append-only
  extension of a tree of ``m`` records, so :class:`MerkleWitness` can co-sign
  growth without reading the growth.

**One witness is one administrator.** A single witness is a single party who can
be coerced, compromised or simply offline. :func:`verify_quorum` requires
co-signatures from ``threshold`` witnesses in **distinct administrative
domains**; two keys run by the same organisation count once. And
:func:`detect_split_view` checks what witnesses have gossiped to each other: a
log that showed two audiences two different trees of the same size has signed
its own conviction.

Nothing here replaces the linear chain. The chain orders records and the notary
signs its head; the tree is a second commitment over the same record hashes that
makes proofs short and quorum co-signing cheap.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .evidence_notary import _canonical, _ed25519, _verify_signature


class TransparencyCode:
    INCLUSION_VALID = "MERKLE_INCLUSION_VALID"
    INCLUSION_INVALID = "MERKLE_INCLUSION_INVALID"
    CONSISTENCY_VALID = "MERKLE_CONSISTENCY_VALID"
    CONSISTENCY_INVALID = "MERKLE_CONSISTENCY_INVALID"
    HEAD_UNTRUSTED = "TREE_HEAD_UNTRUSTED"
    ROLLBACK = "MERKLE_ROLLBACK"
    FORK = "MERKLE_FORK"
    QUORUM_MET = "WITNESS_QUORUM_MET"
    QUORUM_NOT_MET = "WITNESS_QUORUM_NOT_MET"
    SPLIT_VIEW = "EVIDENCE_SPLIT_VIEW"


# ---------------------------------------------------------------------------
# RFC 9162 Merkle tree hashing
# ---------------------------------------------------------------------------

EMPTY_ROOT = hashlib.sha256(b"").digest()


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _split(n: int) -> int:
    """The largest power of two strictly less than ``n`` (``n >= 2``)."""
    k = 1
    while k << 1 < n:
        k <<= 1
    return k


def _root(hashes: Sequence[bytes]) -> bytes:
    if not hashes:
        return EMPTY_ROOT
    level = list(hashes)
    # Iterative form of MTH: RFC 9162's left-heavy split is exactly the tree you
    # get by pairing adjacent nodes and carrying an odd last node up unchanged.
    while len(level) > 1:
        nxt = [node_hash(level[i], level[i + 1]) for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0]


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    """MTH(D[n]) over raw leaf data."""
    return _root([leaf_hash(d) for d in leaves])


def _path(m: int, hashes: Sequence[bytes]) -> list[bytes]:
    n = len(hashes)
    if n <= 1:
        return []
    k = _split(n)
    if m < k:
        return _path(m, hashes[:k]) + [_root(hashes[k:])]
    return _path(m - k, hashes[k:]) + [_root(hashes[:k])]


def inclusion_proof(index: int, leaves: Sequence[bytes]) -> list[bytes]:
    """PATH(m, D[n]): the audit path for leaf ``index``."""
    if not 0 <= index < len(leaves):
        raise ValueError("leaf index outside the tree")
    return _path(index, [leaf_hash(d) for d in leaves])


def _subproof(m: int, hashes: Sequence[bytes], complete: bool) -> list[bytes]:
    n = len(hashes)
    if m == n:
        return [] if complete else [_root(hashes)]
    k = _split(n)
    if m <= k:
        return _subproof(m, hashes[:k], complete) + [_root(hashes[k:])]
    return _subproof(m - k, hashes[k:], False) + [_root(hashes[:k])]


def consistency_proof(old_size: int, leaves: Sequence[bytes]) -> list[bytes]:
    """PROOF(m, D[n]): shows the first ``old_size`` leaves are a prefix."""
    if not 0 < old_size <= len(leaves):
        raise ValueError("old size must be between 1 and the tree size")
    return _subproof(old_size, [leaf_hash(d) for d in leaves], True)


def verify_inclusion(leaf: bytes, index: int, size: int, proof: Sequence[bytes],
                     root: bytes) -> bool:
    """RFC 9162 section 2.1.3.2."""
    if not 0 <= index < size:
        return False
    fn, sn, r = index, size - 1, leaf_hash(leaf)
    for p in proof:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = node_hash(p, r)
            while not fn & 1 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root


def verify_consistency(old_size: int, new_size: int, old_root: bytes, new_root: bytes,
                       proof: Sequence[bytes]) -> bool:
    """RFC 9162 section 2.1.4.2."""
    if not 0 < old_size <= new_size:
        return False
    if old_size == new_size:
        return not proof and old_root == new_root
    if not proof:
        return False
    path = list(proof)
    if old_size & (old_size - 1) == 0:          # exact power of two
        path.insert(0, old_root)
    fn, sn = old_size - 1, new_size - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1
    fr = sr = path[0]
    for c in path[1:]:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            fr, sr = node_hash(c, fr), node_hash(c, sr)
            while not fn & 1 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            sr = node_hash(sr, c)
        fn >>= 1
        sn >>= 1
    return fr == old_root and sr == new_root and sn == 0


def ledger_leaves(rows: Iterable[dict]) -> list[bytes]:
    """Leaves for a ledger: each record's own chain hash, in sequence order."""
    ordered = sorted(rows, key=lambda row: row["seq"])
    if [row["seq"] for row in ordered] != list(range(len(ordered))):
        raise ValueError("ledger rows must be a gap-free run from seq 0")
    return [row["hash"].encode("ascii") for row in ordered]


# ---------------------------------------------------------------------------
# Signed tree heads and a witness that co-signs from consistency proofs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SignedTreeHead:
    size: int
    root: str               # hex
    signed_at: float
    key_id: str
    signature: str

    def payload(self) -> bytes:
        return _canonical({"size": self.size, "root": self.root,
                           "signed_at": self.signed_at, "key_id": self.key_id})

    def to_dict(self) -> dict:
        return {"size": self.size, "root": self.root, "signed_at": self.signed_at,
                "key_id": self.key_id, "signature": self.signature}


class TreeHeadSigner:
    """The log operator's key over (size, root). Ed25519, like the notary."""

    def __init__(self, *, key_id: str = "tree-head-1", seed: bytes | None = None,
                 clock: Callable[[], float] | None = None) -> None:
        private_cls, *_ = _ed25519()
        self.key_id = key_id
        self._key = private_cls.from_private_bytes(seed if seed is not None
                                                   else secrets.token_bytes(32))
        self._clock = clock or time.time

    @property
    def public_keys(self) -> dict[str, bytes]:
        *_, encoding, public_format = _ed25519()
        return {self.key_id: self._key.public_key().public_bytes(encoding.Raw, public_format.Raw)}

    def sign(self, leaves: Sequence[bytes]) -> SignedTreeHead:
        unsigned = SignedTreeHead(len(leaves), merkle_root(leaves).hex(),
                                  round(self._clock(), 6), self.key_id, "")
        return SignedTreeHead(**{**unsigned.__dict__,
                                 "signature": self._key.sign(unsigned.payload()).hex()})


def ed25519_head_verifier(keys: dict[str, bytes]) -> Callable[[SignedTreeHead], str | None]:
    def verify(head: SignedTreeHead) -> str | None:
        return _verify_signature(keys, head.key_id, head.signature, head.payload())
    return verify


class MerkleRefused(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class TreeCosignature:
    size: int
    root: str
    head_key_id: str
    head_signature: str
    domain: str
    witnessed_at: float
    key_id: str
    signature: str

    def payload(self) -> bytes:
        return _canonical({"size": self.size, "root": self.root,
                           "head_key_id": self.head_key_id,
                           "head_signature": self.head_signature, "domain": self.domain,
                           "witnessed_at": self.witnessed_at, "key_id": self.key_id})

    def to_dict(self) -> dict:
        return {**json.loads(self.payload()), "signature": self.signature}


class MerkleWitness:
    """Co-sign tree heads that are append-only extensions of what it last signed.

    The witness keeps only ``(size, root)``. Growth is proved with a consistency
    proof of ``O(log n)`` hashes, so a witness in another organisation can follow
    a large log without ever holding its records. Refusals:

    * ``TREE_HEAD_UNTRUSTED`` -- the operator's signature on the head is bad;
    * ``MERKLE_ROLLBACK`` -- the size went backwards;
    * ``MERKLE_FORK`` -- same size, different root: two histories;
    * ``MERKLE_CONSISTENCY_INVALID`` -- the new tree does not contain the old one.
    """

    STATE = "merkle-witness-state.json"
    LOG = "tree-cosignatures.jsonl"

    def __init__(self, directory: str | os.PathLike, *,
                 verify_head: Callable[[SignedTreeHead], str | None], domain: str,
                 key_id: str = "merkle-witness-1", seed: bytes | None = None,
                 clock: Callable[[], float] | None = None) -> None:
        if not domain.strip():
            raise ValueError("a witness names the administrative domain that runs it")
        private_cls, *_ = _ed25519()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.verify_head, self.domain, self.key_id = verify_head, domain, key_id
        self._key = private_cls.from_private_bytes(seed if seed is not None
                                                   else secrets.token_bytes(32))
        self._clock = clock or time.time

    @property
    def public_key(self) -> bytes:
        *_, encoding, public_format = _ed25519()
        return self._key.public_key().public_bytes(encoding.Raw, public_format.Raw)

    def state(self) -> dict | None:
        path = self.directory / self.STATE
        return json.loads(path.read_text()) if path.exists() else None

    def cosign(self, head: SignedTreeHead, proof: Sequence[bytes] = ()) -> TreeCosignature:
        problem = self.verify_head(head)
        if problem:
            raise MerkleRefused(TransparencyCode.HEAD_UNTRUSTED, problem)
        last = self.state()
        if last is not None:
            if head.size < last["size"]:
                raise MerkleRefused(TransparencyCode.ROLLBACK,
                                    f"already witnessed {last['size']}; head claims {head.size}")
            if head.size == last["size"] and head.root != last["root"]:
                raise MerkleRefused(TransparencyCode.FORK,
                                    f"size {head.size} was already witnessed with another root")
            if last["size"] and not verify_consistency(
                    last["size"], head.size, bytes.fromhex(last["root"]),
                    bytes.fromhex(head.root), list(proof)):
                raise MerkleRefused(TransparencyCode.CONSISTENCY_INVALID,
                                    f"tree {head.size} does not extend witnessed tree {last['size']}")
        unsigned = TreeCosignature(head.size, head.root, head.key_id, head.signature,
                                   self.domain, round(self._clock(), 6), self.key_id, "")
        signed = TreeCosignature(**{**unsigned.__dict__,
                                    "signature": self._key.sign(unsigned.payload()).hex()})
        self._record(signed)
        return signed

    def _record(self, cosignature: TreeCosignature) -> None:
        with (self.directory / self.LOG).open("a", encoding="utf-8") as log:
            log.write(json.dumps(cosignature.to_dict(), sort_keys=True) + "\n")
            log.flush()
            os.fsync(log.fileno())
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix=".state-")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"size": cosignature.size, "root": cosignature.root}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.directory / self.STATE)


@dataclass(frozen=True)
class WitnessIdentity:
    """A witness a verifier trusts, and who administers it."""
    public_key: bytes
    domain: str


def verify_quorum(head: SignedTreeHead, cosignatures: Iterable[TreeCosignature],
                  witnesses: dict[str, WitnessIdentity], *, threshold: int) -> dict:
    """Require co-signatures on exactly ``head`` from ``threshold`` distinct domains.

    The domain counted is the one the *verifier* registered for the key, not the
    one the co-signature claims: a witness cannot promote itself into a second
    organisation by writing a different name.
    """
    if threshold < 1:
        raise ValueError("a quorum needs at least one witness")
    domains: dict[str, str] = {}
    rejected: list[dict] = []
    for c in cosignatures:
        identity = witnesses.get(c.key_id)
        if identity is None:
            rejected.append({"key_id": c.key_id, "why": "WITNESS_UNKNOWN"})
            continue
        if (c.size, c.root, c.head_key_id, c.head_signature) != (
                head.size, head.root, head.key_id, head.signature):
            rejected.append({"key_id": c.key_id, "why": "WITNESS_MISMATCH"})
            continue
        problem = _verify_signature({c.key_id: identity.public_key}, c.key_id, c.signature,
                                    c.payload())
        if problem:
            rejected.append({"key_id": c.key_id, "why": problem})
            continue
        domains.setdefault(identity.domain, c.key_id)
    met = len(domains) >= threshold
    return {"code": TransparencyCode.QUORUM_MET if met else TransparencyCode.QUORUM_NOT_MET,
            "met": met, "threshold": threshold, "distinct_domains": sorted(domains),
            "rejected": rejected}


def detect_split_view(heads: Iterable[SignedTreeHead],
                      verify_head: Callable[[SignedTreeHead], str | None]) -> dict:
    """Find two validly signed heads of the same size with different roots.

    Witnesses and auditors exchange the heads they were shown. Two authentic
    heads for one size are a signed proof that the log presented different
    histories to different audiences -- evidence, not suspicion.
    """
    seen: dict[int, SignedTreeHead] = {}
    conflicts = []
    for head in heads:
        if verify_head(head):
            continue                     # an unsigned claim convicts nobody
        prior = seen.setdefault(head.size, head)
        if prior.root != head.root:
            conflicts.append({"size": head.size, "roots": sorted({prior.root, head.root}),
                              "heads": [prior.to_dict(), head.to_dict()]})
    return {"code": TransparencyCode.SPLIT_VIEW if conflicts else "NO_SPLIT_VIEW",
            "split": bool(conflicts), "conflicts": conflicts}


__all__ = [
    "EMPTY_ROOT", "MerkleRefused", "MerkleWitness", "SignedTreeHead", "TransparencyCode",
    "TreeCosignature", "TreeHeadSigner", "WitnessIdentity", "consistency_proof",
    "detect_split_view", "ed25519_head_verifier", "inclusion_proof", "leaf_hash",
    "ledger_leaves", "merkle_root", "node_hash", "verify_consistency", "verify_inclusion",
    "verify_quorum",
]
