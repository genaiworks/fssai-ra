"""A backend inherits no assurance until the same suites pass on it.

The paper's promotion rule (Section 6, stage 6) is that conformance is rerun on
the target stack. This module enforces it in code. A :class:`ConformanceRecord`
binds:

* the **backend name** (``memory``, ``sqlite``, ``postgres``, ``redis``, ...);
* an **implementation digest**: SHA-256 over the source files of the modules
  that implement that backend, so a record stops counting the moment the code
  it was run against changes;
* the **suite id**, which includes a digest of the conformance suite's own source,
  so a changed suite also needs a fresh run;
* every **per-check result**.

:func:`require_assurance` refuses when there is no record, the record is for a
different backend or suite, no check executed, any check failed, or the
implementation digest no longer matches the code on disk.

Must NOT / residual risk
------------------------
* Must NOT be satisfied by a record for a different backend, a sibling backend
  "of the same kind", or an older build.
* Residual: a record is a local artifact, not a notarized attestation; whoever can
  write the record file and the code can forge both. The digest covers the named
  Python modules, not third-party drivers, the database server, or the host.
  Passing conformance is necessary, not sufficient (``fssaira.conformance``).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SHARED = ("fssaira.exact_action", "fssaira.evidence", "fssaira.event_transport",
           "fssaira.reproducible_data", "fssaira.diode")

#: The modules whose source defines each backend's behaviour.
BACKEND_MODULES: dict[str, tuple[str, ...]] = {
    "memory": (*_SHARED, "fssaira.control_plane"),
    "sqlite": (*_SHARED, "fssaira.sql_backend", "fssaira.atomic_execution",
               "fssaira.postgres_backend"),
    "postgres": (*_SHARED, "fssaira.sql_backend", "fssaira.atomic_execution",
                 "fssaira.postgres_backend"),
    "redis": (*_SHARED, "fssaira.redis_backend"),
    "kafka": ("fssaira.kafka_backend", "fssaira.event_transport"),
    "iceberg": ("fssaira.iceberg_backend",),
}

CONFORMANCE_SUITE = "fssaira.conformance"


class AssuranceCode:
    NO_RECORD = "ASSURANCE_NO_RECORD"
    UNKNOWN_BACKEND = "ASSURANCE_UNKNOWN_BACKEND"
    BACKEND_MISMATCH = "ASSURANCE_BACKEND_MISMATCH"
    SUITE_MISMATCH = "ASSURANCE_SUITE_MISMATCH"
    NO_EXECUTED_CHECKS = "ASSURANCE_NO_EXECUTED_CHECKS"
    CHECK_FAILED = "ASSURANCE_CHECK_FAILED"
    DIGEST_MISMATCH = "ASSURANCE_IMPLEMENTATION_CHANGED"
    MALFORMED = "ASSURANCE_RECORD_MALFORMED"


class AssuranceRefused(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_files(modules: Iterable[str]) -> tuple[Path, ...]:
    """Source files for ``modules``, located without importing them."""
    files = []
    for name in modules:
        spec = importlib.util.find_spec(name)
        if spec is None or not spec.origin or not spec.origin.endswith(".py"):
            raise AssuranceRefused(AssuranceCode.UNKNOWN_BACKEND, f"no source for {name}")
        files.append(Path(spec.origin))
    return tuple(files)


def digest_files(files: Iterable[Path]) -> str:
    """Canonical digest over a set of files: sorted names and content digests."""
    rows = sorted(f"{Path(p).name}\0{_sha256_file(Path(p))}" for p in files)
    return "sha256:" + hashlib.sha256("\n".join(rows).encode()).hexdigest()


def implementation_digest(backend: str, *, files: Sequence[Path] | None = None) -> str:
    """The digest of the code implementing ``backend`` as it is on disk now."""
    if files is None:
        modules = BACKEND_MODULES.get(backend)
        if modules is None:
            raise AssuranceRefused(AssuranceCode.UNKNOWN_BACKEND, backend)
        files = module_files(modules)
    return digest_files(files)


def conformance_suite_id() -> str:
    """Suite identity, bound to the suite's own source."""
    (path,) = module_files([CONFORMANCE_SUITE])
    return f"{CONFORMANCE_SUITE}@{_sha256_file(path)[:16]}"


@dataclass(frozen=True)
class CheckOutcome:
    id: str
    passed: bool
    skipped: bool = False


