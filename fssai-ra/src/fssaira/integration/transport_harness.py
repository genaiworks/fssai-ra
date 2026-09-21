"""A controlled TLS peer, so transport claims are exercised rather than asserted.

The harness generates a private CA and a leaf certificate at run time, serves
them from a loopback socket, and can be told to misbehave in each of the ways a
transport contract must survive: present the wrong key, present the wrong name,
redirect, overrun the byte ceiling, under-deliver a declared body, stall past
the deadline, or offer chunked framing.

Nothing here is a network peer in any meaningful sense, and the module says so
in the evidence it produces: every destination it serves is authorised under
``qualification_only``, which the promotion gate refuses to accept as
production transport evidence. Its value is that the socket, the handshake, the
pin comparison, the framing parser and the ceiling are the *same code paths* a
deployment would run.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import socket
import ssl
import threading
from dataclasses import dataclass
from pathlib import Path

from .network import DestinationPolicy
from .transport import QualifiedTransport, TransportQualification, spki_pin

#: Reserved for documentation and testing; never resolvable (RFC 6761).
HARNESS_HOSTNAME = "qualification.invalid"


@dataclass
class ServerBehaviour:
    """How the controlled peer replies. Defaults are a well-behaved peer."""

    status: int = 200
    body: bytes = b"approved-artifact-bytes"
    #: Announce a different length than is sent, to exercise framing checks.
    declared_length: int | None = None
    location: str = ""
    chunked: bool = False
    omit_length: bool = False
    duplicate_length: bool = False
    #: Seconds to stall before replying, to exercise deadlines.
    stall_seconds: float = 0.0
    #: Send more than the declared length, to exercise the wire-level ceiling.
    overrun_bytes: int = 0


def _materials(tmp: Path, *, hostname: str = HARNESS_HOSTNAME,
               key_seed: int = 1) -> tuple[Path, Path, Path, str]:
    """Generate a CA and a leaf for ``hostname``; return paths and the leaf pin."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    now = _dt.datetime.now(_dt.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "fssaira qualification CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(minutes=5))
        .not_valid_after(now + _dt.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
                       critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number() + key_seed)
        .not_valid_before(now - _dt.timedelta(minutes=5))
        .not_valid_after(now + _dt.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                       critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()),
                       critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    ca_path = tmp / "ca.pem"
    cert_path = tmp / "leaf.pem"
    key_path = tmp / "leaf.key"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(leaf_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    pin = spki_pin(leaf.public_bytes(serialization.Encoding.DER))
    return ca_path, cert_path, key_path, pin


class LoopbackTLSServer:
    """A single-connection TLS peer on 127.0.0.1 with declared misbehaviour."""

    def __init__(
        self,
        tmp: Path,
        behaviour: ServerBehaviour | None = None,
        *,
        hostname: str = HARNESS_HOSTNAME,
        maximum_tls_version: ssl.TLSVersion | None = None,
        key_seed: int = 1,
    ) -> None:
        self.behaviour = behaviour or ServerBehaviour()
        self.hostname = hostname
        self.ca_path, cert, key, self.pin = _materials(
            tmp, hostname=hostname, key_seed=key_seed)
        self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._context.minimum_version = ssl.TLSVersion.TLSv1_2
        if maximum_tls_version is not None:
            self._context.maximum_version = maximum_tls_version
        self._context.load_cert_chain(cert, key)
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(4)
        self.port = self._listener.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> LoopbackTLSServer:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def close(self) -> None:
        self._stop.set()
        # close() alone need not interrupt another thread blocked in accept()
        # on Linux. Shut down the listening socket before releasing its fd.
        with contextlib.suppress(OSError):
            self._listener.shutdown(socket.SHUT_RDWR)
        with contextlib.suppress(OSError):
            self._listener.close()
        self._thread.join(timeout=2)

    # -- the peer ----------------------------------------------------------

    def _response(self) -> bytes:
        behaviour = self.behaviour
        body = behaviour.body
        if behaviour.chunked:
            head = (f"HTTP/1.1 {behaviour.status} OK\r\n"
                    "Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
            return head.encode() + b"%x\r\n" % len(body) + body + b"\r\n0\r\n\r\n"
        lines = [f"HTTP/1.1 {behaviour.status} OK"]
        if behaviour.location:
            lines.append(f"Location: {behaviour.location}")
        declared = behaviour.declared_length
        if declared is None:
            declared = len(body)
        if not behaviour.omit_length:
            lines.append(f"Content-Length: {declared}")
            if behaviour.duplicate_length:
                lines.append(f"Content-Length: {declared + 1}")
        lines.append("Connection: close")
        head = "\r\n".join(lines) + "\r\n\r\n"
        return head.encode() + body + (b"X" * behaviour.overrun_bytes)

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                raw, _ = self._listener.accept()
            except OSError:
                return
            if self._stop.is_set():
                raw.close()
                return
            raw.settimeout(5)
            try:
                with self._context.wrap_socket(raw, server_side=True) as connection:
                    connection.settimeout(5)
                    try:
                        connection.recv(4096)
                    except OSError:
                        continue
                    if self.behaviour.stall_seconds and self._stop.wait(
                            self.behaviour.stall_seconds):
                        return
                    connection.sendall(self._response())
            except (OSError, ssl.SSLError):
                continue

    # -- ready-made client -------------------------------------------------

    def url(self, path: str = "/artifacts/report.txt") -> str:
        return f"https://{self.hostname}:{self.port}{path}"

    def policy(self, *, path_prefixes: tuple[str, ...] = ("/artifacts/",),
               max_bytes: int = 4096) -> DestinationPolicy:
        return DestinationPolicy(
            self.hostname, path_prefixes, max_bytes,
            port=self.port, qualification_only=True)

    def qualification(
        self,
        *,
        pins: frozenset[str] | None = None,
        minimum_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2,
        total_deadline: float = 10.0,
        read_timeout: float = 5.0,
    ) -> TransportQualification:
        return TransportQualification(
            spki_pins=frozenset({self.pin}) if pins is None else pins,
            minimum_tls_version=minimum_tls_version,
            trust_store=str(self.ca_path),
            connect_timeout=2.0,
            read_timeout=read_timeout,
            total_deadline=total_deadline,
            qualification_only=True,
        )

    def transport(self, **kwargs) -> QualifiedTransport:
        return QualifiedTransport(
            self.policy(**{k: v for k, v in kwargs.items()
                           if k in ("path_prefixes", "max_bytes")}),
            self.qualification(**{k: v for k, v in kwargs.items()
                                  if k in ("pins", "minimum_tls_version",
                                           "total_deadline", "read_timeout")}),
            environ={},
        )


__all__ = ["HARNESS_HOSTNAME", "LoopbackTLSServer", "ServerBehaviour"]
