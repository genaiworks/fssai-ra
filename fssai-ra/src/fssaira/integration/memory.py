"""Governed memory: summaries, caches, vectors and handoffs keep their restrictions.

Every artifact written here -- a memory note, a conversation summary, a cache
entry, a vector entry, an agent handoff -- carries:

* its **label**, taken from the :class:`fssaira.disclosure.DisclosureGate`'s own
  record of the output it came from (a claimed label is never accepted), or the
  join of its parents' labels when derived from other artifacts;
* its **provenance**: the source records (id, version, subject, field, grant,
  purpose) and the parent artifacts it was derived from;
* a **retention deadline**, which a derived artifact may not outlive.

Importing an artifact into a session re-reads its sources through the real gate
under the importing session's own grant, so the session's label becomes at least
the artifact's label *before* the content is handed over. A new session therefore
cannot wash away restrictions by importing an old summary: its outputs carry the
original classes, subjects, purposes and zones, and the gate refuses release to a
recipient that does not dominate them.

Invalidation traverses the derivation graph: a source version change, a grant
revocation, a consent withdrawal, or a direct invalidation marks the artifact and
every artifact derived from it, transitively, unavailable. Unknown or incomplete
lineage is quarantined, never served.

Must NOT / residual risk
------------------------
* Must NOT hand artifact content to a session except through
  :meth:`GovernedMemory.import_into_session`.
* Must NOT be bypassed by copying content out of band. :meth:`screen_output`
  detects verbatim reuse of a stored artifact in an output whose label does not
  dominate it; paraphrase is not detected.
* Residual: invalidation is driven by the events this store is told about (use
  the wrappers that call the gate and invalidate together). Retention expiry makes
  an artifact unavailable here; it does not erase copies elsewhere, and this makes
  no machine-unlearning claim for anything trained on the content.
"""
from __future__ import annotations

import hashlib
import math
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum

from ..disclosure import (
    DataLabel,
    DisclosureGate,
    DisclosureGrant,
    GovernedContext,
    GovernedOutput,
)


class ArtifactKind(str, Enum):
    MEMORY = "memory"
    SUMMARY = "conversation_summary"
    CACHE_ENTRY = "cache_entry"
    VECTOR_ENTRY = "vector_entry"
    HANDOFF = "agent_handoff"


class ArtifactStatus(str, Enum):
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    QUARANTINED = "quarantined"


class MemoryCode:
    OUTPUT_UNKNOWN = "MEMORY_OUTPUT_NOT_ISSUED_BY_GATE"
    UNKNOWN_ARTIFACT = "MEMORY_UNKNOWN_ARTIFACT"
    EXPIRED = "MEMORY_RETENTION_EXPIRED"
    INVALIDATED = "MEMORY_INVALIDATED"
    QUARANTINED = "MEMORY_UNKNOWN_LINEAGE_QUARANTINED"
    RETENTION_INVALID = "MEMORY_RETENTION_INVALID"
    RETENTION_EXTENDS_SOURCE = "MEMORY_RETENTION_EXTENDS_SOURCE"
    IMPORT_PURPOSE_MISMATCH = "MEMORY_IMPORT_PURPOSE_MISMATCH"
    IMPORT_LABEL_NOT_PRESERVED = "MEMORY_IMPORT_LABEL_NOT_PRESERVED"
    LAUNDERED_ARTIFACT = "MEMORY_ARTIFACT_CONTENT_UNDER_LOWER_LABEL"


