"""Retrieval as a protected read (paper Section 6.1).

A retrieved passage is a disclosure. :class:`GovernedRetriever` therefore never
reads text of its own: every passage comes from
:meth:`fssaira.disclosure.DisclosureGate.assemble_context`, which authorizes the
read, touches the record source only after every check passes, writes read
evidence, labels the session, and returns each value with the label the gate
computed for it.

Order of operations, and no other:

1. **Restrict to the caller's authenticated tenant.** The index holds provenance
   only (source id, tenant, subject, field, version), so the scope handed to the
   gate never covers another tenant's records.
2. **Read through the gate.** ``assemble_context`` applies grant signature,
   holder, currency, purpose, subject scope, minimum-necessary fields, consent,
   class clearance and residency, then reads.
3. **Chunk and score only the values the gate issued.** Nothing else is ever
   chunked, embedded, scored, reranked or served from a cache.
4. **Preserve provenance** (source id, record version, tenant, subject, field,
   offsets, value id and the gate's label) through chunking and ranking.

Labels come from the gate. :attr:`RetrievedContext.label` is the gate's
``GovernedContext.label``, and :attr:`RetrievedContext.value_ids` names the
issued values so an output is labelled with
``gate.derive_from_values(..., sources=context.value_ids.values())``.

Must NOT / residual risk
------------------------
* Must NOT filter final prose instead of candidates: that is too late.
* Must NOT label an output from anything this module returns by itself. An
  orchestrator that computes its own label reintroduces self-labelling, which is
  what Rule 2 forbids; the gate labels, always.
* Must NOT be given an index or scorer that can reach text the gate did not
  issue; a scorer with its own global corpus defeats step 3.
* A cache hit re-authorizes through the gate before anything is returned, so a
  revoked grant or withdrawn consent also refuses a cached answer. Cached
  rankings are reused only while the gate's values are byte-identical.
* Residual: scores and ranks can still leak aggregate information inside the
  authorized scope, and the index's own metadata (which subjects and fields
  exist for a tenant) is not itself a governed read.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..disclosure import DataLabel, DisclosureGate, DisclosureGrant
from ..encrypted_records import hashed_embedding
from .typed import ContextRequest

#: ``scorer(query, chunk_text) -> float``. Called only for gate-issued chunks.
Scorer = Callable[[str, str], float]


def embedding_scorer(query: str, text: str) -> float:
    """Default deterministic scorer: dot product of hashed bag-of-words embeddings."""
    return sum(a * b for a, b in zip(hashed_embedding(query), hashed_embedding(text),
                                     strict=True))


@dataclass(frozen=True)
class IndexedSource:
    """Provenance for one field of one record. It holds no text: the gate does."""

    source_id: str
    tenant: str
    subject: str
    field: str
    record_version: int

    @property
    def key(self) -> str:
        """The gate's value key for this source (``subject.field``)."""
        return f"{self.subject}.{self.field}"


@dataclass(frozen=True)
class Provenance:
    """Where a chunk came from, carried unchanged through chunking and ranking."""

    source_id: str
    record_version: int
    tenant: str
    subject: str
    field: str
    chunk_index: int
    start: int
    end: int
    label: DataLabel
    value_id: str

    def to_dict(self) -> dict:
        return {"source_id": self.source_id, "record_version": self.record_version,
                "tenant": self.tenant, "subject": self.subject, "field": self.field,
                "chunk_index": self.chunk_index, "start": self.start, "end": self.end,
                "label": self.label.to_dict(), "value_id": self.value_id}


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float
    provenance: Provenance


@dataclass(frozen=True)
class RetrievedContext:
    """Ranked chunks, the gate's session label, and the gate-issued value ids."""

    request_id: str
    session_id: str
    receipt_id: str
    chunks: tuple[RetrievedChunk, ...]
    label: DataLabel
    value_ids: dict[str, str]
    cache_hit: bool = False
    candidates_scored: int = 0


class RetrievalIndex:
    """Provenance for indexed record fields. Its generation changes on every write."""

    def __init__(self, sources: Iterable[IndexedSource] = ()) -> None:
        self._lock = threading.RLock()
        self._sources: dict[str, IndexedSource] = {}
        self.generation = 0
        for source in sources:
            self.add(source)

    def add(self, source: IndexedSource) -> None:
        with self._lock:
            self._sources[source.source_id] = source
            self.generation += 1

    def remove(self, source_id: str) -> None:
        with self._lock:
            self._sources.pop(source_id, None)
            self.generation += 1

    def restricted(self, *, tenant: str, subjects: frozenset[str],
                   fields: frozenset[str]) -> tuple[IndexedSource, ...]:
        """The only way sources leave the index: already restricted to one tenant and scope."""
        with self._lock:
            return tuple(source for _id, source in sorted(self._sources.items())
                         if source.tenant == tenant and source.subject in subjects
                         and source.field in fields)


