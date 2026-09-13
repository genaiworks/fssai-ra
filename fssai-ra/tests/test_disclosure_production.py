"""The gaps between a teaching gate and one an institution can run.

Durable state that survives restarts, real record sources read only after
authorization, a live consent service, value-level labels, and failure of any of
them refusing rather than guessing.
"""
import json
import sqlite3
from contextlib import contextmanager

import httpx
import pytest

from fssaira.disclosure import DataLabel, DisclosureCode, DisclosureDenied, DisclosureGate
from fssaira.disclosure_eval import (
    AGENT,
    NOW,
    OTHER_AGENT,
    SUBJECT_A,
    SUBJECT_B,
    DisclosureFixture,
)
from fssaira.disclosure_sources import (
    FhirRecordSource,
    HttpConsentService,
    MemoryRecordSource,
    RecordNotFound,
    RecordSourceUnavailable,
    SqlTableRecordSource,
)
from fssaira.disclosure_store import MemoryDisclosureStore, SqlDisclosureStore, StoreUnavailable
from fssaira.evidence import EvidenceLedger
from fssaira.profiles import ApplicationProfile
from fssaira.sql_backend import open_sqlite

PACKS = (
    "profiles/healthcare_record_access.yaml",
    "profiles/corporate_confidential_data.yaml",
    "profiles/financial_consumer_data.yaml",
    "profiles/government_benefits.yaml",
)


def _policy(path=PACKS[0]):
    return ApplicationProfile.load(path).disclosure


def _gate(fx, *, records=None, store=None, consent=None, ledger=None):
    return DisclosureGate(
        fx.policy, fx.records if records is None else records,
        ledger or EvidenceLedger("w"), "w",
        grant_keys=fx.authority.trusted_keys,
        declassification_keys=fx.declassifier.trusted_keys, store=store, consent=consent,
    )


def _code(action):
    with pytest.raises(DisclosureDenied) as denied:
        action()
    return denied.value.code


# -- durable state -------------------------------------------------------------


def test_sql_store_survives_restart_and_forgets_nothing(tmp_path):
    fx = DisclosureFixture(_policy())
    path = str(tmp_path / "disclosure.db")
    first = _gate(fx, store=SqlDisclosureStore(open_sqlite(path)))
    fx.read(first, fx.grant())
    output = first.derive_output(requester=AGENT, session_id="session-1", content="summary")
    first.revoke_grant("grant-2", by="data-owner", reason="ended")
    first.withdraw_consent(SUBJECT_B, fx.purpose, recorded_by="privacy-office")
    emergency = fx.break_glass_grant("bg-1")
    fx.read(first, emergency, purpose=emergency.purpose, session_id="bg-session")
    del first

    restarted = _gate(fx, store=SqlDisclosureStore(open_sqlite(path)))
    assert restarted.session_label("session-1") == fx.honest_label()
    assert restarted.output(output.output_id).label == output.label
    assert _code(lambda: fx.read(restarted, fx.grant(grant_id="grant-2"), session_id="s2")) \
        == DisclosureCode.GRANT_REVOKED
    assert _code(lambda: fx.read(restarted, fx.grant(grant_id="grant-3", subjects=[SUBJECT_B]),
                                 subjects=[SUBJECT_B], session_id="s3")) \
        == DisclosureCode.CONSENT_WITHDRAWN
    assert restarted.open_break_glass == {"bg-1": AGENT}
    second = fx.break_glass_grant("bg-2")
    assert _code(lambda: fx.read(restarted, second, purpose=second.purpose, session_id="bg-2")) \
        == DisclosureCode.BREAK_GLASS_REVIEW_OVERDUE
    assert restarted.release(output, recipient=fx.cleared_recipient, purpose=fx.purpose, now=NOW + 2)


def test_the_durable_store_holds_no_protected_values(tmp_path):
    fx = DisclosureFixture(_policy())
    path = str(tmp_path / "disclosure.db")
    gate = _gate(fx, store=SqlDisclosureStore(open_sqlite(path)))
    context = fx.read(gate, fx.grant())
    key = next(iter(context.values))
    gate.derive_from_values(requester=AGENT, session_id="session-1", content="summary",
                            sources=[context.value_ids[key]])
    connection = sqlite3.connect(path)
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'disclosure_%' "
        "AND name <> 'disclosure_outputs'")]
    dump = json.dumps([list(connection.execute(f"SELECT * FROM {name}")) for name in tables])
    values = {v for row in fx.records.values() for v in row.values()}
    assert tables and not any(value in dump for value in values)


def test_an_unavailable_store_refuses_and_records_why():
    class DownStore(MemoryDisclosureStore):
        @contextmanager
        def atomic(self):
            raise StoreUnavailable("database is down")
            yield self  # pragma: no cover

    fx = DisclosureFixture(_policy())
    ledger = EvidenceLedger("w")
    gate = _gate(fx, store=DownStore(), ledger=ledger)
    assert _code(lambda: fx.read(gate, fx.grant())) == DisclosureCode.STORE_UNAVAILABLE
    assert ledger.find("disclosure_outcome")[-1].payload["code"] == DisclosureCode.STORE_UNAVAILABLE


