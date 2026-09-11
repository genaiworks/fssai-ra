"""Bounded-intelligence domain: local models, a task router, least-privilege
agents, and a tool registry.

Retrieved content is wrapped as :class:`UntrustedEvidence` and passed to the
model as *data*, never as instructions. Agents are least-privilege: each has an
explicit set of allowed tools, permitted operations, and a data scope. Every
proposed tool call is routed through the policy enforcement point before it can
have any effect, so the model proposes and the policy disposes.

The router in this module selects which model handles a task. It deliberately
cannot change what that model is allowed to do: routing is a performance and
cost decision, never an authority decision. ``tests/test_privilege_invariance.py``
holds it to that.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from .accountable_action import ActionClass, Decision, PolicyEnforcementPoint, Tool, ToolCall
from .evidence import EvidenceLedger
from .metrics import Metrics


@dataclass(frozen=True)
class UntrustedEvidence:
    source: str
    text: str


class ToolRegistry:
    """Named callables plus their egress classification.

    Registration is an administrative act: a tool that exists here but is not in
    an agent's grant is still unreachable by that agent.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._fns: dict[str, Callable] = {}

    def register(self, name: str, fn: Callable, *, egress: bool = False) -> None:
        self._tools[name] = Tool(name, egress=egress)
        self._fns[name] = fn

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def call(self, name: str, **kwargs):
        return self._fns[name](**kwargs)


class ModelBackend(Protocol):
    def propose(self, task: str, evidence: list[UntrustedEvidence]) -> list[ToolCall]: ...


@dataclass
class Agent:
    id: str
    allowed_tools: set
    permitted_operations: set
    data_scope: set
    tool_registry: ToolRegistry
    max_calls: int = 8

    def grant_summary(self) -> dict:
        return {
            "agent": self.id,
            "tools": sorted(self.allowed_tools),
            "operations": sorted(self.permitted_operations),
            "data_scope": sorted(self.data_scope),
            "max_calls": self.max_calls,
        }


class BoundedAgent:
    def __init__(self, agent: Agent, model: ModelBackend, pep: PolicyEnforcementPoint,
                 evidence: EvidenceLedger, append_token: str, metrics: Metrics) -> None:
        self.agent = agent
        self.model = model
        self.pep = pep
        self._evidence = evidence
        self._token = append_token
        self._m = metrics

    @property
    def model_name(self) -> str:
        return getattr(self.model, "name", type(self.model).__name__)

    def run(self, task: str, evidence_items: list[UntrustedEvidence] | None = None) -> list[dict]:
        evidence_items = evidence_items or []
        plan = self.model.propose(task, evidence_items)[: self.agent.max_calls]
        return [self.execute(call) for call in plan]

    def execute(self, call: ToolCall) -> dict:
        """Submit a single (possibly attacker-influenced) tool call to the PEP."""
        decision = self.pep.check(call, self.agent)
        outcome = {"call": call, "decision": decision, "result": None}
        if decision.allowed:
            outcome["result"] = self.agent.tool_registry.call(call.tool, **call.args)
        return outcome


@dataclass(frozen=True)
class Route:
    """One routing rule: a keyword match to a named model backend."""

    match: str
    model: str
    note: str = ""


class TaskRouter:
    """Selects a model per task. Routing never widens authority.

    A router is useful (send short classifications to a small model, long
    drafting to a larger one) and dangerous if it is allowed to imply trust. The
    agent grant, the capability catalogue, and the enforcement point are
    identical whichever route is taken, so the worst a subverted router can do
    is pick a worse model -- not a more privileged one.
    """

    def __init__(self, default: str, routes: list[Route] | None = None,
                 *, builder: Callable[[str], object] | None = None) -> None:
        self.default = default
        self.routes = list(routes or [])
        self._builder = builder
        self._cache: dict[str, object] = {}

    def choose(self, task: str) -> str:
        lowered = task.lower()
        for route in self.routes:
            if route.match.lower() in lowered:
                return route.model
        return self.default

    def model_for(self, task: str) -> object:
        name = self.choose(task)
        if name not in self._cache:
            if self._builder is None:
                from .models import build_model

                self._cache[name] = build_model(name)
            else:
                self._cache[name] = self._builder(name)
        return self._cache[name]

    def propose(self, task: str, evidence: list[UntrustedEvidence]) -> list[ToolCall]:
        return self.model_for(task).propose(task, evidence)

    @property
    def name(self) -> str:
        return f"router({self.default})"


def _deterministic_model(agent_id: str):
    from .models.deterministic import DeterministicModel

    return DeterministicModel(agent_id)


class _RuleBasedShim:
    """Kept so ``from fssaira import RuleBasedLocalModel`` still works."""

    def __new__(cls, agent_id: str = "agent-1", **kwargs):
        return _deterministic_model(agent_id)


RuleBasedLocalModel = _RuleBasedShim

__all__ = [
    "Agent", "BoundedAgent", "ModelBackend", "Route", "RuleBasedLocalModel",
    "TaskRouter", "ToolRegistry", "UntrustedEvidence",
]
