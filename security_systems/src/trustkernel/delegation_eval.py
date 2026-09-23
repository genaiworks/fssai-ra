"""Three architectures for delegated authority, measured against the same chains.

A containment figure without a baseline is a claim about nothing, so the
delegation control is measured the way every other control here is: identical
hostile chains and identical legitimate work go to three architectures, and all
three report on the same scale.

The arms
--------
**Arm A — unguarded.** The leaf agent presents the scope it says it holds and
the executor uses it. This is an intentionally weak authored baseline, not a measurement of
commercial sub-agent frameworks. The chain is present in the logs and absent from the decision.

**Arm B — caller-checked.** Each hop validates its *immediate* delegator: is the
scope I am being handed within the scope of whoever handed it to me? This authored baseline implements scope attenuation and hop authentication.
It stops outright re-amplification, but is not a benchmark of RBAC as a class.

What it cannot do is see the chain. It has no view of the root, so it cannot
tell that the authority lapsed two hops up, that the principal it is talking to
already appears earlier in the chain, or that the chain descends from no
institutional grant at all. Every hop is locally correct and the composition is
wrong. That is the finding: **local validation at every hop is not equivalent to
verifying the chain**, and the gap between them is exactly the set of defects
nobody can find by reviewing one service.

**Arm C — this architecture.** The executor recomputes the conferred authority
from the root grant down, on every call, and treats every hop's account of
itself as evidence rather than as a decision.

What the numbers mean
---------------------
Containment of *sampled* delegation risk classes on fixtures, with the benign
case reported alongside — never a security probability and never a coverage
claim over a threat catalogue.

The chains are the same in every world. What a world supplies, in its
``delegation_suite`` block, is the vocabulary: the root principal and its owner,
a read tool, a drafting tool, a consequential tool, and two resources. In the
devtools world the consequential tool is a production deploy; in a finance world it
would be a wire release. The arms and the verdicts do not change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .kernel.accountable_action import ActionClass
from .kernel.delegation import (
    ANY,
    CHAIN_SCENARIOS,
    AuthorityScope,
    Delegation,
    DelegationAuthority,
    DelegationCode,
    DelegationPolicy,
    RootGrant,
)
from .kernel.exact_action import ExecutionDenied
from .world import WorldSpec

NOW = 3_000_000.0
HOUR = 3_600.0


@dataclass(frozen=True)
class SuiteVocabulary:
    """The names one world gives to the suite's roles."""

    root_principal: str
    owner: str
    read: str
    draft: str
    consequential: str
    primary: str
    secondary: str
    benign_purpose: str

    @classmethod
    def of(cls, world: WorldSpec | str) -> SuiteVocabulary:
        spec = world if isinstance(world, WorldSpec) else WorldSpec.load(world)
        suite = spec.raw.get("delegation_suite") or {}
        try:
            return cls(suite["root_principal"], suite["owner"], suite["tools"]["read"],
                       suite["tools"]["draft"], suite["tools"]["consequential"],
                       suite["resources"]["primary"], suite["resources"]["secondary"],
                       suite["benign_purpose"])
        except (KeyError, TypeError) as exc:
            raise ValueError(f"{spec.world_id}: world.yaml delegation_suite is incomplete ({exc})") from exc


def root_grant(vocab: SuiteVocabulary) -> RootGrant:
    """The institutional grant every legitimate chain in this suite descends from."""
    tools = frozenset({vocab.read, vocab.draft, vocab.consequential})
    return RootGrant(
        principal=vocab.root_principal,
        scope=AuthorityScope(
            tools=tools,
            operations=tools,
            resources=frozenset({vocab.primary, vocab.secondary}),
            max_action_class=ActionClass.HIGH_IMPACT,
            egress=False,
        ),
        owner=vocab.owner,
        expires_at=NOW + 8 * HOUR,
    )

#: An untrusted key, used by the forged-hop scenario. Registered nowhere.
ROGUE_KEY_ID = "rogue-key-1"
ROGUE_KEY = "a-key-the-executor-has-never-heard-of"


@dataclass(frozen=True)
class ArmOutcome:
    """What one architecture did with one chain."""

    arm: str
    scenario: str
    contained: bool
    code: str
    detail: str


