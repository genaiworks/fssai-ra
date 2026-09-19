"""Reproducibly derive v14 from the preserved, reviewed v13 Word artifact."""
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_paper_revision import NAMESPACES, W, clone, find, set_text, text_of

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'paper/tbc-v13/TBC_v13_Frontier_Threat_Revision.docx'
TARGET = ROOT / 'paper/tbc-v14/TBC_v14_Developer_Security_Revision.docx'


def build(source=SOURCE, target=TARGET):
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri)
    review = json.loads((ROOT / 'paper/tbc-v14/revision-content.json').read_text())
    with zipfile.ZipFile(source) as archive:
        tree = ET.fromstring(archive.read('word/document.xml'))
    body = tree.find(W + 'body')
    for prefix, value in review['replacements'].items():
        set_text(find(body, prefix)[1], value)
    for node in body.iter(W + 'p'):
        value = text_of(node)
        changed = value.replace('1,375 tests passed', '1,400 tests passed')
        changed = changed.replace('31 source-bound capability contracts', '33 source-bound capability contracts')
        changed = changed.replace('Thirty-one contracts are verified', 'Thirty-three contracts are verified')
        changed = changed.replace('The code path is qualified; the network is not.',
                                  'Controlled tests exercise this code path; the deployment network remains unqualified.')
        if changed != value:
            set_text(node, changed)
    _, transport = find(body, 'The destination contract decided')
    body.insert(list(body).index(transport) + 1, clone(transport, review['developer_transport']))
    _, settlement = find(body, 'Three further boundaries')
    body.insert(list(body).index(settlement) + 1, clone(settlement, review['developer_recovery']))
    _, artifact = find(body, 'Code, machine-readable authority profiles')
    set_text(artifact, text_of(artifact) + ' The current v14 developer path is DEVELOPER_GUIDE.md; '
             'make developer-demo runs the offline artifact-integrity and settlement example, and make all '
             'checks the complete release. scripts/build_paper_v14.py regenerates this manuscript from '
             'preserved v13 and reviewed content. The example uses no external model or real student data.')
    refs = [p for p in body if text_of(p).startswith('[')]
    template = copy.deepcopy(refs[0])
    for p in refs:
        body.remove(p)
    index, _ = find(body, 'References')
    for offset, ref in enumerate(review['references']):
        value = f"[{ref['id']}] {ref['authors']}, {ref['title']}. Research preprint, {ref['year']}. {ref['url']}"
        body.insert(index + 1 + offset, clone(template, value))
    updated = ET.tostring(tree, encoding='UTF-8', xml_declaration=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as out:
        for item in archive.infolist():
            out.writestr(item, updated if item.filename == 'word/document.xml' else archive.read(item.filename))
    return {'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
