"""The instrument computes the preregistered quantities and refuses the claim."""
import pytest

from fssaira.institutional_eval import (
    INSTITUTIONAL,
    SYNTHETIC,
    Dataset,
    DecisionRecord,
    InstitutionalStudy,
    Preregistration,
    reference_preregistration,
)


def prereg(**overrides):
    fields = {
        'title': 'study', 'hypotheses': ('H1',), 'primary_outcome': 'task_completion',
        'secondary_outcomes': ('reviewer_overturn',),
        'subgroup_attributes': ('campus',), 'minimum_sample': 10, 'minimum_cell': 4,
        'analysis_plan': 'two-arm comparison, alpha 0.05'}
    fields.update(overrides)
    return Preregistration(**fields)


def records(n, *, campus='north', approved=True, eligible=True, overturned=False):
    return [DecisionRecord(f'{campus}-{i}', completed=True, approved=approved,
                           overturned=overturned, eligible=eligible,
                           seconds_to_decision=float(60 + i),
                           attributes={'campus': campus})
            for i in range(n)]


def dataset(records_, provenance=INSTITUTIONAL):
    return Dataset(provenance, tuple(records_), description='test')


# -- the refusals -----------------------------------------------------------


def test_synthetic_data_yields_measurements_but_never_conclusions():
    study = InstitutionalStudy(prereg())
    report = study.analyse(dataset(records(20), SYNTHETIC))
    assert report['utility']['task_completion']['value'] == 1.0
    assert report['conclusions_permitted'] is False
    assert any('synthetic' in refusal for refusal in report['refusals'])


def test_an_underpowered_sample_is_refused_by_name():
    report = InstitutionalStudy(prereg()).analyse(dataset(records(5)))
    assert report['conclusions_permitted'] is False
    assert any('below the preregistered minimum' in r for r in report['refusals'])


def test_an_analysis_that_departs_from_the_plan_is_exploratory():
    report = InstitutionalStudy(prereg()).analyse(
        dataset(records(20)), analysis_plan='whatever looked interesting afterwards')
    assert report['analysis_plan_followed'] is False
    assert report['conclusions_permitted'] is False
    assert any('exploratory' in r for r in report['refusals'])


def test_institutional_data_without_an_approval_reference_is_refused():
    report = InstitutionalStudy(prereg()).analyse(dataset(records(20)))
    assert any('approval reference' in r for r in report['refusals'])


def test_a_properly_approved_and_powered_study_permits_conclusions():
    study = InstitutionalStudy(prereg(approval_reference='REC-2026-14'))
    report = study.analyse(dataset(records(20)))
    assert report['conclusions_permitted'] is True
    assert report['refusals'] == []


def test_refusals_accumulate_rather_than_short_circuit():
    report = InstitutionalStudy(prereg()).analyse(
        dataset(records(3), SYNTHETIC), analysis_plan='different')
    assert len(report['refusals']) >= 3


# -- the measurements -------------------------------------------------------


def test_utility_reports_completion_overturn_and_time_with_denominators():
    mixed = records(10) + records(10, campus='south', overturned=True)
    report = InstitutionalStudy(prereg(approval_reference='REC-1')).analyse(dataset(mixed))
    utility = report['utility']
    assert utility['task_completion']['n'] == 20
    assert utility['reviewer_overturn']['value'] == 0.5
    low, high = utility['reviewer_overturn']['interval']
    assert low < 0.5 < high
    assert utility['seconds_to_decision']['median'] is not None


def test_overturn_is_reported_beside_completion_so_rubber_stamping_shows():
    """Completion alone would look identical in both of these."""
    careful = InstitutionalStudy(prereg(approval_reference='R')).analyse(
        dataset(records(20)))
    rubber = InstitutionalStudy(prereg(approval_reference='R')).analyse(
        dataset(records(20, overturned=True)))
    assert (careful['utility']['task_completion']['value']
            == rubber['utility']['task_completion']['value'])
    assert (careful['utility']['reviewer_overturn']['value']
            < rubber['utility']['reviewer_overturn']['value'])


