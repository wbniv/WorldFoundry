#!/usr/bin/env python3
"""R0: repack the Aquarium release APK with each probe's cd.iff (same libs, same wf_args.txt), sign with the
debug keystore like scripts/wf_device/prepare_variants.py. Usage: python3 build-docker/r0/repack.py"""
import shutil, subprocess, sys, zipfile
from pathlib import Path
if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'): print(__doc__); raise SystemExit(0)
ROOT = Path(__file__).resolve().parents[2]; R0 = Path(__file__).resolve().parent
sdk = Path.home()/'android-sdk-local/build-tools/34.0.0'
base = R0/'base-release.apk'
if not base.exists(): shutil.copyfile(ROOT/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk', base)
pixel = len(sys.argv) > 1 and sys.argv[1] == 'pixel'   # `repack.py pixel`: the row-0 Pixel bundles
names = [f'pixel-{p}-{s}' for p in ('P0', 'P1', 'P2', 'P3') for s in ('aquarium_thai_reef', 'aquarium_thai_reef_anime')] if pixel else ['P0', 'P1', 'P2', 'P3']
for probe in names:
    cd = (R0/f'{probe}-cd.iff').read_bytes()
    unsigned, aligned, target = R0/f'{probe}-unsigned.apk', R0/f'{probe}-aligned.apk', R0/f'r0-{probe}.apk'
    with zipfile.ZipFile(base) as src, zipfile.ZipFile(unsigned, 'w') as dst:
        for info in src.infolist():
            if info.filename.startswith('META-INF/') and (info.filename.endswith(('.SF', '.RSA', '.DSA', '.EC')) or info.filename == 'META-INF/MANIFEST.MF'):
                continue
            dst.writestr(info, cd if info.filename == 'assets/cd.iff' else src.read(info.filename))
    subprocess.run([str(sdk/'zipalign'), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
    subprocess.run([str(sdk/'apksigner'), 'sign', '--ks', str(Path.home()/'.android/debug.keystore'), '--ks-key-alias', 'androiddebugkey',
                    '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', str(target), str(aligned)], check=True)
    subprocess.run([str(sdk/'apksigner'), 'verify', str(target)], check=True)
    unsigned.unlink(); aligned.unlink()
    print(probe, target, target.stat().st_size)
