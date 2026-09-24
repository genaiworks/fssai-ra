"""Governed memory: restrictions survive import, retention and derivation."""
from __future__ import annotations

import pytest

from fssaira.disclosure import DisclosureDenied
from fssaira.disclosure_eval import AGENT, ARMS, NOW, SUBJECT_A, DisclosureFixture
from fssaira.integration.memory import (
    ArtifactKind,
    GovernedMemory,
    MemoryCode,
    MemoryDenied,
    sources_from_context,
)
from fssaira.profiles import ApplicationProfile

POLICY = ApplicationProfile.load("profiles/healthcare_record_access.yaml").disclosure
DEADLINE = NOW + 10_000


def summary_fixture():
    fx = DisclosureFixture(POLICY)
    gate = fx.gate(ARMS["this_architecture"])
    grant = fx.grant()
    context = fx.read(gate, grant)
    content = "SUMMARY of record: " + " ".join(sorted(context.values.values()))
    output = gate.derive_output(requester=AGENT, session_id="session-1", content=content)
    memory = GovernedMemory(gate)
    versions = dict.fromkeys(context.labelled, 1)
    summary = memory.write_from_output(output, kind=ArtifactKind.SUMMARY,
                                       sources=sources_from_context(context, grant, versions),
                                       retention_deadline=DEADLINE, now=NOW + 1)
    return fx, gate, memory, grant, output, summary


def test_a_new_session_cannot_wash_away_restrictions_by_importing_an_old_summary():
    fx, gate, memory, _grant, output, summary = summary_fixture()
    recipient, purpose = fx.laundering_recipient()
    with pytest.raises(DisclosureDenied):
        gate.release(output, recipient=recipient, purpose=purpose, now=NOW + 2)

    # The hazard is real at the gate alone: raw content in a fresh session is unlabelled.
    washed = gate.derive_output(requester=AGENT, session_id="session-wash",
                                content=output.content)
    assert gate.release(washed, recipient=recipient, purpose=purpose, now=NOW + 2)
    with pytest.raises(MemoryDenied) as denied:
        memory.screen_output(washed)
    assert denied.value.code == MemoryCode.LAUNDERED_ARTIFACT

    # The governed path: importing taints the new session before content is handed over.
    imported = memory.import_into_session(summary, requester=AGENT, session_id="session-2",
                                          grant=fx.grant(grant_id="grant-2"),
                                          model_endpoint=fx.endpoint, now=NOW + 3)
    assert imported.session_label.dominates(output.label)
    assert gate.session_label("session-2").dominates(output.label)
    reuse = gate.derive_output(requester=AGENT, session_id="session-2",
                               content="follow-up: " + imported.content)
    assert reuse.label.dominates(output.label)
    memory.screen_output(reuse)  # carries the label, so not laundering
    with pytest.raises(DisclosureDenied):
        gate.release(reuse, recipient=recipient, purpose=purpose, now=NOW + 4)


def test_import_without_current_entitlement_is_refused_and_hands_over_nothing():
    fx, _gate, memory, _grant, _output, summary = summary_fixture()
    with pytest.raises(DisclosureDenied):
        memory.import_into_session(summary, requester=AGENT, session_id="session-3", grant=None,
                                   model_endpoint=fx.endpoint, now=NOW + 3)
    narrow = fx.grant(grant_id="grant-narrow", fields=fx.granted_fields()[:1])
    with pytest.raises(DisclosureDenied):
        memory.import_into_session(summary, requester=AGENT, session_id="session-3", grant=narrow,
                                   model_endpoint=fx.endpoint, now=NOW + 3)
    assert memory.describe(summary)["imports"] == []


def test_expired_retention_makes_artifacts_unavailable_and_derivatives_cannot_outlive():
    fx, _gate, memory, _grant, _output, summary = summary_fixture()
    with pytest.raises(MemoryDenied) as denied:
        memory.derive([summary], kind=ArtifactKind.CACHE_ENTRY, content="cached",
                      retention_deadline=DEADLINE + 1, now=NOW + 2, holder=AGENT)
    assert denied.value.code == MemoryCode.RETENTION_EXTENDS_SOURCE
    assert memory.is_available(summary, NOW + 2)
    assert not memory.is_available(summary, DEADLINE)
    with pytest.raises(MemoryDenied) as denied:
        memory.import_into_session(summary, requester=AGENT, session_id="late",
                                   grant=fx.grant(grant_id="g-late", ttl_seconds=20_000),
                                   model_endpoint=fx.endpoint, now=DEADLINE)
    assert denied.value.code == MemoryCode.EXPIRED


