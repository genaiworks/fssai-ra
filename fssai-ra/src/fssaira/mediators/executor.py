"""Rule 1 mediator: the executor.

*A model may propose an action; it cannot manufacture the authority to execute it.*

This module is the kernel-facing name for the single executor implementation,
not a second one:

* :class:`fssaira.exact_action.AccountableExecutor` (in-memory teaching profile)
* :class:`fssaira.atomic_execution.AtomicExecutor` (transactional profile; the
  same ``validate_authorization`` rules)
* :class:`fssaira.accountable_action.PolicyEnforcementPoint` (model tool calls;
  the action class comes from the capability catalogue, not the caller)

The executor re-derives every authority question: policy, identity, version,
approval signature, exact proposal digest and replay. No decision consumes a
model's rationale. :class:`ActionProposal` and :class:`Approval` have no field
for one, and ``ToolCall.rationale`` is recorded for audit only. A reassuring,
fabricated or missing rationale therefore produces the identical decision, which
``tests/mediators/test_mediator_executor.py`` checks, with a positive control
showing the check can detect a rationale-dependent decider.

Must NOT: trust a reused approval, a changed proposal, or a model-supplied
action class.
"""
from __future__ import annotations

from fssaira.accountable_action import ActionClass, Decision, PolicyEnforcementPoint, ToolCall
from fssaira.atomic_execution import AtomicExecutor
from fssaira.exact_action import (
    AccountableExecutor,
    ActionProposal,
    Approval,
    ApprovalAuthority,
    AsymmetricApprovalAuthority,
    ExecutionDenied,
    ExecutionResult,
    ExecutionUncertain,
)

#: Parameter or field names that would carry model reasoning into a decision.
REASONING_NAMES: frozenset[str] = frozenset({
    "rationale", "reasoning", "reason", "explanation", "claim", "claims",
    "justification", "thought", "chain_of_thought", "cot",
})

__all__ = [
    "REASONING_NAMES",
    "AccountableExecutor",
    "ActionClass",
    "ActionProposal",
    "Approval",
    "ApprovalAuthority",
    "AsymmetricApprovalAuthority",
    "AtomicExecutor",
    "Decision",
    "ExecutionDenied",
    "ExecutionResult",
    "ExecutionUncertain",
    "PolicyEnforcementPoint",
    "ToolCall",
]
