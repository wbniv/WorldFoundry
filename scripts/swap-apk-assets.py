#!/usr/bin/env python3
"""Replace assets in a built APK and re-sign it, keeping every other entry byte for byte.

Used to hold level data fixed while only the engine varies (for example the
seahorse-grid regression bisect, docs/diagnostics/seahorse-grid-regression-2026-11-10):
take the native libraries and Java side of --apk and put --cd-iff and, optionally,
--wf-args from a reference APK into it.

    scripts/swap-apk-assets.py --apk ENGINE.apk --from REFERENCE.apk --out OUT.apk [--assets assets/cd.iff assets/wf_args.txt]
    scripts/swap-apk-assets.py --apk BASE.apk --file assets/cd.iff=bundle.iff [--file assets/wf_args.txt=args.txt ...] --out OUT.apk

--file takes an entry's new bytes from a local file instead (the candle flicker benchmark's variants: one base APK, a one-level
bundle and a wf_args.txt with --frame-profile each; docs/plans/2026-11-22-cuckoo-village-candle-flicker.md).
"""
import argparse
import copy
import hashlib
import subprocess
import tempfile
import zipfile
from pathlib import Path

TOOLS = Path.home() / 'android-sdk-local/build-tools/34.0.0'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apk', type=Path, required=True, help='APK whose code and libraries are kept')
    ap.add_argument('--from', dest='source', type=Path, help='APK the assets come from')
    ap.add_argument('--file', action='append', default=[], metavar='ENTRY=PATH', help='replace ENTRY with the bytes of the local file PATH')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--assets', nargs='+', default=['assets/cd.iff', 'assets/wf_args.txt'])
    args = ap.parse_args()
    if not args.source and not args.file:
        ap.error('give --from or at least one --file')
    replace = {}
    if args.source:
        with zipfile.ZipFile(args.source) as src:
            replace = {name: src.read(name) for name in args.assets}
    for item in args.file:
        name, sep, path = item.partition('=')
        if not sep or not name or not path:
            ap.error(f'--file wants ENTRY=PATH, not {item!r}')
        replace[name] = Path(path).read_bytes()
    with tempfile.TemporaryDirectory() as temp:
        unsigned, aligned = Path(temp) / 'u.apk', Path(temp) / 'a.apk'
        with zipfile.ZipFile(args.apk) as base, zipfile.ZipFile(unsigned, 'w') as out:
            for entry in base.infolist():
                if entry.filename.startswith('META-INF/'):
                    continue
                data = replace.pop(entry.filename, None)
                out.writestr(copy.copy(entry), base.read(entry.filename) if data is None else data)
            for name, data in replace.items():
                out.writestr(zipfile.ZipInfo(name), data, compress_type=zipfile.ZIP_STORED)
        subprocess.run([str(TOOLS / 'zipalign'), '-f', '-p', '4', str(unsigned), str(aligned)], check=True)
        subprocess.run([str(TOOLS / 'apksigner'), 'sign', '--ks', str(Path.home() / '.android/debug.keystore'),
                        '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', str(args.out),
                        str(aligned)], check=True)
    print(args.out, hashlib.sha256(args.out.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
