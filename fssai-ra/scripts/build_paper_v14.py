"""Reproducibly derive v14 from the preserved, reviewed v13 Word artifact."""
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_paper_revision import NAMESPACES, W, clone, find, set_text, text_of
from build_release_figures import verify as verify_figures

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'paper/tbc-v13/TBC_v13_Frontier_Threat_Revision.docx'
TARGET = ROOT / 'paper/tbc-v14/TBC_v14_Developer_Security_Revision.docx'


def build(source=SOURCE, target=TARGET):
    verify_figures()
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
    set_text(find(body, 'Figure 4.')[1], 'Figure 4. Authority boundaries in v14. Untrusted reasoning proposes requests; the independent service mediates effects. AI monitoring may restrict authority. Host isolation, authenticated adapters and independent key custody remain deployment obligations.')
    set_text(find(body, 'Figure 6.')[1], 'Figure 6. Recorded synthetic results. The three-arm comparison contains seven hostile and two benign proposals per arm. The separate six-profile experiment contains 180 hostile and 58 benign scenarios. These fixture counts do not estimate field attack rates, live-model accuracy or usability.')
    for node in tree.iter('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr'):
        if node.get('id') == '4':
            node.set('descr', 'Authority boundaries: agent proposals enter independent controls; monitor can restrict only; human approval and external isolation remain separate.')
        elif node.get('id') == '5':
            node.set('descr', 'Synthetic containment: unguarded 0 of 7, prompt plus allowlist 2 of 7, independent controls 7 of 7. Separate domain fixtures: 180 of 180 hostile contained and 58 of 58 benign completed.')
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
            figures = {'word/media/image4.png': 'architecture.png', 'word/media/image5.png': 'evidence.png'}
            payload = updated if item.filename == 'word/document.xml' else archive.read(item.filename)
            if item.filename in figures:
                payload = (ROOT / 'paper/tbc-v14/figures' / figures[item.filename]).read_bytes()
            out.writestr(item, payload)
    return {'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
