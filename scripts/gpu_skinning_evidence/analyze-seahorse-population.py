#!/usr/bin/env python3
"""Summarize the four-count cast1 study from downloaded coordinator evidence.

Requires three release rounds and one CPU-instrumented round. Rejects samples
with missing presentation coverage; CPU windows must lie inside the measured
presentation interval. All summaries retain their source evidence paths.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import statistics
from pathlib import Path

COUNTS = {'none': 0, 'pair1': 1, 'pair2': 2, 'pair6': 6}
WINDOW = re.compile(r'frame-window: start-ns=(\d+) end-ns=(\d+)')
SECTION = re.compile(r'frame-profile: (\S+) frames=(\d+) mean=([\d.]+)')
COUNTER = re.compile(r'frame-count: (\S+) frames=(\d+) mean=([\d.]+)')


def read_text(path):
    if path.exists():
        return path.read_text(errors="replace")
    with gzip.open(str(path) + ".gz", "rt", errors="replace") as source:
        return source.read()


def read_json(path):
    return json.loads(read_text(path))


def pss_kib(path):
    text = read_text(path)
    found = re.search(r'TOTAL PSS:\s*(\d+)', text)
    if not found:
        found = re.search(r'^\s*TOTAL\s+(\d+)\b', text, re.M)
    if not found:
        raise ValueError(f'no total PSS: {path}')
    return int(found[1])


def presentation(folder, require_plant_fixture=True):
    summary = read_json(folder / 'summary.json')
    if summary.get('sampling_holes') or summary.get('latency_statistics_may_include_unobserved_bridges'):
        raise ValueError(f'incomplete presentation sampling: {folder}')
    presents = read_json(folder / 'presents-ns.json')
    if presents != sorted(set(presents)) or len(presents) < 11:
        raise ValueError(f'invalid presentation sequence: {folder}')
    span = (presents[-1] - presents[0]) / 1e9
    if span < 59:
        raise ValueError(f'less than 59 s coverage: {folder}: {span}')
    intervals = [(b-a) / 1e6 for a, b in zip(presents, presents[1:])]
    mean = statistics.mean(intervals)
    if abs(1000 / mean - summary['fps']) > .001:
        raise ValueError(f'summary FPS disagrees with raw timestamps: {folder}')
    log = read_text(folder / 'wf.log')
    marker = log.rfind('zforth: INDEXOF_CAMSHOT = 1921 (expect 1921)')
    if marker < 0:
        raise ValueError(f'no current level-load marker in cumulative log: {folder}')
    current = log[marker:]
    fixture = ('PLANTS settings-source=RPRP seed=713 water=saltwater age=150 speed=0 '
               'textures=1 sway=1 random_entry=0 selector_override=0')
    if require_plant_fixture and fixture not in current:
        raise ValueError(f'wrong or missing authored plant fixture: {folder}')
    for error in ('zforth compile error', 'zforth eval error', 'AssertMsg:', 'out of memory'):
        if error.lower() in current.lower():
            raise ValueError(f'current-run engine error {error!r}: {folder}')
    thermal = read_text(folder / 'thermal.txt')
    status = re.search(r'Thermal Status:\s*(\d+)', thermal)
    return dict(source=str(folder), interval_count=len(intervals),
                mean_frame_ms=mean, fps=1000 / mean,
                p95_ms=sorted(intervals)[int((len(intervals)-1)*.95)],
                observed_seconds=span, total_pss_kib=pss_kib(folder / 'meminfo.txt'),
                thermal_status=int(status[1]) if status else None,
                first_present_ns=presents[0], last_present_ns=presents[-1])


def cpu_windows(folder, presentation_row):
    full = read_text(folder / 'wf.log')
    windows = []
    current = None
    for line in full.splitlines():
        if match := WINDOW.search(line):
            current = dict(start_ns=int(match[1]), end_ns=int(match[2]), sections={}, counters={})
            windows.append(current)
        elif current is not None:
            for pattern, name in ((SECTION, 'sections'), (COUNTER, 'counters')):
                if match := pattern.search(line):
                    current[name][match[1]] = dict(frames=int(match[2]), mean=float(match[3]))
    # Cumulative app logs retain older jobs. Select by the current device's
    # monotonic presentation timestamps, never by an arbitrary number of lines.
    selected = {w['start_ns']: w for w in windows
                if w['start_ns'] >= presentation_row['first_present_ns']
                and w['end_ns'] <= presentation_row['last_present_ns']
                and 'total' in w['sections']}
    windows = list(selected.values())
    if len(windows) < 8:
        raise ValueError(f'fewer than eight fully measured CPU windows: {folder}')
    for w in windows:
        if not {'update', 'render', 'director', 'animation', 'total'} <= set(w['sections']):
            raise ValueError(f'incomplete CPU sections: {folder}')
        sections = w['sections']
        frames = sections['total']['frames']
        if frames <= 0 or any(v['frames'] != frames for v in sections.values()):
            raise ValueError(f'inconsistent CPU frame counts: {folder}')
        if abs(sections['total']['mean'] - sections['update']['mean'] - sections['render']['mean']) > .0003:
            raise ValueError(f'CPU total disagrees with update + render: {folder}')
    def means(group):
        names = set.intersection(*(set(w[group]) for w in windows))
        return {n: sum(w[group][n]['mean'] * w[group][n]['frames'] for w in windows)
                / sum(w[group][n]['frames'] for w in windows) for n in sorted(names)}
    return dict(source=str(folder / 'wf.log'), windows=windows,
                covered_seconds=sum((w['end_ns']-w['start_ns'])/1e9 for w in windows),
                measured_frames=sum(w['sections']['total']['frames'] for w in windows),
                frame_weighted_cpu_ms=means('sections'), frame_weighted_counters=means('counters'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    selections = read_json(args.evidence / 'selections.json') if (args.evidence / 'selections.json').exists() else {}
    rows = []
    for name, count in COUNTS.items():
        release = [presentation(args.evidence / selections.get(f'round-{r}/{name}',
                   f'round-{r}/{name}/run-1')) for r in (1, 2, 3)]
        cpu_folder = args.evidence / selections.get(f'cpu/{name}', f'cpu/{name}/run-1')
        cpu_presentation = presentation(cpu_folder)
        cpu = cpu_windows(cpu_folder, cpu_presentation)
        med = statistics.median
        rows.append(dict(pairs=count, residents=2*count, release_runs=release,
                         median_frame_ms=med(r['mean_frame_ms'] for r in release),
                         median_fps=med(r['fps'] for r in release),
                         frame_ms_range=[min(r['mean_frame_ms'] for r in release), max(r['mean_frame_ms'] for r in release)],
                         median_p95_ms=med(r['p95_ms'] for r in release),
                         median_total_pss_mib=med(r['total_pss_kib'] for r in release)/1024,
                         total_pss_mib_range=[min(r['total_pss_kib'] for r in release)/1024,
                                              max(r['total_pss_kib'] for r in release)/1024],
                         cpu_presentation=cpu_presentation, cpu=cpu))
    baseline = rows[0]
    for row in rows:
        row['instrumented_frame_ms_change_percent'] = 100 * (row['cpu_presentation']['mean_frame_ms'] / row['median_frame_ms'] - 1)
        row['frame_ms_delta_vs_none'] = row['median_frame_ms'] - baseline['median_frame_ms']
        row['fps_change_percent_vs_none'] = 100 * (row['median_fps'] / baseline['median_fps'] - 1)
        row['main_thread_cpu_ms_delta_vs_none'] = (row['cpu']['frame_weighted_cpu_ms']['total']
            - baseline['cpu']['frame_weighted_cpu_ms']['total'])
    result = dict(rows=rows, notes=[
        'Release values are medians of three independent 60-second wide-idle runs.',
        'CPU values are frame-weighted means of fully contained five-second profiling windows from separate instrumented runs.',
        'CPU total is update + render main-thread CPU time; it excludes presentation waits and is not whole-process CPU time.',
        'All populations allocate the same twelve residents. None also hides the six posts; memory is process PSS, not per-resident allocation cost.',
        'This experiment does not measure close views, crawling or GPU skinning.',
    ])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print('| Pairs | Mean frame ms | FPS | Main-thread CPU ms | PSS MiB |')
    print('|---:|---:|---:|---:|---:|')
    for r in rows:
        print(f"| {r['pairs']} | {r['median_frame_ms']:.2f} | {r['median_fps']:.2f} | "
              f"{r['cpu']['frame_weighted_cpu_ms']['total']:.2f} | {r['median_total_pss_mib']:.1f} |")


if __name__ == '__main__':
    main()
