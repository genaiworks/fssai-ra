"""Retrieval as a protected read (paper Section 6.1).

:class:`GovernedRetriever` answers a parsed :class:`~fssaira.integration.typed.ContextRequest`
in this order, and in no other:

1. **Authorize** through the real :class:`fssaira.disclosure.DisclosureGate`
   (``authorize_only``): grant signature, holder, currency, purpose, subject
   scope, minimum-necessary fields, consent, class clearance and residency.
2. **Restrict** the candidate set to the caller's authenticated tenant and the
   exact subjects and fields just authorized.
3. Only then **chunk and score**. A document outside the restriction is never
   chunked, embedded, scored, reranked or served from cache.
4. Preserve **provenance** (source id, record version, tenant, subject, field,
   offsets and label) on every chunk through ranking, and label the returned
   context with the **join** of the returned chunks' labels.

Cached answers are keyed by the full authorization scope and the corpus
generation, and a cache hit is served only after step 1 passes again, so a
revoked grant or withdrawn consent also refuses a cached answer.

Must NOT / residual risk
------------------------
* Must NOT filter final prose instead of candidates: that is too late.
* Must NOT be given a scorer or index that reads outside the candidate set it
  is handed; a scorer with its own global index defeats step 3.
* Residual: ``authorize_only`` writes an ``authorization_recheck`` evidence
  record but opens no gate session, so a model output built from the returned
  chunks must be labelled with :attr:`RetrievedContext.label` by the trusted
  orchestrator (or re-read through ``assemble_context``). Scores and ranks can
  still leak aggregate information inside the authorized scope.
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

#: ``scorer(query, chunk_text) -> float``. Called only for authorized chunks.
Scorer = Callable[[str, str], float]


def embedding_scorer(query: str, text: str) -> float:
    """Default deterministic scorer: dot product of hashed bag-of-words embeddings."""
    return sum(a * b for a, b in zip(hashed_embedding(query), hashed_embedding(text),
                                     strict=True))


@dataclass(frozen=True)
class SourceDocument:
    """One field of one record, as indexed. ``record_version`` is the source's version."""

    source_id: str
    tenant: str
    subject: str
    field: str
    record_version: int
    text: str


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

    def to_dict(self) -> dict:
        return {"source_id": self.source_id, "record_version": self.record_version,
                "tenant": self.tenant, "subject": self.subject, "field": self.field,
                "chunk_index": self.chunk_index, "start": self.start, "end": self.end,
                "label": self.label.to_dict()}


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    score: float
    provenance: Provenance


@dataclass(frozen=True)
class RetrievedContext:
    """Ranked chunks and the join of their labels."""

    request_id: str
    chunks: tuple[RetrievedChunk, ...]
    label: DataLabel
    cache_hit: bool = False
    candidates_scored: int = 0


class RetrievalCorpus:
    """An in-memory source index. Its generation changes on every write."""

    def __init__(self, documents: Iterable[SourceDocument] = ()) -> None:
        self._lock = threading.RLock()
        self._docs: dict[str, SourceDocument] = {}
        self.generation = 0
        for doc in documents:
            self.add(doc)

    def add(self, doc: SourceDocument) -> None:
        with self._lock:
            self._docs[doc.source_id] = doc
            self.generation += 1

    def remove(self, source_id: str) -> None:
        with self._lock:
            self._docs.pop(source_id, None)
            self.generation += 1

    def restricted(self, *, tenant: str, subjects: frozenset[str],
                   fields: frozenset[str]) -> tuple[SourceDocument, ...]:
        """The only way documents leave the corpus: already restricted to a scope."""
        with self._lock:
            return tuple(doc for _id, doc in sorted(self._docs.items())
                         if doc.tenant == tenant and doc.subject in subjects
                         and doc.field in fields)


