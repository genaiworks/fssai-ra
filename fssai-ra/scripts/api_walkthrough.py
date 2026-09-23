"""Exercise a synthetic action against a local reference API, or start an isolated one."""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from reproduce import reference_env
from smoke_stack import load_env

APP = Path(__file__).resolve().parents[1]


def exercise(base, tokens, wait=0):
    transcript = []

    def request(method, path, body=None, role=None, expected=200):
        headers = {'Content-Type': 'application/json'}
        if role:
            headers['Authorization'] = 'Bearer ' + tokens[role]
        req = urllib.request.Request(base + path, method=method, headers=headers,
                                     data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                status, result = response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            status, result = exc.code, json.load(exc)
        transcript.append({'method': method, 'path': path, 'role': role, 'status': status})
        if status != expected:
            raise RuntimeError(f'{method} {path}: expected HTTP {expected}, got {status}: {result}')
        return result

    health = request('GET', '/health')
    capacity = (health.get('declared_controls') or {}).get('review_capacity') or {}
    wait = max(wait, float(capacity.get('min_deliberation_seconds') or 0))
    suffix = uuid.uuid4().hex[:12]
    resource = 'walkthrough-' + suffix
    request('POST', '/v1/resources', {'resource_id': resource, 'status': 'draft', 'version': 1},
            role='operator', expected=201)
    proposal = request('POST', '/v1/proposals', {
        'request_id': 'walkthrough-request-' + suffix, 'operation': 'prepare_case_for_review',
        'resource_id': resource, 'from_status': 'draft', 'to_status': 'ready_for_officer_review',
        'evidence_version': 'synthetic-walkthrough-v1',
    }, role='agent', expected=201)
    path = '/v1/proposals/' + proposal['request_id']
    request('POST', path + '/approval', {}, role='agent', expected=403)
    request('POST', path + '/review', role='officer', expected=201)
    if tokens.get('second'):
        request('POST', path + '/review', role='second', expected=201)
    if wait:
        print(f'Waiting {wait:g} seconds for the declared review floor (simulated reviewers).', flush=True)
        time.sleep(wait)
    if tokens.get('second'):
        request('POST', path + '/endorsement', role='second', expected=201)
    request('POST', path + '/approval', {'ttl_seconds': 300}, role='officer', expected=201)
    first = request('POST', path + '/execute', role='operator')
    replay = request('POST', path + '/execute', role='operator')
    state = request('GET', '/v1/resources/' + resource, role='operator')
    evidence = request('GET', path + '/evidence', role='operator')
    chain = request('GET', '/v1/evidence/verify', role='operator')
    checks = {
        'unapproved_role_denied': True,
        'state_changed_once': state['version'] == 2 and state['status'] == 'ready_for_officer_review',
        'same_receipt_on_retry': replay['replayed'] and replay['receipt_hash'] == first['receipt_hash'],
        'intent_and_outcome': [r['kind'] for r in evidence['records']] == ['action_intent', 'action_outcome'],
        'chain_valid': chain['chain_valid'],
    }
    return {'passed': all(checks.values()), 'scope': 'Synthetic local HTTP workflow; simulated reviewers',
            'checks': checks, 'requests': transcript, 'resource_id': resource}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--env-file', type=Path, help='generated local deploy/.env; tokens are never printed')
    parser.add_argument('--review-wait', type=float, default=0)
    parser.add_argument('--self-test', action='store_true', help='start and stop an isolated local API on a free port')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.review_wait < 0:
        parser.error('--review-wait must be nonnegative')
    parsed = urlsplit(args.base_url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'} or parsed.username:
        parser.error('this synthetic walkthrough only supports local HTTP reference services')
    if args.self_test and args.env_file:
        parser.error('--self-test uses isolated teaching configuration; omit --env-file')
    tokens = {'operator': 'dev-operator-token', 'agent': 'dev-agent-token',
              'officer': 'dev-officer-token', 'second': 'dev-second-officer-token'}
    wait = args.review_wait
    if args.env_file:
        env = load_env(args.env_file)
        identities = json.loads(env['FSSAI_AUTH_TOKENS_JSON'])
        for name, role in [('operator', 'platform_operator'), ('agent', 'proposer'), ('officer', 'student_support_officer')]:
            tokens[name] = next(t for t, value in identities.items() if role in value['roles'])
        tokens['second'] = next((t for t, value in identities.items()
                                 if 'student_support_officer' in value['roles'] and t != tokens['officer']), None)
        wait = max(wait, float(env.get('FSSAI_REVIEW_DELIBERATION_FLOOR') or 0))
    server = None
    with tempfile.TemporaryFile(mode='w+t') as server_log:
        try:
            if args.self_test:
                with socket.socket() as port:
                    port.bind(('127.0.0.1', 0))
                    number = port.getsockname()[1]
                args.base_url = f'http://127.0.0.1:{number}'
                server = subprocess.Popen([sys.executable, '-m', 'fssaira.cli', 'serve', '--host', '127.0.0.1', '--port', str(number)],
                                          cwd=APP, env=reference_env(), stdout=server_log, stderr=subprocess.STDOUT)
                for _ in range(100):
                    if server.poll() is not None:
                        server_log.seek(0)
                        raise RuntimeError('API failed to start. Install .[api].\n' + server_log.read())
                    try:
                        with urllib.request.urlopen(args.base_url + '/health', timeout=0.2):
                            break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.1)
                else:
                    raise RuntimeError('API did not become ready within 10 seconds')
            report = exercise(args.base_url.rstrip('/'), tokens, wait)
            rendered = json.dumps(report, indent=2) + '\n'
            print(rendered)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered)
            return 0 if report['passed'] else 1
        except (OSError, RuntimeError, KeyError, ValueError, StopIteration) as exc:
            print(f'Walkthrough failed: {exc}', file=sys.stderr)
            return 1
        finally:
            if server is not None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == '__main__':
    raise SystemExit(main())
