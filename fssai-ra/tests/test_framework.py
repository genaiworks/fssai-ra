"""The adoption framework: catalogue integrity, assessment, roadmap, starter kit, docs."""
from pathlib import Path

import pytest
import yaml

from fssaira.cli import main
from fssaira.framework import (
    STATUSES,
    assess,
    assessment_template,
    init_workspace,
    load,
    load_answers,
    render_markdown,
    roadmap,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]


def all_status(value, catalogue=None):
    return {c.id: value for c in (catalogue or load()).controls}


def test_every_module_test_and_code_the_catalogue_cites_exists():
    assert validate() == []


def test_catalogue_covers_every_domain_and_level_and_every_control_is_askable():
    catalogue = load()
    assert len(catalogue.controls) >= 45
    assert {c.domain for c in catalogue.controls} == set(catalogue.domains)
    assert {c.level for c in catalogue.controls} == set(catalogue.levels)
    for c in catalogue.controls:
        assert c.question.endswith('?') and c.verify and c.owner


def test_validation_catches_broken_references_cycles_and_level_inversions():
    catalogue = load()
    first, second = catalogue.controls[0], catalogue.controls[1]
    broken = [first.__class__(**{**first.__dict__, 'verify': ('tests/test_nowhere.py::test_x',),
                                 'codes': ('NOT_A_REAL_CODE',)}),
              second.__class__(**{**second.__dict__, 'requires': (second.id,)}),
              *catalogue.controls[2:]]
    problems = validate(catalogue.__class__(catalogue.version, catalogue.levels,
                                            catalogue.domains, tuple(broken)))
    joined = '\n'.join(problems)
    assert 'test missing' in joined and 'not registered' in joined and 'cycle' in joined
    high = next(c for c in catalogue.controls if c.level == 5)
    low = next(c for c in catalogue.controls if c.level == 1)
    inverted = [low.__class__(**{**low.__dict__, 'requires': (high.id,)}) if c.id == low.id else c
                for c in catalogue.controls]
    assert any('requires' in p for p in validate(catalogue.__class__(
        catalogue.version, catalogue.levels, catalogue.domains, tuple(inverted))))


def test_levels_are_earned_by_evidence_not_by_claims():
    catalogue = load()
    assert assess(all_status('evidenced'))['evidenced_level'] == 5
    nothing = assess({})
    assert nothing['evidenced_level'] == 0 and nothing['claimed_level'] == 0
    claimed = assess(all_status('implemented'))
    assert claimed['evidenced_level'] == 0 and claimed['claimed_level'] == 5
    assert claimed['claim_gap'] == 5
    level_three = {c.id: ('evidenced' if c.level <= 3 else 'no') for c in catalogue.controls}
    assert assess(level_three)['evidenced_level'] == 3


def test_n_a_is_only_accepted_where_the_control_names_a_condition():
    catalogue = load()
    optional = [c for c in catalogue.controls if c.applies_when]
    mandatory = next(c for c in catalogue.controls if not c.applies_when)
    assert optional
    answers = {c.id: ('n/a' if c.applies_when else 'evidenced') for c in catalogue.controls}
    assert assess(answers)['evidenced_level'] == 5 and not assess(answers)['warnings']
    answers[mandatory.id] = 'n/a'
    result = assess(answers)
    assert result['status'][mandatory.id] == 'no' and result['warnings']
    assert result['evidenced_level'] < mandatory.level or mandatory.level == 5


def test_unknown_statuses_and_unknown_controls_warn():
    result = assess({'GOV-1': 'sort of', 'XYZ-9': 'evidenced'})
    assert any('sort of' in w for w in result['warnings'])
    assert any('XYZ-9' in w for w in result['warnings'])


def test_roadmap_puts_dependencies_first_and_separates_prove_from_build():
    catalogue = load()
    plan = roadmap({'EVD-1': 'implemented'})
    order = [item['id'] for wave in plan['waves'] for item in wave['controls']]
    index = {cid: i for i, cid in enumerate(order)}
    for c in catalogue.controls:
        for dep in c.requires:
            assert index[dep] < index[c.id], (dep, c.id)
    assert [w['to_level'] for w in plan['waves']] == sorted(w['to_level'] for w in plan['waves'])
    evd1 = next(i for w in plan['waves'] for i in w['controls'] if i['id'] == 'EVD-1')
    assert evd1['evidence_only'] and evd1['prove']
    assert roadmap(all_status('evidenced'))['waves'] == []


def test_the_generated_control_document_is_current():
    assert (ROOT / 'docs/framework/CONTROLS.md').read_text(encoding='utf-8') == render_markdown(), \
        'run: fssaira framework render'


