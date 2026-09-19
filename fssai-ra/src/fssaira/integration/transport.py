"""A qualified outbound transport: the socket the destination contract assumed.

``DestinationPolicy`` decides what may be contacted. Until now nothing in the
repository actually contacted it, so five properties the paper relied on were
asserted rather than exercised: that the connection reaches the *pinned*
address rather than whatever a resolver later returns, that the peer's TLS
identity is verified and pinned to a public key, that a redirect is a new
authorisation decision rather than a followed hop, that the byte ceiling is
enforced on the wire rather than after the fact, and that deadlines bound the
transfer.

This module opens the socket and enforces those properties, and returns
:class:`TransportEvidence` describing what actually happened -- negotiated TLS
version, peer public-key pin, pinned address, bytes transferred, elapsed time.
``fssaira.integration.transport_harness`` stands up a loopback TLS server so
every property above is exercised against a real handshake in the offline test
suite.

What it still does not do: it is not the host firewall. A transport that
refuses an address does not prevent a compromised process from opening its own
socket. That is ``egress_default_deny`` in :mod:`fssaira.isolation`, and it is
measured there, not assumed here.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import os
import socket
import ssl
import time
from dataclasses import dataclass, field
from typing import Any

from .network import AuthorizedDestination, DestinationPolicy

#: Proxy variables silently redirect a pinned connection through a third party,
#: which defeats address pinning without any error. Their presence is refused
#: rather than ignored.
PROXY_VARIABLES = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy",
    "all_proxy", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE",
)

MAX_HEADER_BYTES = 8192
MAX_STATUS_LINE = 512


class TransportDenied(RuntimeError):
    """The transfer was refused. The reason is a stable code, never peer text."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


class RedirectRequiresReauthorization(TransportDenied):
    """The peer redirected. The new location is a new authorisation decision."""

    def __init__(self, status: int, location: str) -> None:
        super().__init__("REDIRECT_NOT_FOLLOWED", f"{status} -> {location[:200]}")
        self.status = status
        self.location = location[:200]


