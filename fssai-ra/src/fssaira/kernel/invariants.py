"""Kernel view of the invariant checker.

Action invariants INV-1..INV-5 are enumerated over a pack's declared authority
space by :func:`fssaira.verification.verify_profile`. Delegation invariants are
enumerated by :func:`fssaira.delegation.verify_delegation_space`. Both are
re-exported, not reimplemented, so the figures the paper quotes have one source.
"""
from __future__ import annotations

from fssaira.delegation import verify_delegation_space
from fssaira.verification import INVARIANTS as ACTION_INVARIANTS
from fssaira.verification import verify_profile

__all__ = ["ACTION_INVARIANTS", "verify_delegation_space", "verify_profile"]
