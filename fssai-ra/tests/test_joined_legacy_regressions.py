from fssaira.education_world import EducationWorld
from fssaira.governed_request import run_governed_request


def test_legacy_driver_cannot_select_unassigned_student():
    w = EducationWorld()
    trace = run_governed_request(w, student='stu-b7c2')
    assert trace.outcome.startswith('DENIED')
    assert not w.register.write_log
    assert not w.observed.model_inputs
    assert not w.observed.released


def test_legacy_driver_does_not_treat_requested_grade_as_evidence():
    w = EducationWorld()
    trace = run_governed_request(w, target_grade='grade:A')
    assert trace.outcome.startswith('DENIED')
    assert not w.register.write_log
    assert not w.observed.released