def test_starter_workspace_is_complete_and_starts_at_level_zero(tmp_path):
    target = tmp_path / 'acme'
    written = init_workspace(target, org='Acme Health', sector='healthcare', target_level=4)
    names = {p.relative_to(target).as_posix() for p in written}
    for expected in ('README.md', 'assessment.yaml', 'policy/healthcare.pack.yaml',
                     'deploy/k8s/agent-cell.yaml', 'deploy/witnesses.yaml',
                     '.github/workflows/agentic-assurance.yml', 'runbooks/revocation.md',
                     'evidence/BUNDLE.md'):
        assert expected in names
    answers = load_answers(target / 'assessment.yaml')
    assert set(answers) == {c.id for c in load().controls}
    result = assess(answers)
    assert result['evidenced_level'] == 0 and not result['warnings']
    cell = list(yaml.safe_load_all((target / 'deploy/k8s/agent-cell.yaml').read_text()))
    assert cell[0]['spec']['automountServiceAccountToken'] is False
    assert cell[1]['spec']['ingress'] == []
    assert '--min-level 4' in (target / '.github/workflows/agentic-assurance.yml').read_text()
    with pytest.raises(FileExistsError):
        init_workspace(target, org='Acme', sector='healthcare')
    with pytest.raises(ValueError):
        init_workspace(tmp_path / 'x', org='Acme', sector='astrology')


def test_bare_yaml_no_is_read_as_no_not_as_a_boolean(tmp_path):
    path = tmp_path / 'a.yaml'
    path.write_text('GOV-1: no\nIDN-1: evidenced\nAUT-5: n/a\n')
    answers = load_answers(path)
    assert answers['GOV-1'] == 'no' and not assess(answers)['warnings']
    assert set(STATUSES) >= set(answers.values())
    assert '"no"' in assessment_template()


def test_cli_assess_gates_on_the_minimum_level(tmp_path, capsys):
    init_workspace(tmp_path / 'w', org='Acme', sector='finance')
    answers = tmp_path / 'w' / 'assessment.yaml'
    assert main(['framework', 'assess', str(answers), '--roadmap']) == 0
    assert main(['framework', 'assess', str(answers), '--min-level', '1']) == 2
    assert main(['framework', 'catalogue']) == 0
    assert 'Wave to level 1' in capsys.readouterr().out


def test_v27_and_v28_patterns_have_one_canonical_identity_and_control_binding():
    from fssaira.framework import pattern_manifest

    catalogue = load()
    manifest = pattern_manifest(catalogue)
    assert [p.id for p in catalogue.patterns] == [f'P{n}' for n in range(1, 35)]
    assert manifest['levels'][3] == 'Disclosure-governed'
    assert manifest['levels'][4] == 'Composition-safe'
    assert manifest['levels'][5] == 'Evidenced'
    assert all(p.controls and p.verify and p.limits for p in catalogue.patterns)
    assert manifest['pattern_count'] == 34
    # Evidence may be self-reported in an assessment, never inferred from a test locator.
    assert assess(all_status('evidenced'))['assessment_basis'] == 'self-reported control status'


def test_pattern_validation_rejects_drift_and_unsupported_evidence():
    from dataclasses import replace

    catalogue = load()
    first = catalogue.patterns[0]
    bad = replace(first, controls=('MISSING-1',), verify=('tests/missing.py::test_missing',),
                  codes=('MADE_UP_CODE',), scope='production-proven', limits='')
    problems = '\n'.join(validate(replace(catalogue, patterns=(bad, *catalogue.patterns[1:]))))
    for message in ('unknown operational control', 'test missing', 'not registered',
                    'unknown evidence scope', 'limits is empty'):
        assert message in problems
    assert 'canonical patterns' in '\n'.join(validate(replace(catalogue, patterns=catalogue.patterns[:-1])))
    assert 'duplicate pattern ids' in '\n'.join(validate(replace(
        catalogue, patterns=(*catalogue.patterns, first))))


def test_generated_pattern_guide_cannot_drift_from_the_catalogue():
    from fssaira.framework import render_patterns

    assert (ROOT / 'docs/framework/PATTERNS.md').read_text() == render_patterns()


def test_cli_exports_patterns_and_checks_both_generated_guides(tmp_path, capsys):
    import json

    output = tmp_path / 'patterns.json'
    assert main(['framework', 'patterns', '--output', str(output)]) == 0
    assert json.loads(output.read_text())['pattern_count'] == 34
    assert main(['framework', 'patterns']) == 0
    assert 'Trust by Construction' in capsys.readouterr().out
    controls, patterns = tmp_path / 'CONTROLS.md', tmp_path / 'PATTERNS.md'
    args = ['framework', 'render', '--path', str(controls), '--patterns-path', str(patterns)]
    assert main(args) == 0
    assert main([*args, '--check']) == 0
    patterns.write_text('stale V28 numbering')
    assert main([*args, '--check']) == 2
