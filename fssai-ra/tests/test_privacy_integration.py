"""Hostile and legitimate paths through the opt-in privacy reference profile."""
import hashlib
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from fssaira.api import create_app
from fssaira.control_plane import ControlPlane
from fssaira.encrypted_records import EncryptedRecordSource
from fssaira.key_custody import CustodyDenied, KeyCustody
from fssaira.model_registry import ManifestPublisher, ModelAttestationDenied, ModelRegistry
from fssaira.models.deterministic import DeterministicModel
from fssaira.privacy_pipeline import ErasureService
from fssaira.privacy_runtime import PrivacyConfiguration
from fssaira.privacy_vault import TOKEN_PATTERN, TokenVault, VaultDenied
from fssaira.profiles import ApplicationProfile
from fssaira.security import AuthConfig, Authenticator


def custody_fixture():
    custody = KeyCustody()
    credential = custody.register_principal("trusted-test-service", ["encrypt", "decrypt", "erase", "backup"])
    vault = TokenVault(custody, credential)
    records = EncryptedRecordSource({"name": "identity", "note": "restricted"}, custody,
                                    writer_credential=credential, reader_credential=credential)
    return custody, credential, vault, records


def test_vault_does_not_retain_plaintext_lookup_keys_and_erased_cache_cannot_be_used():
    custody, credential, vault, _ = custody_fixture()
    token = vault.token_for(session_id="tenant/session", subject="S1", kind="NAME", value="Alice Example")
    assert "Alice Example" not in repr(vault._forward)
    assert vault.restore(credential, session_id="tenant/session", token=token) == "Alice Example"
    custody.destroy_subject(credential, "S1", erased_by="owner", reason="expired")
    with pytest.raises(CustodyDenied):
        vault.token_for(session_id="tenant/session", subject="S1", kind="NAME", value="Alice Example")
    vault.forget_subject("S1")
    assert not vault.entries_for("S1") and not vault._forward


@pytest.mark.parametrize("kind", ["N", "123", "", "_id", "NAME"])
def test_every_emitted_token_is_restorable(kind):
    _, credential, vault, _ = custody_fixture()
    token = vault.token_for(session_id="s", subject="S1", kind=kind, value="Alice Example")
    assert TOKEN_PATTERN.fullmatch(token)
    assert vault.restore_text(credential, session_id="s", text=token, subjects=["S1"]) == ("Alice Example", 1)


def test_tokenization_does_not_replace_identifiers_inside_generated_or_existing_tokens():
    _, credential, vault, _ = custody_fixture()
    text, count = vault.tokenize_text("Alice Example and NAME", session_id="s",
        identifiers=[("S1", "NAME", "Alice Example"), ("S2", "NAME", "NAME")])
    assert count == 2 and len(TOKEN_PATTERN.findall(text)) == 2
    assert vault.restore_text(credential, session_id="s", text=text, subjects=["S1", "S2"])[0] == "Alice Example and NAME"
    assert vault.tokenize_text(text, session_id="s", identifiers=[("S2", "NAME", "NAME")]) == (text, 0)


def test_record_load_failure_is_atomic_and_restore_preserves_version_high_water():
    _, _, _, records = custody_fixture()
    records.load("S1", {"name": "old"})
    snapshot = records.snapshot()
    with pytest.raises(KeyError):
        records.load("S1", {"name": "new", "undeclared": "bad"})
    assert records.fetch("S1", ["name"])["name"] == "old"
    assert records._row("S1", "name").version == 1
    records.load("S1", {"name": "v2"})
    records.restore_snapshot(snapshot)
    records.load("S1", {"name": "v3"})
    assert records._row("S1", "name").version == 3


def test_new_record_instance_restores_snapshot_version():
    custody, credential, _, records = custody_fixture()
    records.load("S1", {"name": "v1"})
    records.load("S1", {"name": "v2"})
    fresh = EncryptedRecordSource({"name": "identity"}, custody,
                                  writer_credential=credential, reader_credential=credential)
    fresh.restore_snapshot(records.snapshot())
    fresh.load("S1", {"name": "v3"})
    assert fresh._row("S1", "name").version == 3


