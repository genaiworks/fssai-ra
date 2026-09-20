"""Build publication figures from committed results; verify source and asset hashes.

Rendering requires matplotlib. Verification uses only the standard library.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'paper/tbc-v14/figures'
SOURCES = ['evaluation/results/v1.0.0-architecture-comparison.json',
           'evaluation/results/v1.0.0-domain-pack-matrix.json']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data():
    arms = json.loads((ROOT / SOURCES[0]).read_text())['arms']
    profiles = json.loads((ROOT / SOURCES[1]).read_text())['profiles']
    return {'comparison': [{'arm': a['arm'], 'contained': a['attacks_attempted'] - a['attacks_succeeded'],
                            'attacks': a['attacks_attempted'], 'benign_completed': a['benign_completed'],
                            'benign_total': a['benign_attempted']} for a in arms],
            'domains': [{'profile': p['profile_id'], 'contained': p['scenarios_contained'],
                         'attacks': p['scenarios_total'], 'benign_completed': p['benign_completed'],
                         'benign_total': p['benign_total']} for p in profiles]}


def verify():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    if manifest['data'] != data():
        raise ValueError('figure data changed; regenerate the release figures')
    for name, expected in manifest['sources'].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f'figure source drift: {name}')
    for name, expected in manifest['assets'].items():
        if digest(OUT / name) != expected:
            raise ValueError(f'figure asset drift: {name}')
    return manifest


def build():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 16,
                         'svg.hashsalt': 'tbc-v14-release'})
    OUT.mkdir(parents=True, exist_ok=True)
    ink, blue, teal, gray = '#18384a', '#315e87', '#207767', '#59636a'

    def save(fig, name):
        fig.savefig(OUT / (name + '.png'), dpi=220, facecolor='white')
        fig.savefig(OUT / (name + '.svg'), metadata={'Date': None}, facecolor='white')
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6.46))
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set(xlim=(0, 12), ylim=(0, 6.46))
    ax.axis('off')
    ax.text(6, 6.05, 'Where v14 enforces authority', ha='center', weight='bold', color=ink, fontsize=23)

    def box(x, y, w, h, title, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.05,rounding_size=0.08',
                                   linewidth=1.4, edgecolor=color, facecolor='white'))
        ax.text(x+w/2, y+h-.3, title, ha='center', va='center', color=color, weight='bold', fontsize=14)
        ax.text(x+w/2, y+h/2-.15, text, ha='center', va='center', color=ink, fontsize=12, linespacing=1.45)

    def arrow(start, end, color=blue, style='-'):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=17,
                                    linewidth=1.6, color=color, linestyle=style))

    box(.3, 3.45, 2.5, 1.65, 'Untrusted reasoning', 'Agent and retrieved text\nProposes requests\nNo operator keys', gray)
    box(3.5, 3.45, 4.35, 1.65, 'Trusted control service', 'Identity, scope and lineage\nApproval, revocation and budget\nTyped requests and evidence', blue)
    box(8.55, 3.45, 3.1, 1.65, 'Mediated outcomes', 'Record change and memory\nApproved artifact bytes\nDelivery reauthorization', teal)
    arrow((2.85, 4.25), (3.45, 4.25))
    arrow((7.9, 4.25), (8.5, 4.25))
    box(.3, 1.55, 2.5, 1.15, 'AI monitor', 'May restrict authority\nCannot approve or restore', gray)
    box(3.5, 1.55, 4.35, 1.15, 'Integration checks', 'Pinned TLS and artifact digest\nUncertain remote-effect ledger', blue)
    box(8.55, 1.55, 3.1, 1.15, 'Named human authority', 'Approves exact proposals\nRestores within the ceiling', teal)
    arrow((2.85, 2.2), (3.8, 3.4), gray, '--')
    arrow((9.1, 2.75), (7.7, 3.4), teal)
    arrow((6, 3.4), (6, 2.75))
    ax.text(6, .93, 'External deployment obligations', ha='center', weight='bold', color=gray, fontsize=17)
    ax.text(6, .47, 'OS / network isolation  •  authenticated service adapters  •  independent key custody',
            ha='center', color=gray, fontsize=15)
    save(fig, 'architecture')

    values = data()
    fig = plt.figure(figsize=(12, 6.65))
    fig.text(.5, .95, 'Measured behavior on synthetic fixtures', ha='center', weight='bold', color=ink, fontsize=22)
    ax = fig.add_axes([.07, .24, .45, .58])
    labels = ['Unguarded', 'Prompt + allowlist', 'Independent controls']
    for i, item in enumerate(values['comparison']):
        rate = item['contained'] / item['attacks'] * 100
        ax.barh(i, rate, height=.52, color=[gray, blue, teal][i])
        ax.text(max(rate+2, 2), i, f"{item['contained']}/{item['attacks']} ({rate:.1f}%)", va='center', fontsize=14)
    ax.set_yticks(range(3), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 140)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel('Attack containment (%)', fontsize=14)
    ax.set_title('Same 7 hostile proposals in each arm', fontsize=16, pad=18)
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(axis='y', labelsize=13)
    # Keep the labels within the left panel without colliding with the second panel.
    ax.set_position([.2, .28, .32, .51])
    ax.text(0, -.4, 'Benign completion: 2/2 in every arm', transform=ax.transAxes, fontsize=13, color=gray)
    right = fig.add_axes([.6, .25, .37, .58])
    right.axis('off')
    right.text(.5, 1, 'Transfer across six domain profiles', ha='center', fontsize=16)
    right.text(.5, .75, f"{sum(p['contained'] for p in values['domains'])} / {sum(p['attacks'] for p in values['domains'])} hostile scenarios contained", ha='center', fontsize=16, color=teal, weight='bold')
    right.text(.5, .56, f"{sum(p['benign_completed'] for p in values['domains'])} / {sum(p['benign_total'] for p in values['domains'])} benign tasks completed", ha='center', fontsize=16, color=blue, weight='bold')
    right.text(.5, .26, 'Distinct experiment from the three-arm comparison\nCounts are not pooled; profiles use synthetic data.',
               ha='center', fontsize=13, color=gray, linespacing=1.5)
    fig.text(.5, .045, 'Deterministic fixtures, not field rates or live-model accuracy. Two benign tasks do not establish usability.',
             ha='center', fontsize=12, color=gray)
    save(fig, 'evidence')
    manifest = {'data': values, 'sources': {p: digest(ROOT / p) for p in SOURCES},
                'assets': {p.name: digest(p) for p in sorted(OUT.glob('*')) if p.suffix in ('.png', '.svg')},
                'limits': 'Synthetic deterministic fixtures; no inference to attack prevalence or user utility.'}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return verify()


if __name__ == '__main__':
    import sys
    result = verify() if '--check' in sys.argv else build()
    print(json.dumps({'verified': True, 'assets': list(result['assets'])}))
