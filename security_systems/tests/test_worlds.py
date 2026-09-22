"""Every shipped world holds under the same attacks, and every control still does work there.

These tests are parametrised over :func:`trustkernel.world.available_worlds`, so a new
world dropped into ``worlds/`` is attacked by the full suite with no test written for
it. That is the portability claim, enforced.
"""
import pytest

from trustkernel.delegation_eval import ablate_delegation, run_delegation_suite
from trustkernel.falsification import FALSIFIERS, run_ablation, run_falsifiers
from trustkernel.kernel.pack_floor import check_pack, read_pack
from trustkernel.redteam import GrammarAttacker, run_redteam
from trustkernel.world import ALL_CONTROLS, ScenarioWorld, WorldSpec, WorldSpecError, available_worlds

WORLDS = available_worlds()

#: Ablation rows where removing one control changes nothing because another control
#: independently stops the attack. They are findings, not failures; the list is pinned
#: so a new one appearing (or one disappearing) is noticed.
DEFENCE_IN_DEPTH = {("F11", "residency"), ("F11", "model_attestation"),
                    ("F13", "proposal_digest_binding"), ("F13", "approval_single_use")}


def test_both_audiences_ship():
    assert {"devtools", "education"} <= set(WORLDS)


@pytest.mark.parametrize("world", WORLDS)
def test_every_pack_is_at_or_above_the_kernel_floor(world):
    assert check_pack(read_pack(WorldSpec.load(world).pack_path)) == []


@pytest.mark.parametrize("world", WORLDS)
def test_every_falsifier_holds(world):
    results = run_falsifiers(world=world)
    assert len(results) == len(FALSIFIERS) == 25
    assert [r.id for r in results if not r.held] == []


@pytest.mark.slow
@pytest.mark.parametrize("world", WORLDS)
def test_controls_are_load_bearing_and_defence_in_depth_is_stable(world):
    rows = run_ablation(world=world)
    assert all(r.enabled == 0 and r.restored == 0 for r in rows)
    not_load_bearing = {(r.falsifier, r.control) for r in rows if not r.load_bearing}
    assert not_load_bearing == DEFENCE_IN_DEPTH
    # Removing both redundant controls together does let the attack through.
    joint = {(r.falsifier, r.control): r for r in rows if " + " in r.control}
    assert all(r.load_bearing for r in joint.values()) and len(joint) == 2


@pytest.mark.parametrize("world", WORLDS)
def test_whole_chain_verification_contains_every_hostile_chain(world):
    arms = run_delegation_suite(world=world).to_dict()["arms"]
    assert arms["unguarded"]["contained"] == 0
    assert arms["caller_checked"]["contained"] == 2
    assert arms["this_architecture"]["contained"] == arms["this_architecture"]["of"] == 10
    assert all(arm["benign_chain_completed"] for arm in arms.values())
    assert all(row["load_bearing"] for row in ablate_delegation(world=world))


@pytest.mark.slow
@pytest.mark.parametrize("world", WORLDS)
def test_red_team_finds_nothing_until_a_mediator_is_removed(world):
    assert run_redteam(GrammarAttacker(world, seed=1125), attempts=150, seed=7).violations == 0
    weakened = run_redteam(GrammarAttacker(world, seed=1125), attempts=150, seed=7,
                           remove=["execution_mediator"])
    assert weakened.violations > 0, "an attacker that never wins is indistinguishable from one that cannot run"


def test_worlds_do_not_share_key_material():
    devtools, education = ScenarioWorld("devtools"), ScenarioWorld("education")
    assert devtools.notary.public_keys != education.notary.public_keys
    assert devtools.grants.trusted_keys != education.grants.trusted_keys


def test_unknown_controls_and_worlds_are_refused():
    with pytest.raises(ValueError):
        ScenarioWorld("devtools", [*ALL_CONTROLS, "trust_me"])
    with pytest.raises(WorldSpecError):
        WorldSpec.load("no-such-world")


def test_a_world_can_be_loaded_from_a_path(tmp_path):
    spec = WorldSpec.load(WorldSpec.load("devtools").directory / "world.yaml")
    assert spec.world_id == "devtools" and spec.pack_path.is_file()
