"""Keep the public-incident reading bound to executed tests and honest wording.

The map is an architectural disposition of a published disclosure. It is not an
incident reconstruction, and no entry may claim the incident was preventable.
"""
import json
from pathlib import Path

import pytest

from fssaira.kernel.contracts import resolve_test

ROOT = Path(__file__).resolve().parents[1]
MAP = json.loads((ROOT / 'audit/incident-map.json').read_text())
STAGES = MAP['stages']
FORBIDDEN = ('would have prevented', 'prevents the incident', 'proves', 'guarantees', 'certified')


def test_map_declares_its_dispositions_and_sources():
    assert set(MAP['dispositions']) == {'mediated', 'deployment', 'out_of_scope'}
    assert len(MAP['sources']) >= 3 and MAP['scope']
    assert len({stage['id'] for stage in STAGES}) == len(STAGES)


@pytest.mark.parametrize('stage', STAGES, ids=lambda s: s['id'])
def test_every_stage_is_dispositioned_and_evidence_backed(stage):
    assert set(stage) >= {'id', 'reported', 'disposition', 'control', 'note'}
    assert stage['disposition'] in MAP['dispositions']
    if stage['disposition'] == 'mediated':
        resolve_test(stage['test'], ROOT)
    elif stage['disposition'] == 'out_of_scope':
        assert 'test' not in stage, 'an out-of-scope stage must not imply local evidence'


@pytest.mark.parametrize('stage', STAGES, ids=lambda s: s['id'])
def test_no_stage_overclaims(stage):
    text = ' '.join(str(value) for value in stage.values()).lower()
    assert not any(phrase in text for phrase in FORBIDDEN)


def test_map_keeps_the_unmediated_stages_visible():
    unmediated = [s['id'] for s in STAGES if s['disposition'] != 'mediated']
    assert unmediated, 'a map with no residual risk is a marketing document'


NON_MEDIATED = [s for s in STAGES if s['disposition'] != 'mediated']


@pytest.mark.parametrize('stage', NON_MEDIATED, ids=lambda s: s['id'])
def test_a_named_precondition_resolves_to_a_real_probe_test(stage):
    """A stage may claim a measurable precondition only with an executed test."""
    if 'measured_precondition' not in stage:
        assert 'precondition_test' not in stage
        return
    resolve_test(stage['precondition_test'], ROOT)
    assert stage['precondition_note']


@pytest.mark.parametrize('stage', NON_MEDIATED, ids=lambda s: s['id'])
def test_measuring_a_precondition_is_never_described_as_mediating_it(stage):
    """Measuring an assumption is not supplying it, and the map must not blur that."""
    assert stage['disposition'] != 'mediated'
    text = (stage.get('precondition_note', '') + ' ' + stage['note']).lower()
    for phrase in ('mediates this stage', 'supplies this property', 'closes this gap'):
        assert phrase not in text


def test_the_map_explains_what_a_precondition_is_and_is_not():
    assert 'does not mediate the' in MAP['preconditions']
    assert any('measured_precondition' in stage for stage in NON_MEDIATED)
