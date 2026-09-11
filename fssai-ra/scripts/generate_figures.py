"""Generate the deck's charts from the actual experiment results.

Hand-rolled SVG, for three reasons that matter more than convenience. It has no
dependencies, so the figures regenerate on the same disconnected laptop as
everything else. It inherits the deck's theme tokens, so a chart is legible in
light and dark without a second palette. And the numbers are read from the
results JSON, so a figure cannot drift from the run that produced it -- the same
guarantee the prose has.

Form follows the reader's question. On both charts that question is magnitude
("how far did containment get?", "how much harm reached the asset?"), not
identity, so both are single-series bars: one hue, no legend, direct labels. A
four-colour stacked breakdown would have encoded identity nobody asked about and
spent the deck's reserved semantic colours doing it.

    python scripts/generate_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIGURES = ROOT / "docs" / "presentation" / "figures"
RESULTS = ROOT / "evaluation" / "results"

# Geometry. One scale places marks, ticks and labels; the viewBox leaves room
# for the outermost label so nothing is clipped.
WIDTH, ROW_H, GAP = 760, 56, 14
LEFT, RIGHT, TOP = 210, 92, 34


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def bar_chart(
    *,
    title: str,
    subtitle: str,
    rows: list[tuple[str, float, str]],
    domain_max: float,
    tone: str,
    value_suffix: str = "",
    axis_note: str = "",
) -> str:
    """One single-series horizontal bar chart.

    ``rows`` is ``(label, value, annotation)``. ``tone`` is a CSS variable name
    from the deck's palette, so the mark is the deck's own semantic colour.
    """
    height = TOP + len(rows) * (ROW_H + GAP) + 46
    track = WIDTH - LEFT - RIGHT
    parts = [
        f'<svg viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-labelledby="t-{abs(hash(title)) % 99999}" class="chart">',
        f'<title id="t-{abs(hash(title)) % 99999}">{_escape(title)}. {_escape(subtitle)}</title>',
        f'<text x="0" y="14" class="c-title">{_escape(title)}</text>',
        f'<text x="0" y="29" class="c-sub">{_escape(subtitle)}</text>',
    ]

    # Axis: a baseline and one tick at the domain maximum, both recessive.
    baseline_x = LEFT
    parts.append(
        f'<line x1="{baseline_x}" y1="{TOP + 4}" x2="{baseline_x}" '
        f'y2="{TOP + len(rows) * (ROW_H + GAP) - GAP + 4}" class="c-axis"/>'
    )

    for index, (label, value, annotation) in enumerate(rows):
        y = TOP + index * (ROW_H + GAP)
        share = 0.0 if domain_max == 0 else max(0.0, min(1.0, value / domain_max))
        length = share * track
        parts.append(
            f'<text x="{LEFT - 12}" y="{y + 23}" text-anchor="end" class="c-label">'
            f'{_escape(label)}</text>'
        )
        if annotation:
            parts.append(
                f'<text x="{LEFT - 12}" y="{y + 38}" text-anchor="end" class="c-note">'
                f'{_escape(annotation)}</text>'
            )
        if length >= 1:
            # 4px rounded data-end, anchored to the baseline.
            parts.append(
                f'<rect x="{baseline_x}" y="{y + 8}" width="{length:.1f}" height="22" '
                f'rx="4" fill="var(--{tone})"><title>{_escape(label)}: '
                f'{value:g}{_escape(value_suffix)}</title></rect>'
            )
        else:
            # Zero is the most important value on these charts. Draw it as a
            # visible stub so the row is never mistaken for missing data.
            parts.append(
                f'<rect x="{baseline_x}" y="{y + 8}" width="3" height="22" rx="1.5" '
                f'fill="var(--rule-strong)"><title>{_escape(label)}: 0</title></rect>'
            )
        parts.append(
            f'<text x="{baseline_x + max(length, 3) + 10}" y="{y + 25}" class="c-value">'
            f'{value:g}{_escape(value_suffix)}</text>'
        )

    if axis_note:
        parts.append(
            f'<text x="{baseline_x}" y="{height - 12}" class="c-note">{_escape(axis_note)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


CHART_CSS = """
/* Charts. Text takes theme tokens so it reads on either ground; every drawn
   shape has an explicit fill. Single series, so no legend: the title names it. */
