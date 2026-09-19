"""Derive the submission manuscript from the preserved v14 artifact.

v15 is a presentation revision and nothing else. It removes the revision-diary
voice -- "this revision adds", "can now be", version numbers in captions -- so
the manuscript reads as a paper rather than as a changelog, and it replaces the
abstract with one that leads on the problem and the contribution instead of on
an inventory of fixtures.

No claim, quantity, control or limitation is added, removed or weakened here.
The scope statements stay; they move out of the opening paragraph and into the
sections that carry the evidence, which is where a reader looks for them.
Because every edit is a declared substring replacement rather than a hand edit
of a binary, the whole change is reviewable in this file and the result is
byte-reproducible from its preserved source.
"""
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_paper_revision import NAMESPACES, W, clone, find, set_text, text_of
from build_release_figures import verify as verify_figures

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'paper/tbc-v14/TBC_v14_Developer_Security_Revision.docx'
TARGET = ROOT / 'paper/tbc-v15/Trust_by_Construction.docx'
CONTENT = ROOT / 'paper/tbc-v15/revision-content.json'


def build(source=SOURCE, target=TARGET):
    verify_figures()
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri)
    review = json.loads(CONTENT.read_text())
    with zipfile.ZipFile(source) as archive:
        tree = ET.fromstring(archive.read('word/document.xml'))
    body = tree.find(W + 'body')

    set_text(find(body, 'Agentic AI can retrieve records')[1], review['abstract'])

    # Declared substring edits, applied wherever they occur. Every one is
    # checked to have matched, so a silent no-op cannot pass review.
    applied = {index: 0 for index, _ in enumerate(review['sentence_edits'])}
    for node in body.iter(W + 'p'):
        value = text_of(node)
        changed = value
        for index, (old, new) in enumerate(review['sentence_edits']):
            if old in changed:
                changed = changed.replace(old, new)
                applied[index] += 1
        if changed != value:
            set_text(node, changed)
    unmatched = [review['sentence_edits'][index][0][:60]
                 for index, count in applied.items() if count == 0]
    if unmatched:
        raise ValueError(f'declared edits matched nothing: {unmatched}')

    # Two structural additions a reviewer expects to find: an explicit statement
    # of what the paper contributes, and the headline results before the table
    # that qualifies them.
    body_template = find(body, 'Recent results motivate testing')[1]
    position = list(body).index(body_template) + 1
    body.insert(position, clone(body_template, review['contributions']))
    kernel = find(body, 'The architecture is implemented as the public')[1]
    body.insert(list(body).index(kernel), clone(body_template, review['results_summary']))

    # The channel that content controls cannot close is the paper's newest
    # result, so it gets a heading instead of sitting mid-section. Limitations
    # become a section for the same reason: a reviewer looks for the heading.
    heading_template = find(body, '8. Measuring the Assumptions')[1]
    for anchor, heading in (('Release escrow fixes the bytes that leave',
                             review['headings']['residual_channel']),
                            ('The experiments use synthetic fixtures',
                             review['headings']['limitations'])):
        target_paragraph = find(body, anchor)[1]
        body.insert(list(body).index(target_paragraph),
                    clone(heading_template, heading))

    # References are rewritten in place so the bibliography stays in one block.
    refs = [p for p in body if text_of(p).startswith('[')]
    template = copy.deepcopy(refs[0])
    for paragraph in refs:
        body.remove(paragraph)
    index, _ = find(body, 'References')
    for offset, reference in enumerate(review['references']):
        value = (f"[{reference['id']}] {reference['authors']}, {reference['title']}. "
                 f"Research preprint, {reference['year']}. {reference['url']}")
        body.insert(index + 1 + offset, clone(template, value))

    updated = ET.tostring(tree, encoding='UTF-8', xml_declaration=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(
            target, 'w', zipfile.ZIP_DEFLATED) as out:
        for item in archive.infolist():
            payload = (updated if item.filename == 'word/document.xml'
                       else archive.read(item.filename))
            out.writestr(item, payload)
    return {'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
