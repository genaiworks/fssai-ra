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
    # calls
    ARGUMENTS_MUST_BE_AN_OBJECT = "ARGUMENTS_MUST_BE_AN_OBJECT"
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

    @classmethod
    def parse(cls, value: Mapping[str, Any] | None) -> ToolPolicy:
        raw = dict(UNDECLARED_POLICY if value is None else value)
        unknown = set(raw) - {"power", "irreversibility", "effects", "trusted_output", "max_calls"}
        _require(not unknown, "UNKNOWN_TOOL_POLICY_FIELD")
        max_calls = raw.get("max_calls")
        _require(max_calls is None or (type(max_calls) is int and max_calls >= 0),
                 "INVALID_TOOL_CALL_LIMIT")
        return cls(power=raw.get("power", 3), irreversibility=raw.get("irreversibility", 2),
                   effects=frozenset(raw.get("effects", ())),
                   trusted_output=bool(raw.get("trusted_output", False)), max_calls=max_calls)


@dataclass(frozen=True)
class UpstreamSpec:
    """One stdio MCP server the gate launches on the host's behalf."""

    name: str
    command: tuple[str, ...]
    operator: str
    env: Mapping[str, str] = field(default_factory=dict)
    cwd: str | None = None
    pin_files: tuple[str, ...] = ()
    tools: Mapping[str, ToolPolicy] = field(default_factory=dict)

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
        return sha256(canonical({"command": list(self.command), "env": dict(self.env),
                                 "cwd": self.cwd, "files": files}))

    def policy_for(self, tool: str) -> ToolPolicy:
        return self.tools.get(tool) or ToolPolicy.parse(None)


@dataclass(frozen=True)
class GateConfig:
    servers: tuple[UpstreamSpec, ...]
    trusted_sources: frozenset[str] = frozenset()
    session_starts_untrusted: bool = False
    call_timeout: float = 60.0
    base: Path = Path(".")

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
            command = spec.get("command")
            if isinstance(command, str):
                command = [command]
            command = list(command or []) + list(spec.get("args") or [])
            _require(bool(command) and all(isinstance(p, str) for p in command),
                     "SERVER_COMMAND_REQUIRED")
            # Launch with the interpreter running the gate when a config says
            # ``python``, so examples work inside a virtual environment.
            if command[0] in ("python", "python3"):
                command[0] = sys.executable
            tools = {tool: ToolPolicy.parse(policy)
                     for tool, policy in (spec.get("tools") or {}).items()}
            servers.append(UpstreamSpec(
                name=name, command=tuple(command), operator=str(spec.get("operator") or ""),
                env={str(k): str(v) for k, v in (spec.get("env") or {}).items()},
                cwd=spec.get("cwd"), pin_files=tuple(spec.get("pin_files") or ()), tools=tools))
        trusted = frozenset(raw.get("trusted_sources") or ())
        for source in trusted:
            _require(isinstance(source, str) and source.count("/") == 1, "TRUSTED_SOURCE_MUST_BE_QUALIFIED")
        return cls(servers=tuple(servers), trusted_sources=trusted,
                   session_starts_untrusted=bool(raw.get("session_starts_untrusted", False)),
                   call_timeout=float(raw.get("call_timeout", 60.0)), base=path.resolve().parent)

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
        tools: list[dict] = []
        cursor = None
        for _ in range(64):  # a server that paginates forever does not get to stall the gate
            result = self.request("tools/list", {"cursor": cursor} if cursor else {})
            tools.extend(t for t in result.get("tools") or [] if isinstance(t, dict))
            cursor = result.get("nextCursor")
            if not cursor:
                self.list_changed = False
                return tools
        raise McpGateDenied("UPSTREAM_PAGINATION_UNBOUNDED")

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
        upstream = Upstream(spec, base=config.base, timeout=config.call_timeout)
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
                           "effects": sorted(policy.effects), "trusted_output": policy.trusted_output,
                           "max_calls": policy.max_calls,
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


# -- the gate ----------------------------------------------------------------------


