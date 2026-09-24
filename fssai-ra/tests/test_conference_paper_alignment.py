"""The paper may quote conference figures only as the evidence generator produced them.

``conference/evidence/summary.json`` is written by ``scripts/conference_evidence.py``.
Each template below is rendered from it and must appear verbatim in the paper, so a
regenerated figure forces the sentence quoting it to change.
"""
<<<<<<< HEAD

=======
>>>>>>> d3bd81d (Snapshot: uncommitted conference layer from main working tree (pre-hardening baseline))
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "conference" / "evidence" / "summary.json"
FULL = ROOT / "paper" / "trust-by-construction.md"
EXTENDED = ROOT / "paper" / "extended-abstract.md"


@pytest.fixture(scope="module")
def figures() -> dict:
    body = json.loads(SUMMARY.read_text())["figures"]
    removed = body["stateful_violations_when_control_removed"].values()
    return {**body, "stateful_steps_display": f"{body['stateful_steps']:,}",
            "stateful_removed_min": min(removed), "stateful_removed_max": max(removed),
            "redteam_context_gate_removed": body["redteam_successes_when_one_control_removed"]["context_gate"]}


FULL_TEMPLATES = [
    "**{falsifiers_held} of {falsifiers} falsifiers held**",
    "**{blocked_attacks} of {attack_attempts} attack attempts were blocked**",
    "**{ablation_load_bearing} of {ablation_rows} ablations**",
    "**{stateful_steps_display} steps with {stateful_violations} violations and {stateful_false_denials} false denials**",
    "between {stateful_removed_min} and {stateful_removed_max} violations",
    "**{redteam_attempts} red-team attempts produced {redteam_successes} successes**",
    "with the context gate removed, {redteam_context_gate_removed} of 150 succeeded",
    "**{malicious_pack_findings} findings**",
    "**{delegation_escalations_refused} of {delegation_escalation_cases} delegation escalations**",
    "**{model_attestation_attacks_refused} of {model_attestation_attacks} model-substitution attacks**",
    "**{identity_values_seen_by_model} identity values**",
    "**{erasure_readable_locations} of {erasure_locations_checked} checked locations**",
    "128 concurrent callers produced **{concurrency_mutations_128_callers} mutation**",
    "**{claims_pass} of {claims} register claims**",
    "{falsifiers_held} of {falsifiers} falsifiers held and {redteam_attempts} red-team attempts produced "
    "{redteam_successes} successes",
    "restored harm in {ablation_load_bearing} of {ablation_rows} ablations",
]
EXTENDED_TEMPLATES = [
    "{falsifiers_held} of {falsifiers} falsifiers held and {redteam_attempts} red-team attempts produced "
    "{redteam_successes} successes",
]


@pytest.mark.parametrize("template", FULL_TEMPLATES)
def test_full_paper_quotes_conference_figures_as_generated(template, figures):
    assert template.format(**figures) in FULL.read_text(encoding="utf-8")


@pytest.mark.parametrize("template", EXTENDED_TEMPLATES)
def test_extended_abstract_quotes_conference_figures_as_generated(template, figures):
    assert template.format(**figures) in EXTENDED.read_text(encoding="utf-8")


def test_conference_figures_are_scoped_and_kept_out_of_the_pack_denominators():
    text = FULL.read_text(encoding="utf-8")
    assert "one synthetic pack in one process" in text
    assert "not included in the six-pack or four-pack denominators" in text
<<<<<<< HEAD


pytestmark = pytest.mark.manuscript
=======
>>>>>>> d3bd81d (Snapshot: uncommitted conference layer from main working tree (pre-hardening baseline))