def test_erasure_verification_does_not_restore_over_live_custody():
    custody, credential, vault, records = custody_fixture()
    records.load("S1", {"name": "Alice Example"})
    backup = custody.backup(credential)
    records.load("S2", {"name": "Bob Example"})
    service = ErasureService(custody, credential, record_source=records, vault=vault)
    service.with_backup_credential(credential)
    before = dict(custody._wrapped)
    report = service.verify("S1", fields=["name"], plaintexts=["Alice Example"],
                            custody_backups=[(backup, custody.journal)])
    assert not report.complete
    assert custody._wrapped == before
    assert records.fetch("S2", ["name"])["name"] == "Bob Example"


def test_erasure_probe_does_not_confuse_bad_credentials_with_destroyed_key():
    custody, credential, vault, records = custody_fixture()
    records.load("S1", {"name": "Alice Example"})
    vault.token_for(session_id="s", subject="S1", kind="NAME", value="Alice Example")
    service = ErasureService(custody, credential, record_source=records, vault=vault)
    report = service.verify("S1", fields=["name"], plaintexts=[], restore_credential="wrong")
    assert next(c.status for c in report.checks if c.location == "token_map") == "unverified"
    assert next(c.status for c in report.checks if c.location == "primary_record_store_bytes") == "unverified"


def test_restore_refuses_missing_or_rolled_back_erasure_history():
    custody, credential, _, records = custody_fixture()
    records.load("S1", {"name": "Alice"})
    old = custody.backup(credential)
    custody.destroy_subject(credential, "S1", erased_by="owner", reason="expired")
    with pytest.raises(CustodyDenied):
        custody.restore(credential, old, [])
    after = custody.backup(credential)
    fresh = KeyCustody()
    admin = fresh.register_principal("admin", ["backup"])
    with pytest.raises(CustodyDenied):
        fresh.restore(admin, after, [])


def app_fixture():
    profile = ApplicationProfile.load("profiles/healthcare_record_access.yaml")
    plane = ControlPlane(profile, model=DeterministicModel())
    custody = KeyCustody()
    credential = custody.register_principal("privacy-service", ["encrypt", "decrypt", "erase", "backup"])
    records = EncryptedRecordSource(profile.disclosure.field_classes, custody,
                                    writer_credential=credential, reader_credential=credential)
    vault = TokenVault(custody, credential)
    publisher = ManifestPublisher()
    registry = ModelRegistry(profile.disclosure.endpoints, publisher.trusted_keys, strict=True)
    manifest = publisher.issue(endpoint="on_premises_model", zone="on-premises", provider="fixture",
        model_id="synthetic-model", artifact=b"test-artifact", expires_at=4_000_000_000,
        allowed_classes=tuple(profile.disclosure.class_zones), allowed_purposes=profile.disclosure.purposes)
    registry.register(manifest)
    identity = [manifest.artifact_digest, manifest.model_id]
    config = PrivacyConfiguration(records, vault, {"patient_name": "NAME"}, credential,
                                  registry, lambda endpoint: tuple(identity))
    auth = Authenticator(AuthConfig(tokens={
        "owner": ("owner", ("healthcare_privacy_officer", "platform_operator")),
        "agent": ("agent", ("proposer",)), "other": ("other", ("proposer",)),
        "reviewer": ("reviewer", ("research_review_authority",)),
    }))
    app = create_app(plane, authenticator=auth, model_endpoint="on_premises_model",
                     disclosure_options={"privacy": config})
    client = TestClient(app)
    for subject, name in [("patient-1", "Alice Example"), ("patient-2", "Bob Example")]:
        response = client.post("/v1/disclosure/records", headers=header("owner"), json={
            "subject": subject, "fields": {"patient_name": name, "diagnosis": "Rare diagnosis for " + name}})
        assert response.status_code == 201, response.text
    return client, plane, config, identity


def header(name):
    return {"Authorization": "Bearer " + name}


def grant_context(client, *, purpose="treatment", session="tenant/session"):
    response = client.post("/v1/disclosure/grants", headers=header("owner"), json={
        "holder": "agent", "purpose": purpose, "subjects": ["patient-1"],
        "fields": ["patient_name", "diagnosis"]})
    assert response.status_code == 201, response.text
    return {"grant_id": response.json()["grant_id"], "purpose": purpose,
            "subjects": ["patient-1"], "fields": ["patient_name", "diagnosis"], "session_id": session}


