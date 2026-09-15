"""Rule 2 mediator: the context gate.

*A model may request information; it cannot manufacture the entitlement to see
it, or launder what it saw.*

This module is the kernel-facing name for the gate, not a second implementation.
:class:`fssaira.disclosure.DisclosureGate` holds the record-source credential and
performs every read authorization, output labelling, declassification and
release. Its ``_authorize`` path is shared by ``assemble_context`` and
``authorize_only`` so the two cannot drift. :class:`fssaira.privacy_pipeline.PrivacyGate`
adds tokenization, envelope-encrypted records and model attestation in front of
it. Both are re-exported unchanged, and ``tests/mediators`` fails if this module
ever defines logic of its own.

Must NOT: release to a recipient that does not dominate the output label; let a
model declassify its own summary; read the record source before every
authorization check has passed.
"""
from __future__ import annotations

from fssaira.disclosure import (
    ConsentRegister,
    DataLabel,
    DeclassificationAuthority,
    DisclosureCode,
    DisclosureDenied,
    DisclosureGate,
    DisclosureGrant,
    DisclosurePolicy,
    GovernedContext,
    GovernedOutput,
    GrantAuthority,
    ReleaseReceipt,
)
from fssaira.privacy_pipeline import PrivacyGate

__all__ = [
    "ConsentRegister",
    "DataLabel",
    "DeclassificationAuthority",
    "DisclosureCode",
    "DisclosureDenied",
    "DisclosureGate",
    "DisclosureGrant",
    "DisclosurePolicy",
    "GovernedContext",
    "GovernedOutput",
    "GrantAuthority",
    "PrivacyGate",
    "ReleaseReceipt",
]