@dataclass(frozen=True)
class ConformanceRecord:
    backend: str
    implementation_digest: str
    suite_id: str
    checks: tuple[CheckOutcome, ...]
    generated_at: str = ""
    profile_id: str = ""

    @property
    def executed(self) -> tuple[CheckOutcome, ...]:
        return tuple(c for c in self.checks if not c.skipped)

    @property
    def failures(self) -> tuple[CheckOutcome, ...]:
        return tuple(c for c in self.executed if not c.passed)

    def to_dict(self) -> dict:
        return {"kind": "backend_conformance_record", "backend": self.backend,
                "implementation_digest": self.implementation_digest, "suite_id": self.suite_id,
                "generated_at": self.generated_at, "profile_id": self.profile_id,
                "checks": [c.__dict__ for c in self.checks]}

    @classmethod
    def from_dict(cls, body: Any) -> ConformanceRecord:
        try:
            return cls(str(body["backend"]), str(body["implementation_digest"]),
                       str(body["suite_id"]),
                       tuple(CheckOutcome(str(c["id"]), c["passed"] is True,
                                          c.get("skipped", False) is True)
                             for c in body["checks"]),
                       str(body.get("generated_at", "")), str(body.get("profile_id", "")))
        except (KeyError, TypeError, AttributeError) as exc:
            raise AssuranceRefused(AssuranceCode.MALFORMED) from exc


@dataclass(frozen=True)
class AssuranceStatus:
    backend: str
    assured: bool
    code: str
    implementation_digest: str = ""
    suite_id: str = ""
    checks_executed: int = 0
    checks_skipped: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def record_from_report(backend: str, report: Any, *,
                       files: Sequence[Path] | None = None) -> ConformanceRecord:
    """Bind a :class:`fssaira.conformance.ConformanceReport` to the code it ran against."""
    return ConformanceRecord(
        backend=backend, implementation_digest=implementation_digest(backend, files=files),
        suite_id=conformance_suite_id(),
        checks=tuple(CheckOutcome(c.id, bool(c.passed), bool(c.skipped)) for c in report.checks),
        generated_at=getattr(report, "generated_at", "")
        or datetime.now(timezone.utc).isoformat(),
        profile_id=getattr(report, "profile_id", ""),
    )


def run_and_record(backend: str, bundle: Any, *,
                   files: Sequence[Path] | None = None) -> ConformanceRecord:
    """Run the conformance suite on ``bundle`` and bind the result to ``backend``'s code."""
    from ..conformance import run_conformance

    return record_from_report(backend, run_conformance(bundle), files=files)


def require_assurance(backend: str, record: ConformanceRecord | None, *,
                      files: Sequence[Path] | None = None) -> AssuranceStatus:
    """Refuse unless ``record`` is a current, passing run on exactly this backend's code."""
    if record is None:
        raise AssuranceRefused(AssuranceCode.NO_RECORD, backend)
    if record.backend != backend:
        raise AssuranceRefused(AssuranceCode.BACKEND_MISMATCH,
                               f"record is for {record.backend!r}, not {backend!r}")
    current_suite = conformance_suite_id()
    if record.suite_id != current_suite:
        raise AssuranceRefused(AssuranceCode.SUITE_MISMATCH, "rerun the current suite")
    if not record.executed:
        raise AssuranceRefused(AssuranceCode.NO_EXECUTED_CHECKS, backend)
    if record.failures:
        raise AssuranceRefused(AssuranceCode.CHECK_FAILED,
                               ", ".join(c.id for c in record.failures))
    current = implementation_digest(backend, files=files)
    if record.implementation_digest != current:
        raise AssuranceRefused(AssuranceCode.DIGEST_MISMATCH,
                               f"{backend} code changed since the conformance run")
    return AssuranceStatus(backend, True, "ASSURED", current, current_suite,
                           len(record.executed), len(record.checks) - len(record.executed))


def load_records(path: str | Path) -> dict[str, ConformanceRecord]:
    """Load one record or a list of records from JSON, keyed by backend."""
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    items = body if isinstance(body, list) else [body]
    return {record.backend: record for record in map(ConformanceRecord.from_dict, items)}


def assurance_status(backend: str, record: ConformanceRecord | None, *,
                     files: Sequence[Path] | None = None) -> AssuranceStatus:
    """Non-raising form for reporting (e.g. the teaching profile)."""
    try:
        return require_assurance(backend, record, files=files)
    except AssuranceRefused as refused:
        return AssuranceStatus(backend, False, refused.code, notes=(refused.detail,))


__all__ = [
    "BACKEND_MODULES", "AssuranceCode", "AssuranceRefused", "AssuranceStatus", "CheckOutcome",
    "ConformanceRecord", "assurance_status", "conformance_suite_id", "digest_files",
    "implementation_digest", "load_records", "module_files", "record_from_report",
    "require_assurance", "run_and_record",
]
