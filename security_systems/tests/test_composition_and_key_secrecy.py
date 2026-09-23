"""Two exploits found by adversarial review of the reference implementation, regression-tested on every world.

E1  Rule 1 must not rest on a signing key an attacker can reconstruct from source.
    The approval key is generated per world and the executor holds only the public
    verification key. Reconstructing it from the published key id, or from a
    hard-coded seed, must not forge an approval that executes.

E2  An approved action must not still execute after the read it relied on loses its
    authority (grant revoked, consent withdrawn, or grant expired). This is the
    action/disclosure composition rule: exact-proposal binding stops substitution of
    *what* is done, not the lapse of *why* it was allowed.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from trustkernel.kernel.custody_errors import DENIALS
from trustkernel.kernel.exact_action import Approval, AsymmetricApprovalAuthority, _approval_signing_payload
from trustkernel.world import ScenarioWorld, available_worlds

WORLDS = available_worlds()


def _forged(world: ScenarioWorld, proposal, seed: bytes) -> Approval:
    approver = world.spec.fixture("approver")
    unsigned = Approval(approval_id="forged-1", proposal_digest=proposal.digest, approver=approver,
                        approver_role=world.spec.principals[approver], audience=world.audience,
                        expires_at=world.now + 600, key_id=world.approvals.key_id, signature="")
    key = Ed25519PrivateKey.from_private_bytes(seed)
    return replace(unsigned, signature=key.sign(_approval_signing_payload(unsigned).encode()).hex())


def _victim_proposal(world: ScenarioWorld):
    victim = world.spec.fixture("action", "victim")
    return victim["resource"], world.propose(requester=world.spec.fixture("rogue"),
                                             operation=world.spec.fixture("action", "operation"),
                                             resource=victim["resource"], to_status=victim["to"])


# --- E1: key secrecy --------------------------------------------------------

def test_default_asymmetric_authority_key_is_not_derivable_from_key_id():
    authority = AsymmetricApprovalAuthority(key_id="approval-ed25519-1")
    derivable = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"approval-ed25519-1").digest()).public_key().public_bytes_raw()
    assert authority.public_key != derivable


@pytest.mark.parametrize("world", WORLDS)
def test_world_approval_keys_differ_between_instances(world):
    assert ScenarioWorld(world).approvals.public_key != ScenarioWorld(world).approvals.public_key


@pytest.mark.parametrize("world", WORLDS)
@pytest.mark.parametrize("seed_source", ["key_id", "well_known_seed"])
def test_approval_forged_from_a_guessable_seed_is_rejected(world, seed_source):
    w = ScenarioWorld(world)
    resource, proposal = _victim_proposal(w)
    before = w.register.get(resource)
    seed = hashlib.sha256((w.approvals.key_id if seed_source == "key_id" else "approval-service").encode()).digest()
    with pytest.raises(DENIALS):
        w.execute(proposal, _forged(w, proposal, seed))
    assert w.register.get(resource) == before and w.register.write_log == []


def test_explicit_seed_still_reproducible_for_fixtures():
    seed = b"\x09" * 32
    assert AsymmetricApprovalAuthority("exec", seed=seed).public_key == \
        AsymmetricApprovalAuthority("exec", seed=seed).public_key


# --- E2: action/read composition -------------------------------------------

def _approved_over_a_read(world: ScenarioWorld):
    fx = world.spec.fixture
    field = world.spec.field("routine_2")
    grant = world.grant(holder=fx("agent"), purpose=fx("purpose"), subjects=[fx("subject")], fields=[field])
    world.read(requester=fx("agent"), grant=grant, purpose=fx("purpose"), subjects=[fx("subject")],
               fields=[field], session_id="s1")
    own = fx("action", "own")
    proposal = world.propose(requester=fx("agent"), operation=fx("action", "operation"),
                             resource=own["resource"], to_status=own["to"])
    return grant, proposal, world.review_and_approve(proposal, reviewer=fx("approver"))


@pytest.mark.parametrize("world", WORLDS)
@pytest.mark.parametrize("lapse", ["revoked", "consent_withdrawn", "expired"])
def test_execute_denied_after_the_read_authority_lapses(world, lapse):
    w = ScenarioWorld(world)
    fx = w.spec.fixture
    grant, proposal, approval = _approved_over_a_read(w)
    if lapse == "revoked":
        w.data_delegation.revoke(grant.grant_id, by=fx("data_officer"), reason="composition test")
    elif lapse == "consent_withdrawn":
        w.gate.withdraw_consent(fx("subject"), fx("purpose"), recorded_by=fx("subject"))
    else:
        w.tick(3601)
        approval = w.approvals.approve(proposal, approver=approval.approver, approver_role=approval.approver_role,
                                       now=w.now, ttl_seconds=900)
    with pytest.raises(DENIALS) as refused:
        w.execute(proposal, approval, context_grant=grant)
    assert refused.value.code == "CONTEXT_AUTHORITY_WITHDRAWN"
    assert w.register.mutation_count == 0


@pytest.mark.parametrize("world", WORLDS)
def test_execute_allowed_while_the_read_authority_is_live(world):
    w = ScenarioWorld(world)
    grant, proposal, approval = _approved_over_a_read(w)
    executed = w.execute(proposal, approval, context_grant=grant)
    assert executed["result"].status == w.spec.fixture("action", "own", "to")
    assert w.register.mutation_count == 1
