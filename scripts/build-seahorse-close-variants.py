#!/usr/bin/env python3
"""Build direct-launch close-view benchmark assets using one unchanged native APK.

The deployed coordinator supports idle/school, not the legacy plants trace.
These asset-only fixtures fix the existing close camera and optionally hold the
right bit inside the existing Forth input reader. They do not test input delivery.
Only two verified, complete source strings are changed, in their original slots.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import zipfile
from plant_settings_catalog import configure_level

ROOT = Path(__file__).resolve().parents[1]
CAMERA = 'tk-camera tk@ if tk-cam-close else tk-cam-wide then INDEXOF_CAMSHOT tk!'
HELD = ': tk-held INDEXOF_HARDWARE_JOYSTICK1_RAW tk@ & 0 <> if 1 else 0 then ;'
COUNTS = dict(none=0, pair1=1, pair2=2, pair6=6)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def scripts(text):
    result = {}
    for name in ('Player', 'Director'):
        block = text[text.index('{ \'NAME\' "' + name + '" }'):].split("{ 'OBJ'", 1)[0]
        encoded = re.search(r'\{ \'STR\' \{ \'NAME\' "Script" \} \{ \'STR\' ("(?:\\.|[^"\\])*")', block).group(1)
        result[name] = json.loads(encoded)
    return result


def patch_script(source, view):
    if view not in ('wide-idle', 'close-idle', 'close-crawl'):
        raise ValueError('Unknown benchmark view')
    if source.count(CAMERA) != 1 or source.count(HELD) != 1:
        raise ValueError('Controller source changed; review benchmark anchors')
    changed = source.replace(CAMERA, ('tk-cam-wide' if view == 'wide-idle' else 'tk-cam-close') + ' INDEXOF_CAMSHOT tk!')
    if view == 'close-crawl':
        changed = changed.replace(HELD, HELD.replace('tk@ &', 'tk@ 8192 | &'))
    return changed


def patch_level(level, sources, view):
    result = bytearray(level)
    slots = []
    for name, source in sources.items():
        original = source.encode()
        if level.count(original + b'\0') != 1:
            raise ValueError('Expected one complete NUL-terminated source slot: ' + name)
        start = level.index(original + b'\0')
        replacement = patch_script(source, view).encode()
        if len(replacement) > len(original):
            raise ValueError('Fixture outgrew its original source slot')
        replacement = replacement.ljust(len(original), b' ')
        result[start:start + len(original)] = replacement
        slots.append(dict(actor=name, offset=start, size=len(original),
                          original_sha256=sha(original), fixture_sha256=sha(replacement)))
    slots.sort(key=lambda slot: slot['offset'])
    if slots[0]['offset'] + slots[0]['size'] > slots[1]['offset']:
        raise ValueError('Overlapping or out-of-order source slots')
    restored = bytearray(result)
    for slot in slots:
        start, size = slot['offset'], slot['size']
        restored[start:start + size] = level[start:start + size]
    if bytes(restored) != level or len(result) != len(level):
        raise ValueError('Unexpected changes outside script slots')
    return bytes(result), slots


def verify_catalog_only(before, after):
    """The existing RPRP replacement may change only size/locator and catalog."""
    locator = 2056 + struct.unpack_from('<I', before, 2052)[0] - 12
    if before[locator:locator + 4] != b'RPRP' or after[locator:locator + 4] != b'RPRP':
        raise ValueError('Expected an existing RPRP catalog')
    start = 2048 + struct.unpack_from('<I', before, locator + 4)[0]
    if 2048 + struct.unpack_from('<I', after, locator + 4)[0] != start:
        raise ValueError('Catalog replacement moved asset data')
    restored = bytearray(after[:start])
    for offset, size in ((4, 4), (locator + 4, 8)):
        restored[offset:offset + size] = before[offset:offset + size]
    if bytes(restored) != before[:start]:
        raise ValueError('Property cooking changed bytes outside the catalog')
    return dict(asset_prefix_bytes=start, asset_prefix_sha256=sha(before[:start]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-apk', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tools = Path.home() / 'android-sdk-local/build-tools/34.0.0'
    source_level = (ROOT / 'wflevels/aquarium_plants-standalone.iff').read_bytes()
    sources = scripts((ROOT / 'wflevels/aquarium_plants/aquarium_plants.lev').read_text())
    with zipfile.ZipFile(args.base_apk) as base:
        native = {n: sha(base.read(n)) for n in base.namelist() if n.startswith('lib/') and n.endswith('.so')}
        original_args = base.read('assets/wf_args.txt') if 'assets/wf_args.txt' in base.namelist() else b''
    if b'--frame-profile' in original_args:
        raise ValueError('Expected a release base without frame profiling')
    receipt = dict(source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   base_apk_sha256=sha(args.base_apk.read_bytes()), native=native,
                   source_level_sha256=sha(source_level), variants={})
    for view in ('wide-idle', 'close-idle', 'close-crawl'):
        changed, slots = patch_level(source_level, sources, view)
        for label, count in COUNTS.items():
            level, settings = configure_level(changed, dict(seed=713, water='saltwater', age=150,
                speed=0, textures=True, sway=True, random_entry=False, seahorses=count, greeting=True))
            preservation = verify_catalog_only(changed, level)
            stem = f'{view}-{label}'
            standalone = args.out / (stem + '-standalone.iff')
            cd = args.out / (stem + '-cd.iff')
            standalone.write_bytes(level)
            subprocess.run([str(ROOT / 'wftools/cdpack-rs/target/release/cdpack'),
                str(ROOT / 'wfsource/source/game/shell.fth'), str(standalone.resolve()), '-o', str(cd.resolve())], check=True)
            for profiling in (False, True):
                name = stem + ('-cpu' if profiling else '')
                unsigned, aligned, final = (args.out / (name + suffix) for suffix in ('-unsigned.apk', '-aligned.apk', '.apk'))
                with zipfile.ZipFile(args.base_apk) as base, zipfile.ZipFile(unsigned, 'w') as out:
                    for entry in base.infolist():
                        if entry.filename.startswith('META-INF/') or entry.filename in ('assets/cd.iff', 'assets/wf_args.txt'):
                            continue
                        out.writestr(copy.copy(entry), base.read(entry.filename))
                    out.writestr('assets/cd.iff', cd.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
                    out.writestr('assets/wf_args.txt', original_args + (b'\n--frame-profile\n' if profiling else b''))
                subprocess.run([str(tools / 'zipalign'), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
                subprocess.run([str(tools / 'apksigner'), 'sign', '--ks', str(Path.home() / '.android/debug.keystore'),
                    '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', str(final), str(aligned)], check=True)
                unsigned.unlink(); aligned.unlink()
                with zipfile.ZipFile(args.base_apk) as base, zipfile.ZipFile(final) as out:
                    expected = {n for n in base.namelist() if not n.startswith('META-INF/')} | {'assets/wf_args.txt'}
                    actual = {n for n in out.namelist() if not n.startswith('META-INF/')}
                    assert actual == expected
                    for n in expected - {'assets/cd.iff', 'assets/wf_args.txt'}:
                        assert base.read(n) == out.read(n), n
                    assert {n: sha(out.read(n)) for n in native} == native
                receipt['variants'][name] = dict(apk_sha256=sha(final.read_bytes()), cd_sha256=sha(cd.read_bytes()),
                    level_sha256=sha(level), settings=settings, scripts=slots, preservation=preservation, frame_profile=profiling)
                print(name, receipt['variants'][name]['apk_sha256'], flush=True)
            standalone.unlink(); cd.unlink()
    (args.out / 'variants.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
