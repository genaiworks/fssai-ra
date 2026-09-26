"""From one use case to a target level, a scoped control set and a first sprint.

The catalogue answers "what does good look like?". An organisation starting
out needs an earlier answer: *for this agent, how much of it do we need, and
what do we build first?* Too little and a payments swarm ships with the
controls of a summariser; too much and a summariser never ships at all, and
the team concludes the framework is impractical.

:func:`plan` reads a short use-case description (what the agent reads, what
it can change, whether it can be undone, whether it delegates, where its
tools and inputs come from, how autonomous it is) and returns:

* a **target level**, with every rule that raised it and why;
* the **applicable controls** up to that level, with each conditional
  control marked ``n/a`` only when the use case makes its condition false;
* a **first sprint** -- the level-1 controls in dependency order, plus the
  MCP gate when tools are in play, because those remove the most authority
  for the least work;
* **stop conditions**: combinations under which the agent should not be
  deployed autonomously at all, whatever controls are built;
* a pre-filled self-assessment, so ``fssaira framework assess --roadmap``
  continues from here.

The level rules are a judgement, written down so it can be argued with. Each
is a sentence a reviewer can disagree with and change, not a score.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

from .framework import Catalogue, _topological, load

AUTONOMY = ("human_in_every_loop", "human_approves_consequential", "autonomous")


class UseCaseError(ValueError):
    """A use-case description the planner cannot read."""


@dataclass(frozen=True)
class UseCase:
    """What an agent touches, changes and trusts. Every field is a plain question."""

    name: str
    #: Does it read personal or confidential records?
    reads_protected_data: bool = False
    #: Is that data regulated (health, education, financial, benefits records)?
    regulated_data: bool = False
    #: Can it change anything outside itself (write, send, file, pay, deploy)?
    external_effects: bool = False
    #: Can any of those effects not be undone (a payment, an email, a deletion)?
    irreversible_effects: bool = False
    #: Does it hand work to other agents?
    multi_agent: bool = False
    #: Does it call tools or MCP servers the organisation did not write?
    third_party_tools: bool = False
    #: Does it read content a stranger can write (web, email, uploads, tickets)?
    untrusted_input: bool = False
    #: Do its outputs leave the organisation or cross a trust zone?
    outputs_leave_org: bool = False
    #: Are its human reviewers themselves assisted by an AI model?
    ai_assisted_review: bool = False
    #: Will its record be relied on in an appeal, audit or dispute?
    record_relied_on: bool = False
    #: human_in_every_loop, human_approves_consequential or autonomous
    autonomy: str = "human_approves_consequential"
    #: Is there a source of truth that can confirm the values it proposes?
    source_of_truth: bool = True
    #: Is there a human route that serves people when the agent refuses?
    manual_fallback: bool = True

    @classmethod
    def load(cls, path: str | Path) -> UseCase:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.parse(raw)

    @classmethod
    def parse(cls, raw: dict) -> UseCase:
        if not isinstance(raw, dict) or not str(raw.get("name") or "").strip():
            raise UseCaseError("USE_CASE_NEEDS_A_NAME")
        known = {f.name: f for f in fields(cls)}
        unknown = sorted(set(raw) - set(known))
        if unknown:
            raise UseCaseError(f"UNKNOWN_USE_CASE_FIELD: {', '.join(unknown)}")
        values = {}
        for key, value in raw.items():
            if key in ("name", "autonomy"):
                values[key] = str(value)
            elif not isinstance(value, bool):
                # A missing answer is a question nobody asked; refuse rather than guess.
                raise UseCaseError(f"USE_CASE_ANSWER_MUST_BE_YES_OR_NO: {key}")
            else:
                values[key] = value
        case = cls(**values)
        if case.autonomy not in AUTONOMY:
            raise UseCaseError(f"UNKNOWN_AUTONOMY: {case.autonomy}")
        if case.regulated_data and not case.reads_protected_data:
            raise UseCaseError("REGULATED_DATA_IMPLIES_PROTECTED_DATA")
        if case.irreversible_effects and not case.external_effects:
            raise UseCaseError("IRREVERSIBLE_EFFECTS_IMPLY_EXTERNAL_EFFECTS")
        return case


#: How each conditional control's ``applies_when`` maps onto the use case.
#: tests/test_adoption_plan.py fails if the catalogue gains a condition that is
#: not mapped here, so a new conditional control cannot be silently skipped.
CONDITIONS = {
    "the workflow touches regulated personal data": lambda u: u.regulated_data,
    "agents can trigger irreversible external effects": lambda u: u.irreversible_effects,
    "agent outputs leave the organisation or cross trust zones": lambda u: u.outputs_leave_org,
    "agents delegate to other agents or tools": lambda u: u.multi_agent or u.third_party_tools,
    "agents cause effects in external systems": lambda u: u.external_effects,
    "reviewers are assisted by an AI model": lambda u: u.ai_assisted_review,
}


def _level_rules(u: UseCase) -> list[tuple[int, str]]:
    """Every rule that sets a floor on the target level, with its reason."""
    rules = [(1, "every agent: named owner, no credentials in the agent, declared interfaces, "
                 "a tamper-evident log")]
    if u.external_effects or u.reads_protected_data:
        rules.append((2, "it reads protected data or changes systems, so every action must sit "
                         "inside a declared task contract and approval must bind the exact action"))
    if u.regulated_data:
        rules.append((3, "regulated data: every read and release must be purpose-bound, "
                         "consented where required and checked again at release"))
    if u.outputs_leave_org:
        rules.append((3, "outputs leave the organisation: release must be governed, not just access"))
    if u.multi_agent:
        rules.append((4, "agents delegate: authority, budget and restrictions must hold across the "
                         "whole chain, not per hop"))
    if u.irreversible_effects:
        rules.append((4, "effects cannot be undone: fenced commits, objection windows and "
                         "reconciliation are needed before anything irreversible runs"))
    if u.third_party_tools and u.untrusted_input:
        rules.append((4, "third-party tools plus untrusted input is the injection-to-action path: "
                         "tool supply must be pinned and tainted sessions kept from privileged tools"))
    if u.autonomy == "autonomous" and u.external_effects:
        rules.append((4, "it acts without a human in the loop, so composition safety cannot be "
                         "delegated to a reviewer"))
    if u.record_relied_on:
        rules.append((5, "its record will be relied on in appeals or audits, so the evidence must be "
                         "independently verifiable, witnessed and time-anchored"))
    if u.autonomy == "autonomous" and u.irreversible_effects and u.regulated_data:
        rules.append((5, "autonomous, irreversible and regulated: only evidenced controls are enough"))
    return rules


def _stop_conditions(u: UseCase) -> list[str]:
    """Combinations where the right answer is 'do not deploy this autonomously yet'."""
    stops = []
    if not u.manual_fallback:
        stops.append("There is no manual route. A refusal will strand the person being served; "
                     "build the fallback before the agent (GOV-1).")
    if u.irreversible_effects and u.autonomy == "autonomous" and not u.source_of_truth:
        stops.append("Irreversible, autonomous and nothing can confirm its values. Mediation can prove an "
                     "action was allowed, never that it was right; keep a human approving each effect.")
    if u.irreversible_effects and u.untrusted_input and u.autonomy == "autonomous":
        stops.append("Untrusted input can steer irreversible effects with no human in the loop. Require "
                     "exact-action approval for every irreversible tool (the MCP gate's `approval: "
                     "required`) before going autonomous.")
    return stops


def plan(use_case: UseCase, catalogue: Catalogue | None = None) -> dict:
    catalogue = catalogue or load()
    rules = _level_rules(use_case)
    target = max(level for level, _ in rules)
    unmapped = sorted({c.applies_when for c in catalogue.controls
                       if c.applies_when and c.applies_when not in CONDITIONS})
    status: dict[str, str] = {}
    not_applicable = []
    for control in catalogue.controls:
        condition = control.applies_when
        applies = True if not condition or condition not in CONDITIONS else CONDITIONS[condition](use_case)
        if not applies:
            status[control.id] = "n/a"
            not_applicable.append({"id": control.id, "name": control.name, "because_not": condition})
        else:
            status[control.id] = "no"
    ordered = [c for c in _topological(catalogue.controls) if status[c.id] != "n/a"]
    required = [c for c in ordered if c.level <= target]
    beyond = [c for c in ordered if c.level > target]
    sprint = [{"id": c.id, "name": c.name, "owner": c.owner, "build": list(c.implementation),
               "prove": list(c.verify)} for c in ordered if c.level == 1]
    if use_case.third_party_tools or use_case.external_effects:
        sprint.append({
            "id": "MCP gate", "name": "Put every tool behind the MCP gate",
            "owner": "Platform owner",
            "build": ["fssaira mcp scan", "fssaira mcp lock", "fssaira mcp serve"],
            "prove": ["tests/test_mcp_gate.py", "python scripts/mcp_gate_demo.py"]})
    waves = {}
    for c in required:
        waves.setdefault(c.level, []).append({"id": c.id, "name": c.name, "owner": c.owner})
    return {
        "use_case": use_case.name,
        "target_level": target,
        "target_level_name": catalogue.levels[target],
        "why": [{"level": level, "reason": reason} for level, reason in rules],
        "required_controls": len(required),
        "not_applicable": not_applicable,
        "beyond_target": len(beyond),
        "first_sprint": sprint,
        "waves": [{"level": level, "name": catalogue.levels[level], "controls": items}
                  for level, items in sorted(waves.items())],
        "stop_conditions": _stop_conditions(use_case),
        "assessment": status,
        "unmapped_conditions": unmapped,
        "catalogue": catalogue.version,
        "basis": "a documented judgement over the use-case answers; review and adjust it",
    }


def assessment_yaml(result: dict, catalogue: Catalogue | None = None) -> str:
    """A self-assessment pre-filled with the plan's n/a decisions, ready to answer."""
    catalogue = catalogue or load()
    lines = [f"# Self-assessment for: {result['use_case']}",
             f"# Target: level {result['target_level']} ({result['target_level_name']}), "
             f"catalogue {result['catalogue']}.",
             "# Statuses: evidenced | implemented | partial | planned | no | n/a",
             "# n/a entries were set by `fssaira framework plan`; change them only if the use case changes.",
             ""]
    for control in catalogue.controls:
        value = result["assessment"][control.id]
        lines.append(f"# {control.id} (level {control.level}): {control.question}")
        # Quoted, so no YAML reader turns a bare `no` into a boolean.
        lines.append(f"{control.id}: \"{'n/a' if value == 'n/a' else 'no'}\"")
    return "\n".join(lines) + "\n"


__all__ = ["AUTONOMY", "CONDITIONS", "UseCase", "UseCaseError", "assessment_yaml", "plan"]