# -- record sources -------------------------------------------------------------


class CountingSource(MemoryRecordSource):
    def __init__(self, records):
        super().__init__(records)
        self.calls = 0

    def fetch(self, subject, fields):
        self.calls += 1
        return super().fetch(subject, fields)


def test_record_sources_are_read_only_after_authorization_so_existence_does_not_leak():
    fx = DisclosureFixture(_policy())
    source = CountingSource(fx.records)
    gate = _gate(fx, records=source)
    assert _code(lambda: fx.read(gate, fx.grant(holder=OTHER_AGENT), subjects=["ghost"])) \
        == DisclosureCode.GRANT_HOLDER_MISMATCH
    assert _code(lambda: fx.read(gate, fx.grant(), subjects=["ghost"])) \
        == DisclosureCode.SUBJECT_OUT_OF_SCOPE
    assert source.calls == 0
    assert _code(lambda: fx.read(gate, fx.grant(subjects=["ghost"]), subjects=["ghost"])) \
        == DisclosureCode.SUBJECT_NOT_FOUND
    assert source.calls == 1


def test_sql_table_record_source_reads_real_rows_through_the_gate(tmp_path):
    fx = DisclosureFixture(_policy())
    path = str(tmp_path / "records.db")
    connection = sqlite3.connect(path)
    columns = {name: f"c_{index}" for index, name in enumerate(sorted(fx.policy.field_classes))}
    connection.execute(f"CREATE TABLE patients (patient_id TEXT, {', '.join(c + ' TEXT' for c in columns.values())})")
    row = fx.records[SUBJECT_A]
    connection.execute(f"INSERT INTO patients VALUES (?, {', '.join('?' for _ in columns)})",
                       (SUBJECT_A, *[row[name] for name in columns]))
    connection.commit()
    connection.close()

    source = SqlTableRecordSource(lambda: sqlite3.connect(path), table="patients",
                                  subject_column="patient_id", columns=columns)
    context = fx.read(_gate(fx, records=source), fx.grant())
    assert context.values == {f"{SUBJECT_A}.{name}": row[name] for name in fx.granted_fields()}
    with pytest.raises(RecordNotFound):
        source.fetch(SUBJECT_B, ["diagnosis"])
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        SqlTableRecordSource(lambda: None, table="patients; DROP TABLE x", subject_column="id",
                             columns={})

    def broken():
        raise sqlite3.OperationalError("unable to open database")

    gate = _gate(fx, records=SqlTableRecordSource(broken, table="patients",
                                                  subject_column="patient_id", columns=columns))
    assert _code(lambda: fx.read(gate, fx.grant())) == DisclosureCode.RECORD_SOURCE_UNAVAILABLE


