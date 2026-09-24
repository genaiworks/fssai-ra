"""Typed proposal and context-request interfaces (paper Section 6.1).

A model, orchestrator, or tool protocol hands the server bytes. This module turns
those bytes into a ``Proposal`` or a ``ContextRequest`` only when the bytes are
unambiguous, bounded, versioned, and name nothing the server has not declared.
The server, not the JSON, supplies principal, tenant, policy version, roles and
approval: they are copied from an authenticated :class:`CallerContext`.

Rules enforced (one stable code each, see :class:`RejectCode`):

* strict UTF-8, no byte-order mark, no lone surrogates, NFC text only;
* no duplicate keys at any depth, no nesting deeper than the limit;
* payload, string, array and object-size bounds;
* no NaN, Infinity, or a finite literal that overflows to infinity (``1e999``);
* a supported ``schema_version`` and ``kind``;
* no unknown fields, enumerated operations and purposes only, canonical IDs;
* recipients and model endpoints resolved against a server-side registry;
* server-derived security fields are *rejected*, not ignored, at any depth and
  under any Unicode compatibility spelling.

Must NOT / residual risk
------------------------
* Must NOT be used as authorization. A well-formed proposal is still only a
  proposal; the executor and the disclosure gate decide.
* Must NOT carry a rationale. There is no field for an explanation, so no
  decision can come to depend on one.
* Residual: schema validation does not make an operation's *parameters*
  semantically safe, and a registry entry is only as correct as the governance
  record that declared it. Canonical destination checks here are name-level;
  redirects and resolved network addresses belong to the network adapter.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

#: Schema versions this server parses. Anything else is refused, not guessed at.
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})

#: Canonical identifier: ASCII, no leading punctuation, bounded length.
CANONICAL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")

#: Fields the server derives. Their presence in model JSON is an attack or a bug.
SERVER_DERIVED_FIELDS: frozenset[str] = frozenset({
    "principal", "principal_id", "requester", "actor", "caller", "user", "user_id",
    "tenant", "tenant_id", "policy_version", "policy",
    "classification", "label", "labels", "data_label", "clearance",
    "authority", "role", "roles", "approval", "approvals", "approved", "approved_by",
    "approver", "permissions", "entitlement", "grant_signature",
})

_BOMS = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")


class RejectCode:
    """Stable rejection codes, one per rule."""

    ENCODING_INVALID = "TYPED_ENCODING_INVALID"
    BYTE_ORDER_MARK = "TYPED_BYTE_ORDER_MARK"
    NOT_NORMALIZED = "TYPED_TEXT_NOT_NFC"
    PAYLOAD_TOO_LARGE = "TYPED_PAYLOAD_TOO_LARGE"
    NESTING_TOO_DEEP = "TYPED_NESTING_TOO_DEEP"
    MALFORMED = "TYPED_MALFORMED_JSON"
    DUPLICATE_KEY = "TYPED_DUPLICATE_KEY"
    NON_FINITE = "TYPED_NON_FINITE_NUMBER"
    STRING_TOO_LONG = "TYPED_STRING_TOO_LONG"
    ARRAY_TOO_LONG = "TYPED_ARRAY_TOO_LONG"
    OBJECT_TOO_LARGE = "TYPED_OBJECT_TOO_LARGE"
    NOT_AN_OBJECT = "TYPED_NOT_AN_OBJECT"
    SCHEMA_VERSION = "TYPED_UNSUPPORTED_SCHEMA_VERSION"
    KIND = "TYPED_WRONG_KIND"
    SERVER_DERIVED_FIELD = "TYPED_SERVER_DERIVED_FIELD"
    UNKNOWN_FIELD = "TYPED_UNKNOWN_FIELD"
    MISSING_FIELD = "TYPED_MISSING_FIELD"
    WRONG_TYPE = "TYPED_WRONG_TYPE"
    OPERATION_NOT_ENUMERATED = "TYPED_OPERATION_NOT_ENUMERATED"
    PURPOSE_NOT_ENUMERATED = "TYPED_PURPOSE_NOT_ENUMERATED"
    FIELD_NOT_ENUMERATED = "TYPED_FIELD_NOT_ENUMERATED"
    NON_CANONICAL_ID = "TYPED_NON_CANONICAL_ID"
    UNRESOLVED_DESTINATION = "TYPED_UNRESOLVED_DESTINATION"
    UNAUTHENTICATED_CALLER = "TYPED_UNAUTHENTICATED_CALLER"


class IntegrationRejected(ValueError):
    """Untrusted input did not satisfy the integration contract.

    The message never echoes untrusted values; ``detail`` names the rule and path.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Limits:
    """Structural bounds applied before any schema interpretation."""

    max_bytes: int = 16_384
    max_depth: int = 8
    max_string: int = 4_096
    max_array: int = 64
    max_object_keys: int = 64
    max_int_digits: int = 18


