import hashlib
import hmac

from fastapi.testclient import TestClient

from fssaira.import_api import create_import_app


class RecordingPublisher:
    def __init__(self):
        self.items = []

    def append(self, value, key="", trace_id=""):
        self.items.append((key, value))
        return len(self.items) - 1


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
