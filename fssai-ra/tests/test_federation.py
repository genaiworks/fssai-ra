"""Authority across services, evidence no one custodian owns, and a gate that
will not promote a deployment on its own say-so."""
import pytest

from fssaira.federation import (
    PROMOTION_REQUIREMENTS,
    Attestation,
    FederatedGrant,
    FederationDenied,
    FederationPeer,
    PromotionEvidence,
    PromotionGate,
    WitnessSet,
)

NOW = 1_000_000.0
ISSUER_KEY = b'issuer-shared-secret'

REGISTRY_CEILING = {
    'resources': frozenset({'campus/s1', 'campus/s2'}),
    'operations': frozenset({'read_record', 'propose_correction'}),
}


def peer(service='registry', ceiling=None, clock=lambda: NOW):
    return FederationPeer(service=service, ceiling=ceiling or REGISTRY_CEILING,
                          keys={'tutoring': ISSUER_KEY}, clock=clock)


def grant(**overrides):
    fields = {
        'issuer': 'tutoring', 'audience': 'registry', 'task': 'correction-1',
        'scope': {'resources': frozenset({'campus/s1'}),
               'operations': frozenset({'read_record'})},
        'depth': 2, 'expires': NOW + 60, 'nonce': 'n-1'}
    fields.update(overrides)
    return FederatedGrant(**fields)


def signed(**overrides):
    item = grant(**overrides)
    return item, item.signature(ISSUER_KEY)


# -- federated authority ----------------------------------------------------


def test_a_valid_grant_yields_only_what_both_sides_hold():
    effective = peer().accept(*signed())
    assert effective == {'resources': frozenset({'campus/s1'}),
                         'operations': frozenset({'read_record'})}


def test_a_grant_cannot_teach_a_service_a_capability_it_does_not_have():
    """Intersection, never union. This is the whole federation rule."""
    narrow = peer(ceiling={'resources': frozenset({'campus/s1'}),
                           'operations': frozenset({'read_record'})})
    effective = narrow.accept(*signed(scope={
        'resources': frozenset({'campus/s1', 'campus/s2'}),
        'operations': frozenset({'read_record'})}))
    assert effective['resources'] == frozenset({'campus/s1'})


def test_a_grant_naming_an_axis_the_service_lacks_is_refused():
    with pytest.raises(FederationDenied) as error:
        peer().accept(*signed(scope={'infrastructure': frozenset({'cluster-admin'})}))
    assert 'AXIS_OUTSIDE_LOCAL_CEILING' in str(error.value)


def test_a_grant_that_intersects_to_nothing_is_refused_rather_than_silently_empty():
    with pytest.raises(FederationDenied) as error:
        peer().accept(*signed(scope={'resources': frozenset({'campus/elsewhere'})}))
    assert 'EMPTY_AFTER_INTERSECTION' in str(error.value)


def test_a_forged_signature_is_refused():
    item, _ = signed()
    with pytest.raises(FederationDenied) as error:
        peer().accept(item, 'f' * 64)
    assert 'BAD_SIGNATURE' in str(error.value)


def test_an_unknown_issuer_is_refused():
    receiver = FederationPeer('registry', REGISTRY_CEILING, keys={}, clock=lambda: NOW)
    with pytest.raises(FederationDenied) as error:
        receiver.accept(*signed())
    assert 'UNKNOWN_ISSUER' in str(error.value)


def test_a_grant_addressed_elsewhere_is_refused_by_this_service():
    with pytest.raises(FederationDenied) as error:
        peer().accept(*signed(audience='billing'))
    assert 'WRONG_AUDIENCE' in str(error.value)


def test_an_expired_grant_is_refused():
    with pytest.raises(FederationDenied) as error:
        peer(clock=lambda: NOW + 3600).accept(*signed())
    assert 'GRANT_EXPIRED' in str(error.value)


def test_a_grant_is_single_use():
    receiver = peer()
    item, signature = signed()
    receiver.accept(item, signature)
    with pytest.raises(FederationDenied) as error:
        receiver.accept(item, signature)
    assert 'GRANT_REPLAYED' in str(error.value)


