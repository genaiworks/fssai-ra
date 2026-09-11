from fssaira.profiles import ApplicationProfile
from fssaira.race import run_replay_race


def test_32_simultaneous_replays_commit_one_mutation_and_one_evidence_pair():
    report = run_replay_race(
        ApplicationProfile.load("profiles/student_support.yaml"), callers=32
    )

    assert report.passed
    assert report.executions_returned == 32
    assert report.replayed == 31
    assert report.mutations == 1
    assert report.distinct_receipts == 1
    assert report.intent_records == report.outcome_records == 1
    assert report.evidence_valid


def test_race_report_states_its_narrow_bounds():
    report = run_replay_race(
        ApplicationProfile.load("profiles/student_support.yaml"), callers=4
    )

    assert "one process" in report.bounds
    assert "not a distributed" in report.bounds


def test_replay_race_uses_the_supplied_domain_transition():
    report = run_replay_race(ApplicationProfile.load("profiles/template.yaml"), callers=4)
    assert report.passed
