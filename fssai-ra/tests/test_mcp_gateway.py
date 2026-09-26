"""The shared gateway: one gate per session, authenticated callers, nothing shared that should not be."""
import json
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

from fssaira.integration.mcp_gate import (
    GateConfig,
    HttpUpstream,
    McpGateDenied,
    ReceiptLog,
    UpstreamSpec,
    lock,
    verify_receipts,
)
from fssaira.integration.mcp_gateway import Gateway, GatewayPolicy, make_server, new_client_token

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "mcp"
SEND = {"to": "caseworker@example.org", "body": "status open"}


def code(result):
    assert result.get("isError"), result
    return result["content"][0]["text"].split(": ", 1)[1].split(".", 1)[0]


@pytest.fixture
def tokens():
    return {name: new_client_token() for name in ("alice", "bob", "reader")}


@pytest.fixture
def gateway(tmp_path, tokens):
    for name in ("hostile_server.py", "gate.yaml"):
        shutil.copy(EXAMPLE / name, tmp_path / name)
    path = tmp_path / "gate.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["servers"]["casework"]["env"]["RUGPULL_AFTER_CALLS"] = "0"
    raw["gateway"] = {"clients": {
        "alice": {"token_sha256": tokens["alice"][1]},
        "bob": {"token_sha256": tokens["bob"][1]},
        "reader": {"token_sha256": tokens["reader"][1], "tools": ["casework/lookup_case"]}},
        "allowed_origins": ["https://console.example.org"], "max_sessions": 4}
    path.write_text(yaml.safe_dump(raw))
    config = GateConfig.load(path)
    gw = Gateway(config, lock(config, approved_by="Reviewer A"), GatewayPolicy.load(path),
                 receipts=ReceiptLog(tmp_path / "receipts.jsonl"))
    server = make_server(gw, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    gw.url = f"http://127.0.0.1:{server.server_address[1]}/mcp"
    gw.tmp = tmp_path
    yield gw
    server.shutdown()
    server.server_close()
    gw.close()


def connect(gw, token, monkeypatch, var):
    monkeypatch.setenv(var, f"Bearer {token}")
    client = HttpUpstream(UpstreamSpec(name="host", command=(), operator="test", url=gw.url,
                                       headers={"Authorization": f"env:{var}"}), timeout=20)
    client.initialize()
    return client


def raw_post(gw, body, headers):
    request = urllib.request.Request(gw.url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}


def test_each_session_has_its_own_gate_so_one_callers_taint_is_not_anothers(gateway, tokens, monkeypatch):
    alice = connect(gateway, tokens["alice"][0], monkeypatch, "ALICE")
    bob = connect(gateway, tokens["bob"][0], monkeypatch, "BOB")
    try:
        names = [t["name"] for t in alice.list_tools()]
        assert "casework__send_email" in names and "casework__format_notes" not in names
        alice.call_tool("casework__fetch_page", {"url": "https://news.example"})
        assert code(alice.call_tool("casework__send_email", SEND)) == \
            "UNTRUSTED_CHAIN_CANNOT_REACH_PRIVILEGED_TOOL"
        assert not bob.call_tool("casework__send_email", SEND).get("isError")  # bob read nothing hostile
    finally:
        alice.close()
        bob.close()
    records = [json.loads(line) for line in (gateway.tmp / "receipts.jsonl").read_text().splitlines()]
    callers = {r.get("caller") for r in records if r["event"] == "call"}
    assert callers == {"alice", "bob"} and all(r.get("session") for r in records if r["event"] == "call")
    assert verify_receipts(gateway.tmp / "receipts.jsonl")["verified"]


def test_a_caller_can_be_narrowed_to_named_tools(gateway, tokens, monkeypatch):
    reader = connect(gateway, tokens["reader"][0], monkeypatch, "READER")
    try:
        assert [t["name"] for t in reader.list_tools()] == ["casework__lookup_case"]
        assert code(reader.call_tool("casework__send_email", SEND)) == "CALLER_NOT_PERMITTED"
        assert not reader.call_tool("casework__lookup_case", {"case_id": "C-7"}).get("isError")
    finally:
        reader.close()


def test_callers_must_authenticate(gateway, tokens):
    assert raw_post(gateway, INIT, {})[0] == 401
    assert raw_post(gateway, INIT, {"Authorization": "Bearer not-a-token"})[0] == 401
    status, body = raw_post(gateway, INIT, {"Authorization": f"Bearer {tokens['alice'][0]}"})
    assert status == 200 and body["result"]["serverInfo"]["name"] == "fssaira-mcp-gate"


def test_a_session_belongs_to_the_caller_that_opened_it(gateway, tokens, monkeypatch):
    alice = connect(gateway, tokens["alice"][0], monkeypatch, "ALICE")
    try:
        stolen = alice._session
        status, body = raw_post(gateway, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                                {"Authorization": f"Bearer {tokens['bob'][0]}", "Mcp-Session-Id": stolen})
        assert status == 404 and body["error"]["message"] == "GATEWAY_SESSION_UNKNOWN"
    finally:
        alice.close()


def test_foreign_origins_are_refused(gateway, tokens):
    auth = {"Authorization": f"Bearer {tokens['alice'][0]}"}
    assert raw_post(gateway, INIT, {**auth, "Origin": "https://evil.example"})[0] == 403
    assert raw_post(gateway, INIT, {**auth, "Origin": "https://console.example.org"})[0] == 200


def test_sessions_are_capped_and_closed_sessions_are_gone(gateway, tokens, monkeypatch):
    clients = [connect(gateway, tokens["alice"][0], monkeypatch, "ALICE") for _ in range(4)]
    status, body = raw_post(gateway, INIT, {"Authorization": f"Bearer {tokens['bob'][0]}"})
    assert status == 503 and body["error"]["message"] == "GATEWAY_AT_CAPACITY"
    ended = clients[0]._session
    for client in clients:
        client.close()
    assert gateway.sessions == {}
    status, _ = raw_post(gateway, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
                         {"Authorization": f"Bearer {tokens['alice'][0]}", "Mcp-Session-Id": ended})
    assert status == 404


def test_an_unauthenticated_gateway_may_only_listen_on_loopback(tmp_path):
    for name in ("hostile_server.py", "gate.yaml"):
        shutil.copy(EXAMPLE / name, tmp_path / name)
    config = GateConfig.load(tmp_path / "gate.yaml")
    gw = Gateway(config, lock(config, approved_by="Reviewer A"), GatewayPolicy(),
                 receipts=ReceiptLog(None))
    with pytest.raises(McpGateDenied, match="GATEWAY_NEEDS_CLIENT_AUTH"):
        make_server(gw, "0.0.0.0", 0)  # noqa: S104 - the refusal is the point
    server = make_server(gw, "127.0.0.1", 0)
    server.server_close()


@pytest.mark.parametrize("gateway_raw", [
    {"clients": {"x": {"token_sha256": "short"}}},
    {"clients": {"x": {"token_sha256": "a" * 64, "tools": ["bare_name"]}}},
    {"max_sessions": 0},
    ["not", "a", "mapping"],
])
def test_malformed_gateway_policy_is_refused(gateway_raw):
    with pytest.raises(McpGateDenied, match="GATEWAY_CLIENT_INVALID"):
        GatewayPolicy.parse(gateway_raw)


def test_the_policy_stores_digests_never_tokens(tokens):
    token, digest = tokens["alice"]
    policy = GatewayPolicy.parse({"clients": {"alice": {"token_sha256": digest}}})
    assert token not in json.dumps([c.token_sha256 for c in policy.clients])
    assert policy.authenticate(f"Bearer {token}").name == "alice"
