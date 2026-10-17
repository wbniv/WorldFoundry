#!/usr/bin/env python3
"""Publish measured tables only after all three skinning campaigns validate.

The optional wait monitors local progress files. Device ownership and testing
remain with the coordinator campaign runners. Does not commit or change defaults.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('skinning', Path(__file__).with_name('analyze-gpu-skinning.py'))
skinning = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skinning)


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(value)
    temporary.replace(path)


def comparison_table(rows, population=False):
    heading = 'Bodies' if population else 'Pairs'
    lines = [f'| {heading} | CPU FPS | GPU FPS | CPU render ms | GPU render ms | Render CPU change | p95 CPU / GPU ms | Missed refresh CPU / GPU % | PSS CPU / GPU MiB |',
             '|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        c, g = row['cpu'], row['gpu']
        cr = c['cpu_profile']['median_window_cpu_ms']['render']
        gr = g['cpu_profile']['median_window_cpu_ms']['render']
        cm, gm = c['median'], g['median']
        count = row['actors' if population else 'pairs']
        lines.append(f"| {count} | {cm['fps']:.2f} | {gm['fps']:.2f} | {cr:.3f} | {gr:.3f} | "
                     f"{row['median_render_cpu_change_percent']:+.1f}% | {cm['p95_ms']:.2f} / {gm['p95_ms']:.2f} | "
                     f"{cm['missed_refresh_percent']:.2f} / {gm['missed_refresh_percent']:.2f} | "
                     f"{cm['total_pss_kib']/1024:.1f} / {gm['total_pss_kib']/1024:.1f} |")
    return '\n'.join(lines)


def upload_table(rows, population=False):
    heading = 'Bodies' if population else 'Pairs'
    lines = [f'| {heading} | CPU rig vertex KiB/frame | GPU rig vertex KiB/frame | GPU palette KiB/frame | CPU index KiB/frame | GPU index KiB/frame | GPU resident skin MiB |',
             '|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        c = row['cpu']['cpu_profile']['frame_weighted_counters']
        g = row['gpu']['cpu_profile']['frame_weighted_counters']
        memory = g['skin-gpu-bytes']
        shown = f'{memory/1048576:.3f}'
        count = row['actors' if population else 'pairs']
        lines.append(f"| {count} | {c['skin-vertex-bytes']/1024:.2f} | {g['skin-vertex-bytes']/1024:.2f} | "
                     f"{g['skin-palette-bytes']/1024:.2f} | {c['skin-index-bytes']/1024:.2f} | "
                     f"{g['skin-index-bytes']/1024:.2f} | {shown} |")
    return '\n'.join(lines)


def cpu_sections_table(rows, population=False, modes=('cpu', 'gpu')):
    heading = 'Bodies' if population else 'Pairs'
    lines = [f'| {heading} | Mode | Pose ms | Vertices ms | Normals ms | Cull ms | Object submit ms | Total CPU ms | Profile frame-time change % |',
             '|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        for mode in modes:
            sections = row[mode]['cpu_profile']['frame_weighted_cpu_ms']
            values = ' | '.join('unavailable' if name == 'skin-cull' else f'{sections[name]:.4f}' for name in
                                ['skin-pose', 'skin-vertices', 'skin-normals', 'skin-cull', 'skin-submit', 'total'])
            count = row['actors' if population else 'pairs']
            lines.append(f"| {count} | {mode} | {values} | {row[mode]['profile_presented_frame_change_percent']:+.2f} |")
    return '\n'.join(lines)


def report(root):
    # Each analyzer verifies all receipts, installed/restore hashes, raw
    # timestamps, actual GPU draws, steady uploads and contained CPU windows.
    aquarium = skinning.analyze(root)
    populations = {device: skinning.analyze(root / name, True, device)
                   for name, device in [('cast1-populations', 'chromecast-test-01'),
                                        ('cast2-populations', 'chromecast-test-02')]}
    data = dict(aquarium=aquarium, populations=populations,
                adoption='Not adopted; CPU remains the default. Startup reliability remains unresolved.',
                gpu_time_ms=None)
    text = ['# GPU skinning measured comparison', '',
            'All 48 aquarium release runs and 16 aquarium CPU profiles, plus 36 release runs and 12 CPU profiles per device in the controlled population study, validated.', '',
            'Release FPS, p95 and missed-refresh values are medians of three independent runs. CPU render values are medians of contained five-second window means from a separate instrumented session. Memory is whole-process PSS; uploads are measured rig counters. Detailed ranges, p50/p99, thermal status, draw counts, memory gauges, source paths and receipts are retained in [results.json](results.json).', '',
            '**CPU remains the default.** The experiment does not authorize production adoption or merge. Cast1 startup failures before measurement remain unresolved and are excluded from timing. No GPU timer result or energy measurement is available.', '']
    for view, rows in aquarium['views'].items():
        text += ['## Cast1 ' + view, '', comparison_table(rows), '', upload_table(rows), '',
                 cpu_sections_table(rows), '',
                 'Section costs are frame-weighted means. Submit includes nested culling; total CPU is update + render, never a sum of nested sections.', '']
    for device, result in populations.items():
        rows = result['views']['population']
        text += ['## ' + device + ': controlled DFRM bodies', '',
                 '868 vertices, 35 curve samples and 40 palette entries per body; no fins, plants or behaviour AI. These are not general skeletal-authoring measurements.', '',
                 comparison_table(rows, True), '', upload_table(rows, True), '',
                 '| Bodies | C FPS | C0 FPS | G0 FPS | G1 FPS |', '|---:|---:|---:|---:|---:|']
        for row in rows:
            values = ' | '.join(f"{row[mode]['median']['fps']:.2f}" for mode in ['cpu', 'cpu-no-cull', 'gpu-no-cull', 'gpu'])
            text.append(f"| {row['actors']} | {values} |")
        eligible = [str(row['actors']) for row in rows if row['median_render_cpu_change_percent'] <= -10]
        threshold = ('The sampled populations meeting the 10% render-CPU reduction threshold are: '
                     + ', '.join(eligible) + ' bodies.') if eligible else 'No sampled population meets the 10% render-CPU reduction threshold.'
        text += ['', threshold + ' This reports only the CPU threshold, not a complete acceptance verdict or an interpolated crossover.', '',
                 'C0/G0 explain the cost of culling; G1 versus C is the intended comparison. Cases near the display limit do not establish equal CPU cost.', '',
                 cpu_sections_table(rows, True, ('cpu', 'cpu-no-cull', 'gpu-no-cull', 'gpu')), '',
                 'Section costs are frame-weighted means. Submit includes nested culling; total CPU is update + render, never a sum of nested sections.', '']
    text += ['## Correctness and remaining limits', '',
             'Local GL images agree on the real aquarium and controlled population scenes. The Metal offscreen fixture passes real draws, four influences, normals, fog, culling and resource recreation; Apple aquarium performance is unmeasured.', '',
             'Both casts passed release GPU Home/resume with surface recreation and a reused EGL context. Full device EGL context loss was not forced. Separate diagnostic snapshots verified hardware movement and releases in four directions on both casts; their later native-IME/keypad UI assertion failed, so neither full UI validator passed. Those directions use the freshwater player; GPU body rendering is checked separately in saltwater.', '',
             'The final recommendation remains to retain the CPU default until the startup exits and remaining production gates are resolved. Performance improvements alone do not close those gates.', '']
    investigation = ROOT / 'docs/investigations/2026-10-16-mesh-deformers-vs-joint-rigs.md'
    content = investigation.read_text()
    heading = '## GPU skinning experiment:'
    if content.count(heading) != 1:
        raise ValueError('Expected one investigation results section')
    start = content.index(heading)
    end = content.index('## Back-face culling, and why moving vertices collides with it', start)
    section = ['## GPU skinning experiment: completed timing matrix', '',
               'The approved experiment completed the matched aquarium and controlled population timing matrix in its own worktree. CPU remains the default; startup reliability is unresolved, and production adoption is not approved.', '',
               'The tables below contain measured release medians and separate median CPU-window render costs, not estimates.', '']
    for view, rows in aquarium['views'].items():
        section += ['### Cast1 ' + view, '', comparison_table(rows), '']
    for device, result in populations.items():
        section += ['### ' + device + ': controlled 1/4/16 DFRM bodies', '', comparison_table(result['views']['population'], True), '']
    relative = '../plans/2026-10-16-gpu-skinning-chromecast-experiment/evidence/comparison.md'
    section += [f'[Full comparison, measured uploads, memory, culling variants and limitations]({relative}). GPU time remains unavailable. These results measure the existing DFRM adapter, not general skeletal authoring or animation sampling. The earlier historical baseline is context; use the fresh matched CPU runs for the comparison.', '',
                'Both release GPU surface/resume checks passed with a reused EGL context. Fresh diagnostic input checks verified held/released movement on both casts before a later unrelated keypad assertion failed. Cast1 startup failures are retained and excluded from timing; their cause remains unproven. The recommendation is to retain the CPU default until startup reliability and the production gates are resolved.', '']
    # Complete validation and rendering before publishing; no partial campaign
    # may replace either the measured comparison or the investigation section.
    save(root / 'results.json', json.dumps(data, indent=2) + '\n')
    save(root / 'comparison.md', '\n'.join(text))
    save(investigation, content[:start] + '\n'.join(section) + '\n' + content[end:])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    if args.wait:
        previous = None
        while True:
            states = []
            for folder in [args.evidence, args.evidence / 'cast1-populations', args.evidence / 'cast2-populations']:
                path = folder / 'campaign-progress.json'
                state = json.loads(path.read_text()) if path.exists() else dict(state='not-started', completed=[])
                if state['state'] == 'stopped':
                    raise ValueError('Campaign stopped; no report published: ' + str(folder))
                states.append((folder.name, state['state'], len(state['completed'])))
            if states != previous:
                print(states, flush=True)
                previous = states
            if all(state == 'complete' for _, state, _ in states):
                break
            time.sleep(15)
    report(args.evidence)
    print('Complete matrix validated; published comparison and investigation update.', flush=True)


if __name__ == '__main__':
    main()
