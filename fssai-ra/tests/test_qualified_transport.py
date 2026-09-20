"""The transport contract, exercised against a real TLS handshake.

Every test here opens a socket, completes a handshake and parses a real
response. Nothing is mocked, because the properties being claimed -- pinning,
hostname verification, redirect refusal, wire-level byte ceilings, deadlines --
are exactly the ones a mock would assert into existence.
"""
import ssl

import pytest

from fssaira.integration.network import DestinationPolicy
from fssaira.integration.transport import (
    PROXY_VARIABLES,
    QualifiedTransport,
    RedirectRequiresReauthorization,
    TransportDenied,
    TransportQualification,
)
from fssaira.integration.transport_harness import (
    HARNESS_HOSTNAME,
    LoopbackTLSServer,
    ServerBehaviour,
)

LOOPBACK = ('127.0.0.1',)


@pytest.fixture
def server(tmp_path):
    with LoopbackTLSServer(tmp_path) as running:
        yield running


def serving(tmp_path, behaviour, **kwargs):
    return LoopbackTLSServer(tmp_path, behaviour, **kwargs)


# -- the transfer that should work -----------------------------------------


def test_an_approved_transfer_returns_evidence_of_what_happened(server):
    evidence = server.transport().fetch(server.url(), LOOPBACK)
    assert evidence.status == 200
    assert evidence.pinned_address == '127.0.0.1'
    assert evidence.peer_pin == server.pin
    assert evidence.tls_version in ('TLSv1.2', 'TLSv1.3')
    assert evidence.cipher and evidence.cipher != 'unknown'
    assert evidence.bytes_received == len(ServerBehaviour().body)
    payload = evidence.to_dict()
    assert payload['kind'] == 'transport'
    assert payload['body_sha256']


def test_harness_evidence_is_marked_as_not_production(server):
    evidence = server.transport().fetch(server.url(), LOOPBACK)
    assert evidence.qualification_only is True
    assert evidence.to_dict()['qualification_only'] is True


# -- peer identity ----------------------------------------------------------


def test_a_peer_presenting_a_different_key_is_refused(server):
    wrong = frozenset({'sha256/' + 'A' * 43 + '='})
    with pytest.raises(TransportDenied) as error:
        server.transport(pins=wrong).fetch(server.url(), LOOPBACK)
    assert error.value.code == 'PIN_MISMATCH'


def test_a_certificate_for_another_name_fails_hostname_verification(tmp_path):
    with serving(tmp_path, ServerBehaviour(), hostname='other.invalid') as running:
        policy = DestinationPolicy(
            HARNESS_HOSTNAME, ('/artifacts/',), 4096,
            port=running.port, qualification_only=True)
        transport = QualifiedTransport(
            policy, running.qualification(minimum_tls_version=ssl.TLSVersion.TLSv1_2),
            environ={})
        url = f'https://{HARNESS_HOSTNAME}:{running.port}/artifacts/report.txt'
        with pytest.raises(TransportDenied) as error:
            transport.fetch(url, LOOPBACK)
    assert error.value.code == 'TLS_REJECTED'


def test_an_untrusted_issuer_is_refused(tmp_path):
    with serving(tmp_path, ServerBehaviour()) as running:
        qualification = TransportQualification(
            spki_pins=frozenset({running.pin}),
            minimum_tls_version=ssl.TLSVersion.TLSv1_2,
            trust_store=None,            # the system store, which never signed this leaf
            qualification_only=True)
        transport = QualifiedTransport(running.policy(), qualification, environ={})
        with pytest.raises(TransportDenied) as error:
            transport.fetch(running.url(), LOOPBACK)
    assert error.value.code == 'TLS_REJECTED'


def test_a_tls_version_below_the_declared_floor_is_refused(tmp_path):
    with serving(tmp_path, ServerBehaviour(),
                 maximum_tls_version=ssl.TLSVersion.TLSv1_2) as running:
        transport = QualifiedTransport(
            running.policy(),
            running.qualification(minimum_tls_version=ssl.TLSVersion.TLSv1_3),
            environ={})
        with pytest.raises(TransportDenied) as error:
            transport.fetch(running.url(), LOOPBACK)
    # Either the handshake fails outright or the negotiated version is refused;
    # both are correct, and both must deny.
    assert error.value.code in ('TLS_REJECTED', 'TLS_VERSION_BELOW_FLOOR')


def test_declaring_no_pin_while_requiring_pinning_is_a_configuration_error():
    with pytest.raises(ValueError):
        TransportQualification(spki_pins=frozenset(), require_pinning=True)


def test_tls_11_cannot_be_declared_as_a_floor():
    with pytest.raises(ValueError):
        TransportQualification(spki_pins=frozenset({'sha256/x'}),
                               minimum_tls_version=ssl.TLSVersion.TLSv1_1)


