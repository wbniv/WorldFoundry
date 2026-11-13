#!/usr/bin/env python3
"""Make audited direct-launch E7 benchmark APKs from one frozen base APK.

For each matched level, write a normal presentation APK and a separately
instrumented APK with --frame-profile. Only cd.iff and wf_args.txt differ
from the base outside the APK signatures. Run inside the build container.
"""
import argparse
import copy
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for arg in ('base-apk', 'single-level', 'merged-level', 'cdpack', 'shell', 'zipalign', 'apksigner', 'keystore', 'out'):
        ap.add_argument('--' + arg, type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.base_apk) as src:
        original = {entry.filename: src.read(entry.filename) for entry in src.infolist()
                    if not entry.filename.startswith('META-INF/')}
        descriptors = {entry.filename: copy.copy(entry) for entry in src.infolist()}
    base_args = original['assets/wf_args.txt']
    if b'--frame-profile' in base_args:
        raise ValueError('base APK already enables frame profiling')
    result = {'base_sha256': sha(args.base_apk.read_bytes()), 'variants': {}}
    with tempfile.TemporaryDirectory(prefix='dfrm-e7-') as temp:
        temp = Path(temp)
        for name, level in (('single', args.single_level), ('merged', args.merged_level)):
            cd = temp / (name + '.iff')
            subprocess.run([str(args.cdpack), str(args.shell), str(level), '-o', str(cd)], check=True)
            cd_bytes = cd.read_bytes()
            for profiling in (False, True):
                label = name + ('-cpu' if profiling else '-plain')
                unsigned, aligned = temp / 'unsigned.apk', temp / 'aligned.apk'
                with zipfile.ZipFile(unsigned, 'w') as dst:
                    for entry, data in original.items():
                        if entry == 'assets/cd.iff':
                            data = cd_bytes
                        elif entry == 'assets/wf_args.txt':
                            data = base_args + (b'\n--frame-profile\n' if profiling else b'')
                        dst.writestr(descriptors[entry], data)
                subprocess.run([str(args.zipalign), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
                apk = args.out / (label + '.apk')
                subprocess.run([str(args.apksigner), 'sign', '--ks', str(args.keystore), '--ks-pass', 'pass:android',
                                '--key-pass', 'pass:android', '--out', str(apk), str(aligned)], check=True)
                with zipfile.ZipFile(apk) as check:
                    actual = {name: check.read(name) for name in check.namelist() if not name.startswith('META-INF/')}
                if set(actual) != set(original) or any(actual[n] != original[n] for n in original
                                                        if n not in ('assets/cd.iff', 'assets/wf_args.txt')):
                    raise ValueError(f'{label}: unexpected non-asset change')
                if actual['assets/cd.iff'] != cd_bytes:
                    raise ValueError(f'{label}: incorrect CD payload')
                expected_args = base_args + (b'\n--frame-profile\n' if profiling else b'')
                if actual['assets/wf_args.txt'] != expected_args:
                    raise ValueError(f'{label}: incorrect profiler flag')
                result['variants'][label] = {'apk_sha256': sha(apk.read_bytes()), 'cd_sha256': sha(cd_bytes),
                                              'level_sha256': sha(level.read_bytes()), 'frame_profile': profiling}
    (args.out / 'variants.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