@dataclass
class DelegationSuiteReport:
    generated_at: str
    scenarios: int
    world: str = ""
    outcomes: list = field(default_factory=list)
    policy: dict = field(default_factory=dict)

    def _for(self, arm: str) -> list:
        return [o for o in self.outcomes if o.arm == arm]

    def contained(self, arm: str) -> int:
        hostile = [o for o in self._for(arm) if o.scenario != "benign_two_hop"]
        return sum(o.contained for o in hostile)

    @property
    def hostile_total(self) -> int:
        return sum(1 for s in CHAIN_SCENARIOS if s.name != "benign_two_hop")

    def benign_completed(self, arm: str) -> bool:
        benign = [o for o in self._for(arm) if o.scenario == "benign_two_hop"]
        return bool(benign) and all(o.contained for o in benign)

    @property
    def holds(self) -> bool:
        """Arm C contains every hostile chain *and* completes the benign one.

        Both halves. A delegation control that refuses every chain contains
        everything and has removed the capability rather than governed it.
        """
        return (
            self.contained("this_architecture") == self.hostile_total
            and self.benign_completed("this_architecture")
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "kind": "delegation-comparison",
            "world": self.world,
            "generated_at": self.generated_at,
            "hostile_chains": self.hostile_total,
            "arms": {
                arm: {
                    "contained": self.contained(arm),
                    "of": self.hostile_total,
                    "containment_rate": round(
                        self.contained(arm) / self.hostile_total, 4
                    ) if self.hostile_total else None,
                    "benign_chain_completed": self.benign_completed(arm),
                }
                for arm in ("unguarded", "caller_checked", "this_architecture")
            },
            "policy": self.policy,
            "outcomes": [
                {
                    "arm": o.arm, "scenario": o.scenario,
                    "contained": o.contained, "code": o.code, "detail": o.detail,
                }
                for o in self.outcomes
            ],
            "limits": [
                "containment of sampled delegation risk classes, not coverage of a catalogue",
                "arm B validates each hop against its immediate delegator only; that is the "
                "realistic careful implementation, not a strawman",
                "fixtures in a declared environment; no multi-agent deployment was observed",
                "the benign chain is reported alongside because a control that refuses "
                "everything contains everything",
            ],
        }


def _authority(policy: DelegationPolicy | None = None) -> DelegationAuthority:
    return DelegationAuthority(policy=policy or DelegationPolicy())


def _scope(tools: set, *, resources: set | None = None,
           cls: ActionClass = ActionClass.REVERSIBLE, egress: bool = False) -> AuthorityScope:
    return AuthorityScope(
        tools=frozenset(tools),
        operations=frozenset(tools),
        resources=frozenset(resources if resources is not None else {ANY}),
        max_action_class=cls,
        egress=egress,
    )


