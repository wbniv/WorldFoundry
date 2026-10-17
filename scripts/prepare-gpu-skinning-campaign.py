#!/usr/bin/env python3
"""Verify frozen fixtures and write the 48 release / 16 CPU-profile run recipes.

Submission is a separate coordinator action; this script never controls devices.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--restore-apk', type=Path, required=True)
    parser.add_argument('--restore-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--population-study', action='store_true', help='1/4/16 rigs, C/C0/G0/G1, 30 s warmup')
    args = parser.parse_args()
    if sha(args.restore_apk) != args.restore_sha256:
        raise ValueError('Restore APK hash mismatch')
    fixtures = args.fixtures.resolve()
    receipt = json.loads((fixtures / 'variants.json').read_text())
    for name, item in receipt['variants'].items():
        if sha(fixtures / (name + '.apk')) != item['apk_sha256']:
            raise ValueError('Fixture hash mismatch: ' + name)
    args.out.mkdir(parents=True, exist_ok=True)
    restore = args.out.resolve() / 'restore.apk'
    shutil.copyfile(args.restore_apk, restore)
    manifest = dict(fixtures_manifest_sha256=sha(fixtures / 'variants.json'),
                    restore_sha256=sha(restore), recipes=[], release_runs=0, profile_runs=0)
    counts = ['1', '4', '16'] if args.population_study else ['none', 'pair1', 'pair2', 'pair6']
    def recipe(view, mode, order, suffix, profile=False):
        name = f'{view}-{mode}-{suffix}'
        variants = []
        for count in order:
            key = f'{view}-{count}-{mode}' + ('-profile' if profile else '')
            if key not in receipt['variants']:
                raise ValueError('Missing fixture: ' + key)
            variants.append(dict(label=count, apk=str(fixtures / (key + '.apk'))))
        data = dict(workflow='variant-benchmark', app='aquarium', apk=str(restore),
                    restore_apk=str(restore), trace='idle', duration=60, warmup=30 if args.population_study else 15,
                    runs=1, variants=variants)
        path = args.out / (name + '.json')
        path.write_text(json.dumps(data, indent=2) + '\n')
        manifest['recipes'].append(dict(name=name, path=str(path.resolve()),
            sha256=sha(path), view=view, mode=mode, frame_profile=profile, order=order))
        manifest['profile_runs' if profile else 'release_runs'] += len(order)
    if args.population_study:
        modes = ['cpu', 'cpu-no-cull', 'gpu-no-cull', 'gpu']
        for repeat in range(3):
            order = counts[repeat:] + counts[:repeat]
            for mode in modes[repeat:] + modes[:repeat]:
                recipe('population', mode, order, f'round-{repeat+1}')
        for mode in reversed(modes):
            recipe('population', mode, list(reversed(counts)), 'profile', True)
    else:
        # Alternate paths; rotate populations identically within each round.
        for repeat in range(3):
            order = counts[repeat:] + counts[:repeat]
            modes = ['cpu', 'gpu'] if repeat % 2 == 0 else ['gpu', 'cpu']
            for view in ['close-idle', 'close-crawl']:
                for mode in modes:
                    recipe(view, mode, order, f'round-{repeat+1}')
        for view in ['close-idle', 'close-crawl']:
            for mode in ['gpu', 'cpu']:
                recipe(view, mode, list(reversed(counts)), 'profile', True)
    (args.out / 'campaign.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f"Prepared {manifest['release_runs']} release and {manifest['profile_runs']} profile runs: {args.out}")


if __name__ == '__main__':
    main()