def test_a_service_cannot_issue_authority_it_does_not_hold():
    with pytest.raises(FederationDenied) as error:
        peer().issue(audience='billing', task='t', depth=1, expires=NOW + 10,
                     nonce='n', key=ISSUER_KEY,
                     scope={'resources': frozenset({'campus/elsewhere'})})
    assert 'BEYOND_CEILING' in str(error.value)


# -- attenuation ------------------------------------------------------------


def test_onward_delegation_narrows_and_never_widens():
    original = grant()
    onward = original.attenuate(
        audience='archive', scope={'resources': frozenset({'campus/s1'})},
        expires=NOW + 30, nonce='n-2')
    assert onward.issuer == 'registry'
    assert onward.depth == original.depth - 1
    assert onward.expires <= original.expires


@pytest.mark.parametrize('scope,expires,code', [
    ({'resources': frozenset({'campus/s1', 'campus/s2'})}, NOW + 30, 'CANNOT_WIDEN'),
    ({'zones': frozenset({'public'})}, NOW + 30, 'CANNOT_ADD_AXIS'),
    ({'resources': frozenset({'campus/s1'})}, NOW + 6000, 'CANNOT_EXTEND_EXPIRY'),
])
def test_delegation_cannot_regain_authority(scope, expires, code):
    with pytest.raises(FederationDenied) as error:
        grant().attenuate(audience='archive', scope=scope, expires=expires, nonce='n-2')
    assert code in str(error.value)


def test_delegation_depth_is_finite():
    with pytest.raises(FederationDenied) as error:
        grant(depth=0).attenuate(audience='archive',
                                 scope={'resources': frozenset({'campus/s1'})},
                                 expires=NOW + 10, nonce='n-2')
    assert 'DEPTH_EXHAUSTED' in str(error.value)


def test_a_service_cannot_issue_a_grant_to_itself():
    with pytest.raises(FederationDenied):
        grant(issuer='registry', audience='registry')


@pytest.mark.parametrize('field,value', [
    ('issuer', 'tutor*'), ('task', ' padded '), ('nonce', ''), ('audience', 'x' * 200),
])
def test_malformed_identifiers_are_refused(field, value):
    with pytest.raises(FederationDenied):
        grant(**{field: value})


def test_a_wildcard_scope_value_is_refused():
    with pytest.raises(FederationDenied):
        grant(scope={'resources': frozenset({'campus/*'})})


# -- witnesses --------------------------------------------------------------


HEAD = 'a' * 64
OTHER_HEAD = 'b' * 64
KEYS = {'registrar': b'k1', 'audit-office': b'k2', 'external-auditor': b'k3'}


def test_one_custodian_is_not_a_witness_set():
    with pytest.raises(FederationDenied):
        WitnessSet({'only-me': b'k'}, threshold=1)
    with pytest.raises(FederationDenied):
        WitnessSet(KEYS, threshold=1)


def test_a_head_needs_the_threshold_before_it_counts_as_attested():
    witnesses = WitnessSet(KEYS, threshold=2)
    witnesses.attest('registrar', 7, HEAD)
    assert not witnesses.attested(7, HEAD)
    witnesses.attest('audit-office', 7, HEAD)
    assert witnesses.attested(7, HEAD)


def test_a_fork_is_detected_and_blocks_attestation():
    """Two witnesses attesting different heads at one sequence is a rewrite."""
    witnesses = WitnessSet(KEYS, threshold=2)
    witnesses.attest('registrar', 7, HEAD)
    witnesses.attest('audit-office', 7, HEAD)
    witnesses.attest('external-auditor', 7, OTHER_HEAD)
    assert witnesses.forks() == ({'sequence': 7, 'heads': sorted([HEAD, OTHER_HEAD])},)
    assert not witnesses.attested(7, HEAD)
    assert witnesses.status(7, HEAD)['attested'] is False


def test_a_witness_cannot_contradict_itself():
    witnesses = WitnessSet(KEYS, threshold=2)
    witnesses.attest('registrar', 7, HEAD)
    with pytest.raises(FederationDenied):
        witnesses.attest('registrar', 7, OTHER_HEAD)


def test_an_unknown_witness_cannot_attest():
    with pytest.raises(FederationDenied):
        WitnessSet(KEYS, threshold=2).attest('stranger', 1, HEAD)