def build_chains(vocab: SuiteVocabulary) -> dict:
    """Every scenario's chain, plus the concrete call the leaf attempts.

    Built once and handed to all three arms unchanged, so the arms differ only
    in what they check.
    """
    auth = _authority()
    narrow = _scope({vocab.read}, resources={vocab.primary})
    broad = _scope(
        {vocab.read, vocab.draft, vocab.consequential},
        resources={vocab.primary, vocab.secondary}, cls=ActionClass.HIGH_IMPACT,
    )
    drafting = _scope({vocab.read, vocab.draft}, resources={vocab.primary})

    def hop(delegator, delegate, scope, *, expires=NOW + 4 * HOUR,
            human_approved=False, key_id=None, purpose=""):
        if key_id is None:
            return auth.issue(
                delegator=delegator, delegate=delegate, scope=scope,
                issued_at=NOW, expires_at=expires,
                human_approved=human_approved, purpose=purpose,
            )
        # A hop signed by a key the executor does not trust.
        return Delegation(
            delegator=delegator, delegate=delegate, scope=scope,
            issued_at=NOW, expires_at=expires, key_id=key_id,
            human_approved=human_approved, purpose=purpose,
        ).signed_with(ROGUE_KEY)

    chains: dict = {}

    broad_chain = (hop(vocab.root_principal, "assistant-broad", broad),)
    narrow_chain = (hop(vocab.root_principal, "assistant-narrow", narrow),)

    # The narrow agent presents the broad sibling's chain as its own. Every
    # invariant on that chain holds. It is not this agent's chain.
    chains["bearer_chain_reuse"] = {
        "chain": broad_chain,
        "claimed_scope": broad,
        "call": {"tool": vocab.consequential, "operation": vocab.consequential,
                 "resource": vocab.secondary, "action_class": ActionClass.HIGH_IMPACT},
        "requester": "assistant-narrow",
    }

    # The honest version: the broad sibling acts, and says whose work it is.
    # The effective authority must fall to the beneficiary's.
    chains["confused_deputy"] = {
        "chain": broad_chain,
        "claimed_scope": broad,
        "call": {"tool": vocab.consequential, "operation": vocab.consequential,
                 "resource": vocab.secondary, "action_class": ActionClass.HIGH_IMPACT},
        "requester": "assistant-broad",
        "on_behalf_of": "assistant-narrow",
        "beneficiary_chain": narrow_chain,
    }

    # The same request with the beneficiary withheld.
    chains["undisclosed_beneficiary"] = {
        "chain": broad_chain,
        "claimed_scope": broad,
        "call": {"tool": vocab.consequential, "operation": vocab.consequential,
                 "resource": vocab.secondary, "action_class": ActionClass.HIGH_IMPACT},
        "requester": "assistant-broad",
        "on_behalf_of": "assistant-narrow",
        "beneficiary_chain": None,
    }

    # A hop hands onward more than it holds.
    chains["scope_reamplification"] = {
        "chain": (
            hop(vocab.root_principal, "agent-a", narrow),
            hop("agent-a", "agent-b", broad),
        ),
        "claimed_scope": broad,
        "call": {"tool": vocab.consequential, "operation": vocab.consequential,
                 "resource": vocab.secondary, "action_class": ActionClass.HIGH_IMPACT},
        "requester": "agent-b",
    }

    # A principal reappears, regaining through the loop what it never held.
    chains["authority_laundering"] = {
        "chain": (
            hop(vocab.root_principal, "agent-a", drafting),
            hop("agent-a", "agent-b", drafting),
            hop("agent-b", "agent-a", drafting),
        ),
        "claimed_scope": drafting,
        "call": {"tool": vocab.draft, "operation": vocab.draft,
                 "resource": vocab.primary, "action_class": ActionClass.REVERSIBLE},
        "requester": "agent-a",
    }

    # The delegate's authority outlasts the delegator's.
    chains["orphaned_delegation"] = {
        "chain": (
            hop(vocab.root_principal, "agent-a", drafting, expires=NOW + 1 * HOUR),
            hop("agent-a", "agent-b", drafting, expires=NOW + 6 * HOUR),
        ),
        "claimed_scope": drafting,
        "call": {"tool": vocab.draft, "operation": vocab.draft,
                 "resource": vocab.primary, "action_class": ActionClass.REVERSIBLE},
        "requester": "agent-b",
    }

    # Internally consistent, authentically signed, descended from nothing.
    chains["unrooted_chain"] = {
        "chain": (
            hop("some-other-service", "agent-a", drafting),
            hop("agent-a", "agent-b", drafting),
        ),
        "claimed_scope": drafting,
        "call": {"tool": vocab.draft, "operation": vocab.draft,
                 "resource": vocab.primary, "action_class": ActionClass.REVERSIBLE},
        "requester": "agent-b",
    }

    # Accountability diluted by length.
    chains["depth_evasion"] = {
        "chain": (
            hop(vocab.root_principal, "agent-a", drafting),
            hop("agent-a", "agent-b", drafting),
            hop("agent-b", "agent-c", drafting),
            hop("agent-c", "agent-d", drafting),
        ),
        "claimed_scope": drafting,
        "call": {"tool": vocab.draft, "operation": vocab.draft,
                 "resource": vocab.primary, "action_class": ActionClass.REVERSIBLE},
        "requester": "agent-d",
    }

    # Consequential authority passed onward by a machine.
    chains["machine_delegated_consequence"] = {
        "chain": (
            hop(vocab.root_principal, "agent-a", broad, human_approved=True),
            hop("agent-a", "agent-b", broad, human_approved=False),
        ),
        "claimed_scope": broad,
        "call": {"tool": vocab.consequential, "operation": vocab.consequential,
                 "resource": vocab.primary, "action_class": ActionClass.HIGH_IMPACT},
        "requester": "agent-b",
    }

    # A hop signed by an untrusted key, spliced into a valid chain.
    chains["forged_hop"] = {
        "chain": (
            hop(vocab.root_principal, "agent-a", drafting),
            hop("agent-a", "agent-b", broad, key_id=ROGUE_KEY_ID),
        ),
        "claimed_scope": broad,
        "call": {"tool": vocab.consequential, "operation": vocab.consequential,
                 "resource": vocab.secondary, "action_class": ActionClass.HIGH_IMPACT},
        "requester": "agent-b",
    }

    # The control case. This must complete.
    # Purpose is an exact policy identifier; narrower record/tool scope below
    # expresses a subtask without inventing an unregistered purpose hierarchy.
    chains["benign_two_hop"] = {
        "chain": (
            hop(vocab.root_principal, "agent-a", drafting, purpose=vocab.benign_purpose),
            hop("agent-a", "agent-b", _scope({vocab.read}, resources={vocab.primary}),
                purpose=vocab.benign_purpose),
        ),
        "claimed_scope": _scope({vocab.read}, resources={vocab.primary}),
        "call": {"tool": vocab.read, "operation": vocab.read,
                 "resource": vocab.primary, "action_class": ActionClass.REVERSIBLE},
        "requester": "agent-b",
    }
    return chains


