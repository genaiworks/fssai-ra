"""Measure what an authorised release path leaks, and what closes it.

    python scripts/measure_covert_channels.py            # print the table
    python scripts/measure_covert_channels.py --check    # fail on drift

Runs one adversarial encoder against three policies over every secret of a
declared width, counts the distinct traces an external observer could
distinguish, and records the result in ``audit/covert-channels.json``. The
measurement is deterministic and offline, so ``--check`` is a real regression
gate on the reported numbers rather than a re-run that always agrees.

Every release the adversary makes is authorised. Nothing here is a claim that
the mediated release path is the only path out of a deployment.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from fssaira.covert_channels import (  # noqa: E402
    EgressPolicy,
    canonical_policy,
    run_channel_experiment,
    sealed_policy,
)

OUTPUT = ROOT / 'audit/covert-channels.json'

DESTINATIONS = tuple(f'registrar-{index}' for index in range(8))
PATHS = tuple(f'/reports/{index}/' for index in range(4))
SIZE_BUCKETS = (4096, 16384, 65536, 262144)
SECRET_BITS = 16

#: Reported quantities. Timings and other machine-dependent values are excluded
#: so that a committed result is comparable across machines.
REPORTED = (
    'attempted_bits', 'conveyed_bits', 'distinct_observable_traces',
    'bits_per_release', 'task_capacity_bits', 'within_declared_budget',
    'tasks_escalated_to_a_human', 'adversarial_tasks_escalated_fraction',
    'benign_releases_completed', 'benign_workflow_escalated',
)


def arms() -> dict[str, EgressPolicy]:
    """Three policies over one approved surface: none, canonical, sealed."""
    return {
        'no_control': EgressPolicy(
            DESTINATIONS, PATHS, size_buckets=SIZE_BUCKETS, budget_bits=1e6),
        'canonicalised': canonical_policy(
            DESTINATIONS, PATHS,
            contract_destination=DESTINATIONS[0], contract_path=PATHS[0]),
        'sealed': sealed_policy(
            DESTINATIONS, PATHS,
            contract_destination=DESTINATIONS[0], contract_path=PATHS[0]),
    }


def measure() -> dict:
    results = {}
    for name, policy in arms().items():
        full = run_channel_experiment(policy, secret_bits=SECRET_BITS)
        results[name] = {key: full[key] for key in REPORTED}
        results[name]['canonicalised_dimensions'] = full['policy']['canonicalised']
        results[name]['fixed_releases'] = full['policy']['fixed_releases']
    return {
        'schema_version': '1.0',
        'kind': 'covert_channel_ablation',
        'secret_bits': SECRET_BITS,
        'secrets_per_arm': 2 ** SECRET_BITS,
        'approved_destinations': len(DESTINATIONS),
        'approved_paths': len(PATHS),
        'arms': results,
        'reading': (
            'conveyed_bits is the base-two logarithm of the number of distinct '
            'observable traces, so it assumes a perfect observer and an optimal '
            'decoder. The benign columns are the utility baseline: a control that '
            'stopped the adversary by stopping every release would show zero '
            'completed benign releases and would not be a result.'
        ),
        'limits': [
            'one encoder under three policies; not a proof that no encoder does better',
            'bounds the mediated release interface, not any channel outside it',
            'content is excluded because release escrow already fixes the bytes',
            'the escalation fraction is a real availability cost, not an artefact',
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='compare a fresh run against the committed record')
    arguments = parser.parse_args(argv)

    fresh = measure()
    if arguments.check:
        if not OUTPUT.is_file():
            print(f'missing {OUTPUT.relative_to(ROOT)}; run without --check first')
            return 1
        committed = json.loads(OUTPUT.read_text())
        if committed != fresh:
            print('covert-channel measurement drifted from the committed record')
            return 1
        print(f'covert-channel measurement reproduces ({len(fresh["arms"])} arms)')
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(fresh, indent=2) + '\n')
    width = max(len(name) for name in fresh['arms'])
    print(f"{SECRET_BITS}-bit secret, {2 ** SECRET_BITS} trials per arm, "
          f"{len(DESTINATIONS)} approved destinations\n")
    print(f"{'arm':<{width}}  {'leaked':>7}  {'capacity':>9}  {'escalated':>10}  benign")
    for name, arm in fresh['arms'].items():
        capacity = arm['task_capacity_bits']
        print(f"{name:<{width}}  {arm['conveyed_bits']:>6.1f}b  "
              f"{capacity if capacity is None else f'{capacity:>8.1f}b'}  "
              f"{arm['adversarial_tasks_escalated_fraction']:>9.1%}  "
              f"{arm['benign_releases_completed']}/2 completed")
    print(f"\nwritten to {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
