"""Authorized export of a single request's recorded action, with explicit gaps."""
from __future__ import annotations

from dataclasses import asdict

from .exact_action import ExecutionDenied
from .packet_verifier import SCHEMA, canonical_hash, inspect_packet


def export_decision_packet(plane, request_id: str) -> dict:
    """Export only the requested action. Caller must authorize access first.

    The original records and authoritative receipt must agree. Replaced proposals
    or approvals, incomplete outcomes and legacy digest-less receipts fail closed.
    No signing keys, other cases' records, or invented source evidence are exported.
    """
    proposal = plane.get_proposal(request_id)
    approval = plane.get_approval(request_id)
    receipt = plane.register.result_for(request_id)
    if receipt is None:
        raise ExecutionDenied("PACKET_OUTCOME_MISSING", "a completed action receipt is required")
    profile = asdict(plane.profile)
    profile["transitions"] = [asdict(rule) for rule in plane.profile.transitions]
    body = {
        "schema": SCHEMA,
        "payload": {
            "proposal": asdict(proposal), "approval": asdict(approval), "receipt": asdict(receipt),
            "records": plane.evidence_for(request_id),
            "review_context": {
                "profile": profile, "profile_scope": "configuration_at_export",
                "evidence_content": {"status": "not_included", "reference": proposal.evidence_version},
            },
        },
    }
    packet = {**body, "payload_sha256": canonical_hash(body)}
    report = inspect_packet(packet)
    if not report["consistent"]:
        raise ExecutionDenied("PACKET_INCONSISTENT", ", ".join(report["errors"]))
    return packet