# -- fairness ---------------------------------------------------------------


def test_subgroup_rates_and_the_gap_are_reported_together():
    mixed = records(10, campus='north') + records(10, campus='south', approved=False)
    report = InstitutionalStudy(prereg(approval_reference='R')).analyse(dataset(mixed))
    fairness = report['fairness']['campus']
    assert set(fairness['groups']) == {'north', 'south'}
    assert fairness['gaps']['selection_rate_gap'] == 1.0
    assert fairness['gaps']['equal_opportunity_gap'] == 1.0


def test_a_group_below_the_cell_minimum_is_withheld_not_estimated():
    mixed = records(10, campus='north') + records(2, campus='island')
    report = InstitutionalStudy(prereg(approval_reference='R')).analyse(dataset(mixed))
    fairness = report['fairness']['campus']
    assert 'island' not in fairness['groups']
    assert fairness['withheld_groups'] == ['island']
    assert fairness['withheld_reason']


def test_a_withheld_group_does_not_enter_the_gap():
    mixed = records(10, campus='north') + records(2, campus='island', approved=False)
    report = InstitutionalStudy(prereg(approval_reference='R')).analyse(dataset(mixed))
    # Only one reportable group remains, so no gap is claimed at all.
    assert report['fairness']['campus']['gaps']['selection_rate_gap'] is None


def test_equal_opportunity_uses_eligible_cases_only():
    eligible = records(10, campus='north', eligible=True)
    ineligible = records(10, campus='south', eligible=False, approved=False)
    report = InstitutionalStudy(prereg(approval_reference='R')).analyse(
        dataset(eligible + ineligible))
    fairness = report['fairness']['campus']
    assert 'north' in fairness['true_positive_rate']
    # South has no eligible cases, so no true-positive rate is invented for it.
    assert 'south' not in fairness['true_positive_rate']
    assert fairness['gaps']['equal_opportunity_gap'] is None


def test_records_missing_the_subgroup_attribute_are_simply_absent():
    anonymous = [DecisionRecord(f'a-{i}', True, True, False, True, 30.0, {})
                 for i in range(10)]
    report = InstitutionalStudy(prereg(approval_reference='R')).analyse(
        dataset(records(10) + anonymous))
    assert set(report['fairness']['campus']['groups']) == {'north'}


def test_reporting_rules_forbid_cherry_picking_one_measure():
    report = InstitutionalStudy(prereg(approval_reference='R')).analyse(dataset(records(20)))
    assert any('reported together' in rule for rule in report['reporting_rules'])
    assert any('re-identification' in rule for rule in report['reporting_rules'])


# -- the preregistration itself --------------------------------------------


def test_the_digest_changes_when_the_plan_changes():
    assert prereg().digest != prereg(analysis_plan='a different plan').digest
    assert prereg().digest != prereg(minimum_sample=400).digest
    assert prereg().digest == prereg().digest


def test_a_preregistration_needs_hypotheses_an_outcome_and_a_plan():
    for bad in ({'hypotheses': ()}, {'primary_outcome': ''}, {'analysis_plan': '  '},
                {'minimum_sample': 0}, {'minimum_cell': 0},
                {'minimum_sample': 5, 'minimum_cell': 10}):
        with pytest.raises(ValueError):
            prereg(**bad)


def test_the_published_reference_preregistration_is_complete_and_unapproved():
    published = reference_preregistration()
    assert len(published.hypotheses) >= 4
    assert published.minimum_sample >= 100
    assert published.subgroup_attributes
    # No institution has approved it, and the artefact says so rather than
    # implying a study took place.
    assert published.approval_reference == ''
    assert published.digest


def test_an_unknown_provenance_is_rejected():
    with pytest.raises(ValueError):
        Dataset('vibes', ())


def test_a_record_needs_an_identifier_and_a_nonnegative_time():
    with pytest.raises(ValueError):
        DecisionRecord('', True, True, False, True, 1.0)
    with pytest.raises(ValueError):
        DecisionRecord('a', True, True, False, True, -1.0)
