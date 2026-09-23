"""Generic tool contracts must bind effective arguments and stable implementations."""
import pytest

from trustkernel.guard import ActionClass, Guard
from trustkernel.kernel.exact_action import ExecutionDenied


def test_default_target_is_checked_before_callback():
    guard = Guard()
    calls = []

    @guard.tool(resource="target")
    def read(target="protected"):
        calls.append(target)
        return target

    ctx = guard.root("worker", tools={"read"}, resources={"target"})
    with pytest.raises(ExecutionDenied):
        read(ctx)
    assert calls == []


def test_approval_binds_effective_defaults_and_returns_unpoisoned_receipt():
    guard = Guard()
    calls = []

    @guard.tool(resource="target", action_class=ActionClass.HIGH_IMPACT, approver_role="reviewer")
    def change(target="item", value=2):
        calls.append((target, value))
        return {"values": [value]}

    ctx = guard.root("worker", tools={"change"}, resources={"item"})
    proposal = guard.propose(ctx, "change", resource="item")
    approval = guard.approve(proposal, approver="human", role="reviewer")
    receipt = change(ctx, target="item", value=2, approval=approval)
    receipt["values"].append(999)
    assert change(ctx, approval=approval) == {"values": [2]}
    assert calls == [("item", 2)]


def test_duplicate_tool_names_cannot_change_approved_behavior():
    guard = Guard()
    guard.tool("operation")(lambda value: value)
    with pytest.raises(ValueError, match="registered"):
        guard.tool("operation")(lambda value: "replacement")


def test_unknown_resource_parameter_is_configuration_error():
    with pytest.raises(ValueError, match="resource"):
        Guard().tool(resource="misspelled")(lambda target: target)


def test_async_tool_is_rejected_by_synchronous_guard():
    async def async_tool(value):
        return value
    with pytest.raises(TypeError, match="synchronous"):
        Guard().tool()(async_tool)


def test_invalid_arguments_do_not_consume_approval():
    guard = Guard()
    calls = []

    @guard.tool(action_class=ActionClass.HIGH_IMPACT, approver_role="reviewer")
    def change(value):
        calls.append(value)
        return value

    ctx = guard.root("worker", tools={"change"})
    approval = guard.approve(guard.propose(ctx, "change", value=2), approver="human", role="reviewer")
    with pytest.raises(TypeError):
        change(ctx, approval=approval, value=2, typo=3)
    assert change(ctx, approval=approval, value=2) == 2
    assert calls == [2]
