"""The MCP gate as a task contract on the wire: session, scope and exact-action approval."""
import json
import shutil
from pathlib import Path

import pytest
import yaml

from fssaira.integration.mcp_gate import (
    ApprovalStore,
    Gate,
    GateConfig,
    McpGateDenied,
    ReceiptLog,
    ToolPolicy,
    lock,
    verify_receipts,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "mcp"
PAGE = {"url": "https://news.example"}
SEND = {"to": "caseworker@example.org", "body": "status open"}


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def workdir(tmp_path):
    for name in ("hostile_server.py", "gate.yaml"):
        shutil.copy(EXAMPLE / name, tmp_path / name)
    return tmp_path


def configure(workdir, change):
    path = workdir / "gate.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["servers"]["casework"]["env"]["RUGPULL_AFTER_CALLS"] = "0"  # this suite is not about rug pulls
    change(raw)
    path.write_text(yaml.safe_dump(raw))
    return GateConfig.load(path)


def tools(raw):
    return raw["servers"]["casework"]["tools"]


def open_gate(config, clock=None):
    clock = clock or Clock()
    gate = Gate(config, lock(config, approved_by="Reviewer A", clock=clock),
                receipts=ReceiptLog(config.base / "receipts.jsonl", clock=clock), clock=clock)
    gate.start()
    return gate


def code(result):
    assert result.get("isError"), result
    return result["content"][0]["text"].split(": ", 1)[1].split(".", 1)[0]


# -- session contract -------------------------------------------------------------------


def test_a_session_ends_when_its_contract_expires(workdir):
    clock = Clock()
    config = configure(workdir, lambda raw: raw.update({"session": {"expires_after_seconds": 60}}))
    gate = open_gate(config, clock)
    try:
        assert not gate.call("casework__lookup_case", {"case_id": "C-7"}).get("isError")
        clock.now += 61
        assert code(gate.call("casework__lookup_case", {"case_id": "C-7"})) == "SESSION_EXPIRED"
    finally:
        gate.close()


def test_a_session_has_one_budget_across_all_tools(workdir):
    config = configure(workdir, lambda raw: raw.update({"session": {"max_calls": 2}}))
    gate = open_gate(config)
    try:
        gate.call("casework__lookup_case", {"case_id": "C-7"})
        gate.call("casework__fetch_page", PAGE)
        assert code(gate.call("casework__lookup_case", {"case_id": "C-8"})) == "SESSION_CALL_BUDGET_EXHAUSTED"
    finally:
        gate.close()


@pytest.mark.parametrize("session", [{"expires_after_seconds": 0}, {"expires_after_seconds": float("inf")},
                                     {"max_calls": -1}, {"max_calls": 1.5}, {"forever": True}])
def test_a_malformed_session_contract_is_refused(workdir, session):
    with pytest.raises(McpGateDenied, match="INVALID_SESSION_CONTRACT"):
        configure(workdir, lambda raw: raw.update({"session": session}))


# -- argument scope ----------------------------------------------------------------------


def test_arguments_outside_their_scope_are_refused_even_in_a_trusted_session(workdir):
    config = configure(workdir, lambda raw: tools(raw)["send_email"].update(
        {"scope": {"to": ["caseworker@example.org"]}}))
    gate = open_gate(config)
    try:
        assert not gate.call("casework__send_email", SEND).get("isError")
        assert code(gate.call("casework__send_email", {**SEND, "to": "exfil@example.net"})) == \
            "ARGUMENT_OUT_OF_SCOPE"
        assert code(gate.call("casework__send_email", {"body": "no recipient"})) == "ARGUMENT_OUT_OF_SCOPE"
    finally:
        gate.close()


@pytest.mark.parametrize("scope", [{"to": "a@example.org"}, {"to": []}, {"to": [{"any": 1}]}, ["to"]])
def test_scope_is_exact_values_only(scope):
    with pytest.raises(McpGateDenied, match="INVALID_ARGUMENT_SCOPE"):
        ToolPolicy.parse({"power": 3, "irreversibility": 2, "effects": ["external_write"], "scope": scope})


def test_widening_scope_after_the_lock_is_drift(workdir):
    config = configure(workdir, lambda raw: tools(raw)["send_email"].update(
        {"scope": {"to": ["caseworker@example.org"]}}))
    data = lock(config, approved_by="Reviewer A")
    wider = configure(workdir, lambda raw: tools(raw)["send_email"].update(
        {"scope": {"to": ["caseworker@example.org", "exfil@example.net"]}}))
    gate = Gate(wider, data, receipts=ReceiptLog(None))
    gate.start()
    try:
        assert gate.status()["hidden"]["casework/send_email"] == "POLICY_CHANGED_AFTER_APPROVAL"
    finally:
        gate.close()


# -- exact-action approval -------------------------------------------------------------------


def approval_config(workdir):
    return configure(workdir, lambda raw: (
        tools(raw)["send_email"].update({"approval": "required"}),
        raw.update({"approvals": "approvals", "approval_ttl": 300})))


def test_approval_requires_a_store(workdir):
    with pytest.raises(McpGateDenied, match="APPROVAL_STORE_REQUIRED"):
        configure(workdir, lambda raw: tools(raw)["send_email"].update({"approval": "required"}))


def test_a_held_call_runs_once_after_a_named_person_approves_it(workdir):
    clock = Clock()
    config = approval_config(workdir)
    gate = open_gate(config, clock)
    store = ApprovalStore(config.approvals, clock=clock)
    try:
        first = gate.call("casework__send_email", SEND)
        assert code(first) == "APPROVAL_REQUIRED"
        [pending] = [r for r in store.all() if r["status"] == "pending"]
        assert pending["arguments"] == SEND  # the approver sees exactly what will run
        again = gate.call("casework__send_email", SEND)  # a retry reuses the request
        assert code(again) == "APPROVAL_REQUIRED" and len(store.all()) == 1
        store.decide(pending["id"], by="Registrar B", approve=True, ttl=300)
        assert not gate.call("casework__send_email", SEND).get("isError")
        assert code(gate.call("casework__send_email", SEND)) == "APPROVAL_REQUIRED"  # single use
        used = store.get(pending["id"])
        assert used["status"] == "used" and "arguments" not in used
    finally:
        gate.close()
    allowed = [r for r in gate.receipts.records if r["event"] == "call" and r["decision"] == "allow"]
    assert allowed[-1]["approved_by"] == "Registrar B" and allowed[-1]["approval"] == pending["id"]
    assert verify_receipts(workdir / "receipts.jsonl")["verified"]


def test_an_approval_binds_the_exact_arguments(workdir):
    config = approval_config(workdir)
    gate = open_gate(config)
    store = ApprovalStore(config.approvals)
    try:
        gate.call("casework__send_email", SEND)
        store.decide(store.all()[0]["id"], by="Registrar B", approve=True)
        changed = {**SEND, "to": "someone-else@example.org"}
        assert code(gate.call("casework__send_email", changed)) == "APPROVAL_REQUIRED"
        assert len([r for r in store.all() if r["status"] == "pending"]) == 1
    finally:
        gate.close()


def test_approvals_expire_and_denials_stick(workdir):
    clock = Clock()
    config = approval_config(workdir)
    gate = open_gate(config, clock)
    store = ApprovalStore(config.approvals, clock=clock)
    try:
        gate.call("casework__send_email", SEND)
        request = store.all()[0]["id"]
        store.decide(request, by="Registrar B", approve=True, ttl=300)
        clock.now += 301
        assert code(gate.call("casework__send_email", SEND)) == "APPROVAL_REQUIRED"
        assert store.get(request)["status"] == "expired"
        fresh = [r for r in store.all() if r["status"] == "pending"][0]["id"]
        store.decide(fresh, by="Registrar B", approve=False)
        with pytest.raises(McpGateDenied, match="APPROVAL_REQUEST_NOT_PENDING"):
            store.decide(fresh, by="Registrar C", approve=True)
        with pytest.raises(McpGateDenied, match="APPROVAL_NEEDS_A_NAMED_HUMAN"):
            store.decide(fresh, by=" ", approve=True)
        with pytest.raises(McpGateDenied, match="APPROVAL_REQUEST_UNKNOWN"):
            store.get("../../etc/passwd")
    finally:
        gate.close()


def test_a_person_approving_the_exact_action_is_the_authority_a_tainted_session_lacks(workdir):
    config = approval_config(workdir)
    gate = open_gate(config)
    store = ApprovalStore(config.approvals)
    try:
        gate.call("casework__fetch_page", PAGE)
        assert gate.chain.untrusted
        assert code(gate.call("casework__send_email", SEND)) == "APPROVAL_REQUIRED"
        store.decide(store.all()[0]["id"], by="Registrar B", approve=True)
        assert not gate.call("casework__send_email", SEND).get("isError")
    finally:
        gate.close()


def test_without_an_approval_policy_a_tainted_session_still_cannot_reach_privilege(workdir):
    gate = open_gate(configure(workdir, lambda raw: None))
    try:
        gate.call("casework__fetch_page", PAGE)
        assert code(gate.call("casework__send_email", SEND)) == "UNTRUSTED_CHAIN_CANNOT_REACH_PRIVILEGED_TOOL"
    finally:
        gate.close()


def test_approval_cli_round_trip(workdir, capsys):
    from fssaira.cli import main

    config = approval_config(workdir)
    gate = open_gate(config)
    try:
        gate.call("casework__send_email", SEND)
        assert main(["mcp", "approvals", "--config", str(workdir / "gate.yaml")]) == 0
        listing = capsys.readouterr().out
        assert "casework/send_email" in listing and "caseworker@example.org" in listing
        request = json.loads(next((workdir / "approvals").glob("*.json")).read_text())["id"]
        assert main(["mcp", "approve", request, "--config", str(workdir / "gate.yaml"), "--by", "Registrar B"]) == 0
        assert not gate.call("casework__send_email", SEND).get("isError")
        assert main(["mcp", "deny", request, "--config", str(workdir / "gate.yaml"), "--by", "Registrar B"]) == 2
    finally:
        gate.close()


def test_old_lock_files_without_governance_fields_still_load(workdir):
    config = configure(workdir, lambda raw: None)
    data = lock(config, approved_by="Reviewer A")
    for server in data["servers"]:
        for tool in server["tools"]:
            for key in ("approval", "scope"):
                tool["policy"].pop(key)
    gate = Gate(config, data, receipts=ReceiptLog(None))
    gate.start()
    try:
        assert "casework/send_email" in gate.status()["tools"]
    finally:
        gate.close()


def test_the_published_authority_example_loads(tmp_path):
    for name in ("hostile_server.py", "gate.authority.yaml"):
        shutil.copy(EXAMPLE / name, tmp_path / name)
    config = GateConfig.load(tmp_path / "gate.authority.yaml")
    policy = config.server("casework").policy_for("send_email")
    assert policy.approval and policy.scope["to"] and config.session.max_calls == 50
