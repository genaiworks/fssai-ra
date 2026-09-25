"""An out-of-process witness that co-signs evidence checkpoints.

The notary (:mod:`fssaira.evidence_notary`) signs the ledger's count and head in
the enforcer's own process. That stops silent rewriting of history once a signed
checkpoint has been copied elsewhere, but an attacker who controls the enforcer
holds the notary key: from then on they can sign a checkpoint for any history
they like, including a rewritten one.

A witness removes that power over the *past*. It runs as a separate process
(``fssaira witness cosign``), under its own key and its own state, ideally on a
host administered by someone else. It co-signs a checkpoint only when:

* the notary's signature on it is valid (``WITNESS_NOTARY_UNTRUSTED``);
* the count never goes backwards (``WITNESS_ROLLBACK``);
* the same count never arrives with a different head -- an enforcer showing two
  histories to two audiences (``WITNESS_FORK``);
* growth arrives with the new records, and they chain from the head the witness
  already co-signed and recompute to the new head (``WITNESS_EXTENSION_REQUIRED``,
  ``WITNESS_INCONSISTENT``).

So a compromised enforcer can still sign *new* falsehoods from the moment of
compromise -- no witness can stop that -- but it cannot obtain a co-signature for
a history that contradicts one already witnessed. A verifier that requires the
witness's co-signature therefore detects a rewritten or forked past with only the
witness's public key. This is the move Certificate Transparency made with
witnesses that co-sign log heads; here the consistency proof is the linear run of
records, because the ledger is a hash chain rather than a Merkle tree.

The first checkpoint a witness sees is trusted on first use unless its records
are supplied from genesis, and the cosignature says which.
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .chain_verification import GENESIS_HASH, recompute
from .evidence_notary import Checkpoint, _canonical, _ed25519, _verify_signature


class WitnessRefused(Exception):
    """The witness will not co-sign. ``code`` is stable; ``detail`` explains."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Cosignature:
    count: int
    head_hash: str
    notary_key_id: str
    notary_signature: str
    witnessed_at: float
    first_seen: str          # "genesis-verified", "trusted-on-first-use" or "extension"
    key_id: str
    signature: str

    def payload(self) -> bytes:
        return _canonical({"count": self.count, "head_hash": self.head_hash,
                           "notary_key_id": self.notary_key_id,
                           "notary_signature": self.notary_signature,
                           "witnessed_at": self.witnessed_at, "first_seen": self.first_seen,
                           "key_id": self.key_id})

    def to_dict(self) -> dict:
        return {"count": self.count, "head_hash": self.head_hash,
                "notary_key_id": self.notary_key_id, "notary_signature": self.notary_signature,
                "witnessed_at": self.witnessed_at, "first_seen": self.first_seen,
                "key_id": self.key_id, "signature": self.signature}


def _chains(rows: list[dict], start: int, previous: str, end_head: str, count: int) -> str | None:
    """Why ``rows`` are not the records ``start..count-1`` from ``previous`` to ``end_head``."""
    if [row["seq"] for row in rows] != list(range(start, count)):
        return f"expected records {start}..{count - 1}, got {len(rows)} other record(s)"
    for row in rows:
        if row["prev_hash"] != previous:
            return f"record {row['seq']} does not link to the witnessed head"
        if recompute(row["seq"], row["ts"], row["kind"], row["payload_json"],
                     row["prev_hash"]) != row["hash"]:
            return f"record {row['seq']} does not recompute"
        previous = row["hash"]
    if previous != end_head:
        return "the records do not end at the checkpoint's head"
    return None


