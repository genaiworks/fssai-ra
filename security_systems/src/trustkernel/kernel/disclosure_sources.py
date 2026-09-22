"""Where protected values come from, and who says consent still holds.

The gate never owns the institution's records. It reads them, after every
authorization check has passed, from a :class:`RecordSource`. Consent is likewise
an institutional system of record, so the gate can consult a :class:`ConsentService`
live on every read and every release.

Every adapter here fails closed. A source that times out, returns malformed data,
or refuses the gate's credential raises an error the gate turns into a refusal
with a stable code. Nothing is released on a guess.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Protocol


class RecordNotFound(LookupError):
    """The subject does not exist in the record source."""


class RecordSourceUnavailable(RuntimeError):
    """The record source could not answer; nothing is released."""


class ConsentServiceUnavailable(RuntimeError):
    """The consent service could not answer; nothing is released."""


class RecordSource(Protocol):
    def fetch(self, subject: str, fields: Iterable[str]) -> dict[str, str]: ...


class ConsentService(Protocol):
    def permits(self, subject: str, purpose: str) -> bool: ...


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class MemoryRecordSource:
    """Synthetic or fixture records held in process. Writable, for teaching."""

    def __init__(self, records: dict[str, dict[str, str]] | None = None) -> None:
        self._records = {subject: dict(fields) for subject, fields in (records or {}).items()}

    def fetch(self, subject: str, fields: Iterable[str]) -> dict[str, str]:
        if subject not in self._records:
            raise RecordNotFound(subject)
        row = self._records[subject]
        return {name: str(row.get(name, "")) for name in fields}

    def load(self, subject: str, fields: dict[str, str]) -> None:
        self._records.setdefault(subject, {}).update({k: str(v) for k, v in fields.items()})


def as_record_source(records: Any) -> Any:
    if records is None:
        return MemoryRecordSource({})
    if isinstance(records, dict):
        return MemoryRecordSource(records)
    if not callable(getattr(records, "fetch", None)):
        raise TypeError("records must be a mapping or an object with fetch(subject, fields)")
    return records


# ---------------------------------------------------------------------------
# SQL table
# ---------------------------------------------------------------------------

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}(\.[A-Za-z_][A-Za-z0-9_]{0,62})?$")


class SqlTableRecordSource:
    """Read governed fields from an existing institutional table.

    Table and column names are validated identifiers fixed at configuration time;
    subjects are bound parameters. The gate's database role should have read
    access to this table and nothing else.
    """

    def __init__(self, connect, *, table: str, subject_column: str,
                 columns: dict[str, str], placeholder: str = "?") -> None:
        for name in (table, subject_column, *columns.values()):
            if not _IDENTIFIER.match(name):
                raise ValueError(f"unsafe SQL identifier: {name!r}")
        self._connect = connect
        self._table = table
        self._subject_column = subject_column
        self._columns = dict(columns)
        self._placeholder = placeholder

    def fetch(self, subject: str, fields: Iterable[str]) -> dict[str, str]:
        requested = list(fields)
        unknown = sorted(set(requested) - set(self._columns))
        if unknown:
            raise RecordSourceUnavailable(f"no column mapping for fields: {', '.join(unknown)}")
        columns = ", ".join(self._columns[name] for name in requested)
        sql = (f"SELECT {columns} FROM {self._table} "
               f"WHERE {self._subject_column} = {self._placeholder}")
        try:
            connection = self._connect()
            try:
                row = connection.execute(sql, (subject,)).fetchone()
            finally:
                close = getattr(connection, "close", None)
                if close:
                    close()
        except Exception as exc:
            raise RecordSourceUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if row is None:
            raise RecordNotFound(subject)
        return {name: "" if value is None else str(value) for name, value in zip(requested, row, strict=True)}


# ---------------------------------------------------------------------------
# FHIR
# ---------------------------------------------------------------------------


def _path(resource: Any, path: str) -> list:
    """A small, explicit subset of FHIRPath: dotted names and numeric indexes."""
    current = [resource]
    for part in path.split("."):
        nxt = []
        for item in current:
            if part.isdigit() and isinstance(item, list):
                index = int(part)
                if index < len(item):
                    nxt.append(item[index])
            elif isinstance(item, dict) and part in item:
                value = item[part]
                nxt.extend(value if isinstance(value, list) and not part.isdigit() else [value])
            elif isinstance(item, list):
                for element in item:
                    if isinstance(element, dict) and part in element:
                        value = element[part]
                        nxt.extend(value if isinstance(value, list) else [value])
        current = nxt
    return [value for value in current if isinstance(value, (str, int, float, bool))]


class FhirRecordSource:
    """Read governed fields from a FHIR R4 server.

    Each field maps to ``{"resource": "Patient", "path": "birthDate"}`` for the
    patient resource itself, or ``{"resource": "Condition", "path":
    "code.coding.display"}`` for resources searched by ``patient``. The HTTP
    client carries the gate's own credential, for example a SMART backend-services
    token, and is supplied by the deployment.
    """

    def __init__(self, base_url: str, client: Any, *, fields: dict[str, dict],
                 timeout: float = 5.0) -> None:
        if not base_url.startswith("https://") and not base_url.startswith("http://localhost"):
            raise ValueError("FHIR base URL must use https outside localhost")
        self._base = base_url.rstrip("/")
        self._client = client
        self._fields = dict(fields)
        self._timeout = timeout

    def _get(self, url: str, params: dict | None = None) -> dict:
        try:
            response = self._client.get(url, params=params, timeout=self._timeout,
                                        headers={"Accept": "application/fhir+json"})
        except Exception as exc:
            raise RecordSourceUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if response.status_code == 404:
            raise RecordNotFound(url)
        if response.status_code != 200:
            raise RecordSourceUnavailable(f"FHIR server returned {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise RecordSourceUnavailable("FHIR server returned malformed JSON") from exc
        if not isinstance(body, dict) or "resourceType" not in body:
            raise RecordSourceUnavailable("FHIR response is not a resource")
        return body

    def fetch(self, subject: str, fields: Iterable[str]) -> dict[str, str]:
        if not re.match(r"^[A-Za-z0-9\-\.]{1,64}$", subject):
            raise RecordNotFound(subject)
        requested = list(fields)
        unknown = sorted(set(requested) - set(self._fields))
        if unknown:
            raise RecordSourceUnavailable(f"no FHIR mapping for fields: {', '.join(unknown)}")
        patient = self._get(f"{self._base}/Patient/{subject}")
        if patient.get("resourceType") != "Patient":
            raise RecordSourceUnavailable("expected a Patient resource")
        searched: dict[str, list] = {}
        out: dict[str, str] = {}
        for name in requested:
            spec = self._fields[name]
            resource = spec["resource"]
            if resource == "Patient":
                values = _path(patient, spec["path"])
            else:
                if resource not in searched:
                    bundle = self._get(f"{self._base}/{resource}", {"patient": subject})
                    searched[resource] = [entry.get("resource", {})
                                          for entry in bundle.get("entry", []) or []]
                values = [v for item in searched[resource] for v in _path(item, spec["path"])]
            out[name] = "; ".join(str(v) for v in values)
        return out


# ---------------------------------------------------------------------------
# Consent service
# ---------------------------------------------------------------------------


class HttpConsentService:
    """Ask an institutional consent service, live, whether a purpose is permitted.

    Expects ``GET {base}/consents/{subject}?purpose=...`` to return
    ``{"permitted": true|false}``. Any other answer, status, or delay is a refusal.
    Results are never cached: a withdrawal takes effect at the next check.
    """

    def __init__(self, base_url: str, client: Any, *, timeout: float = 2.0) -> None:
        self._base = base_url.rstrip("/")
        self._client = client
        self._timeout = timeout

    def permits(self, subject: str, purpose: str) -> bool:
        try:
            response = self._client.get(f"{self._base}/consents/{subject}",
                                        params={"purpose": purpose}, timeout=self._timeout)
        except Exception as exc:
            raise ConsentServiceUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise ConsentServiceUnavailable(f"consent service returned {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise ConsentServiceUnavailable("consent service returned malformed JSON") from exc
        if not isinstance(body, dict) or not isinstance(body.get("permitted"), bool):
            raise ConsentServiceUnavailable("consent service answer has no boolean 'permitted'")
        return body["permitted"]

    def withdraw(self, subject: str, purpose: str) -> None:
        raise ConsentServiceUnavailable(
            "consent is managed by the institutional consent service; record the withdrawal there")

    restore = withdraw


__all__ = [
    "ConsentService", "ConsentServiceUnavailable", "FhirRecordSource", "HttpConsentService",
    "MemoryRecordSource", "RecordNotFound", "RecordSource", "RecordSourceUnavailable",
    "SqlTableRecordSource", "as_record_source",
]
