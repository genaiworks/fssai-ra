"""Isolation is measured, and an unmeasured host never qualifies."""
import os
import stat

import pytest

from fssaira.isolation import (
    METADATA_ENDPOINTS,
    NOT_MEASURABLE,
    REQUIREMENTS,
    SATISFIED,
    SERVICE_ACCOUNT_TOKEN,
    VIOLATED,
    HostAttribution,
    HostProbe,
    IsolationGate,
    IsolationNotQualified,
    IsolationReport,
    Measurement,
    probe_host,
)

NOW = 1_000_000.0


def isolated_probe(tmp_path, **overrides):
    """A host that satisfies every required property."""
    store = tmp_path / 'control.db'
    store.write_bytes(b'')
    store.chmod(0o600)
    code = tmp_path / 'enforcement'
    code.mkdir(exist_ok=True)
    code.chmod(0o755)

    def refuse(address, timeout):
        raise ConnectionRefusedError(f'no route to {address[0]}')

    defaults = {
        'control_store': store,
        'enforcement_root': code,
        'agent_uid': os.getuid() + 1,
        'agent_environ': {'PATH': '/usr/bin'},
        'egress_canary': ('198.51.100.7', 443),
        'connect': refuse,
        'path_exists': lambda p: False,
        'seccomp_status': lambda: '2',
    }
    defaults.update(overrides)
    return HostProbe(**defaults)


def report_for(probe, *, now=NOW):
    return IsolationReport(
        attribution=HostAttribution('operator-alice', 'host-1', now),
        measurements=probe.measure(),
        platform='test-platform',
    )


def test_a_fully_isolated_host_qualifies_for_production(tmp_path):
    report = report_for(isolated_probe(tmp_path))
    assert report.qualification(NOW) == 'production'
    assert report.blocking_reasons(NOW) == ()
    assert all(m.outcome == SATISFIED for m in report.measurements)


@pytest.mark.parametrize('requirement', [r.id for r in REQUIREMENTS if r.required])
def test_every_required_property_alone_blocks_production(tmp_path, requirement):
    """One violated requirement is enough. There is no partial credit."""
    report = report_for(isolated_probe(tmp_path))
    broken = tuple(
        Measurement(m.requirement, VIOLATED, m.method, 'injected failure')
        if m.requirement == requirement else m
        for m in report.measurements
    )
    degraded = IsolationReport(report.attribution, broken, report.platform)
    assert degraded.qualification(NOW) == 'reference'
    assert any(requirement in reason for reason in degraded.blocking_reasons(NOW))


def test_an_unmeasurable_requirement_is_not_treated_as_satisfied(tmp_path):
    # No egress canary declared: default-deny cannot be measured, so it is open.
    report = report_for(isolated_probe(tmp_path, egress_canary=None))
    measurement = report.by_id('egress_default_deny')
    assert measurement.outcome == NOT_MEASURABLE
    assert report.qualification(NOW) == 'reference'
    assert any('not measurable' in reason for reason in report.blocking_reasons(NOW))


def test_a_never_measured_requirement_blocks_and_is_named(tmp_path):
    report = report_for(isolated_probe(tmp_path))
    partial = IsolationReport(
        report.attribution,
        tuple(m for m in report.measurements if m.requirement != 'no_standing_credentials'),
        report.platform)
    assert partial.unmeasured == ('no_standing_credentials',)
    assert partial.qualification(NOW) == 'reference'


def test_stale_evidence_does_not_qualify_however_good_it_was(tmp_path):
    report = report_for(isolated_probe(tmp_path))
    assert report.qualification(NOW) == 'production'
    later = NOW + report.max_age_seconds + 1
    assert report.qualification(later) == 'reference'
    assert any('old' in reason for reason in report.blocking_reasons(later))


def test_reachable_cloud_metadata_is_a_violation(tmp_path):
    reached = []

    def connect(address, timeout):
        reached.append(address)
        if address == METADATA_ENDPOINTS[0]:
            return None
        raise ConnectionRefusedError('refused')

    report = report_for(isolated_probe(tmp_path, connect=connect))
    measurement = report.by_id('no_ambient_cloud_metadata')
    assert measurement.outcome == VIOLATED
    assert '169.254.169.254' in measurement.detail
    assert report.qualification(NOW) == 'reference'


