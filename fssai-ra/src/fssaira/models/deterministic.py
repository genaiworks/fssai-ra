"""Deterministic offline backend: the default in tests, evaluation, and CI.

No weights, no network, no nondeterminism. It exists so that every assurance
claim in this repository can be reproduced on a disconnected laptop, and so the
adversarial suite measures the *controls* rather than a particular model's mood.
It also doubles as the honest-baseline arm in the utility evaluation.
"""
from __future__ import annotations

from ..accountable_action import ToolCall
from .base import CapabilityCatalogue, parse_proposals


class DeterministicModel:
    """Maps a small set of tasks to proposed tool calls, reproducibly."""

    name = "deterministic"

    def __init__(
        self,
        agent_id: str = "agent-1",
        *,
        catalogue: CapabilityCatalogue | None = None,
        script: dict[str, list[dict]] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.catalogue = catalogue or CapabilityCatalogue.default()
        self._script = script or {}

    def health(self) -> dict:
        return {"backend": self.name, "reachable": True, "model": "rule-based", "offline": True}

    def propose(self, task: str, evidence: list | None = None) -> list[ToolCall]:
        lowered = task.lower()
        for trigger, plan in self._script.items():
            if trigger.lower() in lowered:
                return self._materialise(plan)
        if any(word in lowered for word in ("recommend", "support", "review", "case")):
            return self._materialise([
                {"tool": "read_case", "target": task, "rationale": "review the assigned case"},
                {"tool": "prepare_recommendation", "target": task,
                 "rationale": "draft a recommendation for a human to review"},
            ])
        return []

    def _materialise(self, plan: list[dict]) -> list[ToolCall]:
        import json

        return parse_proposals(
            json.dumps(plan), agent_id=self.agent_id,
            catalogue=self.catalogue, model_name=self.name,
        )


# Backwards-compatible alias for the name used in v0.5.0 and in the paper text.
RuleBasedLocalModel = DeterministicModel

__all__ = ["DeterministicModel", "RuleBasedLocalModel"]
