"""Sensitivity-aware semantic routing that cannot widen authority or residency.

:class:`fssaira.bounded_intelligence.TaskRouter` picks a model by keyword. That
is a reasonable performance device and a dangerous privacy device: the words in a
request are written by whoever wrote the request, including an injected document,
so a keyword router can be talked into sending restricted data to the cheapest
endpoint by a prompt that simply avoids the sensitive words.

This router makes two separate decisions and keeps them apart.

1. **What is being asked.** The request is classified against *intent
   prototypes the domain pack declares*, by deterministic TF-IDF cosine
   similarity (no network, no model, no new dependency). An optional embedding
   backend can replace the vectoriser behind :class:`EmbeddingBackend`; the
   Ollama implementation is provided and is never used by tests or results.
2. **How sensitive it is.** Sensitivity is *not* inferred from the text. It is
   the set of data classes of the fields the orchestrator will actually request,
   joined with the fields the classified intent needs. Classification can
   therefore only add sensitivity, never remove it; a request the classifier
   cannot place is treated as touching every declared class.

The endpoint is then the **lowest-cost registered endpoint whose zone may
process every one of those classes**. Restricted classes end up on the local
model because the pack says only the local zone may process them, not because
the router prefers local; low-sensitivity work goes to a cheaper approved cloud
endpoint when the pack allows it, which is the utility the router exists for.
Endpoint names that appear in the request text are ignored.

Routing is advisory
-------------------
The router's choice is a suggestion to the orchestrator. The gate's residency
check and the attestation registry still decide. A router that is subverted,
misconfigured, or replaced can pick a worse model; it cannot put a class in a zone
the pack forbids, because the gate refuses that context regardless of who chose
the endpoint. When no permitted, registered endpoint exists the router refuses
(``ROUTE_NO_PERMITTED_ENDPOINT``) rather than degrading to a permissive one.
"""
from __future__ import annotations

import json
import math
import re
import urllib.request
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .disclosure import DisclosureDenied, DisclosurePolicy


class RoutingCode:
    ROUTE_NO_PERMITTED_ENDPOINT = "ROUTE_NO_PERMITTED_ENDPOINT"
    ROUTE_FIELD_UNDECLARED = "ROUTE_FIELD_UNDECLARED"


class RoutingRefused(DisclosureDenied):
    """No endpoint may lawfully and verifiably process this request."""


_STOPWORDS = frozenset("""
a an and are as at be but by for from has have i in into is it its me my of on or our please
so that the their them then there these this to up us was we what when which who will with you
your can could would should just also any all each every some about over per via
""".split())
_WORD = re.compile(r"[a-z]+")


