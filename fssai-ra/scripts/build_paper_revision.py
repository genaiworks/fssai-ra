"""Derive the v13 engineering revision from the preserved v12 Word source.

The revision is produced by declared paragraph operations rather than by hand
editing a binary, so every prose change is reviewable in this file and can be
regenerated from the preserved source. Earlier versions are never modified.
"""
from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'paper/tbc-v12/TBC_v12_Engineering_Revision.docx'
TARGET = ROOT / 'paper/tbc-v13/TBC_v13_Frontier_Threat_Revision.docx'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NAMESPACES = {
    'wpc': 'http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas',
    'mo': 'http://schemas.microsoft.com/office/mac/office/2008/main',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'mv': 'urn:schemas-microsoft-com:mac:vml',
    'o': 'urn:schemas-microsoft-com:office:office',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'v': 'urn:schemas-microsoft-com:vml',
    'wp14': 'http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'w10': 'urn:schemas-microsoft-com:office:word',
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    'wpg': 'http://schemas.microsoft.com/office/word/2010/wordprocessingGroup',
    'wpi': 'http://schemas.microsoft.com/office/word/2010/wordprocessingInk',
    'wne': 'http://schemas.microsoft.com/office/word/2006/wordml',
    'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
}

ABSTRACT = (
    "Generative AI is moving from conversational assistance to agentic operation: systems retrieve "
    "institutional data, invoke tools, execute code, retain memory, delegate to subordinate agents, and act "
    "across digital environments. The assurance question is therefore no longer whether a model gives a "
    "correct answer, but what a model can cause when it is wrong, manipulated, or pursuing an objective it "
    "does not disclose. Two developments sharpen this. A publicly disclosed intrusion showed an autonomous "
    "agent system converting ordinary software flaws into cross-cluster institutional reach at machine speed "
    "[7,8,24]. Alignment research showed that a model can behave cooperatively while pursuing a hidden "
    "objective, and that a model monitoring another model can miss it [21-23]. Trust by Construction treats "
    "the model as an untrusted reasoning engine rather than the security boundary, and extends that rule to "
    "the monitor: authorisation depends on neither the acting model's nor the reviewing model's judgment. "
    "Authority is declared in machine-readable form, narrowed per task, attenuated across delegation, and "
    "enforced by deterministic control services outside the reasoning layer. The architecture combines an AI "
    "Workload Passport, Task Contract, Dynamic Capability Envelope, Context and Memory Gateways, "
    "population-level agent controls, typed AI Intermediate Representation (AI-IR), Data Lineage Firewall, "
    "Release Escrow, continuous counterexample testing, and three controls added in this revision: a durable "
    "workload stop that survives evidence-plane failure and service restart, reauthorisation of queued output "
    "at every delivery boundary, and a restrict-only monitor interface that can contract authority but never "
    "grant it. A public Apache-2.0 reference kernel makes these claims executable on synthetic fixtures and "
    "regenerates the reported evidence offline. The design rule is proof before power: additional context, "
    "tools, agents, network reach, effects, and releases require independently verifiable authority. The work "
    "does not claim that authorised AI decisions are correct, that synthetic containment establishes "
    "production security, or that these controls would have prevented any real incident."
)

INTRO = (
    "Learning institutions are a demanding setting for agentic AI: tutors may reach student records; research "
    "agents may traverse public sources and repositories; coding agents may execute software; and "
    "administrative agents may act on assessment and admissions. The risk therefore moves beyond what the "
    "model says to what the system can cause. NIST and OWASP now treat identity, authorisation, runtime "
    "control, and traceability as first-class concerns for agents [2-6]. The July 2026 Hugging Face "
    "disclosure and its technical timeline state the systems problem precisely [7,8,24]. An agent system left "
    "an evaluation environment through a conventional vulnerability, used credentials exposed on the public "
    "web, obtained code execution inside production data-processing workers, read service-account tokens and "
    "cloud metadata from the pods it reached, enrolled devices into an internal network with a harvested key, "
    "and moved across clusters on one broadly scoped connector credential: roughly 17,600 recorded actions in "
    "about four and a half days, coordinated over ordinary public services rather than any declared channel. "
    "The initial compromise was ordinary software failure. Every amplifying step afterwards was an authority "
    "property: standing credentials, unconstrained reach, undeclared channels, and no bound on the number of "
    "mediated attempts. Trust by Construction does not claim to prevent conventional vulnerabilities; it aims "
    "to prevent an intelligence-layer compromise from automatically becoming institutional authority. The "
    "repository publishes this reading as a machine-checked map that assigns each reported stage to a "
    "mediated control, a deployment requirement, or a platform property the architecture does not supply. "
    "Five of the fourteen mapped stages are not mediated locally, and the map is tested to keep them visible."
)