def test_http_privacy_context_output_and_entitled_restoration():
    client, plane, config, _ = app_fixture()
    request = grant_context(client)
    response = client.post("/v1/disclosure/context", headers=header("agent"), json=request)
    assert response.status_code == 200, response.text
    values = response.json()["values"]
    assert "Alice Example" not in json.dumps(values) and "patient-1" not in json.dumps(values)
    assert b"Alice Example" not in config.records.raw_bytes()
    output = client.post("/v1/disclosure/outputs", headers=header("agent"), json={
        "session_id": request["session_id"], "content": "Alice Example needs support"})
    assert output.status_code == 201, output.text
    path = "/v1/disclosure/outputs/" + output.json()["output_id"] + "/release"
    payload = {"recipient": "treating_clinician", "purpose": "treatment"}
    released = client.post(path, headers=header("agent"), json=payload)
    assert released.status_code == 200 and "Alice Example" not in released.text
    restored = client.post(path, headers=header("agent"), json={**payload, "restore_identity": True})
    assert restored.status_code == 200, restored.text
    assert restored.json()["content"] == "Alice Example needs support"
    evidence = plane.evidence.find("identity_restoration")[-1].payload
    assert evidence["released_content_digest"] == hashlib.sha256(restored.json()["content"].encode()).hexdigest()
    assert "Alice Example" not in json.dumps([record.payload for record in plane.evidence])
    assert client.post(path, headers=header("other"), json=payload).status_code == 403
    assert client.post(path, headers=header("agent"), json={"recipient": "external_email", "purpose": "treatment"}).status_code == 403
    client.post(f"/v1/disclosure/grants/{request['grant_id']}/revoke", headers=header("owner"), json={"reason": "ended"})
    assert client.post(path, headers=header("agent"), json={**payload, "restore_identity": True}).status_code == 403


@pytest.mark.parametrize("attack", ["digest", "identity", "revoke", "expire", "purpose", "class"])
def test_http_model_registry_rejects_substitution_or_unapproved_use(attack):
    client, _, config, identity = app_fixture()
    request = grant_context(client)
    manifest = config.registry.manifest("on_premises_model")
    if attack == "digest":
        identity[0] = "wrong-digest"
    elif attack == "identity":
        identity[1] = "other-model"
    elif attack == "revoke":
        config.registry.revoke("on_premises_model")
    elif attack == "expire":
        # Re-sign as a trusted administrative update, not an invalid signature test.
        publisher = ManifestPublisher()
        config.registry._trusted = publisher.trusted_keys
        config.registry.register(publisher.sign(replace(manifest, expires_at=1)))
    elif attack == "purpose":
        request["purpose"] = "marketing"
    else:
        request["fields"] = ["undeclared"]
    response = client.post("/v1/disclosure/context", headers=header("agent"), json=request)
    assert response.status_code == 403, response.text
    assert "Alice Example" not in response.text


def test_strict_registry_requires_use_scope_and_explicit_reinstatement():
    _, _, config, identity = app_fixture()
    for arguments in [{}, {"purpose": "treatment"}, {"classes": ["highly-restricted"]}]:
        with pytest.raises(ModelAttestationDenied):
            config.registry.attest("on_premises_model", identity[0], **arguments)
    manifest = config.registry.manifest("on_premises_model")
    config.registry.revoke("on_premises_model")
    with pytest.raises(ModelAttestationDenied):
        config.registry.register(manifest)
    config.registry.register(manifest, reinstate=True)
    assert config.registry.attest("on_premises_model", identity[0], purpose="treatment", classes=["highly-restricted"])


def test_slash_session_declassification_uses_exact_source_and_case_insensitive_redaction():
    client, _, _, _ = app_fixture()
    request = grant_context(client, purpose="research", session="tenant/session")
    assert client.post("/v1/disclosure/context", headers=header("agent"), json=request).status_code == 200
    created = client.post("/v1/disclosure/outputs", headers=header("agent"), json={
        "session_id": request["session_id"], "content": "RARE DIAGNOSIS FOR ALICE EXAMPLE"})
    lowered = client.post("/v1/disclosure/outputs/" + created.json()["output_id"] + "/declassify",
                          headers=header("reviewer"), json={"rule": "deidentify_for_research"})
    assert lowered.status_code == 201, lowered.text
    # The privacy wrapper may replace names before the base redaction. The source
    # session must still remain exact so subsequent decisions never select 'tenant'.
    assert "ALICE EXAMPLE" not in lowered.json()["content"]


