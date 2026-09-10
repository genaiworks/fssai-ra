"""Bounded-intelligence domain: local models, a semantic router, least-privilege
agents, and a tool registry.

Retrieved content is wrapped as :class:`UntrustedEvidence` and passed to the
model as *data*, never as instructions. Agents are least-privilege: each has an
explicit set of allowed tools, permitted operations, and a data scope. Every
proposed tool call is routed through the policy enforcement point before it can
have any effect, so the model proposes and the policy disposes.
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
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._fns: dict[str, Callable] = {}

    def register(self, name: str, fn: Callable, *, egress: bool = False) -> None:
        self._tools[name] = Tool(name, egress=egress)
        self._fns[name] = fn

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def call(self, name: str, **kwargs):
        return self._fns[name](**kwargs)


class ModelBackend(Protocol):
    def propose(self, task: str, evidence: list[UntrustedEvidence]) -> list[ToolCall]: ...


class RuleBasedLocalModel:
    """Deterministic offline stand-in for a local LLM (e.g. Llama via Ollama).

    It maps a small set of benign tasks to proposed tool calls so the demo and
    tests are reproducible with no model weights. Swap in
    ``adapters/local_model_ollama.py`` for a real local model; the ``propose``
    signature is the seam.
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def propose(self, task: str, evidence: list[UntrustedEvidence]) -> list[ToolCall]:
        t = task.lower()
        if "recommend" in t or "student-support" in t or "support" in t:
            return [
                ToolCall(self.agent_id, "read_case", "read_case", target=task,
                         action_class=ActionClass.REVERSIBLE, rationale="review assigned case"),
                ToolCall(self.agent_id, "prepare_recommendation", "prepare_recommendation",
                         target=task, action_class=ActionClass.REVERSIBLE,
                         rationale="draft a recommendation for a human to review"),
            ]
        return []


@dataclass
class Agent:
    id: str
    allowed_tools: set
    permitted_operations: set
    data_scope: set
    tool_registry: ToolRegistry
    max_calls: int = 8


class BoundedAgent:
    def __init__(self, agent: Agent, model: ModelBackend, pep: PolicyEnforcementPoint,
                 evidence: EvidenceLedger, append_token: str, metrics: Metrics) -> None:
        self.agent = agent
        self.model = model
        self.pep = pep
        self._evidence = evidence
        self._token = append_token
        self._m = metrics

    def run(self, task: str, evidence_items: list[UntrustedEvidence] | None = None) -> list[dict]:
        evidence_items = evidence_items or []
        plan = self.model.propose(task, evidence_items)[: self.agent.max_calls]
        results = []
        for call in plan:
            results.append(self.execute(call))
        return results

    def execute(self, call: ToolCall) -> dict:
        """Submit a single (possibly attacker-influenced) tool call to the PEP."""
        decision = self.pep.check(call, self.agent)
        outcome = {"call": call, "decision": decision, "result": None}
        if decision.allowed:
            outcome["result"] = self.agent.tool_registry.call(call.tool, **call.args)
        return outcome
