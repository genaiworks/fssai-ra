"""One publication step for evidence: tree head, forward-secure key, time, quorum.

The evidence modules each close one hole. This one composes them into the
checkpoint a deployment actually publishes and the single verification an
auditor actually runs:

1. **Commit.** The ledger's record hashes become the leaves of an RFC 9162
   Merkle tree (:mod:`fssaira.transparency`).
2. **Sign.** The tree head is signed with the forward-secure key of the period
   its ``signed_at`` falls in (:mod:`fssaira.forward_secure`), so a key stolen
   later cannot produce it.
3. **Anchor.** The signed head seeds a chained query to several time servers
   (:mod:`fssaira.time_anchor`), so its claimed time is bounded by clocks the
   enforcer does not control.
4. **Witness.** Each witness co-signs only if the head extends what it
   co-signed before, checked from a logarithmic consistency proof; the verifier
   counts distinct administrative domains.

:func:`verify_federated` checks all four and the recomputed root when the
leaves are supplied, and names the first failure. :func:`prove_record` and
:func:`verify_record` show one record is in a published checkpoint without
handing over the rest of the ledger -- what an appeal or a regulator's spot
check needs.
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from .evidence_notary import _canonical
from .forward_secure import (
    ForwardSecureCode,
    ForwardSecureSignature,
    ForwardSecureSigner,
    verify_forward_secure,
)
from .time_anchor import TimeAnchor, TimeServer, anchor, verify_anchor
from .transparency import (
    MerkleRefused,
    MerkleWitness,
    SignedTreeHead,
    TreeCosignature,
    WitnessIdentity,
    consistency_proof,
    inclusion_proof,
    merkle_root,
    verify_inclusion,
    verify_quorum,
)


class FederationCode:
    VALID = "EVIDENCE_FEDERATED_VALID"
    ROOT_MISMATCH = "EVIDENCE_ROOT_MISMATCH"
    RECORD_INCLUDED = "EVIDENCE_RECORD_INCLUDED"
    RECORD_NOT_INCLUDED = "EVIDENCE_RECORD_NOT_INCLUDED"


def runtime_leaves(db: sqlite3.Connection) -> list[bytes]:
    """Leaves from a runtime ``evidence`` table (seq from 1, HMAC-chained ``head``)."""
    rows = db.execute("SELECT seq, head FROM evidence ORDER BY seq").fetchall()
    if [row[0] for row in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("evidence rows must be a gap-free run from seq 1")
    return [row[1].encode("ascii") for row in rows]


def fs_head_verifier(roots: dict[str, bytes]) -> Callable[[SignedTreeHead], str | None]:
    """Verify a tree head whose signature field carries a forward-secure signature."""
    def verify(head: SignedTreeHead) -> str | None:
        try:
            signature = ForwardSecureSignature.from_dict(json.loads(head.signature))
        except (ValueError, KeyError, TypeError):
            return ForwardSecureCode.SIGNATURE_INVALID
        if signature.key_id != head.key_id:
            return ForwardSecureCode.ROOT_UNTRUSTED
        code = verify_forward_secure(roots, head.payload(), signature, at=head.signed_at)
        return None if code == ForwardSecureCode.VALID else code
    return verify


@dataclass(frozen=True)
class FederatedCheckpoint:
    head: SignedTreeHead
    anchor: TimeAnchor
    cosignatures: tuple[TreeCosignature, ...]
    refusals: tuple[dict, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {"head": self.head.to_dict(), "anchor": self.anchor.to_dict(),
                "cosignatures": [c.to_dict() for c in self.cosignatures],
                "refusals": list(self.refusals)}


class EvidenceFederation:
    """Publish checkpoints through every evidence control at once."""

    def __init__(self, *, signer: ForwardSecureSigner, time_servers: Sequence[TimeServer],
                 witnesses: Sequence[MerkleWitness],
                 clock: Callable[[], float] | None = None) -> None:
        if not witnesses or not time_servers:
            raise ValueError("federation needs witnesses and time servers")
        self.signer, self.time_servers, self.witnesses = signer, tuple(time_servers), tuple(witnesses)
        self._clock = clock or time.time

    def publish(self, leaves: Sequence[bytes]) -> FederatedCheckpoint:
        signed_at = round(self._clock(), 6)
        self.signer.advance_to_time(signed_at)
        unsigned = SignedTreeHead(len(leaves), merkle_root(leaves).hex(), signed_at,
                                  self.signer.schedule.key_id, "")
        signature = self.signer.sign(unsigned.payload())
        head = SignedTreeHead(**{**unsigned.__dict__,
                                 "signature": json.dumps(signature.to_dict(), sort_keys=True)})
        cosignatures, refusals = [], []
        for witness in self.witnesses:
            last = witness.state()
            proof = (consistency_proof(last["size"], leaves)
                     if last and 0 < last["size"] <= len(leaves) else [])
            try:
                cosignatures.append(witness.cosign(head, proof))
            except MerkleRefused as refused:
                refusals.append({"witness": witness.key_id, "domain": witness.domain,
                                 "code": refused.code})
        return FederatedCheckpoint(head, anchor(head.payload(), self.time_servers),
                                   tuple(cosignatures), tuple(refusals))


def verify_federated(checkpoint: FederatedCheckpoint, *, fs_roots: dict[str, bytes],
                     witnesses: dict[str, WitnessIdentity], threshold: int,
                     time_keys: dict[str, bytes], min_time_servers: int = 2,
                     tolerance: float = 1.0, leaves: Sequence[bytes] | None = None) -> dict:
    """Every evidence check in one verdict; the first failure names the code."""
    head = checkpoint.head
    problem = fs_head_verifier(fs_roots)(head)
    time_result = verify_anchor(checkpoint.anchor, time_keys, min_servers=min_time_servers,
                                claimed_time=head.signed_at, tolerance=tolerance,
                                subject=head.payload())
    quorum = verify_quorum(head, checkpoint.cosignatures, witnesses, threshold=threshold)
    checks = {"forward_secure": problem or ForwardSecureCode.VALID,
              "time": time_result["code"], "quorum": quorum["code"]}
    passed = {"forward_secure": problem is None, "time": time_result["anchored"],
              "quorum": quorum["met"]}
    if leaves is not None:
        recomputed = len(leaves) == head.size and merkle_root(leaves).hex() == head.root
        checks["root"] = "ROOT_RECOMPUTED" if recomputed else FederationCode.ROOT_MISMATCH
        passed["root"] = recomputed
    failed = [checks[name] for name, ok in passed.items() if not ok]
    return {"code": failed[0] if failed else FederationCode.VALID, "valid": not failed,
            "checks": checks, "distinct_domains": quorum["distinct_domains"],
            "anchored_interval": (time_result.get("earliest"), time_result.get("latest")),
            "witness_refusals": list(checkpoint.refusals)}


def prove_record(leaves: Sequence[bytes], index: int) -> dict:
    return {"index": index, "leaf": leaves[index].decode("ascii"),
            "proof": [h.hex() for h in inclusion_proof(index, leaves)]}


def verify_record(record: dict, checkpoint: FederatedCheckpoint) -> dict:
    """Is this one record in the published tree? Needs nothing else from the ledger."""
    ok = verify_inclusion(record["leaf"].encode("ascii"), record["index"], checkpoint.head.size,
                          [bytes.fromhex(h) for h in record["proof"]],
                          bytes.fromhex(checkpoint.head.root))
    return {"code": FederationCode.RECORD_INCLUDED if ok else FederationCode.RECORD_NOT_INCLUDED,
            "included": ok, "proof_hashes": len(record["proof"]),
            "tree_size": checkpoint.head.size}


def canonical_checkpoint(checkpoint: FederatedCheckpoint) -> bytes:
    return _canonical(checkpoint.to_dict())


__all__ = ["EvidenceFederation", "FederatedCheckpoint", "FederationCode", "canonical_checkpoint",
           "fs_head_verifier", "prove_record", "runtime_leaves", "verify_federated",
           "verify_record"]
