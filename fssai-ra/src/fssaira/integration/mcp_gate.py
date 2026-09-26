"""A Trust by Construction gate for the Model Context Protocol.

:mod:`fssaira.integration.tool_servers` states the rules for third-party tool
servers: namespaced names, pinned definitions, named approvals, and no path
from untrusted content to privileged capability. This module puts those rules
on the wire. The gate is an MCP server to the agent and an MCP client to every
upstream server, so it can be dropped in front of any MCP host (an IDE, a
desktop assistant, an agent framework) without changing the host or the
servers. The host sees one server; the upstream servers never see the host.

Three commands make up the workflow:

``scan``
    Connect to the declared servers, list their tools, and report every piece
    of model-visible text that reads like an instruction. Nothing is approved.
``lock``
    A named human approves the listing they reviewed. The lock file records the
    exact text, schemas and launch identity of every approved tool, so review
    diffs are readable and approval is bound to bytes, not to names.
``serve``
    Run the gate. Every listing is re-offered against the lock, so a redefined
    tool (a rug pull) is quarantined rather than shown. Every call is checked
    against the session's call chain, so a session that has read untrusted
    output cannot reach a privileged tool. Every decision is appended to a
    hash-chained receipt log that records digests, never argument content.

Beyond tool hygiene, the gate enforces a task contract on the wire (P2, P7):

* a **session contract** -- an expiry and a total call budget for the session;
* **argument scope** -- per tool, exact-match allow-lists for named arguments,
  so an agent that may email two recipients cannot email a third, however it
  is asked;
* **exact-action approval** -- for a tool marked ``approval: required`` the
  gate holds the call, records a request carrying the exact arguments, and
  runs it only after a named person approves that request. The approval is
  bound to the argument digest, single-use and expiring, so a changed
  argument needs a new approval. A human approval of the exact action is also
  the one thing that lets a session that has read untrusted content reach a
  privileged tool: the person, not the page, is the authority.

What the gate decides is taken from the deployment's policy file, never from
the server. MCP tool annotations such as ``readOnlyHint`` are claims made by
the party being governed; the gate hashes them, shows them to the reviewer,
flags disagreement with policy, and grants nothing on their basis. A tool the
policy does not describe is treated as privileged.

Upstream servers may not send requests to the host through the gate.
``sampling/createMessage`` would let a tool server write into the model's
context and ``elicitation/create`` would let it question the user directly;
both are refused with ``UPSTREAM_REQUEST_NOT_FORWARDED``.

This is enforcement at the protocol boundary over declared identity. It does
not attest what a server's code does when called, and it cannot see content
that reaches the model by any path other than this gate (a pasted document, a
browser tab). A deployment that has such paths should start sessions untrusted
(``session_starts_untrusted: true``).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import IO, Any

from .supply import ToolManifest
from .tool_servers import (
    CallChain,
    ToolRegistry,
    ToolServer,
    ToolSupplyDenied,
    scan_description,
)

#: Protocol revisions this gate can speak. The gate answers with the client's
#: requested revision when it knows it, and with the newest one otherwise.
PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
LATEST_PROTOCOL = PROTOCOL_VERSIONS[-1]
GATE_NAME = "fssaira-mcp-gate"
LOCK_SCHEMA = "fssaira.mcp-lock/1"
RECEIPT_SCHEMA = "fssaira.mcp-receipt/1"
GENESIS = "0" * 64

#: Separates server and tool in the name the host sees. MCP hosts commonly
#: restrict tool names to ``[A-Za-z0-9_-]``, so ``server/tool`` cannot be used
#: on the wire; the gate maps ``server__tool`` back to ``server/tool`` exactly
#: and never resolves a bare tool name.
WIRE_SEPARATOR = "__"

#: Applied to any tool the policy file does not describe: privileged, so an
#: undeclared tool is unreachable from an untrusted chain.
UNDECLARED_POLICY = {"power": 3, "irreversibility": 2, "effects": ("external_write",),
                     "trusted_output": False}

#: Upstream-initiated requests the gate refuses to forward to the host.
UPSTREAM_REQUESTS_REFUSED = ("sampling/createMessage", "elicitation/create", "roots/list")


class McpGateDenied(ToolSupplyDenied):
    """A stable reason code for a refused gate configuration, listing or call."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise McpGateDenied(code)


class McpGateCodes:
    """Every reason the gate gives, beyond those the core tool registry raises.

    Declared here so the published refusal registry lists the gate's whole
    vocabulary; an auditor searching receipts can find each one.
    """

    # configuration and lock
    GATE_CONFIG_NEEDS_SERVERS = "GATE_CONFIG_NEEDS_SERVERS"
    INVALID_SERVER_ENTRY = "INVALID_SERVER_ENTRY"
    SERVER_COMMAND_REQUIRED = "SERVER_COMMAND_REQUIRED"
    SERVER_NAME_CONTAINS_WIRE_SEPARATOR = "SERVER_NAME_CONTAINS_WIRE_SEPARATOR"
    TRUSTED_SOURCE_MUST_BE_QUALIFIED = "TRUSTED_SOURCE_MUST_BE_QUALIFIED"
    UNKNOWN_TOOL_POLICY_FIELD = "UNKNOWN_TOOL_POLICY_FIELD"
    INVALID_TOOL_CALL_LIMIT = "INVALID_TOOL_CALL_LIMIT"
    PINNED_FILE_MISSING = "PINNED_FILE_MISSING"
    UNSUPPORTED_LOCK_FILE = "UNSUPPORTED_LOCK_FILE"
    # servers
    SERVER_NOT_LOCKED = "SERVER_NOT_LOCKED"
    SERVER_IDENTITY_ROTATED = "SERVER_IDENTITY_ROTATED"
    UPSTREAM_REQUEST_NOT_FORWARDED = "UPSTREAM_REQUEST_NOT_FORWARDED"
    UPSTREAM_URL_MUST_BE_HTTPS = "UPSTREAM_URL_MUST_BE_HTTPS"
    UPSTREAM_REDIRECT_REFUSED = "UPSTREAM_REDIRECT_REFUSED"
    UPSTREAM_HEADER_ENV_MISSING = "UPSTREAM_HEADER_ENV_MISSING"
    SERVER_NEEDS_COMMAND_OR_URL = "SERVER_NEEDS_COMMAND_OR_URL"
    NOTIFY_FAILED = "NOTIFY_FAILED"
    APPROVAL_ALREADY_USED = "APPROVAL_ALREADY_USED"
    CALLER_NOT_PERMITTED = "CALLER_NOT_PERMITTED"
    UPSTREAM_RESPONSE_TOO_LARGE = "UPSTREAM_RESPONSE_TOO_LARGE"
    # calls
    ARGUMENTS_MUST_BE_AN_OBJECT = "ARGUMENTS_MUST_BE_AN_OBJECT"
    ARGUMENT_OUT_OF_SCOPE = "ARGUMENT_OUT_OF_SCOPE"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_CALL_BUDGET_EXHAUSTED = "SESSION_CALL_BUDGET_EXHAUSTED"
    POLICY_CHANGED_AFTER_APPROVAL = "POLICY_CHANGED_AFTER_APPROVAL"
    # exact-action approval
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_STORE_REQUIRED = "APPROVAL_STORE_REQUIRED"
    APPROVAL_REQUEST_UNKNOWN = "APPROVAL_REQUEST_UNKNOWN"
    APPROVAL_REQUEST_NOT_PENDING = "APPROVAL_REQUEST_NOT_PENDING"
    INVALID_ARGUMENT_SCOPE = "INVALID_ARGUMENT_SCOPE"
    INVALID_APPROVER_KEY = "INVALID_APPROVER_KEY"
    APPROVER_NOT_REGISTERED = "APPROVER_NOT_REGISTERED"
    APPROVAL_SIGNATURE_INVALID = "APPROVAL_SIGNATURE_INVALID"
    APPROVAL_SIGNATURE_REQUIRED = "APPROVAL_SIGNATURE_REQUIRED"
    INVALID_SESSION_CONTRACT = "INVALID_SESSION_CONTRACT"
    TOOL_NOT_OFFERED = "TOOL_NOT_OFFERED"
    TOOL_CALL_LIMIT_REACHED = "TOOL_CALL_LIMIT_REACHED"
    # shared with the core registry, and raised by the gate directly as well
    APPROVAL_NEEDS_A_NAMED_HUMAN = "APPROVAL_NEEDS_A_NAMED_HUMAN"
    INVALID_TOOL_NAME = "INVALID_TOOL_NAME"
    # receipts
    RECEIPT_SEQUENCE_BROKEN = "RECEIPT_SEQUENCE_BROKEN"
    RECEIPT_CHAIN_BROKEN = "RECEIPT_CHAIN_BROKEN"
    RECEIPT_HASH_MISMATCH = "RECEIPT_HASH_MISMATCH"