@dataclass(frozen=True)
class CallerContext:
    """What the authentication layer established. Never parsed from model JSON."""

    principal: str
    tenant: str
    policy_version: str
    roles: frozenset[str] = frozenset()
    authenticated_by: str = ""

    def __post_init__(self) -> None:
        if not self.authenticated_by:
            raise IntegrationRejected(RejectCode.UNAUTHENTICATED_CALLER,
                                      "caller context must name its authenticator")
        for name in ("principal", "tenant", "policy_version"):
            if not CANONICAL_ID.fullmatch(getattr(self, name)):
                raise IntegrationRejected(RejectCode.NON_CANONICAL_ID, f"caller.{name}")


@dataclass(frozen=True)
class OperationSpec:
    """One enumerated operation and the exact types of its parameters."""

    name: str
    parameters: Mapping[str, type] = field(default_factory=dict)
    required: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DestinationRegistry:
    """Server-side declarations the untrusted side can name but never extend."""

    operations: Mapping[str, OperationSpec]
    recipients: frozenset[str] = frozenset()
    endpoints: frozenset[str] = frozenset()
    purposes: frozenset[str] = frozenset()
    fields: frozenset[str] = frozenset()

    @classmethod
    def from_policy(cls, policy: Any, operations: Iterable[OperationSpec]) -> DestinationRegistry:
        """Build from a disclosure policy: its recipients, endpoints, purposes and fields."""
        return cls(
            operations={spec.name: spec for spec in operations},
            recipients=frozenset(policy.recipients), endpoints=frozenset(policy.endpoints),
            purposes=frozenset(policy.purposes), fields=frozenset(policy.field_classes),
        )


@dataclass(frozen=True)
class Proposal:
    """A parsed proposal. Security fields come from the caller context only."""

    schema_version: str
    request_id: str
    operation: str
    target: str
    parameters: Mapping[str, Any]
    recipient: str | None
    principal: str
    tenant: str
    policy_version: str
    roles: frozenset[str]


@dataclass(frozen=True)
class ContextRequest:
    """A parsed context request. Security fields come from the caller context only."""

    schema_version: str
    request_id: str
    purpose: str
    subjects: tuple[str, ...]
    fields: tuple[str, ...]
    model_endpoint: str
    query: str
    principal: str
    tenant: str
    policy_version: str
    roles: frozenset[str]


# ---------------------------------------------------------------------------
# Structural layer: bytes to bounded, unambiguous JSON values
# ---------------------------------------------------------------------------


def _scan_depth(text: str, limit: int) -> None:
    """Refuse nesting deeper than ``limit`` before the recursive parser sees it."""
    depth, in_string, escaped = 0, False, False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > limit:
                raise IntegrationRejected(RejectCode.NESTING_TOO_DEEP, f"limit {limit}")
        elif char in "]}":
            depth -= 1


def _check_text(value: str, where: str, limits: Limits) -> None:
    if len(value) > limits.max_string:
        raise IntegrationRejected(RejectCode.STRING_TOO_LONG, where)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise IntegrationRejected(RejectCode.ENCODING_INVALID, f"{where}: lone surrogate") from exc
    if unicodedata.normalize("NFC", value) != value:
        raise IntegrationRejected(RejectCode.NOT_NORMALIZED, where)


def _security_key(key: str) -> str:
    """The compatibility-folded spelling used to detect disguised security fields."""
    return unicodedata.normalize("NFKC", key).casefold().replace("-", "_")


def _walk(value: Any, where: str, limits: Limits) -> None:
    if isinstance(value, dict):
        if len(value) > limits.max_object_keys:
            raise IntegrationRejected(RejectCode.OBJECT_TOO_LARGE, where)
        for key, item in value.items():
            _check_text(key, f"{where}.<key>", limits)
            if _security_key(key) in SERVER_DERIVED_FIELDS:
                raise IntegrationRejected(RejectCode.SERVER_DERIVED_FIELD,
                                          f"{where}: the server derives this field")
            if not key.isascii() or unicodedata.normalize("NFKC", key) != key:
                raise IntegrationRejected(RejectCode.NOT_NORMALIZED, f"{where}.<key>")
            _walk(item, f"{where}.{key}", limits)
    elif isinstance(value, list):
        if len(value) > limits.max_array:
            raise IntegrationRejected(RejectCode.ARRAY_TOO_LONG, where)
        for index, item in enumerate(value):
            _walk(item, f"{where}[{index}]", limits)
    elif isinstance(value, str):
        _check_text(value, where, limits)


