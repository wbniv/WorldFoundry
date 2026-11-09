#!/usr/bin/env python3
"""Make the two S2 caustics fixture levels for the reef plan's step 14 cast1 gate.

Both are copies of the realistic reef (aquarium_thai_reef) that differ only in
the Camera's CausticStrength: reef_caustic_off (0) and reef_caustic_on (--strength,
default 0.25, the 2026-11-02 fixture value). Every other field, including the
ReefSettings defaults, is unchanged, so on/off isolates the S2 cost. Run in the
level-build container (WF_CONTAINER_IMAGE=blender) with --build; then package each
standalone level as a direct-launch APK with scripts/build-dfrm-e7-bench-apks.py.
"""
import argparse
import re
import subprocess
from pathlib import Path

from level_asset_links import link_source_assets

ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = 'aquarium_thai_reef'
SOURCE = ROOT / 'wflevels' / SOURCE_NAME
FIELD = re.compile(r"(\{ 'FX32' \{ 'NAME' \"CausticStrength\" \} \{ 'DATA' )[-\d.]+(\(1\.15\.16\) \} \{ 'STR' \")[^\"]*(\" \})")


def variant(name, strength, build):
    target = ROOT / 'wflevels' / name
    target.mkdir(exist_ok=True)
    link_source_assets(SOURCE, target)
    level, count = FIELD.subn(lambda m: f'{m[1]}{strength:.16f}{m[2]}{strength}{m[3]}',
                              (SOURCE / f'{SOURCE_NAME}.lev').read_text())
    if count != 1:
        raise ValueError(f'expected one CausticStrength field in the reef level, found {count}')
    (target / f'{name}.lev').write_text(level)
    wrapper = (SOURCE / f'{SOURCE_NAME}-standalone.iff.txt').read_text()
    (target / f'{name}-standalone.iff.txt').write_text(wrapper.replace(f'../{SOURCE_NAME}.iff', f'../{name}.iff'))
    if build:
        subprocess.run(['bash', 'wftools/wf_blender/build_level_binary.sh', name], cwd=ROOT, check=True)
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--strength', type=float, default=.25, help='CausticStrength of the "on" level')
    ap.add_argument('--build', action='store_true', help='also compile both levels with the Rust tools')
    args = ap.parse_args()
    for name, strength in (('reef_caustic_off', 0.0), ('reef_caustic_on', args.strength)):
        print(variant(name, strength, args.build))


if __name__ == '__main__':
    main()