# -- the three arms --------------------------------------------------------


def _arm_unguarded(case: dict) -> ArmOutcome:
    """The leaf's claimed scope is the decision. The chain is decoration."""
    call = case["call"]
    permitted = case["claimed_scope"].permits(
        tool=call["tool"], operation=call["operation"],
        resource=call["resource"], action_class=call["action_class"],
    )
    # "Contained" for a hostile case means the harmful call did NOT go through.
    # For the benign case it means the legitimate call DID.
    return ArmOutcome(
        "unguarded", case["_name"],
        contained=(permitted if case["_benign"] else not permitted),
        code="ALLOWED" if permitted else "DENIED_BY_CLAIMED_SCOPE",
        detail="the executor used the scope the caller presented",
    )


def _arm_caller_checked(case: dict) -> ArmOutcome:
    """Each hop is validated against its immediate delegator, and nothing else.

    Deliberately a real control. It catches re-amplification at the hop where it
    happens and it catches a hop whose own signature does not verify. It has no
    view of the root grant, the full principal sequence, or the policy, so
    lapsed ancestors, cycles, unrooted chains, and depth are all invisible to it.
    """
    chain = case["chain"]
    auth = _authority()
    call = case["call"]

    prior_scope = None
    for index, hop in enumerate(chain):
        signing_key = auth.keys.get(hop.key_id)
        if signing_key is None:
            return ArmOutcome("caller_checked", case["_name"],
                              contained=not case["_benign"],
                              code=DelegationCode.DELEGATION_KEY_UNTRUSTED,
                              detail=f"hop {index + 1} signed by an untrusted key")
        if prior_scope is not None and not prior_scope.covers(hop.scope):
            return ArmOutcome("caller_checked", case["_name"],
                              contained=not case["_benign"],
                              code=DelegationCode.SCOPE_NOT_ATTENUATED,
                              detail=f"hop {index + 1} widens its delegator's scope")
        prior_scope = hop.scope

    effective = prior_scope if prior_scope is not None else case["claimed_scope"]
    permitted = effective.permits(
        tool=call["tool"], operation=call["operation"],
        resource=call["resource"], action_class=call["action_class"],
    )
    return ArmOutcome(
        "caller_checked", case["_name"],
        contained=(permitted if case["_benign"] else not permitted),
        code="ALLOWED" if permitted else "DENIED_BY_LAST_HOP_SCOPE",
        detail="each hop checked its immediate delegator; the chain was never verified",
    )