def strict_loads(raw: bytes | str, limits: Limits | None = None) -> Any:
    """Parse untrusted JSON, refusing every ambiguous or unbounded form.

    This generalises ``fssaira.joined_workflow.strict_json`` (duplicate keys,
    non-finite constants, a size cap) with encoding, normalization, depth, per-
    value bounds and overflow-to-infinity checks. It returns plain JSON values.
    """
    limits = limits if limits is not None else Limits()
    if isinstance(raw, str):
        try:
            data = raw.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise IntegrationRejected(RejectCode.ENCODING_INVALID, "lone surrogate") from exc
    elif isinstance(raw, (bytes, bytearray)):
        data = bytes(raw)
    else:
        raise IntegrationRejected(RejectCode.WRONG_TYPE, "payload must be bytes or str")
    if len(data) > limits.max_bytes:
        raise IntegrationRejected(RejectCode.PAYLOAD_TOO_LARGE, f"limit {limits.max_bytes}")
    if data.startswith(_BOMS) or "﻿" in data.decode("utf-8", errors="ignore")[:1]:
        raise IntegrationRejected(RejectCode.BYTE_ORDER_MARK)
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise IntegrationRejected(RejectCode.ENCODING_INVALID, "not UTF-8") from exc
    _scan_depth(text, limits.max_depth)

    def pairs(items: list[tuple[str, Any]]) -> dict:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise IntegrationRejected(RejectCode.DUPLICATE_KEY)
            out[key] = value
        return out

    def constant(_name: str) -> Any:
        raise IntegrationRejected(RejectCode.NON_FINITE)

    def finite(literal: str) -> float:
        number = float(literal)
        if not math.isfinite(number):
            raise IntegrationRejected(RejectCode.NON_FINITE, "literal overflows")
        return number

    def bounded_int(literal: str) -> int:
        if len(literal.lstrip("-")) > limits.max_int_digits:
            raise IntegrationRejected(RejectCode.NON_FINITE, "integer out of range")
        return int(literal)

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant,
                           parse_float=finite, parse_int=bounded_int)
    except IntegrationRejected:
        raise
    except (ValueError, RecursionError) as exc:
        raise IntegrationRejected(RejectCode.MALFORMED) from exc
    _walk(value, "$", limits)
    return value


# ---------------------------------------------------------------------------
# Schema layer
# ---------------------------------------------------------------------------

_PROPOSAL_FIELDS = frozenset({"schema_version", "kind", "request_id", "operation", "target",
                              "parameters", "recipient"})
_PROPOSAL_REQUIRED = frozenset({"schema_version", "kind", "request_id", "operation", "target"})
_CONTEXT_FIELDS = frozenset({"schema_version", "kind", "request_id", "purpose", "subjects",
                             "fields", "model_endpoint", "query"})
_CONTEXT_REQUIRED = frozenset({"schema_version", "kind", "request_id", "purpose", "subjects",
                               "fields", "model_endpoint"})


def _envelope(body: Any, kind: str, allowed: frozenset[str],
              required: frozenset[str]) -> dict:
    if not isinstance(body, dict):
        raise IntegrationRejected(RejectCode.NOT_AN_OBJECT)
    version = body.get("schema_version")
    if not isinstance(version, str) or version not in SUPPORTED_SCHEMA_VERSIONS:
        raise IntegrationRejected(RejectCode.SCHEMA_VERSION)
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise IntegrationRejected(RejectCode.UNKNOWN_FIELD, f"{len(unknown)} unknown field(s)")
    missing = sorted(required - set(body))
    if missing:
        raise IntegrationRejected(RejectCode.MISSING_FIELD, ", ".join(missing))
    if body["kind"] != kind:
        raise IntegrationRejected(RejectCode.KIND, f"expected {kind}")
    return body


