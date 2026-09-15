"""Kernel view of the evidence plane.

The implementation lives in :mod:`fssaira.evidence` (hash chain, guarded append
path) and :mod:`fssaira.evidence_notary` (Ed25519 checkpoints signed with a key
the writer does not hold). They are re-exported here unchanged, so the kernel has
exactly one evidence implementation.
"""
from __future__ import annotations

from fssaira.evidence import GENESIS_HASH, EvidenceError, EvidenceLedger, EvidenceRecord
from fssaira.evidence_notary import (
    Checkpoint,
    CheckpointVerdict,
    EvidenceNotary,
    verify_against_checkpoint,
)

__all__ = [
    "GENESIS_HASH",
    "Checkpoint",
    "CheckpointVerdict",
    "EvidenceError",
    "EvidenceLedger",
    "EvidenceNotary",
    "EvidenceRecord",
    "verify_against_checkpoint",
]