class CheckpointWitness:
    """Co-sign checkpoints that are consistent with everything already witnessed."""

    STATE = "witness-state.json"
    LOG = "cosignatures.jsonl"

    def __init__(self, directory: str | os.PathLike, *, notary_keys: dict[str, bytes],
                 key_id: str = "evidence-witness-1", seed: bytes | None = None,
                 clock=None) -> None:
        private_cls, *_ = _ed25519()
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.notary_keys = dict(notary_keys)
        self.key_id = key_id
        self._key = private_cls.from_private_bytes(seed if seed is not None
                                                   else secrets.token_bytes(32))
        self._clock = clock or time.time

    @classmethod
    def from_key_file(cls, path, directory, *, notary_keys, key_id="evidence-witness-1"):
        from .custody_store import load_master_key

        return cls(directory, notary_keys=notary_keys, key_id=key_id, seed=load_master_key(path))

    @property
    def public_keys(self) -> dict[str, bytes]:
        *_, encoding, public_format = _ed25519()
        return {self.key_id: self._key.public_key().public_bytes(encoding.Raw, public_format.Raw)}

    def state(self) -> dict | None:
        path = self.directory / self.STATE
        return json.loads(path.read_text()) if path.exists() else None

    def cosign(self, checkpoint: Checkpoint, extension: list[dict] | None = None) -> Cosignature:
        problem = _verify_signature(self.notary_keys, checkpoint.key_id, checkpoint.signature,
                                    checkpoint.payload())
        if problem:
            raise WitnessRefused("WITNESS_NOTARY_UNTRUSTED",
                                 f"the checkpoint's notary signature failed ({problem})")
        last = self.state()
        rows = sorted(extension or [], key=lambda row: row["seq"])
        if last is None:
            if rows:
                why = _chains(rows, 0, GENESIS_HASH, checkpoint.head_hash, checkpoint.count)
                if why:
                    raise WitnessRefused("WITNESS_INCONSISTENT", why)
                first_seen = "genesis-verified"
            else:
                first_seen = "trusted-on-first-use"
        elif checkpoint.count < last["count"]:
            raise WitnessRefused("WITNESS_ROLLBACK",
                                 f"already witnessed {last['count']} records; this checkpoint "
                                 f"claims {checkpoint.count}")
        elif checkpoint.count == last["count"]:
            if checkpoint.head_hash != last["head_hash"]:
                raise WitnessRefused("WITNESS_FORK",
                                     f"record count {checkpoint.count} was already witnessed "
                                     "with a different head")
            first_seen = "extension"
        else:
            if not rows:
                raise WitnessRefused("WITNESS_EXTENSION_REQUIRED",
                                     f"records {last['count']}..{checkpoint.count - 1} are "
                                     "needed to show the new head extends the witnessed one")
            why = _chains(rows, last["count"], last["head_hash"], checkpoint.head_hash,
                          checkpoint.count)
            if why:
                raise WitnessRefused("WITNESS_INCONSISTENT", why)
            first_seen = "extension"
        unsigned = Cosignature(checkpoint.count, checkpoint.head_hash, checkpoint.key_id,
                               checkpoint.signature, round(self._clock(), 6), first_seen,
                               self.key_id, "")
        signed = Cosignature(**{**unsigned.__dict__,
                                "signature": self._key.sign(unsigned.payload()).hex()})
        self._record(signed)
        return signed

    def _record(self, cosignature: Cosignature) -> None:
        with (self.directory / self.LOG).open("a", encoding="utf-8") as log:
            log.write(json.dumps(cosignature.to_dict(), sort_keys=True) + "\n")
            log.flush()
            os.fsync(log.fileno())
        state = {"count": cosignature.count, "head_hash": cosignature.head_hash}
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix=".state-")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.directory / self.STATE)


def verify_cosignature(checkpoint: Checkpoint, cosignature: Cosignature,
                       witness_keys: dict[str, bytes]) -> tuple[bool, str]:
    """Does this witness vouch for exactly this checkpoint?"""
    if (cosignature.count, cosignature.head_hash, cosignature.notary_key_id,
            cosignature.notary_signature) != (checkpoint.count, checkpoint.head_hash,
                                              checkpoint.key_id, checkpoint.signature):
        return False, "WITNESS_MISMATCH"
    problem = _verify_signature(witness_keys, cosignature.key_id, cosignature.signature,
                                cosignature.payload())
    return (False, problem) if problem else (True, "COSIGNED")


__all__ = ["CheckpointWitness", "Cosignature", "WitnessRefused", "verify_cosignature"]