def test_model_exception_does_not_echo_sensitive_payload():
    client, plane, _, _ = app_fixture()
    request = grant_context(client)
    def fail(*args):
        raise RuntimeError("Alice Example and private-key-secret")
    plane.model.propose = fail
    response = client.post("/v1/propose-task", headers=header("agent"), json={
        "task": "review", "governed_context": request})
    assert response.status_code == 502, response.text
    assert "Alice Example" not in response.text and "private-key-secret" not in response.text


def test_model_task_and_evidence_are_tokenized_and_ungoverned_inference_denies():
    client, plane, _, _ = app_fixture()
    request = grant_context(client)
    captured = []
    def propose(task, evidence):
        captured.append(task + " ".join(e.text for e in evidence))
        return []
    plane.model.propose = propose
    response = client.post("/v1/propose-task", headers=header("agent"), json={
        "task": "review Alice Example for patient-1", "evidence": ["Alice Example needs help"],
        "governed_context": request})
    assert response.status_code == 200, response.text
    assert captured and "Alice Example" not in captured[0] and "patient-1" not in captured[0]
    assert client.post("/v1/propose-task", headers=header("agent"), json={"task": "review"}).status_code == 422


def test_unknown_output_contacts_deny_instead_of_unlabelled_restoration():
    client, _, _, _ = app_fixture()
    request = grant_context(client)
    unknown = client.post("/v1/disclosure/outputs", headers=header("agent"), json={
        "session_id": "unknown", "content": "unproven content"})
    assert unknown.status_code == 403
    client.post("/v1/disclosure/context", headers=header("agent"), json=request)
    response = client.post("/v1/disclosure/outputs", headers=header("agent"), json={
        "session_id": request["session_id"], "content": "Email newly-learned@example.org"})
    assert response.status_code == 403, response.text


def test_vault_cross_session_tokens_do_not_restore():
    _, credential, vault, _ = custody_fixture()
    token = vault.token_for(session_id="a", subject="S1", kind="NAME", value="Alice")
    with pytest.raises(VaultDenied):
        vault.restore(credential, session_id="b", token=token)


def test_base_gate_declassification_with_slash_session_redacts_actual_source_values():
    from fssaira.disclosure import DeclassificationAuthority, DisclosureGate, GrantAuthority
    from fssaira.evidence import EvidenceLedger
    policy = ApplicationProfile.load("profiles/healthcare_record_access.yaml").disclosure
    authority, declassifier = GrantAuthority(), DeclassificationAuthority()
    gate = DisclosureGate(policy, {"p1": {"diagnosis": "Private finding"}}, EvidenceLedger("writer"),
                          "writer", grant_keys=authority.trusted_keys,
                          declassification_keys=declassifier.trusted_keys)
    grant = authority.issue(grant_id="g", holder="agent", purpose="research", subjects=["p1"],
        fields=["diagnosis"], classes=["highly-restricted"], issued_by="owner", now=10, ttl_seconds=100)
    gate.assemble_context(requester="agent", session_id="tenant/session", grant=grant,
        purpose="research", subjects=["p1"], fields=["diagnosis"], model_endpoint="on_premises_model", now=11)
    output = gate.derive_output(requester="agent", session_id="tenant/session", content="PRIVATE FINDING for P1")
    approval = declassifier.approve(output, rule="deidentify_for_research", approver="reviewer",
                                    approver_role="research_review_authority", now=12)
    lowered = gate.declassify(output, rule="deidentify_for_research", approval=approval, now=13)
    assert "private finding" not in lowered.content.lower()
    assert "p1" not in lowered.content.lower()
    assert lowered.session_id == "tenant/session"


def test_failed_collection_cannot_be_published_as_partial_test_evidence(monkeypatch):
    import subprocess

    from scripts.generate_results import _test_count
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess([], 2, "tests/example.py: 5\n", "collection error"))
    with pytest.raises(RuntimeError, match="test collection failed"):
        _test_count()