#: MCP tool names: mixed case is normal (``getWeather``). Server names keep the
#: core registry's lower-case rule, because they are the namespace an operator
#: chose, not text a third party supplied.
_MCP_TOOL_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,126}[A-Za-z0-9])?")


class McpToolRegistry(ToolRegistry):
    """The core registry, accepting tool names as the MCP specification writes them."""

    @staticmethod
    def qualified_name(manifest: ToolManifest) -> str:
        ToolRegistry.qualified_name(replace(manifest, name="x"))  # the server-name rule
        _require(bool(_MCP_TOOL_NAME.fullmatch(manifest.name)), "INVALID_TOOL_NAME")
        return f"{manifest.server}/{manifest.name}"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


# -- configuration -------------------------------------------------------------


@dataclass(frozen=True)
class ToolPolicy:
    """What the deployment says a tool can do. Never read from the server."""

    power: int
    irreversibility: int
    effects: frozenset[str]
    trusted_output: bool = False
    max_calls: int | None = None
    #: A named person approves each exact call before it runs.
    approval: bool = False
    #: ``{argument: (allowed, values)}``: exact matches only, no wildcards.
    scope: Mapping[str, tuple] = field(default_factory=dict)

    @classmethod
    def parse(cls, value: Mapping[str, Any] | None) -> ToolPolicy:
        raw = dict(UNDECLARED_POLICY if value is None else value)
        unknown = set(raw) - {"power", "irreversibility", "effects", "trusted_output", "max_calls",
                              "approval", "scope"}
        _require(not unknown, "UNKNOWN_TOOL_POLICY_FIELD")
        max_calls = raw.get("max_calls")
        _require(max_calls is None or (type(max_calls) is int and max_calls >= 0),
                 "INVALID_TOOL_CALL_LIMIT")
        approval = raw.get("approval", False)
        _require(approval in (False, True, "required", "none"), "UNKNOWN_TOOL_POLICY_FIELD")
        scope_raw = raw.get("scope") or {}
        _require(isinstance(scope_raw, dict), "INVALID_ARGUMENT_SCOPE")
        scope = {}
        for argument, allowed in scope_raw.items():
            # Exact values only. A pattern would be a second policy language
            # with its own bypasses; an allow-list is reviewable at a glance.
            _require(isinstance(allowed, list) and bool(allowed)
                     and all(isinstance(v, (str, int, bool)) for v in allowed), "INVALID_ARGUMENT_SCOPE")
            scope[str(argument)] = tuple(allowed)
        return cls(power=raw.get("power", 3), irreversibility=raw.get("irreversibility", 2),
                   effects=frozenset(raw.get("effects", ())),
                   trusted_output=bool(raw.get("trusted_output", False)), max_calls=max_calls,
                   approval=approval in (True, "required"), scope=scope)

    def governance(self) -> dict:
        """The parts of policy that a lock pins beyond the manifest digest."""
        return {"trusted_output": self.trusted_output, "max_calls": self.max_calls,
                "approval": self.approval, "scope": {k: list(v) for k, v in sorted(self.scope.items())}}



def locked_governance(policy: Mapping[str, Any]) -> dict:
    """The same view read back from a lock file; absent fields meant 'off' when it was written."""
    return {"trusted_output": bool(policy.get("trusted_output", False)),
            "max_calls": policy.get("max_calls"), "approval": bool(policy.get("approval", False)),
            "scope": {k: list(v) for k, v in sorted((policy.get("scope") or {}).items())},
            "approvers": list(policy.get("approvers") or [])}


def parse_approvers(value: Any) -> dict[str, str]:
    raw = value or {}
    _require(isinstance(raw, dict), "INVALID_APPROVER_KEY")
    approvers = {}
    for name, key in raw.items():
        _require(isinstance(name, str) and bool(name.strip()), "APPROVAL_NEEDS_A_NAMED_HUMAN")
        _require(isinstance(key, str) and key.startswith("ed25519:"), "INVALID_APPROVER_KEY")
        hexkey = key.split(":", 1)[1]
        _require(len(hexkey) == 64 and all(c in "0123456789abcdef" for c in hexkey), "INVALID_APPROVER_KEY")
        approvers[name.strip()] = hexkey
    return approvers


def approval_payload(record: Mapping[str, Any]) -> bytes:
    """What an approver's signature covers: the request, the exact call and the decision."""
    return canonical({k: record.get(k) for k in (
        "id", "tool", "args_sha256", "status", "decided_by", "decided_at", "expires_at")})


def generate_approver_key(path: str | Path, name: str) -> str:
    """Write an owner-only Ed25519 key for one named approver; return the config line."""
    from ..evidence_notary import _ed25519

    private_cls, _, _, encoding, public_format = _ed25519()
    _require(isinstance(name, str) and bool(name.strip()), "APPROVAL_NEEDS_A_NAMED_HUMAN")
    key = private_cls.generate()
    from cryptography.hazmat.primitives.serialization import NoEncryption, PrivateFormat

    private = key.private_bytes(encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
    public = key.public_key().public_bytes(encoding.Raw, public_format.Raw).hex()
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"name": name.strip(), "ed25519_private": private, "ed25519_public": public}, handle)
    return f"ed25519:{public}"


def sign_approval(record: dict, key_path: str | Path) -> dict:
    from ..evidence_notary import _ed25519

    private_cls = _ed25519()[0]
    key = json.loads(Path(key_path).read_text(encoding="utf-8"))
    _require(key.get("name") == record.get("decided_by"), "APPROVER_NOT_REGISTERED")
    signer = private_cls.from_private_bytes(bytes.fromhex(key["ed25519_private"]))
    return {**record, "signature": signer.sign(approval_payload(record)).hex()}


def approval_signature_valid(record: Mapping[str, Any], approvers: Mapping[str, str]) -> bool:
    from ..evidence_notary import _ed25519

    _, public_cls, invalid, _, _ = _ed25519()
    key = approvers.get(str(record.get("decided_by")))
    signature = record.get("signature")
    if key is None or not isinstance(signature, str):
        return False
    try:
        public_cls.from_public_bytes(bytes.fromhex(key)).verify(bytes.fromhex(signature),
                                                                approval_payload(record))
    except (invalid, ValueError):
        return False
    return True


def tool_governance(config: GateConfig, spec: UpstreamSpec, tool: str) -> dict:
    """A tool's pinned governance: its policy, plus who may approve it."""
    policy = spec.policy_for(tool)
    approvers = sorted(f"{n}={k}" for n, k in config.approvers.items()) if policy.approval else []
    return {**policy.governance(), "approvers": approvers}