class MemoryDenied(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SourceRef:
    """One governed source value an artifact was built from."""

    source_id: str
    record_version: int
    subject: str
    field: str
    grant_id: str
    purpose: str


@dataclass
class MemoryArtifact:
    artifact_id: str
    kind: ArtifactKind
    content: str
    label: DataLabel
    sources: tuple[SourceRef, ...]
    parents: tuple[str, ...]
    retention_deadline: float
    holder: str
    origin_session: str
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    reason: str = ""
    imports: list[str] = field(default_factory=list)

    def metadata(self) -> dict:
        """Everything but the content: safe for evidence and inventories."""
        return {"artifact_id": self.artifact_id, "kind": self.kind.value,
                "label": self.label.to_dict(), "parents": list(self.parents),
                "sources": [s.__dict__ for s in self.sources],
                "retention_deadline": self.retention_deadline, "holder": self.holder,
                "origin_session": self.origin_session, "status": self.status.value,
                "reason": self.reason, "imports": list(self.imports),
                "content_digest": hashlib.sha256(self.content.encode()).hexdigest()}


@dataclass(frozen=True)
class ImportedArtifact:
    artifact_id: str
    session_id: str
    content: str
    session_label: DataLabel


def sources_from_context(context: GovernedContext, grant: DisclosureGrant,
                         versions: Mapping[str, int]) -> tuple[SourceRef, ...]:
    """Provenance for every value a gate context released. ``versions`` maps ``subject.field``."""
    refs = []
    for key in sorted(context.labelled):
        subject, _, name = key.partition(".")
        refs.append(SourceRef(key, int(versions[key]), subject, name, grant.grant_id,
                              grant.purpose))
    return tuple(refs)


class GovernedMemory:
    """Labelled, provenance-carrying, retention-bounded artifacts over one gate."""

    def __init__(self, gate: DisclosureGate) -> None:
        self._gate = gate
        self._artifacts: dict[str, MemoryArtifact] = {}
        self._children: dict[str, set[str]] = {}
        self._lock = threading.RLock()
        self._next = 0

    # -- helpers --------------------------------------------------------------
    def _id(self, kind: ArtifactKind) -> str:
        self._next += 1
        return f"{kind.value}-{self._next}"

    def _source_label(self, ref: SourceRef) -> DataLabel:
        policy = self._gate.policy
        cls = policy.field_classes.get(ref.field)
        if cls is None:
            return DataLabel(frozenset({"__undeclared__"}), frozenset({ref.subject}),
                             frozenset(), frozenset())
        return DataLabel(frozenset({cls}), frozenset({ref.subject}), frozenset({ref.purpose}),
                         frozenset(policy.class_zones.get(cls, frozenset())))

    @staticmethod
    def _check_deadline(deadline: float, now: float) -> None:
        if not (math.isfinite(deadline) and math.isfinite(now)) or deadline <= now:
            raise MemoryDenied(MemoryCode.RETENTION_INVALID, "deadline must be finite and future")

    def _available(self, artifact_id: str, now: float) -> MemoryArtifact:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise MemoryDenied(MemoryCode.UNKNOWN_ARTIFACT, artifact_id)
        if artifact.status is ArtifactStatus.QUARANTINED:
            raise MemoryDenied(MemoryCode.QUARANTINED, artifact.reason)
        if artifact.status is ArtifactStatus.INVALIDATED:
            raise MemoryDenied(MemoryCode.INVALIDATED, artifact.reason)
        if not math.isfinite(now) or now >= artifact.retention_deadline:
            raise MemoryDenied(MemoryCode.EXPIRED, artifact_id)
        return artifact

    # -- writes ---------------------------------------------------------------
    def write_from_output(self, output: GovernedOutput, *, kind: ArtifactKind,
                          sources: Iterable[SourceRef], retention_deadline: float,
                          now: float) -> str:
        """Store a gate-issued output. The label is the gate's; lineage must cover it."""
        self._check_deadline(retention_deadline, now)
        try:
            known = self._gate.output(output.output_id)
        except Exception as exc:
            raise MemoryDenied(MemoryCode.OUTPUT_UNKNOWN) from exc
        if known is None or known.digest != output.digest or known.label != output.label:
            raise MemoryDenied(MemoryCode.OUTPUT_UNKNOWN)
        refs = tuple(sources)
        with self._lock:
            artifact_id = self._id(kind)
            artifact = MemoryArtifact(artifact_id, kind, known.content, known.label, refs, (),
                                      float(retention_deadline), known.holder, known.session_id)
            lineage = DataLabel(frozenset(), frozenset(), known.label.purposes,
                                known.label.zones)
            for ref in refs:
                lineage = lineage.join(self._source_label(ref))
            if not refs:
                artifact.status, artifact.reason = ArtifactStatus.QUARANTINED, "no lineage"
            elif not (lineage.classes >= known.label.classes
                      and lineage.subjects >= known.label.subjects
                      and "__undeclared__" not in lineage.classes):
                artifact.status = ArtifactStatus.QUARANTINED
                artifact.reason = "declared lineage does not cover the output label"
            self._artifacts[artifact_id] = artifact
            return artifact_id

    def derive(self, parents: Iterable[str], *, kind: ArtifactKind, content: str,
               retention_deadline: float, now: float, holder: str) -> str:
        """Derive a new artifact. Label is the join of parents; retention cannot extend."""
        self._check_deadline(retention_deadline, now)
        with self._lock:
            parent_ids = tuple(dict.fromkeys(parents))
            if not parent_ids:
                raise MemoryDenied(MemoryCode.QUARANTINED, "a derived artifact needs parents")
            items = [self._available(pid, now) for pid in parent_ids]
            label = items[0].label
            for item in items[1:]:
                label = label.join(item.label)
            ceiling = min(item.retention_deadline for item in items)
            if retention_deadline > ceiling:
                raise MemoryDenied(MemoryCode.RETENTION_EXTENDS_SOURCE,
                                   "a derived artifact may not outlive its sources")
            sources = tuple(dict.fromkeys(ref for item in items for ref in item.sources))
            artifact_id = self._id(kind)
            self._artifacts[artifact_id] = MemoryArtifact(
                artifact_id, kind, content, label, sources, parent_ids,
                float(retention_deadline), holder, items[0].origin_session)
            for pid in parent_ids:
                self._children.setdefault(pid, set()).add(artifact_id)
            return artifact_id

    def handoff(self, artifact_id: str, *, to_holder: str, now: float) -> str:
        """Hand an artifact to another agent: same content, label, lineage and deadline."""
        with self._lock:
            source = self._available(artifact_id, now)
            return self.derive([artifact_id], kind=ArtifactKind.HANDOFF, content=source.content,
                               retention_deadline=source.retention_deadline, now=now,
                               holder=to_holder)

    # -- reads ------------------------------------------------------------------
    def describe(self, artifact_id: str) -> dict:
        with self._lock:
            artifact = self._artifacts.get(artifact_id)
            if artifact is None:
                raise MemoryDenied(MemoryCode.UNKNOWN_ARTIFACT, artifact_id)
            return artifact.metadata()

    def is_available(self, artifact_id: str, now: float) -> bool:
        try:
            with self._lock:
                self._available(artifact_id, now)
            return True
        except MemoryDenied:
            return False

    def import_into_session(self, artifact_id: str, *, requester: str, session_id: str,
                            grant: DisclosureGrant | None, model_endpoint: str,
                            now: float) -> ImportedArtifact:
        """Taint ``session_id`` with the artifact's sources through the gate, then hand over content.

        Raises :class:`fssaira.disclosure.DisclosureDenied` if the importing session has
        no current entitlement to the artifact's sources.
        """
        with self._lock:
            artifact = self._available(artifact_id, now)
            purposes = {ref.purpose for ref in artifact.sources}
            if grant is not None and purposes != {grant.purpose}:
                raise MemoryDenied(MemoryCode.IMPORT_PURPOSE_MISMATCH,
                                   "the importing grant must be for the artifact's purpose")
            self._gate.assemble_context(
                requester=requester, session_id=session_id, grant=grant,
                purpose=next(iter(purposes)),
                subjects=sorted({ref.subject for ref in artifact.sources}),
                fields=sorted({ref.field for ref in artifact.sources}),
                model_endpoint=model_endpoint, now=now,
            )
            label = self._gate.session_label(session_id)
            if label is None or not label.dominates(artifact.label):
                raise MemoryDenied(MemoryCode.IMPORT_LABEL_NOT_PRESERVED)
            artifact.imports.append(session_id)
            return ImportedArtifact(artifact_id, session_id, artifact.content, label)

    def screen_output(self, output: GovernedOutput, *, min_length: int = 16) -> None:
        """Refuse an output that reuses stored artifact content verbatim under a lower label."""
        with self._lock:
            for artifact in self._artifacts.values():
                text = artifact.content
                if len(text) >= min_length and text in output.content \
                        and not output.label.dominates(artifact.label):
                    raise MemoryDenied(MemoryCode.LAUNDERED_ARTIFACT, artifact.artifact_id)

    # -- invalidation -----------------------------------------------------------
    def _invalidate_closure(self, roots: Iterable[str], reason: str) -> tuple[str, ...]:
        seen: list[str] = []
        queue = list(roots)
        while queue:
            current = queue.pop(0)
            if current in seen or current not in self._artifacts:
                continue
            seen.append(current)
            artifact = self._artifacts[current]
            if artifact.status is ArtifactStatus.ACTIVE:
                artifact.status, artifact.reason = ArtifactStatus.INVALIDATED, reason
            queue.extend(sorted(self._children.get(current, ())))
        return tuple(seen)

    def invalidate(self, artifact_id: str, *, reason: str) -> tuple[str, ...]:
        with self._lock:
            return self._invalidate_closure([artifact_id], reason)

    def _roots(self, predicate) -> list[str]:
        return sorted(a.artifact_id for a in self._artifacts.values()
                      if any(predicate(ref) for ref in a.sources))

    def on_source_version(self, source_id: str, new_version: int) -> tuple[str, ...]:
        with self._lock:
            roots = self._roots(lambda r: r.source_id == source_id
                                and r.record_version < new_version)
            return self._invalidate_closure(roots, f"source {source_id} changed")

    def on_grant_revoked(self, grant_id: str) -> tuple[str, ...]:
        with self._lock:
            return self._invalidate_closure(self._roots(lambda r: r.grant_id == grant_id),
                                            f"grant {grant_id} revoked")

    def on_consent_withdrawn(self, subject: str, purpose: str) -> tuple[str, ...]:
        with self._lock:
            roots = self._roots(lambda r: r.subject == subject and r.purpose == purpose)
            return self._invalidate_closure(roots, f"consent withdrawn by {subject}")

    def revoke_grant(self, grant_id: str, *, by: str, reason: str) -> tuple[str, ...]:
        """Revoke at the gate and invalidate dependent artifacts in one call."""
        self._gate.revoke_grant(grant_id, by=by, reason=reason)
        return self.on_grant_revoked(grant_id)

    def withdraw_consent(self, subject: str, purpose: str, *, recorded_by: str) -> tuple[str, ...]:
        """Withdraw consent at the gate and invalidate dependent artifacts in one call."""
        self._gate.withdraw_consent(subject, purpose, recorded_by=recorded_by)
        return self.on_consent_withdrawn(subject, purpose)


__all__ = [
    "ArtifactKind", "ArtifactStatus", "GovernedMemory", "ImportedArtifact", "MemoryArtifact",
    "MemoryCode", "MemoryDenied", "SourceRef", "sources_from_context",
]
