#!/usr/bin/env python3
"""Seahorse device variants of one built aquarium APK: the planted tank's authored
settings are cooked into the bundled selector cd.iff (plant_settings_catalog.configure_cd),
everything else (native libraries, wf_args.txt, resources) is kept byte for byte, and the
APK is aligned and signed with the local debug key, as build-aquarium-variant.py does.

Variants (docs/plans/2026-10-16-saltwater-seahorses.md, Phase 3 step 10 and Phase 4):
  none, pair1, pair2   saltwater with Seahorses = None / 1 pair / 2 pairs
  freshwater           freshwater (the seahorses and posts hidden)
Each is seed 713, plant age 150, growth paused, greeting on.

    scripts/build-planted-seahorse-variants.py --base-apk APK --out DIR [--variants none pair1 pair2 freshwater]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from plant_settings_catalog import configure_cd  # noqa: E402

VARIANTS = {
    'none': dict(water='saltwater', seahorses=0),
    'pair1': dict(water='saltwater', seahorses=1),
    'pair2': dict(water='saltwater', seahorses=2),
    'freshwater': dict(water='freshwater', seahorses=2),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-apk', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--variants', nargs='+', choices=sorted(VARIANTS), default=sorted(VARIANTS))
    ap.add_argument('--seed', type=int, default=713)
    ap.add_argument('--age', type=float, default=150)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    properties = ROOT / 'android/local.properties'
    configured = next((line.split('=', 1)[1] for line in properties.read_text().splitlines()
                       if line.startswith('sdk.dir=')), '') if properties.exists() else ''
    tools = Path(configured or os.environ.get('ANDROID_HOME', str(Path.home() / 'android-sdk-local'))) / 'build-tools/34.0.0'
    with zipfile.ZipFile(a.base_apk) as src:
        cd = src.read('assets/cd.iff')
    receipts = {}
    for name in a.variants:
        data, receipt = configure_cd(cd, dict(seed=a.seed, age=a.age, speed=0, greeting=True, **VARIANTS[name]))
        unsigned, aligned, final = (a.out / f'{name}-{k}.apk' for k in ('unsigned', 'aligned', 'signed'))
        with zipfile.ZipFile(a.base_apk) as src, zipfile.ZipFile(unsigned, 'w') as dst:
            for entry in src.infolist():
                if entry.filename.startswith('META-INF/') or entry.filename == 'assets/cd.iff':
                    continue
                dst.writestr(entry, src.read(entry.filename))
            dst.writestr('assets/cd.iff', data, compress_type=zipfile.ZIP_DEFLATED)
        subprocess.run([str(tools / 'zipalign'), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
        subprocess.run([str(tools / 'apksigner'), 'sign', '--ks', str(Path.home() / '.android/debug.keystore'),
                        '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', str(final), str(aligned)],
                       check=True)
        unsigned.unlink()
        aligned.unlink()
        apk = a.out / f'{name}.apk'
        final.rename(apk)
        receipt['apk_sha256'] = hashlib.sha256(apk.read_bytes()).hexdigest()
        receipts[name] = receipt
    receipt = dict(base_apk=str(a.base_apk.resolve()), base_apk_sha256=hashlib.sha256(a.base_apk.read_bytes()).hexdigest(),
                   revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   variants=receipts)
    (a.out / 'variants.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: v['apk_sha256'][:12] for k, v in receipts.items()}))


if __name__ == '__main__':
    main()
