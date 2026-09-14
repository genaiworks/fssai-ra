"""Regression tests for two exploits found by adversarial review of v1.0.0.

Both are executed end to end against the real education world on synthetic data.
They are kept out of the counted falsifier/ablation suites on purpose: they guard
claims the paper makes in prose (Rule 1 key secrecy; action/read composition) and
must not shift the pinned figure counts.

E1  Rule 1 must not rest on a signing key an attacker can reconstruct from source.
    The approval key is generated per world and the executor holds only the public
    verification key. Reconstructing the key from the published key id, or from the
    old hard-coded fixture seed, must not forge an approval that executes.

E2  An approved action must not still execute after the read it relied on loses its
    authority (grant revoked, consent withdrawn, or grant expired). This is the
    action/disclosure composition rule; before the fix the execution path bound the
    proposal but never rechecked the context's live authority.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fssaira.custody_errors import DENIALS
from fssaira.education_world import EducationWorld
from fssaira.exact_action import (
    Approval,
    AsymmetricApprovalAuthority,
    _approval_signing_payload,
)

RESOURCE = "transcript:stu-b7c2:MATH101"


def _sign_with(seed: bytes, approval: Approval) -> Approval:
    key = Ed25519PrivateKey.from_private_bytes(seed)
    signed = replace(approval, signature=key.sign(_approval_signing_payload(approval).encode()).hex())
    return signed


def _forged_for(world: EducationWorld, proposal, seed: bytes) -> Approval:
    unsigned = Approval(
        approval_id="forged-1", proposal_digest=proposal.digest, approver="dr-lin",
        approver_role="university_registrar", audience="student-records-executor",
        expires_at=world.now + 600, key_id=world.approvals.key_id, signature="")
    return _sign_with(seed, unsigned)


# --- E1: key secrecy --------------------------------------------------------

def test_default_asymmetric_authority_key_is_not_derivable_from_key_id():
    """The private key must not be sha256(key_id): that value is published."""
    authority = AsymmetricApprovalAuthority(key_id="approval-ed25519-1")
    derivable = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"approval-ed25519-1").digest()
    ).public_key().public_bytes_raw()
    assert authority.public_key != derivable


def test_world_approval_keys_differ_between_instances():
    """Two worlds must not share a signing key; source knowledge is not key knowledge."""
    assert EducationWorld().approvals.public_key != EducationWorld().approvals.public_key


def test_approval_forged_from_old_fixture_seed_is_rejected():
    """The historical hard-coded seed no longer signs a usable approval."""
    world = EducationWorld()
    before = world.register.get(RESOURCE)
    proposal = world.propose(requester="rogue-agent", operation="correct_transcript_grade",
                             resource=RESOURCE, to_status="grade:A")
    forged = _forged_for(world, proposal, hashlib.sha256(b"approval-service").digest())
    with pytest.raises(DENIALS):
        world.execute(proposal, forged)
    assert world.register.get(RESOURCE) == before
    assert world.register.write_log == []


def test_approval_forged_from_key_id_seed_is_rejected():
    world = EducationWorld()
    before = world.register.get(RESOURCE)
    proposal = world.propose(requester="rogue-agent", operation="correct_transcript_grade",
                             resource=RESOURCE, to_status="grade:A")
    forged = _forged_for(world, proposal, hashlib.sha256(world.approvals.key_id.encode()).digest())
    with pytest.raises(DENIALS):
        world.execute(proposal, forged)
    assert world.register.get(RESOURCE) == before


def test_explicit_seed_still_reproducible_for_fixtures():
    seed = b"\x09" * 32
    a, b = AsymmetricApprovalAuthority("exec", seed=seed), AsymmetricApprovalAuthority("exec", seed=seed)
    assert a.public_key == b.public_key


# --- E2: action/read composition -------------------------------------------

def _legitimate_proposal(world: EducationWorld):
    resource = "transcript:stu-a1f3:MATH101"
    grant = world.grant(holder="support-agent", purpose="academic-support",
                        subjects=["stu-a1f3"], fields=["current_grades"])
    world.read(requester="support-agent", grant=grant, purpose="academic-support",
               subjects=["stu-a1f3"], fields=["current_grades"], session_id="s1")
    proposal = world.propose(requester="support-agent", operation="correct_transcript_grade",
                            resource=resource, to_status="grade:B")
    approval = world.review_and_approve(proposal, reviewer="dr-lin")
    return resource, grant, proposal, approval


def test_execute_denied_after_context_grant_revoked():
    world = EducationWorld()
    resource, grant, proposal, approval = _legitimate_proposal(world)
    before = world.register.get(resource)
    world.data_delegation.revoke(grant.grant_id, by="privacy-officer-ng", reason="composition test")
    with pytest.raises(DENIALS) as exc:
        world.execute(proposal, approval, context_grant=grant)
    assert exc.value.code == "CONTEXT_AUTHORITY_WITHDRAWN"
    assert world.register.get(resource) == before  # no write happened
    assert world.register.mutation_count == 0


def test_execute_denied_after_consent_withdrawn():
    world = EducationWorld()
    resource, grant, proposal, approval = _legitimate_proposal(world)
    world.gate.withdraw_consent("stu-a1f3", "academic-support", recorded_by="stu-a1f3")
    with pytest.raises(DENIALS) as exc:
        world.execute(proposal, approval, context_grant=grant)
    assert exc.value.code == "CONTEXT_AUTHORITY_WITHDRAWN"
    assert world.register.mutation_count == 0


def test_execute_allowed_when_context_authority_is_still_live():
    """The check denies withdrawn authority without breaking the legitimate path."""
    world = EducationWorld()
    resource, grant, proposal, approval = _legitimate_proposal(world)
    executed = world.execute(proposal, approval, context_grant=grant)
    assert executed["result"].status == "grade:B"
    assert world.register.mutation_count == 1
