import pytest

from fssaira.integration.messages import ContextRequest, EffectRequest, parse_sdk_request
from fssaira.integration.network import DestinationPolicy
from fssaira.integration.supply import FrozenCatalog, ModelBundle, ToolManifest


def test_versioned_boundary_rejects_model_authority_and_ambiguous_json():
    for raw in ('{"op":"request_context","schema_version":2}',
                '{"op":"request_context","op":"execute_effect"}',
                '{"op":"request_context","principal":"admin"}',
                '{"op":"derive_artifact","text":NaN}'):
        with pytest.raises(ValueError):
            parse_sdk_request(raw)
    assert parse_sdk_request('{"op":"request_context","schema_version":1}') == {'op':'request_context'}
    with pytest.raises(ValueError):
        ContextRequest.parse({'schema_version':1, 'subjects':['../other'], 'fields':['name'], 'purpose':'treatment', 'endpoint':'local'})
    with pytest.raises(ValueError):
        EffectRequest.parse({'schema_version':1, 'operation':'execute_sql', 'resource':'r1', 'expected_version':True,
                             'destination':'recipient', 'context_refs':['ctx1'], 'desired_state':'approved'})


def test_full_model_bundle_changes_when_any_component_changes():
    from dataclasses import replace
    parts = dict.fromkeys(ModelBundle.COMPONENTS, 'a' * 64)
    bundle = ModelBundle.from_dict(parts)
    for key in parts:
        assert replace(bundle, **{key:'b'*64}).digest != bundle.digest
    with pytest.raises(ValueError):
        ModelBundle.from_dict({**parts, 'weights':'model-reported-name'})


def manifest(description='a'*64):
    return ToolManifest('summarize', 'trusted-service', description, 'b'*64, 'c'*64, 'd'*64,
                        power=1, irreversibility=0, effects=frozenset({'protected_read'}))


def test_tool_catalog_frozen_and_risk_derived_from_manifest():
    catalog = FrozenCatalog([manifest()])
    assert catalog.check(manifest()).power == 1
    with pytest.raises(ValueError):
        catalog.check(manifest('e'*64))
    with pytest.raises(ValueError):
        ToolManifest('shell', 'worker', 'a'*64, 'b'*64, 'c'*64, 'd'*64, power=5,
                      irreversibility=4, effects=frozenset({'infrastructure'})).validate_model_exposure()


@pytest.mark.parametrize('url,ips', [
    ('http://example.org/docs/a',['8.8.8.8']),
    ('https://user:secret@example.org/docs/a',['8.8.8.8']),
    ('https://example.org/docs/a',['127.0.0.1']),
    ('https://example.org/docs/a',['169.254.169.254']),
    ('https://example.org/docs/a',['10.0.0.1']),
    ('https://evil.org/docs/a',['8.8.8.8']),
    ('https://example.org/docs/../admin',['8.8.8.8']),
    ('https://example.org/docs/%2e%2e/admin',['8.8.8.8']),
    ('https://example.org/docs/a?secret=payload',['8.8.8.8']),
])
def test_destination_bound_egress_rejects_ssrf_and_hidden_channels(url, ips):
    policy = DestinationPolicy('example.org', ('/docs/',), max_bytes=1000)
    with pytest.raises(ValueError):
        policy.authorize(url, ips, classifications=frozenset())


def test_public_network_requires_public_data_and_pins_resolved_addresses():
    policy = DestinationPolicy('example.org', ('/docs/',), max_bytes=1000)
    approved = policy.authorize('https://example.org/docs/a', ['8.8.8.8'], classifications=frozenset())
    assert approved.addresses == ('8.8.8.8',) and approved.tls_identity == 'example.org'
    with pytest.raises(ValueError):
        policy.authorize('https://example.org/docs/a', ['8.8.8.8'], classifications=frozenset({'health'}))


@pytest.mark.parametrize('path', [
    '/docs/..;/admin', '/docs/%2fadmin', '/docs/%3fsecret', '/docs/%23secret',
    '/docs/%3badmin', '/docs//admin', '/docs/%7f', '/docs/%ff', '/docs/a\x7f',
])
def test_destination_rejects_parser_differential_paths(path):
    policy = DestinationPolicy('example.org', ('/docs/',), max_bytes=1000)
    with pytest.raises(ValueError):
        policy.authorize('https://example.org' + path, ['8.8.8.8'], classifications=frozenset())


def test_destination_preserves_safe_unreserved_encoding_and_mixed_dns_denial():
    policy = DestinationPolicy('example.org', ('/docs/',), max_bytes=1000)
    target = policy.authorize('https://example.org/docs/%61rticle', ['8.8.8.8'], classifications=frozenset())
    assert target.tls_identity == 'example.org'
    with pytest.raises(ValueError):
        policy.authorize(target.url, ['8.8.8.8', '127.0.0.1'], classifications=frozenset())
