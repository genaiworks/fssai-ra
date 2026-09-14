"""The privacy pipeline: identity leaves the data plane only as tokens, and returns
only to an entitled recipient.

    raw record ─► classify ─► authorize (context gate) ─► decrypt under custody
      ─► tokenize identity ─► minimum-necessary context ─► model (tokens only)
      ─► labelled output (identity re-tokenized) ─► release authorization
      ─► identity restoration for an entitled recipient ─► evidence

:class:`PrivacyGate` wraps :class:`fssaira.disclosure.DisclosureGate` rather than
changing it. Every authorization decision stays in the gate's fourteen checks; the
pipeline adds what the gate never did: the model context carries tokens instead of
names and numbers, outputs are re-scanned so a model that learned an identifier
elsewhere cannot write it into a summary, and restoration is a separate decision
made after release against the recipient's clearance for the identity fields.

:class:`ErasureService` destroys a subject's keys, purges derived outputs, and
:meth:`ErasureService.verify` then *tries to read the subject back* from every
copy the architecture governs. A location that still yields plaintext is reported
as ``READABLE`` and the erasure as incomplete; nothing is reported erased because a
function returned.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .disclosure import DataLabel, DisclosureGate, GovernedOutput, ReleaseReceipt
from .disclosure_sources import RecordNotFound
from .encrypted_records import EncryptedRecordSource, GovernedVectorIndex, RecordSnapshot
from .evidence import EvidenceLedger
from .key_custody import CustodyBackup, ErasureCertificate, ErasureEntry, KeyCustody
from .privacy_vault import TOKEN_PATTERN, TokenVault, VaultDenied

#: The pipeline's own ablatable controls, separate from the gate's fourteen.
PRIVACY_CHECKS = ("tokenization", "output_retokenization", "identity_restoration_entitlement")

PIPELINE_STAGES = (
    "classification", "authorization", "decryption", "tokenization", "minimum_necessary",
    "model", "labelled_output", "release_authorization", "identity_restoration",
)


class PrivacyCode:
    IDENTITY_NOT_ENTITLED = "IDENTITY_NOT_ENTITLED"
    IDENTITY_RESTORED = "IDENTITY_RESTORED"
    NOTHING_TO_RESTORE = "NOTHING_TO_RESTORE"


@dataclass(frozen=True)
class ModelContext:
    """Exactly what the intelligence plane receives. No subject identifiers, no keys."""

    session_id: str
    receipt_id: str
    values: dict
    classes: tuple[str, ...]
    purposes: tuple[str, ...]
    model_endpoint: str
    tokens: tuple[str, ...] = ()

    def as_text(self) -> str:
        return "\n".join(f"{key}: {value}" for key, value in sorted(self.values.items()))


@dataclass(frozen=True)
class ReleasedOutput:
    receipt: ReleaseReceipt
    content: str
    identity_restored: bool
    code: str
    tokens_restored: int = 0


class PrivacyGate:
    """Tokenizing, re-identifying front of the context gate."""

    def __init__(self, gate: DisclosureGate, vault: TokenVault, records: Any, *,
                 identity_fields: dict[str, str], restore_credential: str,
                 enforce: Iterable[str] = PRIVACY_CHECKS) -> None:
        self.gate = gate
        self.vault = vault
        self._records = records
        self.identity_fields = dict(identity_fields)
        self._restore_credential = restore_credential
        self.enforce = frozenset(enforce)
        unknown = sorted(self.enforce - set(PRIVACY_CHECKS))
        if unknown:
            raise ValueError(f"unknown privacy checks: {', '.join(unknown)}")
        self._session_subjects: dict[str, set[str]] = {}
        self.trace: list[dict] = []

    def _on(self, check: str) -> bool:
        return check in self.enforce

    def _record(self, kind: str, payload: dict) -> None:
        self.gate._record(kind, payload)
        self.trace.append({"kind": kind, **payload})

    def _identifiers(self, session_id: str) -> list[tuple[str, str, str]]:
        """Every identity value of every subject this session has been released."""
        kind = self.gate.policy.subject_kind.upper()
        found: list[tuple[str, str, str]] = []
        for subject in sorted(self._session_subjects.get(session_id, ())):
            found.append((subject, kind, subject))
            try:
                row = self._records.fetch(subject, sorted(self.identity_fields))
            except RecordNotFound:
                continue
            found.extend((subject, self.identity_fields[name], value)
                         for name, value in row.items() if value)
        return found

    # -- read path ---------------------------------------------------------
    def context_for_model(self, *, requester: str, session_id: str, grant: Any, purpose: str,
                          subjects: Iterable[str], fields: Iterable[str], model_endpoint: str,
                          now: float) -> ModelContext:
        context = self.gate.assemble_context(
            requester=requester, session_id=session_id, grant=grant, purpose=purpose,
            subjects=subjects, fields=fields, model_endpoint=model_endpoint, now=now)
        self._session_subjects.setdefault(session_id, set()).update(context.label.subjects)
        if not self._on("tokenization"):
            values = dict(context.values)
            tokens: tuple[str, ...] = ()
            replacements = 0
        else:
            identifiers = self._identifiers(session_id)
            kind = self.gate.policy.subject_kind.upper()
            values, replacements = {}, 0
            for key, text in sorted(context.values.items()):
                subject, _, name = key.rpartition(".")
                subject_token = self.vault.token_for(session_id=session_id, subject=subject,
                                                     kind=kind, value=subject)
                clean, count = self.vault.tokenize_text(text, session_id=session_id,
                                                        identifiers=identifiers)
                for detail_kind, detail in self.vault.detect_contact_details(clean):
                    token = self.vault.token_for(session_id=session_id, subject=subject,
                                                 kind=detail_kind, value=detail)
                    clean = clean.replace(detail, token)
                    count += 1
                values[f"{subject_token}.{name}"] = clean
                replacements += count
            tokens = tuple(sorted({m.group(0) for v in [*values, *values.values()]
                                   for m in TOKEN_PATTERN.finditer(v)}))
        model_context = ModelContext(
            session_id=session_id, receipt_id=context.receipt_id, values=values,
            classes=tuple(sorted(context.label.classes)),
            purposes=tuple(sorted(context.label.purposes)), model_endpoint=model_endpoint,
            tokens=tokens)
        self._record("context_tokenized", {
            "receipt_id": context.receipt_id, "session_id": session_id,
            "fields": sorted({k.rpartition(".")[2] for k in values}),
            "tokens": len(tokens), "replacements": replacements,
            "tokenization_enforced": self._on("tokenization"),
        })
        return model_context

    # -- derivation ----------------------------------------------------------
    def derive(self, *, requester: str, session_id: str, content: str,
               claimed_label: DataLabel | None = None) -> GovernedOutput:
        """Label an output; first re-tokenize any identity the model wrote in clear."""
        replacements = 0
        if self._on("output_retokenization"):
            content, replacements = self.vault.tokenize_text(
                content, session_id=session_id, identifiers=self._identifiers(session_id))
        output = self.gate.derive_output(requester=requester, session_id=session_id,
                                         content=content, claimed_label=claimed_label)
        self._record("output_retokenized", {"output_id": output.output_id,
                                            "identifiers_retokenized": replacements})
        return output

    # -- release and restoration ---------------------------------------------------
    def identity_entitlement(self, recipient: str, recipient_id: str,
                             label: DataLabel) -> tuple[bool, str]:
        policy = self.gate.policy
        rule = policy.recipients.get(recipient)
        if rule is None or not label.subjects:
            return False, PrivacyCode.NOTHING_TO_RESTORE if rule else PrivacyCode.IDENTITY_NOT_ENTITLED
        identity_classes = {policy.field_classes[name] for name in self.identity_fields
                            if name in policy.field_classes}
        if not identity_classes <= rule.classes:
            return False, PrivacyCode.IDENTITY_NOT_ENTITLED
        if rule.subject_scope == "self" and not label.subjects <= {recipient_id}:
            return False, PrivacyCode.IDENTITY_NOT_ENTITLED
        return True, PrivacyCode.IDENTITY_RESTORED

    def release(self, output: GovernedOutput, *, recipient: str, purpose: str, now: float,
                recipient_id: str = "", restore_identity: bool = False) -> ReleasedOutput:
        receipt = self.gate.release(output, recipient=recipient, recipient_id=recipient_id,
                                    purpose=purpose, now=now)
        stored = self.gate.output(output.output_id)
        content = stored.content
        if not restore_identity:
            return ReleasedOutput(receipt, content, False, PrivacyCode.NOTHING_TO_RESTORE)
        if self._on("identity_restoration_entitlement"):
            entitled, code = self.identity_entitlement(recipient, recipient_id, receipt.label)
        else:
            entitled, code = True, PrivacyCode.IDENTITY_RESTORED
        restored = 0
        if entitled:
            base_session = stored.session_id.split("/", 1)[0]
            subjects = receipt.label.subjects or self._session_subjects.get(base_session, set())
            try:
                content, restored = self.vault.restore_text(
                    self._restore_credential, session_id=base_session, text=content,
                    subjects=subjects)
            except VaultDenied as exc:
                entitled, code = False, exc.code
        self._record("identity_restoration", {
            "receipt_id": receipt.receipt_id, "output_id": output.output_id,
            "recipient": recipient, "restored": entitled, "code": code,
            "tokens_restored": restored,
        })
        return ReleasedOutput(receipt, content, entitled, code, restored)


# ---------------------------------------------------------------------------
# Cryptographic erasure, and the attempt to read the subject back
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocationCheck:
    location: str
    status: str            # "unreadable", "absent", "READABLE", "declared-residual"
    detail: str

    def to_dict(self) -> dict:
        return {"location": self.location, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class ErasureVerification:
    subject: str
    checks: tuple[LocationCheck, ...]
    certificate: dict = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return bool(self.checks) and all(
            check.status in {"unreadable", "absent"} for check in self.checks
        )

    @property
    def governed_locations(self) -> int:
        return sum(1 for check in self.checks if check.status != "declared-residual")

    def to_dict(self) -> dict:
        return {"subject": self.subject, "complete": self.complete,
                "governed_locations": self.governed_locations,
                "scope": "supplied locations only; not a complete copy inventory",
                "unverified_locations": [c.location for c in self.checks
                                         if c.status not in {"unreadable", "absent", "READABLE"}],
                "readable_locations": [c.location for c in self.checks if c.status == "READABLE"],
                "checks": [c.to_dict() for c in self.checks], "certificate": self.certificate}


#: Copies the architecture does not govern and therefore cannot erase. Listed in
#: every verification so the report cannot be read as covering them.
DECLARED_RESIDUALS = (
    ("released_outputs_outside_boundary",
     "content already released to an entitled person or system is outside custody; "
     "erasure there is that recipient's obligation"),
    ("model_runtime_memory",
     "restricted classes run only on stateless local endpoints that receive tokens, not "
     "identity; the runtime's own memory is not inspected by this check"),
)


class ErasureService:
    def __init__(self, custody: KeyCustody, erase_credential: str, *,
                 record_source: EncryptedRecordSource, vault: TokenVault,
                 gates: Iterable[DisclosureGate] = (),
                 vector_index: GovernedVectorIndex | None = None,
                 evidence: EvidenceLedger | None = None, evidence_token: str | None = None) -> None:
        self.custody = custody
        self._credential = erase_credential
        self.records = record_source
        self.vault = vault
        self.gates = tuple(gates)
        self.vector_index = vector_index
        self._evidence = evidence
        self._token = evidence_token
        self.certificates: dict[str, ErasureCertificate] = {}

    def erase(self, subject: str, *, erased_by: str, reason: str) -> ErasureCertificate:
        certificate = self.custody.destroy_subject(self._credential, subject,
                                                   erased_by=erased_by, reason=reason)
        purged = 0
        for gate in self.gates:
            with gate.store.atomic() as tx:
                purged += tx.purge_subject_outputs(subject)
        self.certificates[subject] = certificate
        if self._evidence is not None and self._token is not None:
            self._evidence.append("subject_erased", {
                "subject": subject, "certificate_digest": certificate.digest,
                "classes": list(certificate.classes), "derived_outputs_purged": purged,
                "erased_by": erased_by,
            }, token=self._token)
        return certificate

    def verify(self, subject: str, *, fields: Iterable[str], plaintexts: Iterable[str],
               snapshots: Iterable[RecordSnapshot] = (),
               custody_backups: Iterable[tuple[CustodyBackup, tuple[ErasureEntry, ...]]] = (),
               restore_credential: str | None = None) -> ErasureVerification:
        """Try to recover the subject from every governed copy. Report what succeeds."""
        names = list(fields)
        secrets_ = [text for text in plaintexts if text and len(text) >= 6]
        checks: list[LocationCheck] = []

        def read_back(source: EncryptedRecordSource, where: str) -> None:
            try:
                row = source.fetch(subject, names)
                leaked = [name for name, value in row.items() if value]
                checks.append(LocationCheck(where, "READABLE" if leaked else "absent",
                                            f"fields returned: {', '.join(leaked) or 'none'}"))
            except RecordNotFound as exc:
                checks.append(LocationCheck(where, "unreadable", str(exc)))

        def scan(blob: bytes, where: str) -> None:
            hits = sum(1 for text in secrets_ if text.encode("utf-8") in blob)
            checks.append(LocationCheck(where, "READABLE" if hits else "absent",
                                        f"{hits} plaintext value(s) found in stored bytes"))

        read_back(self.records, "primary_record_store")
        scan(self.records.raw_bytes(), "primary_record_store_bytes")
        for snapshot in snapshots:
            probe = EncryptedRecordSource(dict(self.records._classes), self.custody,
                                          writer_credential="", reader_credential=self.records._reader)
            probe.restore_snapshot(snapshot)
            read_back(probe, f"backup:{snapshot.snapshot_id}")
            scan(json.dumps(sorted(str(v.body.hex()) for v in snapshot.rows.values())).encode(),
                 f"backup_bytes:{snapshot.snapshot_id}")
        for index, (backup, journal) in enumerate(custody_backups, start=1):
            self.custody.restore(self._restore_admin(), backup, journal)
            read_back(self.records, f"key_backup_{index}_restored_with_journal")

        entries = self.vault.entries_for(subject)
        reversible = 0
        for entry in entries:
            try:
                self.vault.restore(restore_credential or self.records._reader,
                                   session_id=entry.session_id, token=entry.token)
                reversible += 1
            except VaultDenied:
                continue
        checks.append(LocationCheck("token_map", "READABLE" if reversible else
                                    ("unreadable" if entries else "absent"),
                                    f"{reversible} of {len(entries)} token(s) still reversible"))

        if self.vector_index is not None:
            readable = self.vector_index.readable_entries(subject)
            total = self.vector_index.entries_for(subject)
            checks.append(LocationCheck("vector_index", "READABLE" if readable else
                                        ("unreadable" if total else "absent"),
                                        f"{readable} of {total} embedding(s) decryptable"))

        for index, gate in enumerate(self.gates, start=1):
            with gate.store.atomic() as tx:
                bodies = tx.output_bodies()
            linked = sum(1 for body in bodies if subject in body.get("label", {}).get("subjects", ()))
            blob = json.dumps(bodies, sort_keys=True).encode("utf-8")
            hits = sum(1 for text in secrets_ if text.encode("utf-8") in blob)
            status = "READABLE" if (linked or hits) else "absent"
            checks.append(LocationCheck(f"derived_outputs_gate_{index}", status,
                                        f"{linked} output(s) still linked, {hits} plaintext hit(s)"))
            if gate._evidence is not None:
                scan(json.dumps([r.payload for r in gate._evidence], sort_keys=True,
                                default=str).encode("utf-8"), f"evidence_ledger_gate_{index}")

        checks.extend(LocationCheck(name, "declared-residual", why) for name, why in DECLARED_RESIDUALS)
        certificate = self.certificates.get(subject)
        return ErasureVerification(subject, tuple(checks),
                                   certificate.to_dict() if certificate else {})

    def _restore_admin(self) -> str:
        if not hasattr(self, "_backup_credential"):
            raise RuntimeError("configure a backup credential with with_backup_credential()")
        return self._backup_credential

    def with_backup_credential(self, credential: str) -> ErasureService:
        self._backup_credential = credential
        return self


__all__ = [
    "DECLARED_RESIDUALS", "ErasureService", "ErasureVerification", "LocationCheck",
    "ModelContext", "PIPELINE_STAGES", "PRIVACY_CHECKS", "PrivacyCode", "PrivacyGate",
    "ReleasedOutput",
]
