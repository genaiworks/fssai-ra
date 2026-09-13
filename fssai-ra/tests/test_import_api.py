import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from fssaira import __version__
from fssaira.import_api import create_import_app


class RecordingPublisher:
    def __init__(self):
        self.items = []

    def append(self, value, key="", trace_id=""):
        self.items.append((key, value))
        return len(self.items) - 1


class FailingPublisher:
    def append(self, value, key="", trace_id=""):
        raise RuntimeError("broker unavailable")


def signed_payload(data="A safely imported observation."):
    key = "test-source-key"
    return key, {
        "source": "research-partner",
        "content_type": "text/plain",
        "data": data,
        "signature": hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest(),
    }


def test_import_gateway_accepts_authentic_input_and_publishes_inward():
    publisher = RecordingPublisher()
    key, payload = signed_payload()
    client = TestClient(create_import_app(
        publisher=publisher, trusted_keys={"research-partner": key}
    ))

    response = client.post("/v1/imports", json=payload)

    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"status": "accepted", "broker_offset": 0}
    key, value = publisher.items[0]
    assert key == "research-partner"
    assert value["source"] == "research-partner"
    assert value["text"] == "A safely imported observation."
    assert value["stripped"] == []
    # The inward record carries a content hash so a downstream decision can be
    # bound to the exact bytes that crossed the boundary.
    assert value["content_hash"] == hashlib.sha256(value["text"].encode()).hexdigest()


def test_import_gateway_quarantines_bad_signature_without_publishing():
    publisher = RecordingPublisher()
    _key, payload = signed_payload()
    payload["signature"] = "0" * 64
    client = TestClient(create_import_app(
        publisher=publisher, trusted_keys={"research-partner": "irrelevant"}
    ))

    response = client.post("/v1/imports", json=payload)

    assert response.status_code == 422
    assert response.json()["status"] == "quarantined"
    assert publisher.items == []


def test_import_gateway_has_no_readback_route():
    publisher = RecordingPublisher()
    app = create_import_app(publisher=publisher, trusted_keys={})
    paths = set(app.openapi()["paths"])

    assert paths == {"/health", "/v1/imports"}
    assert set(app.openapi()["paths"]["/v1/imports"]) == {"post"}


def test_import_gateway_schema_uses_the_package_version():
    app = create_import_app(publisher=RecordingPublisher(), trusted_keys={})

    assert app.openapi()["info"]["version"] == __version__


def test_import_gateway_rejects_malformed_source_key_configuration(monkeypatch):
    monkeypatch.setenv("FSSAI_IMPORT_SOURCE_KEYS_JSON", "[]")

    with pytest.raises(ValueError, match="source names"):
        create_import_app(publisher=RecordingPublisher())


def test_import_gateway_rejects_non_positive_size_limit(monkeypatch):
    monkeypatch.setenv("FSSAI_IMPORT_MAX_BYTES", "0")

    with pytest.raises(ValueError, match="positive integer"):
        create_import_app(publisher=RecordingPublisher(), trusted_keys={})


def test_import_gateway_persists_quarantine_evidence_across_restart(tmp_path, monkeypatch):
    audit_path = tmp_path / "import-audit.sqlite3"
    monkeypatch.setenv("FSSAI_IMPORT_AUDIT_PATH", str(audit_path))
    publisher = RecordingPublisher()
    _key, payload = signed_payload()
    payload["signature"] = "0" * 64

    with TestClient(create_import_app(
        publisher=publisher, trusted_keys={"research-partner": "irrelevant"}
    )) as first:
        assert first.get("/health").json()["audit_durable"] is True
        assert first.post("/v1/imports", json=payload).status_code == 422

    second_app = create_import_app(publisher=publisher, trusted_keys={})
    try:
        records = second_app.state.audit_evidence.find("quarantine")
        assert len(records) == 1
        assert records[0].payload["source"] == "research-partner"
    finally:
        second_app.state.audit_database.close()


def test_import_gateway_records_an_unclosed_intent_when_delivery_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("FSSAI_IMPORT_AUDIT_PATH", str(tmp_path / "audit.sqlite3"))
    key, payload = signed_payload()
    app = create_import_app(
        publisher=FailingPublisher(), trusted_keys={"research-partner": key}
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.post("/v1/imports", json=payload).status_code == 500
        assert len(app.state.audit_evidence.find("ingest_intent")) == 1
        assert len(app.state.audit_evidence.find("ingest_delivery_failed")) == 1
        assert app.state.audit_evidence.find("ingest") == []
    finally:
        app.state.audit_database.close()
