#!/usr/bin/env python3
"""Plot both recorded soaks; mark initial entry, every reload, and the final 10 min.

Run normally to render from the adjacent CSVs (no raw evidence needed).
Use --extract to regenerate CSVs from sample JSON, logcat and dumpsys meminfo.
Memory values remain KiB in CSVs and are divided by 1024 for MiB in plots.
"""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'wf-memory-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

BASE = Path(__file__).resolve().parent
TZ = dt.timezone(dt.timedelta(hours=7))


def device_time(line):
    stamp = dt.datetime.strptime('2026-' + line[:18], '%Y-%m-%d %H:%M:%S.%f')
    return stamp.replace(tzinfo=TZ).timestamp()


def extract(folder):
    starts = sorted(device_time(line) for line in json.loads((folder / 'markers.json').read_text()))
    rows = []
    for sample in json.loads((folder / 'sample-values.json').read_text()):
        log = (folder / 'evidence' / sample['logcat']).read_text(errors='replace')
        gc_times = [device_time(line) for line in log.splitlines() if 'Explicit' in line and ' GC ' in line]
        assert gc_times, sample['logcat']
        when = gc_times[-1]
        mem = (folder / 'evidence' / sample['meminfo']).read_text()
        detail, summary = mem.split('App Summary', 1)

        def pss(name):
            match = re.search(r'^\s*' + re.escape(name) + r'\s+(\d+)', detail, re.M)
            assert match, (sample['meminfo'], name)
            return int(match[1])

        code_summary = re.search(r'^\s*Code:\s+(\d+)', summary, re.M)
        assert code_summary
        total = pss('TOTAL')
        assert total == sample['total_pss_kb'], sample['meminfo']
        previous = [t for t in starts if t <= when]
        assert previous
        rows.append(dict(sample=sample['meminfo'].split('-')[2], device_unix_s=f'{when:.3f}',
                         elapsed_s=f'{when-starts[0]:.3f}',
                         device_local_time=dt.datetime.fromtimestamp(when, TZ).isoformat(timespec='milliseconds'),
                         tank=len(previous), phase_s=f'{when-previous[-1]:.3f}',
                         total_pss_kib=total, gl_mtrack_pss_kib=pss('GL mtrack'),
                         native_heap_pss_kib=pss('Native Heap'), dalvik_heap_pss_kib=pss('Dalvik Heap'),
                         mapped_code_pss_kib=sum(pss(name) for name in ['.so mmap', '.jar mmap', '.apk mmap', '.dex mmap', '.oat mmap']),
                         code_app_summary_kib=int(code_summary[1])))
    with (folder / 'memory-samples.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    with (folder / 'level-resets.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['reload', 'event', 'device_unix_s', 'elapsed_s'], lineterminator='\n')
        writer.writeheader()
        writer.writerows(dict(reload=i, event='initial entry' if i == 0 else 'level reset',
                              device_unix_s=f'{t:.3f}', elapsed_s=f'{t-starts[0]:.3f}')
                         for i, t in enumerate(starts))


