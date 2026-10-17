#!/usr/bin/env python3
"""Freeze matched CPU/GPU fixtures from one native APK for the skinning experiment."""
import argparse
import copy
import importlib.util
import json
import re
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
    parser.add_argument('--selector', action='store_true', help='Keep the base selector CD for input and lifecycle checks')
    parser.add_argument('--profile-only', action='store_true', help='Freeze corrected instrumented cases without replacing release timing APKs')
    parser.add_argument('--views', nargs='+', choices=['wide-idle', 'close-idle', 'close-crawl'],
                        default=['wide-idle', 'close-idle', 'close-crawl'])
    parser.add_argument('--modes', nargs='+', choices=['cpu', 'cpu-no-cull', 'gpu-no-cull', 'gpu'], default=['cpu', 'gpu'])
    parser.add_argument('--counts', nargs='+', choices=list(fixture.COUNTS), default=list(fixture.COUNTS))
    args = parser.parse_args()
    if args.selector and args.populations:
        parser.error('--selector and --populations are mutually exclusive')
    args.out.mkdir(parents=True, exist_ok=True)
    tools = Path.home() / 'android-sdk-local/build-tools/34.0.0'
    manifest = subprocess.check_output([str(tools / 'aapt'), 'dump', 'xmltree',
        str(args.base_apk), 'AndroidManifest.xml'], text=True)
    test_only = re.search(r'android:testOnly[^\n]*=\(type 0x12\)(0x[0-9a-fA-F]+)', manifest)
    if test_only and int(test_only[1], 16):
        raise ValueError('Base APK is testOnly; rebuild with -Pandroid.injected.testOnly=false')
    sha = fixture.sha
    source_level = (ROOT / 'wflevels/aquarium_plants-standalone.iff').read_bytes()
    sources = fixture.scripts((ROOT / 'wflevels/aquarium_plants/aquarium_plants.lev').read_text())
    with zipfile.ZipFile(args.base_apk) as base:
        native = {n: sha(base.read(n)) for n in base.namelist() if n.startswith('lib/') and n.endswith('.so')}
        original_args = base.read('assets/wf_args.txt') if 'assets/wf_args.txt' in base.namelist() else b''
        original_cd = base.read('assets/cd.iff')
        if not native or not any(b'gpu-no-cull' in base.read(n) for n in native):
            raise ValueError('Base APK lacks the experimental native modes')
        if not any(b'frame-profile-schema: v2 flushed-final-batch no-per-face-clocks' in base.read(n) for n in native):
            raise ValueError('Base APK lacks corrected v2 profiling; rebuild before freezing profiles')
    if b'--frame-profile' in original_args or b'--gpu-skinning' in original_args:
        raise ValueError('Base arguments must not select profiling or skinning')
    receipt = dict(source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   source_diff_sha256=sha(subprocess.check_output(['git', 'diff', 'HEAD', '--'], cwd=ROOT)),
                   base_apk_sha256=sha(args.base_apk.read_bytes()), native=native,
                   source_level_sha256=sha(source_level), profile_scope_version=2, variants={})
    cases = []
    if args.selector:
        cases.append(('selector', None, dict(scope='Unmodified base selector assets; input and lifecycle checks only'), [], {}))
    elif args.populations:
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
        if level is not None:
            standalone.write_bytes(level)
            subprocess.run([str(ROOT / 'wftools/cdpack-rs/target/release/cdpack'),
                str(ROOT / 'wfsource/source/game/shell.fth'), str(standalone.resolve()), '-o', str(cd.resolve())], check=True)
        cd_bytes = cd.read_bytes() if level is not None else original_cd
        for mode in args.modes:
            for profiling in ((True,) if args.profile_only else (False, True)):
                name = f'{stem}-{mode}' + ('-profile' if profiling else '')
                unsigned, aligned, final = (args.out / (name + suffix) for suffix in ('-unsigned.apk', '-aligned.apk', '.apk'))
                runtime_args = original_args + f'\n--gpu-skinning={mode}\n'.encode() + (b'--frame-profile\n' if profiling else b'')
                with zipfile.ZipFile(args.base_apk) as base, zipfile.ZipFile(unsigned, 'w') as out:
                    for entry in base.infolist():
                        if entry.filename.startswith('META-INF/') or entry.filename in ('assets/cd.iff', 'assets/wf_args.txt'):
                            continue
                        out.writestr(copy.copy(entry), base.read(entry.filename))
                    out.writestr('assets/cd.iff', cd_bytes, compress_type=zipfile.ZIP_DEFLATED)
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
                    if out.read('assets/cd.iff') != cd_bytes:
                        raise ValueError('Packaged CD mismatch')
                receipt['variants'][name] = dict(apk_sha256=sha(final.read_bytes()), cd_sha256=sha(cd_bytes),
                    level_sha256=sha(level) if level is not None else None, mode=mode, settings=settings, scripts=slots,
                    preservation=preservation, frame_profile=profiling)
                receipt['variants'][name].update(native=native, profile_scope_version=2 if profiling else None)
                print(name, receipt['variants'][name]['apk_sha256'], flush=True)
        if level is not None:
            cd.unlink()
    (args.out / 'variants.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
