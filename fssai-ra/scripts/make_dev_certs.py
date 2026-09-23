#!/usr/bin/env python3
"""Create a private development CA and server certificates for the TLS overlay.

    python scripts/make_dev_certs.py --out deploy/certs

Writes ``ca.crt`` plus a key and certificate for each internal service, named for
its Compose host name so clients can verify the host, not just the CA. Keys are
written owner-only; the ``tls-init`` service in ``deploy/compose.tls.yaml`` copies
them into a volume with the owner each server process needs.

These certificates are for a local development stack only. A deployment should
issue certificates from the institution's own CA and rotate them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

SERVICES = ("postgres", "redis", "kafka", "minio", "iceberg-rest", "control-api", "import-gateway")
#: Kafka requires a client certificate (mutual TLS), so only these may read or write
#: topics. Each is written as .crt/.key and as a combined .pem (key then certificate).
KAFKA_CLIENTS = ("kafka-client-control-api", "kafka-client-import-gateway",
                 "kafka-client-spark", "kafka-client-admin")
TRUSTSTORE_PASSWORD = "changeit"


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _write(path: Path, data: bytes, mode: int) -> None:
    path.write_bytes(data)
    os.chmod(path, mode)


def _key_pem(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def make(out: Path, days: int = 365) -> None:
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca = (
        x509.CertificateBuilder()
        .subject_name(_name("fssaira development CA"))
        .issuer_name(_name("fssaira development CA"))
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                       critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
                       critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    _write(out / "ca.crt", ca.public_bytes(serialization.Encoding.PEM), 0o644)
    _write(out / "ca.key", _key_pem(ca_key), 0o600)
    # Java clients (Spark, the Iceberg catalog) read trust anchors from a keystore.
    # The password only protects integrity of public data, so it is the usual default.
    _write(out / "truststore.p12", pkcs12.serialize_java_truststore(
        [pkcs12.PKCS12Certificate(ca, b"fssaira-dev-ca")],
        serialization.BestAvailableEncryption(TRUSTSTORE_PASSWORD.encode())), 0o644)

    for service in SERVICES:
        key = ec.generate_private_key(ec.SECP256R1())
        names = [x509.DNSName(service), x509.DNSName("localhost"),
                 x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
        cert = (
            x509.CertificateBuilder()
            .subject_name(_name(service))
            .issuer_name(ca.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=days))
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            # Kafka validates its keystore with a self-handshake in which its own
            # certificate also acts as the client, so with client authentication
            # required the broker certificate needs clientAuth as well.
            .add_extension(x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.SERVER_AUTH]
                + ([ExtendedKeyUsageOID.CLIENT_AUTH] if service == "kafka" else [])),
                critical=False)
            # Key identifiers are required by strict verifiers, including Python 3.13's
            # default TLS context (VERIFY_X509_STRICT).
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                           critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                           critical=False)
            .sign(ca_key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        _write(out / f"{service}.crt", cert_pem, 0o644)
        _write(out / f"{service}.key", _key_pem(key), 0o600)
        # Kafka reads one PEM file holding the key followed by the certificate chain.
        if service == "kafka":
            _write(out / "kafka.pem", _key_pem(key) + cert_pem, 0o600)
    for client in KAFKA_CLIENTS:
        key = ec.generate_private_key(ec.SECP256R1())
        cert = (
            x509.CertificateBuilder()
            .subject_name(_name(client))
            .issuer_name(ca.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5))
            .not_valid_after(now + dt.timedelta(days=days))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
                           critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                           critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                           critical=False)
            .sign(ca_key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        _write(out / f"{client}.crt", cert_pem, 0o644)
        _write(out / f"{client}.key", _key_pem(key), 0o600)
        _write(out / f"{client}.pem", _key_pem(key) + cert_pem, 0o600)
    print(f"wrote a development CA, {len(SERVICES)} server and {len(KAFKA_CLIENTS)} Kafka "
          f"client certificates to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("deploy/certs"))
    parser.add_argument("--days", type=int, default=365)
    make(parser.parse_args().out, parser.parse_args().days)


if __name__ == "__main__":
    main()