def plot(name, title, job):
    folder = BASE / name
    with (folder / 'memory-samples.csv').open() as f:
        rows = list(csv.DictReader(f))
    with (folder / 'level-resets.csv').open() as f:
        resets = list(csv.DictReader(f))
    x = [float(r['elapsed_s']) / 60 for r in rows]
    reset_x = [float(r['elapsed_s']) / 60 for r in resets]
    final_start = x[-1] - 10
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True,
                             gridspec_kw={'height_ratios': [1.35, 1.2, 1]})
    fig.subplots_adjust(top=.86, bottom=.11, left=.075, right=.985, hspace=.28)
    fig.suptitle('Planted Tank · ' + title, x=.075, ha='left', y=.98, fontsize=19, weight='bold')
    fig.text(.075, .942, f'cast2  ·  {job}  ·  8× growth, 5 s hold  ·  {len(resets)-1} level resets  ·  {len(rows)} samples', fontsize=11)
    fig.legend(handles=[Line2D([], [], color='#697586', linestyle='--', linewidth=.8, label='Level reset'),
                        Line2D([], [], marker='^', color='#697586', linestyle='None', label='Reset number (every tenth labelled)'),
                        Patch(facecolor='#fff0ce', label='Final 10 minutes')],
               loc='upper left', bbox_to_anchor=(.068, .926), ncol=3, frameon=False, fontsize=10)
    colors = {'total_pss_kib': '#163d70', 'gl_mtrack_pss_kib': '#20856b', 'native_heap_pss_kib': '#d86c1d',
              'dalvik_heap_pss_kib': '#a65c94', 'mapped_code_pss_kib': '#7656a2', 'code_app_summary_kib': '#007f9b'}
    def curve(ax, key, label):
        values = [int(r[key]) / 1024 for r in rows]
        ax.plot(x, values, '.-', color=colors[key], label=label, linewidth=1.5, markersize=4)
    curve(axes[0], 'total_pss_kib', 'Total PSS')
    curve(axes[1], 'gl_mtrack_pss_kib', 'Graphics (GL mtrack PSS)')
    curve(axes[1], 'native_heap_pss_kib', 'Native heap PSS')
    curve(axes[1], 'mapped_code_pss_kib', 'Mapped code PSS')
    curve(axes[2], 'code_app_summary_kib', 'Code (Android App Summary)')
    curve(axes[2], 'dalvik_heap_pss_kib', 'Dalvik heap PSS')
    for ax in axes:
        ax.axvspan(max(0, final_start), x[-1], color='#fff0ce', zorder=0)
        ax.axvline(0, color='#697586', linewidth=.9)
        for t in reset_x[1:]:
            ax.axvline(t, color='#697586', linestyle='--', alpha=.28, linewidth=.65, zorder=0)
        ax.grid(axis='y', color='#dce1e7', linewidth=.7)
        ax.set_ylabel('Memory (MiB)')
        ax.spines[['top', 'right']].set_visible(False)
        ax.legend(loc='upper right', fontsize=9, framealpha=.95)
        ax.set_ylim(bottom=0)
    total_mib = [int(r['total_pss_kib']) / 1024 for r in rows]
    axes[0].set_ylim(min(total_mib) - 3, max(total_mib) + 5)
    for i, t in enumerate(reset_x):
        axes[0].plot(t, 1.015, marker='^', color='#697586', markersize=3, transform=axes[0].get_xaxis_transform(), clip_on=False)
        if i == 0 or i % 10 == 0:
            axes[0].text(t, 1.045, 'entry' if i == 0 else str(i), ha='center', fontsize=8, color='#475467',
                         transform=axes[0].get_xaxis_transform())
    axes[-1].set_xlim(-.15, max(x[-1], reset_x[-1]) + .2)
    axes[-1].set_xlabel('Minutes since initial level entry (device clock)')
    fig.text(.075, .035, 'Points are recorded measurements; lines connect samples, not continuous telemetry. Reset times: OAD tank-start logs.\n'
             'Sample times: meminfo-triggered GC logs on the same device clock. Mapped code sums .so/.jar/.apk/.dex/.oat PSS; Code summary is separate. Curves are not additive.',
             fontsize=9, color='#475467')
    for suffix in ['svg', 'png']:
        destination = folder / ('memory-timeline.' + suffix)
        fig.savefig(destination, dpi=160, facecolor='white')
        if suffix == 'svg':
            destination.write_text('\n'.join(line.rstrip() for line in destination.read_text().splitlines()) + '\n')
    plt.close(fig)
    print(f'{name}: {len(rows)} samples, {len(resets)-1} resets; wrote SVG/PNG')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', action='store_true', help='Regenerate CSVs from raw evidence')
    args = parser.parse_args()
    for name, title, job in [('soak', 'continuous sampling', 'J‑bf9150654784'),
                             ('soak-phase', 'phase-locked sampling', 'J‑dadba4fb4900')]:
        if args.extract or not (BASE / name / 'memory-samples.csv').exists():
            extract(BASE / name)
        plot(name, title, job)


if __name__ == '__main__':
    main()
