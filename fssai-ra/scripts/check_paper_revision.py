"""Check revised Word source, claim locators and recorded engineering evidence.

This checks explicit bindings, not semantic equivalence of prose and code.
"""
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from fssaira.kernel.contracts import resolve_test, source_digest

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    manifest = json.loads((root / 'paper/tbc-v13/implementation.json').read_text())
    preserved = root / manifest['derived_from']
    if not preserved.is_file():
        raise ValueError('the preserved earlier revision must remain in the repository')
    document = root / manifest['source']
    if hashlib.sha256(document.read_bytes()).hexdigest() != manifest['source_sha256']:
        raise ValueError('revised paper changed; review claim bindings')
    with zipfile.ZipFile(document) as archive:
        tree = ET.fromstring(archive.read('word/document.xml'))
    text = ' '.join(node.text or '' for node in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
    for claim in manifest['claims']:
        if claim['paper_anchor'] not in text:
            raise ValueError('missing paper claim anchor')
        for test in claim['tests']:
            resolve_test(test, root)
    evidence = json.loads((root / 'audit/architecture/claims-register.json').read_text())
    if not evidence['passed'] or evidence['source_sha256'] != source_digest(root):
        raise ValueError('stale or failed capability evidence; run verify_architecture.py')
    if evidence['counts']['machine_verified'] != manifest['executed_contracts']:
        raise ValueError('contract count drift')
    if manifest['regression_source_sha256'] != source_digest(root):
        raise ValueError('recorded regression evidence is stale for this source')
    suites = ET.parse(root / 'audit/architecture/full-tests.xml').getroot()
    count = sum(int(s.get('tests', 0)) for s in suites.iter('testsuite'))
    bad = sum(int(s.get(key, 0)) for s in suites.iter('testsuite') for key in ('errors', 'failures', 'skipped'))
    if bad or count != manifest['regression_tests'] or f'{count:,} tests passed' not in text:
        raise ValueError('paper regression count differs from executed evidence')
    return {'passed': True, 'claims': len(manifest['claims']), 'executed_contracts': manifest['executed_contracts'],
            'regression_tests': count, 'scope': 'explicit prose anchors, test locators and recorded local evidence'}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
