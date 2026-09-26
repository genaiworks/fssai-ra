"""The MCP gate as a shared service: one gateway, many callers, one session each.

``fssaira mcp serve`` runs one gate for one host over stdio. An organisation
running many agents wants one place to operate instead: a gateway every agent
host connects to over Streamable HTTP, with the same lock, the same policy and
one receipt log. This module provides it without weakening what a single gate
guarantees:

* **Each MCP session gets its own gate**, with its own upstream connections,
  call chain, budgets and expiry. One caller's session reading a hostile page
  never taints another caller's session.
* **Callers authenticate.** A caller presents a bearer token; the gateway
  stores only the token's SHA-256, never the token. A session is bound to the
  caller that opened it, so a session id presented under another caller's
  token is unknown.
* **Callers can be narrowed.** A caller entry may list the qualified tools it
  may use; everything else is hidden and refused (``CALLER_NOT_PERMITTED``).
* **Browser attacks are refused.** A request carrying an ``Origin`` header not
  on the allow-list is rejected, which is what the MCP specification asks of
  HTTP servers to stop DNS rebinding.
* **Capacity is bounded.** Sessions are capped and expire when idle.
* **Every receipt names the caller and the session.**

A gateway with no registered callers may only listen on loopback: an
unauthenticated gateway on a network interface is refused at start
(``GATEWAY_NEEDS_CLIENT_AUTH``).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .mcp_gate import (
    Gate,
    GateConfig,
    McpGateDenied,
    ReceiptLog,
    _reply,
    handle_message,
)

LOOPBACK = ("127.0.0.1", "::1", "localhost")
MAX_BODY_BYTES = 4 * 1024 * 1024


class GatewayCodes:
    """Reasons the gateway refuses to start or to serve a request."""

    GATEWAY_NEEDS_CLIENT_AUTH = "GATEWAY_NEEDS_CLIENT_AUTH"
    GATEWAY_CLIENT_INVALID = "GATEWAY_CLIENT_INVALID"
    GATEWAY_UNAUTHENTICATED = "GATEWAY_UNAUTHENTICATED"
    GATEWAY_SESSION_UNKNOWN = "GATEWAY_SESSION_UNKNOWN"
    GATEWAY_AT_CAPACITY = "GATEWAY_AT_CAPACITY"
    GATEWAY_ORIGIN_REFUSED = "GATEWAY_ORIGIN_REFUSED"
    GATEWAY_BODY_TOO_LARGE = "GATEWAY_BODY_TOO_LARGE"


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_client_token() -> tuple[str, str]:
    """A fresh bearer token and the digest to put in the gateway policy."""
    token = secrets.token_urlsafe(32)
    return token, token_digest(token)


@dataclass(frozen=True)
class Client:
    name: str
    token_sha256: str
    tools: frozenset[str] | None = None


@dataclass(frozen=True)
class GatewayPolicy:
    clients: tuple[Client, ...] = ()
    allowed_origins: frozenset[str] = frozenset()
    max_sessions: int = 16
    idle_seconds: float = 900.0

    @classmethod
    def parse(cls, raw: Any) -> GatewayPolicy:
        raw = raw or {}
        if not isinstance(raw, dict):
            raise McpGateDenied("GATEWAY_CLIENT_INVALID")
        clients = []
        for name, entry in (raw.get("clients") or {}).items():
            if not (isinstance(entry, dict) and isinstance(entry.get("token_sha256"), str)
                    and len(entry["token_sha256"]) == 64 and str(name).strip()):
                raise McpGateDenied("GATEWAY_CLIENT_INVALID")
            tools = entry.get("tools")
            if tools is not None and not (isinstance(tools, list) and all(
                    isinstance(t, str) and t.count("/") == 1 for t in tools)):
                raise McpGateDenied("GATEWAY_CLIENT_INVALID")
            clients.append(Client(str(name), entry["token_sha256"].lower(),
                                  frozenset(tools) if tools is not None else None))
        max_sessions = raw.get("max_sessions", 16)
        idle = raw.get("idle_seconds", 900)
        if type(max_sessions) is not int or max_sessions < 1 or not isinstance(idle, (int, float)) or idle <= 0:
            raise McpGateDenied("GATEWAY_CLIENT_INVALID")
        return cls(tuple(clients), frozenset(raw.get("allowed_origins") or ()), max_sessions, float(idle))

    @classmethod
    def load(cls, config_path: str | Path) -> GatewayPolicy:
        import yaml

        raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
        return cls.parse(raw.get("gateway"))

    def authenticate(self, header: str | None) -> Client | None:
        if not self.clients:
            return Client("local", "")
        if not header or not header.startswith("Bearer "):
            return None
        presented = token_digest(header[7:].strip())
        for client in self.clients:
            if hmac.compare_digest(presented, client.token_sha256):
                return client
        return None


@dataclass
class _Session:
    gate: Gate
    client: Client
    last_used: float = field(default_factory=time.monotonic)
    #: One request at a time per session: a gate's upstream connections are sequential.
    lock: threading.Lock = field(default_factory=threading.Lock)


class Gateway:
    """Sessions, each a gate, behind one authenticated HTTP endpoint."""

    def __init__(self, config: GateConfig, lock_data: Mapping[str, Any], policy: GatewayPolicy, *,
                 receipts: ReceiptLog, clock: Callable[[], float] = time.time) -> None:
        self.config, self.lock_data, self.policy = config, lock_data, policy
        self.receipts, self._clock = receipts, clock
        self.sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def _expire(self) -> None:
        cutoff = time.monotonic() - self.policy.idle_seconds
        for sid in [s for s, v in self.sessions.items() if v.last_used < cutoff]:
            self.sessions.pop(sid).gate.close()

    def open_session(self, client: Client) -> str:
        with self._lock:
            self._expire()
            if len(self.sessions) >= self.policy.max_sessions:
                raise McpGateDenied("GATEWAY_AT_CAPACITY")
            sid = secrets.token_hex(16)
            gate = Gate(self.config, self.lock_data, receipts=self.receipts, clock=self._clock,
                        allowed_tools=client.tools, context={"caller": client.name, "session": sid[:12]})
            gate.start()
            self.sessions[sid] = _Session(gate, client)
            return sid

    def session(self, sid: str | None, client: Client) -> _Session:
        with self._lock:
            entry = self.sessions.get(sid or "")
            # A session belongs to the caller that opened it; to anyone else it does not exist.
            if entry is None or entry.client.name != client.name:
                raise McpGateDenied("GATEWAY_SESSION_UNKNOWN")
            entry.last_used = time.monotonic()
            return entry

    def close_session(self, sid: str | None, client: Client) -> None:
        entry = self.session(sid, client)
        with self._lock:
            self.sessions.pop(sid or "", None)
        entry.gate.close()

    def close(self) -> None:
        with self._lock:
            for entry in self.sessions.values():
                entry.gate.close()
            self.sessions.clear()


def make_server(gateway: Gateway, host: str, port: int) -> ThreadingHTTPServer:
    if not gateway.policy.clients and host not in LOOPBACK:
        raise McpGateDenied("GATEWAY_NEEDS_CLIENT_AUTH")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:
            pass

        def _send(self, status: int, body: Any = None, headers: Mapping[str, str] | None = None) -> None:
            data = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
            self.send_response(status)
            if body is not None:
                self.send_header("Content-Type", "application/json")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)

        def _refuse(self, status: int, code: str) -> None:
            self._send(status, {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": code}})

        def _admit(self) -> Client | None:
            origin = self.headers.get("Origin")
            if origin is not None and origin not in gateway.policy.allowed_origins:
                self._refuse(403, "GATEWAY_ORIGIN_REFUSED")
                return None
            client = gateway.policy.authenticate(self.headers.get("Authorization"))
            if client is None:
                self._refuse(401, "GATEWAY_UNAUTHENTICATED")
            return client

        def do_POST(self) -> None:  # noqa: N802 - http.server naming
            client = self._admit()
            if client is None:
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self._refuse(413, "GATEWAY_BODY_TOO_LARGE")
                return
            try:
                message = json.loads(self.rfile.read(length) or b"null")
            except json.JSONDecodeError:
                self._send(400, _reply(None, error={"code": -32700, "message": "parse error"}))
                return
            try:
                if isinstance(message, dict) and message.get("method") == "initialize":
                    sid = gateway.open_session(client)
                    entry = gateway.session(sid, client)
                    with entry.lock:
                        reply = handle_message(entry.gate, message)
                    self._send(200, reply, {"Mcp-Session-Id": sid})
                    return
                entry = gateway.session(self.headers.get("Mcp-Session-Id"), client)
            except McpGateDenied as exc:
                status = 503 if str(exc) == "GATEWAY_AT_CAPACITY" else 404
                self._refuse(status, str(exc))
                return
            with entry.lock:
                reply = handle_message(entry.gate, message)
            if reply is None:
                self._send(202)
            else:
                self._send(200, reply)

        def do_DELETE(self) -> None:  # noqa: N802 - http.server naming
            client = self._admit()
            if client is None:
                return
            try:
                gateway.close_session(self.headers.get("Mcp-Session-Id"), client)
            except McpGateDenied as exc:
                self._refuse(404, str(exc))
                return
            self._send(204)

        def do_GET(self) -> None:  # noqa: N802 - no server-initiated stream is offered
            self._send(405, None, {"Allow": "POST, DELETE"})

    return ThreadingHTTPServer((host, port), Handler)


__all__ = ["Client", "Gateway", "GatewayCodes", "GatewayPolicy", "make_server", "new_client_token",
           "token_digest"]