class GovernedRetriever:
    """Restrict to the tenant, read through the gate, then chunk and score. See the module docstring."""

    def __init__(self, gate: DisclosureGate, index: RetrievalIndex, *,
                 scorer: Scorer = embedding_scorer, chunk_size: int = 200,
                 cache: bool = True) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._gate = gate
        self._index = index
        self._scorer = scorer
        self._chunk_size = chunk_size
        self._cache_enabled = cache
        self._cache: dict[str, tuple[str, tuple[RetrievedChunk, ...]]] = {}

    def _chunks(self, source: IndexedSource, text: str, label: DataLabel,
                value_id: str) -> list[tuple[str, Provenance]]:
        out = []
        text = text or ""
        for index, start in enumerate(range(0, max(len(text), 1), self._chunk_size)):
            end = min(start + self._chunk_size, len(text))
            out.append((text[start:end], Provenance(
                source.source_id, source.record_version, source.tenant, source.subject,
                source.field, index, start, end, label, value_id)))
        return out

    def _cache_key(self, request: ContextRequest, grant: DisclosureGrant, limit: int,
                   scope: tuple[IndexedSource, ...]) -> str:
        return hashlib.sha256(json.dumps({
            "tenant": request.tenant, "principal": request.principal,
            "grant": grant.grant_id, "grant_signature": grant.signature,
            "purpose": request.purpose, "endpoint": request.model_endpoint,
            "policy_version": request.policy_version, "query": request.query,
            "limit": limit, "generation": self._index.generation,
            "scope": [s.source_id for s in scope],
        }, sort_keys=True).encode()).hexdigest()

    def retrieve(self, request: ContextRequest, *, grant: DisclosureGrant | None, now: float,
                 session_id: str | None = None, limit: int = 5) -> RetrievedContext:
        """Answer ``request``; raises :class:`fssaira.disclosure.DisclosureDenied` on refusal."""
        # 1. Restrict the scope to the authenticated caller's tenant, before any read.
        scope = self._index.restricted(
            tenant=request.tenant, subjects=frozenset(request.subjects),
            fields=frozenset(request.fields))
        subjects = sorted({source.subject for source in scope})
        fields = sorted({source.field for source in scope})
        session = session_id or f"retrieval:{request.request_id}"

        # 2. The gate authorizes, reads, evidences and labels. Out-of-scope subjects
        #    and fields are still sent when the caller asked for them, so the gate,
        #    not this module, decides and records the refusal.
        context = self._gate.assemble_context(
            requester=request.principal, session_id=session, grant=grant,
            purpose=request.purpose,
            subjects=subjects or sorted(request.subjects),
            fields=fields or sorted(request.fields),
            model_endpoint=request.model_endpoint, now=now)
        assert grant is not None  # the gate refuses a missing grant

        issued = {source.key: source for source in scope if source.key in context.labelled}
        fingerprint = hashlib.sha256(json.dumps(
            {key: context.labelled[key].text for key in sorted(issued)}, sort_keys=True
        ).encode()).hexdigest()
        key = self._cache_key(request, grant, limit, scope)
        if self._cache_enabled and key in self._cache:
            cached_fingerprint, chunks = self._cache[key]
            if cached_fingerprint == fingerprint:
                return RetrievedContext(request.request_id, context.session_id, context.receipt_id,
                                        chunks, context.label, context.value_ids, cache_hit=True)

        # 3. Chunk and score only what the gate issued.
        scored: list[RetrievedChunk] = []
        for value_key, source in sorted(issued.items()):
            value = context.labelled[value_key]
            for text, provenance in self._chunks(source, value.text, value.label, value.value_id):
                scored.append(RetrievedChunk(text, float(self._scorer(request.query, text)),
                                             provenance))
        ranked = tuple(sorted(scored, key=lambda c: (-c.score, c.provenance.source_id,
                                                     c.provenance.chunk_index))[:limit])
        if self._cache_enabled:
            self._cache[key] = (fingerprint, ranked)
        # 4. The label is the gate's, never one computed here.
        return RetrievedContext(request.request_id, context.session_id, context.receipt_id,
                                ranked, context.label, context.value_ids,
                                candidates_scored=len(scored))


__all__ = [
    "GovernedRetriever", "IndexedSource", "Provenance", "RetrievalIndex", "RetrievedChunk",
    "RetrievedContext", "Scorer", "embedding_scorer",
]
