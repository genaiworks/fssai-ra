"""Signed evidence checkpoints for the running system.

A hash chain proves every record links to the one before it. It cannot show
that the newest records were deleted: a shorter chain is still a valid chain.
A checkpoint -- the record count and head hash, signed by a notary key -- can,
because a later reader compares the chain against what was signed.

:class:`CheckpointNotary` binds :class:`~fssaira.evidence_notary.EvidenceNotary`
to a deployment. The signing key is read from an owner-only file, so it is the
same key after a restart, and every checkpoint is appended to
``checkpoints.jsonl`` in a directory that should live on storage the ledger's
writer cannot rewrite: another volume, another host, or a write-once bucket.

Limits, stated here so they travel with the code: the notary signs in the same
process as the control plane, so an attacker who controls that process can sign
a falsified ledger from then on. What it prevents is silent rewriting of history
that was already checkpointed and copied elsewhere.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .evidence_notary import Checkpoint, EvidenceNotary, verify_against_checkpoint


class CheckpointNotary:
    """Sign checkpoints, keep them append-only on disk, verify against the latest."""

    FILE = "checkpoints.jsonl"

    def __init__(self, notary: EvidenceNotary, directory: str | os.PathLike) -> None:
        self.notary = notary
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / self.FILE
        self._lock = threading.Lock()

    @classmethod
    def from_files(cls, key_file, directory, *, key_id: str = "evidence-notary-1"):
        return cls(EvidenceNotary.from_key_file(key_file, key_id=key_id), directory)

    @classmethod
    def from_env(cls) -> CheckpointNotary | None:
        """``FSSAI_NOTARY_KEY_FILE`` and ``FSSAI_NOTARY_CHECKPOINT_DIR``; ``None`` if unset."""
        key_file = os.getenv("FSSAI_NOTARY_KEY_FILE")
        if not key_file:
            return None
        directory = os.getenv("FSSAI_NOTARY_CHECKPOINT_DIR")
        if not directory:
            raise ValueError("FSSAI_NOTARY_KEY_FILE needs FSSAI_NOTARY_CHECKPOINT_DIR")
        return cls.from_files(key_file, directory,
                              key_id=os.getenv("FSSAI_NOTARY_KEY_ID", "evidence-notary-1"))

    @property
    def public_keys(self) -> dict[str, bytes]:
        return self.notary.public_keys

    def sign(self, ledger) -> Checkpoint:
        """Checkpoint the ledger as it is now and append it durably."""
        with self._lock:
            head = getattr(ledger, "head", None)
            # Reading the whole ledger on every change would make each execution
            # slower than the last; the count and head hash are all that is signed.
            checkpoint = (self.notary.checkpoint_head(*head()) if head is not None
                          else self.notary.checkpoint(list(ledger)))
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(checkpoint.to_dict(), sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return checkpoint

    def latest(self) -> Checkpoint | None:
        """The checkpoint with the highest signed count.

        Not simply the last line: concurrent executions can append a checkpoint
        for a shorter ledger after one for a longer ledger, and trusting the last
        line would then let a truncation back to the shorter length pass.
        """
        authentic, _forged = self._read()
        if not authentic:
            return None
        return max(authentic, key=lambda item: (item.count, item.signed_at))

    def _read(self) -> tuple[list[Checkpoint], int]:
        """Checkpoints whose signature verifies, and how many lines did not.

        A forged line (anyone who can write this file can append one) is counted
        and reported, never trusted: otherwise one fake high-count line would make
        every later verification fail.
        """
        from .evidence_notary import _verify_signature

        if not self.path.exists():
            return [], 0
        authentic, forged = [], 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = Checkpoint(**json.loads(line))
            except (TypeError, ValueError):
                forged += 1
                continue
            if _verify_signature(self.public_keys, item.key_id, item.signature, item.payload()):
                forged += 1
            else:
                authentic.append(item)
        return authentic, forged

    def verify(self, ledger) -> dict:
        """Compare the ledger with the latest retained checkpoint."""
        checkpoint = self.latest()
        if checkpoint is None:
            _authentic, forged = self._read()
            if forged:
                return {"valid": False, "code": "CHECKPOINTS_FORGED",
                        "detail": f"{forged} checkpoint line(s) failed signature verification",
                        "forged_checkpoint_lines": forged}
            return {"valid": None, "code": "NO_CHECKPOINT",
                    "detail": "no signed checkpoint has been retained yet"}
        verdict = verify_against_checkpoint(list(ledger), checkpoint, self.public_keys)
        _authentic, forged = self._read()
        return {"valid": verdict.valid, "code": verdict.code, "detail": verdict.detail,
                "checkpoint_count": checkpoint.count,
                # Someone wrote to the checkpoint store without the key: investigate.
                "forged_checkpoint_lines": forged}


__all__ = ["CheckpointNotary"]