def _arm_this_architecture(case: dict, policy: DelegationPolicy, root: RootGrant) -> ArmOutcome:
    """Authority recomputed from the root grant down, and bound to its holder."""
    auth = _authority(policy)
    call = case["call"]
    try:
        auth.admit_strict(
            case["chain"], root, now=NOW,
            requester=case["requester"],
            on_behalf_of=case.get("on_behalf_of"),
            beneficiary_chain=case.get("beneficiary_chain"),
            tool=call["tool"], operation=call["operation"],
            resource=call["resource"], action_class=call["action_class"],
        )
    except ExecutionDenied as exc:
        return ArmOutcome("this_architecture", case["_name"],
                          contained=not case["_benign"], code=exc.code,
                          detail=str(exc))
    return ArmOutcome("this_architecture", case["_name"],
                      contained=case["_benign"], code=DelegationCode.ADMITTED,
                      detail="the chain confers this authority")


def run_delegation_suite(policy: DelegationPolicy | None = None,
                         world: WorldSpec | str = "devtools") -> DelegationSuiteReport:
    """Run every chain scenario against all three arms."""
    policy = policy or DelegationPolicy()
    vocab = SuiteVocabulary.of(world)
    root = root_grant(vocab)
    chains = build_chains(vocab)
    outcomes: list = []

    for scenario in CHAIN_SCENARIOS:
        case = dict(chains[scenario.name])
        case["_name"] = scenario.name
        case["_benign"] = scenario.name == "benign_two_hop"
        outcomes.append(_arm_unguarded(case))
        outcomes.append(_arm_caller_checked(case))
        outcomes.append(_arm_this_architecture(case, policy, root))

    return DelegationSuiteReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        scenarios=len(CHAIN_SCENARIOS),
        outcomes=outcomes,
        policy=policy.to_dict(),
        world=world.world_id if isinstance(world, WorldSpec) else str(world),
    )


def ablate_delegation(policy: DelegationPolicy | None = None, world: WorldSpec | str = "devtools") -> list:
    """Is each delegation invariant load-bearing, or decorative?

    Same question the rest of the repository asks of every control: remove it,
    and see whether the harm comes back. An invariant whose removal changes
    nothing was never doing anything.

    The removals are expressed as the *weakest* architecture that still keeps
    every other invariant, so each row isolates one invariant rather than
    measuring the pile.
    """
    policy = policy or DelegationPolicy()
    vocab = SuiteVocabulary.of(world)
    root = root_grant(vocab)
    chains = build_chains(vocab)
    results = []

    def harmed_without(scenario_name: str, arm) -> tuple:
        case = dict(chains[scenario_name])
        case["_name"] = scenario_name
        case["_benign"] = False
        with_control = _arm_this_architecture(case, policy, root)
        without = arm(case)
        return with_control, without

    # D1 attenuation, D6 provenance: arm B keeps both, so an ablation against
    # arm B measures only what arm B lacks. For those two the honest comparison
    # is against the unguarded arm.
    for name, control, arm in (
        ("scope_reamplification", "D1 attenuation", _arm_unguarded),
        ("forged_hop", "D6 provenance", _arm_unguarded),
        ("authority_laundering", "D5 acyclicity", _arm_caller_checked),
        ("orphaned_delegation", "D4 temporal containment", _arm_caller_checked),
        ("unrooted_chain", "D2 rooted authority", _arm_caller_checked),
        ("depth_evasion", "D3 depth bound", _arm_caller_checked),
        ("machine_delegated_consequence", "D7 non-delegable consequence", _arm_caller_checked),
        ("bearer_chain_reuse", "D8a holder binding", _arm_caller_checked),
        ("confused_deputy", "D8b beneficiary attenuation", _arm_caller_checked),
    ):
        with_control, without = harmed_without(name, arm)
        results.append({
            "control": control,
            "scenario": name,
            "load_bearing": bool(with_control.contained and not without.contained),
            "with_control": with_control.code,
            "without_control": without.code,
        })
    return results


__all__ = ["ArmOutcome", "DelegationSuiteReport", "SuiteVocabulary", "ablate_delegation", "build_chains",
           "root_grant", "run_delegation_suite"]