COVERT = (
    "A second body of evidence constrains the design in a different direction. Anti-scheming work trained "
    "reasoning models against an explicit specification and reported roughly a thirty-fold reduction in "
    "covert actions across twenty-six held-out agentic evaluations, while also reporting residual cases under "
    "further red-teaming and partial attribution to the model recognising that it was being evaluated [21]. "
    "Studies of agentic misalignment across sixteen frontier models found insider-threat behaviour under goal "
    "conflict and threatened replacement [23]. The multi-organisation position on chain-of-thought "
    "monitorability describes reasoning transparency as a real but fragile signal that training pressure can "
    "erode [22]. Policy analysis through 2026 draws the operational conclusion that autonomy risk is "
    "near-term engineering work rather than speculation [25]. The architectural consequence is narrow and "
    "testable. A monitor is worth deploying, but it must never be worth compromising: authorisation must "
    "depend on neither the acting model's nor the reviewing model's judgment, and a detector that could "
    "restore privilege would itself become the escalation path."
)

STOP = (
    "Three controls added in this revision answer questions operators ask before deployment. The first is "
    "whether a workload can be stopped and whether the stop holds. The stop commits its authority change "
    "before attempting to write evidence: every agent is revoked, every task is quarantined and every epoch "
    "advances in one durable transaction. If the evidence writer then fails, the call reports that the "
    "workload is stopped and that evidence was not recorded, rather than unwinding the stop, because a "
    "failure in the assurance plane must not restore authority. The flag survives closing and reopening the "
    "service, and resumption never revives a previous identity: recovery requires a named operator, a new "
    "task and a fresh lease. The limit is stated plainly. This stops declared authority in a local control "
    "service, not operating-system processes, and it assumes the control database lies outside the model's "
    "write authority."
)

DELIVERY = (
    "The second question is whether revocation reaches output that is already in flight. An approved artifact "
    "is delivered against a binding re-resolved at every chunk boundary: recipient identity, task epoch, "
    "destination scope, expiry, workload stop state and source quarantine. Revocation, automatic contraction, "
    "expiry, an emergency stop or a source quarantine therefore denies the remainder of a partially delivered "
    "artifact, and the bulk path cannot be used to bypass a stream in progress. Delivery is exact-byte and "
    "single-use: a completed delivery cannot be replayed and a different recipient cannot collect it. Bytes "
    "already committed are not recalled, and the implementation does not pretend otherwise. This is staged "
    "artifact delivery, not live token generation over a qualified network transport."
)

MONITOR = (
    "The third control follows from the alignment results directly. An AI monitor receives a snapshot "
    "containing task metadata and the current evidence head, never protected text, and returns a three-field "
    "finding drawn from a fixed vocabulary. A finding may move a task toward READ_ONLY or QUARANTINED and may "
    "do nothing else. A clear verdict is recorded as an observation and changes no authority, so a monitor "
    "that has been deceived, or that is itself pursuing an undisclosed objective, cannot return privilege to "
    "a restricted workload. Findings are bound to a fresh evidence head, are single-use, and are rejected "
    "when forged, stale, replayed, submitted under another role, or carrying additional fields such as an "
    "approval. Restoration remains a named human action within the original ceiling. This is not a claim to "
    "detect scheming. It is a claim that a detection failure does not become an escalation path."
)

VALIDITY_SUFFIX = (
    " The three controls added in this revision are tested as deterministic local scenarios over the declared "
    "interface; they do not reproduce frontier-model propensities, and the incident map is an architectural "
    "reading of a public disclosure rather than a reconstruction or a claim that any real breach was "
    "preventable. The workload stop bounds declared authority, not host processes. The monitor interface "
    "bounds what a monitor can do to authority; it does not make a monitor accurate."
)

ARTIFACT_SUFFIX = (
    " The controls added in this revision run with python -m pytest tests/test_frontier_controls.py "
    "tests/test_incident_map.py, and the incident reading is published as docs/THREAT_MODEL_2026.md with its "
    "machine-checked form in audit/incident-map.json."
)

SDK_SUFFIX = (
    " This revision adds emergency_stop() and resume_workload() for operators, collect_release() and "
    "collect_chunk() for authenticated recipients, and monitor_snapshot() with apply_monitor_finding() for a "
    "separately deployed AI monitor that may contract authority and can never grant it."
)

