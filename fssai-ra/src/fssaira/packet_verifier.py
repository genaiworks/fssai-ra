"""Offline, standard-library-only checks for a decision-evidence packet.

This module deliberately does not import the executor, approval authority or
ledger implementation. Run it directly with Python on a separate machine.
It checks consistency and an optional externally retained packet fingerprint.
It does NOT authenticate the HMAC approval signature or prove that an event
occurred, that the source evidence was true, or that a decision was fair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

SCHEMA = "fssaira.decision-packet.v1"
MAX_BYTES = 2_000_000
LIMITS = [
    "Approval signature not authenticated: never distribute a signing key with a packet.",
    "A supplied fingerprint only helps if obtained and retained through an independently trusted channel.",
    "Selected request records do not establish completeness of the institution's entire ledger.",
    "The profile is the configuration at export, not proof of the policy in force at execution.",
    "Evidence source content is not included; its reference alone cannot reconstruct what the reviewer saw.",
    "Internal consistency is not proof of an event, identity, legal compliance, policy fairness or educational benefit.",
]


def canonical_hash(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _fields(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("unexpected or missing fields")


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected non-empty text")


def _number(value, *, integer=False, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int if integer else (int, float)):
        raise ValueError("unexpected number type")
    if not math.isfinite(value) or value < minimum:
        raise ValueError("invalid numeric value")


def inspect_packet(packet, expected_sha256: str | None = None) -> dict:
    """Return explicit failures and limitations. Unanchored consistency is not acceptance."""
    errors = []
    digest = None
    summary = {}
    try:
        _fields(packet, "schema payload payload_sha256")
        if packet["schema"] != SCHEMA:
            raise ValueError("unsupported packet schema")
        payload = packet["payload"]
        _fields(payload, "proposal approval receipt records review_context")
        digest = canonical_hash({"schema": SCHEMA, "payload": payload})
        if packet["payload_sha256"] != digest:
            errors.append("PACKET_DIGEST_MISMATCH")
        proposal, approval, receipt = (payload[name] for name in ("proposal", "approval", "receipt"))
        _fields(proposal, "request_id requester operation case_id expected_version from_status to_status evidence_version")
        _fields(approval, "approval_id proposal_digest approver approver_role audience expires_at key_id signature")
        _fields(receipt, "request_id case_id version status receipt_hash replayed proposal_digest")
        for name, value in proposal.items():
            if name == "expected_version":
                _number(value, integer=True, minimum=1)
            else:
                _text(value)
        for name, value in approval.items():
            if name == "expires_at":
                _number(value)
            else:
                _text(value)
        _number(receipt["version"], integer=True, minimum=1)
        if type(receipt["replayed"]) is not bool:
            raise ValueError("replayed must be boolean")
        proposal_hash = canonical_hash(proposal)
        if approval["proposal_digest"] != proposal_hash or receipt["proposal_digest"] != proposal_hash:
            errors.append("PROPOSAL_BINDING_MISMATCH")
        if approval["approver"] == proposal["requester"]:
            errors.append("REVIEWER_IS_REQUESTER")
        if (receipt["request_id"] != proposal["request_id"] or receipt["case_id"] != proposal["case_id"]
                or receipt["status"] != proposal["to_status"] or receipt["version"] != proposal["expected_version"] + 1):
            errors.append("RECEIPT_ACTION_MISMATCH")
        if receipt["receipt_hash"] != canonical_hash({
            "request_id": receipt["request_id"], "case_id": receipt["case_id"],
            "version": receipt["version"], "status": receipt["status"],
        }):
            errors.append("RECEIPT_DIGEST_MISMATCH")

        records = payload["records"]
        if not isinstance(records, list) or len(records) != 2:
            raise ValueError("exactly one intent and one outcome required")
        for record in records:
            _fields(record, "seq ts kind payload prev_hash hash")
            _number(record["seq"], integer=True)
            _number(record["ts"])
            if not isinstance(record["payload"], dict):
                raise ValueError("record payload must be an object")
            for name in ("prev_hash", "hash"):
                if not isinstance(record[name], str) or not re.fullmatch(r"[0-9a-f]{64}", record[name]):
                    raise ValueError("invalid record hash")
            encoded = json.dumps({"seq": record["seq"], "ts": record["ts"], "kind": record["kind"],
                                  "payload": record["payload"], "prev": record["prev_hash"]},
                                 sort_keys=True, allow_nan=False)
            if hashlib.sha256(encoded.encode()).hexdigest() != record["hash"]:
                errors.append("RECORD_DIGEST_MISMATCH")
        intent, outcome = records
        if intent["kind"] != "action_intent" or outcome["kind"] != "action_outcome":
            errors.append("RECORD_ORDER_INVALID")
        if outcome["seq"] <= intent["seq"]:
            errors.append("RECORD_SEQUENCE_INVALID")
        # Intervening requests are deliberately not disclosed. Check direct
        # linkage only when these two records are adjacent in the source ledger.
        if outcome["seq"] == intent["seq"] + 1 and outcome["prev_hash"] != intent["hash"]:
            errors.append("ADJACENT_LINK_MISMATCH")
        if intent["seq"] == 0 and intent["prev_hash"] != "0" * 64:
            errors.append("GENESIS_LINK_MISMATCH")
        if intent["ts"] >= approval["expires_at"]:
            errors.append("APPROVAL_EXPIRED_BEFORE_INTENT")
        ip, op = intent["payload"], outcome["payload"]
        if any(ip.get(key) != value for key, value in {
            "request_id": proposal["request_id"], "proposal_digest": proposal_hash,
            "approval_id": approval["approval_id"], "approver": approval["approver"],
            "approval_key_id": approval["key_id"], "evidence_version": proposal["evidence_version"],
        }.items()):
            errors.append("INTENT_BINDING_MISMATCH")
        if any(op.get(key) != receipt[key] for key in ("request_id", "case_id", "version", "status", "receipt_hash")):
            errors.append("OUTCOME_BINDING_MISMATCH")

        context = payload["review_context"]
        _fields(context, "profile profile_scope evidence_content")
        profile = context["profile"]
        _fields(profile, "profile_id version title resource_name owner manual_fallback transitions")
        for name in ("profile_id", "version", "title", "resource_name", "owner", "manual_fallback"):
            _text(profile[name])
        if context["profile_scope"] != "configuration_at_export":
            raise ValueError("unsupported policy provenance")
        if context["evidence_content"] != {"status": "not_included", "reference": proposal["evidence_version"]}:
            raise ValueError("unsupported evidence content declaration")
        rules = profile["transitions"]
        if not isinstance(rules, list) or not rules:
            raise ValueError("profile transitions required")
        matching = []
        for rule in rules:
            _fields(rule, "operation from_status to_status consequential approval_role")
            if type(rule["consequential"]) is not bool:
                raise ValueError("consequential must be boolean")
            if all(rule[key] == proposal[key] for key in ("operation", "from_status", "to_status")):
                matching.append(rule)
        if len(matching) != 1:
            errors.append("EXPORT_PROFILE_TRANSITION_MISMATCH")
        elif matching[0]["consequential"] and matching[0]["approval_role"] != approval["approver_role"]:
            errors.append("EXPORT_PROFILE_ROLE_MISMATCH")
        summary = {
            "request_id": proposal["request_id"], "resource_id": proposal["case_id"],
            "requested_by": proposal["requester"], "approved_by": approval["approver"],
            "recorded_change": f"{proposal['from_status']} -> {receipt['status']}",
            "evidence_reference": proposal["evidence_version"],
            "manual_fallback": profile["manual_fallback"],
        }
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        errors.append("MALFORMED_PACKET")

    anchored = expected_sha256 is not None
    anchor_matches = None
    if anchored:
        anchor_matches = bool(isinstance(expected_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
                              and digest == expected_sha256)
        if not anchor_matches:
            errors.append("EXTERNAL_FINGERPRINT_MISMATCH")
    consistent = not errors
    return {
        "consistent": consistent,
        "status": "inconsistent" if errors else ("anchored_consistent" if anchored else "unanchored_consistent"),
        "external_fingerprint_matches": anchor_matches,
        "approval_signature_authenticated": False,
        "evidence_content_available": False,
        "full_ledger_completeness_checked": False,
        "packet_sha256": digest, "errors": sorted(set(errors)),
        "summary": summary, "limitations": list(LIMITS),
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load_packet(path: str | Path):
    with Path(path).open("rb") as source:
        content = source.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("packet exceeds 2 MB limit")
    return json.loads(content, object_pairs_hook=_unique_object)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected-sha256", help="fingerprint obtained through a separately trusted channel")
    args = parser.parse_args(argv)
    try:
        report = inspect_packet(load_packet(args.path), args.expected_sha256)
    except (OSError, ValueError, RecursionError):
        report = {"consistent": False, "status": "invalid_input", "errors": ["UNREADABLE_OR_INVALID_JSON"]}
    print(json.dumps(report, indent=2, allow_nan=False))
    # Unanchored consistency is an incomplete check, never a green acceptance.
    return 1 if not report["consistent"] else (0 if args.expected_sha256 else 2)


if __name__ == "__main__":
    raise SystemExit(main())
