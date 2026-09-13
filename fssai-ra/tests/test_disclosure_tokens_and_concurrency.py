"""Grants from an institutional authorization server, races, and pilot indicators."""
import json
import time
from dataclasses import replace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from fssaira.api import create_app
from fssaira.cli import main
from fssaira.control_plane import ControlPlane
from fssaira.disclosure import DisclosureCode, DisclosureDenied, DisclosureGate
from fssaira.disclosure_concurrency import run_process_race, run_thread_race
from fssaira.disclosure_eval import AGENT, NOW, REVIEWER, SUBJECT_A, DisclosureFixture
from fssaira.disclosure_metrics import disclosure_metrics, export_records
from fssaira.disclosure_store import SqlDisclosureStore
from fssaira.disclosure_tokens import JwtGrantVerifier, TokenRejected, encode_grant_token
from fssaira.evidence import EvidenceLedger
from fssaira.profiles import ApplicationProfile
from fssaira.security import AuthConfig, Authenticator
from fssaira.sql_backend import open_sqlite

HEALTH = "profiles/healthcare_record_access.yaml"
ISSUER = "https://auth.example.test/realms/hospital"
AUDIENCE = "fssaira-disclosure-gate"


@pytest.fixture(scope="module")
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, rogue


@pytest.fixture(scope="module")
def fx():
    return DisclosureFixture(ApplicationProfile.load(HEALTH).disclosure)


def _token(key, fx, **overrides):
    spec = {"kid": "k1", "issuer": ISSUER, "audience": AUDIENCE, "holder": AGENT,
            "grant_id": "token-grant-1", "purpose": fx.purpose, "subjects": [SUBJECT_A],
            "fields": list(fx.granted_fields()), "classes": sorted(fx.classes),
            "issued_by": "data-owner", "now": time.time(), "ttl_seconds": 600}
    spec.update(overrides)
    return encode_grant_token(key, **spec)


def _verifier(keys):
    return JwtGrantVerifier(issuer=ISSUER, audience=AUDIENCE, keys={"k1": keys[0].public_key()})


def _code(action):
    with pytest.raises(DisclosureDenied) as denied:
        action()
    return denied.value.code


def test_a_grant_issued_by_the_authorization_server_authorizes_exactly_what_it_says(keys, fx):
    verifier = _verifier(keys)
    grant = verifier.grant_from_token(_token(keys[0], fx))
    gate = DisclosureGate(fx.policy, fx.records, EvidenceLedger("w"), "w", grant_keys={},
                          token_verifier=verifier)
    assert fx.read(gate, grant).values
    widened = replace(grant, subjects=grant.subjects | {"subject-B"})
    assert _code(lambda: fx.read(gate, widened, subjects=[SUBJECT_A], session_id="s2")) \
        == DisclosureCode.GRANT_SIGNATURE_INVALID
    unverified = DisclosureGate(fx.policy, fx.records, EvidenceLedger("w"), "w", grant_keys={})
    assert _code(lambda: fx.read(unverified, grant)) == DisclosureCode.GRANT_KEY_UNTRUSTED


@pytest.mark.parametrize("make", [
    lambda keys, fx: _token(keys[0], fx, audience="another-service"),
    lambda keys, fx: _token(keys[0], fx, issuer="https://evil.example.test"),
    lambda keys, fx: _token(keys[0], fx, now=time.time() - 7200, ttl_seconds=60),
    lambda keys, fx: _token(keys[1], fx),
    lambda keys, fx: jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": AGENT, "jti": "x",
                                 "iat": int(time.time()), "exp": int(time.time()) + 60},
                                "a-shared-secret-that-is-long-enough-for-hs256", algorithm="HS256",
                                headers={"kid": "k1"}),
    lambda keys, fx: jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": AGENT, "jti": "x",
                                 "iat": int(time.time()), "exp": int(time.time()) + 60},
                                keys[0], algorithm="RS256", headers={"kid": "k1"}),
], ids=["wrong-audience", "wrong-issuer", "expired", "untrusted-key", "hmac-algorithm",
        "no-disclosure-detail"])
def test_grant_tokens_are_rejected_when_anything_is_wrong(keys, fx, make):
    with pytest.raises(TokenRejected):
        _verifier(keys).grant_from_token(make(keys, fx))


def test_the_verifier_refuses_symmetric_algorithms_and_missing_keys(keys):
    with pytest.raises(ValueError, match="asymmetric"):
        JwtGrantVerifier(issuer=ISSUER, audience=AUDIENCE, keys={"k1": "secret"},
                         algorithms=("HS256",))
    with pytest.raises(ValueError, match="keys"):
        JwtGrantVerifier(issuer=ISSUER, audience=AUDIENCE)