def test_a_forged_attestation_does_not_count():
    witnesses = WitnessSet(KEYS, threshold=2)
    real = witnesses.attest('registrar', 7, HEAD)
    assert witnesses.verify(real)
    assert not witnesses.verify(Attestation('registrar', 7, HEAD, 'f' * 64))
    assert not witnesses.verify(Attestation('stranger', 7, HEAD, real.signature))


def test_a_malformed_head_is_refused():
    with pytest.raises(FederationDenied):
        WitnessSet(KEYS, threshold=2).attest('registrar', 1, 'short')


# -- promotion --------------------------------------------------------------


def ready(**overrides):
    fields = {
        'conformance_passed': True, 'conformance_at': NOW,
        'isolation_qualification': 'production', 'isolation_at': NOW,
        'transport_qualified': True, 'transport_qualification_only': False, 'transport_at': NOW,
        'evidence_attested': True, 'unresolved_effects': 0,
        'evaluated_bundle_digest': 'd1', 'promoted_bundle_digest': 'd1',
        'operator': 'operator-alice'}
    fields.update(overrides)
    return PromotionEvidence(**fields)


def test_a_fully_evidenced_deployment_promotes():
    decision = PromotionGate().evaluate(ready(), now=NOW)
    assert decision['promoted'] and decision['qualification'] == 'production'
    assert decision['missing'] == []
    assert len(decision['requirements']) == len(PROMOTION_REQUIREMENTS)


@pytest.mark.parametrize('overrides,expected', [
    ({'conformance_passed': False}, 'conformance'),
    ({'isolation_qualification': 'reference'}, 'isolation'),
    ({'transport_qualification_only': True}, 'transport'),
    ({'transport_qualified': False}, 'transport'),
    ({'evidence_attested': False}, 'witnesses'),
    ({'unresolved_effects': 3}, 'remote_effects'),
    ({'promoted_bundle_digest': 'd2'}, 'bundle'),
])
def test_each_missing_item_alone_refuses_promotion_and_is_named(overrides, expected):
    decision = PromotionGate().evaluate(ready(**overrides), now=NOW)
    assert not decision['promoted']
    assert any(reason.startswith(expected) for reason in decision['missing'])


def test_loopback_transport_evidence_never_promotes_a_deployment():
    """The harness proves the code path, not the network. The gate knows."""
    decision = PromotionGate().evaluate(
        ready(transport_qualification_only=True), now=NOW)
    assert not decision['promoted']
    assert any('loopback' in reason for reason in decision['missing'])


@pytest.mark.parametrize('field', ['conformance_at', 'isolation_at', 'transport_at'])
def test_stale_evidence_refuses_promotion(field):
    decision = PromotionGate().evaluate(ready(**{field: NOW - 200_000}), now=NOW)
    assert not decision['promoted']
    assert any('old' in reason for reason in decision['missing'])


def test_promotion_requires_a_named_operator():
    with pytest.raises(FederationDenied):
        ready(operator='  ')


def test_require_raises_with_every_reason():
    with pytest.raises(FederationDenied) as error:
        PromotionGate().require(
            ready(conformance_passed=False, evidence_attested=False), now=NOW)
    message = str(error.value)
    assert 'conformance' in message and 'witnesses' in message


def test_this_repository_cannot_promote_itself(tmp_path):
    """An end-to-end honesty check across three of the new modules."""
    from fssaira.federation import PromotionGate as Gate
    from fssaira.integration.transport_harness import LoopbackTLSServer
    from fssaira.isolation import probe_host

    isolation = probe_host(operator='ci', control_store=tmp_path / 'missing.db')
    with LoopbackTLSServer(tmp_path) as server:
        evidence = server.transport().fetch(server.url(), ('127.0.0.1',))

    decision = Gate().evaluate(PromotionEvidence(
        conformance_passed=True, conformance_at=NOW,
        isolation_qualification=isolation.qualification(),
        isolation_at=isolation.attribution.measured_at,
        transport_qualified=True,
        transport_qualification_only=evidence.qualification_only,
        transport_at=NOW,
        evidence_attested=False, unresolved_effects=0,
        evaluated_bundle_digest='d1', promoted_bundle_digest='d1',
        operator='ci'), now=NOW)
    assert not decision['promoted']
    assert decision['qualification'] == 'reference'