@dataclass(frozen=True)
class SessionContract:
    """A task contract for one gate session: it ends, and it has a budget."""

    expires_after_seconds: float | None = None
    max_calls: int | None = None

    @classmethod
    def parse(cls, value: Any) -> SessionContract:
        raw = value or {}
        _require(isinstance(raw, dict) and set(raw) <= {"expires_after_seconds", "max_calls"},
                 "INVALID_SESSION_CONTRACT")
        expires, calls = raw.get("expires_after_seconds"), raw.get("max_calls")
        _require(expires is None or (isinstance(expires, (int, float)) and not isinstance(expires, bool)
                                     and 0 < expires < float("inf")), "INVALID_SESSION_CONTRACT")
        _require(calls is None or (type(calls) is int and calls >= 0), "INVALID_SESSION_CONTRACT")
        return cls(expires_after_seconds=expires, max_calls=calls)


@dataclass(frozen=True)
class UpstreamSpec:
    """One MCP server: launched on stdio, or reached at a Streamable HTTP ``url``."""

    name: str
    command: tuple[str, ...]
    operator: str
    env: Mapping[str, str] = field(default_factory=dict)
    cwd: str | None = None
    pin_files: tuple[str, ...] = ()
    tools: Mapping[str, ToolPolicy] = field(default_factory=dict)
    url: str | None = None
    #: Header values of the form ``env:NAME`` are read from the gate's
    #: environment at connect time, so secrets never sit in the policy file.
    headers: Mapping[str, str] = field(default_factory=dict)

    def launch_identity(self, base: Path) -> str:
        """The server's identity pin: how it is launched, plus pinned file bytes.

        Changing the command, arguments, environment or any pinned file makes
        this a different server, and every approval it held is withdrawn. Env
        values are included because they select behaviour (``--mode``, API
        endpoints); secrets should be passed by the host's own environment,
        which the gate inherits and does not pin.
        """
        files = {}
        for path in self.pin_files:
            resolved = (base / path) if not os.path.isabs(path) else Path(path)
            _require(resolved.is_file(), "PINNED_FILE_MISSING")
            files[path] = sha256(resolved.read_bytes())
        identity: dict[str, Any] = {"command": list(self.command), "env": dict(self.env),
                                    "cwd": self.cwd, "files": files}
        if self.url is not None:
            # Header names, not values: a rotated token is not a different server.
            identity.update(url=self.url, headers=sorted(self.headers))
        return sha256(canonical(identity))

    def policy_for(self, tool: str) -> ToolPolicy:
        return self.tools.get(tool) or ToolPolicy.parse(None)


@dataclass(frozen=True)
class GateConfig:
    servers: tuple[UpstreamSpec, ...]
    trusted_sources: frozenset[str] = frozenset()
    session_starts_untrusted: bool = False
    call_timeout: float = 60.0
    base: Path = Path(".")
    session: SessionContract = SessionContract()
    approvals: Path | None = None
    approval_ttl: float = 900.0
    #: ``{name: public-key hex}``. When set, only these people can approve,
    #: and only with a signature the gate verifies.
    approvers: Mapping[str, str] = field(default_factory=dict)
    #: Where to announce a held call (a chat or ticketing webhook). Metadata only.
    notify_url: str | None = None
    #: Gate-owned record of used approvals. Put it where only gates can write,
    #: so restoring a spent approval file in ``approvals`` achieves nothing.
    spent_ledger: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> GateConfig:
        import yaml

        path = Path(path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _require(isinstance(raw, dict) and isinstance(raw.get("servers"), dict) and raw["servers"],
                 "GATE_CONFIG_NEEDS_SERVERS")
        servers = []
        for name, spec in raw["servers"].items():
            _require(isinstance(spec, dict), "INVALID_SERVER_ENTRY")
            _require(WIRE_SEPARATOR not in str(name), "SERVER_NAME_CONTAINS_WIRE_SEPARATOR")
            url = spec.get("url")
            _require((url is None) != (spec.get("command") is None), "SERVER_NEEDS_COMMAND_OR_URL")
            command = spec.get("command")
            if isinstance(command, str):
                command = [command]
            command = list(command or []) + list(spec.get("args") or [])
            if url is None:
                _require(bool(command) and all(isinstance(p, str) for p in command),
                         "SERVER_COMMAND_REQUIRED")
                # Launch with the interpreter running the gate when a config says
                # ``python``, so examples work inside a virtual environment.
                if command[0] in ("python", "python3"):
                    command[0] = sys.executable
            else:
                check_upstream_url(url)
            tools = {tool: ToolPolicy.parse(policy)
                     for tool, policy in (spec.get("tools") or {}).items()}
            servers.append(UpstreamSpec(
                name=name, command=tuple(command), operator=str(spec.get("operator") or ""),
                env={str(k): str(v) for k, v in (spec.get("env") or {}).items()},
                cwd=spec.get("cwd"), pin_files=tuple(spec.get("pin_files") or ()), tools=tools,
                url=url, headers={str(k): str(v) for k, v in (spec.get("headers") or {}).items()}))
        trusted = frozenset(raw.get("trusted_sources") or ())
        for source in trusted:
            _require(isinstance(source, str) and source.count("/") == 1, "TRUSTED_SOURCE_MUST_BE_QUALIFIED")
        base = path.resolve().parent
        approvals = raw.get("approvals")
        ttl = raw.get("approval_ttl", 900)
        _require(isinstance(ttl, (int, float)) and not isinstance(ttl, bool) and 0 < ttl < float("inf"),
                 "INVALID_SESSION_CONTRACT")
        config = cls(servers=tuple(servers), trusted_sources=trusted,
                     session_starts_untrusted=bool(raw.get("session_starts_untrusted", False)),
                     call_timeout=float(raw.get("call_timeout", 60.0)), base=base,
                     session=SessionContract.parse(raw.get("session")),
                     approvals=(base / approvals) if approvals else None, approval_ttl=float(ttl),
                     approvers=parse_approvers(raw.get("approvers")),
                     notify_url=check_upstream_url(raw["notify_url"]) if raw.get("notify_url") else None,
                     spent_ledger=(base / raw["spent_ledger"]) if raw.get("spent_ledger")
                     else ((base / approvals / ".spent") if approvals else None))
        needs_store = any(p.approval for s in config.servers for p in s.tools.values())
        _require(config.approvals is not None or not needs_store, "APPROVAL_STORE_REQUIRED")
        return config

    def server(self, name: str) -> UpstreamSpec:
        for spec in self.servers:
            if spec.name == name:
                return spec
        raise McpGateDenied("UNKNOWN_SERVER")

    def trusted(self) -> frozenset[str]:
        """Sources whose output keeps a chain trusted: named in the file or by policy."""
        declared = {f"{s.name}/{tool}" for s in self.servers
                    for tool, policy in s.tools.items() if policy.trusted_output}
        return frozenset(self.trusted_sources | declared)


# -- upstream client -----------------------------------------------------------


class Upstream:
    """A newline-delimited JSON-RPC client for one stdio MCP server."""

    def __init__(self, spec: UpstreamSpec, *, base: Path, timeout: float = 60.0,
                 on_request: Callable[[str, dict], None] | None = None) -> None:
        self.spec = spec
        self.timeout = timeout
        self.list_changed = False
        self.server_info: dict = {}
        self._next_id = 0
        self._on_request = on_request
        self._inbox: queue.Queue = queue.Queue()
        # Relative paths in a config mean "next to the config file", wherever
        # the gate itself was started from.
        cwd = str(base if spec.cwd is None else base / spec.cwd)
        self._process = subprocess.Popen(
            list(spec.command), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, cwd=cwd, env={**os.environ, **spec.env},
            text=True, encoding="utf-8", bufsize=1)
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self._inbox.put(json.loads(line))
            except json.JSONDecodeError:
                continue  # a server that writes noise to stdout is ignored, not trusted
        self._inbox.put(None)

    def _send(self, message: dict) -> None:
        assert self._process.stdin is not None
        try:
            self._process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise McpGateDenied("UPSTREAM_UNAVAILABLE") from exc

    def notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})})

    def request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        ident = self._next_id
        self._send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}})
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            _require(remaining > 0, "UPSTREAM_TIMEOUT")
            try:
                message = self._inbox.get(timeout=remaining)
            except queue.Empty as exc:
                raise McpGateDenied("UPSTREAM_TIMEOUT") from exc
            _require(message is not None, "UPSTREAM_UNAVAILABLE")
            if "method" in message and "id" in message:
                self._answer_upstream_request(message)
            elif "method" in message:
                if message["method"] == "notifications/tools/list_changed":
                    self.list_changed = True
            elif message.get("id") == ident:
                if "error" in message:
                    raise McpGateDenied("UPSTREAM_ERROR")
                return message.get("result") or {}

    def _answer_upstream_request(self, message: dict) -> None:
        method = message.get("method", "")
        if method == "ping":
            self._send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
            return
        if self._on_request is not None:
            self._on_request(method, message.get("params") or {})
        self._send({"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": -32601, "message": "UPSTREAM_REQUEST_NOT_FORWARDED"}})

    def initialize(self) -> dict:
        result = self.request("initialize", {
            "protocolVersion": LATEST_PROTOCOL, "capabilities": {},
            "clientInfo": {"name": GATE_NAME, "version": "1"}})
        self.server_info = dict(result.get("serverInfo") or {})
        self.notify("notifications/initialized")
        return result

    def list_tools(self) -> list[dict]:
        return _list_all_tools(self)

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        try:
            if self._process.stdin:
                self._process.stdin.close()
        except OSError:
            pass
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()


