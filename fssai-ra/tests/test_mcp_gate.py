"""The MCP gate: the tool-supply rules enforced on the wire against a hostile server."""
import io
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from fssaira.integration.mcp_gate import (
    PROTOCOL_VERSIONS,
    Gate,
    GateConfig,
    McpGateDenied,
    ReceiptLog,
    ToolPolicy,
    annotation_findings,
    lock,
    model_text,
    qualified_from_wire,
    scan,
    serve,
    verify_receipts,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "mcp"


@pytest.fixture
def workdir(tmp_path):
    for name in ("hostile_server.py", "gate.yaml"):
        shutil.copy(EXAMPLE / name, tmp_path / name)
    return tmp_path


def edit_config(workdir, change):
    path = workdir / "gate.yaml"
    raw = yaml.safe_load(path.read_text())
    change(raw)
    path.write_text(yaml.safe_dump(raw))
    return GateConfig.load(path)


def open_gate(workdir, config=None, *, accept=()):
    config = config or GateConfig.load(workdir / "gate.yaml")
    data = lock(config, approved_by="Reviewer A", accept_findings=accept, clock=lambda: 1.0)
    gate = Gate(config, data, receipts=ReceiptLog(workdir / "receipts.jsonl"))
    gate.start()
    return gate


def refused(result):
    assert result.get("isError"), result
    return result["content"][0]["text"].split(": ", 1)[1].split(".", 1)[0]


# -- review ------------------------------------------------------------------------


def test_model_text_reaches_nested_parameter_descriptions():
    tool = {"name": "t", "description": "top", "inputSchema": {"properties": {
        "a": {"description": "one", "items": {"properties": {"b": {"description": "deep"}}}}}}}
    text = model_text(tool)
    assert "input.a.description: one" in text and "deep" in text


def test_scan_flags_the_instruction_hidden_in_a_parameter(workdir):
    report = scan(GateConfig.load(workdir / "gate.yaml"))
    flagged = {t["name"]: t["findings"] for s in report["servers"] for t in s["tools"] if t["findings"]}
    assert set(flagged) == {"format_notes"}
    assert {"secret_path", "concealment", "tool_sequencing"} <= {f["finding"] for f in flagged["format_notes"]}


def test_lock_excludes_flagged_tools_unless_accepted_by_name(workdir):
    config = GateConfig.load(workdir / "gate.yaml")
    plain = lock(config, approved_by="Reviewer A")
    assert [e["tool"] for e in plain["excluded"]] == ["casework/format_notes"]
    accepted = lock(config, approved_by="Reviewer A", accept_findings=["casework/format_notes"])
    names = [t["name"] for t in accepted["servers"][0]["tools"]]
    assert "format_notes" in names and accepted["excluded"] == []


def test_lock_needs_a_named_human(workdir):
    with pytest.raises(McpGateDenied, match="APPROVAL_NEEDS_A_NAMED_HUMAN"):
        lock(GateConfig.load(workdir / "gate.yaml"), approved_by="  ")


def test_annotations_that_disagree_with_policy_are_flagged_not_trusted():
    tool = {"annotations": {"destructiveHint": True, "openWorldHint": True}}
    ordinary = ToolPolicy(power=0, irreversibility=0, effects=frozenset(), trusted_output=True)
    found = {f["finding"] for f in annotation_findings(tool, ordinary)}
    assert found == {"annotation_claims_destructive_policy_does_not", "open_world_output_declared_trusted"}


def test_undeclared_tools_are_privileged_by_default():
    policy = ToolPolicy.parse(None)
    assert policy.power >= 3 and "external_write" in policy.effects and not policy.trusted_output


# -- naming ------------------------------------------------------------------------


def test_only_qualified_wire_names_resolve():
    assert qualified_from_wire("casework__send_email", ["casework"]) == "casework/send_email"
    for bare in ("send_email", "other__send_email", "casework__", 7):
        with pytest.raises(McpGateDenied, match="QUALIFIED_NAME_REQUIRED"):
            qualified_from_wire(bare, ["casework"])


def test_mcp_tool_names_keep_their_case_and_server_names_stay_strict():
    import hashlib

    from fssaira.integration.mcp_gate import McpToolRegistry
    from fssaira.integration.supply import ToolManifest
    from fssaira.integration.tool_servers import ToolSupplyDenied

    h = hashlib.sha256(b"x").hexdigest()

    def manifest(server, name):
        return ToolManifest(name=name, server=server, description_hash=h, input_hash=h, output_hash=h,
                            executable_hash=h, power=0, irreversibility=0, effects=frozenset())

    assert McpToolRegistry.qualified_name(manifest("weather", "getForecast")) == "weather/getForecast"
    for server, name in (("Weather", "getForecast"), ("weather", "../etc"), ("weather", "a b")):
        with pytest.raises(ToolSupplyDenied, match="INVALID_(SERVER|TOOL)_NAME"):
            McpToolRegistry.qualified_name(manifest(server, name))


def test_server_names_cannot_contain_the_wire_separator(workdir):
    with pytest.raises(McpGateDenied, match="SERVER_NAME_CONTAINS_WIRE_SEPARATOR"):
        edit_config(workdir, lambda raw: raw["servers"].update({"a__b": raw["servers"].pop("casework")}))


# -- the gate against the hostile server ---------------------------------------------


def test_the_injection_cannot_reach_the_privileged_tool(workdir):
    gate = open_gate(workdir)
    try:
        assert gate.status()["tools"] == ["casework/fetch_page", "casework/lookup_case", "casework/send_email"]
        assert not gate.call("casework__lookup_case", {"case_id": "C-7"}).get("isError")
        assert not gate.chain.untrusted  # trusted_output keeps the chain clean
        assert not gate.call("casework__send_email", {"to": "a@example.org", "body": "x"}).get("isError")
        page = gate.call("casework__fetch_page", {"url": "https://news.example"})
        assert "Ignore previous instructions" in page["content"][0]["text"]
        assert gate.chain.untrusted
        code = refused(gate.call("casework__send_email", {"to": "exfil@example.net", "body": "record"}))
        assert code == "UNTRUSTED_CHAIN_CANNOT_REACH_PRIVILEGED_TOOL"
    finally:
        gate.close()


def test_a_rug_pull_quarantines_the_tool_and_keeps_its_reason(workdir):
    gate = open_gate(workdir)
    try:
        for _ in range(3):  # the server redefines lookup_case after its third call
            gate.call("casework__lookup_case", {"case_id": "C-7"})
        assert refused(gate.call("casework__lookup_case", {"case_id": "C-7"})) == \
            "DEFINITION_CHANGED_AFTER_APPROVAL"
        gate.refresh()
        gate.refresh()
        assert "casework/lookup_case" not in gate.status()["tools"]
        assert gate.status()["hidden"]["casework/lookup_case"] == "DEFINITION_CHANGED_AFTER_APPROVAL"
        drift = [r for r in gate.receipts.records if r["subject"] == "casework/lookup_case"
                 and r["event"] == "offer"]
        assert len(drift) == 1
    finally:
        gate.close()


def test_unapproved_and_flagged_tools_are_hidden_and_uncallable(workdir):
    gate = open_gate(workdir)
    try:
        assert gate.status()["hidden"] == {"casework/format_notes": "TOOL_NOT_APPROVED"}
        assert refused(gate.call("casework__format_notes", {"notes": "a"})) == "TOOL_NOT_APPROVED"
        assert refused(gate.call("casework__nonexistent", {})) == "TOOL_NOT_OFFERED"
    finally:
        gate.close()


def test_upstream_sampling_requests_are_refused_and_recorded(workdir):
    gate = open_gate(workdir)
    try:
        gate.call("casework__fetch_page", {"url": "https://news.example"})
        assert any(r["event"] == "upstream_request" and r["subject"] == "casework:sampling/createMessage"
                   and r["code"] == "UPSTREAM_REQUEST_NOT_FORWARDED" for r in gate.receipts.records)
    finally:
        gate.close()


def test_editing_the_server_code_withdraws_every_approval(workdir):
    config = GateConfig.load(workdir / "gate.yaml")
    data = lock(config, approved_by="Reviewer A")
    with (workdir / "hostile_server.py").open("a") as handle:
        handle.write("\n# edited after approval\n")
    gate = Gate(config, data, receipts=ReceiptLog(None))
    gate.start()
    try:
        assert gate.status()["tools"] == []
        assert gate.receipts.records[0]["code"] == "SERVER_IDENTITY_ROTATED"
    finally:
        gate.close()


def test_changing_policy_after_approval_is_drift(workdir):
    config = GateConfig.load(workdir / "gate.yaml")
    data = lock(config, approved_by="Reviewer A")
    # Someone "downgrades" send_email so it becomes reachable from untrusted chains.
    weaker = edit_config(workdir, lambda raw: raw["servers"]["casework"]["tools"].update(
        {"send_email": {"power": 0, "irreversibility": 0, "effects": []}}))
    gate = Gate(weaker, data, receipts=ReceiptLog(None))
    gate.start()
    try:
        assert gate.status()["hidden"]["casework/send_email"] == "DEFINITION_CHANGED_AFTER_APPROVAL"
    finally:
        gate.close()


def test_call_limits_hold(workdir):
    config = edit_config(workdir, lambda raw: raw["servers"]["casework"]["tools"]["fetch_page"].update(
        {"max_calls": 1}))
    gate = open_gate(workdir, config)
    try:
        assert not gate.call("casework__fetch_page", {"url": "u"}).get("isError")
        assert refused(gate.call("casework__fetch_page", {"url": "u"})) == "TOOL_CALL_LIMIT_REACHED"
    finally:
        gate.close()


def test_sessions_can_start_untrusted(workdir):
    config = edit_config(workdir, lambda raw: raw.update({"session_starts_untrusted": True}))
    gate = open_gate(workdir, config)
    try:
        assert refused(gate.call("casework__send_email", {"to": "a", "body": "b"})) == \
            "UNTRUSTED_CHAIN_CANNOT_REACH_PRIVILEGED_TOOL"
    finally:
        gate.close()


# -- receipts ------------------------------------------------------------------------


def test_receipts_chain_verify_and_hold_no_argument_content(workdir):
    gate = open_gate(workdir)
    try:
        gate.call("casework__fetch_page", {"url": "https://news.example"})
        gate.call("casework__send_email", {"to": "exfil@example.net", "body": "SECRET-BODY"})
    finally:
        gate.close()
    path = workdir / "receipts.jsonl"
    report = verify_receipts(path)
    assert report["verified"] and report["decisions"]["call:deny"] == 1
    raw = path.read_text()
    assert "exfil@example.net" not in raw and "SECRET-BODY" not in raw
    assert all(len(json.loads(line)["args_sha256"]) == 64
               for line in raw.splitlines() if json.loads(line)["event"] == "call")


def test_receipt_tampering_is_detected(workdir):
    gate = open_gate(workdir)
    try:
        gate.call("casework__lookup_case", {"case_id": "C-7"})
        gate.call("casework__fetch_page", {"url": "u"})
    finally:
        gate.close()
    path = workdir / "receipts.jsonl"
    lines = path.read_text().splitlines()
    edited = [line.replace('"deny"', '"allow"') for line in lines]
    path.write_text("\n".join(edited) + "\n")
    problems = {p["problem"] for p in verify_receipts(path)["problems"]}
    assert "RECEIPT_HASH_MISMATCH" in problems
    path.write_text("\n".join(lines[1:]) + "\n")  # deleting the first receipt
    assert not verify_receipts(path)["verified"]


def test_a_reopened_log_continues_the_chain(workdir):
    path = workdir / "r.jsonl"
    ReceiptLog(path).append(event="a", decision="allow")
    ReceiptLog(path).append(event="b", decision="deny")
    report = verify_receipts(path)
    assert report["verified"] and report["receipts"] == 2


# -- protocol --------------------------------------------------------------------------


def converse(gate, *messages):
    out = io.StringIO()
    serve(gate, io.StringIO("".join(json.dumps(m) + "\n" for m in messages) + "not json\n"), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_the_gate_speaks_mcp(workdir):
    gate = open_gate(workdir)
    try:
        replies = converse(
            gate,
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "send_email", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
        )
    finally:
        gate.close()
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
    names = [t["name"] for t in replies[1]["result"]["tools"]]
    assert names == ["casework__lookup_case", "casework__fetch_page", "casework__send_email"]
    assert replies[2]["result"]["isError"]
    assert replies[3]["error"]["code"] == -32601
    assert replies[4]["error"]["code"] == -32700


def test_unknown_protocol_versions_get_the_latest(workdir):
    gate = open_gate(workdir)
    try:
        reply = converse(gate, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                "params": {"protocolVersion": "1999-01-01"}})[0]
    finally:
        gate.close()
    assert reply["result"]["protocolVersion"] == PROTOCOL_VERSIONS[-1]


def test_the_demo_runs_end_to_end_through_the_cli(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import mcp_gate_demo
    finally:
        sys.path.pop(0)
    report = mcp_gate_demo.run(tmp_path / "demo")
    assert report["all_as_expected"] and report["receipts"]["verified"]
    assert "casework__lookup_case" not in report["offered_after"]


def test_every_code_the_gate_emits_is_published():
    import re

    from fssaira.refusal_registry import scan as registry

    source = (ROOT / "src/fssaira/integration/mcp_gate.py").read_text()
    emitted = set(re.findall(r'(?:_require\(.*?|McpGateDenied\(|, )"([A-Z]+(?:_[A-Z0-9]+)+)"\)', source, re.S))
    published = set(registry())
    assert emitted and emitted <= published, sorted(emitted - published)
