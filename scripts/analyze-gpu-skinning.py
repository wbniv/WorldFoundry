#!/usr/bin/env python3
"""Analyze matched aquarium skinning runs; refuse partial or fallback GPU evidence.

Evidence layout: <view>/<cpu|gpu>/<round-1|round-2|round-3|profile>/<count>/run-1.
Each session folder needs its downloaded coordinator receipt and installations.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics

spec = importlib.util.spec_from_file_location('population', Path(__file__).with_name('analyze-seahorse-population.py'))
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def presentation(folder, mode, pairs):
    row = baseline.presentation(folder)
    summary = baseline.read_json(folder / 'summary.json')
    for name in ['refresh_ms', 'p50_ms', 'p99_ms', 'missed_refresh_percent']:
        row[name] = summary[name]
    if mode == 'gpu' and pairs:
        log = baseline.read_text(folder / 'wf.log')
        current = log[log.rfind('zforth: INDEXOF_CAMSHOT = 1921 (expect 1921)'):]
        if 'skinning: effective=gpu vertices=868 faces=1027 palette=40' not in current:
            raise ValueError(f'No actual GPU body draw: {folder}')
        if 'skinning: effective=cpu' in current:
            raise ValueError(f'GPU fallback occurred: {folder}')
    return row


def analyze(root):
    frozen = baseline.read_json(root / 'variants.json')['variants']
    campaign = baseline.read_json(root / 'campaign.json')
    jobs = baseline.read_json(root / 'jobs.json')
    verified = []
    for view in ['close-idle', 'close-crawl']:
        for mode in ['cpu', 'gpu']:
            for run in ['round-1', 'round-2', 'round-3', 'profile']:
                key = f'{view}/{mode}/{run}'
                folder = root / key
                receipt = baseline.read_json(folder / 'receipt.json')
                if (receipt['job'] != jobs[key] or receipt['status'] != 'succeeded'
                        or receipt['health'] != 'ready' or receipt['device'] != 'chromecast-test-01'
                        or receipt['survivors'] or any(not j['restored'] for j in receipt['journal'])):
                    raise ValueError(f'Incomplete coordinator session/cleanup: {key}')
                installs = baseline.read_json(folder / 'apk-installations.json')
                if len(installs) != 4 or {i['variant'] for i in installs} != set(baseline.COUNTS):
                    raise ValueError(f'Unexpected populations: {key}')
                for item in installs:
                    fixture = f"{view}-{item['variant']}-{mode}" + ('-profile' if run == 'profile' else '')
                    if item['status'] != 'verified' or item['installed_sha256'] != frozen[fixture]['apk_sha256']:
                        raise ValueError(f'Fixture hash mismatch: {key}/{fixture}')
                restored = [j for j in receipt['journal'] if j['key'] == 'variant']
                if len(restored) != 1 or restored[0]['verification']['installed_sha256'] != campaign['restore_sha256']:
                    raise ValueError(f'Restore hash mismatch: {key}')
                verified.append(dict(source=str(folder / 'receipt.json'), job=jobs[key]))
    result = dict(verified_jobs=verified, views={}, gpu_time_ms=None,
                  gpu_time_note='No supported GPU timer evidence; presentation and thread CPU only.')
    for view in ['close-idle', 'close-crawl']:
        rows = []
        for count, pairs in baseline.COUNTS.items():
            row = dict(pairs=pairs)
            for mode in ['cpu', 'gpu']:
                runs = [presentation(root / view / mode / f'round-{r}' / count / 'run-1', mode, pairs) for r in [1, 2, 3]]
                folder = root / view / mode / 'profile' / count / 'run-1'
                instrumented = presentation(folder, mode, pairs)
                cpu = baseline.cpu_windows(folder, instrumented)
                sections, counters = cpu['frame_weighted_cpu_ms'], cpu['frame_weighted_counters']
                if not {'skin-pose', 'skin-vertices', 'skin-normals', 'skin-cull', 'skin-submit'} <= sections.keys():
                    raise ValueError(f'Missing rig CPU sections: {folder}')
                if mode == 'gpu':
                    for key in ['skin-vertex-bytes', 'skin-index-bytes', 'skin-rebuilds', 'skin-fallbacks']:
                        if counters[key] != 0:
                            raise ValueError(f'Unexpected steady GPU {key}: {folder}')
                    if pairs and not (counters['skin-draws'] > 0 and counters['skin-palette-bytes'] > 0):
                        raise ValueError(f'No measured GPU work: {folder}')
                if mode == 'cpu' and pairs and counters['skin-vertex-bytes'] <= 0:
                    raise ValueError(f'Missing CPU rig stream upload accounting: {folder}')
                row[mode] = dict(release_runs=runs, cpu_profile=cpu, instrumented_presentation=instrumented,
                    median={k: statistics.median(r[k] for r in runs) for k in ['mean_frame_ms', 'fps', 'p50_ms', 'p95_ms', 'p99_ms', 'missed_refresh_percent', 'total_pss_kib']},
                    frame_ms_range=[min(r['mean_frame_ms'] for r in runs), max(r['mean_frame_ms'] for r in runs)])
            c, g = row['cpu'], row['gpu']
            row['render_cpu_change_percent'] = 100 * (g['cpu_profile']['frame_weighted_cpu_ms']['render'] / c['cpu_profile']['frame_weighted_cpu_ms']['render'] - 1)
            row['presented_frame_change_percent'] = 100 * (g['median']['mean_frame_ms'] / c['median']['mean_frame_ms'] - 1)
            rows.append(row)
        result['views'][view] = rows
    result['notes'] = [
        'Fresh CPU/GPU paths use identical native code and cooked assets; installed hashes and cleanup are verified.',
        'Release presentation and separate instrumented CPU results must not be combined into a single timing.',
        'Skin submit includes nested culling; total is update plus render, never a sum of nested sections.',
        'Skin vertex bytes include the actual CPU rig share of mixed streamed batches and GPU resource creation; steady GPU uses palette bytes.',
        'Skin draws/faces are GPU-path counters; overall draws/faces cover CPU and GPU.',
        'All aquarium counts allocate twelve residents; None also hides six posts. Memory is whole-process PSS plus separately reported skin resource gauges.',
        'Crawl holds right in authored Forth; this does not verify delivery/release of remote input.',
    ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.evidence)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print('Verified all 48 release runs and 16 profile runs:', args.out)


if __name__ == '__main__':
    main()
