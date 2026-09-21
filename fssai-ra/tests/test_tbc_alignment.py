"""Make the user-supplied Word specification an explicit CI claim surface."""

import importlib.util
from pathlib import Path

import pytest


def test_v11_specification_bindings_and_inventory_are_current():
    path = Path(__file__).resolve().parents[1] / 'scripts/check_tbc_alignment.py'
    spec = importlib.util.spec_from_file_location('check_tbc_alignment', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.check()['passed']


def test_word_alignment_rejects_source_and_metric_drift(tmp_path):
    import json
    import shutil

    import pytest

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('check_tbc_alignment', root / 'scripts/check_tbc_alignment.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Reuse implementation source read-only; mutate only a temporary claim surface.
    for folder in ('src', 'tests', 'profiles'):
        (tmp_path / folder).symlink_to(root / folder, target_is_directory=True)
    (tmp_path / 'paper').mkdir()
    shutil.copytree(root / 'paper/tbc-v11', tmp_path / 'paper/tbc-v11')
    (tmp_path / 'evaluation/results').mkdir(parents=True)
    summary = root / 'evaluation/results/v1.0.0-summary.json'
    figures = json.loads(summary.read_text())
    figures['figures']['domain_pack_scenarios_contained'] -= 1
    (tmp_path / 'evaluation/results/v1.0.0-summary.json').write_text(json.dumps(figures))
    with pytest.raises(ValueError, match='figures differ'):
        module.check(tmp_path)
    paper = tmp_path / 'paper/tbc-v11/TBC_v11.docx'
    paper.write_bytes(paper.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='Paper changed'):
        module.check(tmp_path)


pytestmark = pytest.mark.manuscript