class GovernedRetriever:
    """Authorize, restrict, then chunk and score. See the module docstring."""

    def __init__(self, gate: DisclosureGate, corpus: RetrievalCorpus, *,
                 scorer: Scorer = embedding_scorer, chunk_size: int = 200,
                 cache: bool = True) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._gate = gate
        self._corpus = corpus
        self._scorer = scorer
        self._chunk_size = chunk_size
        self._cache_enabled = cache
        self._cache: dict[str, tuple[RetrievedChunk, ...]] = {}

    def _chunk_label(self, doc: SourceDocument, purpose: str) -> DataLabel:
        # Built exactly as DisclosureGate labels a value it assembles.
        policy = self._gate.policy
        cls = policy.field_classes[doc.field]
        return DataLabel(classes=frozenset({cls}), subjects=frozenset({doc.subject}),
                         purposes=frozenset({purpose}),
                         zones=frozenset(policy.class_zones.get(cls, frozenset())))

    def _chunks(self, doc: SourceDocument, purpose: str) -> list[tuple[str, Provenance]]:
        label = self._chunk_label(doc, purpose)
        out = []
        text = doc.text or ""
        for index, start in enumerate(range(0, max(len(text), 1), self._chunk_size)):
            end = min(start + self._chunk_size, len(text))
            out.append((text[start:end], Provenance(
                doc.source_id, doc.record_version, doc.tenant, doc.subject, doc.field,
                index, start, end, label)))
        return out

    def _cache_key(self, request: ContextRequest, grant: DisclosureGrant, limit: int) -> str:
        return hashlib.sha256(json.dumps({
            "tenant": request.tenant, "principal": request.principal,
            "grant": grant.grant_id, "grant_signature": grant.signature,
            "purpose": request.purpose, "subjects": sorted(request.subjects),
            "fields": sorted(request.fields), "endpoint": request.model_endpoint,
            "policy_version": request.policy_version, "query": request.query,
            "limit": limit, "generation": self._corpus.generation,
        }, sort_keys=True).encode()).hexdigest()

    def retrieve(self, request: ContextRequest, *, grant: DisclosureGrant | None, now: float,
                 limit: int = 5) -> RetrievedContext:
        """Answer ``request``; raises :class:`fssaira.disclosure.DisclosureDenied` on refusal."""
        # 1. Authorize before anything is read, generated, scored, or served from cache.
        self._gate.authorize_only(
            requester=request.principal, grant=grant, purpose=request.purpose,
            subjects=request.subjects, fields=request.fields,
            model_endpoint=request.model_endpoint, now=now,
            reason=f"retrieval:{request.request_id}",
        )
        assert grant is not None  # authorize_only refuses a missing grant
        key = self._cache_key(request, grant, limit)
        policy = self._gate.policy
        if self._cache_enabled and key in self._cache:
            chunks = self._cache[key]
            return RetrievedContext(request.request_id, chunks, _join(policy, chunks),
                                    cache_hit=True)

        # 2. Restrict candidates to the authenticated tenant and authorized scope.
        candidates = self._corpus.restricted(
            tenant=request.tenant, subjects=frozenset(request.subjects),
            fields=frozenset(request.fields))

        # 3. Chunk and score only what survived.
        scored: list[RetrievedChunk] = []
        for doc in candidates:
            for text, provenance in self._chunks(doc, request.purpose):
                scored.append(RetrievedChunk(text, float(self._scorer(request.query, text)),
                                             provenance))
        ranked = tuple(sorted(scored, key=lambda c: (-c.score, c.provenance.source_id,
                                                     c.provenance.chunk_index))[:limit])
        if self._cache_enabled:
            self._cache[key] = ranked
        # 4. The context label is the join of what is returned.
        return RetrievedContext(request.request_id, ranked, _join(policy, ranked),
                                candidates_scored=len(scored))


def _join(policy, chunks: Iterable[RetrievedChunk]) -> DataLabel:
    label = DataLabel.bottom(policy)
    for chunk in chunks:
        label = label.join(chunk.provenance.label)
    return label


__all__ = [
    "GovernedRetriever", "Provenance", "RetrievalCorpus", "RetrievedChunk", "RetrievedContext",
    "Scorer", "SourceDocument", "embedding_scorer",
]