def _fhir(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


FHIR_FIELDS = {
    "patient_name": {"resource": "Patient", "path": "name.family"},
    "date_of_birth": {"resource": "Patient", "path": "birthDate"},
    "diagnosis": {"resource": "Condition", "path": "code.coding.display"},
}


def test_fhir_record_source_maps_resources_and_fails_closed():
    def handler(request):
        if request.url.path == f"/fhir/Patient/{SUBJECT_A}":
            return httpx.Response(200, json={"resourceType": "Patient", "id": SUBJECT_A,
                                             "name": [{"family": "Synthetic"}],
                                             "birthDate": "1970-01-01"})
        if request.url.path == "/fhir/Condition" and request.url.params["patient"] == SUBJECT_A:
            return httpx.Response(200, json={"resourceType": "Bundle", "entry": [
                {"resource": {"resourceType": "Condition",
                              "code": {"coding": [{"display": "Synthetic condition"}]}}}]})
        if request.url.path.startswith("/fhir/Patient/"):
            return httpx.Response(404, json={"resourceType": "OperationOutcome"})
        return httpx.Response(500)

    source = FhirRecordSource("https://fhir.example.test/fhir", _fhir(handler), fields=FHIR_FIELDS)
    assert source.fetch(SUBJECT_A, list(FHIR_FIELDS)) == {
        "patient_name": "Synthetic", "date_of_birth": "1970-01-01",
        "diagnosis": "Synthetic condition"}
    with pytest.raises(RecordNotFound):
        source.fetch(SUBJECT_B, ["patient_name"])
    down = FhirRecordSource("https://fhir.example.test/fhir",
                            _fhir(lambda request: httpx.Response(503)), fields=FHIR_FIELDS)
    with pytest.raises(RecordSourceUnavailable):
        down.fetch(SUBJECT_A, ["patient_name"])
    with pytest.raises(ValueError, match="https"):
        FhirRecordSource("http://fhir.example.test", _fhir(handler), fields=FHIR_FIELDS)

    fx = DisclosureFixture(_policy())
    fields = ["date_of_birth", "diagnosis", "patient_name"]
    grant = fx.grant(fields=fields, classes={fx.policy.field_classes[f] for f in fields})
    context = fx.read(_gate(fx, records=source), grant, fields=fields)
    assert context.values[f"{SUBJECT_A}.diagnosis"] == "Synthetic condition"


# -- consent service ---------------------------------------------------------------


def test_live_consent_service_is_checked_at_read_and_release_and_fails_closed():
    state = {"up": True}

    def handler(request):
        if not state["up"]:
            return httpx.Response(503)
        subject = request.url.path.rsplit("/", 1)[-1]
        if subject == "malformed":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={"permitted": subject == SUBJECT_A})

    service = HttpConsentService("https://consent.example.test", _fhir(handler))
    fx = DisclosureFixture(_policy(PACKS[1]))
    gate = _gate(fx, consent=service)
    fx.read(gate, fx.grant())
    output = gate.derive_output(requester=AGENT, session_id="session-1", content="summary")
    assert _code(lambda: fx.read(gate, fx.grant(subjects=[SUBJECT_B]), subjects=[SUBJECT_B],
                                 session_id="s2")) == DisclosureCode.CONSENT_WITHDRAWN
    state["up"] = False
    assert _code(lambda: gate.release(output, recipient=fx.cleared_recipient, purpose=fx.purpose,
                                      now=NOW + 2)) == DisclosureCode.CONSENT_SERVICE_UNAVAILABLE
    assert _code(lambda: gate.withdraw_consent(SUBJECT_A, fx.purpose, recorded_by="x")) \
        == DisclosureCode.CONSENT_SERVICE_UNAVAILABLE
    state["up"] = True
    with pytest.raises(Exception, match="permitted"):
        service.permits("malformed", fx.purpose)


# -- value-level labels ------------------------------------------------------------


@pytest.mark.parametrize("path", PACKS)
def test_value_level_labels_release_what_session_labels_would_refuse(path):
    fx = DisclosureFixture(_policy(path))
    recipient, low, _high = fx.precision_path()
    gate = _gate(fx)
    context = fx.read(gate, fx.grant())
    key = f"{SUBJECT_A}.{low}"
    whole_session = gate.derive_output(requester=AGENT, session_id="session-1",
                                       content=context.values[key])
    assert _code(lambda: gate.release(whole_session, recipient=recipient, purpose=fx.purpose,
                                      now=NOW + 2)).startswith("RECIPIENT_")
    precise = gate.derive_from_values(requester=AGENT, session_id="session-1",
                                      content=context.values[key], sources=[context.value_ids[key]])
    assert precise.label.classes == {fx.policy.field_classes[low]}
    assert gate.release(precise, recipient=recipient, purpose=fx.purpose, now=NOW + 2)


def test_an_omitted_source_over_labels_and_the_evidence_says_so():
    fx = DisclosureFixture(_policy())
    recipient, low, high = fx.precision_path()
    ledger = EvidenceLedger("w")
    gate = _gate(fx, ledger=ledger)
    context = fx.read(gate, fx.grant())
    content = f"{context.values[f'{SUBJECT_A}.{low}']} and {context.values[f'{SUBJECT_A}.{high}']}"
    output = gate.derive_from_values(requester=AGENT, session_id="session-1", content=content,
                                     sources=[context.value_ids[f"{SUBJECT_A}.{low}"]],
                                     claimed_label=DataLabel.bottom(fx.policy))
    assert output.label == gate.session_label("session-1")
    assert ledger.find("output_labelled")[-1].payload["undeclared_source_detected"] is True
    assert _code(lambda: gate.release(output, recipient=recipient, purpose=fx.purpose, now=NOW + 2))


def test_value_identifiers_must_belong_to_this_session_and_holder():
    fx = DisclosureFixture(_policy())
    gate = _gate(fx)
    context = fx.read(gate, fx.grant())
    other = fx.read(gate, fx.grant(grant_id="grant-9"), session_id="session-2")
    key = next(iter(context.values))
    assert _code(lambda: gate.derive_from_values(requester=AGENT, session_id="session-1",
                                                 content="x", sources=["value-forged"])) \
        == DisclosureCode.VALUE_NOT_ISSUED
    assert _code(lambda: gate.derive_from_values(requester=AGENT, session_id="session-1",
                                                 content="x", sources=[other.value_ids[key]])) \
        == DisclosureCode.VALUE_NOT_ISSUED
    assert _code(lambda: gate.derive_from_values(requester=OTHER_AGENT, session_id="session-1",
                                                 content="x", sources=[context.value_ids[key]])) \
        == DisclosureCode.SESSION_HOLDER_MISMATCH
