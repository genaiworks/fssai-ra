"""Validate architecture traceability without promoting partial claims."""
import json
from pathlib import Path

from fssaira.kernel.contracts import resolve_test

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    register = json.loads((root / 'audit/architecture-controls.json').read_text())
    controls = register['controls']
    ids = [c['id'] for c in controls]
    if len(set(ids)) != len(ids) or len(ids) != register['catalogue_size'] or len(ids) != 109:
        raise ValueError('control inventory drift')
    counts = dict.fromkeys(('implemented-local', 'partial-reference', 'deployment-required', 'not-implemented'), 0)
    for control in controls:
        counts[control['status']] += 1
        for key in ('implementation', 'related_test_file'):
            path = (root / control[key]).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                raise ValueError('missing or unsafe traceability path')
        if not control['scope'].strip() or not 1 <= control['page'] <= 657:
            raise ValueError('missing scope or source page')
        if control['status'] == 'implemented-local':
            resolve_test(control['failure_test'], root)
    return {'passed': True, 'controls': len(ids), 'statuses': counts,
            'meaning': 'Traceability structure validated; behavioral verification runs separately.'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