# -- address pinning --------------------------------------------------------


def test_the_connection_uses_the_pinned_address_not_a_resolver(server, monkeypatch):
    """A resolver answer that changes after authorisation must not move us."""
    def forbidden(*args, **kwargs):  # pragma: no cover - fails the test if called
        raise AssertionError('the transport resolved a name instead of using the pin')

    monkeypatch.setattr('socket.getaddrinfo', forbidden)
    evidence = server.transport().fetch(server.url(), LOOPBACK)
    assert evidence.pinned_address == '127.0.0.1'


def test_an_unreachable_pinned_address_is_reported_as_such(tmp_path):
    with serving(tmp_path, ServerBehaviour()) as running:
        policy = DestinationPolicy(
            running.hostname, ('/artifacts/',), 4096,
            port=running.port, qualification_only=True)
        transport = QualifiedTransport(policy, running.qualification(), environ={})
        running.close()
        with pytest.raises(TransportDenied) as error:
            transport.fetch(running.url(), LOOPBACK)
    assert error.value.code in ('PINNED_ADDRESS_UNREACHABLE', 'TLS_REJECTED')


def test_a_public_policy_still_refuses_private_and_loopback_addresses():
    policy = DestinationPolicy('example.org', ('/docs/',), 1000)
    for address in ('127.0.0.1', '10.0.0.5', '169.254.169.254', '::1'):
        with pytest.raises(ValueError):
            policy.authorize('https://example.org/docs/a', (address,),
                             classifications=frozenset())


def test_a_qualification_policy_refuses_anything_but_loopback():
    policy = DestinationPolicy('example.org', ('/docs/',), 1000,
                               port=8443, qualification_only=True)
    with pytest.raises(ValueError):
        policy.authorize('https://example.org:8443/docs/a', ('93.184.216.34',),
                         classifications=frozenset())


def test_a_nonstandard_port_requires_the_qualification_flag():
    with pytest.raises(ValueError):
        DestinationPolicy('example.org', ('/docs/',), 1000, port=8443)


# -- response handling ------------------------------------------------------


def test_a_redirect_is_a_new_authorisation_decision_not_a_followed_hop(tmp_path):
    behaviour = ServerBehaviour(status=302, location='https://elsewhere.invalid/x', body=b'')
    with serving(tmp_path, behaviour) as running, \
            pytest.raises(RedirectRequiresReauthorization) as error:
        running.transport().fetch(running.url(), LOOPBACK)
    assert error.value.location == 'https://elsewhere.invalid/x'
    assert error.value.code == 'REDIRECT_NOT_FOLLOWED'


def test_a_declared_body_over_the_ceiling_is_refused_before_it_is_read(tmp_path):
    with serving(tmp_path, ServerBehaviour(body=b'Z' * 5000)) as running, pytest.raises(TransportDenied) as error:
            running.transport(max_bytes=100).fetch(running.url(), LOOPBACK)
    assert error.value.code == 'BYTE_CEILING_EXCEEDED'


def test_a_peer_that_understates_its_length_cannot_overrun_the_ceiling(tmp_path):
    # Declares 10 bytes, sends far more: the ceiling is enforced on the wire.
    behaviour = ServerBehaviour(body=b'0123456789', overrun_bytes=4000)
    with serving(tmp_path, behaviour) as running, pytest.raises(TransportDenied) as error:
        running.transport(max_bytes=64).fetch(running.url(), LOOPBACK)
    assert error.value.code in ('BYTE_CEILING_EXCEEDED', 'LENGTH_MISMATCH')


def test_a_truncated_body_is_refused_rather_than_returned_short(tmp_path):
    with serving(tmp_path, ServerBehaviour(body=b'short', declared_length=500)) as running, pytest.raises(TransportDenied) as error:
            running.transport().fetch(running.url(), LOOPBACK)
    assert error.value.code == 'TRUNCATED_RESPONSE'


def test_chunked_framing_is_refused(tmp_path):
    with serving(tmp_path, ServerBehaviour(chunked=True)) as running, pytest.raises(TransportDenied) as error:
            running.transport().fetch(running.url(), LOOPBACK)
    assert error.value.code == 'CHUNKED_FRAMING_REFUSED'


def test_a_missing_content_length_is_refused(tmp_path):
    with serving(tmp_path, ServerBehaviour(omit_length=True)) as running, pytest.raises(TransportDenied) as error:
            running.transport().fetch(running.url(), LOOPBACK)
    assert error.value.code == 'LENGTH_REQUIRED'


