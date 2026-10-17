#!/usr/bin/env python3
"""Plot measured close-view FPS and frame-time interpolation for 3–5 pairs."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def series(rows):
    measured = {r['pairs']: r for r in rows}
    if set(measured) != {0, 1, 2, 6}:
        raise ValueError('Expected measured None / 1 / 2 / 6 pairs')
    start, end = (measured[n]['median_frame_ms'] for n in (2, 6))
    estimates = [dict(pairs=n, frame_ms=start + (end-start)*(n-2)/4,
                      measured=False) for n in (3, 4, 5)]
    for item in estimates:
        item['fps'] = 1000 / item['frame_ms']
    return measured, estimates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', type=Path, required=True)
    parser.add_argument('--out-prefix', type=Path, required=True)
    args = parser.parse_args()
    comparison = json.loads(args.comparison.read_text())
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.7), sharey=True)
    measured_colour, estimated_colour = '#17669b', '#a64b00'
    results = dict(method='Linear interpolation of median frame time between measured 2 and 6 pairs; FPS = 1000/frame_ms.',
                   source=str(args.comparison), views={})
    for ax, (view, title) in zip(axes, (('close-idle', 'Close idle'), ('close-crawl', 'Close crawl'))):
        measured, estimates = series(comparison['views'][view])
        results['views'][view] = dict(measured=[dict(pairs=n, frame_ms=r['median_frame_ms'], fps=r['median_fps'])
                                               for n, r in sorted(measured.items())], interpolated=estimates)
        counts = sorted(measured)
        fps = [measured[n]['median_fps'] for n in counts]
        errors = [[measured[n]['median_fps']-1000/measured[n]['frame_ms_range'][1] for n in counts],
                  [1000/measured[n]['frame_ms_range'][0]-measured[n]['median_fps'] for n in counts]]
        ax.errorbar(counts, fps, yerr=errors, fmt='o', color=measured_colour, capsize=3, ms=6, zorder=3)
        ax.plot([0, 1, 2], [measured[n]['median_fps'] for n in (0, 1, 2)], color=measured_colour, lw=1.4)
        xs = [2 + 4*i/100 for i in range(101)]
        first, last = (measured[n]['median_frame_ms'] for n in (2, 6))
        ax.plot(xs, [1000/(first+(last-first)*(x-2)/4) for x in xs], '--', color=estimated_colour, lw=1.4)
        ax.scatter([r['pairs'] for r in estimates], [r['fps'] for r in estimates],
                   marker='s', facecolors='white', edgecolors=estimated_colour, s=40, zorder=4)
        for n, r in measured.items():
            ax.annotate(f"{r['median_fps']:.2f}", (n, r['median_fps']), xytext=(0, 10),
                        textcoords='offset points', ha='center', color=measured_colour, fontsize=9)
        for r in estimates:
            ax.annotate(f"{r['fps']:.2f}", (r['pairs'], r['fps']), xytext=(0, 10),
                        textcoords='offset points', ha='center', color=estimated_colour, fontsize=9)
        ax.set(title=title, xlabel='Seahorse pairs', xlim=(-.35, 6.35), ylim=(0, 25))
        ax.set_xticks(range(7), ['None', '1', '2', '3', '4', '5', '6'])
        ax.set_yticks(range(0, 26, 5))
        ax.grid(axis='y', alpha=.2)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('Median FPS')
    fig.suptitle('Seahorse population on cast1', fontsize=15, y=.98)
    fig.legend(handles=[Line2D([], [], color=measured_colour, marker='o', linestyle='none', label='Measured (3 runs; bars show run range)'),
                        Line2D([], [], color=estimated_colour, marker='s', markerfacecolor='white', linestyle='--', label='Interpolated; not measured')],
               loc='lower center', bbox_to_anchor=(.5, .10), ncol=2, frameon=False, fontsize=9)
    fig.text(.5, .045, '3–5 pairs: interpolate frame time between 2 and 6, then convert to FPS.\n60-second release runs after 15 seconds warmup · saltwater · seed 713 · age 150 · growth paused',
             ha='center', fontsize=8, color='#444444')
    fig.tight_layout(rect=(0, .19, 1, .94))
    args.out_prefix.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out_prefix.with_suffix('.png'), dpi=170)
    fig.savefig(args.out_prefix.with_suffix('.svg'), metadata={'Date': None})
    args.out_prefix.with_suffix('.json').write_text(json.dumps(results, indent=2) + '\n')
    for n in (3, 4, 5):
        print(n, {v: next(r['fps'] for r in data['interpolated'] if r['pairs'] == n) for v, data in results['views'].items()})


if __name__ == '__main__':
    main()
