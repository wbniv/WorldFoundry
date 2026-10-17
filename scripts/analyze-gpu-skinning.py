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


def presentation(folder, mode, pairs, population_study=False):
    row = baseline.presentation(folder, require_plant_fixture=not population_study)
    summary = baseline.read_json(folder / 'summary.json')
    for name in ['refresh_ms', 'p50_ms', 'p99_ms', 'missed_refresh_percent']:
        row[name] = summary[name]
    if mode.startswith('gpu') and pairs:
        log = baseline.read_text(folder / 'wf.log')
        current = log[log.rfind('zforth: INDEXOF_CAMSHOT = 1921 (expect 1921)'):]
        if f'skinning: effective={mode} vertices=868 faces=1027 palette=40' not in current:
            raise ValueError(f'No actual GPU body draw: {folder}')
        if 'skinning: effective=cpu' in current:
            raise ValueError(f'GPU fallback occurred: {folder}')
    return row


def analyze(root, population_study=False, device='chromecast-test-01'):
    frozen = baseline.read_json(root / 'variants.json')['variants']
    campaign = baseline.read_json(root / 'campaign.json')
    jobs = baseline.read_json(root / 'jobs.json')
    views = ['population'] if population_study else ['close-idle', 'close-crawl']
    modes = ['cpu', 'cpu-no-cull', 'gpu-no-cull', 'gpu'] if population_study else ['cpu', 'gpu']
    counts = {'1': 1, '4': 4, '16': 16} if population_study else baseline.COUNTS
    verified = []
    for view in views:
        for mode in modes:
            for run in ['round-1', 'round-2', 'round-3', 'profile']:
                key = f'{view}/{mode}/{run}'
                folder = root / key
                receipt = baseline.read_json(folder / 'receipt.json')
                if (receipt['job'] != jobs[key] or receipt['status'] != 'succeeded'
                        or receipt['health'] != 'ready' or receipt['device'] != device
                        or receipt['survivors'] or any(not j['restored'] for j in receipt['journal'])):
                    raise ValueError(f'Incomplete coordinator session/cleanup: {key}')
                installs = baseline.read_json(folder / 'apk-installations.json')
                if len(installs) != len(counts) or {i['variant'] for i in installs} != set(counts):
                    raise ValueError(f'Unexpected populations: {key}')
                for item in installs:
                    fixture = f"{view}-{item['variant']}-{mode}" + ('-profile' if run == 'profile' else '')
                    if item['status'] != 'verified' or item['installed_sha256'] != frozen[fixture]['apk_sha256']:
                        raise ValueError(f'Fixture hash mismatch: {key}/{fixture}')
                restored = [j for j in receipt['journal'] if j['key'] == 'variant']
                if len(restored) != 1 or restored[0]['verification']['installed_sha256'] != campaign['restore_sha256']:
                    raise ValueError(f'Restore hash mismatch: {key}')
                verified.append(dict(source=str(folder / 'receipt.json'), job=jobs[key]))
    result = dict(device=device, population_study=population_study, verified_jobs=verified, views={}, gpu_time_ms=None,
                  gpu_time_note='No supported GPU timer evidence; presentation and thread CPU only.')
    for view in views:
        rows = []
        for count, pairs in counts.items():
            row = dict(actors=pairs) if population_study else dict(pairs=pairs)
            for mode in modes:
                runs = [presentation(root / view / mode / f'round-{r}' / count / 'run-1', mode, pairs, population_study) for r in [1, 2, 3]]
                folder = root / view / mode / 'profile' / count / 'run-1'
                instrumented = presentation(folder, mode, pairs, population_study)
                cpu = baseline.cpu_windows(folder, instrumented)
                sections, counters = cpu['frame_weighted_cpu_ms'], cpu['frame_weighted_counters']
                if not {'skin-pose', 'skin-vertices', 'skin-normals', 'skin-cull', 'skin-submit'} <= sections.keys():
                    raise ValueError(f'Missing rig CPU sections: {folder}')
                if mode.startswith('gpu'):
                    for key in ['skin-vertex-bytes', 'skin-index-bytes', 'skin-rebuilds', 'skin-fallbacks']:
                        if counters[key] != 0:
                            raise ValueError(f'Unexpected steady GPU {key}: {folder}')
                    if pairs and not (counters['skin-draws'] > 0 and counters['skin-palette-bytes'] > 0):
                        raise ValueError(f'No measured GPU work: {folder}')
                if mode.startswith('cpu') and pairs and counters['skin-vertex-bytes'] <= 0:
                    raise ValueError(f'Missing CPU rig stream upload accounting: {folder}')
                row[mode] = dict(release_runs=runs, cpu_profile=cpu, instrumented_presentation=instrumented,
                    median={k: statistics.median(r[k] for r in runs) for k in ['mean_frame_ms', 'fps', 'p50_ms', 'p95_ms', 'p99_ms', 'missed_refresh_percent', 'total_pss_kib']},
                    frame_ms_range=[min(r['mean_frame_ms'] for r in runs), max(r['mean_frame_ms'] for r in runs)])
            c, g = row['cpu'], row['gpu']
            row['render_cpu_change_percent'] = 100 * (g['cpu_profile']['frame_weighted_cpu_ms']['render'] / c['cpu_profile']['frame_weighted_cpu_ms']['render'] - 1)
            row['presented_frame_change_percent'] = 100 * (g['median']['mean_frame_ms'] / c['median']['mean_frame_ms'] - 1)
            if population_study:
                row['comparisons'] = {}
                for name, base, candidate in [('skinning_without_culling', 'cpu-no-cull', 'gpu-no-cull'),
                                               ('cpu_culling', 'cpu-no-cull', 'cpu'),
                                               ('gpu_culling', 'gpu-no-cull', 'gpu')]:
                    a, b = row[base], row[candidate]
                    row['comparisons'][name] = dict(baseline=base, candidate=candidate,
                        render_cpu_change_percent=100 * (b['cpu_profile']['frame_weighted_cpu_ms']['render'] / a['cpu_profile']['frame_weighted_cpu_ms']['render'] - 1),
                        presented_frame_change_percent=100 * (b['median']['mean_frame_ms'] / a['median']['mean_frame_ms'] - 1))
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
    if population_study:
        result['notes'] = result['notes'][:5] + [
            'Controlled 1/4/16 DFRM bodies: 868 vertices, 35 samples, 40 palette entries; no fins, plants or behavior AI.',
            'This measures the existing DFRM adapter, not general four-weight authoring performance.',
            'C/C0/G0/G1 separate skinning from culling; only G1 versus C is the adoption comparison.',
            'PSS is whole-process memory. Skin memory gauges are reported separately in the profile counters.',
        ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--population-study', action='store_true')
    parser.add_argument('--device', choices=['chromecast-test-01', 'chromecast-test-02'], default='chromecast-test-01')
    args = parser.parse_args()
    result = analyze(args.evidence, args.population_study, args.device)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print('Verified all ' + ('36 release runs and 12 profile runs' if args.population_study else '48 release runs and 16 profile runs') + ':', args.out)


if __name__ == '__main__':
    main()
