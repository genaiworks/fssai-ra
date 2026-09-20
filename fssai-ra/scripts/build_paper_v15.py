"""Derive the submission manuscript from the preserved v14 artifact.

v15 is a presentation and scholarship revision. It removes the revision-diary
voice -- "this revision adds", "can now be", version numbers in captions -- so
the manuscript reads as a paper rather than as a changelog, and it replaces the
abstract with one that leads on the problem and the contribution instead of on
an inventory of fixtures.

It then does three things a reviewer of a first submission expects. It states
the central claim as a named property that can be refuted, rather than leaving
it as prose in three separate places. It credits the capability,
information-flow and confinement results whose vocabulary the architecture had
been using without citation, and names the governance frameworks the education
argument answers to. And it adds the apparatus that makes a dense paper
followable: a reading guide, a terminology table, a placement table against
related work, and a recipe for extending the kernel.

No claim, quantity, control or limitation is added, removed or weakened here.
The scope statements stay; they move out of the opening paragraph and into the
sections that carry the evidence, and the evidence scope is stated once where a
reader looks for it rather than repeated in every table row and caption.
Because every edit is a declared substring replacement or a declared insertion
rather than a hand edit of a binary, the whole change is reviewable in this file
and the result is byte-reproducible from its preserved source.
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


def _cell(template_cell, value):
    """One table cell carrying one paragraph of text."""
    cell = copy.deepcopy(template_cell)
    paragraphs = cell.findall(W + 'p')
    set_text(paragraphs[0], value)
    for extra in paragraphs[1:]:
        cell.remove(extra)
    return cell


def build_table(template, spec):
    """Clone the manuscript's own table style into a new table.

    Reusing the existing element keeps borders, widths and cell styles
    identical, so an added table cannot look like a foreign paste.
    """
    table = copy.deepcopy(template)
    rows = table.findall(W + 'tr')
    header_row, body_row = rows[0], rows[1]
    for row in rows:
        table.remove(row)
    for source, values in ((header_row, spec['header']),
                           *((body_row, row) for row in spec['rows'])):
        row = copy.deepcopy(source)
        cells = row.findall(W + 'tc')
        for cell in cells:
            row.remove(cell)
        for cell, value in zip(cells, values, strict=True):
            row.append(_cell(cell, value))
        table.append(row)
    return table


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

    body_template = find(body, 'Recent results motivate testing')[1]
    caption_template = find(body, 'Figure 1.')[1]
    table_template = next(node for node in body if node.tag == W + 'tbl')

    def insert_at(anchor, nodes, after=True):
        target_node = find(body, anchor)[1]
        position = list(body).index(target_node) + (1 if after else 0)
        for offset, node in enumerate(nodes):
            body.insert(position + offset, node)

    # Where this work sits. A reviewer should be able to place the paper
    # against its neighbours without reconstructing it from prose, so the table
    # closes the related-work discussion rather than interrupting it.
    insert_at('Recent results motivate testing',
              [build_table(table_template, review['related_work']),
               clone(caption_template, review['related_work']['caption'])])

    # Two structural additions a reviewer expects to find: an explicit statement
    # of what the paper contributes, and the headline results before the table
    # that qualifies them.
    insert_at(review['related_work']['caption'][:40],
              [clone(body_template, review['contributions'])])

    # The apparatus that makes the rest followable: how to read the paper, and
    # the seven terms it will not redefine later.
    insert_at('This paper makes four contributions',
              [clone(body_template, review['reading_guide']),
               build_table(table_template, review['terminology']),
               clone(caption_template, review['terminology']['caption'])])

    # The adversary, stated once and in one place. Property 1 is meaningless
    # until the reader knows what the attacker is assumed to hold, and that was
    # previously scattered across five sections.
    insert_at('Figure 2. Proof before power', [clone(body_template, review['threat_model'])],
              after=False)

    # The central claim, named and stated so that refuting it is a procedure
    # rather than an argument. It closes the architecture section because that
    # is what the architecture is for; section 4 then attacks it.
    insert_at(review['threat_model'][:40], [clone(body_template, review['property_statement'])])

    kernel = find(body, 'The architecture is implemented as the public')[1]
    body.insert(list(body).index(kernel), clone(body_template, review['results_summary']))

    # How to extend the kernel, at the end of the section a developer reads.
    insert_at('6. Stopping, Delivery and Monitoring',
              [clone(body_template, review['extension_recipe'])], after=False)

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

    # References are rewritten in place so the bibliography stays in one block,
    # grouped because the three kinds carry different weight: recent preprints
    # are current evidence, foundations are settled results, and standards are
    # the obligations an adopting institution already has.
    refs = [p for p in body if text_of(p).startswith('[')]
    template = copy.deepcopy(refs[0])
    for paragraph in refs:
        body.remove(paragraph)
    index, _ = find(body, 'References')
    offset = 0
    for group, entries in (('Recent research', review['references']),
                           ('Foundations', review['foundations']),
                           ('Standards and policy', review['standards'])):
        body.insert(index + 1 + offset, clone(template, group))
        offset += 1
        for reference in entries:
            venue = reference.get('venue', 'Research preprint')
            url = f" {reference['url']}" if reference.get('url') else ''
            value = (f"[{reference['id']}] {reference['authors']}, {reference['title']}. "
                     f"{venue}, {reference['year']}.{url}")
            body.insert(index + 1 + offset, clone(template, value))
            offset += 1

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
