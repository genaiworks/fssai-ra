"""Retrieval is a protected read: every chunk comes from the gate's own read.

R9 (a2's review): the previous version authorized through ``authorize_only``,
which opens no gate session, so an orchestrator had to attach a label itself —
exactly the self-labelling Rule 2 forbids. This version reads exclusively
through ``DisclosureGate.assemble_context``: the gate authorizes, reads,
evidences, and labels; the label on ``RetrievedContext`` is always the gate's.
"""
from __future__ import annotations

import json

import pytest

from fssaira.disclosure import DisclosureCode, DisclosureDenied
from fssaira.disclosure_eval import AGENT, ARMS, NOW, SUBJECT_A, SUBJECT_B, DisclosureFixture
from fssaira.integration.retrieval import GovernedRetriever, IndexedSource, RetrievalIndex
from fssaira.integration.typed import (
    CallerContext,
    DestinationRegistry,
    parse_context_request,
)
from fssaira.profiles import ApplicationProfile

POLICY = ApplicationProfile.load("profiles/healthcare_record_access.yaml").disclosure
CHUNK_SIZE = 8  # small enough that one synthetic ~26-character value yields several chunks


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
    sources = [IndexedSource(f"a-{name}", "hospital-1", SUBJECT_A, name, 3) for name in granted]
    sources += [
        IndexedSource("forbidden-subject", "hospital-1", SUBJECT_B, granted[0], 1),
        IndexedSource("forbidden-field", "hospital-1", SUBJECT_A, fx.widen_field(), 1),
        IndexedSource("forbidden-tenant", "hospital-2", SUBJECT_A, granted[0], 1),
    ]
    scorer = RecordingScorer()
    retriever = GovernedRetriever(gate, RetrievalIndex(sources), scorer=scorer, chunk_size=CHUNK_SIZE)
    caller = CallerContext(principal=AGENT, tenant=tenant, policy_version="1",
                           authenticated_by="test-authenticator")
    registry = DestinationRegistry.from_policy(POLICY, ())
    return fx, gate, retriever, scorer, caller, registry


def request(fx, caller, registry, **overrides):
    body = {"schema_version": "1.0", "kind": "context_request", "request_id": "ctx-1",
            "purpose": fx.purpose, "subjects": [SUBJECT_A], "fields": list(fx.granted_fields()),
            "model_endpoint": fx.endpoint, "query": "SYNTHETIC"}
    body.update(overrides)
    return parse_context_request(json.dumps(body).encode(), caller=caller, registry=registry)


def test_only_gate_issued_sources_ever_reach_the_scorer():
    fx, _gate, retriever, scorer, caller, registry = build()
    context = retriever.retrieve(request(fx, caller, registry), grant=fx.grant(), now=NOW + 1,
                                 limit=50)
    assert context.chunks
    granted_ids = {f"a-{name}" for name in fx.granted_fields()}
    assert {c.provenance.source_id for c in context.chunks} <= granted_ids
    # The forbidden field/subject/tenant sources' text never reaches the scorer either.
    assert scorer.seen and all("FORBIDDEN" not in text for text in scorer.seen)


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


def test_the_index_restricts_to_the_authenticated_tenant_before_the_gate_is_touched():
    fx, _gate, retriever, scorer, caller, registry = build(tenant="hospital-2")
    context = retriever.retrieve(request(fx, caller, registry), grant=fx.grant(), now=NOW + 1,
                                 limit=50)
    assert {c.provenance.tenant for c in context.chunks} == {"hospital-2"}
    assert all("hospital-1" not in text for text in scorer.seen)


def test_the_label_is_exactly_the_gates_governed_context_label():
    """The orchestrator computes no label of its own; RetrievedContext.label is the gate's."""
    fx, gate, retriever, _scorer, caller, registry = build()
    grant = fx.grant()
    session_id = "shared-session"
    context = retriever.retrieve(request(fx, caller, registry), grant=grant, now=NOW + 1,
                                 session_id=session_id, limit=50)
    assert context.label == gate.session_label(session_id)
    assert context.label.dominates(fx.honest_label()) and fx.honest_label().dominates(context.label)


def test_provenance_survives_chunking_and_ranking_and_carries_the_issued_value_id():
    fx, gate, retriever, _scorer, caller, registry = build()
    context = retriever.retrieve(request(fx, caller, registry), grant=fx.grant(), now=NOW + 1,
                                 limit=50)
    assert len(context.chunks) > len(fx.granted_fields())  # really chunked
    for chunk in context.chunks:
        p = chunk.provenance
        assert p.record_version == 3 and p.subject == SUBJECT_A
        assert p.label.classes == {POLICY.field_classes[p.field]}
        assert p.end - p.start == len(chunk.text)
        assert p.value_id  # the gate's own value identity, not one this module invented
        assert p.value_id in context.value_ids.values()


def test_an_output_built_from_the_context_is_labelled_by_the_gate_not_the_orchestrator():
    """The intended downstream use: derive_from_values over the issued value ids."""
    fx, gate, retriever, _scorer, caller, registry = build()
    grant = fx.grant()
    session_id = "downstream-session"
    context = retriever.retrieve(request(fx, caller, registry), grant=grant, now=NOW + 1,
                                 session_id=session_id, limit=50)
    output = gate.derive_from_values(requester=AGENT, session_id=session_id, content="a drafted answer",
                                     sources=context.value_ids.values())
    assert output.label == context.label


def test_a_cached_answer_is_refused_after_revocation_and_consent_withdrawal():
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
