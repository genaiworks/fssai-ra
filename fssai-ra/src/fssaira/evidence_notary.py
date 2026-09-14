"""Signed checkpoints and receipts: evidence an insider cannot quietly rewrite.

A hash chain detects an edited record only if the verifier does not also accept a
recomputed chain. Anyone who can write the ledger's storage can edit a record and
recompute every later hash; :meth:`fssaira.evidence.EvidenceLedger.verify` then
passes, because the chain is internally consistent. The chain proves order, not
authorship.

The notary closes that. It holds an Ed25519 signing key that the evidence writer
does not hold, and periodically signs a **checkpoint**: the record count and the
head hash at that moment. Verification compares the ledger against the most recent
checkpoint, so a rewritten history (different head), a truncated one (fewer
records), or a forged checkpoint (bad signature) is detected by anyone holding only
the public key. Executors and gates also ask the notary for **signed receipts**, so
a receipt shown to a student or an auditor is attributable to the mediator that
issued it and not merely a hash anyone could compute.

Publishing checkpoints outside the institution (a transparency log, a regulator's
inbox) is what removes the notary itself from the trusted base; that step is a
deployment decision and is not simulated here.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections.abc import Iterable
from dataclasses import dataclass

from .evidence import GENESIS_HASH, EvidenceRecord, _digest


class NotaryCode:
    CHECKPOINT_VALID = "CHECKPOINT_VALID"
    SIGNATURE_INVALID = "CHECKPOINT_SIGNATURE_INVALID"
    KEY_UNTRUSTED = "CHECKPOINT_KEY_UNTRUSTED"
    LEDGER_TRUNCATED = "LEDGER_TRUNCATED"
    HISTORY_REWRITTEN = "LEDGER_HISTORY_REWRITTEN"
    CHAIN_BROKEN = "LEDGER_CHAIN_BROKEN"
    RECEIPT_VALID = "RECEIPT_VALID"
    RECEIPT_INVALID = "RECEIPT_SIGNATURE_INVALID"


def _ed25519():
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    return Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature, Encoding, PublicFormat


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


@dataclass(frozen=True)
class Checkpoint:
    count: int
    head_hash: str
    signed_at: float
    key_id: str
    signature: str

    def payload(self) -> bytes:
        return _canonical({"count": self.count, "head_hash": self.head_hash,
                           "signed_at": self.signed_at, "key_id": self.key_id})

    def to_dict(self) -> dict:
        return {"count": self.count, "head_hash": self.head_hash, "signed_at": self.signed_at,
                "key_id": self.key_id, "signature": self.signature}


@dataclass(frozen=True)
class SignedReceipt:
    kind: str
    body: dict
    key_id: str
    signature: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical({"kind": self.kind, "body": self.body})).hexdigest()

    def payload(self) -> bytes:
        return _canonical({"kind": self.kind, "body": self.body, "key_id": self.key_id})

    def to_dict(self) -> dict:
        return {"kind": self.kind, "body": self.body, "digest": self.digest,
                "key_id": self.key_id, "signature": self.signature}


@dataclass(frozen=True)
class CheckpointVerdict:
    valid: bool
    code: str
    detail: str


class EvidenceNotary:
    """Signs checkpoints and receipts. ``seed`` makes the key reproducible for fixtures."""

    def __init__(self, *, key_id: str = "evidence-notary-1", seed: bytes | None = None,
                 clock=None) -> None:
        private_cls, *_ = _ed25519()
        material = seed if seed is not None else secrets.token_bytes(32)
        self._key = private_cls.from_private_bytes(material)
        self.key_id = key_id
        self._clock = clock or time.time

    @property
    def public_keys(self) -> dict[str, bytes]:
        *_, encoding, public_format = _ed25519()
        return {self.key_id: self._key.public_key().public_bytes(encoding.Raw, public_format.Raw)}

    def checkpoint(self, records: Iterable[EvidenceRecord]) -> Checkpoint:
        items = list(records)
        head = items[-1].hash if items else GENESIS_HASH
        unsigned = Checkpoint(len(items), head, round(self._clock(), 6), self.key_id, "")
        return Checkpoint(unsigned.count, head, unsigned.signed_at, self.key_id,
                          self._key.sign(unsigned.payload()).hex())

    def sign_receipt(self, kind: str, body: dict) -> SignedReceipt:
        unsigned = SignedReceipt(kind, json.loads(_canonical(body)), self.key_id, "")
        return SignedReceipt(unsigned.kind, unsigned.body, self.key_id,
                             self._key.sign(unsigned.payload()).hex())


def _verify_signature(public_keys: dict[str, bytes], key_id: str, signature: str,
                      payload: bytes) -> str | None:
    _private, public_cls, invalid, *_ = _ed25519()
    key = public_keys.get(key_id)
    if key is None:
        return NotaryCode.KEY_UNTRUSTED
    try:
        public_cls.from_public_bytes(key).verify(bytes.fromhex(signature), payload)
    except (invalid, ValueError):
        return NotaryCode.SIGNATURE_INVALID
    return None


def verify_against_checkpoint(records: Iterable[EvidenceRecord], checkpoint: Checkpoint,
                              public_keys: dict[str, bytes]) -> CheckpointVerdict:
    """Is this ledger the one the notary signed, extended only by appends?"""
    problem = _verify_signature(public_keys, checkpoint.key_id, checkpoint.signature,
                                checkpoint.payload())
    if problem:
        return CheckpointVerdict(False, problem, "the checkpoint is not authentic")
    items = list(records)
    if len(items) < checkpoint.count:
        return CheckpointVerdict(False, NotaryCode.LEDGER_TRUNCATED,
                                 f"{checkpoint.count} records were signed; {len(items)} remain")
    prev = GENESIS_HASH
    for index, record in enumerate(items):
        if record.seq != index or record.prev_hash != prev or \
                _digest(record.seq, record.ts, record.kind, record.payload, record.prev_hash) != record.hash:
            return CheckpointVerdict(False, NotaryCode.CHAIN_BROKEN,
                                     f"record {index} does not chain to its predecessor")
        prev = record.hash
    signed_head = items[checkpoint.count - 1].hash if checkpoint.count else GENESIS_HASH
    if signed_head != checkpoint.head_hash:
        return CheckpointVerdict(False, NotaryCode.HISTORY_REWRITTEN,
                                 "the chain is internally consistent but is not the history "
                                 "the notary signed")
    return CheckpointVerdict(True, NotaryCode.CHECKPOINT_VALID,
                             f"{checkpoint.count} signed records intact; "
                             f"{len(items) - checkpoint.count} appended since")


def verify_receipt(receipt: SignedReceipt, public_keys: dict[str, bytes]) -> CheckpointVerdict:
    problem = _verify_signature(public_keys, receipt.key_id, receipt.signature, receipt.payload())
    if problem:
        return CheckpointVerdict(False, NotaryCode.RECEIPT_INVALID if problem ==
                                 NotaryCode.SIGNATURE_INVALID else problem,
                                 "the receipt was not issued by a trusted mediator")
    return CheckpointVerdict(True, NotaryCode.RECEIPT_VALID, "receipt authentic")


def rewrite_history(ledger, index: int, payload: dict) -> None:
    """Attack helper: an insider with storage access edits a record and recomputes the chain.

    Lives here, beside the defence it defeats, so the attack and the check are
    reviewed together. It touches the ledger's private list exactly as write access
    to its storage would.
    """
    records = list(ledger._records)
    rebuilt: list[EvidenceRecord] = []
    prev = GENESIS_HASH
    for position, record in enumerate(records):
        body = payload if position == index else record.payload
        digest = _digest(record.seq, record.ts, record.kind, body, prev)
        rebuilt.append(EvidenceRecord(record.seq, record.ts, record.kind, body, prev, digest))
        prev = digest
    ledger._records[:] = rebuilt


__all__ = [
    "Checkpoint", "CheckpointVerdict", "EvidenceNotary", "NotaryCode", "SignedReceipt",
    "rewrite_history", "verify_against_checkpoint", "verify_receipt",
]
