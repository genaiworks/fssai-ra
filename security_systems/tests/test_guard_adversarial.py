"""Regressions at the public integration boundary, judged by side effects."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from trustkernel.guard import ActionClass, Guard
from trustkernel.kernel.exact_action import ExecutionDenied
from trustkernel.world import WorldSpec


def setup_action():
    guard = Guard(clock=lambda: 1000)
    calls = []

    @guard.tool(resource="service", action_class=ActionClass.HIGH_IMPACT, approver_role="human")
    def deploy(service, payload):
        calls.append(payload)
        return "receipt"

    ctx = guard.root("agent", tools={"deploy"}, resources={"svc"})
    proposal = guard.propose(ctx, "deploy", resource="svc", service="svc", payload=[1])
    approval = guard.approve(proposal, approver="reviewer", role="human")
    return guard, ctx, deploy, approval, calls


def test_cached_result_still_requires_authentic_approval():
    _, ctx, deploy, approval, calls = setup_action()
    assert deploy(ctx, service="svc", payload=[1], approval=approval) == "receipt"
    with pytest.raises(ExecutionDenied, match="authenticated"):
        deploy(ctx, service="svc", payload=[1], approval=replace(approval, signature="00" * 64))
    assert calls == [[1]]


@pytest.mark.parametrize("payload", [(1,), {1: "value"}, float("nan"), object()])
def test_approval_arguments_reject_non_json_types(payload):
    guard, ctx, _, _, calls = setup_action()
    with pytest.raises((TypeError, ValueError)):
        guard.propose(ctx, "deploy", resource="svc", service="svc", payload=payload)
    assert calls == []


def test_tuple_cannot_reuse_list_approval():
    _, ctx, deploy, approval, calls = setup_action()
    with pytest.raises((TypeError, ValueError)):
        deploy(ctx, service="svc", payload=(1,), approval=approval)
    assert calls == []


def test_high_impact_tool_requires_an_approver_role():
    with pytest.raises(ValueError, match="approver_role"):
        Guard().tool(action_class=ActionClass.HIGH_IMPACT)(lambda: None)


def test_replacing_session_cannot_erase_secret_label():
    guard = Guard.from_pack(WorldSpec.load("devtools").pack_path)
    ctx = guard.root("reader", tools=set())
    guard.observe(ctx, {"secret-credentials"})
    with pytest.raises(ExecutionDenied):
        guard.release(replace(ctx, session="fresh"), "secret", recipient="slack_general", purpose="incident-triage")


def test_forged_root_cannot_widen_registered_context():
    guard = Guard()
    ctx = guard.root("reader", tools={"read"})
    forged = replace(ctx, root=replace(ctx.root, scope=guard.scope({"delete"})))
    with pytest.raises(ExecutionDenied):
        guard.authorize(forged, "delete")


def test_guard_instances_do_not_share_delegation_signing_keys():
    assert Guard().delegation.keys != Guard().delegation.keys


def test_concurrent_replays_run_one_callback():
    _, ctx, deploy, approval, calls = setup_action()
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda _: deploy(ctx, service="svc", payload=[1], approval=approval), range(32)))
    assert results == ["receipt"] * 32
    assert calls == [[1]]


def test_forged_parent_cannot_mint_a_registered_child():
    guard = Guard()
    ctx = guard.root("reader", tools={"read"})
    forged = replace(ctx, root=replace(ctx.root, scope=guard.scope({"delete"})))
    with pytest.raises(ExecutionDenied):
        guard.spawn(forged, "child", tools={"delete"})


def test_read_labels_apply_before_callback_even_when_it_raises():
    guard = Guard.from_pack(WorldSpec.load("devtools").pack_path)
    ctx = guard.root("reader", tools={"read"})

    @guard.tool(reads=iter(["secret-credentials"]))
    def read():
        assert guard.label(ctx) == frozenset({"secret-credentials"})
        raise RuntimeError("failed after reading")

    with pytest.raises(RuntimeError):
        read(ctx)
    assert guard.label(ctx) == frozenset({"secret-credentials"})


def test_expired_approval_cannot_retrieve_cached_result():
    guard, ctx, deploy, approval, calls = setup_action()
    deploy(ctx, service="svc", payload=[1], approval=approval)
    guard.clock = lambda: approval.expires_at
    with pytest.raises(ExecutionDenied) as refused:
        deploy(ctx, service="svc", payload=[1], approval=approval)
    assert refused.value.code == "APPROVAL_EXPIRED"
    assert calls == [[1]]


def test_callback_failure_does_not_automatically_repeat_side_effect():
    guard = Guard()
    calls = []

    @guard.tool(action_class=ActionClass.HIGH_IMPACT, approver_role="human")
    def failing():
        calls.append("effect")
        raise RuntimeError("receipt lost")

    ctx = guard.root("agent", tools={"failing"})
    approval = guard.approve(guard.propose(ctx, "failing"), approver="reviewer", role="human")
    with pytest.raises(RuntimeError):
        failing(ctx, approval=approval)
    with pytest.raises(ExecutionDenied):
        failing(ctx, approval=approval)
    assert calls == ["effect"]
