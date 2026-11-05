"""Reproduce descriptive A/B results from the displayed-value CSV snapshot.

Run from any directory. All paths resolve relative to this repository.
The source workbook is linked in data/README.md. Values are display precision,
so use its recorded energy column instead of squaring rounded voltage values.
"""

from pathlib import Path
import csv
import json
import statistics

import numpy as np
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/ab-comparison'
FIGURES = ROOT / 'assets/figures'


def read(name):
    with (DATA / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def value(row, name):
    return float(row[name])


def main():
    single = read('single-step.csv')
    quasi = read('quasi-open-circuit.csv')
    multi = read('multi-step.csv')
    assert len(single) == 200 and len(quasi) == 120 and len(multi) == 30
    for structure in ['A', 'B']:
        assert len([r for r in single if r['structure'] == structure]) == 100
        assert len([r for r in quasi if r['structure'] == structure]) == 60
        for group in range(1, 6):
            assert sorted(int(r['trial']) for r in single if r['structure'] == structure and int(r['group']) == group) == list(range(1, 21))
    for row in quasi:
        assert abs(value(row, 'vmax_v') - value(row, 'vmin_v') - value(row, 'vpp_v')) < 0.011
    for row in single:
        assert value(row, 'voltage_before_display_v') == 0
        v1 = value(row, 'voltage_after_display_v')
        # One-decimal voltage and energy displays have +/-0.05 rounding cells.
        lower = 2.35 * max(0, v1 - 0.05) ** 2 - 0.0501
        upper = 2.35 * (v1 + 0.05) ** 2 + 0.0501
        assert lower <= value(row, 'recorded_energy_display_uj') <= upper
    for row in multi:
        # Two-decimal voltage and energy displays have +/-0.005 rounding cells.
        v0 = value(row, 'voltage_before_display_v')
        assert v0 == 0
        v1 = value(row, 'voltage_after_display_v')
        lower = 2.35 * max(0, v1 - 0.005) ** 2 - 0.0051
        upper = 2.35 * (v1 + 0.005) ** 2 + 0.0051
        assert lower <= value(row, 'recorded_energy_display_uj') <= upper

    summary = []
    for kind, records, field in [('single_step', single, 'recorded_energy_display_uj'), ('quasi_open_circuit', quasi, 'vpp_v')]:
        for structure in ['A', 'B']:
            values = [value(r, field) for r in records if r['structure'] == structure]
            summary.append(dict(test=kind, structure=structure, steps=1, n=len(values), metric=field, mean=statistics.mean(values), sample_sd=statistics.stdev(values)))
    for steps in [5, 10, 20]:
        for structure in ['A', 'B']:
            values = [value(r, 'recorded_energy_display_uj') for r in multi if r['structure'] == structure and int(r['steps']) == steps]
            assert len(values) == 5
            summary.append(dict(test='multi_step', structure=structure, steps=steps, n=len(values), metric='recorded_energy_display_uj', mean=statistics.mean(values), sample_sd=statistics.stdev(values)))
    with (DATA / 'summary.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.titleweight': 'bold', 'svg.fonttype': 'none'})
    colors = {'A': '#496b90', 'B': '#bd573c'}
    labels = {'A': 'A · V1-derived', 'B': 'B · V3'}
    rng = np.random.default_rng(342)
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 5.0), gridspec_kw={'width_ratios': [1, 1.4]})
    fig.subplots_adjust(left=0.075, right=0.98, bottom=0.22, top=0.82, wspace=0.34)
    fig.suptitle('Stored capacitor energy: sponge baseline and center-punch mechanism', x=0.075, y=0.96, ha='left', fontsize=14, weight='bold')
    fig.text(0.075, 0.895, '4.7 μF capacitor · single-disc structures · workbook display snapshot, 4 Nov 2026', color='#505050', fontsize=10)
    ax = axes[0]
    for x, structure in enumerate(['A', 'B'], 1):
        values = np.array([value(r, 'recorded_energy_display_uj') for r in single if r['structure'] == structure])
        ax.scatter(x + rng.uniform(-0.19, 0.19, len(values)), values, color=colors[structure], s=15, alpha=0.42, linewidths=0, zorder=2)
        mean = float(values.mean())
        ax.plot([x-0.26, x+0.26], [mean, mean], color=colors[structure], linewidth=2.5, zorder=4)
        ax.text(x, 115, f'{mean:.1f} μJ', ha='center', color=colors[structure], weight='bold', fontsize=11)
    ax.set(title='Single step', ylabel='Recorded stored energy (μJ)', xticks=[1, 2], xticklabels=[labels['A'], labels['B']], xlim=(0.5, 2.5), ylim=(0, 125))
    ax.grid(axis='y', color='#e5e5e5', linewidth=0.7)
    ax.set_axisbelow(True)
    ax = axes[1]
    for structure in ['A', 'B']:
        xvalues, means, sds = [], [], []
        for steps in [5, 10, 20]:
            vals = np.array([value(r, 'recorded_energy_display_uj') for r in multi if r['structure'] == structure and int(r['steps']) == steps])
            xpos = steps + (-0.3 if structure == 'A' else 0.3)
            ax.scatter(xpos + rng.uniform(-0.12, 0.12, len(vals)), vals, color=colors[structure], s=22, alpha=0.55, linewidths=0, zorder=3)
            xvalues.append(xpos)
            means.append(float(vals.mean()))
            sds.append(float(vals.std(ddof=1)))
        ax.errorbar(xvalues, means, yerr=sds, fmt='o-', color=colors[structure], capsize=4, linewidth=1.8, markersize=5, label=labels[structure], zorder=4)
    ax.set(title='Accumulated charging', xlabel='Steps per charging run', ylabel='Total stored energy (μJ)', xticks=[5,10,20], ylim=(0,1750))
    ax.grid(axis='y', color='#e5e5e5', linewidth=0.7)
    ax.set_axisbelow(True)
    ax.legend(loc='upper left', frameon=False)
    fig.text(0.075, 0.092, 'Left: 100 records per structure and mean lines. Right: five runs per condition; error bars show sample SD.', color='#505050', fontsize=9)
    fig.text(0.075, 0.052, 'Descriptive results from displayed energy cells. Input mechanical energy was not measured; these are not efficiency values.', color='#505050', fontsize=9)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / 'ab-energy-comparison.png', dpi=180, facecolor='white')
    fig.savefig(FIGURES / 'ab-energy-comparison.svg', facecolor='white')
    plt.close(fig)
    ratio = summary[1]['mean'] / summary[0]['mean']
    print(json.dumps(dict(checks='passed', single_step_mean_ratio_B_over_A=ratio, summary=summary), indent=2))


if __name__ == '__main__':
    main()
