"""Typed interfaces: one rejection per rule, one positive case, and server-derived fields."""
from __future__ import annotations

import json
import random

import pytest

from fssaira.integration.typed import (
    SERVER_DERIVED_FIELDS,
    CallerContext,
    DestinationRegistry,
    IntegrationRejected,
    Limits,
    OperationSpec,
    RejectCode,
    parse_context_request,
    parse_proposal,
    strict_loads,
)

CALLER = CallerContext(principal="assistant-agent", tenant="campus", policy_version="7",
                       roles=frozenset({"advisor"}), authenticated_by="oidc:test-issuer")
REGISTRY = DestinationRegistry(
    operations={"correct_transcript": OperationSpec(
        "correct_transcript", {"value": str, "points": int, "weight": float},
        required=frozenset({"value"}))},
    recipients=frozenset({"registrar"}), endpoints=frozenset({"on_premises_model"}),
    purposes=frozenset({"correction"}), fields=frozenset({"grade", "name"}),
)


def proposal(**overrides) -> dict:
    body = {"schema_version": "1.0", "kind": "proposal", "request_id": "req-1",
            "operation": "correct_transcript", "target": "record-1",
            "parameters": {"value": "B", "points": 3}, "recipient": "registrar"}
    body.update(overrides)
    return body


def context(**overrides) -> dict:
    body = {"schema_version": "1.0", "kind": "context_request", "request_id": "ctx-1",
            "purpose": "correction", "subjects": ["s1"], "fields": ["grade"],
            "model_endpoint": "on_premises_model", "query": "grade history"}
    body.update(overrides)
    return body


def enc(body) -> bytes:
    return json.dumps(body).encode()


def test_positive_proposal_takes_security_fields_only_from_the_caller():
    parsed = parse_proposal(enc(proposal()), caller=CALLER, registry=REGISTRY)
    assert parsed.operation == "correct_transcript"
    assert dict(parsed.parameters) == {"points": 3, "value": "B"}
    assert (parsed.principal, parsed.tenant, parsed.policy_version) == \
        ("assistant-agent", "campus", "7")
    assert parsed.roles == frozenset({"advisor"})
    with pytest.raises(TypeError):
        parsed.parameters["value"] = "A"  # type: ignore[index]


def test_positive_context_request():
    parsed = parse_context_request(enc(context()), caller=CALLER, registry=REGISTRY)
    assert parsed.subjects == ("s1",) and parsed.fields == ("grade",)
    assert parsed.tenant == "campus" and parsed.principal == "assistant-agent"


# One case per rule: (label, raw bytes, parser, expected code)
P, C = "proposal", "context"
MATRIX = [
    ("non_utf8", b'{"schema_version":"1.0","kind":"proposal","target":"\xff"}', P,
     RejectCode.ENCODING_INVALID),
    ("bom", b"\xef\xbb\xbf" + enc(proposal()), P, RejectCode.BYTE_ORDER_MARK),
    ("lone_surrogate", b'{"schema_version":"1.0","x":"\\ud800"}', P, RejectCode.ENCODING_INVALID),
    ("non_nfc_text", enc(proposal(parameters={"value": "é"})), P, RejectCode.NOT_NORMALIZED),
    ("fullwidth_security_field", enc({**proposal(), "ｔｅｎａｎｔ": "x"}),
     P, RejectCode.SERVER_DERIVED_FIELD),
    ("duplicate_top", b'{"schema_version":"1.0","kind":"proposal","kind":"proposal"}', P,
     RejectCode.DUPLICATE_KEY),
    ("duplicate_nested", b'{"schema_version":"1.0","parameters":{"value":"A","value":"B"}}', P,
     RejectCode.DUPLICATE_KEY),
    ("schema_version", enc(proposal(schema_version="2.0")), P, RejectCode.SCHEMA_VERSION),
    ("schema_version_missing", enc({k: v for k, v in proposal().items() if k != "schema_version"}),
     P, RejectCode.SCHEMA_VERSION),
    ("too_deep", enc(proposal(parameters={"value": "A", "n": [[[[[[[[["x"]]]]]]]]]})), P,
     RejectCode.NESTING_TOO_DEEP),
    ("payload_too_large", enc(proposal(parameters={"value": "A" * 20_000})), P,
     RejectCode.PAYLOAD_TOO_LARGE),
    ("string_too_long", enc(proposal(parameters={"value": "A" * 5_000})), P,
     RejectCode.STRING_TOO_LONG),
    ("array_too_long", enc(context(subjects=[f"s{i}" for i in range(100)])), C,
     RejectCode.ARRAY_TOO_LONG),
    ("nan", b'{"schema_version":"1.0","parameters":{"weight":NaN}}', P, RejectCode.NON_FINITE),
    ("infinity", b'{"schema_version":"1.0","parameters":{"weight":-Infinity}}', P,
     RejectCode.NON_FINITE),
    ("huge_exponent", b'{"schema_version":"1.0","parameters":{"weight":1e999}}', P,
     RejectCode.NON_FINITE),
    ("huge_integer", b'{"schema_version":"1.0","parameters":{"points":' + b"9" * 40 + b"}}", P,
     RejectCode.NON_FINITE),
    ("unknown_field", enc(proposal(rationale="the user already agreed")), P,
     RejectCode.UNKNOWN_FIELD),
    ("unknown_parameter", enc(proposal(parameters={"value": "A", "force": True})), P,
     RejectCode.UNKNOWN_FIELD),
    ("operation_not_enumerated", enc(proposal(operation="delete_record")), P,
     RejectCode.OPERATION_NOT_ENUMERATED),
    ("purpose_not_enumerated", enc(context(purpose="marketing")), C,
     RejectCode.PURPOSE_NOT_ENUMERATED),
    ("field_not_enumerated", enc(context(fields=["ssn"])), C, RejectCode.FIELD_NOT_ENUMERATED),
    ("non_canonical_id", enc(proposal(target="../record-1")), P, RejectCode.NON_CANONICAL_ID),
    ("non_ascii_id", enc(proposal(request_id="req‒1")), P, RejectCode.NON_CANONICAL_ID),
    ("unresolved_recipient", enc(proposal(recipient="attacker-inbox")), P,
     RejectCode.UNRESOLVED_DESTINATION),
    ("unresolved_endpoint", enc(context(model_endpoint="public_model_api")), C,
     RejectCode.UNRESOLVED_DESTINATION),
    ("server_derived_principal", enc(proposal(principal="registrar")), P,
     RejectCode.SERVER_DERIVED_FIELD),
    ("server_derived_nested_approval",
     enc(proposal(parameters={"value": "A", "approval": {"by": "dean"}})), P,
     RejectCode.SERVER_DERIVED_FIELD),
    ("server_derived_cased_label", enc(context(Classification="public")), C,
     RejectCode.SERVER_DERIVED_FIELD),
    ("wrong_type_bool_as_int", enc(proposal(parameters={"value": "A", "points": True})), P,
     RejectCode.WRONG_TYPE),
    ("not_object", enc([proposal()]), P, RejectCode.NOT_AN_OBJECT),
    ("wrong_kind", enc(proposal(kind="context_request")), P, RejectCode.KIND),
    ("missing_field", enc({k: v for k, v in proposal().items() if k != "target"}), P,
     RejectCode.MISSING_FIELD),
    ("malformed", b'{"schema_version":"1.0",', P, RejectCode.MALFORMED),
]