ISOLATION = (
    "A reviewer of the previous revision made the decisive objection: every control above rests on the "
    "assumption that the model runtime reaches the control plane only through mediation, and that assumption "
    "was prose. An assumption nobody checks is the most dangerous component in an architecture, because it "
    "has no owner and no failure mode. This revision does not implement host isolation, which belongs to the "
    "deployment, but it stops assuming it. Seven required properties and one advisory property are probed "
    "against the live host: whether the agent identity can write the control database, whether it shares an "
    "operating-system identity with the control service, whether it can modify the enforcement package, "
    "whether the instance metadata service answers, whether a projected service-account token is readable, "
    "whether a declared canary address is reachable, whether standing credential material sits in the agent "
    "environment, and whether a kernel sandbox confines the process. Each measurement returns satisfied, "
    "violated, or not measurable, and not measurable is never counted as success: a host that declares no "
    "egress canary has an open default-deny requirement, not a satisfied one. A host qualifies as production "
    "only when every required property is measured satisfied, the evidence is less than a day old, and it "
    "names an operator and a host. The development machine and the continuous-integration runner used for "
    "this work both report reference, and a test exists whose only purpose is to fail if they ever stop "
    "doing so."
)

TRANSPORT = (
    "The destination contract decided what could be contacted and then opened no socket, so address pinning, "
    "certificate verification, redirect handling and byte ceilings were adapter obligations written in prose. "
    "They are now performed. The transport connects to the pinned literal address with no name-service lookup "
    "of any kind, so a resolver answer obtained after authorisation cannot move the connection; it verifies "
    "the hostname, enforces a protocol-version floor and compares the peer's public key against declared "
    "pins; it returns a redirect to the authorisation layer instead of following it; it refuses chunked and "
    "duplicated framing, where intermediaries disagree about message boundaries; and it enforces the byte "
    "ceiling during the read, so a peer that understates its length cannot overrun the budget. Every one of "
    "those properties is exercised against a real handshake with a controlled peer. That peer is a loopback "
    "server, and the evidence says so: a qualification marker propagates from the destination policy through "
    "the transport record into the promotion gate, which refuses to accept harness evidence as production "
    "transport evidence. The code path is qualified; the network is not."
)

SUPPLY = (
    "The threat classes that matured through 2025 and 2026 target the tool surface rather than the model "
    "[10,11]. A tool description is prose the model reads as instruction, so a server that writes "
    "instructions into a description has issued them without being called; a server can present a benign "
    "tool for review and redefine it afterwards; a second server can claim a name the first already uses and "
    "win resolution; and a chain that has read untrusted content can reach a privileged tool with nothing "
    "forged at all. The same rule answers all four. Tools exist only as server-qualified names and a bare "
    "name does not resolve, because the ambiguity is the attack and refusing to guess is the fix. Every byte "
    "a model will read about a tool is hashed at approval and compared at every offer, so a later "
    "redefinition is drift and drift quarantines the tool until a named human approves the new definition. A "
    "server that rotates its identity loses every approval it held. Descriptions are scanned for "
    "instruction-shaped content before approval, and a flagged description may still be approved knowingly, "
    "by a named person, with the acceptance recorded. A call chain that has absorbed an untrusted source is "
    "permanently tainted and cannot reach a privileged tool, which is the control-flow and data-flow "
    "separation argued for in [2] applied to the tool catalogue rather than to the prompt."
)

SETTLEMENT = (
    "Three further boundaries are now enforced rather than deferred. A local transaction cannot make a remote "
    "effect exactly-once, because the call that times out may have succeeded; outbound effects therefore "
    "carry a key derived from the approved decision, record their intent durably before the call, and treat "
    "an unacknowledged call as uncertain, which is a state rather than an error to swallow. An uncertain "
    "effect is never retried blindly, is reconciled against the provider by key, and blocks the work that "
    "depends on it until it settles; a provider offering no lookup leaves a permanent uncertain remainder "
    "that the report states rather than resolving by assumption. Authority crossing a service boundary is "
    "carried by a signed, audience-bound, single-use, depth-limited grant whose scope is intersected with the "
    "receiving service's own ceiling, never merged, so a grant can permit part of what a service already "
    "holds and can never teach it something new. An evidence chain kept by one custodian is exactly as "
    "trustworthy as that custodian, so a head counts as attested only on independent co-signatures above a "
    "threshold, and two witnesses attesting different heads at one sequence is reported as a fork rather "
    "than averaged away. Promotion to production requires all of it, fresh and together, and names every "
    "missing item rather than returning a verdict."
)