def test_forged_output_and_unknown_lineage_are_not_served():
    from dataclasses import replace

    from fssaira.disclosure import DataLabel

    fx, gate, memory, grant, output, _summary = summary_fixture()
    forged = replace(output, label=DataLabel.bottom(POLICY))
    with pytest.raises(MemoryDenied) as denied:
        memory.write_from_output(forged, kind=ArtifactKind.MEMORY, sources=(),
                                 retention_deadline=DEADLINE, now=NOW + 1)
    assert denied.value.code == MemoryCode.OUTPUT_UNKNOWN
    orphan = memory.write_from_output(output, kind=ArtifactKind.VECTOR_ENTRY, sources=(),
                                      retention_deadline=DEADLINE, now=NOW + 1)
    with pytest.raises(MemoryDenied) as denied:
        memory.import_into_session(orphan, requester=AGENT, session_id="s", grant=grant,
                                   model_endpoint=fx.endpoint, now=NOW + 2)
    assert denied.value.code == MemoryCode.QUARANTINED


def _chain():
    fx, gate, memory, grant, output, summary = summary_fixture()
    level2 = memory.derive([summary], kind=ArtifactKind.CACHE_ENTRY, content="cache of summary",
                           retention_deadline=DEADLINE, now=NOW + 2, holder=AGENT)
    level3 = memory.handoff(level2, to_holder="other-agent", now=NOW + 2)
    # An unrelated artifact built from a different grant on one field only.
    field0 = fx.granted_fields()[0]
    other_grant = fx.grant(grant_id="grant-other", fields=(field0,))
    other_ctx = fx.read(gate, other_grant, session_id="session-other", fields=(field0,))
    other_out = gate.derive_output(requester=AGENT, session_id="session-other", content="other")
    unrelated = memory.write_from_output(
        other_out, kind=ArtifactKind.MEMORY,
        sources=sources_from_context(other_ctx, other_grant, dict.fromkeys(other_ctx.labelled, 1)),
        retention_deadline=DEADLINE, now=NOW + 2)
    return fx, gate, memory, grant, (summary, level2, level3), unrelated


def test_source_version_change_invalidates_a_three_level_derivation_chain():
    fx, _gate, memory, _grant, chain, unrelated = _chain()
    changed_field = fx.granted_fields()[-1]
    touched = memory.on_source_version(f"{SUBJECT_A}.{changed_field}", 2)
    assert set(chain) <= set(touched) and unrelated not in touched
    assert not any(memory.is_available(a, NOW + 3) for a in chain)
    assert memory.is_available(unrelated, NOW + 3)
    assert memory.describe(chain[2])["kind"] == ArtifactKind.HANDOFF.value


def test_direct_invalidation_traverses_children_not_siblings():
    _fx, _gate, memory, _grant, (summary, level2, level3), unrelated = _chain()
    sibling = memory.derive([summary], kind=ArtifactKind.VECTOR_ENTRY, content="vec",
                            retention_deadline=DEADLINE, now=NOW + 2, holder=AGENT)
    assert memory.invalidate(level2, reason="found wrong") == (level2, level3)
    assert memory.is_available(summary, NOW + 3) and memory.is_available(sibling, NOW + 3)
    assert not memory.is_available(level3, NOW + 3) and memory.is_available(unrelated, NOW + 3)


def test_grant_revocation_and_consent_withdrawal_invalidate_through_the_real_gate():
    fx, gate, memory, grant, chain, unrelated = _chain()
    memory.revoke_grant(grant.grant_id, by="data-owner", reason="test")
    assert not any(memory.is_available(a, NOW + 3) for a in chain)
    assert memory.is_available(unrelated, NOW + 3)
    memory.withdraw_consent(SUBJECT_A, fx.purpose, recorded_by="subject")
    assert not memory.is_available(unrelated, NOW + 3)
    assert not gate.consent.permits(SUBJECT_A, fx.purpose)