def test_a_readable_service_account_token_is_a_violation(tmp_path):
    probe = isolated_probe(
        tmp_path,
        path_exists=lambda p: p == SERVICE_ACCOUNT_TOKEN,
        path_readable=lambda p: True,
    )
    assert probe.no_service_account_token().outcome == VIOLATED


def test_a_present_but_unreadable_token_is_satisfied(tmp_path):
    probe = isolated_probe(
        tmp_path,
        path_exists=lambda p: p == SERVICE_ACCOUNT_TOKEN,
        path_readable=lambda p: False,
    )
    assert probe.no_service_account_token().outcome == SATISFIED


@pytest.mark.parametrize('variable', [
    'AWS_SECRET_ACCESS_KEY', 'KUBERNETES_SERVICE_HOST', 'OPENAI_API_KEY',
    'GITHUB_TOKEN', 'DATABASE_URL',
])
def test_standing_credentials_in_the_agent_environment_are_a_violation(tmp_path, variable):
    probe = isolated_probe(tmp_path, agent_environ={'PATH': '/usr/bin', variable: 'x'})
    measurement = probe.no_standing_credentials()
    assert measurement.outcome == VIOLATED
    assert variable in measurement.detail


def test_sharing_a_uid_with_the_agent_violates_two_requirements(tmp_path):
    probe = isolated_probe(tmp_path, agent_uid=os.getuid())
    assert probe.distinct_runtime_identity().outcome == VIOLATED
    assert probe.control_store_not_writable().outcome == VIOLATED
    assert probe.code_immutable_to_agent().outcome == VIOLATED


def test_a_world_writable_control_store_is_a_violation(tmp_path):
    store = tmp_path / 'loose.db'
    store.write_bytes(b'')
    store.chmod(0o666)
    probe = isolated_probe(tmp_path, control_store=store)
    measurement = probe.control_store_not_writable()
    assert measurement.outcome == VIOLATED
    assert stat.filemode(store.stat().st_mode) in measurement.detail


def test_an_undeclared_egress_destination_that_answers_is_a_violation(tmp_path):
    probe = isolated_probe(tmp_path, connect=lambda address, timeout: None)
    assert probe.egress_default_deny().outcome == VIOLATED


def test_the_advisory_sandbox_requirement_does_not_block_promotion(tmp_path):
    report = report_for(isolated_probe(tmp_path, seccomp_status=lambda: '0'))
    assert report.by_id('kernel_sandbox_active').outcome == VIOLATED
    # Advisory, so it is reported but does not by itself deny production.
    assert report.qualification(NOW) == 'production'


def test_the_gate_refuses_and_explains(tmp_path):
    report = report_for(isolated_probe(tmp_path, agent_uid=os.getuid()))
    with pytest.raises(IsolationNotQualified) as error:
        IsolationGate().check(report, now=NOW)
    assert 'distinct_runtime_identity' in str(error.value)
    # The teaching setting still refuses to call it production.
    assert IsolationGate(strict=False).check(report, now=NOW) == 'reference'


def test_evidence_without_an_operator_is_not_evidence():
    with pytest.raises(ValueError):
        HostAttribution('', 'host-1', NOW)
    with pytest.raises(ValueError):
        HostAttribution('operator-alice', 'host-1', 0)


def test_this_repository_host_is_honestly_reported_as_reference(tmp_path):
    """The development host must never print 'production'.

    This is the check that keeps the repository honest about itself: the probe
    runs for real, against this machine, with no injected results.
    """
    report = probe_host(operator='ci', control_store=tmp_path / 'missing.db')
    assert report.qualification() == 'reference'
    assert report.blocking_reasons()
    payload = report.to_dict()
    assert payload['qualification'] == 'reference'
    assert payload['limits']


def test_the_report_serialises_every_measurement(tmp_path):
    payload = report_for(isolated_probe(tmp_path)).to_dict(NOW)
    assert len(payload['measurements']) == len(REQUIREMENTS)
    assert payload['summary']['required_total'] == sum(1 for r in REQUIREMENTS if r.required)
    assert 'isolation' in report_for(isolated_probe(tmp_path)).render()


def test_an_unknown_requirement_or_outcome_is_rejected():
    with pytest.raises(ValueError):
        Measurement('no_such_requirement', SATISFIED, 'method')
    with pytest.raises(ValueError):
        Measurement('egress_default_deny', 'probably_fine', 'method')
