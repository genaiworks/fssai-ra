"""The developer example must demonstrate outcomes, not print invented success."""
import importlib.util
from pathlib import Path


def test_developer_demo_executes_transport_and_settlement():
    path = Path(__file__).resolve().parents[1] / 'scripts/developer_security_demo.py'
    spec = importlib.util.spec_from_file_location('developer_security_demo', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run()
    assert result['exact_artifact_bytes'] is True
    assert result['digest_mismatch'] == 'ARTIFACT_DIGEST_MISMATCH'
    assert result['effect_states'] == ['UNCERTAIN', 'UNCERTAIN', 'CONFIRMED']
    assert result['dependent_work_blocked_while_pending'] is True
    assert result['provider_submissions'] == 1
    assert result['qualification'] == 'local-reference'