def test_duplicate_framing_headers_are_refused(tmp_path):
    with serving(tmp_path, ServerBehaviour(duplicate_length=True)) as running, pytest.raises(TransportDenied) as error:
            running.transport().fetch(running.url(), LOOPBACK)
    assert error.value.code == 'DUPLICATE_HEADER'


def test_an_unexpected_status_is_refused(tmp_path):
    with serving(tmp_path, ServerBehaviour(status=500, body=b'error')) as running, pytest.raises(TransportDenied) as error:
            running.transport().fetch(running.url(), LOOPBACK)
    assert error.value.code == 'UNEXPECTED_STATUS'


def test_a_stalled_peer_hits_the_deadline(tmp_path):
    with serving(tmp_path, ServerBehaviour(stall_seconds=5)) as running, pytest.raises(TransportDenied) as error:
            running.transport(total_deadline=1.0, read_timeout=0.5).fetch(
                running.url(), LOOPBACK)
    assert error.value.code in ('READ_TIMEOUT', 'DEADLINE_EXCEEDED')


# -- configuration refusals -------------------------------------------------


@pytest.mark.parametrize('variable', PROXY_VARIABLES)
def test_any_proxy_variable_refuses_the_transfer(server, variable):
    """A proxy silently defeats address pinning, so its presence is fatal."""
    transport = QualifiedTransport(
        server.policy(), server.qualification(), environ={variable: 'http://127.0.0.1:1'})
    with pytest.raises(TransportDenied) as error:
        transport.fetch(server.url(), LOOPBACK)
    assert error.value.code == 'PROXY_CONFIGURED'


def test_a_production_policy_cannot_be_paired_with_a_qualification_profile(server):
    production_policy = DestinationPolicy('example.org', ('/docs/',), 1000)
    with pytest.raises(ValueError):
        QualifiedTransport(production_policy, server.qualification())


def test_a_path_outside_the_approved_prefix_never_reaches_the_socket(server):
    with pytest.raises(ValueError):
        server.transport().fetch(server.url('/secrets/keys.txt'), LOOPBACK)


def test_classified_content_is_never_sent_to_a_public_destination(server):
    with pytest.raises(ValueError):
        server.transport().fetch(server.url(), LOOPBACK,
                                 classifications=frozenset({'restricted-personal'}))


def test_verified_artifact_returns_exact_bytes_after_trusted_digest_check(server):
    import hashlib
    expected = ServerBehaviour().body
    result = server.transport().fetch_artifact(
        server.url(), LOOPBACK, expected_sha256=hashlib.sha256(expected).hexdigest())
    assert result.body == expected
    assert result.evidence.bytes_received == len(expected)
    assert result.evidence.qualification_only


def test_changed_artifact_is_not_returned_despite_valid_peer_identity(server):
    with pytest.raises(TransportDenied, match='ARTIFACT_DIGEST_MISMATCH'):
        server.transport().fetch_artifact(server.url(), LOOPBACK, expected_sha256='0' * 64)


@pytest.mark.parametrize('digest', ['', 'x' * 64, 'A' * 64, None])
def test_artifact_requires_an_explicit_well_formed_digest(server, digest):
    with pytest.raises(ValueError):
        server.transport().fetch_artifact(server.url(), LOOPBACK, expected_sha256=digest)


def test_concurrent_transfers_do_not_share_response_buffers(tmp_path, monkeypatch):
    import hashlib
    import threading
    from concurrent.futures import ThreadPoolExecutor

    class DistinctResponses(LoopbackTLSServer):
        sequence = 0
        def _response(self):
            self.sequence += 1
            body = str(self.sequence).encode()
            return b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\n' + body

    with DistinctResponses(tmp_path) as running:
        transport = running.transport()
        original = transport._read_headers
        barrier = threading.Barrier(2)
        def synchronize(*args):
            result = original(*args)
            barrier.wait(timeout=5)
            return result
        monkeypatch.setattr(transport, '_read_headers', synchronize)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(transport.fetch, running.url(), LOOPBACK) for _ in range(2)]
            hashes = {f.result(timeout=10).body_sha256 for f in futures}
    assert hashes == {hashlib.sha256(b'1').hexdigest(), hashlib.sha256(b'2').hexdigest()}


@pytest.mark.parametrize('raw', [
    b'HTTP/1.9 200 OK\r\nContent-Length: 0\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nContent-Length : 0\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nX-Test: bad\x00value\r\nContent-Length: 0\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nContent-Length: \xb2\r\n\r\n',
])
def test_malformed_http_framing_is_refused_over_real_tls(tmp_path, raw):
    class MalformedPeer(LoopbackTLSServer):
        def _response(self):
            return raw
    with MalformedPeer(tmp_path) as running, pytest.raises(TransportDenied):
        running.transport().fetch(running.url(), LOOPBACK)
