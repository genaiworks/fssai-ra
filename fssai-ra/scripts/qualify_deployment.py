"""Measure this deployment and decide, from evidence, what it is allowed to be.

    python scripts/qualify_deployment.py --operator alice

Runs the three measurements a reviewer asked for -- host isolation, outbound
transport, and the settlement state of outbound effects -- then puts them
through the promotion gate and writes the result to
``audit/qualification/``. On a laptop or a CI runner it prints ``reference``
and names every reason, which is the correct answer and the point of running it.

Nothing here is a substitute for an adversarial exercise in the target
deployment. It is the difference between a deployment that has been checked
against its own assumptions and one that has merely described them.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from fssaira.federation import PromotionEvidence, PromotionGate  # noqa: E402
from fssaira.isolation import probe_host  # noqa: E402
from fssaira.remote_effects import EffectLedger  # noqa: E402


def transport_evidence(workspace: Path) -> dict:
    """Exercise the real transport code path against the loopback harness.

    This proves the socket, handshake, pin comparison and ceiling work here. It
    is explicitly not a network peer, and the record says so, so the promotion
    gate below refuses to accept it as production transport evidence.
    """
    from fssaira.integration.transport_harness import LoopbackTLSServer

    with LoopbackTLSServer(workspace) as server:
        return server.transport().fetch(server.url(), ('127.0.0.1',)).to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator', required=True,
                        help='the named person accountable for this measurement')
    parser.add_argument('--control-store', default=None,
                        help='path to the control database the agent must not write')
    parser.add_argument('--agent-uid', type=int, default=None,
                        help='the OS uid the model runtime executes as')
    parser.add_argument('--egress-canary', default=None, metavar='HOST:PORT',
                        help='an address that must NOT be reachable from this host')
    parser.add_argument('--effect-ledger', default=None,
                        help='path to the outbound effect ledger, if one exists')
    parser.add_argument('--bundle-digest', default='',
                        help='digest of the model bundle being promoted')
    parser.add_argument('--out', default=str(ROOT / 'audit/qualification'))
    parser.add_argument('--conformance-passed', action='store_true',
                        help='declare that the conformance suite passed for this deployment')
    arguments = parser.parse_args(argv)

    canary = None
    if arguments.egress_canary:
        host, _, port = arguments.egress_canary.rpartition(':')
        canary = (host, int(port))

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)

    isolation = probe_host(
        operator=arguments.operator,
        control_store=arguments.control_store,
        agent_uid=arguments.agent_uid,
        egress_canary=canary,
    )
    isolation.write_json(out / 'isolation.json')

    transport = transport_evidence(out)
    (out / 'transport.json').write_text(json.dumps(transport, indent=2) + '\n')

    unresolved = 0
    if arguments.effect_ledger:
        ledger = EffectLedger(arguments.effect_ledger)
        try:
            unresolved = len(ledger.unresolved())
        finally:
            ledger.close()

    now = time.time()
    decision = PromotionGate().evaluate(PromotionEvidence(
        conformance_passed=arguments.conformance_passed,
        conformance_at=now,
        isolation_qualification=isolation.qualification(now),
        isolation_at=isolation.attribution.measured_at,
        transport_qualified=transport['status'] == 200,
        transport_qualification_only=transport['qualification_only'],
        transport_at=now,
        # No witness set is configured by default: a single custodian is not a
        # witness set, and pretending otherwise is the failure this checks for.
        evidence_attested=False,
        unresolved_effects=unresolved,
        evaluated_bundle_digest=arguments.bundle_digest,
        promoted_bundle_digest=arguments.bundle_digest,
        operator=arguments.operator,
    ), now=now)
    (out / 'promotion.json').write_text(json.dumps(decision, indent=2) + '\n')

    print(isolation.render())
    print(f"transport: {transport['tls_version']} {transport['cipher']} "
          f"pin {transport['peer_pin'][:24]}... "
          f"(qualification_only={transport['qualification_only']})")
    print(f"outbound effects unresolved: {unresolved}")
    print(f"\npromotion: {decision['qualification']}")
    for reason in decision['missing']:
        print(f"  missing: {reason}")
    print(f"\nwritten to {out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
