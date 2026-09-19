"""The current Word revision must be rebuildable from its preserved source."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_paper_revision import build  # noqa: E402

MANIFEST = json.loads((ROOT / 'paper/tbc-v13/implementation.json').read_text())


def test_committed_revision_matches_a_fresh_build(tmp_path):
    result = build(ROOT / MANIFEST['derived_from'], tmp_path / 'rebuilt.docx')
    assert result['target_sha256'] == MANIFEST['source_sha256']


def test_earlier_revisions_are_preserved_unedited():
    for version, digest in (('tbc-v11/TBC_v11.docx', None), ('tbc-v12/TBC_v12_Engineering_Revision.docx', None)):
        source = ROOT / 'paper' / version
        assert source.is_file(), 'a superseded revision must stay in the repository for provenance'
        manifest = json.loads((source.parent / 'implementation.json').read_text())
        assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest['source_sha256'], digest or version
