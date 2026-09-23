#!/usr/bin/env python3
"""Synthetic encryption -> SQL -> governed context -> release -> evidence lab.

This is a one-process teaching harness, not a persistent custody implementation.
SQL retains ciphertext. Keys, grants and vault state deliberately expire with the
process. Use only the bundled synthetic input. See docs/PIPELINE_WALKTHROUGH.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP / "src"))

from fssaira.disclosure import DisclosureDenied, DisclosureGate, GrantAuthority  # noqa: E402
from fssaira.disclosure_sources import RecordNotFound  # noqa: E402
from fssaira.evidence import EvidenceLedger  # noqa: E402
from fssaira.evidence_notary import EvidenceNotary, verify_against_checkpoint  # noqa: E402
from fssaira.key_custody import Ciphertext, CustodyDenied, KeyCustody  # noqa: E402
from fssaira.privacy_pipeline import PrivacyGate  # noqa: E402
from fssaira.privacy_vault import TokenVault  # noqa: E402
from fssaira.profiles import ApplicationProfile  # noqa: E402


class LabSqlRecords:
    """Insert-only SQL RecordSource for this fixture; all field values are ciphertext.

    Identifiers are fixed in code; values use DB-API parameters. run_id isolates
    repeat runs. Custody authenticates subject/field/class/version as AEAD AAD.
    No database function ever receives a plaintext field or key.
    """

    def __init__(self, connection, custody, writer, reader, classes, *, postgres=False):
        self.db, self.custody = connection, custody
        self.writer, self.reader, self.classes = writer, reader, classes
        self.run_id = uuid.uuid4().hex
        self.placeholder = "%s" if postgres else "?"
        self.table = "pipeline_lab.encrypted_fields" if postgres else "encrypted_fields"
        self.fetch_count = 0
        if postgres:
            self.db.execute("CREATE SCHEMA IF NOT EXISTS pipeline_lab")
        binary = "BYTEA" if postgres else "BLOB"
        self.db.execute(f"""CREATE TABLE IF NOT EXISTS {self.table} (
            run_id TEXT NOT NULL, subject TEXT NOT NULL, field TEXT NOT NULL,
            data_class TEXT NOT NULL, version INTEGER NOT NULL CHECK (version > 0),
            key_generation INTEGER NOT NULL, nonce {binary} NOT NULL,
            body {binary} NOT NULL,
            PRIMARY KEY (run_id, subject, field),
            CHECK (length(nonce) = 12), CHECK (length(body) >= 16))""")
        self.db.commit()

    def query(self, sql, params=()):
        return self.db.execute(sql.replace("?", self.placeholder), params)

    def load(self, subject, fields):
        if set(fields) - set(self.classes):
            raise ValueError("undeclared fields")
        encrypted = [self.custody.encrypt(
            self.writer, subject=subject, field=name, data_class=self.classes[name],
            plaintext=value, version=1,
        ) for name, value in fields.items()]
        try:
            for item in encrypted:
                self.query(f"INSERT INTO {self.table} VALUES (?,?,?,?,?,?,?,?)", (
                    self.run_id, item.subject, item.field, item.data_class, item.version,
                    item.key_generation, item.nonce, item.body,
                ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def row(self, subject, field):
        result = self.query(f"""SELECT subject, field, data_class, version,
            key_generation, nonce, body FROM {self.table}
            WHERE run_id=? AND subject=? AND field=?""", (self.run_id, subject, field)).fetchone()
        if result is None:
            raise RecordNotFound(subject)
        return Ciphertext(*result[:5], bytes(result[5]), bytes(result[6]))

    def fetch(self, subject, fields):
        self.fetch_count += 1
        return {name: self.custody.decrypt(
            self.reader, self.row(subject, name), subject=subject, field=name,
        ) for name in fields}

    def encrypted_export(self):
        rows = self.query(f"""SELECT subject, field, data_class, version,
            key_generation, nonce, body FROM {self.table} WHERE run_id=?
            ORDER BY subject, field""", (self.run_id,)).fetchall()
        return [dict(zip(("subject", "field", "data_class", "version", "key_generation",
                          "nonce_hex", "body_hex"), (*r[:5], bytes(r[5]).hex(), bytes(r[6]).hex()),
                         strict=True)) for r in rows]


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def denied(call, exception):
    try:
        call()
    except exception as exc:
        return getattr(exc, "code", type(exc).__name__)
    raise RuntimeError("negative check unexpectedly succeeded")


def run(output: Path, *, postgres_dsn: str | None = None):
    output.mkdir(parents=True, exist_ok=False)
    if postgres_dsn:
        import psycopg
        connection = psycopg.connect(postgres_dsn)
    else:
        connection = sqlite3.connect(output / "records.sqlite3")
    try:
        return exercise(output, connection, postgres=bool(postgres_dsn))
    finally:
        connection.close()


def exercise(output, connection, *, postgres):
    fixture = json.loads((APP / "examples/pipeline/records.json").read_text())
    profile = ApplicationProfile.load(APP / "profiles/healthcare_record_access.yaml")
    custody = KeyCustody()
    writer = custody.register_principal("ingestion", ["encrypt"])
    reader = custody.register_principal("context-and-release-gate", ["decrypt"])
    eraser = custody.register_principal("erasure-officer", ["erase"])
    records = LabSqlRecords(connection, custody, writer, reader,
                            profile.disclosure.field_classes, postgres=postgres)
    for record in fixture["records"]:
        records.load(record["subject"], record["fields"])
    ciphertext_rows = records.encrypted_export()
    require(len(ciphertext_rows) == 4, "expected two subjects with two fields each")
    require(records.fetch("patient-1", ["patient_name"])["patient_name"] == "Alice Example",
            "SQL ciphertext round trip failed")
    original = records.row("patient-1", "patient_name")
    checks = {"sql_roundtrip": True}
    checks["ingest_cannot_decrypt"] = denied(lambda: custody.decrypt(
        writer, original, subject="patient-1", field="patient_name"), CustodyDenied)
    checks["moved_ciphertext_denied"] = denied(lambda: custody.decrypt(
        reader, original, subject="patient-2", field="patient_name"), CustodyDenied)
    corrupted = replace(original, body=bytes([original.body[0] ^ 1]) + original.body[1:])
    checks["tampered_ciphertext_denied"] = denied(lambda: custody.decrypt(
        reader, corrupted, subject="patient-1", field="patient_name"), CustodyDenied)
    checks["changed_version_denied"] = denied(lambda: custody.decrypt(
        reader, replace(original, version=2), subject="patient-1", field="patient_name"), CustodyDenied)

    evidence_token = secrets.token_hex(32)
    evidence = EvidenceLedger(evidence_token)
    authority = GrantAuthority(secret=secrets.token_hex(32))
    gate = DisclosureGate(profile.disclosure, records, evidence, evidence_token,
                          grant_keys=authority.trusted_keys)
    vault = TokenVault(custody, writer)
    privacy = PrivacyGate(gate, vault, records, identity_fields={"patient_name": "NAME"},
                          restore_credential=reader)
    now = time.time()
    grant = authority.issue(grant_id="lab-grant", holder="agent", purpose="treatment",
        subjects=["patient-1"], fields=["patient_name", "diagnosis"],
        classes=["synthetic-health-record", "highly-restricted"], issued_by="privacy-officer",
        now=now, basis="synthetic access-governance exercise")
    request = {"requester": "agent", "session_id": "lab-session", "grant": grant,
               "purpose": "treatment", "subjects": ["patient-1"],
               "fields": ["patient_name", "diagnosis"],
               "model_endpoint": "on_premises_model", "now": now}
    before = records.fetch_count
    checks["out_of_scope_subject_denied"] = denied(lambda: privacy.context_for_model(
        **{**request, "subjects": ["patient-2"]}), DisclosureDenied)
    require(records.fetch_count == before, "unauthorized request reached SQL record source")
    checks["denied_before_sql_read"] = True
    context = privacy.context_for_model(**request)
    model_values = json.dumps(context.values)
    require("Alice Example" not in model_values and "patient-1" not in model_values,
            "known identity leaked in model values")
    checks["model_values_tokenized"] = True
    # A scripted model sees ONLY values, not internal labels, credentials or context objects.
    name_token = next(v for k, v in context.values.items() if k.endswith(".patient_name"))
    model_output = f"Access review prepared for {name_token}."
    derived = privacy.derive(requester="agent", session_id="lab-session", content=model_output)
    checks["external_release_denied"] = denied(lambda: privacy.release(
        derived, recipient="external_email", purpose="treatment", now=now), DisclosureDenied)
    released = privacy.release(derived, recipient="treating_clinician", purpose="treatment",
                               now=now, restore_identity=True)
    require(released.content == "Access review prepared for Alice Example.", "release mismatch")
    released_digest = hashlib.sha256(released.content.encode()).hexdigest()
    require(evidence.find("identity_restoration")[-1].payload["released_content_digest"] == released_digest,
            "receipt does not match released bytes")
    checks["release_digest_matches"] = True
    gate.revoke_grant(grant.grant_id, by="privacy-officer", reason="lab complete")
    checks["release_after_revocation_denied"] = denied(lambda: privacy.release(
        derived, recipient="treating_clinician", purpose="treatment", now=now,
        restore_identity=True), DisclosureDenied)
    custody.destroy_subject(eraser, "patient-1", erased_by="privacy-officer", reason="synthetic lab")
    checks["erased_sql_ciphertext_unreadable"] = denied(lambda: records.fetch(
        "patient-1", ["patient_name"]), CustodyDenied)
    require(records.fetch("patient-2", ["patient_name"])["patient_name"] == "Bob Example",
            "erasing one subject affected another")
    checks["other_subject_still_readable"] = True
    notary = EvidenceNotary()
    checkpoint = notary.checkpoint(evidence)
    require(verify_against_checkpoint(evidence, checkpoint, notary.public_keys).valid,
            "signed checkpoint failed")
    require(not verify_against_checkpoint(list(evidence)[:-1], checkpoint, notary.public_keys).valid,
            "truncation was not detected")
    checks["signed_checkpoint_valid"] = True
    checks["truncated_evidence_denied"] = True
    report = {"synthetic": True, "backend": "postgres" if postgres else "sqlite",
              "run_id": records.run_id, "table": records.table, "encrypted_rows": len(ciphertext_rows),
              "checks": checks, "verified": True,
              "limits": ["ephemeral custody, vault and disclosure state", "scripted model",
                         "no network delivery to recipient", "not a Kafka/Spark integration run",
                         "erasure probe covers SQL fields through live custody only"]}
    artifacts = {"01-input.json": fixture, "02-encrypted-rows.json": ciphertext_rows,
                 "03-model-values.json": context.values,
                 "04-output.json": {"model_output": model_output, "released_content": released.content,
                                    "sha256": released_digest},
                 "05-evidence.json": [asdict(r) for r in evidence],
                 "06-checkpoint.json": checkpoint.to_dict(),
                 "07-public-keys.json": {k: v.hex() for k, v in notary.public_keys.items()},
                 "report.json": report}
    for name, value in artifacts.items():
        (output / name).write_text(json.dumps(value, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory; never overwritten")
    parser.add_argument("--postgres", action="store_true", help="use PIPELINE_LAB_DSN")
    args = parser.parse_args()
    dsn = os.environ["PIPELINE_LAB_DSN"] if args.postgres else None
    print(json.dumps(run(args.output, postgres_dsn=dsn), indent=2))


if __name__ == "__main__":
    main()
