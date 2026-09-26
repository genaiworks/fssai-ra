"""From a use case to a target level: proportionate, explained, and never silently incomplete."""
from pathlib import Path

import pytest
import yaml

from fssaira.adoption_plan import CONDITIONS, UseCase, UseCaseError, assessment_yaml, plan
from fssaira.framework import assess, load, load_answers

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "examples" / "use-cases"


def case(**answers):
    return UseCase.parse({"name": "test", **answers})


def test_every_conditional_control_is_mapped_to_a_use_case_question():
    conditions = {c.applies_when for c in load().controls if c.applies_when}
    assert conditions <= set(CONDITIONS), sorted(conditions - set(CONDITIONS))
    assert plan(case())["unmapped_conditions"] == []


@pytest.mark.parametrize("name, level", [("meeting-summariser", 1), ("records-correction", 3),
                                         ("payments-swarm", 5)])
def test_the_worked_examples_get_proportionate_targets(name, level):
    result = plan(UseCase.load(CASES / f"{name}.yaml"))
    assert result["target_level"] == level
    assert result["why"][-1]["level"] == level or any(w["level"] == level for w in result["why"])


def test_every_level_rise_has_a_stated_reason():
    result = plan(case(reads_protected_data=True, regulated_data=True, external_effects=True,
                       multi_agent=True))
    assert result["target_level"] == 4
    assert {w["level"] for w in result["why"]} == {1, 2, 3, 4}
    assert all(w["reason"] for w in result["why"])


def test_conditional_controls_are_na_only_when_their_condition_is_false():
    quiet = plan(case())
    busy = plan(case(reads_protected_data=True, regulated_data=True, external_effects=True,
                     irreversible_effects=True, multi_agent=True, outputs_leave_org=True,
                     ai_assisted_review=True))
    assert {c["id"] for c in quiet["not_applicable"]} == {
        c.id for c in load().controls if c.applies_when}
    assert busy["not_applicable"] == []


def test_tools_put_the_mcp_gate_in_the_first_sprint():
    assert "MCP gate" not in [s["id"] for s in plan(case())["first_sprint"]]
    assert "MCP gate" in [s["id"] for s in plan(case(third_party_tools=True))["first_sprint"]]


def test_stop_conditions_name_the_combinations_to_not_automate():
    assert plan(case())["stop_conditions"] == []
    assert plan(case(manual_fallback=False))["stop_conditions"]
    blind = plan(case(external_effects=True, irreversible_effects=True, autonomy="autonomous",
                      source_of_truth=False))
    assert any("confirm its values" in s for s in blind["stop_conditions"])
    steered = plan(case(external_effects=True, irreversible_effects=True, autonomy="autonomous",
                        untrusted_input=True))
    assert any("approval" in s for s in steered["stop_conditions"])
    supervised = plan(case(external_effects=True, irreversible_effects=True, untrusted_input=True))
    assert supervised["stop_conditions"] == []


def test_the_prefilled_assessment_feeds_the_existing_roadmap(tmp_path):
    result = plan(UseCase.load(CASES / "records-correction.yaml"))
    path = tmp_path / "assessment.yaml"
    path.write_text(assessment_yaml(result))
    assert set(yaml.safe_load(path.read_text()).values()) == {"no", "n/a"}
    scored = assess(load_answers(path))
    assert scored["warnings"] == [] and scored["evidenced_level"] == 0
    assert scored["counts"]["n/a"] == len(result["not_applicable"])


@pytest.mark.parametrize("raw, message", [
    ({}, "USE_CASE_NEEDS_A_NAME"),
    ({"name": "x", "reads_everything": True}, "UNKNOWN_USE_CASE_FIELD"),
    ({"name": "x", "external_effects": "maybe"}, "USE_CASE_ANSWER_MUST_BE_YES_OR_NO"),
    ({"name": "x", "autonomy": "mostly"}, "UNKNOWN_AUTONOMY"),
    ({"name": "x", "regulated_data": True}, "REGULATED_DATA_IMPLIES_PROTECTED_DATA"),
    ({"name": "x", "irreversible_effects": True}, "IRREVERSIBLE_EFFECTS_IMPLY_EXTERNAL_EFFECTS"),
])
def test_unclear_use_cases_are_refused_not_guessed(raw, message):
    with pytest.raises(UseCaseError, match=message):
        UseCase.parse(raw)


def test_the_adoption_guide_quotes_what_the_planner_computes():
    guide = (ROOT / "docs" / "ADOPT.md").read_text()
    for name in ("meeting-summariser", "records-correction", "payments-swarm"):
        result = plan(UseCase.load(CASES / f"{name}.yaml"))
        row = f"| {result['use_case']} | {result['target_level']} {result['target_level_name']} | " \
              f"{result['required_controls']} |"
        assert row in guide, row


def test_cli_plan_writes_an_assessment_and_exits_nonzero_on_a_stop(tmp_path, capsys):
    from fssaira.cli import main

    out = tmp_path / "assessment.yaml"
    assert main(["framework", "plan", str(CASES / "records-correction.yaml"),
                 "--write-assessment", str(out)]) == 0
    assert out.is_file() and "target level 3" in capsys.readouterr().out
    assert main(["framework", "plan", str(CASES / "payments-swarm.yaml")]) == 1
