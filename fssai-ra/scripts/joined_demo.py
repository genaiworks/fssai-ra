#!/usr/bin/env python3
"""Run a synthetic SQLite workflow and write a static, escaped evidence viewer."""
import argparse
import html
import json
import sys
from pathlib import Path

# Load the stdlib-only leaf without the legacy package facade (which imports YAML).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "fssaira"))

from joined_workflow import Workflow, call


def run(path, pack='education', control=True, wrong=False):
    w = Workflow(path, pack=pack, control=control)
    transcript = []

    def step(token='demo-advisor', **q):
        result = call(w, token, **q)
        transcript.append({'request': q, 'result': result})
        return result

    step(op='read', subject='s2')
    step(op='tool', url='http://127.0.0.1/controlled-sink')
    c = step(op='read')['context']
    p = step(op='propose', context=c, operation=w.pack['operation'], recipient='recipient',
             value=w.pack['wrong'] if wrong else w.pack['supported'],
             rationale='Synthetic scripted proposal; not hidden chain-of-thought')['proposal']
    confirmed = step('demo-instructor', op='confirm', proposal=p)
    if confirmed['ok']:
        a = step('demo-registrar', op='approve', proposal=p, confirmation=confirmed['confirmation'])['approval']
        step(op='execute', proposal=p, approval=a, value='tampered-after-approval')
        step(op='execute', proposal=p, approval=a)
        step(op='release', proposal=p)
        # Simulate losing the response after a real commit, then reopen the database.
        w.close()
        w = Workflow(path, pack=pack, control=control)
        step(op='reconcile', proposal=p)
        step('demo-recipient', op='release', proposal=p)
        step('demo-admin', op='revoke', grant='root')
        step('demo-recipient', op='release', proposal=p)
        step('demo-appeal', op='appeal', proposal=p, value=w.pack['before'])
    result = {'mode': 'offline scripted model and simulated human decisions; real SQLite effects',
              'control': control, 'pack': pack, 'transcript': transcript,
              'records': [dict(r) for r in w.db.execute('SELECT * FROM records')],
              'sinks': [{'recipient': r['recipient'], 'bytes': bytes(r['bytes']).decode()} for r in w.db.execute('SELECT * FROM sinks')],
              'evidence': [dict(r) for r in w.db.execute('SELECT * FROM evidence')],
              'checkpoint': w.checkpoint(), 'verified': w.verify(w.checkpoint())}
    w.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('audit/demo'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Never overwrite a used store: a second run must use a fresh directory.
    if any(args.output.glob('*.db')):
        parser.error('output contains a prior database; choose a fresh --output directory')
    results = [run(args.output / 'education.db'), run(args.output / 'benefits.db', 'benefits')]
    for i, enabled in enumerate((True, False, True)):
        results.append(run(args.output / f'ablation-{i}.db', control=enabled, wrong=True))
    raw = json.dumps(results, indent=2)
    (args.output / 'receipts.json').write_text(raw)
    (args.output / 'viewer.html').write_text('<!doctype html><meta charset="utf-8"><title>Governed workflow evidence</title>'
        '<style>body{max-width:1000px;margin:3em auto;font:16px system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
        '<h1>Trust by Construction: executed evidence</h1><p>Synthetic data; scripted model; simulated reviewers. '
        'SQLite effects and sink bytes below are actual local execution. No live model or institutional deployment.</p><pre>'
        + html.escape(raw) + '</pre>')
    print(json.dumps({'output': str(args.output), 'runs': len(results), 'verified': all(r['verified'] for r in results)}))


if __name__ == '__main__':
    main()