.chart { width: 100%; height: auto; display: block; max-width: 100%; }
.chart text { font-family: var(--display); fill: var(--ink); }
.chart .c-title { font-size: 13px; font-weight: 700; letter-spacing: -.005em; }
.chart .c-sub { font-size: 11px; fill: var(--ink-faint); font-family: var(--body); }
.chart .c-label { font-size: 12.5px; font-weight: 600; fill: var(--ink); }
.chart .c-note { font-size: 10.5px; fill: var(--ink-faint); font-family: var(--mono); }
.chart .c-value { font-size: 14px; font-weight: 700; fill: var(--ink);
                  font-variant-numeric: tabular-nums; }
.chart .c-axis { stroke: var(--rule-strong); stroke-width: 1; }
"""


def main() -> int:
    from fssaira.experiment import run_comparison

    FIGURES.mkdir(parents=True, exist_ok=True)
    comparison = run_comparison()
    (RESULTS / "v1.0.0-architecture-comparison.json").write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
    )
    arms = comparison["arms"]

    # Chart 1 — the headline. Containment rises; utility does not fall.
    containment = bar_chart(
        title="Attacks contained, by architecture",
        subtitle="Seven attacks. Identical hostile proposals to all three arms.",
        rows=[
            (arm["arm"], round(arm["containment_rate"] * 100),
             f"{arm['attacks_attempted'] - arm['attacks_succeeded']}/{arm['attacks_attempted']} contained")
            for arm in arms
        ],
        domain_max=100,
        tone="ink",
        value_suffix="%",
        axis_note="0–100% of attempted attacks contained",
    )
    (FIGURES / "containment-by-arm.svg").write_text(containment, encoding="utf-8")

    # Chart 2 — the cost of that containment, which is the number that makes it
    # meaningful. Same axis, same arms, so the two read as a pair.
    utility = bar_chart(
        title="Benign tasks completed, by architecture",
        subtitle="The same legitimate work, put to all three arms.",
        rows=[
            (arm["arm"], round(arm["benign_completion_rate"] * 100),
             f"{arm['benign_completed']}/{arm['benign_attempted']} completed")
            for arm in arms
        ],
        domain_max=100,
        tone="authorize",
        value_suffix="%",
        axis_note="0–100% of legitimate tasks completed — containment costs nothing here",
    )
    (FIGURES / "utility-by-arm.svg").write_text(utility, encoding="utf-8")

    # Chart 3 — harm that actually reached the protected asset.
    harms = bar_chart(
        title="Harmful actions that reached the protected asset",
        subtitle="Exfiltration, unauthorized award, self-escalation, evidence destruction.",
        rows=[
            (arm["arm"], sum(arm["harms"].values()),
             " · ".join(f"{name.split('_')[0]} {count}"
                        for name, count in arm["harms"].items() if count) or "none")
            for arm in arms
        ],
        domain_max=max(sum(arm["harms"].values()) for arm in arms) or 1,
        tone="refuse",
        axis_note="count of completed harmful actions across the seven attacks",
    )
    (FIGURES / "harms-by-arm.svg").write_text(harms, encoding="utf-8")

    (FIGURES / "chart.css").write_text(CHART_CSS.strip() + "\n", encoding="utf-8")

    print(json.dumps({
        "figures": sorted(p.name for p in FIGURES.glob("*.svg")),
        "arms": {arm["arm"]: {
            "containment": arm["containment_rate"],
            "benign": arm["benign_completion_rate"],
            "harms": sum(arm["harms"].values()),
        } for arm in arms},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
