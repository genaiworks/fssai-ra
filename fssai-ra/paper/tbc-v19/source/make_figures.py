"""Deterministic original figures for the Trust by Construction V19 manuscript.

Every figure draws the architecture, the pattern catalogue or a recorded
mechanism trace. No figure reports a field measurement or a benchmark ranking.
Palette: two categorical hues separable under colour-vision deficiency on a
white print surface (blue #2a78d6, orange #eb6834); all other ink is neutral,
and every mark carries a label, so identity is never colour alone.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib import font_manager

BASE = Path(__file__).resolve().parent
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
for p in (ARIAL, ARIAL_B):
    font_manager.fontManager.addfont(p)
plt.rcParams.update({
    "font.family": ["Arial", "DejaVu Sans"], "pdf.fonttype": 42, "svg.fonttype": "none",
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "axes.facecolor": "white",
})

INK, SEC, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, RULE, PANEL = "#e1e0d9", "#c3c2b7", "#f4f6f8"
BLUE, ORANGE, PALE = "#2a78d6", "#eb6834", "#cde2fb"
SOFT, WARM = "#eaf2fd", "#fdeee8"
DPI = 300


def save(fig, name):
    fig.savefig(BASE / name, dpi=DPI, bbox_inches="tight", pad_inches=0.02,
                metadata={"Software": "trust-by-construction-v19"})
    plt.close(fig)
    print(f"  wrote {name}")


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def panel(ax, x, y, w, h, fill="white", edge=RULE, lw=1.0, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                facecolor=fill, edgecolor=edge, linewidth=lw,
                                linestyle=ls, zorder=2))


def box(ax, x, y, w, h, title, lines, fill=PANEL, edge=RULE, lw=1.1, tsize=8.4, bsize=7.4,
        tcolor=INK):
    panel(ax, x, y, w, h, fill, edge, lw)
    ax.text(x + w / 2, y + h - 3.4, title, ha="center", va="top", fontsize=tsize,
            fontweight="bold", color=tcolor, zorder=3)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 9.2 - i * 5.4, line, ha="center", va="top",
                fontsize=bsize, color=SEC, zorder=3)


def arrow(ax, x1, y1, x2, y2, color=INK, lw=1.2, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, color=color,
                                 linewidth=lw, linestyle=ls, mutation_scale=11,
                                 shrinkA=0, shrinkB=0, zorder=4))


def strip(ax, x, y, w, h, label, fill="white", edge=RULE, size=6.9, color=INK, lw=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.7",
                                facecolor=fill, edgecolor=edge, linewidth=lw, zorder=3))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=size,
            color=color, zorder=4)


# ---------------------------------------------------------------- Figure 1
def figure_1():
    """The model is not the security boundary."""
    fig, ax = canvas(6.8, 3.35)
    ax.text(50, 98, "THE MODEL IS NOT THE SECURITY BOUNDARY", ha="center", va="top",
            fontsize=9.0, fontweight="bold", color=INK)
    ax.text(50, 92.5, "Reasoning creates intent. Independently enforced services create effects.",
            ha="center", va="top", fontsize=7.0, color=SEC)

    cols = [
        (1.0, WARM, ORANGE, (0, (3, 2)), "LOWER-TRUST INTELLIGENCE LAYER",
         ["Language model", "Planning and orchestration", "Retrieved documents",
          "Memory contents", "Model-generated code", "Tool and agent messages"],
         "all treated as untrusted input"),
        (35.75, SOFT, BLUE, "-", "TRUSTED CONTROL PLANE",
         ["Machine identity and leases", "Context and memory gateways",
          "Capability broker", "Typed effect executor", "Release escrow and lineage",
          "Evidence receipts"],
         "small, deterministic, independently enforced"),
        (70.5, "white", RULE, "-", "INSTITUTIONAL SYSTEMS",
         ["Student records", "Learning management", "Research repositories",
          "Finance and admissions", "External network egress", "Code deployment"],
         "reached only through a declared path"),
    ]
    for x, fill, edge, ls, title, rows, foot in cols:
        panel(ax, x, 22, 28.5, 65, fill, edge, 1.5 if edge != RULE else 1.1, ls)
        ax.text(x + 14.25, 83.5, title, ha="center", va="center", fontsize=7.4,
                fontweight="bold", color=edge if edge != RULE else INK, zorder=3)
        for i, row in enumerate(rows):
            strip(ax, x + 2.0, 72.5 - i * 8.6, 24.5, 6.8, row, fill="white",
                  edge=GRID, size=6.7)
        ax.text(x + 14.25, 25.5, foot, ha="center", va="center", fontsize=6.4,
                color=MUTED, style="italic", zorder=3)

    arrow(ax, 30.3, 58, 35.3, 58, color=INK, lw=1.4)
    ax.text(32.8, 60.6, "typed\nproposal", ha="center", va="bottom", fontsize=5.9,
            color=SEC, linespacing=1.3)
    arrow(ax, 65.0, 58, 70.0, 58, color=INK, lw=1.4)
    ax.text(67.5, 60.6, "validated\neffect", ha="center", va="bottom", fontsize=5.9,
            color=SEC, linespacing=1.3)

    ax.plot([15.25, 15.25], [22, 12], color=ORANGE, lw=1.1, linestyle=(0, (3, 2)), zorder=2)
    ax.plot([84.75, 84.75], [22, 12], color=ORANGE, lw=1.1, linestyle=(0, (3, 2)), zorder=2)
    ax.plot([15.25, 84.75], [12, 12], color=ORANGE, lw=1.1, linestyle=(0, (3, 2)), zorder=2)
    ax.plot([50], [12], marker="x", markersize=9, markeredgewidth=2.0, color=ORANGE, zorder=5)
    ax.text(50, 5.5, "No direct path: no standing credential, no ambient authority, "
                     "no inherited administrator session",
            ha="center", va="center", fontsize=7.2, fontweight="bold", color=ORANGE)
    save(fig, "fig1-enforcement-boundary.png")


# ---------------------------------------------------------------- Figure 2
def figure_2():
    """Proof before power: authority is computed, never assumed."""
    fig, ax = canvas(6.8, 3.25)
    ax.text(50, 98, "PROOF BEFORE POWER: AUTHORITY IS COMPUTED, NOT ASSUMED",
            ha="center", va="top", fontsize=9.0, fontweight="bold", color=INK)
    ax.text(50, 92.5, "Each gate narrows what the workload may do. No gate can widen it.",
            ha="center", va="top", fontsize=7.0, color=SEC)
    gates = [
        ("P1", "Declared\nceiling", "models, data classes,\ntools, zones, effects"),
        ("P2", "Task\ncontract", "one purpose, subject,\ndestination, expiry"),
        ("P3–P4", "Lease and\nattenuation", "short-lived scope,\nchild ⊆ parent"),
        ("P5–P7", "Mediated read\nand typed effect", "gateway, lineage,\nversion and replay"),
        ("P8", "Sealed\nrelease", "exact bytes, recipient,\nper-chunk recheck"),
    ]
    w, gap = 17.2, 3.1
    for i, (tag, name, sub) in enumerate(gates):
        x = 1.0 + i * (w + gap)
        panel(ax, x, 56, w, 30, SOFT if i in (1, 3) else "white", BLUE, 1.3)
        ax.add_patch(Ellipse((x + 3.0, 82.2), 4.0, 4.0 * 6.8 / 3.25, facecolor=BLUE,
                             edgecolor="none", zorder=4))
        ax.text(x + 3.0, 82.2, str(i + 1), ha="center", va="center", fontsize=6.4,
                fontweight="bold", color="white", zorder=5)
        ax.text(x + w / 2 + 1.6, 79.0, name, ha="center", va="top", fontsize=7.6,
                fontweight="bold", color=INK, linespacing=1.3, zorder=3)
        ax.text(x + w / 2, 66.5, sub, ha="center", va="top", fontsize=6.4, color=SEC,
                linespacing=1.4, zorder=3)
        ax.text(x + w / 2, 58.3, tag, ha="center", va="center", fontsize=6.6,
                fontweight="bold", color=BLUE, zorder=3)
        if i < 4:
            arrow(ax, x + w + 0.3, 71, x + w + gap - 0.3, 71, color=MUTED, lw=1.1)

    ax.text(1.0, 51.0, "AUTHORITY REMAINING AFTER EACH GATE", ha="left", va="center",
            fontsize=6.6, fontweight="bold", color=MUTED)
    heights = [26, 21, 16, 11, 6]
    for i, h in enumerate(heights):
        x = 1.0 + i * (w + gap)
        ax.add_patch(Rectangle((x + 1.5, 19), w - 3.0, h, facecolor=PALE,
                               edgecolor=BLUE, linewidth=0.9, zorder=2))
    ax.text(1.0, 16.0, "DECLARED CEILING", ha="left", va="center", fontsize=6.4, color=MUTED)
    ax.text(99.0, 16.0, "EFFECT PERMITTED", ha="right", va="center", fontsize=6.4, color=BLUE)
    panel(ax, 1.0, 1.5, 98, 11.5, "white", ORANGE, 1.2)
    ax.text(50, 9.2, "Assurance may contract authority automatically: a changed tool manifest "
                     "moves a workload to proposal-only.",
            ha="center", va="center", fontsize=6.9, color=SEC, zorder=3)
    ax.text(50, 4.3, "Nothing automatic may promote. Restoration is a named operator, a fresh "
                     "lease, and never past the ceiling.",
            ha="center", va="center", fontsize=7.2, fontweight="bold", color=ORANGE, zorder=3)
    save(fig, "fig2-proof-before-power.png")


# ---------------------------------------------------------------- Figure 3
def figure_3():
    """The pattern catalogue laid over the task lifecycle."""
    fig, ax = canvas(6.8, 3.4)
    ax.text(50, 98, "TEN PATTERNS ON ONE TASK LIFECYCLE", ha="center", va="top",
            fontsize=9.0, fontweight="bold", color=INK)
    ax.text(50, 92.5, "Each stage runs the same five-step contract; the patterns differ only "
                      "in what they refuse.", ha="center", va="top", fontsize=7.0, color=SEC)
    stages = [
        ("ADMIT", [("P1", "declared ceiling"), ("P2", "task contract"),
                   ("P3", "credentialless runtime")]),
        ("READ", [("P5", "mediated context"), ("P6", "reauthorised memory")]),
        ("DELEGATE", [("P4", "attenuated delegation"), ("P10", "declared graph")]),
        ("ACT", [("P7", "typed effect")]),
        ("RELEASE", [("P8", "sealed release"), ("P9", "restricting monitor")]),
    ]
    w, gap, x0 = 17.0, 2.85, 2.3
    for i, (stage, pats) in enumerate(stages):
        x = x0 + i * (w + gap)
        panel(ax, x, 42, w, 44, "white", BLUE, 1.3)
        ax.add_patch(Rectangle((x + 0.9, 79.6), w - 1.8, 5.5, facecolor=BLUE,
                               edgecolor="none", zorder=3))
        ax.text(x + w / 2, 82.3, stage, ha="center", va="center", fontsize=7.4,
                fontweight="bold", color="white", zorder=4)
        for j, (tag, name) in enumerate(pats):
            y = 66.0 - j * 11.5
            ax.add_patch(FancyBboxPatch((x + 1.0, y), w - 2.0, 10.0,
                                        boxstyle="round,pad=0,rounding_size=0.7",
                                        facecolor=SOFT, edgecolor=BLUE, linewidth=0.9,
                                        zorder=3))
            ax.text(x + w / 2, y + 7.0, tag, ha="center", va="center", fontsize=6.6,
                    fontweight="bold", color=BLUE, zorder=4)
            ax.text(x + w / 2, y + 2.8, name, ha="center", va="center", fontsize=6.0,
                    color=INK, zorder=4)
        ax.text(x + w / 2, 38.5, "refuse on any failed check", ha="center", va="center",
                fontsize=6.0, color=MUTED, style="italic", zorder=3)
        if i < 4:
            arrow(ax, x + w + 0.25, 64, x + w + gap - 0.25, 64, color=MUTED, lw=1.1)
    panel(ax, x0, 11.5, 61, 21.5, PANEL, RULE, 1.0)
    ax.text(x0 + 30.5, 29.5, "THE FIVE-STEP CONTRACT AT EVERY STAGE", ha="center",
            va="center", fontsize=7.2, fontweight="bold", color=INK, zorder=3)
    steps = ["authenticate the caller", "load current trusted state",
             "intersect the applicable rights", "validate the exact operation",
             "commit under concurrency and replay checks"]
    for i, step in enumerate(steps):
        ax.text(x0 + 1.8 + (i % 2) * 30.0, 23.5 - (i // 2) * 5.4, f"{i + 1}. {step}",
                ha="left", va="center", fontsize=6.4, color=SEC, zorder=3)
    panel(ax, x0 + 63.5, 11.5, 34.2, 21.5, "white", ORANGE, 1.2)
    ax.text(x0 + 80.6, 29.0, "WHAT A PATTERN COSTS", ha="center", va="center", fontsize=7.2,
            fontweight="bold", color=ORANGE, zorder=3)
    ax.text(x0 + 80.6, 19.5, "A declaration to write, a check on the\nhot path, and a refusal "
                             "the workload\nmust handle. A pattern that costs\nnothing to adopt "
                             "enforces nothing.",
            ha="center", va="center", fontsize=6.4, color=SEC, linespacing=1.55, zorder=3)
    ax.text(50, 5.0, "Authority never widens along this line. A model output selects among "
                     "permitted operations, or it is refused.",
            ha="center", va="center", fontsize=7.2, fontweight="bold", color=INK)
    save(fig, "fig3-pattern-map.png")


# ---------------------------------------------------------------- Figure 4
def figure_4():
    """Authority composes across an agent graph."""
    fig, ax = canvas(6.8, 2.95)
    ax.text(50, 98, "CAPABILITY COMPOSES ACROSS THE AGENT GRAPH", ha="center", va="top",
            fontsize=9.0, fontweight="bold", color=INK)
    nodes = [
        (3, 56, "COORDINATOR", ["plans the task,", "holds no data access"], PANEL, RULE),
        (27, 56, "AGENT A", ["reads protected", "transcripts"], SOFT, BLUE),
        (51, 56, "AGENT B", ["summarises and", "reformats"], SOFT, BLUE),
        (75, 56, "AGENT C", ["posts to a public", "channel"], SOFT, BLUE),
    ]
    for x, y, title, lines, fill, edge in nodes:
        box(ax, x, y, 22, 28, title, lines, fill=fill, edge=edge,
            lw=1.3 if edge == BLUE else 1.0, tsize=7.8, bsize=6.6)
        ax.text(x + 11, y - 4.0, "own scope: allowed", ha="center", fontsize=6.3, color=MUTED)
    for x in (25.4, 49.4, 73.4):
        arrow(ax, x - 0.4, 70, x + 1.6, 70, color=SEC, lw=1.1)
    ax.plot([38, 38], [48.5, 41], color=ORANGE, lw=1.0, linestyle=(0, (2, 2)), zorder=2)
    ax.plot([86, 86], [48.5, 41], color=ORANGE, lw=1.0, linestyle=(0, (2, 2)), zorder=2)
    ax.plot([38, 86], [41, 41], color=ORANGE, lw=1.4, zorder=2)
    ax.text(62, 36.5, "COMPOSED PATH: protected source → public sink", ha="center",
            va="center", fontsize=7.6, fontweight="bold", color=ORANGE)
    panel(ax, 3, 11, 94, 21, "white", ORANGE, 1.3)
    ax.text(50, 26.5, "P10 REJECTS THE PATH BEFORE AGENT C CAN ACT", ha="center",
            va="center", fontsize=7.8, fontweight="bold", color=ORANGE, zorder=3)
    ax.text(50, 18.0, "Lineage travels with the derived summary, so B's output still carries A's "
                      "restrictions; one shared task budget,\na population cap and a delegation "
                      "depth limit stop the graph from growing its way around the ceiling.\n"
                      "The check covers registered topology, not hidden channels between "
                      "co-resident processes.",
            ha="center", va="center", fontsize=6.6, color=SEC, linespacing=1.5, zorder=3)
    ax.text(50, 4.0, "Per-agent least privilege is not enough. Authority composes across the "
                     "graph, so the graph is what must be checked.",
            ha="center", va="center", fontsize=7.0, fontweight="bold", color=INK)
    save(fig, "fig4-agent-graph.png")


# ---------------------------------------------------------------- Figure 5
def figure_5():
    """Guardian authority states: contraction is automatic, restoration is not."""
    fig, ax = canvas(6.8, 2.95)
    ax.text(50, 98, "AUTHORITY STATES: CONTRACTION IS AUTOMATIC, RESTORATION IS NOT",
            ha="center", va="top", fontsize=9.0, fontweight="bold", color=INK)
    states = [
        ("NORMAL", "full declared\nauthority", "#eef6ee", "#5b8f5b"),
        ("RESTRICTED", "reduced tools\nand destinations", SOFT, BLUE),
        ("PROPOSAL_ONLY", "may propose,\nmay not effect", SOFT, BLUE),
        ("READ_ONLY", "no writes,\nno releases", WARM, ORANGE),
        ("QUARANTINED", "capabilities\nrevoked", "#fde8e4", "#c0392b"),
    ]
    w, gap = 17.6, 2.4
    for i, (name, sub, fill, edge) in enumerate(states):
        x = 1.2 + i * (w + gap)
        panel(ax, x, 62, w, 26, fill, edge, 1.3)
        ax.text(x + w / 2, 81.5, name, ha="center", va="center", fontsize=7.2,
                fontweight="bold", color=edge, zorder=3)
        ax.text(x + w / 2, 70.5, sub, ha="center", va="center", fontsize=6.5, color=SEC,
                linespacing=1.4, zorder=3)
        if i < 4:
            arrow(ax, x + w + 0.1, 75, x + w + gap - 0.1, 75, color=MUTED, lw=1.1)
    panel(ax, 1.0, 33, 98, 23, "white", RULE, 1.0)
    ax.text(50, 51.5, "AUTOMATIC CONTRACTION — ANY OF THESE MOVES A WORKLOAD RIGHTWARD, "
                      "WITH NO HUMAN ACTION",
            ha="center", va="center", fontsize=6.9, fontweight="bold", color=INK, zorder=3)
    triggers = ["changed tool manifest", "stale policy state", "undeclared destination",
                "budget exhaustion", "abnormal graph expansion", "invariant violation"]
    for i, trig in enumerate(triggers):
        ax.plot([4.5 + (i % 3) * 32.0], [44.0 - (i // 3) * 7.0], marker="o", markersize=3.0,
                color=BLUE, zorder=4)
        ax.text(6.8 + (i % 3) * 32.0, 44.0 - (i // 3) * 7.0, trig, ha="left", va="center",
                fontsize=6.6, color=SEC, zorder=3)
    arrow(ax, 88, 26, 12, 26, color="#5b8f5b", lw=1.3, ls=(0, (4, 2)))
    ax.text(50, 22.0, "RESTORATION — named human authority, fresh evidence, a new lease. "
                      "Never automatic, never by the assurance plane.",
            ha="center", va="top", fontsize=6.9, fontweight="bold", color="#3f6b3f")
    panel(ax, 1.0, 1.5, 98, 12, WARM, ORANGE, 1.2)
    ax.text(50, 9.0, "A detector, a monitor or another model can restrict a workload. "
                     "None of them can promote one.",
            ha="center", va="center", fontsize=7.2, fontweight="bold", color=ORANGE, zorder=3)
    ax.text(50, 4.2, "An assurance component that could grant privilege would itself become "
                     "the escalation path.",
            ha="center", va="center", fontsize=6.6, color=SEC, zorder=3)
    save(fig, "fig5-authority-states.png")


# ---------------------------------------------------------------- Figure 6
def figure_6():
    """Recorded delivery and revocation trace."""
    fig, ax = canvas(6.8, 2.7)
    x0, ytop, unit = 3, 84, 4.9
    ax.text(x0, ytop + 9, "APPROVED ARTIFACT — ten bytes bound to exact content and "
                          "one recipient", ha="left", fontsize=7.3, fontweight="bold", color=INK)
    for i in range(10):
        delivered = i < 3
        ax.add_patch(Rectangle((x0 + i * unit, ytop - 9), unit - 0.45, 9,
                               facecolor=BLUE if delivered else "white",
                               edgecolor=BLUE if delivered else RULE, linewidth=1.0, zorder=2))
        ax.text(x0 + i * unit + (unit - 0.45) / 2, ytop - 4.5, "abcdefghij"[i], ha="center",
                va="center", fontsize=7.4, color="white" if delivered else MUTED, zorder=3)
    ax.text(x0 + 1.5 * unit, ytop - 13.8, "delivered (3)", ha="center", fontsize=6.7, color=BLUE)
    ax.text(x0 + 6.5 * unit, ytop - 13.8, "never delivered (7)", ha="center", fontsize=6.7,
            color=MUTED)
    ax.plot([x0 + 3 * unit - 0.22] * 2, [ytop + 2, ytop - 19], color=INK, lw=1.2, zorder=4)
    ax.text(x0 + 3 * unit + 1.4, ytop - 21.5,
            "the delivery cursor stays at three bytes in every case below",
            ha="left", fontsize=7.1, fontweight="bold", color=INK)
    rows = ["authority revoked", "task contract restricted", "task expired",
            "emergency stop asserted", "source binding invalidated"]
    for i, label in enumerate(rows):
        y = 50 - i * 9.6
        ax.text(x0, y, f"{i + 1}.  {label}", ha="left", va="center", fontsize=7.4, color=INK)
        for cx, txt in ((44, "next chunk"), (68, "bulk delivery")):
            ax.add_patch(FancyBboxPatch((cx, y - 3.4), 22, 6.8,
                                        boxstyle="round,pad=0,rounding_size=0.8",
                                        facecolor="white", edgecolor=ORANGE, linewidth=1.0,
                                        zorder=2))
            ax.text(cx + 11, y, f"{txt}: denied", ha="center", va="center", fontsize=6.8,
                    color=ORANGE, zorder=3)
        ax.plot([x0, 97], [y - 5.0, y - 5.0], color=GRID, lw=0.7, zorder=1)
    ax.text(x0, 0.5, "Each intervention is exercised independently from the same approved state. "
                     "Bytes already received are not recalled.",
            ha="left", va="center", fontsize=6.8, color=MUTED)
    save(fig, "fig6-delivery-revocation.png")


if __name__ == "__main__":
    print("building figures")
    figure_1(); figure_2(); figure_3(); figure_4(); figure_5(); figure_6()
