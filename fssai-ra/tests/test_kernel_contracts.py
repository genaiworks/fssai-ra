
import pytest

from fssaira.kernel.contracts import (
    CapabilityContract,
    execute_contracts,
    load_contracts,
    resolve_test,
)
from fssaira.kernel.state import EffectState, transition


def contract(test='tests/test_guard.py::test_refusal'):
    return dict(protected_asset='record', permitted_operation='correct', enforcement_point='executor',
                accountable_owner='registrar', failure_test=test, evidence_artifact='audit/refusal.json',
                failure_response='deny and route to registrar')


def test_seven_fields_reject_empty_unknown_and_missing_test(tmp_path):
    (tmp_path/'tests').mkdir()
    (tmp_path/'tests/test_guard.py').write_text('def test_refusal():\n    assert True\n')
    c = CapabilityContract.from_dict(contract(), tmp_path)
    assert c.accountable_owner == 'registrar'
    for field in contract():
        with pytest.raises(ValueError):
            CapabilityContract.from_dict({**contract(), field: ' '}, tmp_path)
    with pytest.raises(ValueError):
        CapabilityContract.from_dict({**contract(), 'auto_approve': True}, tmp_path)
    with pytest.raises(ValueError):
        resolve_test('tests/test_guard.py::test_nonexistent', tmp_path)
    with pytest.raises(ValueError):
        resolve_test('../escape.py::test_refusal', tmp_path)


def test_duplicate_yaml_security_fields_are_rejected(tmp_path):
    p = tmp_path/'contract.yaml'
    p.write_text('capabilities:\n  x:\n    protected_asset: first\n    protected_asset: second\n')
    with pytest.raises(ValueError, match='duplicate'):
        load_contracts(p, tmp_path)


def test_actual_execution_distinguishes_pass_failure_and_skip(tmp_path):
    tests = tmp_path/'tests'
    tests.mkdir()
    path = tests/'test_guard.py'
    path.write_text('import pytest\ndef test_refusal():\n    assert 1 == 1\n')
    controls = {'correct': CapabilityContract.from_dict(contract(), tmp_path)}
    report = execute_contracts(controls, tmp_path, tmp_path/'run')
    assert report['claims'][0]['status'] == 'machine_verified'
    assert report['passed']
    path.write_text('import pytest\ndef test_refusal():\n    pytest.skip("not exercised")\n')
    report = execute_contracts(controls, tmp_path, tmp_path/'skip')
    assert report['claims'][0]['status'] == 'unverified'
    assert not report['passed']
    path.write_text('def test_refusal():\n    assert False\n')
    report = execute_contracts(controls, tmp_path, tmp_path/'fail')
    assert report['claims'][0]['status'] == 'unverified'
    assert not report['passed']


def test_uncertain_effect_cannot_be_retried_or_declared_committed():
    assert transition(EffectState.APPROVED, EffectState.DISPATCHED) == EffectState.DISPATCHED
    assert transition(EffectState.DISPATCHED, EffectState.UNCERTAIN) == EffectState.UNCERTAIN
    for target in (EffectState.PENDING, EffectState.DISPATCHED, EffectState.COMMITTED):
        with pytest.raises(ValueError):
            transition(EffectState.UNCERTAIN, target)
    with pytest.raises(ValueError):
        transition(EffectState.UNCERTAIN, EffectState.RECONCILED)
    assert transition(EffectState.UNCERTAIN, EffectState.RECONCILED, evidence='external-status-receipt') == EffectState.RECONCILED
