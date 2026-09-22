"""The same request boundary applies to arbitrary tool names and resources."""
import pytest

from trustkernel.guard import ActionClass, Guard
from trustkernel.kernel.exact_action import ExecutionDenied
from trustkernel.runtime import GuardedDispatcher


@pytest.mark.parametrize("operation,target", [("deploy", "service-7"), ("refund", "order-8"), ("publish", "article-9")])
def test_generic_dispatch_binds_identity_and_exact_action(operation, target):
    guard = Guard()
    effects = []

    @guard.tool(operation, resource="target", action_class=ActionClass.HIGH_IMPACT, approver_role="reviewer")
    def apply(target, value="reviewed"):
        effects.append((target, value))
        return {"target": target, "value": value}

    owner = guard.root("owner", tools={operation}, resources={target})
    worker = guard.spawn(owner, "worker", tools=set())
    bindings = {"transport-owner": owner, "transport-worker": worker}
    dispatcher = GuardedDispatcher(guard, bindings)
    bindings["transport-worker"] = owner  # the dispatcher must have taken a snapshot
    request = {"tool": operation, "arguments": {"target": target}}
    approval = guard.approve(dispatcher.propose("transport-owner", request), approver="human", role="reviewer")
    with pytest.raises(ExecutionDenied):
        dispatcher.dispatch("transport-worker", request, approval=approval)
    with pytest.raises(ExecutionDenied):
        dispatcher.dispatch("transport-owner", {"tool": operation, "arguments": {"target": target, "value": "swapped"}},
                            approval=approval)
    receipt = dispatcher.dispatch("transport-owner", request, approval=approval)
    assert receipt["value"] == "reviewed"
    assert dispatcher.dispatch("transport-owner", request, approval=approval) == receipt
    assert effects == [(target, "reviewed")]


@pytest.mark.parametrize("injection", [{"caller": "owner"}, {"approval": "ADMIN"}, {"context": {}}, {"role": "admin"}])
def test_request_cannot_choose_identity_or_approval(injection):
    guard = Guard()
    dispatcher = GuardedDispatcher(guard, {"worker": guard.root("worker", tools=set())})
    with pytest.raises(ExecutionDenied) as exc:
        dispatcher.dispatch("worker", {"tool": "anything", "arguments": {}, **injection})
    assert exc.value.code == "REQUEST_INVALID"


def test_unbound_caller_and_unknown_tool_fail_closed():
    guard = Guard()
    dispatcher = GuardedDispatcher(guard, {"known": guard.root("known", tools={"*"})})
    for caller, expected in [("unknown", "CALLER_UNKNOWN"), ("known", "TOOL_UNKNOWN")]:
        with pytest.raises(ExecutionDenied) as exc:
            dispatcher.dispatch(caller, {"tool": "not_registered", "arguments": {}})
        assert exc.value.code == expected


def test_handoff_copies_content_and_carries_labels():
    from trustkernel.kernel.disclosure import DisclosureDenied
    from trustkernel.world import WorldSpec
    guard = Guard.from_pack(WorldSpec.load("devtools").pack_path)
    sender, receiver = guard.root("sender", tools=set()), guard.root("receiver", tools=set())
    dispatcher = GuardedDispatcher(guard, {"sender": sender, "receiver": receiver})
    guard.observe(sender, {"secret-credentials"})
    original = {"summary": ["SYNTHETIC"]}
    received = dispatcher.handoff("sender", "receiver", original)
    original["summary"].clear()
    assert received == {"summary": ["SYNTHETIC"]}
    with pytest.raises(DisclosureDenied):
        dispatcher.release("receiver", str(received), recipient="slack_general", purpose="incident-triage")


def test_argument_names_do_not_collide_with_proposal_metadata():
    guard = Guard()

    @guard.tool(resource="resource", action_class=ActionClass.HIGH_IMPACT, approver_role="reviewer")
    def change(resource, tool="item"):
        return {"resource": resource, "tool": tool}

    dispatcher = GuardedDispatcher(guard, {"caller": guard.root("owner", tools={"change"}, resources={"r1"})})
    request = {"tool": "change", "arguments": {"resource": "r1"}}
    approval = guard.approve(dispatcher.propose("caller", request), approver="human", role="reviewer")
    assert dispatcher.dispatch("caller", request, approval=approval) == {"resource": "r1", "tool": "item"}
