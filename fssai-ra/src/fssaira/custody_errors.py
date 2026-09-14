"""Every refusal a mediator can raise, and its stable code.

Attack harnesses catch exactly these and nothing broader: an unexpected exception is a
bug in the harness or the kernel and must surface, not be counted as a "denial".
"""
from __future__ import annotations

from .disclosure import DisclosureDenied
from .exact_action import ExecutionDenied
from .key_custody import CustodyDenied
from .model_registry import ModelAttestationDenied
from .pack_floor import PackRejected
from .privacy_vault import VaultDenied
from .review_queue import ReviewRefused

DENIALS = (DisclosureDenied, ExecutionDenied, CustodyDenied, ModelAttestationDenied, PackRejected,
           VaultDenied, ReviewRefused, PermissionError)


def denial_code(exc: BaseException) -> str:
    if isinstance(exc, PackRejected):
        return "PACK_REJECTED"
    code = getattr(exc, "code", "")
    if code:
        return str(code)
    text = str(exc)
    return text.split(":", 1)[0] if ":" in text else type(exc).__name__


__all__ = ["DENIALS", "denial_code"]