def _list_all_tools(upstream: Any) -> list[dict]:
    tools: list[dict] = []
    cursor = None
    for _ in range(64):  # a server that paginates forever does not get to stall the gate
        result = upstream.request("tools/list", {"cursor": cursor} if cursor else {})
        tools.extend(t for t in result.get("tools") or [] if isinstance(t, dict))
        cursor = result.get("nextCursor")
        if not cursor:
            upstream.list_changed = False
            return tools
    raise McpGateDenied("UPSTREAM_PAGINATION_UNBOUNDED")


def _json_or_none(text: str | bytes) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def check_upstream_url(url: Any) -> str:
    """HTTPS, or plain HTTP to this machine only. Nothing else carries a credential."""
    from urllib.parse import urlsplit

    _require(isinstance(url, str), "UPSTREAM_URL_MUST_BE_HTTPS")
    parts = urlsplit(url)
    loopback = parts.hostname in ("localhost", "127.0.0.1", "::1")
    _require(parts.scheme == "https" or (parts.scheme == "http" and loopback), "UPSTREAM_URL_MUST_BE_HTTPS")
    return url


class HttpUpstream:
    """A Streamable HTTP client for one remote MCP server, with the stdio client's interface.

    Each JSON-RPC message is POSTed to the server's endpoint. A reply is either
    one JSON body or an event stream that may carry server requests and
    notifications before the response; server requests are answered, and
    refused, exactly as on stdio. Redirects are refused rather than followed,
    so a credential header can never be replayed to another host.
    """

    def __init__(self, spec: UpstreamSpec, *, timeout: float = 60.0,
                 on_request: Callable[[str, dict], None] | None = None) -> None:
        import urllib.request

        self.spec = spec
        self.timeout = timeout
        self.list_changed = False
        self.server_info: dict = {}
        self._next_id = 0
        self._on_request = on_request
        self._session: str | None = None
        self._protocol: str | None = None
        self._headers = {}
        for key, value in spec.headers.items():
            if value.startswith("env:"):
                resolved = os.environ.get(value[4:])
                if resolved is None:
                    raise McpGateDenied("UPSTREAM_HEADER_ENV_MISSING")
                value = resolved
            self._headers[key] = value

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args: Any, **kwargs: Any) -> None:
                raise McpGateDenied("UPSTREAM_REDIRECT_REFUSED")

        self._opener = urllib.request.build_opener(NoRedirect)

    def _post(self, message: dict) -> Any:
        import urllib.error
        import urllib.request

        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   **self._headers}
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        if self._protocol:
            headers["MCP-Protocol-Version"] = self._protocol
        request = urllib.request.Request(str(self.spec.url), data=json.dumps(message).encode(),
                                         headers=headers, method="POST")
        try:
            return self._opener.open(request, timeout=self.timeout)
        except McpGateDenied:
            raise
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                raise McpGateDenied("UPSTREAM_REDIRECT_REFUSED") from exc
            raise McpGateDenied("UPSTREAM_ERROR") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise McpGateDenied("UPSTREAM_UNAVAILABLE") from exc

    #: A response larger than this is refused rather than buffered.
    MAX_RESPONSE_BYTES = 16 * 1024 * 1024

    def _messages(self, response: Any) -> Iterable[dict]:
        kind = (response.headers.get("Content-Type") or "").split(";")[0].strip()
        deadline, received = time.monotonic() + self.timeout, 0
        if kind == "text/event-stream":
            data: list[str] = []
            for raw in response:
                # A server that trickles an endless stream does not hold the gate.
                received += len(raw)
                _require(received <= self.MAX_RESPONSE_BYTES, "UPSTREAM_RESPONSE_TOO_LARGE")
                _require(time.monotonic() < deadline, "UPSTREAM_TIMEOUT")
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("data:"):
                    data.append(line[5:].lstrip())
                elif not line and data:
                    parsed = _json_or_none("\n".join(data))
                    data = []
                    if parsed is not None:
                        yield parsed
            if data and (parsed := _json_or_none("\n".join(data))) is not None:
                yield parsed
        else:
            body = response.read(self.MAX_RESPONSE_BYTES + 1)
            _require(len(body) <= self.MAX_RESPONSE_BYTES, "UPSTREAM_RESPONSE_TOO_LARGE")
            parsed = _json_or_none(body or b"null")
            if parsed is not None:
                yield parsed

    def notify(self, method: str, params: dict | None = None) -> None:
        self._post({"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})}).close()

    def request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        ident = self._next_id
        response = self._post({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}})
        with response:
            session = response.headers.get("Mcp-Session-Id")
            if session and self._session is None:
                self._session = session
            for message in self._messages(response):
                if not isinstance(message, dict):
                    continue
                if "method" in message and "id" in message:
                    self._answer_upstream_request(message)
                elif "method" in message:
                    if message["method"] == "notifications/tools/list_changed":
                        self.list_changed = True
                elif message.get("id") == ident:
                    if "error" in message:
                        raise McpGateDenied("UPSTREAM_ERROR")
                    return message.get("result") or {}
        raise McpGateDenied("UPSTREAM_UNAVAILABLE")

    def _answer_upstream_request(self, message: dict) -> None:
        method = message.get("method", "")
        if method == "ping":
            self._post({"jsonrpc": "2.0", "id": message["id"], "result": {}}).close()
            return
        if self._on_request is not None:
            self._on_request(method, message.get("params") or {})
        self._post({"jsonrpc": "2.0", "id": message["id"],
                    "error": {"code": -32601, "message": "UPSTREAM_REQUEST_NOT_FORWARDED"}}).close()

    def initialize(self) -> dict:
        result = self.request("initialize", {
            "protocolVersion": LATEST_PROTOCOL, "capabilities": {},
            "clientInfo": {"name": GATE_NAME, "version": "1"}})
        self.server_info = dict(result.get("serverInfo") or {})
        version = result.get("protocolVersion")
        self._protocol = version if version in PROTOCOL_VERSIONS else LATEST_PROTOCOL
        self.notify("notifications/initialized")
        return result

    def list_tools(self) -> list[dict]:
        return _list_all_tools(self)

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        if self._session:
            import urllib.request

            request = urllib.request.Request(str(self.spec.url), method="DELETE",
                                             headers={**self._headers, "Mcp-Session-Id": self._session})
            with contextlib.suppress(Exception):  # ending a session is best effort
                self._opener.open(request, timeout=min(self.timeout, 5)).close()


def open_upstream(spec: UpstreamSpec, *, base: Path, timeout: float,
                  on_request: Callable[[str, dict], None] | None = None) -> Upstream | HttpUpstream:
    if spec.url is not None:
        return HttpUpstream(spec, timeout=timeout, on_request=on_request)
    return Upstream(spec, base=base, timeout=timeout, on_request=on_request)


# -- turning an MCP listing into a manifest ------------------------------------


def model_text(tool: Mapping[str, Any]) -> str:
    """Every string the model will read about a tool, in a stable order.

    Poisoning is not confined to the ``description`` field: parameter
    descriptions, titles and enum labels reach the model the same way, and a
    scanner that reads only the top-level description misses the attack
    placed one level down.
    """
    parts = [f"name: {tool.get('name', '')}"]
    if tool.get("title"):
        parts.append(f"title: {tool['title']}")
    parts.append(f"description: {tool.get('description') or ''}")

    def walk(schema: Any, path: str) -> None:
        if isinstance(schema, dict):
            for key in ("title", "description"):
                if isinstance(schema.get(key), str):
                    parts.append(f"{path}.{key}: {schema[key]}")
            if isinstance(schema.get("enum"), list):
                parts.append(f"{path}.enum: " + ", ".join(map(str, schema["enum"])))
            for key in sorted(schema):
                if key in ("properties", "$defs", "definitions", "patternProperties"):
                    for child in sorted(schema[key] or {}):
                        walk(schema[key][child], f"{path}.{child}")
                elif key in ("items", "additionalProperties", "not"):
                    walk(schema[key], f"{path}[]")
                elif key in ("anyOf", "oneOf", "allOf"):
                    for i, child in enumerate(schema[key] or []):
                        walk(child, f"{path}|{i}")

    walk(tool.get("inputSchema"), "input")
    return "\n".join(parts)


def annotation_findings(tool: Mapping[str, Any], policy: ToolPolicy) -> list[dict]:
    """Where the server's self-description disagrees with the deployment's policy."""
    notes = tool.get("annotations") or {}
    findings = []
    privileged = (policy.power >= 3 or policy.irreversibility >= 2
                  or bool(policy.effects & {"external_write", "infrastructure"}))
    if notes.get("destructiveHint") is True and not privileged:
        findings.append({"finding": "annotation_claims_destructive_policy_does_not",
                         "excerpt": "destructiveHint"})
    if notes.get("openWorldHint") is True and policy.trusted_output:
        findings.append({"finding": "open_world_output_declared_trusted", "excerpt": "openWorldHint"})
    return findings


def manifest_for(spec: UpstreamSpec, tool: Mapping[str, Any], *, executable_hash: str) -> ToolManifest:
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        raise McpGateDenied("UPSTREAM_TOOL_WITHOUT_NAME")
    policy = spec.policy_for(name)
    return ToolManifest(
        name=name, server=spec.name,
        description_hash=sha256(model_text(tool)),
        input_hash=sha256(canonical(tool.get("inputSchema") or {})),
        output_hash=sha256(canonical({"outputSchema": tool.get("outputSchema"),
                                      "annotations": tool.get("annotations")})),
        executable_hash=executable_hash,
        power=policy.power, irreversibility=policy.irreversibility, effects=policy.effects)


def executable_hash(identity: str, server_info: Mapping[str, Any]) -> str:
    """The launch identity plus what the server reports itself to be."""
    return sha256(canonical({"identity": identity,
                             "server": {k: server_info.get(k) for k in ("name", "version")}}))


def wire_name(qualified: str) -> str:
    server, tool = qualified.split("/", 1)
    return f"{server}{WIRE_SEPARATOR}{tool}"


def qualified_from_wire(name: Any, servers: Iterable[str]) -> str:
    """Map ``server__tool`` back to ``server/tool``. A bare name never resolves."""
    _require(isinstance(name, str), "QUALIFIED_NAME_REQUIRED")
    for server in sorted(servers, key=len, reverse=True):
        prefix = server + WIRE_SEPARATOR
        if name.startswith(prefix) and len(name) > len(prefix):
            return f"{server}/{name[len(prefix):]}"
    raise McpGateDenied("QUALIFIED_NAME_REQUIRED")


# -- scan and lock ---------------------------------------------------------------


def _survey(config: GateConfig) -> list[dict]:
    """Connect to every server and return what a reviewer needs to see."""
    known = [s.name for s in config.servers]
    survey = []
    for spec in config.servers:
        identity = spec.launch_identity(config.base)
        upstream = open_upstream(spec, base=config.base, timeout=config.call_timeout)
        try:
            upstream.initialize()
            listing = upstream.list_tools()
        finally:
            upstream.close()
        exe = executable_hash(identity, upstream.server_info)
        tools: list[dict[str, Any]] = []
        for tool in listing:
            manifest = manifest_for(spec, tool, executable_hash=exe)
            policy = spec.policy_for(manifest.name)
            text = model_text(tool)
            tools.append({
                "name": manifest.name,
                "wire_name": wire_name(f"{spec.name}/{manifest.name}"),
                "model_text": text,
                "input_schema": tool.get("inputSchema") or {},
                "output_hash": manifest.output_hash,
                "annotations": tool.get("annotations") or {},
                "policy": {"power": policy.power, "irreversibility": policy.irreversibility,
                           "effects": sorted(policy.effects), **tool_governance(config, spec, manifest.name),
                           "declared": manifest.name in spec.tools},
                "privileged": ToolRegistry.is_privileged(manifest),
                "findings": list(scan_description(text, known_servers=known, own_server=spec.name))
                            + annotation_findings(tool, policy),
            })
        survey.append({"name": spec.name, "operator": spec.operator, "identity_pin": identity,
                       "executable_hash": exe, "server_info": upstream.server_info,
                       "tools": sorted(tools, key=lambda t: t["name"])})
    return survey


def scan(config: GateConfig) -> dict:
    """Report what each server would show a model. Approves nothing."""
    survey = _survey(config)
    flagged = sum(1 for s in survey for t in s["tools"] if t["findings"])
    return {"schema_version": "1.0", "kind": "mcp_scan", "servers": survey,
            "tools": sum(len(s["tools"]) for s in survey), "flagged_tools": flagged,
            "undeclared_tools": sorted(f"{s['name']}/{t['name']}" for s in survey
                                       for t in s["tools"] if not t["policy"]["declared"]),
            "limits": ["a clean scan is not evidence that a description is safe; "
                       "it is a review aid ahead of a named approval"]}


def lock(config: GateConfig, *, approved_by: str, accept_findings: Iterable[str] = (),
         clock: Callable[[], float] = time.time) -> dict:
    """Record a named human's approval of exactly what the servers listed now.

    A tool with scan findings is left out of the lock unless its qualified name
    is passed in ``accept_findings``: accepting flagged text is a decision a
    person makes about one tool, never a blanket switch.
    """
    _require(isinstance(approved_by, str) and bool(approved_by.strip()), "APPROVAL_NEEDS_A_NAMED_HUMAN")
    accepted = set(accept_findings)
    registry = McpToolRegistry(clock=clock)
    servers, excluded = [], []
    for server in _survey(config):
        registry.register_server(ToolServer(server["name"], server["identity_pin"],
                                            server["operator"]))
        entries = []
        for tool in server["tools"]:
            qualified = f"{server['name']}/{tool['name']}"
            if tool["findings"] and qualified not in accepted:
                excluded.append({"tool": qualified, "reason": "FLAGGED_DESCRIPTION_NOT_EXPLICITLY_ACCEPTED",
                                 "findings": tool["findings"]})
                continue
            manifest = _manifest_from_lock(server, tool)
            approval = registry.approve(manifest, tool["model_text"], approved_by=approved_by,
                                        accept_findings=qualified in accepted)
            entries.append({**{k: tool[k] for k in ("name", "model_text", "input_schema", "output_hash",
                                                    "annotations", "policy", "privileged", "findings")},
                            "digest": approval.digest})
        servers.append({k: server[k] for k in ("name", "operator", "identity_pin", "executable_hash",
                                               "server_info")} | {"tools": entries})
    return {"schema": LOCK_SCHEMA, "approved_by": approved_by, "approved_at": clock(),
            "servers": servers, "excluded": excluded}


def _manifest_from_lock(server: Mapping[str, Any], tool: Mapping[str, Any]) -> ToolManifest:
    policy = tool["policy"]
    return ToolManifest(
        name=tool["name"], server=server["name"], description_hash=sha256(tool["model_text"]),
        input_hash=sha256(canonical(tool["input_schema"])), output_hash=tool["output_hash"],
        executable_hash=server["executable_hash"], power=policy["power"],
        irreversibility=policy["irreversibility"], effects=frozenset(policy["effects"]))


# -- receipts --------------------------------------------------------------------


class ReceiptLog:
    """Append-only, hash-chained, metadata-only record of every gate decision.

    A receipt names the tool, the decision and the reason code, and carries
    SHA-256 digests of the arguments and result. It never stores their content:
    an auditor can prove *that* a given argument was sent by presenting it and
    matching the digest, while the log itself discloses nothing.
    """

    def __init__(self, path: str | Path | None, *, clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path) if path else None
        self._clock = clock
        self._lock = threading.Lock()
        self.seq, self.head = 0, GENESIS
        if self.path and self.path.exists():
            for record in _read_receipts(self.path):
                self.seq, self.head = record["seq"], record["hash"]
        self.records: list[dict] = []

    def history(self) -> list[dict]:
        """Every receipt, including those written before this process started."""
        if self.path and self.path.exists():
            return _read_receipts(self.path)
        return list(self.records)

    def append(self, **fields: Any) -> dict:
        with self._lock:
            body = {"schema": RECEIPT_SCHEMA, "seq": self.seq + 1, "prev": self.head,
                    "time": round(self._clock(), 3), **fields}
            record = {**body, "hash": sha256(canonical(body))}
            self.seq, self.head = record["seq"], record["hash"]
            self.records.append(record)
            if self.path:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")
            return record


def _read_receipts(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_receipts(path: str | Path) -> dict:
    """Recompute the chain. Any edit, deletion or reordering breaks it."""
    records = _read_receipts(Path(path))
    head, problems = GENESIS, []
    counts: dict[str, int] = {}
    for index, record in enumerate(records, start=1):
        body = {k: v for k, v in record.items() if k != "hash"}
        if record.get("seq") != index:
            problems.append({"seq": record.get("seq"), "problem": "RECEIPT_SEQUENCE_BROKEN"})
        if record.get("prev") != head:
            problems.append({"seq": record.get("seq"), "problem": "RECEIPT_CHAIN_BROKEN"})
        if sha256(canonical(body)) != record.get("hash"):
            problems.append({"seq": record.get("seq"), "problem": "RECEIPT_HASH_MISMATCH"})
        head = record.get("hash", "")
        key = f"{record.get('event')}:{record.get('decision')}"
        counts[key] = counts.get(key, 0) + 1
    return {"verified": not problems and bool(records), "receipts": len(records), "head": head,
            "decisions": dict(sorted(counts.items())), "problems": problems}


# -- exact-action approval --------------------------------------------------------


class ApprovalStore:
    """Requests a named person approves, one file each, outside the agent's reach.

    A request carries the exact arguments, because a person cannot approve what
    they have not seen. Once decided and used, the arguments are dropped and
    only their digest remains, so the store does not become a second copy of
    what the agent handled. The directory must not be writable by the agent's
    operating-system user: the gate cannot tell who ran ``fssaira mcp approve``,
    only that someone who could write here did.
    """

    def __init__(self, directory: str | Path, *, clock: Callable[[], float] = time.time,
                 spent: str | Path | None = None) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.spent = Path(spent) if spent else self.directory / ".spent"
        self.spent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = threading.Lock()

    def _mark_spent(self, request_id: str) -> bool:
        """Create the spent marker exclusively; False if any gate already used it."""
        try:
            fd = os.open(self.spent / self._path(request_id).stem, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return False
        os.close(fd)
        return True

    def _path(self, request_id: str) -> Path:
        _require(isinstance(request_id, str) and request_id.isalnum() and 8 <= len(request_id) <= 64,
                 "APPROVAL_REQUEST_UNKNOWN")
        return self.directory / f"{request_id}.json"

    def _write(self, record: dict) -> None:
        path = self._path(record["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def get(self, request_id: str) -> dict:
        path = self._path(request_id)
        _require(path.is_file(), "APPROVAL_REQUEST_UNKNOWN")
        return json.loads(path.read_text(encoding="utf-8"))

    def all(self) -> list[dict]:
        records = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue  # a file that is not a request is not a request
        return sorted(records, key=lambda r: r.get("requested_at", 0))

    def request(self, tool: str, args_digest: str, arguments: Mapping[str, Any]) -> dict:
        """Reuse the pending request for this exact call, or open one (``new`` says which)."""
        with self._lock:
            for record in self.all():
                if (record["status"] == "pending" and record["tool"] == tool
                        and record["args_sha256"] == args_digest):
                    return {**record, "new": False}
            record = {"id": sha256(f"{tool}|{args_digest}|{self._clock()}|{os.urandom(8).hex()}")[:20],
                      "tool": tool, "args_sha256": args_digest, "arguments": dict(arguments),
                      "requested_at": round(self._clock(), 3), "status": "pending"}
            self._write(record)
            return {**record, "new": True}

    def decide(self, request_id: str, *, by: str, approve: bool, ttl: float = 900.0,
               key_path: str | Path | None = None) -> dict:
        _require(isinstance(by, str) and bool(by.strip()), "APPROVAL_NEEDS_A_NAMED_HUMAN")
        with self._lock:
            record = self.get(request_id)
            _require(record["status"] == "pending", "APPROVAL_REQUEST_NOT_PENDING")
            now = self._clock()
            record.update(status="approved" if approve else "denied", decided_by=by.strip(),
                          decided_at=round(now, 3))
            if approve:
                record["expires_at"] = round(now + ttl, 3)
                if key_path is not None:
                    record = sign_approval(record, key_path)
            else:
                record.pop("arguments", None)
            self._write(record)
            return record

    def consume(self, tool: str, args_digest: str, *,
                approvers: Mapping[str, str] | None = None,
                on_reject: Callable[[dict, str], None] | None = None,
                spent: Iterable[str] = ()) -> dict | None:
        """Use one live approval for exactly this call, or return None.

        Use is claimed by renaming the request file, which the operating
        system does atomically: of two gate processes racing for one approval,
        exactly one succeeds. With registered approvers, an approval counts
        only if its signature verifies against the named approver's key.
        """
        with self._lock:
            now = self._clock()
            for record in self.all():
                if not (record["status"] == "approved" and record["tool"] == tool
                        and record["args_sha256"] == args_digest):
                    continue
                path = self._path(record["id"])
                claim = path.with_suffix(f".claim-{os.getpid()}-{threading.get_ident()}")
                try:
                    os.rename(path, claim)
                except FileNotFoundError:
                    continue  # another gate claimed it first
                record = json.loads(claim.read_text(encoding="utf-8"))
                reason = None
                if record.get("id") in set(spent):
                    # The file says unused, the gate's own record says used: someone
                    # who can write this directory restored a spent approval.
                    record["status"], reason = "rejected", "APPROVAL_ALREADY_USED"
                elif record.get("status") != "approved":
                    reason = "APPROVAL_REQUEST_NOT_PENDING"
                elif record.get("expires_at", 0) <= now:
                    record["status"], reason = "expired", "APPROVAL_EXPIRED"
                elif approvers and record.get("decided_by") not in approvers:
                    record["status"], reason = "rejected", "APPROVER_NOT_REGISTERED"
                elif approvers and "signature" not in record:
                    record["status"], reason = "rejected", "APPROVAL_SIGNATURE_REQUIRED"
                elif approvers and not approval_signature_valid(record, approvers):
                    record["status"], reason = "rejected", "APPROVAL_SIGNATURE_INVALID"
                elif not self._mark_spent(record["id"]):
                    record["status"], reason = "rejected", "APPROVAL_ALREADY_USED"
                else:
                    record.update(status="used", used_at=round(now, 3))
                record.pop("arguments", None)
                self._write(record)
                claim.unlink(missing_ok=True)
                if reason is None:
                    return record
                if on_reject is not None and reason != "APPROVAL_EXPIRED":
                    on_reject(record, reason)
            return None


# -- the gate ----------------------------------------------------------------------


class Gate:
    """One agent session: the host on one side, pinned upstream servers on the other."""

    def __init__(self, config: GateConfig, lock_data: Mapping[str, Any], *,
                 receipts: ReceiptLog, clock: Callable[[], float] = time.time,
                 allowed_tools: Iterable[str] | None = None,
                 context: Mapping[str, str] | None = None) -> None:
        _require(lock_data.get("schema") == LOCK_SCHEMA, "UNSUPPORTED_LOCK_FILE")
        self.config = config
        #: When set, the only qualified tools this session's caller may see or call.
        self.allowed = frozenset(allowed_tools) if allowed_tools is not None else None
        #: Added to every receipt, e.g. the authenticated caller and the session.
        self.context = dict(context or {})
        self.receipts = receipts
        self.registry = McpToolRegistry(clock=clock)
        self.chain = CallChain(trusted_sources=config.trusted())
        if config.session_starts_untrusted:
            self.chain.absorb("host/untrusted-context")
        self.calls: dict[str, int] = {}
        self.upstreams: dict[str, Upstream | HttpUpstream] = {}
        self.visible: dict[str, dict] = {}
        self._clock = clock
        self.started_at = clock()
        self.approvals = (ApprovalStore(config.approvals, clock=clock, spent=config.spent_ledger)
                          if config.approvals else None)
        #: Approvals this gate has used, from its own receipts: the approvals
        #: directory is not trusted to remember, because it can be rewritten.
        self.spent: set[str] = {r["approval"] for r in receipts.history() if r.get("approval")}
        self._locked = {s["name"]: s for s in lock_data.get("servers") or []}
        self._locked_policy = {f"{s['name']}/{t['name']}": t.get("policy") or {}
                               for s in self._locked.values() for t in s["tools"]}
        for server in self._locked.values():
            # The lock's pin is registered first; the live pin below replaces it
            # only if it matches, and otherwise withdraws every approval.
            self.registry.register_server(ToolServer(server["name"], server["identity_pin"],
                                                     server["operator"]))
            for tool in server["tools"]:
                self.registry.approve(_manifest_from_lock(server, tool), tool["model_text"],
                                      approved_by=lock_data.get("approved_by") or "",
                                      accept_findings=bool(tool.get("findings")))

    # -- upstream lifecycle --

    def start(self) -> None:
        for spec in self.config.servers:
            identity = spec.launch_identity(self.config.base)
            operator = spec.operator or "undeclared"
            self.registry.register_server(ToolServer(spec.name, identity, operator))
            locked = self._locked.get(spec.name)
            if locked is None or locked["identity_pin"] != identity:
                self._record("server", spec.name, "deny",
                             "SERVER_NOT_LOCKED" if locked is None else "SERVER_IDENTITY_ROTATED")
                continue
            upstream = open_upstream(spec, base=self.config.base, timeout=self.config.call_timeout,
                                     on_request=self._upstream_request_refused(spec.name))
            try:
                upstream.initialize()
            except McpGateDenied as exc:
                upstream.close()
                self._record("server", spec.name, "deny", str(exc))
                continue
            self.upstreams[spec.name] = upstream
        self.refresh()

    def _upstream_request_refused(self, server: str) -> Callable[[str, dict], None]:
        def record(method: str, _params: dict) -> None:
            self._record("upstream_request", f"{server}:{method}", "deny",
                         "UPSTREAM_REQUEST_NOT_FORWARDED")
        return record

    def close(self) -> None:
        for upstream in self.upstreams.values():
            upstream.close()

    def refresh(self) -> list[dict]:
        """Re-list every server and offer each tool against its approval.

        Called at start, on every host ``tools/list``, and before a call when a
        server has announced ``list_changed``. A redefinition is caught here
        whichever way the server tries to deliver it.
        """
        visible: dict[str, dict] = {}
        for name, upstream in self.upstreams.items():
            spec = self.config.server(name)
            try:
                listing = upstream.list_tools()
            except McpGateDenied as exc:
                self._record("server", name, "deny", str(exc))
                continue
            exe = executable_hash(spec.launch_identity(self.config.base), upstream.server_info)
            for tool in listing:
                try:
                    manifest = manifest_for(spec, tool, executable_hash=exe)
                    qualified = self.registry.qualified_name(manifest)
                    self.registry.offer(manifest, model_text(tool))
                    # Scope, approval and limits are policy the reviewer approved
                    # too; widening any of them after the lock is drift.
                    _require(tool_governance(self.config, spec, manifest.name)
                             == locked_governance(self._locked_policy.get(qualified, {})),
                             "POLICY_CHANGED_AFTER_APPROVAL")
                except ToolSupplyDenied as exc:
                    label = f"{name}/{tool.get('name', '?')}"
                    previous = self.visible.get(label, {})
                    if previous.get("_hidden") and str(exc) == "TOOL_QUARANTINED":
                        visible[label] = previous  # keep the reason it was quarantined for
                        continue
                    if previous.get("_code") != str(exc):
                        self._record("offer", label, "deny", str(exc))
                    visible[label] = {"_hidden": True, "_code": str(exc)}
                    continue
                visible[qualified] = {k: v for k, v in tool.items()
                                      if k in ("title", "description", "inputSchema",
                                               "outputSchema", "annotations")}
                visible[qualified]["name"] = wire_name(qualified)
        if self.allowed is not None:
            for qualified in list(visible):
                if qualified not in self.allowed and not visible[qualified].get("_hidden"):
                    visible[qualified] = {"_hidden": True, "_code": "CALLER_NOT_PERMITTED"}
        self.visible = visible
        return [tool for tool in visible.values() if not tool.get("_hidden")]

    # -- calls --

    def call(self, wire: Any, arguments: Any) -> dict:
        """Authorise one call, forward it, and taint the chain with its output."""
        args_digest = sha256(canonical(arguments if arguments is not None else {}))
        try:
            _require(isinstance(arguments, dict) or arguments is None, "ARGUMENTS_MUST_BE_AN_OBJECT")
            qualified = qualified_from_wire(wire, self.upstreams)
            server, tool = qualified.split("/", 1)
            if self.upstreams[server].list_changed:
                self.refresh()
            offered = self.visible.get(qualified)
            if offered is None:
                raise McpGateDenied("TOOL_NOT_OFFERED")
            if offered.get("_hidden"):
                raise McpGateDenied(offered["_code"])
            contract = self.config.session
            _require(contract.expires_after_seconds is None
                     or self._clock() - self.started_at < contract.expires_after_seconds, "SESSION_EXPIRED")
            _require(contract.max_calls is None or sum(self.calls.values()) < contract.max_calls,
                     "SESSION_CALL_BUDGET_EXHAUSTED")
            policy = self.config.server(server).policy_for(tool)
            for argument, allowed in policy.scope.items():
                value = (arguments or {}).get(argument, _MISSING)
                # Type-strict: in Python True == 1, and a scope of [1] must not admit true.
                _require(any(type(value) is type(v) and value == v for v in allowed), "ARGUMENT_OUT_OF_SCOPE")
            used = self.calls.get(qualified, 0)
            _require(policy.max_calls is None or used < policy.max_calls, "TOOL_CALL_LIMIT_REACHED")
            approval = None
            if policy.approval:
                assert self.approvals is not None  # GateConfig.load refuses a config without a store
                approval = self.approvals.consume(
                    qualified, args_digest, approvers=self.config.approvers, spent=self.spent,
                    on_reject=lambda r, why: self._record("approval", qualified, "deny", why,
                                                          args_sha256=args_digest, request=r["id"]))
                if approval is None:
                    pending = self.approvals.request(qualified, args_digest, arguments or {})
                    self._record("approval", qualified, "hold", "APPROVAL_REQUIRED",
                                 args_sha256=args_digest, request=pending["id"])
                    if pending["new"]:
                        self._notify(pending)
                    return _refusal("APPROVAL_REQUIRED", (
                        f" Request {pending['id']} holds these exact arguments for a named person. "
                        "Retry the same call, unchanged, after it is approved; any change needs a new approval."))
            if approval is not None:
                # A person approved these exact arguments: they, not the content the
                # session read, are the authority. Everything else still applies.
                self.registry.resolve(qualified)
                self.chain.calls.append(qualified)
            else:
                self.registry.authorise_call(qualified, self.chain)
        except ToolSupplyDenied as exc:
            self._record("call", wire, "deny", str(exc), args_sha256=args_digest)
            return _refusal(str(exc))
        self.calls[qualified] = used + 1
        try:
            result = self.upstreams[server].call_tool(tool, arguments or {})
        except McpGateDenied as exc:
            self._record("call", qualified, "error", str(exc), args_sha256=args_digest)
            return _refusal(str(exc))
        # Output enters the chain whatever it says. Absorbing before returning
        # means the very next call is judged with this content counted.
        self.chain.absorb(qualified)
        extra = {"approval": approval["id"], "approved_by": approval["decided_by"]} if approval else {}
        if approval:
            self.spent.add(approval["id"])
        self._record("call", qualified, "allow", "AUTHORISED", args_sha256=args_digest,
                     result_sha256=sha256(canonical(result)), **extra)
        return result

    def _notify(self, pending: Mapping[str, Any]) -> None:
        """Tell approvers a call is waiting. Never the arguments; never blocking."""
        if not self.config.notify_url:
            return
        import urllib.request

        body = {"event": "approval_requested", "gate": GATE_NAME, "request": pending["id"],
                "tool": pending["tool"], "args_sha256": pending["args_sha256"],
                "requested_at": pending["requested_at"],
                "review": f"fssaira mcp approvals --config <gate.yaml>  (request {pending['id']})"}
        request = urllib.request.Request(self.config.notify_url, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(request, timeout=5).close()  # noqa: S310 - scheme checked at load
        except Exception:  # noqa: BLE001 - a failed notification must not change the decision
            self._record("notify", pending["tool"], "error", "NOTIFY_FAILED", request=pending["id"])

    def _record(self, event: str, subject: str, decision: str, code: str, **extra: Any) -> None:
        self.receipts.append(event=event, subject=subject, decision=decision, code=code,
                             chain_untrusted=self.chain.untrusted, **self.context, **extra)

    def status(self) -> dict:
        return {"tools": sorted(k for k, v in self.visible.items() if not v.get("_hidden")),
                "hidden": {k: v["_code"] for k, v in sorted(self.visible.items()) if v.get("_hidden")},
                "chain_untrusted": self.chain.untrusted, "sources": sorted(self.chain.sources),
                "quarantined": dict(self.registry.quarantined()), "receipt_head": self.receipts.head}


_MISSING = object()


def _refusal(code: str, detail: str = "") -> dict:
    """A refusal the model can read and cannot argue with.

    Returned as a tool result with ``isError`` rather than a protocol error, as
    MCP recommends, so the model sees the reason and the host keeps running.
    """
    return {"isError": True, "content": [{"type": "text", "text": (
        f"Refused by the Trust by Construction gate: {code}. This decision is made "
        "outside the model and cannot be changed by rephrasing the request." + detail)}]}


# -- the host-facing server --------------------------------------------------------


def _reply(ident: Any, *, result: Any = None, error: dict | None = None) -> dict:
    message: dict = {"jsonrpc": "2.0", "id": ident}
    message.update({"error": error} if error else {"result": result})
    return message


def handle_message(gate: Gate, message: Any) -> dict | None:
    """One host message in, one reply out (None for notifications). Shared by stdio and HTTP."""
    if not isinstance(message, dict):
        return _reply(None, error={"code": -32600, "message": "invalid request"})
    method, ident, params = message.get("method"), message.get("id"), message.get("params") or {}
    if method is None or ident is None:
        return None  # notifications and stray responses need no answer
    if method == "initialize":
        requested = params.get("protocolVersion")
        return _reply(ident, result={
            "protocolVersion": requested if requested in PROTOCOL_VERSIONS else LATEST_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": GATE_NAME, "version": "1"},
            "instructions": ("Tools are named server__tool. Calls are checked by an independent "
                             "gate; a refusal names its reason and is final for this session.")})
    if method == "ping":
        return _reply(ident, result={})
    if method == "tools/list":
        return _reply(ident, result={"tools": gate.refresh()})
    if method == "tools/call":
        return _reply(ident, result=gate.call(params.get("name"), params.get("arguments")))
    return _reply(ident, error={"code": -32601, "message": f"method not offered by the gate: {method}"})


def serve(gate: Gate, stdin: IO[str] = sys.stdin, stdout: IO[str] = sys.stdout) -> None:
    """Speak MCP over stdio to the host until it closes the stream."""
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            reply: dict | None = _reply(None, error={"code": -32700, "message": "parse error"})
        else:
            reply = handle_message(gate, message)
        if reply is not None:
            stdout.write(json.dumps(reply, separators=(",", ":"), ensure_ascii=False) + "\n")
            stdout.flush()


def load_lock(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(data: Mapping[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                          encoding="utf-8")


__all__ = [
    "GATE_NAME", "LATEST_PROTOCOL", "LOCK_SCHEMA", "PROTOCOL_VERSIONS", "RECEIPT_SCHEMA",
    "UNDECLARED_POLICY", "UPSTREAM_REQUESTS_REFUSED", "WIRE_SEPARATOR", "Gate", "GateConfig", "HttpUpstream",
    "ApprovalStore", "McpGateCodes", "McpGateDenied", "McpToolRegistry", "ReceiptLog", "SessionContract", "ToolPolicy", "Upstream", "UpstreamSpec", "annotation_findings",
    "executable_hash", "handle_message", "load_lock", "approval_payload", "approval_signature_valid", "generate_approver_key", "check_upstream_url", "lock", "locked_governance", "open_upstream", "parse_approvers", "sign_approval", "tool_governance", "manifest_for", "model_text", "qualified_from_wire",
    "scan", "serve", "verify_receipts", "wire_name", "write_json",
]
