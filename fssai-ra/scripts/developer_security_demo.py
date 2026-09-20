"""Offline v14 developer example: authenticated bytes and uncertain remote effects.

Uses only a generated loopback TLS peer and an in-memory synthetic provider.
No external services, model keys or real student records are used.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from fssaira.integration.transport import TransportDenied
from fssaira.integration.transport_harness import LoopbackTLSServer, ServerBehaviour
from fssaira.remote_effects import EffectLedger, LostAcknowledgement, UnresolvedEffect


class SyntheticRegistrar:
    def __init__(self):
        self.submissions = 0
        self.final = False

    def submit(self, key, operation, payload):
        self.submissions += 1
        raise LostAcknowledgement('reply lost after provider accepted the request')

    def lookup(self, key):
        if not self.final:
            return {'status': 'pending'}
        return {'status': 'applied', 'result': {'receipt': 'synthetic-1'}}


def run():
    with tempfile.TemporaryDirectory(prefix='tbc-v14-') as directory:
        root = Path(directory)
        body = ServerBehaviour().body
        with LoopbackTLSServer(root) as peer:
            transport = peer.transport()
            artifact = transport.fetch_artifact(peer.url(), ('127.0.0.1',),
                                                expected_sha256=hashlib.sha256(body).hexdigest())
            try:
                transport.fetch_artifact(peer.url(), ('127.0.0.1',), expected_sha256='0' * 64)
            except TransportDenied as error:
                rejected = error.code
            else:
                raise AssertionError('changed artifact was accepted')
        ledger = EffectLedger(root / 'effects.db')
        try:
            provider = SyntheticRegistrar()
            record = ledger.submit(provider, key='demo-approved-decision',
                                   operation='correct_transcript', payload={'synthetic': True})
            states = [record.state, ledger.reconcile(provider, record.key).state]
            try:
                ledger.require_settled()
            except UnresolvedEffect:
                blocked = True
            else:
                raise AssertionError('pending work was released')
            provider.final = True
            states.append(ledger.reconcile(provider, record.key).state)
            ledger.require_settled()
            return {'qualification': 'local-reference', 'exact_artifact_bytes': artifact.body == body,
                    'digest_mismatch': rejected, 'effect_states': states,
                    'dependent_work_blocked_while_pending': blocked,
                    'provider_submissions': provider.submissions,
                    'limits': ['synthetic provider', 'loopback TLS peer', 'not production isolation']}
        finally:
            ledger.close()


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
