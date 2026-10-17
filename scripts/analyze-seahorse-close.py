#!/usr/bin/env python3
"""Analyze cast1 close-idle / close-crawl using the wide study's coverage gates."""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics

spec = importlib.util.spec_from_file_location('population', Path(__file__).with_name('analyze-seahorse-population.py'))
population = importlib.util.module_from_spec(spec)
spec.loader.exec_module(population)


def verify_jobs(root):
    frozen = population.read_json(root / 'variants.json')['variants']
    restore = population.read_json(root / 'restore.json')['variants']['pair6']['apk_sha256']
    checked = []
    for relative, job in population.read_json(root / 'jobs.json').items():
        folder = root / relative
        receipt = population.read_json(folder / 'receipt.json')
        if (receipt['job'] != job or receipt['status'] != 'succeeded'
                or receipt['health'] != 'ready' or receipt['device'] != 'chromecast-test-01'
                or receipt['survivors'] or any(not item['restored'] for item in receipt['journal'])):
            raise ValueError(f'Incomplete session or cleanup: {relative}')
        view, round_name = relative.split('/')
        installs = population.read_json(folder / 'apk-installations.json')
        if len(installs) != 4 or {item['variant'] for item in installs} != set(population.COUNTS):
            raise ValueError(f'Unexpected installed populations: {relative}')
        for item in installs:
            name = view + '-' + item['variant'] + ('-cpu' if round_name == 'cpu' else '')
            expected = frozen[name]['apk_sha256']
            if item['status'] != 'verified' or item['installed_sha256'] != expected:
                raise ValueError(f'Installed fixture hash mismatch: {relative}/{name}')
        restored = [item for item in receipt['journal'] if item['key'] == 'variant']
        if len(restored) != 1 or restored[0]['verification']['installed_sha256'] != restore:
            raise ValueError(f'Restoration hash mismatch: {relative}')
        checked.append(dict(source=str(folder / 'receipt.json'), job=job,
                            status=receipt['status'], restored_apk_sha256=restore))
    return checked


def analyze(root):
    selections = population.read_json(root / 'selections.json') if (root / 'selections.json').exists() else {}
    def selected(key):
        return root / selections.get(key, key + '/run-1')
    result = dict(views={}, verified_jobs=verify_jobs(root))
    for view in ('close-idle', 'close-crawl'):
        rows = []
        for label, count in population.COUNTS.items():
            release = [population.presentation(selected(f'{view}/round-{r}/{label}')) for r in (1, 2, 3)]
            cpu_folder = selected(f'{view}/cpu/{label}')
            cpu_presentation = population.presentation(cpu_folder)
            cpu = population.cpu_windows(cpu_folder, cpu_presentation)
            rows.append(dict(pairs=count, release_runs=release,
                median_frame_ms=statistics.median(r['mean_frame_ms'] for r in release),
                median_fps=statistics.median(r['fps'] for r in release),
                frame_ms_range=[min(r['mean_frame_ms'] for r in release), max(r['mean_frame_ms'] for r in release)],
                median_p95_ms=statistics.median(r['p95_ms'] for r in release),
                median_total_pss_mib=statistics.median(r['total_pss_kib'] for r in release)/1024,
                cpu_presentation=cpu_presentation, cpu=cpu))
        baseline = rows[0]
        for row in rows:
            row['frame_ms_delta_vs_none'] = row['median_frame_ms'] - baseline['median_frame_ms']
            row['main_thread_cpu_ms_delta_vs_none'] = row['cpu']['frame_weighted_cpu_ms']['total'] - baseline['cpu']['frame_weighted_cpu_ms']['total']
            row['instrumented_frame_ms_change_percent'] = 100 * (row['cpu_presentation']['mean_frame_ms']/row['median_frame_ms']-1)
        result['views'][view] = rows
    result['wide_controls'] = [dict(pairs=count, **population.presentation(selected(f'wide-idle/control/{label}')))
                               for label, count in population.COUNTS.items()]
    result['notes'] = [
        'Each close case uses three independent 60-second release runs after 15 seconds warmup; values are medians.',
        'Separate CPU runs use only complete five-second windows contained in the measured presentation interval.',
        'CPU total is update + render on the main thread; nested sections overlap and must not be summed.',
        'Direct-launch fixtures fix the existing close camera. Crawl holds right inside the authored Forth input reader; this does not test physical input delivery.',
        'All APKs share byte-identical native libraries and resources. Full source-slot receipts and per-APK hashes are in variants.json.',
        'The four fresh wide controls are single samples, not a replacement for the earlier three-run wide baseline.',
        'All counts allocate twelve residents. None additionally hides six posts; PSS is whole-process memory.',
    ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.evidence)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    for view, rows in result['views'].items():
        print('\n' + view)
        print('| Pairs | Frame ms | FPS | Main CPU ms | PSS MiB |')
        print('|---:|---:|---:|---:|---:|')
        for row in rows:
            print(f"| {row['pairs']} | {row['median_frame_ms']:.2f} | {row['median_fps']:.2f} | {row['cpu']['frame_weighted_cpu_ms']['total']:.2f} | {row['median_total_pss_mib']:.1f} |")


if __name__ == '__main__':
    main()