def _terms(text: str) -> list[str]:
    words = []
    for word in _WORD.findall(text.lower()):
        if len(word) < 3 or word in _STOPWORDS:
            continue
        for suffix in ("ing", "ies", "es", "ed", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[: -len(suffix)] + ("y" if suffix == "ies" else "")
                break
        words.append(word)
    return words


class EmbeddingBackend(Protocol):
    """Anything that turns texts into comparable vectors."""

    name: str

    def fit(self, corpus: Sequence[str]) -> None: ...

    def vector(self, text: str) -> dict[str, float]: ...


class TfidfBackend:
    """Deterministic bag-of-words TF-IDF over the pack's own prototype phrases."""

    name = "tfidf"

    def __init__(self) -> None:
        self._idf: dict[str, float] = {}

    def fit(self, corpus: Sequence[str]) -> None:
        documents = [set(_terms(text)) for text in corpus]
        total = len(documents)
        frequency = Counter(term for document in documents for term in document)
        self._idf = {term: math.log((1 + total) / (1 + count)) + 1.0
                     for term, count in sorted(frequency.items())}

    def vector(self, text: str) -> dict[str, float]:
        counts = Counter(_terms(text))
        weights = {term: count * self._idf[term] for term, count in sorted(counts.items())
                   if term in self._idf}
        norm = math.sqrt(sum(value * value for value in weights.values()))
        return {term: value / norm for term, value in weights.items()} if norm else {}


class OllamaEmbeddingBackend:
    """Dense vectors from a local Ollama ``/api/embeddings`` endpoint.

    Provided so a deployment can swap in a better classifier without touching the
    routing rule. Never used by the tests or the published results, which must
    not depend on a network or on model weights. ``opener`` is injectable.
    """

    name = "ollama-embeddings"

    def __init__(self, *, model: str = "nomic-embed-text", host: str = "http://localhost:11434",
                 timeout: float = 10.0, opener: Callable[..., Any] | None = None) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def fit(self, corpus: Sequence[str]) -> None:
        return None

    def vector(self, text: str) -> dict[str, float]:
        request = urllib.request.Request(
            f"{self.host}/api/embeddings",
            data=json.dumps({"model": self.model, "prompt": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self._open(request, timeout=self.timeout) as response:
            values = json.loads(response.read()).get("embedding", [])
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return {str(index): value / norm for index, value in enumerate(values)}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(term, 0.0) for term, value in left.items())


@dataclass(frozen=True)
class RouteCandidate:
    endpoint: str
    zone: str
    cost: float
    permitted: bool
    registered: bool

    def to_dict(self) -> dict:
        return {"endpoint": self.endpoint, "zone": self.zone, "cost": self.cost,
                "permitted": self.permitted, "registered": self.registered}


@dataclass(frozen=True)
class RoutingDecision:
    """What the router suggests, and everything needed to see why."""

    intent: str | None
    score: float
    fields: tuple[str, ...]
    classes: tuple[str, ...]
    endpoint: str
    zone: str
    cost: float
    candidates: tuple[RouteCandidate, ...] = field(default_factory=tuple)
    confident: bool = True

    def to_dict(self) -> dict:
        return {"intent": self.intent, "score": round(self.score, 4), "fields": list(self.fields),
                "classes": list(self.classes), "endpoint": self.endpoint, "zone": self.zone,
                "cost": self.cost, "confident": self.confident,
                "candidates": [c.to_dict() for c in self.candidates]}


class SemanticRouter:
    """Classify, derive sensitivity from fields, pick the cheapest permitted endpoint.

    ``privacy`` is the pack's :class:`fssaira.privacy.PrivacyPolicy` (it carries the
    intents and endpoint costs). ``registry`` is optional; when given, only
    registered endpoints are candidates.
    """

    def __init__(self, policy: DisclosurePolicy, privacy: Any, *, registry: Any = None,
                 backend: EmbeddingBackend | None = None, threshold: float = 0.2) -> None:
        self.policy = policy
        self.privacy = privacy
        self.registry = registry
        self.threshold = threshold
        self.backend = backend if backend is not None else TfidfBackend()
        corpus = [example for intent in privacy.intents.values() for example in intent.examples]
        self.backend.fit(corpus)
        self._prototypes = [
            (name, [self.backend.vector(example) for example in intent.examples])
            for name, intent in sorted(privacy.intents.items())
        ]

    def classify(self, text: str) -> tuple[str | None, float]:
        query = self.backend.vector(text)
        best: tuple[str | None, float] = (None, 0.0)
        for name, vectors in self._prototypes:
            score = max((_cosine(query, vector) for vector in vectors), default=0.0)
            if score > best[1] + 1e-12:
                best = (name, score)
        return best

    def sensitivity(self, fields: Iterable[str]) -> tuple[str, ...]:
        classes = set()
        for name in fields:
            if name not in self.policy.field_classes:
                raise RoutingRefused(RoutingCode.ROUTE_FIELD_UNDECLARED,
                                     f"field {name} is not declared by the pack")
            classes.add(self.policy.field_classes[name])
        return tuple(sorted(classes))

    def route(self, text: str, *, fields: Iterable[str] = ()) -> RoutingDecision:
        intent, score = self.classify(text)
        requested = set(fields)
        confident = intent is not None and score >= self.threshold
        if confident:
            requested |= set(self.privacy.intents[intent].fields)
        if not requested:
            # Nothing named and nothing recognised: assume the most sensitive case.
            requested = set(self.policy.field_classes)
        classes = self.sensitivity(requested)
        candidates = []
        for endpoint, zone in sorted(self.policy.endpoints.items()):
            profile = self.privacy.endpoints.get(endpoint)
            cost = profile.cost if profile is not None else math.inf
            permitted = all(zone in self.policy.class_zones.get(cls, ()) for cls in classes)
            registered = self.registry is None or self.registry.is_registered(endpoint)
            candidates.append(RouteCandidate(endpoint, zone, cost, permitted, registered))
        eligible = [c for c in candidates if c.permitted and c.registered and c.cost < math.inf]
        if not eligible:
            raise RoutingRefused(
                RoutingCode.ROUTE_NO_PERMITTED_ENDPOINT,
                f"no registered endpoint may process {', '.join(classes)}; refusing rather "
                "than degrading to a less protected one",
            )
        best = min(eligible, key=lambda c: (c.cost, c.endpoint))
        return RoutingDecision(intent if confident else None, score, tuple(sorted(requested)),
                               classes, best.endpoint, best.zone, best.cost, tuple(candidates),
                               confident)


__all__ = [
    "EmbeddingBackend", "OllamaEmbeddingBackend", "RouteCandidate", "RoutingCode",
    "RoutingDecision", "RoutingRefused", "SemanticRouter", "TfidfBackend",
]