def _canonical(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise IntegrationRejected(RejectCode.WRONG_TYPE, where)
    if not CANONICAL_ID.fullmatch(value):
        raise IntegrationRejected(RejectCode.NON_CANONICAL_ID, where)
    return value


def _typed(value: Any, expected: type, where: str) -> Any:
    # bool is an int subclass; a boolean never satisfies a numeric parameter.
    if isinstance(value, bool) and expected is not bool:
        raise IntegrationRejected(RejectCode.WRONG_TYPE, where)
    if expected is float and isinstance(value, int):
        return float(value)
    if not isinstance(value, expected):
        raise IntegrationRejected(RejectCode.WRONG_TYPE, where)
    return value


def _require_caller(caller: Any) -> CallerContext:
    if not isinstance(caller, CallerContext):
        raise IntegrationRejected(RejectCode.UNAUTHENTICATED_CALLER)
    return caller


def parse_proposal(raw: bytes | str, *, caller: CallerContext,
                   registry: DestinationRegistry, limits: Limits | None = None) -> Proposal:
    """Parse a model-authored proposal under an authenticated caller context."""
    caller = _require_caller(caller)
    body = _envelope(strict_loads(raw, limits), "proposal", _PROPOSAL_FIELDS, _PROPOSAL_REQUIRED)
    request_id = _canonical(body["request_id"], "request_id")
    operation = body["operation"]
    if not isinstance(operation, str) or operation not in registry.operations:
        raise IntegrationRejected(RejectCode.OPERATION_NOT_ENUMERATED)
    spec = registry.operations[operation]
    target = _canonical(body["target"], "target")
    parameters = body.get("parameters", {})
    if not isinstance(parameters, dict):
        raise IntegrationRejected(RejectCode.WRONG_TYPE, "parameters")
    unknown = set(parameters) - set(spec.parameters)
    if unknown:
        raise IntegrationRejected(RejectCode.UNKNOWN_FIELD, "parameters")
    if spec.required - set(parameters):
        raise IntegrationRejected(RejectCode.MISSING_FIELD, "parameters")
    typed = {name: _typed(value, spec.parameters[name], f"parameters.{name}")
             for name, value in sorted(parameters.items())}
    recipient = body.get("recipient")
    if recipient is not None:
        recipient = _canonical(recipient, "recipient")
        if recipient not in registry.recipients:
            raise IntegrationRejected(RejectCode.UNRESOLVED_DESTINATION, "recipient")
    return Proposal(
        schema_version=body["schema_version"], request_id=request_id, operation=operation,
        target=target, parameters=MappingProxyType(typed), recipient=recipient,
        principal=caller.principal, tenant=caller.tenant,
        policy_version=caller.policy_version, roles=caller.roles,
    )


def parse_context_request(raw: bytes | str, *, caller: CallerContext,
                          registry: DestinationRegistry,
                          limits: Limits | None = None) -> ContextRequest:
    """Parse a model-authored context request under an authenticated caller context."""
    caller = _require_caller(caller)
    body = _envelope(strict_loads(raw, limits), "context_request", _CONTEXT_FIELDS,
                     _CONTEXT_REQUIRED)
    request_id = _canonical(body["request_id"], "request_id")
    purpose = body["purpose"]
    if not isinstance(purpose, str) or purpose not in registry.purposes:
        raise IntegrationRejected(RejectCode.PURPOSE_NOT_ENUMERATED)
    subjects, fields = body["subjects"], body["fields"]
    if not isinstance(subjects, list) or not subjects:
        raise IntegrationRejected(RejectCode.WRONG_TYPE, "subjects must be a non-empty list")
    if not isinstance(fields, list) or not fields:
        raise IntegrationRejected(RejectCode.WRONG_TYPE, "fields must be a non-empty list")
    subject_ids = tuple(_canonical(s, f"subjects[{i}]") for i, s in enumerate(subjects))
    if len(set(subject_ids)) != len(subject_ids):
        raise IntegrationRejected(RejectCode.DUPLICATE_KEY, "subjects repeat")
    for index, name in enumerate(fields):
        if not isinstance(name, str) or name not in registry.fields:
            raise IntegrationRejected(RejectCode.FIELD_NOT_ENUMERATED, f"fields[{index}]")
    if len(set(fields)) != len(fields):
        raise IntegrationRejected(RejectCode.DUPLICATE_KEY, "fields repeat")
    endpoint = _canonical(body["model_endpoint"], "model_endpoint")
    if endpoint not in registry.endpoints:
        raise IntegrationRejected(RejectCode.UNRESOLVED_DESTINATION, "model_endpoint")
    query = body.get("query", "")
    if not isinstance(query, str):
        raise IntegrationRejected(RejectCode.WRONG_TYPE, "query")
    return ContextRequest(
        schema_version=body["schema_version"], request_id=request_id, purpose=purpose,
        subjects=subject_ids, fields=tuple(fields), model_endpoint=endpoint, query=query,
        principal=caller.principal, tenant=caller.tenant,
        policy_version=caller.policy_version, roles=caller.roles,
    )


__all__ = [
    "CANONICAL_ID", "SERVER_DERIVED_FIELDS", "SUPPORTED_SCHEMA_VERSIONS", "CallerContext",
    "ContextRequest", "DestinationRegistry", "IntegrationRejected", "Limits", "OperationSpec",
    "Proposal", "RejectCode", "parse_context_request", "parse_proposal", "strict_loads",
]
