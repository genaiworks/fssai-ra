"""Clients switch to verified TLS only when configured, and refuse bad settings."""
import pytest

from fssaira.kafka_backend import kafka_security_config


def test_plaintext_by_default(monkeypatch):
    monkeypatch.delenv("FSSAI_KAFKA_SECURITY_PROTOCOL", raising=False)
    assert kafka_security_config() == {}


def test_kafka_tls_verifies_ca_and_host(monkeypatch):
    monkeypatch.setenv("FSSAI_KAFKA_SECURITY_PROTOCOL", "ssl")
    monkeypatch.setenv("FSSAI_KAFKA_SSL_CA_LOCATION", "/tls/ca.crt")
    assert kafka_security_config() == {
        "security.protocol": "SSL",
        "ssl.endpoint.identification.algorithm": "https",
        "ssl.ca.location": "/tls/ca.crt",
    }


def test_unsupported_kafka_protocol_is_refused(monkeypatch):
    monkeypatch.setenv("FSSAI_KAFKA_SECURITY_PROTOCOL", "SASL_PLAINTEXT")
    with pytest.raises(ValueError):
        kafka_security_config()


def test_redis_tls_url_uses_the_configured_ca(monkeypatch):
    import redis

    from fssaira.redis_backend import connect_redis

    captured = {}

    def fake_from_url(url, **kwargs):
        captured.update(url=url, **kwargs)
        return "client"

    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(fake_from_url))
    monkeypatch.setenv("FSSAI_REDIS_CA_FILE", "/tls/ca.crt")
    connect_redis("rediss://:pw@redis:6379/0")
    assert captured["ssl_ca_certs"] == "/tls/ca.crt"
    assert captured["ssl_cert_reqs"] == "required" and captured["ssl_check_hostname"] is True
    captured.clear()
    connect_redis("redis://:pw@redis:6379/0")
    assert "ssl_ca_certs" not in captured


def test_dev_certificates_name_each_service(tmp_path):
    import importlib.util
    from pathlib import Path

    from cryptography import x509

    spec = importlib.util.spec_from_file_location(
        "make_dev_certs", Path(__file__).resolve().parents[1] / "scripts/make_dev_certs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.make(tmp_path)
    ca = x509.load_pem_x509_certificate((tmp_path / "ca.crt").read_bytes())
    for service in module.SERVICES:
        cert = x509.load_pem_x509_certificate((tmp_path / f"{service}.crt").read_bytes())
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        assert service in names.get_values_for_type(x509.DNSName)
        cert.verify_directly_issued_by(ca)
        assert (tmp_path / f"{service}.key").stat().st_mode & 0o077 == 0
    assert (tmp_path / "kafka.pem").read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")


def test_dev_certificates_pass_a_strict_tls_handshake(tmp_path):
    """Python 3.13+ verifies strictly by default; the certificates must satisfy it."""
    import importlib.util
    import ssl
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "make_dev_certs", Path(__file__).resolve().parents[1] / "scripts/make_dev_certs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.make(tmp_path)

    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(tmp_path / "redis.crt", tmp_path / "redis.key")
    client_ctx = ssl.create_default_context(cafile=str(tmp_path / "ca.crt"))
    client_ctx.verify_flags |= getattr(ssl, "VERIFY_X509_STRICT", 0)

    def handshake(hostname):
        c_in, c_out, s_in, s_out = (ssl.MemoryBIO() for _ in range(4))
        client = client_ctx.wrap_bio(c_in, c_out, server_hostname=hostname)
        server = server_ctx.wrap_bio(s_in, s_out, server_side=True)
        for _ in range(10):
            for end, outgoing, incoming in ((client, c_out, s_in), (server, s_out, c_in)):
                try:
                    end.do_handshake()
                except ssl.SSLWantReadError:
                    pass
                incoming.write(outgoing.read())
        return client.version()

    assert handshake("redis") in {"TLSv1.2", "TLSv1.3"}
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake("not-redis")
