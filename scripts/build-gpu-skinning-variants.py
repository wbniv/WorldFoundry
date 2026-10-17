#!/usr/bin/env python3
"""Freeze matched CPU/GPU fixtures from one native APK for the skinning experiment."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile
from plant_settings_catalog import configure_level

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('close_variants', ROOT / 'scripts/build-seahorse-close-variants.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-apk', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--populations', type=Path, help='Controlled population manifest instead of aquarium views')
    parser.add_argument('--views', nargs='+', choices=['wide-idle', 'close-idle', 'close-crawl'],
                        default=['wide-idle', 'close-idle', 'close-crawl'])
    parser.add_argument('--modes', nargs='+', choices=['cpu', 'cpu-no-cull', 'gpu-no-cull', 'gpu'], default=['cpu', 'gpu'])
    parser.add_argument('--counts', nargs='+', choices=list(fixture.COUNTS), default=list(fixture.COUNTS))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tools = Path.home() / 'android-sdk-local/build-tools/34.0.0'
    sha = fixture.sha
    source_level = (ROOT / 'wflevels/aquarium_plants-standalone.iff').read_bytes()
    sources = fixture.scripts((ROOT / 'wflevels/aquarium_plants/aquarium_plants.lev').read_text())
    with zipfile.ZipFile(args.base_apk) as base:
        native = {n: sha(base.read(n)) for n in base.namelist() if n.startswith('lib/') and n.endswith('.so')}
        original_args = base.read('assets/wf_args.txt') if 'assets/wf_args.txt' in base.namelist() else b''
        if not native or not any(b'gpu-no-cull' in base.read(n) for n in native):
            raise ValueError('Base APK lacks the experimental native modes')
    if b'--frame-profile' in original_args or b'--gpu-skinning' in original_args:
        raise ValueError('Base arguments must not select profiling or skinning')
    receipt = dict(source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   source_diff_sha256=sha(subprocess.check_output(['git', 'diff', 'HEAD', '--'], cwd=ROOT)),
                   base_apk_sha256=sha(args.base_apk.read_bytes()), native=native,
                   source_level_sha256=sha(source_level), variants={})
    cases = []
    if args.populations:
        populations = json.loads(args.populations.read_text())
        receipt['population_manifest_sha256'] = sha(args.populations.read_bytes())
        for count, item in populations['populations'].items():
            level = Path(item['standalone']).read_bytes()
            if sha(level) != item['standalone_sha256']:
                raise ValueError('Population level hash mismatch: ' + count)
            cases.append((f'population-{count}', level, dict(actors=int(count), scope=populations['scope']), [], {}))
    else:
        for view in args.views:
            changed, slots = fixture.patch_level(source_level, sources, view)
            for label in args.counts:
                level, settings = configure_level(changed, dict(seed=713, water='saltwater', age=150,
                    speed=0, textures=True, sway=True, random_entry=False,
                    seahorses=fixture.COUNTS[label], greeting=True))
                preservation = fixture.verify_catalog_only(changed, level)
                cases.append((f'{view}-{label}', level, settings, slots, preservation))
    for stem, level, settings, slots, preservation in cases:
        standalone = args.out / (stem + '-standalone.iff')
        cd = args.out / (stem + '-cd.iff')
        standalone.write_bytes(level)
        subprocess.run([str(ROOT / 'wftools/cdpack-rs/target/release/cdpack'),
            str(ROOT / 'wfsource/source/game/shell.fth'), str(standalone.resolve()), '-o', str(cd.resolve())], check=True)
        for mode in args.modes:
            for profiling in (False, True):
                name = f'{stem}-{mode}' + ('-profile' if profiling else '')
                unsigned, aligned, final = (args.out / (name + suffix) for suffix in ('-unsigned.apk', '-aligned.apk', '.apk'))
                runtime_args = original_args + f'\n--gpu-skinning={mode}\n'.encode() + (b'--frame-profile\n' if profiling else b'')
                with zipfile.ZipFile(args.base_apk) as base, zipfile.ZipFile(unsigned, 'w') as out:
                    for entry in base.infolist():
                        if entry.filename.startswith('META-INF/') or entry.filename in ('assets/cd.iff', 'assets/wf_args.txt'):
                            continue
                        out.writestr(copy.copy(entry), base.read(entry.filename))
                    out.writestr('assets/cd.iff', cd.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
                    out.writestr('assets/wf_args.txt', runtime_args)
                subprocess.run([str(tools / 'zipalign'), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
                subprocess.run([str(tools / 'apksigner'), 'sign', '--ks', str(Path.home() / '.android/debug.keystore'),
                    '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', str(final), str(aligned)], check=True)
                unsigned.unlink(); aligned.unlink()
                with zipfile.ZipFile(args.base_apk) as base, zipfile.ZipFile(final) as out:
                    expected = {n for n in base.namelist() if not n.startswith('META-INF/')} | {'assets/wf_args.txt'}
                    if {n for n in out.namelist() if not n.startswith('META-INF/')} != expected:
                        raise ValueError('APK entries changed')
                    for n in expected - {'assets/cd.iff', 'assets/wf_args.txt'}:
                        if base.read(n) != out.read(n):
                            raise ValueError('Unexpected APK mutation: ' + n)
                    if out.read('assets/wf_args.txt') != runtime_args:
                        raise ValueError('Runtime mode mismatch')
                receipt['variants'][name] = dict(apk_sha256=sha(final.read_bytes()), cd_sha256=sha(cd.read_bytes()),
                    level_sha256=sha(level), mode=mode, settings=settings, scripts=slots,
                    preservation=preservation, frame_profile=profiling)
                print(name, receipt['variants'][name]['apk_sha256'], flush=True)
        cd.unlink()
    (args.out / 'variants.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