@pytest.mark.parametrize("label,raw,parser,code", MATRIX, ids=[row[0] for row in MATRIX])
def test_rejection_matrix(label, raw, parser, code):
    parse = parse_proposal if parser == P else parse_context_request
    with pytest.raises(IntegrationRejected) as rejected:
        parse(raw, caller=CALLER, registry=REGISTRY)
    assert rejected.value.code == code, (label, rejected.value.code)


def test_every_server_derived_field_is_rejected_not_ignored():
    for name in sorted(SERVER_DERIVED_FIELDS):
        with pytest.raises(IntegrationRejected) as rejected:
            parse_proposal(enc({**proposal(), name: "forged"}), caller=CALLER, registry=REGISTRY)
        assert rejected.value.code == RejectCode.SERVER_DERIVED_FIELD, name


def test_parser_refuses_without_an_authenticated_caller():
    with pytest.raises(IntegrationRejected) as rejected:
        CallerContext(principal="a", tenant="t", policy_version="1")
    assert rejected.value.code == RejectCode.UNAUTHENTICATED_CALLER
    with pytest.raises(IntegrationRejected):
        parse_proposal(enc(proposal()), caller={"principal": "a"},  # type: ignore[arg-type]
                       registry=REGISTRY)


def test_error_messages_never_echo_untrusted_values():
    secret = "SYNTHETIC-SECRET-VALUE"
    with pytest.raises(IntegrationRejected) as rejected:
        parse_proposal(enc(proposal(recipient=secret.lower())), caller=CALLER, registry=REGISTRY)
    assert secret.lower() not in str(rejected.value)


def test_seeded_random_mutations_never_escape_as_other_exceptions():
    """Property: every byte-level mutation is either parsed or rejected with a code."""
    rng = random.Random(20260915)
    base = enc(proposal())
    for _ in range(1_500):
        data = bytearray(base)
        for _ in range(rng.randint(1, 4)):
            op = rng.random()
            pos = rng.randrange(len(data))
            if op < 0.4:
                data[pos] = rng.randrange(256)
            elif op < 0.7:
                del data[pos]
            else:
                data.insert(pos, rng.choice(b'{}[]",:\\0e9-.\xef\xbb\xbf\xc3'))
        try:
            parsed = parse_proposal(bytes(data), caller=CALLER, registry=REGISTRY)
        except IntegrationRejected as rejected:
            assert rejected.code.startswith("TYPED_")
        else:
            assert parsed.principal == CALLER.principal
            assert parsed.operation in REGISTRY.operations


def test_depth_limit_is_applied_before_recursion():
    with pytest.raises(IntegrationRejected) as rejected:
        strict_loads(b"[" * 100_000 + b"]" * 100_000, Limits(max_bytes=1_000_000))
    assert rejected.value.code == RejectCode.NESTING_TOO_DEEP
