"""Generate the proceedings paper's figures from the committed results.

The paper's prose is held to the generated results by
``tests/test_paper_alignment.py``. A chart is a claim surface too, and a more
persuasive one, so the figures are built the same way: every mark and every
number in every caption is read from ``evaluation/results/``. Nothing is typed.

Three figures are explanatory diagrams rather than charts: the architecture,
the ten steps of one governed request, and the lifecycle for building a new AI
capability. They carry no measured values, but they are generated here too so
that the paper has exactly one source for every figure and one ``--check``.

Hand-rolled SVG for the same reasons as ``generate_figures.py``: no plotting
dependency, so the figures regenerate on the same disconnected laptop as the
results; and the output is text, so ``--check`` can compare it byte for byte.
Unlike the deck's charts these are print figures: a fixed light palette, a
system sans, direct labels on every bar, and no reliance on hover.

    python scripts/generate_paper_figures.py           # write paper/figures/
    python scripts/generate_paper_figures.py --check   # fail if they have drifted
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"
FIGURES = ROOT / "paper" / "figures"

# Print palette. One accent carries the architecture under test; comparison arms
# are a recessive grey, so the reader's eye goes to the claim. Status-like
# encodings (contained, bounded, residual) use an ordinal blue pair and one
# contrasting hue, validated for colour-vision deficiency, and always carry a
# direct label so colour is never the only channel.
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#77756f"
AXIS, GRID, SURFACE = "#c3c2b7", "#e8e7e1", "#ffffff"
ACCENT, ACCENT_DARK, ACCENT_LIGHT = "#2a78d6", "#184f95", "#6da7ec"
CONTRAST, COMPARE = "#eb6834", "#a8a79f"
WASH, PLANE = "#eef4fc", "#f4f3ef"
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
BAR_H = 16


def _load(name: str) -> dict:
    return json.loads((RESULTS / f"v1.0.0-{name}.json").read_text(encoding="utf-8"))


def _attr(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def text(x: float, y: float, content: object, *, size: float = 11, weight: int = 400,
         fill: str = INK, anchor: str = "start", extra: str = "") -> str:
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{escape(str(content))}</text>')


def rect(x: float, y: float, w: float, h: float, *, fill: str, stroke: str = "none",
         width: float = 1, rx: float = 6) -> str:
    return (f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx:g}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width:g}"/>')


def line(x1: float, y1: float, x2: float, y2: float, *, stroke: str = GRID,
         width: float = 1, extra: str = "") -> str:
    return (f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{stroke}" '
            f'stroke-width="{width:g}"{extra}/>')


def arrow_marker(marker_id: str) -> str:
    return (f'<defs><marker id="{marker_id}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{INK_2}"/></marker></defs>')


def flow(d: str, marker_id: str) -> str:
    return (f'<path d="{d}" fill="none" stroke="{INK_2}" stroke-width="1.5" '
            f'marker-end="url(#{marker_id})"/>')


def hbar(x: float, y: float, length: float, fill: str, tip: str, h: float = BAR_H) -> str:
    """A horizontal bar: square at the baseline, 4px rounded data end.

    Zero is the most important value in several of these figures, so it is drawn
    as a visible stub rather than omitted and mistaken for missing data.
    """
    if length < 1:
        return (f'<rect x="{x:g}" y="{y:g}" width="2" height="{h:g}" fill="{AXIS}">'
                f"<title>{escape(tip)}</title></rect>")
    r = min(4.0, length / 2, h / 2)
    end = x + length
    d = (f"M{x:g},{y:g} H{end - r:.1f} Q{end:.1f},{y:g} {end:.1f},{y + r:g} "
         f"V{y + h - r:g} Q{end:.1f},{y + h:g} {end - r:.1f},{y + h:g} H{x:g} Z")
    return f'<path d="{d}" fill="{fill}"><title>{escape(tip)}</title></path>'


def svg(width: int, height: int, label: str, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{_attr(label)}" '
        f'font-family="{FONT}">\n<title>{escape(label)}</title>\n'
        f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>\n'
        + "\n".join(body) + "\n</svg>\n"
    )


def _nice_ceiling(value: float) -> float:
    magnitude = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if step * magnitude >= value:
            return step * magnitude
    return 10 * magnitude


def _lines(x: float, y: float, rows: tuple[str, ...], *, size: float = 10,
           step: float = 15, fill: str = INK_2) -> list[str]:
    return [text(x, y + index * step, row, size=size, fill=fill)
            for index, row in enumerate(rows)]


# ---------------------------------------------------------------------------
# The architecture
# ---------------------------------------------------------------------------

def figure_architecture(figures: dict) -> tuple[str, str]:
    fields = figures["control_contract_fields"]
    marker = "arch-arrow"
    body = [
        arrow_marker(marker),
        # The boundary wraps everything the institution runs.
        rect(0, 0, 58, 538, fill=PLANE, stroke=AXIS),
        text(0, 0, "BOUNDARY PLANE", size=10.5, weight=700, anchor="middle",
             extra=' transform="translate(24,269) rotate(-90)"'),
        text(0, 0, "authenticated ingress and egress, quarantine, one-way seam",
             size=9.5, fill=INK_2, anchor="middle",
             extra=' transform="translate(41,269) rotate(-90)"'),
        # Untrusted intelligence and its components.
        rect(76, 0, 684, 96, fill=PLANE, stroke=AXIS),
        text(92, 22, "INTELLIGENCE PLANE  -  untrusted", size=12, weight=700),
        text(92, 40, "Declared identifiers tokenized; inference remains possible. "
             "Isolation must protect credentials and keys.", size=10.5, fill=INK_2),
    ]
    chips = (("Semantic router", "advisory: intent + sensitivity"),
             ("Attested local model", "default for restricted data"),
             ("Approved cloud model", "low-sensitivity work only"),
             ("Agents and retrieval", "retrieved text is data"))
    chip_w = (684 - 32 - 3 * 10) / 4
    for index, (name, note) in enumerate(chips):
        cx = 92 + index * (chip_w + 10)
        body.append(rect(cx, 50, chip_w, 36, fill=SURFACE, stroke=AXIS, rx=5))
        body.append(text(cx + 9, 65, name, size=10, weight=700))
        body.append(text(cx + 9, 79, note, size=8.8, fill=MUTED))

    body += [
        rect(76, 126, 684, 58, fill=WASH, stroke=ACCENT, width=1.5),
        text(92, 146, f"CONTROL CONTRACT  -  {fields} fields per consequential capability",
             size=11.5, weight=700, fill=ACCENT_DARK),
    ]
    chip_x = 92.0
    for label in ("asset", "operation", "enforcement point", "owner", "failure test",
                  "evidence", "failure response"):
        width = len(label) * 5.4 + 16
        body.append(rect(chip_x, 156, width, 19, fill=SURFACE, stroke=ACCENT_LIGHT, rx=9.5))
        body.append(text(chip_x + width / 2, 169, label, size=9.5, anchor="middle"))
        chip_x += width + 8

    body += [
        rect(76, 216, 180, 120, fill=PLANE, stroke=AXIS),
        text(90, 237, "AUTHORITY PLANE", size=11, weight=700),
        *_lines(90, 256, ("Purpose-, time-, and", "holder-bound grants;",
                          "approvals; model manifests;", "key custody; delegation",
                          "only narrows")),
        rect(276, 216, 232, 120, fill=SURFACE, stroke=ACCENT_DARK, width=2),
        text(290, 237, "EXECUTION PLANE  -  Rule 1", size=11, weight=700),
        *_lines(290, 256, ("Rechecks policy, identity, version,",
                           "approval, and replay; binds the",
                           "exact proposal digest; local atomicity,",
                           "external reconciliation.")),
        text(290, 325, "Sole holder of the write credential", size=9.5, weight=700,
             fill=ACCENT_DARK),
        rect(528, 216, 232, 120, fill=SURFACE, stroke=ACCENT_DARK, width=2),
        text(542, 237, "CONTEXT GATE  -  Rule 2", size=11, weight=700),
        *_lines(542, 256, ("Checks grant, purpose, consent,",
                           "zone, and model attestation;",
                           "tokenizes PII; labels every output;",
                           "restores identity only if entitled.")),
        text(542, 325, "Sole holder of record access and keys", size=9.5, weight=700,
             fill=ACCENT_DARK),
        rect(76, 384, 180, 82, fill=PLANE, stroke=AXIS),
        text(90, 405, "EVIDENCE PLANE", size=11, weight=700),
        *_lines(90, 425, ("Binds intent to outcome;", "receipts from both mediators;",
                          "digests and sensitive metadata")),
        rect(276, 384, 484, 82, fill=PLANE, stroke=AXIS),
        text(290, 405, "GOVERNED DATA PLANE", size=11, weight=700),
        *_lines(290, 425, ("Per-subject encryption; key deletion has limits on "
                           "retained copies.",
                           "Stable identifiers, replayable events, versioned snapshots.",
                           "Read only through the gate; changed only by the executor.")),
        rect(76, 486, 684, 52, fill=PLANE, stroke=AXIS),
        text(92, 517, "RESILIENCE PLANE", size=11, weight=700),
        text(222, 517, "Fails secure, revokes, reconciles uncertain effects, and routes "
             "work to a manual fallback.", size=10, fill=INK_2),
        # Flows, drawn last so they visibly cross the contract band: nothing the
        # model emits reaches a mediator except through a contracted capability.
        # A request enters the contract band and leaves it towards a mediator;
        # the segments stop at the band so no arrow runs through its labels.
        flow("M392,96 V125", marker),
        flow("M392,184 V215", marker),
        text(384, 115, "proposes an action", size=9.5, fill=INK_2, anchor="end"),
        flow("M600,96 V125", marker),
        flow("M600,184 V215", marker),
        text(592, 115, "requests data", size=9.5, fill=INK_2, anchor="end"),
        flow("M700,216 V97", marker),
        text(692, 204, "labelled output", size=9.5, fill=INK_2, anchor="end"),
        flow("M256,276 H275", marker),
        flow("M166,336 V354 H600 V337", marker),
        text(470, 349, "grants, approvals, keys", size=9.5, fill=INK_2, anchor="middle"),
        flow("M392,336 V383", marker),
        text(400, 377, "one checked write", size=9.5, fill=INK_2),
        flow("M720,384 V337", marker),
        text(712, 377, "decrypt after authorization", size=9.5, fill=INK_2, anchor="end"),
        text(76, 558, "Heavy blue outline: a mediator holding what the model lacks. "
             "Mediators, contract, keys, and evidence store form the declared trusted "
             "base.", size=9.5, fill=MUTED),
    ]
    caption = (
        "Target deployment architecture, conditional on trusted-service isolation. Intelligence works "
        "on vault tokens and can only propose actions and request data. Every request "
        f"crosses the {fields}-field control contract to one of two mediators, each the "
        "sole holder of what the model lacks: the execution plane holds the write "
        "credential (Rule 1); the context gate holds record access and data keys "
        "(Rule 2). The semantic router advises which attested model to use; the gate "
        "decides where data may go. Logical planes do not prove process isolation or full API integration."
    )
    label = "Seven-plane reference architecture with two mediators around a control contract"
    return svg(760, 566, label, body), caption


# ---------------------------------------------------------------------------
# One governed request in ten steps
# ---------------------------------------------------------------------------

#: (name, plane, two description lines, guarantee, kind). ``kind`` is
#: "mediator" for steps enforced by a component the model cannot bypass,
#: "model" for the one step untrusted intelligence performs, else "plane".
STEPS = (
    ("Admit", "BOUNDARY PLANE",
     ("Authenticate every caller and source; quarantine",
      "untrusted content so it is handled as data, not code."),
     "Authenticate at each supported interface.", "plane"),
    ("Protect", "GOVERNED DATA PLANE",
     ("Detect personal data and replace it with vault tokens;",
      "encrypt sensitive fields under per-subject keys."),
     "Tokenization is not anonymity.", "mediator"),
    ("Route", "INTELLIGENCE PLANE, ADVISORY",
     ("Classify intent and sensitivity; choose the cheapest",
      "attested model whose zone may process every class."),
     "Restricted data stays on local models.", "plane"),
    ("Entitle", "CONTEXT GATE",
     ("Check signed grant, purpose, consent, revocation,",
      "zone, and attestation; decrypt the minimum fields."),
     "No entitlement, no read.", "mediator"),
    ("Reason", "INTELLIGENCE PLANE, UNTRUSTED",
     ("The model drafts or proposes over tokens and labelled",
      "context. It holds no key, token map, or credential."),
     "An output is a proposal, never a power.", "model"),
    ("Authorize", "AUTHORITY PLANE",
     ("Approve the exact proposal digest within declared",
      "review capacity; delegated authority only narrows."),
     "Authority cannot be manufactured.", "plane"),
    ("Execute", "EXECUTION PLANE",
     ("Recheck policy, identity, version, approval, and",
      "replay; make one write and issue external reconciliation."),
     "Local replay bound; external effects uncertain.", "mediator"),
    ("Release", "CONTEXT GATE",
     ("Label the output by everything it used; restore real",
      "values only for a recipient entitled to see them."),
     "Release checks cover supported paths.", "mediator"),
    ("Record", "EVIDENCE PLANE",
     ("Bind intent to outcome in an append-only chain that",
      "stores digests and access-controlled metadata."),
     "Missing evidence requires reconciliation.", "plane"),
    ("Recover", "RESILIENCE PLANE",
     ("Revoke, reconcile uncertain effects, fall back to",
      "manual work, and verify deletion across known copies."),
     "Recovery and erasure require qualification.", "plane"),
)


def figure_request_steps(figures: dict) -> tuple[str, str]:
    marker = "steps-arrow"
    card_w, card_h, gap = 370, 86, 14
    body = [arrow_marker(marker)]
    for index, (name, plane, description, guarantee, kind) in enumerate(STEPS):
        column, row = divmod(index, 5)
        x = column * (card_w + 20)
        y = row * (card_h + gap)
        fill = PLANE if kind == "model" else SURFACE
        stroke, width = (ACCENT_DARK, 2) if kind == "mediator" else (AXIS, 1)
        circle = MUTED if kind == "model" else (ACCENT_DARK if kind == "mediator" else ACCENT)
        body += [
            rect(x, y, card_w, card_h, fill=fill, stroke=stroke, width=width),
            f'<circle cx="{x + 22}" cy="{y + 22}" r="13" fill="{circle}"/>',
            text(x + 22, y + 26.5, index + 1, size=11.5, weight=700, fill=SURFACE,
                 anchor="middle"),
            text(x + 44, y + 23, name, size=12.5, weight=700),
            text(x + card_w - 12, y + 22, plane, size=8.5, weight=700, fill=MUTED,
                 anchor="end"),
            *_lines(x + 44, y + 42, description, size=10, step=14.5),
            text(x + 44, y + 76, guarantee, size=10, weight=700,
                 fill=MUTED if kind == "model" else ACCENT_DARK),
        ]
        if row < 4:
            body.append(flow(f"M{x + 22},{y + card_h} V{y + card_h + gap - 1}", marker))
    last_left = 4 * (card_h + gap) + card_h / 2
    body.append(flow(f"M{card_w},{last_left} H{card_w + 10} V{card_h / 2} "
                     f"H{card_w + 19}", marker))
    height = 5 * card_h + 4 * gap
    caption = (
        "Target lifecycle in ten steps, requiring end-to-end integration evidence; "
        "only the domain pack changes what each step checks. Steps outlined in dark blue "
        "require independently enforced boundaries, qualified on the deployed stack. The grey step is the only "
        "one performed by untrusted intelligence, and it produces a proposal or a draft, "
        "never an effect or a disclosure."
    )
    label = "Ten steps of one governed request, from admission to recovery"
    return svg(760, int(height), label, body), caption


# ---------------------------------------------------------------------------
# The lifecycle for building any new AI capability
# ---------------------------------------------------------------------------

LIFECYCLE = (
    ("Frame", ("Name one consequential", "capability, its asset,", "harm, and owner."),
     "capability card", "an owner accepts it"),
    ("Contract", ("Fill all seven fields;", "an empty field is an", "open governance decision."),
     "control contract", "no field left empty"),
    ("Pack", ("Declare purposes, data", "classes, zones, recipients,",
              "transitions, and fallback."),
     "domain pack", "the pack validates"),
    ("Bind", ("Give credentials only to", "mediators; register and", "attest every model."),
     "bindings, manifests", "no model holds a key"),
    ("Falsify", ("Attack it on synthetic data:", "hostile scenarios, ablation,",
                 "bounded checks."),
     "evidence run", "zero counterexamples"),
    ("Promote", ("Rerun conformance on the", "target stack; deploy only", "on current evidence."),
     "release evidence", "fresh run matches"),
    ("Operate", ("Watch review capacity;", "revoke, reconcile, erase;", "exit any vendor."),
     "evidence ledger", "redress works"),
)


def figure_lifecycle(figures: dict) -> tuple[str, str]:
    marker = "life-arrow"
    card_w, card_h, gap, row_gap = 178, 138, 16, 40
    body = [arrow_marker(marker)]
    positions = [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1)]
    for index, ((name, description, artifact, gate), (column, row)) in enumerate(
            zip(LIFECYCLE, positions, strict=True)):
        x = column * (card_w + gap)
        y = row * (card_h + row_gap)
        stroke, width = (ACCENT_DARK, 2) if name == "Falsify" else (AXIS, 1)
        body += [
            rect(x, y, card_w, card_h, fill=SURFACE, stroke=stroke, width=width),
            f'<circle cx="{x + 20}" cy="{y + 21}" r="12" fill="{ACCENT}"/>',
            text(x + 20, y + 25.5, index + 1, size=11, weight=700, fill=SURFACE,
                 anchor="middle"),
            text(x + 40, y + 26, name, size=12.5, weight=700),
            *_lines(x + 12, y + 51, description, size=9.8, step=14),
            line(x + 12, y + 92, x + card_w - 12, y + 92, stroke=GRID),
            text(x + 12, y + 108, f"Artifact: {artifact}", size=9.5, fill=INK_2),
            text(x + 12, y + 124, f"Gate: {gate}", size=9.5, weight=700, fill=ACCENT_DARK),
        ]
        if index in (0, 1, 2, 4, 5):
            body.append(flow(f"M{x + card_w},{y + card_h / 2} H{x + card_w + gap - 1}",
                             marker))
    third = 3 * (card_w + gap)
    body.append(flow(f"M{third + card_w / 2},{card_h} V{card_h + row_gap / 2} "
                     f"H{card_w / 2} V{card_h + row_gap - 1}", marker))
    loop_x, loop_y = third, card_h + row_gap
    body += [
        flow(f"M{2 * (card_w + gap) + card_w},{loop_y + card_h / 2} H{loop_x - 1}", marker),
        rect(loop_x, loop_y, card_w, card_h, fill=WASH, stroke=ACCENT, width=1.5),
        text(loop_x + card_w / 2, loop_y + 28, "Any change returns to 5", size=11.5,
             weight=700, fill=ACCENT_DARK, anchor="middle"),
    ]
    for offset, row in enumerate(("A new model, vendor, pack,", "or backend inherits no",
                                  "assurance. The same", "falsifiers run again and",
                                  "the evidence is regenerated.")):
        body.append(text(loop_x + card_w / 2, loop_y + 54 + offset * 15, row, size=9.8,
                         fill=INK_2, anchor="middle"))
    caption = (
        "Building any new AI capability. Each stage produces an artifact and must pass a "
        "gate before the next begins. Falsification happens on synthetic data before real "
        "records or keys are connected, and any later change to a model, vendor, pack, or "
        "backend returns to stage 5, so assurance is regenerated rather than inherited."
    )
    label = "Seven-stage lifecycle for building and operating a governed AI capability"
    return svg(760, 2 * card_h + row_gap, label, body), caption


# ---------------------------------------------------------------------------
# Containment by architecture, three suites
# ---------------------------------------------------------------------------

ARM_LABELS = ("No mediation", "Conventional control", "Mediated (this work)")


def figure_containment(figures: dict) -> tuple[str, str]:
    comparison = _load("architecture-comparison")
    disclosure = _load("governed-disclosure")
    delegation = _load("delegation")

    actions = [(a["attacks_attempted"] - a["attacks_succeeded"], a["attacks_attempted"])
               for a in comparison["arms"]]
    flows_total = sum(p["summary"]["hostile_scenarios"] for p in disclosure["profiles"])
    flows = [
        (sum(p["summary"]["contained_by_arm"][arm] for p in disclosure["profiles"]), flows_total)
        for arm in ("unguarded", "access_controlled", "this_architecture")
    ]
    chains = [(delegation["arms"][arm]["contained"], delegation["arms"][arm]["of"])
              for arm in ("unguarded", "caller_checked", "this_architecture")]
    panels = [
        ("(a) Hostile actions", f"n = {actions[0][1]} attacks", actions),
        ("(b) Hostile data flows", f"n = {flows_total} flows, {len(disclosure['profiles'])} packs",
         flows),
        ("(c) Hostile delegation chains", f"n = {chains[0][1]} risk classes", chains),
    ]

    label_w, panel_w, track = 150, 203, 128
    top, row = 62, 34
    body = []
    for index, name in enumerate(ARM_LABELS):
        y = top + index * row
        weight = 700 if index == 2 else 400
        body.append(text(label_w - 12, y + 12.5, name, size=11, weight=weight, anchor="end"))

    for p, (title, subtitle, values) in enumerate(panels):
        x0 = label_w + 8 + p * panel_w
        body.append(text(x0, 16, title, size=11.5, weight=700))
        body.append(text(x0, 33, subtitle, size=9.5, fill=MUTED))
        axis_bottom = top + 3 * row - 8
        for share in (0, 0.5, 1):
            gx = x0 + share * track
            body.append(line(gx, top - 10, gx, axis_bottom,
                             stroke=AXIS if share == 0 else GRID))
            body.append(text(gx, axis_bottom + 14, f"{share:.0%}", size=9, fill=MUTED,
                             anchor="middle"))
        for index, (contained, total) in enumerate(values):
            y = top + index * row
            length = track * contained / total
            fill = ACCENT if index == 2 else COMPARE
            tip = f"{ARM_LABELS[index]}: {contained} of {total} contained"
            body.append(hbar(x0, y, length, fill, tip))
            body.append(text(x0 + max(length, 2) + 6, y + 12.5, f"{contained}/{total}",
                             size=10.5, weight=700 if index == 2 else 400))
    body.append(text(label_w - 12, top + 3 * row + 6, "share contained", size=9,
                     fill=MUTED, anchor="end"))

    arms = comparison["arms"]
    harms = [sum(arm["harms"].values()) for arm in arms]
    benign = arms[0]
    caption = (
        "Containment across three independent suites. Each panel sends identical hostile "
        "inputs to no mediation, a conventional control, and this architecture. "
        "(a) Actions: the conventional arm is a safety prompt with a per-agent tool "
        f"allowlist; {harms[0]}, {harms[1]}, and {harms[2]} harmful actions reached the "
        f"protected asset, and every arm completed {benign['benign_completed']} of "
        f"{benign['benign_attempted']} benign tasks. (b) Data flows: the conventional arm "
        "uses signed class-cleared grants and checks the model's claimed output label; "
        f"{figures['disclosure_benign_completed']} of {figures['disclosure_benign_total']} "
        "legitimate flows completed under the context gate. (c) Delegation: the "
        "conventional arm validates each hop against its immediate caller; a benign "
        "two-hop chain completes in every arm."
    )
    label = "Share of hostile actions, data flows, and delegation chains contained by architecture"
    return svg(760, top + 3 * row + 16, label, body), caption


# ---------------------------------------------------------------------------
# Review capacity
# ---------------------------------------------------------------------------

def figure_oversight(figures: dict) -> tuple[str, str]:
    queue = _load("oversight")
    assisted = _load("assisted-review")
    uncontrolled = queue["arms"]["no_load_control"]
    controlled = queue["arms"]["declared_load_control"]
    dependent = assisted["arms"]["assisted_dependent_lowered_floor"]
    independent = assisted["arms"]["assisted_independent_lowered_floor"]
    lowered = dependent["deliberation_floor_seconds"]
    rows = [
        ("Unaided, no load control", uncontrolled),
        ("Unaided, declared load control", controlled),
        (f"Assisted at {lowered:g} s floor, dependent", dependent),
        (f"Assisted at {lowered:g} s floor, independent", independent),
    ]
    benign_total = queue["arrivals"] - uncontrolled["merit_refusals_required"]
    harm_max = _nice_ceiling(max(arm["harmful_executed"] for _, arm in rows) or 1)

    label_w, top, row = 232, 58, 32
    panels = [
        (label_w + 10, 170, "(a) Merit failures executed", "lower is better",
         harm_max, lambda arm: arm["harmful_executed"],
         lambda arm: str(arm["harmful_executed"])),
        (label_w + 262, 150, "(b) Legitimate work completed",
         f"of {benign_total} benign arrivals",
         benign_total, lambda arm: arm["benign_executed"],
         lambda arm: f"{arm['benign_executed']}" + (
             f"  ({arm['deferred_to_manual_fallback']} deferred to manual)"
             if arm["deferred_to_manual_fallback"] else "")),
    ]
    body = []
    for index, (name, _) in enumerate(rows):
        body.append(text(label_w - 10, top + index * row + 12.5, name, size=11, anchor="end"))
    divider = top + 2 * row - 8
    body.append(line(0, divider, 760, divider, stroke=GRID))
    for x0, track, title, subtitle, domain, value, shown in panels:
        body.append(text(x0, 16, title, size=11.5, weight=700))
        body.append(text(x0, 33, subtitle, size=9.5, fill=MUTED))
        axis_bottom = top + len(rows) * row - 8
        body.append(line(x0, top - 10, x0, axis_bottom, stroke=AXIS))
        body.append(line(x0 + track, top - 10, x0 + track, axis_bottom, stroke=GRID))
        body.append(text(x0, axis_bottom + 14, "0", size=9, fill=MUTED, anchor="middle"))
        body.append(text(x0 + track, axis_bottom + 14, f"{domain:g}", size=9, fill=MUTED,
                         anchor="middle"))
        for index, (name, arm) in enumerate(rows):
            y = top + index * row
            length = track * value(arm) / domain
            body.append(hbar(x0, y, length, ACCENT, f"{name}: {shown(arm)}"))
            body.append(text(x0 + max(length, 2) + 6, y + 12.5, shown(arm), size=10.5))

    caption = (
        f"Human review as a bounded resource. In the queue trial, {queue['arrivals']} "
        "arrivals reach one reviewer with a declared attentive capacity of "
        f"{queue['reviewer_model']['attentive_until']}; "
        f"{uncontrolled['merit_refusals_required']} proposals are valid in form but wrong on "
        f"merit. Declared load control stops {uncontrolled['harmful_executed']} merit "
        f"failures from executing at the cost of {controlled['deferred_to_manual_fallback']} "
        f"deferrals. Adding a review assistant and lowering the floor to {lowered:g} s restores "
        f"throughput; a dependent assistant lets {dependent['harmful_executed']} failures "
        f"through and an independent one {independent['harmful_executed']}, so the dependent "
        "configuration is refused before it starts. Reviewer behaviour is modelled by "
        "declared, adjustable parameters."
    )
    label = "Merit failures executed and legitimate work completed under four review configurations"
    return svg(760, top + len(rows) * row + 16, label, body), caption


# ---------------------------------------------------------------------------
# One kernel, six packs
# ---------------------------------------------------------------------------

PACK_NAMES = {
    "student-support": "Student support",
    "academic-record-correction": "Academic record correction",
    "corporate-confidential-data": "Corporate confidential data",
    "healthcare-record-access": "Healthcare record access",
    "financial-consumer-data": "Consumer financial data",
    "government-benefits": "Government benefits",
}


def figure_domain_packs(figures: dict) -> tuple[str, str]:
    packs = _load("domain-pack-matrix")["profiles"]
    label_w, top, row, track = 200, 62, 28, 210
    x0 = label_w + 10
    domain = _nice_ceiling(max(p["states_explored"] for p in packs))
    columns = ((560, "Hostile", "contained"), (640, "Benign", "completed"),
               (722, "Unauthorized", "mutations"))
    body = [
        text(x0, 16, "(a) Bounded configurations explored", size=11.5, weight=700),
        text(x0, 33, "zero invariant violations in every pack", size=9.5, fill=MUTED),
        text(522, 16, "(b) Scenario outcomes", size=11.5, weight=700),
    ]
    for cx, first, second in columns:
        body.append(text(cx, 38, first, size=9.5, fill=MUTED, anchor="middle"))
        body.append(text(cx, 50, second, size=9.5, fill=MUTED, anchor="middle"))
    axis_bottom = top + len(packs) * row - 6
    step = 10 ** math.floor(math.log10(domain))
    for tick in range(0, int(domain) + 1, step):
        gx = x0 + track * tick / domain
        body.append(line(gx, top - 8, gx, axis_bottom, stroke=AXIS if tick == 0 else GRID))
        body.append(text(gx, axis_bottom + 14, f"{tick:,.0f}", size=9, fill=MUTED,
                         anchor="middle"))
    for index, pack in enumerate(packs):
        y = top + index * row
        name = PACK_NAMES.get(pack["profile_id"], pack["profile_id"])
        body.append(text(label_w - 8, y + 12.5, name, size=11, anchor="end"))
        length = track * pack["states_explored"] / domain
        body.append(hbar(x0, y, length, ACCENT,
                         f"{name}: {pack['states_explored']:,} configurations"))
        body.append(text(x0 + max(length, 2) + 6, y + 12.5, f"{pack['states_explored']:,}",
                         size=10.5))
        cells = (f"{pack['scenarios_contained']}/{pack['scenarios_total']}",
                 f"{pack['benign_completed']}/{pack['benign_total']}",
                 str(pack["unauthorized_mutations"]))
        for (cx, _, _), cell in zip(columns, cells, strict=True):
            body.append(text(cx, y + 12.5, cell, size=10.5, anchor="middle"))

    total_y = axis_bottom + 34
    body.append(line(0, total_y - 16, 760, total_y - 16, stroke=AXIS))
    body.append(text(label_w - 8, total_y, "All six packs", size=11, weight=700, anchor="end"))
    body.append(text(x0, total_y, f"{figures['domain_pack_states_explored_display']} "
                     "configurations", size=10.5, weight=700))
    totals = (f"{figures['domain_pack_scenarios_contained']}/{figures['domain_pack_scenarios_total']}",
              f"{figures['domain_pack_benign_completed']}/{figures['domain_pack_benign_total']}",
              str(figures["domain_pack_unauthorized_mutations"]))
    for (cx, _, _), cell in zip(columns, totals, strict=True):
        body.append(text(cx, total_y, cell, size=10.5, weight=700, anchor="middle"))

    caption = (
        f"One kernel, {figures['domains_verified']} domain packs. Each pack is verified "
        "independently against its own denominators: bounded configurations explored with "
        "zero invariant violations (a), and hostile scenarios contained, benign tasks "
        "completed, and unauthorized mutations (b). Across all packs: "
        f"{figures['domain_pack_states_explored_display']} configurations, "
        f"{figures['domain_pack_scenarios_contained']} of "
        f"{figures['domain_pack_scenarios_total']} hostile scenarios contained, and "
        f"{figures['domain_pack_benign_completed']} of {figures['domain_pack_benign_total']} "
        "benign tasks completed. A new sector replaces the pack and regenerates its own "
        "evidence; the kernel is unchanged."
    )
    label = "Bounded configurations and scenario outcomes for six domain packs"
    return svg(760, total_y + 12, label, body), caption


# ---------------------------------------------------------------------------
# Evidence against the safety case
# ---------------------------------------------------------------------------

STATUS = (("contained", ACCENT_DARK), ("bounded", ACCENT_LIGHT), ("residual", CONTRAST))


def figure_evidence(figures: dict) -> tuple[str, str]:
    catalogue = _load("threat-catalogue")["summary"]
    thesis = _load("mediation-thesis")
    families = catalogue["by_family"]

    body = [
        text(0, 16, "(a) Threat and alignment catalogue", size=11.5, weight=700),
        text(0, 33, f"{catalogue['threats']} failure classes by family", size=9.5, fill=MUTED),
    ]
    legend_x = 0.0
    legend = {"residual": "research agenda"}
    for status, colour in STATUS:
        name = legend.get(status, status)
        body.append(rect(legend_x, 44, 10, 10, fill=colour, rx=2))
        body.append(text(legend_x + 14, 53, name, size=9.5, fill=INK_2))
        legend_x += 14 + len(name) * 5.4 + 16

    label_w, top, row, track = 96, 76, 34, 232
    x0 = label_w + 8
    domain = max(sum(counts.values()) for counts in families.values())
    unit = track / domain
    for index, (family, counts) in enumerate(families.items()):
        y = top + index * row
        total = sum(counts.values())
        body.append(text(label_w - 4, y + 12.5, f"{family.capitalize()} ({total})",
                         size=11, anchor="end"))
        x = x0
        for status, colour in STATUS:
            count = counts.get(status, 0)
            if not count:
                continue
            width = count * unit - 2  # 2px surface gap between segments
            body.append(f'<rect x="{x:.1f}" y="{y}" width="{width:.1f}" height="{BAR_H}" '
                        f'fill="{colour}"><title>{family}: {count} {status}</title></rect>')
            if width >= 14:
                ink = SURFACE if colour == ACCENT_DARK else INK
                body.append(text(x + width / 2, y + 12, count, size=10, weight=700, fill=ink,
                                 anchor="middle"))
            x += count * unit
    body.append(line(x0, top - 8, x0, top + len(families) * row - 8, stroke=AXIS))

    # (b) falsifier attempts on a log scale, because they span three decades.
    bx_label, bx0, btrack, low, high = 578, 590, 120, 1, 5
    body.append(text(412, 16, "(b) Attempts to refute the thesis", size=11.5, weight=700))
    body.append(text(412, 33, f"{thesis['summary']['counterexamples']} counterexamples "
                     "in every falsifier; log scale", size=9.5, fill=MUTED))
    brow, btop = 24, 58
    rows = thesis["falsifiers"]
    axis_bottom = btop + len(rows) * brow - 4
    for power in range(low + 1, high + 1):
        gx = bx0 + btrack * (power - low) / (high - low)
        body.append(line(gx, btop - 6, gx, axis_bottom, stroke=GRID))
        tick = 10 ** power
        shown = f"{tick // 1000:,}k" if tick >= 1000 else f"{tick:,}"
        body.append(text(gx, axis_bottom + 13, shown, size=8.5, fill=MUTED, anchor="middle"))
    body.append(line(bx0, btop - 6, bx0, axis_bottom, stroke=AXIS))
    for index, falsifier in enumerate(rows):
        y = btop + index * brow
        attempts = falsifier["attempts"]
        share = (math.log10(max(attempts, 10 ** low)) - low) / (high - low)
        length = btrack * min(1.0, share)
        body.append(text(bx_label, y + 11, f"{falsifier['id']} {falsifier['name']}",
                         size=10.5, anchor="end"))
        body.append(hbar(bx0, y, length, ACCENT,
                         f"{falsifier['id']}: {attempts:,} attempts, "
                         f"{falsifier['counterexamples']} counterexamples", h=14))
        body.append(text(bx0 + max(length, 2) + 5, y + 11, f"{attempts:,}", size=10))

    height = max(top + len(families) * row, axis_bottom + 20) + 4
    caption = (
        f"The safety case does not rest on alignment. (a) Of {catalogue['threats']} failure "
        f"classes, including {figures['threats_alignment_total']} alignment failures, "
        f"{catalogue['contained']} are contained, {catalogue['bounded']} bounded, and "
        f"{catalogue['residual']} assigned to the research agenda; every evidence locator is "
        f"checked to exist. (b) Six falsifiers made {thesis['summary']['attempts']:,} bounded "
        "attempts to produce a governed effect or disclosure from model output alone and "
        "found none; removing a single mediator check produces counterexamples."
    )
    label = "Threat catalogue status by family and falsification attempts per falsifier"
    return svg(760, height, label, body), caption


#: Paper order. A figure's number is its position here, and the paper must cite
#: every one of them (``scripts/build_paper.py`` refuses otherwise).
FIGURE_BUILDERS = (
    ("architecture", figure_architecture),
    ("request-steps", figure_request_steps),
    ("lifecycle", figure_lifecycle),
    ("containment", figure_containment),
    ("oversight", figure_oversight),
    ("domain-packs", figure_domain_packs),
    ("evidence", figure_evidence),
)


def build() -> dict[str, tuple[str, str]]:
    """Every figure as ``{stem: (svg, caption)}``, in paper order."""
    figures = json.loads((RESULTS / "v1.0.0-summary.json").read_text(encoding="utf-8"))["figures"]
    return {stem: builder(figures) for stem, builder in FIGURE_BUILDERS}


def _expected_files() -> dict[Path, str]:
    built = build()
    files = {FIGURES / f"{stem}.svg": content for stem, (content, _) in built.items()}
    captions = {stem: caption for stem, (_, caption) in built.items()}
    files[FIGURES / "captions.json"] = json.dumps(captions, indent=2) + "\n"
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare against committed figures without writing")
    args = parser.parse_args()
    expected = _expected_files()
    if args.check:
        stale = [path.name for path, content in expected.items()
                 if not path.exists() or path.read_text(encoding="utf-8") != content]
        extra = sorted(p.name for p in FIGURES.glob("*.svg") if p not in expected)
        if stale or extra:
            print("paper figures have drifted from the results: "
                  + ", ".join(stale + [f"{name} (no longer generated)" for name in extra])
                  + "\nregenerate with: python scripts/generate_paper_figures.py")
            return 1
        print(f"paper figures match the committed results ({len(expected) - 1} figures)")
        return 0
    FIGURES.mkdir(parents=True, exist_ok=True)
    for stale in FIGURES.glob("*.svg"):
        if stale not in expected:
            stale.unlink()
    for path, content in expected.items():
        path.write_text(content, encoding="utf-8")
    print(json.dumps(sorted(path.name for path in expected), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