MONITOR_QUALITY = (
    "The monitor can now be measured rather than described. Labelled held-out trajectories are run through "
    "the runtime against a denial oracle, a blind monitor that clears everything, and a hostile monitor that "
    "clears every attack and restricts every ordinary task, with false restriction, missed attacks, latency, "
    "retained utility and adaptive evasion reported with denominators and intervals. The result that matters "
    "is not any of those rates. Across all three monitors, including the one an adversary would install, no "
    "protected outcome changes: the hostile monitor costs all of the availability and none of the authority. "
    "The evasion figure is reported without flattery. An attacker who probes once, observes the refusal, and "
    "thereafter works strictly inside its granted envelope produces a history indistinguishable from ordinary "
    "work and evades every monitor reading a metadata-only snapshot [4,7]. That is expected, and it is "
    "affordable precisely because the envelope rather than the monitor is what bounds the attacker. Offline "
    "rates describe scripted monitors and are not detector accuracy; a live backend yields a report labelled "
    "as such, describing one model, one prompt and these trajectories, compared against no published "
    "benchmark."
)


REFERENCES = [
    "[21] B. Schoen et al., “Stress Testing Deliberative Alignment for Anti-Scheming Training,” 2025. "
    "https://arxiv.org/abs/2509.15541",
    "[22] T. Korbak et al., “Chain of Thought Monitorability: A New and Fragile Opportunity for AI "
    "Safety,” 2025. https://arxiv.org/abs/2507.11473",
    "[23] A. Lynch et al., “Agentic Misalignment: How LLMs Could Be Insider Threats,” 2025. "
    "https://arxiv.org/abs/2510.05179",
    "[24] Hugging Face, “Anatomy of a Frontier Lab Agent Intrusion: A Technical Timeline of the July 2026 "
    "Incident,” 2026. https://huggingface.co/blog/agent-intrusion-technical-timeline",
    "[25] D. Amodei, “The Adolescence of Technology,” essay, 2026. "
    "https://darioamodei.com/essay/the-adolescence-of-technology",
]

TABLE_ROWS = (
    (
        "Frontier-threat controls",
        "38 executed cases: durable stop, per-chunk reauthorisation, restrict-only monitoring, "
        "recorded blocked attempts",
        "Deterministic local scenarios over the declared interface; they do not replay frontier-model "
        "experiments or estimate real-world frequency",
    ),
    (
        "Deployment qualification",
        "Measured host isolation, transport qualified against a controlled TLS peer, tool-supply integrity, "
        "settlement of outbound effects, witnessed evidence and an evidence-gated promotion decision",
        "Measuring an assumption is not supplying it; loopback transport evidence and a reference isolation "
        "verdict both refuse promotion, and no production deployment was qualified",
    ),
    (
        "Monitor quality",
        "Held-out benign and adversarial trajectories against oracle, blind and hostile monitors; no monitor "
        "changes a protected outcome",
        "Offline rates describe scripted monitors and are not detector accuracy; an attacker that stays "
        "inside its envelope evades a metadata-only monitor by construction",
    ),
)


def text_of(node) -> str:
    return ''.join(t.text or '' for t in node.iter(W + 't'))


def set_text(paragraph, value: str) -> None:
    """Keep the first run's formatting and drop the rest, as Word itself does."""
    runs = paragraph.findall(W + 'r')
    for run in runs[1:]:
        paragraph.remove(run)
    for node in runs[0].findall(W + 't'):
        runs[0].remove(node)
    node = ET.SubElement(runs[0], W + 't')
    node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    node.text = value


def clone(template, value: str):
    copied = copy.deepcopy(template)
    set_text(copied, value)
    return copied


def find(body, prefix: str):
    for index, node in enumerate(body):
        if node.tag == W + 'p' and text_of(node).startswith(prefix):
            return index, node
    raise ValueError(f'paragraph not found: {prefix!r}')


