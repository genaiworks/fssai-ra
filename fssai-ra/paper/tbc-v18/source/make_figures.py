"""Deterministic original figures for the Trust by Construction V18 manuscript.

Every figure is a drawing of the architecture or of a recorded mechanism trace.
No figure reports a field measurement, a benchmark ranking or a user study.
Palette: two categorical hues validated for colour-vision deficiency separation
against a white print surface (blue #2a78d6, orange #eb6834); all other ink is
neutral. Identity is never carried by colour alone: every mark is labelled.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
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
DPI = 300


def save(fig, name):
    out = BASE / name
    fig.savefig(out, dpi=DPI, bbox_inches="tight", pad_inches=0.02,
                metadata={"Software": "trust-by-construction-v18"})
    plt.close(fig)
    print(f"  wrote {name}")


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, title, lines, fill=PANEL, edge=RULE, lw=1.1, tsize=8.4, bsize=7.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                facecolor=fill, edgecolor=edge, linewidth=lw, zorder=2))
    ax.text(x + w / 2, y + h - 3.4, title, ha="center", va="top", fontsize=tsize,
            fontweight="bold", color=INK, zorder=3)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 9.2 - i * 5.4, line, ha="center", va="top",
                fontsize=bsize, color=SEC, zorder=3)


def arrow(ax, x1, y1, x2, y2, color=INK, lw=1.2, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, color=color,
                                 linewidth=lw, linestyle=ls, mutation_scale=11,
                                 shrinkA=0, shrinkB=0, zorder=4))


# ---------------------------------------------------------------- Figure 1
def figure_1():
    fig, ax = canvas(6.8, 2.85)
    box(ax, 1, 60, 28, 30, "MODEL AND INPUTS",
        ["Proposes typed requests", "Holds no standing", "credentials or policy"])
    box(ax, 36, 60, 28, 30, "AUTHORITY SERVICE",
        ["Authenticates the caller", "Recomputes current rights", "Rechecks before commit"],
        fill="#eaf2fd", edge=BLUE, lw=1.5)
    box(ax, 71, 60, 28, 30, "PROTECTED SYSTEMS",
        ["Reads or changes records", "Delivers approved", "artifacts to a recipient"])
    arrow(ax, 29.4, 75, 35.4, 75)
    ax.text(32.4, 77.2, "proposal", ha="center", fontsize=6.6, color=MUTED)
    arrow(ax, 64.4, 75, 70.4, 75)
    ax.text(67.4, 77.2, "authorised", ha="center", fontsize=6.6, color=MUTED)
    ax.add_patch(Rectangle((33, 26), 34, 18, facecolor="white", edgecolor=BLUE,
                           linewidth=1.0, linestyle=(0, (3, 2)), zorder=2))
    ax.text(50, 39.0, "TRUSTED STATE  s", ha="center", va="center", fontsize=7.6,
            fontweight="bold", color=BLUE, zorder=3)
    ax.text(50, 31.5, "contract | lineage | approvals\nrevocation epoch | version | budget",
            ha="center", va="center", fontsize=6.7, color=SEC, linespacing=1.4, zorder=3)
    arrow(ax, 50, 44.4, 50, 59.4, color=BLUE, lw=1.0)
    box(ax, 1, 3, 28, 16, "AI MONITOR", ["May restrict authority"], fill="white")
    box(ax, 71, 3, 28, 16, "NAMED OPERATOR", ["Only path that restores"], fill="white")
    arrow(ax, 20, 19.4, 33.6, 29.5, color=ORANGE, lw=1.3)
    ax.text(21.5, 25.5, "restrict only", ha="left", fontsize=6.6, color=ORANGE)
    arrow(ax, 80, 19.4, 66.4, 29.5, color=SEC, lw=1.3)
    ax.text(78.5, 25.5, "restore", ha="right", fontsize=6.6, color=SEC)
    save(fig, "fig1-enforcement-path.png")


# ---------------------------------------------------------------- Figure 2
def figure_2():
    fig, ax = canvas(6.8, 3.15)
    stages = [
        ("Admit", "passport ∩\ntask contract"),
        ("Retrieve", "subject, purpose\nand scope ceiling"),
        ("Remember", "privileged write,\nreads reauthorised"),
        ("Delegate", "a subset of the\nparent's rights"),
        ("Propose", "typed resource,\nbound version"),
        ("Approve", "separate roles bind\nthe exact proposal"),
        ("Execute", "version, replay,\nepoch, destination"),
        ("Release", "exact bytes, per\nchunk recheck"),
    ]
    cw, bw = 15.6, 14.4
    for i, (name, checked) in enumerate(stages):
        col, row = i % 4, i // 4
        x = 1.0 + col * cw
        y = 58 - row * 33
        fill = "#eaf2fd" if i in (4, 6, 7) else PANEL
        ax.add_patch(FancyBboxPatch((x, y), bw, 27, boxstyle="round,pad=0,rounding_size=1.0",
                                    facecolor=fill, edgecolor=RULE, linewidth=1.0, zorder=2))
        ax.text(x + bw / 2, y + 22.5, name, ha="center", va="center", fontsize=8.0,
                fontweight="bold", color=INK, zorder=3)
        ax.text(x + bw / 2, y + 12.5, checked, ha="center", va="center", fontsize=6.4,
                color=SEC, linespacing=1.45, zorder=3)
        ax.plot([x + bw / 2], [y - 2.2], marker="o", markersize=3.4, color=BLUE, zorder=3)
        ax.plot([x + bw / 2] * 2, [y - 0.4, y - 2.2], color=BLUE, lw=0.9, zorder=2)
        if col < 3:
            arrow(ax, x + bw + 0.2, y + 13.5, x + cw - 0.2, y + 13.5, color=MUTED, lw=0.9)
    ax.add_patch(FancyBboxPatch((66, 22), 33, 63, boxstyle="round,pad=0,rounding_size=1.2",
                                facecolor="white", edgecolor=BLUE, linewidth=1.4, zorder=2))
    ax.text(82.5, 79.5, "AT EVERY MARKED BOUNDARY", ha="center", va="center", fontsize=7.6,
            fontweight="bold", color=BLUE, zorder=3)
    steps = ["authenticate the caller", "load current trusted state",
             "intersect the applicable rights", "validate the exact operation",
             "commit under concurrency\nand replay checks"]
    for i, step in enumerate(steps):
        y = 72 - i * 9.0
        ax.text(68.5, y, f"{i + 1}", ha="left", va="top", fontsize=7.2,
                fontweight="bold", color=BLUE, zorder=3)
        ax.text(72.0, y, step, ha="left", va="top", fontsize=7.0, color=INK,
                linespacing=1.45, zorder=3)
    ax.text(82.5, 24.8, "A failed step yields no protected operation.", ha="center",
            va="center", fontsize=6.8, color=SEC, zorder=3)
    ax.text(1.0, 13.0, "State read for a decision must still be valid at commitment: a cached "
                       "approval cannot override a newer\nrevocation or resource version. Shaded "
                       "stages are those a model output reaches most directly; the contract\nitself "
                       "does not vary between stages.",
            ha="left", va="top", fontsize=6.9, color=SEC, linespacing=1.6)
    save(fig, "fig2-five-step-contract.png")


# ---------------------------------------------------------------- Figure 3
def figure_3():
    fig, ax = canvas(6.8, 3.05)
    rings = [
        (2, 8, 64, 88, "WORKLOAD PASSPORT CEILING",
         "data classes | models | tools | zones | delegation | budgets", "white", RULE),
        (7, 13, 54, 72, "TASK CONTRACT",
         "one purpose, subject, resource set, destination, expiry", "#fbfbfa", RULE),
        (12, 18, 44, 56, "EFFECTIVE ENVELOPE  A(s)",
         "∩ identity, lineage, ancestor scopes, epoch, budget", PALE, BLUE),
        (17, 25, 34, 36, "ADMITTED  O(s, m, r)",
         "what this proposal may actually do", "#eaf2fd", BLUE),
    ]
    for x, y, w, h, title, sub, fill, edge in rings:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6",
                                    facecolor=fill, edgecolor=edge,
                                    linewidth=1.6 if edge == BLUE else 1.0, zorder=2))
        ax.text(x + 2.6, y + h - 4.0, title, ha="left", va="center", fontsize=7.6,
                fontweight="bold", color=BLUE if edge == BLUE else INK, zorder=3)
        ax.text(x + 2.6, y + h - 9.0, sub, ha="left", va="center", fontsize=6.4,
                color=SEC, zorder=3)
    ax.text(34, 39, "Property 1", ha="center", fontsize=8.0, fontweight="bold",
            color=BLUE, zorder=4)
    ax.text(34, 32, "O(s, m, r) ⊆ A(s)", ha="center", fontsize=10.5, fontweight="bold",
            color=BLUE, zorder=4)
    ax.add_patch(FancyBboxPatch((70, 60), 29, 28, boxstyle="round,pad=0,rounding_size=1.2",
                                facecolor="white", edgecolor=ORANGE, linewidth=1.2, zorder=2))
    ax.text(84.5, 83.5, "MODEL AND REVIEWER", ha="center", va="center", fontsize=7.6,
            fontweight="bold", color=INK, zorder=3)
    ax.text(84.5, 74.5, "select inside the envelope\nor trigger a restriction", ha="center",
            va="center", fontsize=6.8, color=SEC, linespacing=1.4, zorder=3)
    ax.text(84.5, 65.5, "never widen it", ha="center", va="center", fontsize=7.4,
            fontweight="bold", color=ORANGE, zorder=3)
    arrow(ax, 69.6, 70, 52.5, 58, color=ORANGE, lw=1.3)
    ax.add_patch(FancyBboxPatch((70, 26), 29, 26, boxstyle="round,pad=0,rounding_size=1.2",
                                facecolor="white", edgecolor=RULE, linewidth=1.0, zorder=2))
    ax.text(84.5, 47.5, "AUTHENTICATED OPERATOR", ha="center", va="center", fontsize=7.6,
            fontweight="bold", color=INK, zorder=3)
    ax.text(84.5, 37.5, "the only transition that\nrestores lost authority,\nand it stays inside\nthe ceiling",
            ha="center", va="center", fontsize=6.8, color=SEC, linespacing=1.4, zorder=3)
    arrow(ax, 69.6, 40, 57.0, 40, color=SEC, lw=1.2)
    ax.text(50, 2.5, "A counterexample is one admitted operation outside A(s), or an automated "
                     "transition that widens A(s). A refusal is not a counterexample.",
            ha="center", va="center", fontsize=6.8, color=MUTED)
    save(fig, "fig3-authority-envelope.png")


# ---------------------------------------------------------------- Figure 4
def figure_4():
    fig, ax = canvas(6.8, 2.7)
    x0, ytop = 3, 84
    unit = 4.9
    ax.text(x0, ytop + 9, "APPROVED ARTIFACT — ten bytes bound to exact content and one recipient",
            ha="left", fontsize=7.3, fontweight="bold", color=INK)
    for i in range(10):
        delivered = i < 3
        ax.add_patch(Rectangle((x0 + i * unit, ytop - 9), unit - 0.45, 9,
                               facecolor=BLUE if delivered else "white",
                               edgecolor=BLUE if delivered else RULE, linewidth=1.0, zorder=2))
        ax.text(x0 + i * unit + (unit - 0.45) / 2, ytop - 4.5, "abcdefghij"[i], ha="center",
                va="center", fontsize=7.4, color="white" if delivered else MUTED, zorder=3)
    ax.text(x0 + 1.5 * unit, ytop - 13.8, "delivered (3)", ha="center", fontsize=6.7, color=BLUE)
    ax.text(x0 + 6.5 * unit, ytop - 13.8, "never delivered (7)", ha="center", fontsize=6.7, color=MUTED)
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
                                        facecolor="white", edgecolor=ORANGE, linewidth=1.0, zorder=2))
            ax.text(cx + 11, y, f"{txt}: denied", ha="center", va="center", fontsize=6.8,
                    color=ORANGE, zorder=3)
        ax.plot([x0, 97], [y - 5.0, y - 5.0], color=GRID, lw=0.7, zorder=1)
    ax.text(x0, 0.5, "Each intervention is exercised independently from the same approved state. "
                     "Bytes already received are not recalled.",
            ha="left", va="center", fontsize=6.8, color=MUTED)
    save(fig, "fig4-delivery-revocation.png")


# ---------------------------------------------------------------- Figure 5
def figure_5b():
    """Authority composes across an agent graph: per-agent least privilege is not enough."""
    fig, ax = canvas(6.8, 2.9)
    nodes = [
        (3, 58, "COORDINATOR", ["plans the task,", "holds no data access"], PANEL, RULE),
        (27, 58, "AGENT A", ["reads protected", "transcripts"], "#eaf2fd", BLUE),
        (51, 58, "AGENT B", ["summarises and", "reformats"], "#eaf2fd", BLUE),
        (75, 58, "AGENT C", ["posts to a public", "channel"], "#eaf2fd", BLUE),
    ]
    for x, y, title, lines, fill, edge in nodes:
        box(ax, x, y, 22, 30, title, lines, fill=fill, edge=edge, lw=1.3 if edge == BLUE else 1.0,
            tsize=8.0, bsize=6.8)
        ax.text(x + 11, y - 4.5, "own scope: allowed", ha="center", fontsize=6.4, color=MUTED)
    for x in (25.4, 49.4, 73.4):
        arrow(ax, x, 73, x + 1.4, 73, color=MUTED, lw=1.0)
        arrow(ax, x - 0.4, 73, x + 1.6, 73, color=SEC, lw=1.1)
    ax.plot([38, 38], [50.5, 42], color=ORANGE, lw=1.0, linestyle=(0, (2, 2)), zorder=2)
    ax.plot([86, 86], [50.5, 42], color=ORANGE, lw=1.0, linestyle=(0, (2, 2)), zorder=2)
    ax.plot([38, 86], [42, 42], color=ORANGE, lw=1.4, zorder=2)
    ax.text(62, 37.5, "COMPOSED PATH: protected source \u2192 public sink", ha="center",
            va="center", fontsize=7.6, fontweight="bold", color=ORANGE)
    ax.add_patch(FancyBboxPatch((3, 12), 94, 21, boxstyle="round,pad=0,rounding_size=1.2",
                                facecolor="white", edgecolor=ORANGE, linewidth=1.3, zorder=2))
    ax.text(50, 27.5, "THE DECLARED-GRAPH CHECK REJECTS THE PATH BEFORE AGENT C CAN ACT",
            ha="center", va="center", fontsize=7.8, fontweight="bold", color=ORANGE, zorder=3)
    ax.text(50, 19.0, "Lineage travels with the derived summary, so B's output still carries A's "
                      "restrictions; the shared task budget and\ndelegation depth stop the graph "
                      "from growing its way around the ceiling. Registered topology only: this check "
                      "does not\ndiscover hidden operating-system channels between co-resident agents.",
            ha="center", va="center", fontsize=6.7, color=SEC, linespacing=1.5, zorder=3)
    ax.text(50, 4.0, "Per-agent least privilege is not enough. Authority composes across the graph, "
                     "so the graph is what must be checked.",
            ha="center", va="center", fontsize=7.0, fontweight="bold", color=INK)
    save(fig, "fig5-agent-graph.png")


# ---------------------------------------------------------------- Figure 6
def figure_5():
    fig = plt.figure(figsize=(6.8, 2.55))
    labels = ["no release\ncontrols", "intermediate\npolicy", "sealed\npolicy"]
    bits = [16, 1, 0]
    escalated = [0.0, 98.4, 98.4]
    for k, (vals, colour, title, ylab, top, ticks, fmt) in enumerate((
            (bits, BLUE, "(a)  Distinguishable release traces",
             "L(P, f)  in bits", 19.5, [0, 4, 8, 12, 16], "{:.0f}"),
            (escalated, ORANGE, "(b)  Cost of the same two policies",
             "adversarial tasks escalated (%)", 120, [0, 25, 50, 75, 100], "{:.1f}"))):
        ax = fig.add_axes([0.075 + k * 0.5, 0.235, 0.375, 0.585])
        bars = ax.bar(range(3), vals, width=0.52, color=colour, zorder=3)
        for b in bars:
            b.set_linewidth(0)
        for i, v in enumerate(vals):
            ax.text(i, v + top * 0.045, fmt.format(v), ha="center", fontsize=8.2,
                    fontweight="bold", color=INK, zorder=4)
        ax.set_xticks(range(3))
        ax.set_xticklabels(labels, fontsize=6.9, color=SEC, linespacing=1.3)
        ax.set_ylim(0, top)
        ax.set_yticks(ticks)
        ax.set_ylabel(ylab, fontsize=7.0, color=SEC, labelpad=4)
        ax.set_title(title, fontsize=7.8, fontweight="bold", color=INK, loc="left", pad=7)
        ax.tick_params(axis="y", labelsize=6.6, colors=MUTED, length=2)
        ax.tick_params(axis="x", length=0, pad=4)
        ax.yaxis.grid(True, color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.spines["left"].set_color(RULE)
        ax.spines["bottom"].set_color(RULE)
    fig.text(0.5, 0.045, "Policy P and encoder f are fixed; 65,536 secrets are enumerated. The "
                         "observer sees destination, path, slot, size and release count only.",
             ha="center", fontsize=6.6, color=MUTED)
    save(fig, "fig6-release-channel.png")


if __name__ == "__main__":
    print("building figures")
    figure_1(); figure_2(); figure_3(); figure_4(); figure_5b(); figure_5()
