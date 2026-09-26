"""FERPA release table and the stricter minors mandate: every row is a test."""
from datetime import date

import pytest

from fssaira.ferpa import (
    DIRECTORY,
    NON_DIRECTORY,
    POLICY_TABLE,
    AmendmentCase,
    Consent,
    Request,
    Student,
    decide,
    rights_holder,
)

MINOR = Student('s-minor', age=15)
ADULT = Student('s-adult', age=19, postsecondary=True)
GRADES = frozenset({'grades'})


def req(requester, cls=NON_DIRECTORY, **kw):
    kw.setdefault('recipient', 'registrar-archive')
    return Request(requester=requester, record_class=cls, records=kw.pop('records', GRADES),
                   purpose=kw.pop('purpose', 'grade-correction'), **kw)


def test_rights_transfer_at_eighteen_or_postsecondary():
    assert rights_holder(MINOR) == 'parent'
    assert rights_holder(ADULT) == 'student'
    assert rights_holder(Student('early', age=17, postsecondary=True)) == 'student'


def test_holders_read_their_own_records_with_the_45_day_deadline():
    d = decide(ADULT, req('student'))
    assert d.allowed and d.code == 'FERPA_ACCESS_RIGHT' and '45 days' in d.obligations[0]
    assert decide(MINOR, req('parent')).allowed
    assert decide(MINOR, req('student')).code == 'FERPA_NOT_RIGHTS_HOLDER'


def test_parents_of_eligible_students_need_the_dependency_exception():
    assert decide(ADULT, req('parent')).code == 'FERPA_RIGHTS_TRANSFERRED'
    dependent = Student('s', age=19, postsecondary=True, tax_dependent_of_requester=True)
    d = decide(dependent, req('parent'))
    assert d.allowed and d.record_required


def test_directory_information_respects_opt_out():
    assert decide(ADULT, req('third_party', DIRECTORY)).code == 'FERPA_DIRECTORY'
    opted = Student('s', age=19, postsecondary=True, directory_opt_out=True)
    assert decide(opted, req('third_party', DIRECTORY)).code == 'FERPA_CONSENT_REQUIRED'


def test_school_officials_need_legitimate_interest():
    assert decide(ADULT, req('school_official')).code == 'FERPA_NO_LEGITIMATE_INTEREST'
    d = decide(ADULT, req('school_official', legitimate_educational_interest=True))
    assert d.allowed and not d.record_required


def test_transfer_and_emergency_paths_are_recorded():
    assert decide(ADULT, req('other_school', student_enrolling=True)).record_required
    assert decide(ADULT, req('emergency')).code == 'FERPA_THREAT_NOT_ARTICULATED'
    d = decide(ADULT, req('emergency', articulable_threat='credible threat of self-harm'))
    assert d.allowed and d.record_required and '99.32' in d.obligations[0]


def test_consent_must_match_holder_records_recipient_and_purpose():
    good = Consent('student', GRADES, 'grade-correction', 'registrar-archive', date(2026, 9, 1))
    assert decide(ADULT, req('third_party', consent=good)).code == 'FERPA_CONSENT'
    for bad in (Consent('parent', GRADES, 'grade-correction', 'registrar-archive', date(2026, 9, 1)),
                Consent('student', frozenset({'other'}), 'grade-correction', 'registrar-archive',
                        date(2026, 9, 1)),
                Consent('student', GRADES, 'marketing', 'registrar-archive', date(2026, 9, 1)),
                Consent('student', GRADES, 'grade-correction', 'vendor', date(2026, 9, 1)),
                Consent('student', GRADES, 'grade-correction', 'registrar-archive',
                        date(2026, 9, 1), revoked=True)):
        assert decide(ADULT, req('third_party', consent=bad)).code == 'FERPA_CONSENT_INVALID'
    assert decide(ADULT, req('third_party')).code == 'FERPA_CONSENT_REQUIRED'
    assert decide(ADULT, req('other')).code == 'FERPA_PATH_NOT_MODELLED'


def test_minors_get_dual_approval_short_grants_and_named_recipients():
    consent = Consent('parent', GRADES, 'grade-correction', 'registrar-archive', date(2026, 9, 1))
    one = req('third_party', consent=consent, approvers=('a',))
    d = decide(MINOR, one)
    assert d.code == 'MINOR_DUAL_APPROVAL_REQUIRED' and d.source == 'institution'
    same_twice = req('third_party', consent=consent, approvers=('a', 'a'))
    assert decide(MINOR, same_twice).code == 'MINOR_DUAL_APPROVAL_REQUIRED'
    long = req('third_party', consent=consent, approvers=('a', 'b'), grant_days=14)
    assert decide(MINOR, long).code == 'MINOR_GRANT_TOO_LONG'
    anyone = req('third_party', consent=consent, approvers=('a', 'b'), recipient='*')
    assert decide(MINOR, anyone).code == 'MINOR_RECIPIENT_NOT_NAMED'
    assert decide(MINOR, req('third_party', consent=consent, approvers=('a', 'b'))).allowed
    # The same request for an adult needs one approver.
    adult_consent = Consent('student', GRADES, 'grade-correction', 'registrar-archive',
                            date(2026, 9, 1))
    assert decide(ADULT, req('third_party', consent=adult_consent, approvers=('a',))).allowed


def test_contested_portions_travel_with_the_students_statement():
    disputed = Student('s', age=20, postsecondary=True, contested_portions=GRADES)
    ask = req('school_official', legitimate_educational_interest=True)
    assert decide(disputed, ask).code == 'FERPA_STATEMENT_MISSING'
    with_statement = req('school_official', legitimate_educational_interest=True,
                         includes_statements=True)
    assert decide(disputed, with_statement).allowed


def test_amendment_deadlines_and_table_coverage():
    case = AmendmentCase(received=date(2026, 9, 1))
    assert case.decision_due() == date(2026, 10, 1)
    assert case.hearing_due(date(2026, 10, 2)) == date(2026, 11, 16)
    assert len(case.after_refusal()) == 3
    assert {row[2] for row in POLICY_TABLE} == {'law', 'institution'}
    with pytest.raises(ValueError):
        decide(ADULT, req('robot'))
