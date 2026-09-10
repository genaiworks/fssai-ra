"""Accountable-action domain: the policy enforcement point (PEP), action
classes, human approval, and evidence logging.

The central fail-secure rule: a consequential (high-impact) action is only
authorized when an independent execution service verifies the *actual*
operation and current policy - never the model's explanation of what it is
doing. If required authorization is missing or uncertain, the action is denied
(fail-secure), and a defined manual path preserves service.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .evidence import EvidenceLedger
from .metrics import Metrics


class ActionClass(Enum):
    REVERSIBLE = "reversible"
    HIGH_IMPACT = "high_impact"


@dataclass(frozen=True)
class Tool:
    name: str
    egress: bool = False  # declares whether the tool can send data outward


@dataclass
class ToolCall:
    agent_id: str
    tool: str
    operation: str          # the real operation, checked independently of rationale
    target: str
    action_class: ActionClass
    args: dict = field(default_factory=dict)
    rationale: str = ""     # the model's explanation - recorded, never trusted for the decision
    evidence_refs: list = field(default_factory=list)


@dataclass
class Decision:
    allowed: bool
    reason: str
    approver: str | None = None


# A human approver returns (approved, approver_name). None means "no approver available".
HumanApprover = Callable[[ToolCall], "tuple[bool, str] | None"]


class PolicyEnforcementPoint:
    def __init__(
        self,
        evidence: EvidenceLedger,
        append_token: str,
        metrics: Metrics,
        *,
        allow_egress: bool = False,
        approver: HumanApprover | None = None,
        require_human_for_high_impact: bool = True,
    ) -> None:
        self._evidence = evidence
        self._token = append_token
        self._m = metrics
        self._allow_egress = allow_egress
        self._approver = approver
        self._require_human = require_human_for_high_impact

    def check(self, call: ToolCall, agent) -> Decision:
        decision = self._evaluate(call, agent)
        # Evidence is written on a separate path: the PEP holds the token, the agent never does.
        self._evidence.append(
            "policy_decision",
            {
                "agent": call.agent_id,
                "tool": call.tool,
                "operation": call.operation,
                "target": call.target,
                "class": call.action_class.value,
                "model_rationale": call.rationale,  # recorded for audit, not used to decide
                "allowed": decision.allowed,
                "reason": decision.reason,
                "approver": decision.approver,
            },
            token=self._token,
        )
        if decision.allowed:
            self._m.tool_calls_allowed += 1
        else:
            self._m.tool_calls_denied += 1
        return decision

    def _evaluate(self, call: ToolCall, agent) -> Decision:
        # 1. Least privilege: the tool must be granted to this agent.
        if call.tool not in agent.allowed_tools:
            return Decision(False, f"tool '{call.tool}' not granted to agent")
        # 2. Permitted operation: the operation must be in the agent's scope.
        if call.operation not in agent.permitted_operations:
            return Decision(False, f"operation '{call.operation}' outside agent scope")
        # 3. Egress: egress-capable tools are denied unless explicitly allowed.
        tool = agent.tool_registry.get(call.tool)
        if tool.egress and not self._allow_egress:
            self._m.egress_blocked += 1
            return Decision(False, "egress blocked: no outbound path permitted")
        # 4. High-impact actions require an available, approving human.
        if call.action_class is ActionClass.HIGH_IMPACT and self._require_human:
            if self._approver is None:
                self._m.high_impact_denied += 1
                return Decision(False, "high-impact action requires human approval; none available")
            result = self._approver(call)
            if not result or not result[0]:
                self._m.high_impact_denied += 1
                return Decision(False, "high-impact action not approved by human")
            return Decision(True, "authorized with human approval", approver=result[1])
        return Decision(True, "authorized within scope")
