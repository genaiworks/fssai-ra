"""Accountable-action domain: the policy enforcement point (PEP), action
classes, human approval, and evidence logging.

The central fail-secure rule: a consequential (high-impact) action is only
authorized when an independent execution service verifies the *actual*
operation and current policy - never the model's explanation of what it is
doing. If required authorization is missing or uncertain, the action is denied
(fail-secure), and a defined manual path preserves service.

Three properties are enforced here and tested in ``tests/test_attacks.py`` and
``tests/test_privilege_invariance.py``:

**Least privilege.** A call must name a tool granted to this agent and an
operation inside its scope. Both lists are deployment configuration.

**Privilege invariance.** The action class used for the decision is read from
the deployment's capability catalogue, never from the call. A compromised agent
that constructs ``ToolCall(..., action_class=REVERSIBLE)`` for an operation the
catalogue classes as high-impact is *still* routed to a named human, and the
attempted downgrade is recorded as its own evidence record. Without this, the
"model proposes, policy disposes" claim leaks: the proposer would be setting
its own review level.

**Default-deny egress.** Tools that can send data outward are denied unless a
deployment explicitly allows them, and argument inspection catches a
non-egress-classified tool being handed an outward destination.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from .evidence import EvidenceLedger
from .metrics import Metrics


class ActionClass(Enum):
    REVERSIBLE = "reversible"
    HIGH_IMPACT = "high_impact"


#: Stable denial codes. Tests, metrics, dashboards, and the paper's result
#: tables all key on these, so they are part of the public contract.
class DenyCode:
    TOOL_NOT_GRANTED = "TOOL_NOT_GRANTED"
    OPERATION_OUT_OF_SCOPE = "OPERATION_OUT_OF_SCOPE"
    EGRESS_BLOCKED = "EGRESS_BLOCKED"
    EGRESS_IN_ARGUMENTS = "EGRESS_IN_ARGUMENTS"
    NO_APPROVER_AVAILABLE = "NO_APPROVER_AVAILABLE"
    HUMAN_DENIED = "HUMAN_DENIED"
    CALL_BUDGET_EXHAUSTED = "CALL_BUDGET_EXHAUSTED"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    ALLOWED = "ALLOWED"
    ALLOWED_WITH_APPROVAL = "ALLOWED_WITH_APPROVAL"


_OUTWARD_ARGUMENT = re.compile(
    r"(https?://|ftp://|mailto:|\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b|\b\d{1,3}(?:\.\d{1,3}){3}:\d+\b)",
    re.IGNORECASE,
)


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
    code: str = ""
    effective_class: ActionClass | None = None
    class_downgrade_attempted: bool = False


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
        catalogue=None,
        inspect_arguments: bool = True,
        enforce_call_budget: bool = True,
    ) -> None:
        self._evidence = evidence
        self._token = append_token
        self._m = metrics
        self._allow_egress = allow_egress
        self._approver = approver
        self._require_human = require_human_for_high_impact
        self._catalogue = catalogue
        self._inspect_arguments = inspect_arguments
        self._enforce_budget = enforce_call_budget
        self._calls_by_agent: dict[str, int] = {}

    # -- public API --------------------------------------------------------
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
                "effective_class": (
                    decision.effective_class.value if decision.effective_class else call.action_class.value
                ),
                "class_downgrade_attempted": decision.class_downgrade_attempted,
                "model_rationale": call.rationale,  # recorded for audit, not used to decide
                "allowed": decision.allowed,
                "code": decision.code,
                "reason": decision.reason,
                "approver": decision.approver,
            },
            token=self._token,
        )
        if decision.class_downgrade_attempted:
            self._m.class_downgrade_attempts += 1
        if decision.allowed:
            self._m.tool_calls_allowed += 1
        else:
            self._m.tool_calls_denied += 1
        return decision

    def effective_class(self, call: ToolCall) -> tuple[ActionClass, bool]:
        """Resolve the action class from the catalogue, not from the caller.

        Returns ``(class, downgrade_attempted)``. With no catalogue configured
        the declared class is used and no downgrade can be detected -- which is
        why a deployment should always configure one.
        """
        if self._catalogue is None:
            return call.action_class, False
        capability = self._catalogue.get(call.tool)
        if capability is None:
            return ActionClass.HIGH_IMPACT, False  # unknown capability fails closed
        declared = call.action_class
        actual = capability.action_class
        downgraded = (
            declared is ActionClass.REVERSIBLE and actual is ActionClass.HIGH_IMPACT
        )
        return actual, downgraded

    def reset_budgets(self) -> None:
        self._calls_by_agent.clear()

    # -- evaluation --------------------------------------------------------
    def _evaluate(self, call: ToolCall, agent) -> Decision:
        actual_class, downgraded = self.effective_class(call)

        def deny(code: str, reason: str) -> Decision:
            return Decision(False, reason, code=code, effective_class=actual_class,
                            class_downgrade_attempted=downgraded)

        # 0. Call budget: a looping or runaway agent is a denial-of-service risk.
        if self._enforce_budget:
            budget = getattr(agent, "max_calls", None)
            if budget is not None:
                used = self._calls_by_agent.get(call.agent_id, 0)
                if used >= budget:
                    return deny(DenyCode.CALL_BUDGET_EXHAUSTED,
                                f"agent exceeded its budget of {budget} enforced calls")
                self._calls_by_agent[call.agent_id] = used + 1

        # 1. Least privilege: the tool must be granted to this agent.
        if call.tool not in agent.allowed_tools:
            return deny(DenyCode.TOOL_NOT_GRANTED, f"tool '{call.tool}' not granted to agent")
        # 2. Permitted operation: the operation must be in the agent's scope.
        if call.operation not in agent.permitted_operations:
            return deny(DenyCode.OPERATION_OUT_OF_SCOPE, f"operation '{call.operation}' outside agent scope")
        # 3. Egress: egress-capable tools are denied unless explicitly allowed.
        try:
            tool = agent.tool_registry.get(call.tool)
        except KeyError:
            return deny(DenyCode.UNKNOWN_CAPABILITY, f"tool '{call.tool}' is not registered")
        if tool.egress and not self._allow_egress:
            self._m.egress_blocked += 1
            return deny(DenyCode.EGRESS_BLOCKED, "egress blocked: no outbound path permitted")
        # 3b. A tool that is not egress-classified must not be handed a destination.
        if self._inspect_arguments and not tool.egress and not self._allow_egress:
            outward = self._outward_arguments(call)
            if outward:
                self._m.egress_blocked += 1
                return deny(DenyCode.EGRESS_IN_ARGUMENTS,
                            f"outward destination in arguments: {', '.join(sorted(outward))}")
        # 4. High-impact actions require an available, approving human.
        if actual_class is ActionClass.HIGH_IMPACT and self._require_human:
            if self._approver is None:
                self._m.high_impact_denied += 1
                return deny(DenyCode.NO_APPROVER_AVAILABLE,
                            "high-impact action requires human approval; none available")
            result = self._approver(call)
            if not result or not result[0]:
                self._m.high_impact_denied += 1
                return deny(DenyCode.HUMAN_DENIED, "high-impact action not approved by human")
            return Decision(True, "authorized with human approval", approver=result[1],
                            code=DenyCode.ALLOWED_WITH_APPROVAL, effective_class=actual_class,
                            class_downgrade_attempted=downgraded)
        return Decision(True, "authorized within scope", code=DenyCode.ALLOWED,
                        effective_class=actual_class, class_downgrade_attempted=downgraded)

    @staticmethod
    def _outward_arguments(call: ToolCall) -> set[str]:
        found: set[str] = set()
        for key, value in (call.args or {}).items():
            match = _OUTWARD_ARGUMENT.search(str(value))
            if match:
                found.add(f"{key}={match.group(0)[:80]}")
        return found


__all__ = [
    "ActionClass", "DenyCode", "Decision", "HumanApprover",
    "PolicyEnforcementPoint", "Tool", "ToolCall",
]
