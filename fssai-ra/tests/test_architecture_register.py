import importlib.util
from pathlib import Path


def test_architecture_register_keeps_all_controls_and_open_gaps():
    path = Path(__file__).resolve().parents[1] / 'scripts/check_architecture.py'
    spec = importlib.util.spec_from_file_location('architecture_check', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.check()
    assert result['controls'] == 109
    assert result['statuses']['not-implemented'] > 0
    assert result['statuses']['deployment-required'] > 0