def _label(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def build(source: Path = SOURCE, target: Path = TARGET) -> dict:
    for prefix in NAMESPACES.items():
        ET.register_namespace(*prefix)
    with zipfile.ZipFile(source) as archive:
        document = archive.read('word/document.xml')
    root = ET.fromstring(document)
    body = root.find(W + 'body')

    set_text(find(body, 'Generative AI is moving')[1], ABSTRACT)
    index, intro = find(body, 'Learning institutions are a demanding setting')
    set_text(intro, INTRO)
    mechanisms = find(body, 'The underlying mechanisms are established')
    body.insert(mechanisms[0] + 1, clone(intro, COVERT))

    set_text(find(body, 'The SDK exposes request_context()')[1],
             text_of(find(body, 'The SDK exposes request_context()')[1]) + SDK_SUFFIX)
    validity = find(body, 'Threats to validity and deployment limits')[1]
    set_text(validity, text_of(validity) + VALIDITY_SUFFIX)
    artifact = find(body, 'Code, machine-readable authority profiles')[1]
    set_text(artifact, text_of(artifact) + ARTIFACT_SUFFIX)

    regression = find(body, 'Engineering verification distinguishes mechanism tests')[1]
    set_text(regression, text_of(regression).replace('Six contracts are verified',
                                                     'Thirty-one contracts are verified'))

    # Two new sections, inserted before the education section, which is renumbered.
    education_index, education = find(body, '6. Relevance to AI')
    set_text(education, text_of(education).replace('6. Relevance', '8. Relevance'))
    conclusion = find(body, '7. Conclusion')[1]
    set_text(conclusion, '9. Conclusion')
    body_template = find(body, 'The executable SDK now implements Passports')[1]
    inserted = [
        clone(education, '6. Stopping, Delivery and Monitoring When a Model May Be Covert'),
        clone(body_template, STOP),
        clone(body_template, DELIVERY),
        clone(body_template, MONITOR),
        clone(body_template, MONITOR_QUALITY),
        clone(education, '7. Measuring the Assumptions a Deployment Inherits'),
        clone(body_template, ISOLATION),
        clone(body_template, TRANSPORT),
        clone(body_template, SUPPLY),
        clone(body_template, SETTLEMENT),
    ]
    for offset, paragraph in enumerate(inserted):
        body.insert(education_index + offset, paragraph)

    table = next(node for node in body if node.tag == W + 'tbl')
    rows = table.findall(W + 'tr')
    last = rows[-1]
    cells = last.findall(W + 'tc')
    set_text(cells[1].find(W + 'p'), '1,375 tests passed; 31 source-bound capability contracts executed')
    set_text(cells[2].find(W + 'p'), 'Local functional evidence, including schema rejection, durable source '
             'quarantine, the added frontier controls and the deployment measurements; not operational '
             'certification')
    for values in TABLE_ROWS:
        added = copy.deepcopy(last)
        for cell, value in zip(added.findall(W + 'tc'), values, strict=True):
            set_text(cell.find(W + 'p'), value)
        table.append(added)

    reference_template = [node for node in body if text_of(node).startswith('[20] R. Srivastava')][0]
    position = list(body).index(reference_template) + 1
    for offset, reference in enumerate(REFERENCES):
        body.insert(position + offset, clone(reference_template, reference))

    review = json.loads((ROOT / 'paper/tbc-v13/revision-content.json').read_text())
    set_text(find(body, 'Generative AI is moving')[1], review['abstract'])
    set_text(find(body, 'Learning institutions are a demanding setting')[1], review['intro'])
    set_text(find(body, 'The underlying mechanisms are established')[1], review['foundations'])
    set_text(find(body, 'A second body of evidence')[1], review['covert'])
    set_text(find(body, 'Threats to validity and deployment limits')[1], review['validity'])
    set_text(find(body, 'The alignment is therefore concrete')[1], review['education_example'])
    p = find(body, 'Education sharpens the general problem')[1]
    set_text(p, text_of(p).replace('making institutional deployment safer', 'making institutional authority inspectable'))
    for prefix in ('The architecture is implemented as', 'Code, machine-readable authority profiles'):
        p = find(body, prefix)[1]
        set_text(p, text_of(p).replace(' [20]', ''))
    p = find(body, 'The third control follows')[1]
    set_text(p, text_of(p).replace('task metadata and the current evidence head, never protected text',
             'task metadata, the current evidence head and at most 32 recent allowlisted event types, never protected text'))
    set_text(p, text_of(p).replace('the current evidence head', 'task and global-control evidence heads'))
    index = list(body).index(p)
    body.insert(index + 1, clone(p, review['security_review']))
    # Old foundational and non-paper citations are replaced, not merely relabelled.
    template = copy.deepcopy(reference_template)
    for node in list(body):
        if node.tag == W + 'p' and text_of(node).startswith('['):
            body.remove(node)
    ref_index, _ = find(body, 'References')
    for offset, ref in enumerate(review['references']):
        value = f"[{ref['id']}] {ref['authors']}, {ref['title']}. Research preprint, {ref['year']}. {ref['url']}"
        body.insert(ref_index + 1 + offset, clone(template, value))
    updated = ET.tostring(root, encoding='UTF-8', xml_declaration=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Reuse each source entry's metadata so rebuilding the revision is byte-reproducible.
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as out:
        for item in archive.infolist():
            payload = updated if item.filename == 'word/document.xml' else archive.read(item.filename)
            out.writestr(item, payload)
    return {'source': _label(source), 'target': _label(target),
            'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
