"""Retrieval is a protected read: authorize and restrict before scoring."""
from __future__ import annotations

import json

import pytest

from fssaira.disclosure import DataLabel, DisclosureCode, DisclosureDenied
from fssaira.disclosure_eval import AGENT, ARMS, NOW, SUBJECT_A, SUBJECT_B, DisclosureFixture
from fssaira.integration.retrieval import GovernedRetriever, RetrievalCorpus, SourceDocument
from fssaira.integration.typed import (
    CallerContext,
    DestinationRegistry,
    parse_context_request,
)
from fssaira.profiles import ApplicationProfile

POLICY = ApplicationProfile.load("profiles/healthcare_record_access.yaml").disclosure


class RecordingScorer:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, query: str, text: str) -> float:
        self.seen.append(text)
        return float(len(set(query.split()) & set(text.split())))


def build(tenant: str = "hospital-1"):
    fx = DisclosureFixture(POLICY)
    gate = fx.gate(ARMS["this_architecture"])
    granted = fx.granted_fields()
    docs = [SourceDocument(f"a-{name}", "hospital-1", SUBJECT_A, name, 3,
                           f"ALLOWED {name} note for {SUBJECT_A} " * 12) for name in granted]
    docs += [
        SourceDocument("forbidden-subject", "hospital-1", SUBJECT_B, granted[0], 1,
                       "FORBIDDEN-SUBJECT note"),
        SourceDocument("forbidden-field", "hospital-1", SUBJECT_A, fx.widen_field(), 1,
                       "FORBIDDEN-FIELD note"),
        SourceDocument("forbidden-tenant", "hospital-2", SUBJECT_A, granted[0], 1,
                       "FORBIDDEN-TENANT note"),
    ]
    scorer = RecordingScorer()
    retriever = GovernedRetriever(gate, RetrievalCorpus(docs), scorer=scorer, chunk_size=64)
    caller = CallerContext(principal=AGENT, tenant=tenant, policy_version="1",
                           authenticated_by="test-authenticator")
    registry = DestinationRegistry.from_policy(POLICY, ())
    return fx, gate, retriever, scorer, caller, registry


def request(fx, caller, registry, **overrides):
    body = {"schema_version": "1.0", "kind": "context_request", "request_id": "ctx-1",
            "purpose": fx.purpose, "subjects": [SUBJECT_A], "fields": list(fx.granted_fields()),
            "model_endpoint": fx.endpoint, "query": "ALLOWED note"}
    body.update(overrides)
    return parse_context_request(json.dumps(body).encode(), caller=caller, registry=registry)


def test_forbidden_documents_never_enter_scoring():
    fx, _gate, retriever, scorer, caller, registry = build()
    context = retriever.retrieve(request(fx, caller, registry), grant=fx.grant(), now=NOW + 1,
                                 limit=50)
    assert context.chunks
    assert scorer.seen and all("FORBIDDEN" not in text for text in scorer.seen)
    assert {c.provenance.source_id for c in context.chunks} <= \
        {f"a-{name}" for name in fx.granted_fields()}


def test_out_of_scope_request_is_refused_before_candidate_generation():
    fx, _gate, retriever, scorer, caller, registry = build()
    with pytest.raises(DisclosureDenied) as denied:
        retriever.retrieve(request(fx, caller, registry, subjects=[SUBJECT_A, SUBJECT_B]),
                           grant=fx.grant(), now=NOW + 1)
    assert denied.value.code == DisclosureCode.SUBJECT_OUT_OF_SCOPE
    with pytest.raises(DisclosureDenied) as denied:
        retriever.retrieve(request(fx, caller, registry,
                                   fields=[*fx.granted_fields(), fx.widen_field()]),
                           grant=fx.grant(), now=NOW + 1)
    assert denied.value.code == DisclosureCode.FIELD_NOT_MINIMUM_NECESSARY
    with pytest.raises(DisclosureDenied):
        retriever.retrieve(request(fx, caller, registry), grant=None, now=NOW + 1)
    assert scorer.seen == []


def test_tenant_comes_from_the_authenticated_caller_only():
    fx, _gate, retriever, scorer, caller, registry = build(tenant="hospital-2")
    context = retriever.retrieve(request(fx, caller, registry), grant=fx.grant(), now=NOW + 1,
                                 limit=50)
    assert {c.provenance.tenant for c in context.chunks} == {"hospital-2"}
    assert all("ALLOWED" not in text for text in scorer.seen)


def test_provenance_survives_chunking_and_ranking_and_label_is_the_join():
    fx, _gate, retriever, _scorer, caller, registry = build()
    context = retriever.retrieve(request(fx, caller, registry), grant=fx.grant(), now=NOW + 1,
                                 limit=50)
    assert len(context.chunks) > len(fx.granted_fields())  # really chunked
    expected = DataLabel.bottom(POLICY)
    for chunk in context.chunks:
        p = chunk.provenance
        assert p.record_version == 3 and p.subject == SUBJECT_A
        assert p.label.classes == {POLICY.field_classes[p.field]}
        assert p.end - p.start == len(chunk.text)
        expected = expected.join(p.label)
    assert context.label == expected
    assert context.label.dominates(fx.honest_label()) and fx.honest_label().dominates(context.label)


def test_cached_answer_is_refused_after_revocation_and_consent_withdrawal():
    fx, gate, retriever, scorer, caller, registry = build()
    grant = fx.grant()
    first = retriever.retrieve(request(fx, caller, registry), grant=grant, now=NOW + 1)
    calls = len(scorer.seen)
    hit = retriever.retrieve(request(fx, caller, registry), grant=grant, now=NOW + 2)
    assert hit.cache_hit and hit.chunks == first.chunks and len(scorer.seen) == calls

    gate.withdraw_consent(SUBJECT_A, fx.purpose, recorded_by="subject")
    with pytest.raises(DisclosureDenied) as denied:
        retriever.retrieve(request(fx, caller, registry), grant=grant, now=NOW + 3)
    assert denied.value.code == DisclosureCode.CONSENT_WITHDRAWN

    fx2, gate2, retriever2, _s, caller2, registry2 = build()
    grant2 = fx2.grant()
    retriever2.retrieve(request(fx2, caller2, registry2), grant=grant2, now=NOW + 1)
    gate2.revoke_grant(grant2.grant_id, by="data-owner", reason="test")
    with pytest.raises(DisclosureDenied) as denied:
        retriever2.retrieve(request(fx2, caller2, registry2), grant=grant2, now=NOW + 2)
    assert denied.value.code == DisclosureCode.GRANT_REVOKED
