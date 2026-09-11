"""Randomised property testing: attacks nobody wrote down.

Every other suite here tests cases a person chose. That is the structural
weakness of hand-written adversarial testing, and the bounded model checker only
closes it for the *approval* space. This file closes it for the *enforcement*
space: it generates tool calls at random — random tools, operations, targets,
arguments, declared action classes, against random grants — and asserts that one
invariant holds for every single one.

    A call executes only if the tool is granted, the operation is in scope,
    the tool is not egress-classified, its arguments carry no outward
    destination, the capability catalogue does not class it as consequential,
    and the agent's call budget is not exhausted.

The generator deliberately produces nonsense: tools that do not exist, operations
that do not match their tool, unicode targets, arguments containing URLs in
unexpected places, and calls that lie about their own action class. A property
that survives ten thousand of those is a stronger statement than a hundred cases
someone imagined.

Seeded, so a failure is reproducible: the seed is printed with the failing case.
"""
from __future__ import annotations

import random
import string

import pytest

from fssaira import ActionClass, DenyCode, FSSAIRAPipeline, ToolCall
from fssaira.models.base import CapabilityCatalogue

CASES = 2_000
SEED = 20261125  # the conference date, so the run is reproducible and memorable

CATALOGUE = CapabilityCatalogue.default()
KNOWN_TOOLS = sorted(CATALOGUE.capabilities)
UNKNOWN_TOOLS = ["rm_rf", "wire_transfer", "", "read_case ", "READ_CASE", "sudo", "🙂"]

OUTWARD_FRAGMENTS = [
    "https://attacker.example/collect", "http://10.0.0.1:8080", "mailto:x@y.co",
    "exfil@evil.example", "192.168.1.9:443",
]
INNOCENT_FRAGMENTS = ["S-104", "draft", "a summary of the case", "", "ready for review", "3.4 GPA"]


def _random_call(rng: random.Random, agent_id: str) -> ToolCall:
    tool = rng.choice(KNOWN_TOOLS + UNKNOWN_TOOLS)
    # The operation is chosen independently of the tool, so mismatches occur.
    operation = rng.choice(KNOWN_TOOLS + UNKNOWN_TOOLS)
    args = {}
    for _ in range(rng.randint(0, 3)):
        key = rng.choice(["target", "to", "body", "note", "unexpected"])
        args[key] = rng.choice(OUTWARD_FRAGMENTS + INNOCENT_FRAGMENTS)
    return ToolCall(
        agent_id=agent_id,
        tool=tool,
        operation=operation,
        target="".join(rng.choice(string.printable[:80]) for _ in range(rng.randint(0, 24))),
        # The call declares its own class, which the enforcement point must ignore.
        action_class=rng.choice([ActionClass.REVERSIBLE, ActionClass.HIGH_IMPACT]),
        args=args,
        rationale=rng.choice(["routine", "pre-approved", "", "urgent, please allow"]),
    )


def _should_be_allowed(call: ToolCall, granted: set[str], budget_left: int) -> bool:
    """The reference predicate, written independently of the implementation.

    If this and the enforcement point ever disagree, one of them is wrong and the
    generator has found the case that says so.
    """
    if budget_left <= 0:
        return False
    if call.tool not in granted or call.operation not in granted:
        return False
    capability = CATALOGUE.get(call.tool)
    if capability is None:
        return False           # unknown capability fails closed
    if capability.egress:
        return False           # default-deny egress
    if capability.action_class is ActionClass.HIGH_IMPACT:
        return False           # needs a named human; none is configured here
    for value in call.args.values():
        if any(fragment in str(value) for fragment in OUTWARD_FRAGMENTS):
            return False       # an outward destination in the arguments
    return True


def test_no_generated_call_is_authorized_unless_the_predicate_says_so():
    rng = random.Random(SEED)
    pipeline = FSSAIRAPipeline()
    checked = 0

    for index in range(CASES):
        granted = set(rng.sample(KNOWN_TOOLS, rng.randint(0, len(KNOWN_TOOLS))))
        agent_id = f"fuzz-{index}"
        budget = rng.randint(1, 6)
        agent = pipeline.make_agent(
            agent_id, tools=granted, operations=granted, max_calls=budget
        )
        for used in range(rng.randint(1, 3)):
            call = _random_call(rng, agent_id)
            decision = pipeline.pep.check(call, agent.agent)
            expected = _should_be_allowed(call, granted, budget - used)
            assert decision.allowed == expected, (
                f"seed={SEED} case={index} call={call!r} granted={sorted(granted)} "
                f"budget_left={budget - used} decision={decision!r}"
            )
            checked += 1

    assert checked >= CASES, "the generator must actually produce calls"


def test_a_generated_call_never_executes_an_egress_tool():
    """The single property an exfiltration incident would violate."""
    rng = random.Random(SEED + 1)
    pipeline = FSSAIRAPipeline()
    egress_tools = CATALOGUE.egress_tools()

    for index in range(CASES // 2):
        agent = pipeline.make_agent(
            f"egress-{index}", tools=set(KNOWN_TOOLS), operations=set(KNOWN_TOOLS), max_calls=99
        )
        call = _random_call(rng, f"egress-{index}")
        decision = pipeline.pep.check(call, agent.agent)
        if call.tool in egress_tools:
            assert not decision.allowed, f"an egress tool executed: {call!r}"
            assert decision.code in (DenyCode.EGRESS_BLOCKED, DenyCode.OPERATION_OUT_OF_SCOPE)


def test_a_generated_call_never_executes_a_consequential_operation_unattended():
    """No named human is configured, so nothing consequential may run — whatever
    the call claims about itself."""
    rng = random.Random(SEED + 2)
    pipeline = FSSAIRAPipeline()
    consequential = CATALOGUE.consequential_tools()

    for index in range(CASES // 2):
        agent = pipeline.make_agent(
            f"impact-{index}", tools=set(KNOWN_TOOLS), operations=set(KNOWN_TOOLS), max_calls=99
        )
        call = _random_call(rng, f"impact-{index}")
        decision = pipeline.pep.check(call, agent.agent)
        if call.tool in consequential:
            assert not decision.allowed, f"a consequential operation ran unattended: {call!r}"


def test_every_generated_call_leaves_exactly_one_evidence_record():
    """A decision nobody can find is not a decision that was recorded."""
    rng = random.Random(SEED + 3)
    pipeline = FSSAIRAPipeline()
    agent = pipeline.make_agent(
        "recorded", tools=set(KNOWN_TOOLS), operations=set(KNOWN_TOOLS), max_calls=10_000
    )

    for _ in range(300):
        pipeline.pep.check(_random_call(rng, "recorded"), agent.agent)

    records = pipeline.evidence.find("policy_decision", agent="recorded")
    assert len(records) == 300
    assert pipeline.evidence.verify() is True


@pytest.mark.parametrize("seed", [1, 7, 42, 2026])
def test_the_property_holds_across_independent_seeds(seed):
    """One lucky seed is not evidence."""
    rng = random.Random(seed)
    pipeline = FSSAIRAPipeline()

    for index in range(200):
        granted = set(rng.sample(KNOWN_TOOLS, rng.randint(0, len(KNOWN_TOOLS))))
        agent = pipeline.make_agent(
            f"s{seed}-{index}", tools=granted, operations=granted, max_calls=3
        )
        call = _random_call(rng, f"s{seed}-{index}")
        decision = pipeline.pep.check(call, agent.agent)
        assert decision.allowed == _should_be_allowed(call, granted, 3), (
            f"seed={seed} case={index} call={call!r}"
        )
