"""The current Word revision must be rebuildable from its preserved source."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_paper_v15 import build  # noqa: E402

MANIFEST = json.loads((ROOT / 'paper/tbc-v15/implementation.json').read_text())


def test_committed_revision_matches_a_fresh_build(tmp_path):
    result = build(ROOT / MANIFEST['derived_from'], tmp_path / 'rebuilt.docx')
    assert result['target_sha256'] == MANIFEST['source_sha256']


def test_earlier_revisions_are_preserved_unedited():
    for version, digest in (('tbc-v11/TBC_v11.docx', None),
                            ('tbc-v12/TBC_v12_Engineering_Revision.docx', None),
                            ('tbc-v13/TBC_v13_Frontier_Threat_Revision.docx', None),
                            ('tbc-v14/TBC_v14_Developer_Security_Revision.docx', None)):
        source = ROOT / 'paper' / version
        assert source.is_file(), 'a superseded revision must stay in the repository for provenance'
        manifest = json.loads((source.parent / 'implementation.json').read_text())
        assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['source_sha256'], digest or version


def test_current_references_are_grouped_resolved_and_each_kind_is_what_it_claims():
    """Three kinds of source, three rules, one numbering.

    Recent research must be current and reachable, because that is the claim
    being made for it. Foundations must be published venue-of-record work and
    must predate that window, because a settled result cited as a preprint is
    a citation error. Standards must name their issuing body. Every reference
    must be cited somewhere in the body, and every citation must resolve: an
    uncited entry is padding and a dangling citation is a broken claim.
    """
    import re
    import zipfile
    from datetime import date
    from xml.etree import ElementTree as ET

    content = json.loads((ROOT / 'paper/tbc-v15/revision-content.json').read_text())
    recent, foundations, standards = (content['references'], content['foundations'],
                                      content['standards'])
    groups = recent + foundations + standards
    assert [r['id'] for r in groups] == list(range(1, len(groups) + 1)), 'numbering runs once, in document order'

    earliest, cutoff = date.fromisoformat(content['earliest']), date.fromisoformat(content['cutoff'])
    for reference in recent:
        assert earliest <= date.fromisoformat(reference['published']) <= cutoff
        assert reference['url'].startswith('https://arxiv.org/abs/')
    for reference in foundations:
        assert reference['year'] < earliest.year, 'a foundation is settled work, not recent work'
        assert reference.get('venue'), 'a foundation carries its venue of record'
        assert not reference.get('url'), 'foundations are cited by venue, not by link'
    for reference in standards:
        assert reference.get('venue') and reference.get('authors'), 'a standard names its issuing body'

    with zipfile.ZipFile(ROOT / MANIFEST['source']) as z:
        tree = ET.fromstring(z.read('word/document.xml'))
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    paragraphs = [''.join(n.text or '' for n in p.iter(ns + 't')) for p in tree.iter(ns + 'p')]
    body = '\n'.join(p for p in paragraphs if not p.startswith('['))

    cited = set()
    for group in re.findall(r'\[([\d, \-]+)\]', body):
        for part in (piece.strip() for piece in group.split(',')):
            bounds = part.split('-')
            if len(bounds) == 2 and all(b.isdigit() for b in bounds):
                cited.update(range(int(bounds[0]), int(bounds[1]) + 1))
            elif part.isdigit():
                cited.add(int(part))
    declared = {r['id'] for r in groups}
    assert cited == declared, f'uncited {sorted(declared - cited)}, dangling {sorted(cited - declared)}'

    bibliography = [p for p in paragraphs if p.startswith('[')]
    assert len(bibliography) == len(groups)
    assert all(r['title'] in bibliography[r['id'] - 1] for r in groups)
    assert {'Recent research', 'Foundations', 'Standards and policy'} <= set(paragraphs), \
        'the bibliography is grouped so a reader can see which kind of source carries which weight'


pytestmark = pytest.mark.manuscript
