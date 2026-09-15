"""Evaluation must not train, and finite episodes must not bootstrap past termination."""
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'scripts/adaptive_attacks.py'
spec = importlib.util.spec_from_file_location('reaudit_adaptive', path)
adaptive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adaptive)


def test_evaluation_does_not_modify_frozen_policy():
    table = {}
    result = adaptive.episode('tabular-q', 99, table)
    assert table == {}
    assert result['termination'] == 'step_limit'
    assert result['outcome']['unsupported_correction'] == 0


def test_terminal_step_does_not_bootstrap_future_reward():
    values = [5.0] * len(adaptive.ACTIONS)
    table = {'0000:1': values, '1000:0': [100.0] * len(adaptive.ACTIONS)}
    result = adaptive.episode('static', 0, table, training=True, steps=1)
    assert result['termination'] == 'step_limit'
    assert values[adaptive.ACTIONS.index('read')] == 3.0
    assert result['trace'][0]['outcome']['effects'] == 0