def spki_pin(certificate_der: bytes) -> str:
    """``sha256/<base64>`` over the peer's SubjectPublicKeyInfo.

    Pinning the key rather than the certificate survives ordinary renewal and
    still refuses a different key presented by a trusted-but-wrong issuer.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
    except ImportError as error:  # pragma: no cover - exercised by fail-closed test
        raise TransportDenied("PINNING_UNAVAILABLE", str(error)) from error
    certificate = x509.load_der_x509_certificate(certificate_der)
    info = certificate.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return "sha256/" + base64.b64encode(hashlib.sha256(info).digest()).decode()


@dataclass(frozen=True)
class TransportQualification:
    """The terms a transfer must meet before any byte is accepted."""

    #: Public-key pins. An empty set means the deployment has not pinned, which
    #: is permitted only when ``require_pinning`` is explicitly disabled.
    spki_pins: frozenset[str] = frozenset()
    minimum_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_3
    trust_store: str | None = None
    connect_timeout: float = 5.0
    read_timeout: float = 5.0
    total_deadline: float = 20.0
    require_pinning: bool = True
    #: Set only by the loopback harness; propagates into evidence.
    qualification_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.spki_pins, frozenset) or any(
                not isinstance(p, str) or not p.startswith("sha256/") or len(p) > 128
                for p in self.spki_pins):
            raise ValueError("pins must be sha256/<base64> strings")
        if self.require_pinning and not self.spki_pins:
            raise ValueError("pinning required but no public-key pin declared")
        if self.minimum_tls_version < ssl.TLSVersion.TLSv1_2:
            raise ValueError("TLS 1.2 is the floor")
        for name in ("connect_timeout", "read_timeout", "total_deadline"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not 0 < value <= 300:
                raise ValueError(f"invalid {name}")

    def context(self, *, hostname: str) -> ssl.SSLContext:
        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH, cafile=self.trust_store)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.minimum_version = self.minimum_tls_version
        # Session resumption would let a later transfer skip the pin check.
        context.options |= ssl.OP_NO_TICKET
        context.set_alpn_protocols(["http/1.1"])
        return context


@dataclass(frozen=True)
class TransportEvidence:
    """What happened on the wire. Published alongside a release decision."""

    url: str
    pinned_address: str
    port: int
    tls_version: str
    cipher: str
    peer_pin: str
    status: int
    bytes_received: int
    elapsed_seconds: float
    qualification_only: bool
    body_sha256: str
    limits: tuple[str, ...] = field(default=(
        "one transfer at one moment; not a statement about the peer's future behaviour",
        "verifies the peer's identity and key, not the correctness of its content",
    ))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "kind": "transport",
            "url": self.url,
            "pinned_address": self.pinned_address,
            "port": self.port,
            "tls_version": self.tls_version,
            "cipher": self.cipher,
            "peer_pin": self.peer_pin,
            "status": self.status,
            "bytes_received": self.bytes_received,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "qualification_only": self.qualification_only,
            "body_sha256": self.body_sha256,
            "limits": list(self.limits),
        }


class QualifiedTransport:
    """Fetch approved bytes from an approved destination under declared terms."""

    def __init__(
        self,
        policy: DestinationPolicy,
        qualification: TransportQualification,
        *,
        environ: dict[str, str] | None = None,
        clock=time.monotonic,
    ) -> None:
        if policy.qualification_only != qualification.qualification_only:
            raise ValueError("policy and qualification disagree about production status")
        self.policy = policy
        self.qualification = qualification
        self._environ = os.environ if environ is None else environ
        self._clock = clock
        self._pending = b""

    # -- public ------------------------------------------------------------

    def fetch(
        self,
        url: str,
        addresses: tuple[str, ...],
        *,
        classifications: frozenset[str] | set[str] = frozenset(),
    ) -> TransportEvidence:
        self._refuse_proxies()
        destination = self.policy.authorize(
            url, addresses, classifications=classifications)
        started = self._clock()
        deadline = started + self.qualification.total_deadline
        connection, address = self._connect(destination, deadline)
        try:
            peer_pin = self._verify_peer(connection)
            self._send_request(connection, destination, deadline)
            status, headers = self._read_headers(connection, deadline)
            self._refuse_redirect(status, headers)
            if status != 200:
                raise TransportDenied("UNEXPECTED_STATUS", str(status))
            body = self._read_body(connection, destination, headers, deadline)
            # Read the negotiated parameters while the socket is still open;
            # a closed SSLSocket reports neither version nor cipher.
            tls_version = connection.version() or "unknown"
            cipher = (connection.cipher() or ("unknown",))[0]
        finally:
            with contextlib.suppress(OSError):
                connection.close()
        return TransportEvidence(
            url=destination.url,
            pinned_address=address,
            port=destination.port,
            tls_version=tls_version,
            cipher=cipher,
            peer_pin=peer_pin,
            status=status,
            bytes_received=len(body),
            elapsed_seconds=self._clock() - started,
            qualification_only=destination.qualification_only,
            body_sha256=hashlib.sha256(body).hexdigest(),
        )

    # -- steps -------------------------------------------------------------

    def _refuse_proxies(self) -> None:
        present = sorted(name for name in PROXY_VARIABLES if self._environ.get(name))
        if present:
            raise TransportDenied("PROXY_CONFIGURED", ", ".join(present))

    def _remaining(self, deadline: float, code: str) -> float:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise TransportDenied("DEADLINE_EXCEEDED", code)
        return remaining

    def _connect(
        self, destination: AuthorizedDestination, deadline: float
    ) -> tuple[ssl.SSLSocket, str]:
        context = self.qualification.context(hostname=destination.tls_identity)
        errors: list[str] = []
        for address in destination.addresses:
            budget = min(self.qualification.connect_timeout,
                         self._remaining(deadline, "connect"))
            raw = None
            try:
                # The pinned literal address is used directly. No resolver runs
                # here -- not even the no-op lookup socket.create_connection
                # performs on a literal -- so neither a DNS answer that changes
                # between authorisation and transfer nor a hostile name-service
                # module can move the connection.
                raw = _open(address, destination.port, budget)
                raw.settimeout(min(self.qualification.read_timeout,
                                   self._remaining(deadline, "handshake")))
                secure = context.wrap_socket(
                    raw, server_hostname=destination.tls_identity, do_handshake_on_connect=True)
            except ssl.SSLError as error:
                _shut(raw)
                raise TransportDenied("TLS_REJECTED", str(error)) from error
            except OSError as error:
                _shut(raw)
                errors.append(f"{address}: {type(error).__name__}")
                continue
            negotiated = secure.version()
            if _version_rank(negotiated) < _version_rank(
                    self.qualification.minimum_tls_version.name.replace("TLSv1_", "TLSv1.")):
                secure.close()
                raise TransportDenied("TLS_VERSION_BELOW_FLOOR", str(negotiated))
            return secure, address
        raise TransportDenied("PINNED_ADDRESS_UNREACHABLE", "; ".join(errors))

    def _verify_peer(self, connection: ssl.SSLSocket) -> str:
        der = connection.getpeercert(binary_form=True)
        if not der:
            connection.close()
            raise TransportDenied("NO_PEER_CERTIFICATE")
        pin = spki_pin(der)
        if self.qualification.spki_pins and pin not in self.qualification.spki_pins:
            raise TransportDenied("PIN_MISMATCH", pin)
        return pin

    def _send_request(
        self, connection: ssl.SSLSocket, destination: AuthorizedDestination, deadline: float
    ) -> None:
        host = destination.tls_identity
        if destination.port != 443:
            host = f"{host}:{destination.port}"
        request = (
            f"GET {destination.path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "User-Agent: fssaira-qualified-transport/1\r\n"
            "Accept-Encoding: identity\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        connection.settimeout(self._remaining(deadline, "send"))
        connection.sendall(request)

    def _read_headers(
        self, connection: ssl.SSLSocket, deadline: float
    ) -> tuple[int, dict[str, str]]:
        buffer = bytearray()
        while b"\r\n\r\n" not in buffer:
            connection.settimeout(min(self.qualification.read_timeout,
                                      self._remaining(deadline, "headers")))
            try:
                chunk = connection.recv(1024)
            except TimeoutError as error:
                raise TransportDenied("READ_TIMEOUT", "headers") from error
            if not chunk:
                raise TransportDenied("TRUNCATED_RESPONSE", "headers")
            buffer.extend(chunk)
            if len(buffer) > MAX_HEADER_BYTES:
                raise TransportDenied("HEADER_LIMIT_EXCEEDED", str(len(buffer)))
        head, _, rest = bytes(buffer).partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        if not lines or len(lines[0]) > MAX_STATUS_LINE:
            raise TransportDenied("MALFORMED_STATUS")
        parts = lines[0].decode("latin-1").split(" ", 2)
        if len(parts) < 2 or not parts[0].startswith("HTTP/1.") or not parts[1].isdigit():
            raise TransportDenied("MALFORMED_STATUS", lines[0].decode("latin-1")[:80])
        headers: dict[str, str] = {}
        for line in lines[1:]:
            name, separator, value = line.decode("latin-1").partition(":")
            if not separator:
                raise TransportDenied("MALFORMED_HEADER")
            key = name.strip().lower()
            if key in headers:
                # Duplicate framing headers are the classic request-smuggling
                # ambiguity: two intermediaries can disagree about the body.
                raise TransportDenied("DUPLICATE_HEADER", key)
            headers[key] = value.strip()
        if "transfer-encoding" in headers:
            raise TransportDenied("CHUNKED_FRAMING_REFUSED", headers["transfer-encoding"])
        self._pending = rest
        return int(parts[1]), headers

    def _refuse_redirect(self, status: int, headers: dict[str, str]) -> None:
        if 300 <= status < 400:
            raise RedirectRequiresReauthorization(status, headers.get("location", ""))

    def _read_body(
        self,
        connection: ssl.SSLSocket,
        destination: AuthorizedDestination,
        headers: dict[str, str],
        deadline: float,
    ) -> bytes:
        declared = headers.get("content-length")
        if declared is None or not declared.isdigit():
            raise TransportDenied("LENGTH_REQUIRED", str(declared))
        expected = int(declared)
        if expected > destination.max_bytes:
            raise TransportDenied("BYTE_CEILING_EXCEEDED",
                                  f"declared {expected} > {destination.max_bytes}")
        body = bytearray(self._pending)
        self._pending = b""
        if len(body) > destination.max_bytes:
            raise TransportDenied("BYTE_CEILING_EXCEEDED", str(len(body)))
        while len(body) < expected:
            connection.settimeout(min(self.qualification.read_timeout,
                                      self._remaining(deadline, "body")))
            try:
                chunk = connection.recv(min(8192, expected - len(body) + 1))
            except TimeoutError as error:
                raise TransportDenied("READ_TIMEOUT", "body") from error
            if not chunk:
                raise TransportDenied("TRUNCATED_RESPONSE",
                                      f"{len(body)} of {expected}")
            body.extend(chunk)
            if len(body) > destination.max_bytes:
                # Refused on the wire, before the caller ever sees the overage.
                raise TransportDenied("BYTE_CEILING_EXCEEDED", str(len(body)))
        if len(body) != expected:
            raise TransportDenied("LENGTH_MISMATCH", f"{len(body)} != {expected}")
        return bytes(body)


def _open(address: str, port: int, timeout: float) -> socket.socket:
    """Connect to a literal address without consulting any name service."""
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    raw = socket.socket(family, socket.SOCK_STREAM)
    try:
        raw.settimeout(timeout)
        raw.connect((address, port))
    except OSError:
        _shut(raw)
        raise
    return raw


def _shut(raw: socket.socket | None) -> None:
    if raw is not None:
        with contextlib.suppress(OSError):
            raw.close()


_VERSION_ORDER = {"SSLv3": 0, "TLSv1": 1, "TLSv1.1": 2, "TLSv1.2": 3, "TLSv1.3": 4}


def _version_rank(version: str | None) -> int:
    return _VERSION_ORDER.get(version or "", -1)


__all__ = [
    "MAX_HEADER_BYTES", "PROXY_VARIABLES", "QualifiedTransport",
    "RedirectRequiresReauthorization", "TransportDenied", "TransportEvidence",
    "TransportQualification", "spki_pin",
]