class Gate:
    """One agent session: the host on one side, pinned upstream servers on the other."""

    def __init__(self, config: GateConfig, lock_data: Mapping[str, Any], *,
                 receipts: ReceiptLog, clock: Callable[[], float] = time.time) -> None:
        _require(lock_data.get("schema") == LOCK_SCHEMA, "UNSUPPORTED_LOCK_FILE")
        self.config = config
        self.receipts = receipts
        self.registry = McpToolRegistry(clock=clock)
        self.chain = CallChain(trusted_sources=config.trusted())
        if config.session_starts_untrusted:
            self.chain.absorb("host/untrusted-context")
        self.calls: dict[str, int] = {}
        self.upstreams: dict[str, Upstream] = {}
        self.visible: dict[str, dict] = {}
        self._locked = {s["name"]: s for s in lock_data.get("servers") or []}
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
            upstream = Upstream(spec, base=self.config.base, timeout=self.config.call_timeout,
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
            self.registry.authorise_call(qualified, self.chain)
            limit = self.config.server(server).policy_for(tool).max_calls
            used = self.calls.get(qualified, 0)
            _require(limit is None or used < limit, "TOOL_CALL_LIMIT_REACHED")
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
        self._record("call", qualified, "allow", "AUTHORISED", args_sha256=args_digest,
                     result_sha256=sha256(canonical(result)))
        return result

    def _record(self, event: str, subject: str, decision: str, code: str, **extra: Any) -> None:
        self.receipts.append(event=event, subject=subject, decision=decision, code=code,
                             chain_untrusted=self.chain.untrusted, **extra)

    def status(self) -> dict:
        return {"tools": sorted(k for k, v in self.visible.items() if not v.get("_hidden")),
                "hidden": {k: v["_code"] for k, v in sorted(self.visible.items()) if v.get("_hidden")},
                "chain_untrusted": self.chain.untrusted, "sources": sorted(self.chain.sources),
                "quarantined": dict(self.registry.quarantined()), "receipt_head": self.receipts.head}


def _refusal(code: str) -> dict:
    """A refusal the model can read and cannot argue with.

    Returned as a tool result with ``isError`` rather than a protocol error, as
    MCP recommends, so the model sees the reason and the host keeps running.
    """
    return {"isError": True, "content": [{"type": "text", "text": (
        f"Refused by the Trust by Construction gate: {code}. This decision is made "
        "outside the model and cannot be changed by rephrasing the request.")}]}


# -- the host-facing server --------------------------------------------------------


def serve(gate: Gate, stdin: IO[str] = sys.stdin, stdout: IO[str] = sys.stdout) -> None:
    """Speak MCP over stdio to the host until it closes the stream."""

    def reply(ident: Any, *, result: Any = None, error: dict | None = None) -> None:
        message: dict = {"jsonrpc": "2.0", "id": ident}
        message.update({"error": error} if error else {"result": result})
        stdout.write(json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n")
        stdout.flush()

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            reply(None, error={"code": -32700, "message": "parse error"})
            continue
        if not isinstance(message, dict):
            reply(None, error={"code": -32600, "message": "invalid request"})
            continue
        method, ident, params = message.get("method"), message.get("id"), message.get("params") or {}
        if method is None or ident is None:
            continue  # notifications and stray responses need no answer
        if method == "initialize":
            requested = params.get("protocolVersion")
            reply(ident, result={
                "protocolVersion": requested if requested in PROTOCOL_VERSIONS else LATEST_PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": GATE_NAME, "version": "1"},
                "instructions": ("Tools are named server__tool. Calls are checked by an independent "
                                 "gate; a refusal names its reason and is final for this session.")})
        elif method == "ping":
            reply(ident, result={})
        elif method == "tools/list":
            reply(ident, result={"tools": gate.refresh()})
        elif method == "tools/call":
            reply(ident, result=gate.call(params.get("name"), params.get("arguments")))
        else:
            reply(ident, error={"code": -32601, "message": f"method not offered by the gate: {method}"})


def load_lock(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(data: Mapping[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                          encoding="utf-8")


__all__ = [
    "GATE_NAME", "LATEST_PROTOCOL", "LOCK_SCHEMA", "PROTOCOL_VERSIONS", "RECEIPT_SCHEMA",
    "UNDECLARED_POLICY", "UPSTREAM_REQUESTS_REFUSED", "WIRE_SEPARATOR", "Gate", "GateConfig",
    "McpGateCodes", "McpGateDenied", "McpToolRegistry", "ReceiptLog", "ToolPolicy", "Upstream", "UpstreamSpec", "annotation_findings",
    "executable_hash", "load_lock", "lock", "manifest_for", "model_text", "qualified_from_wire",
    "scan", "serve", "verify_receipts", "wire_name", "write_json",
]