def test_the_api_registers_token_grants_only_for_their_holder(keys, fx):
    tokens = {"t-operator": ("platform.operator", ("platform_operator",)),
              "t-holder": ("clinical-assistant", ("proposer",)),
              "t-other": ("other-agent", ("proposer",))}
    plane = ControlPlane(ApplicationProfile.load(HEALTH))
    client = TestClient(create_app(plane, authenticator=Authenticator(AuthConfig(tokens=tokens)),
                                   model_endpoint="on_premises_model",
                                   disclosure_options={"token_verifier": _verifier(keys)}))
    assert client.post("/v1/disclosure/records", headers={"Authorization": "Bearer t-operator"},
                       json={"subject": SUBJECT_A, "fields": fx.records[SUBJECT_A]}).status_code == 201
    token = _token(keys[0], fx, holder="clinical-assistant", grant_id="api-token-grant")
    assert client.post("/v1/disclosure/grants/token", headers={"Authorization": "Bearer t-other"},
                       json={"token": token}).status_code == 403
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    rejected = client.post("/v1/disclosure/grants/token",
                           headers={"Authorization": "Bearer t-holder"}, json={"token": tampered})
    assert rejected.status_code == 403 and rejected.json()["error"] == "GRANT_SIGNATURE_INVALID"
    assert client.post("/v1/disclosure/grants/token", headers={"Authorization": "Bearer t-holder"},
                       json={"token": token}).status_code == 201
    read = client.post("/v1/disclosure/context", headers={"Authorization": "Bearer t-holder"},
                       json={"grant_id": "api-token-grant", "session_id": "s", "purpose": fx.purpose,
                             "subjects": [SUBJECT_A], "fields": list(fx.granted_fields())})
    assert read.status_code == 200, read.text


# -- concurrency ----------------------------------------------------------------


def test_thread_races_on_memory_and_sql_stores_never_release_after_revocation(tmp_path, fx):
    for store in (None, SqlDisclosureStore(open_sqlite(str(tmp_path / "race.db")))):
        report = run_thread_race(fx.policy, store=store)
        assert report["holds"], report
        assert report["release"]["succeeded"] > 0
        assert report["release"]["refused_after_revocation"] > 0
        assert report["break_glass"]["opened"] == report["break_glass"]["limit"]


def test_independent_processes_share_one_store_without_violating_either_invariant():
    report = run_process_race(HEALTH, processes=4)
    assert report["holds"], report
    assert report["release"]["succeeded"] > 0
    assert report["break_glass"]["opened"] == report["break_glass"]["limit"]


# -- pilot indicators -------------------------------------------------------------


def test_pilot_indicators_come_from_evidence_and_name_what_they_cannot_measure(tmp_path, fx):
    ledger = EvidenceLedger("w")
    gate = DisclosureGate(fx.policy, fx.records, EvidenceLedger("unused"), "unused",
                          grant_keys=fx.authority.trusted_keys)
    gate._evidence, gate._token = ledger, "w"
    fx.read(gate, fx.grant())
    output = gate.derive_output(requester=AGENT, session_id="session-1", content="summary",
                                claimed_label=None)
    gate.release(output, recipient=fx.cleared_recipient, purpose=fx.purpose, now=NOW + 2)
    with pytest.raises(DisclosureDenied):
        fx.read(gate, fx.grant(), subjects=["subject-B"], session_id="s2")
    emergency = fx.break_glass_grant("bg-1")
    fx.read(gate, emergency, purpose=emergency.purpose, session_id="bg")
    gate.record_break_glass_review("bg-1", reviewer=REVIEWER,
                                   reviewer_role=fx.policy.break_glass.review_role, finding="ok")

    report = disclosure_metrics(ledger)
    assert report["evidence"]["intact"] is True
    assert report["reads"]["attempts"] == 3 and report["reads"]["released"] == 2
    assert report["reads"]["refusals_by_code"] == {"SUBJECT_OUT_OF_SCOPE": 1}
    assert report["releases"]["released"] == 1
    assert report["break_glass"] == {"opened": 1, "reviewed": 1, "awaiting_review": 0,
                                     "review_latency_seconds": report["break_glass"]["review_latency_seconds"]}
    assert report["cannot_measure"]

    exported = tmp_path / "evidence.json"
    exported.write_text(json.dumps({"records": export_records(ledger)}), encoding="utf-8")
    output_path = tmp_path / "indicators.json"
    assert main(["pilot-report", str(exported), "--output", str(output_path)]) == 0
    assert json.loads(output_path.read_text())["reads"]["attempts"] == 3
