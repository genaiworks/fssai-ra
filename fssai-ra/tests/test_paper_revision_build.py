"""The current Word revision must be rebuildable from its preserved source."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_paper_v14 import build  # noqa: E402

MANIFEST = json.loads((ROOT / 'paper/tbc-v14/implementation.json').read_text())


def test_committed_revision_matches_a_fresh_build(tmp_path):
    result = build(ROOT / MANIFEST['derived_from'], tmp_path / 'rebuilt.docx')
    assert result['target_sha256'] == MANIFEST['source_sha256']


def test_earlier_revisions_are_preserved_unedited():
    for version, digest in (('tbc-v11/TBC_v11.docx', None), ('tbc-v12/TBC_v12_Engineering_Revision.docx', None), ('tbc-v13/TBC_v13_Frontier_Threat_Revision.docx', None)):
        source = ROOT / 'paper' / version
        assert source.is_file(), 'a superseded revision must stay in the repository for provenance'
        manifest = json.loads((source.parent / 'implementation.json').read_text())
        assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['source_sha256'], digest or version


def test_current_references_are_recent_papers_with_resolved_citations():
    import re
    import zipfile
    from datetime import date
    from xml.etree import ElementTree as ET

    content = json.loads((ROOT / 'paper/tbc-v14/revision-content.json').read_text())
    refs = content['references']
    assert {r['id'] for r in refs} == set(range(1, len(refs) + 1))
    assert all(date.fromisoformat(content['earliest']) <= date.fromisoformat(r['published'])
               <= date.fromisoformat(content['cutoff']) for r in refs)
    assert all(r['url'].startswith('https://arxiv.org/abs/') for r in refs)
    with zipfile.ZipFile(ROOT / MANIFEST['source']) as z:
        tree = ET.fromstring(z.read('word/document.xml'))
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    paragraphs = [''.join(n.text or '' for n in p.iter(ns + 't')) for p in tree.iter(ns + 'p')]
    body = '\n'.join(p for p in paragraphs if not p.startswith('['))
    cited = {int(n) for group in re.findall(r'\[([\d, -]+)\]', body) for n in re.findall(r'\d+', group)}
    assert cited == {r['id'] for r in refs}
    bibliography = [p for p in paragraphs if p.startswith('[')]
    assert len(bibliography) == len(refs)
    assert all(r['title'] in bibliography[r['id'] - 1] for r in refs)
