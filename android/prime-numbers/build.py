#!/usr/bin/env python3
"""Build a signed, immutable, offline Prime Numbers Android TV APK."""
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SDK = Path('/home/will/android-sdk-local')
TOOLS = SDK / 'build-tools/34.0.0'
ANDROID = SDK / 'platforms/android-34/android.jar'
COMPILER = Path('/tmp/patchwork-ecj.jar')
COMPILER_SHA = '01f5a92ac19bb2b3bf85e295a68f2c73c264369109158b566ce9b490af982948'


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def main():
    if not COMPILER.exists() or hashlib.sha256(COMPILER.read_bytes()).hexdigest() != COMPILER_SHA:
        raise SystemExit('Install the pinned ecj 3.39.0 compiler at /tmp/patchwork-ecj.jar; see Quilt Night tv/build.py.')
    run(sys.executable, ROOT / 'artwork.py')
    folder = ROOT / 'build'
    classes, dex = folder / 'classes', folder / 'dex'
    # Clear compiler/package inputs, preserving the signing key and previous frozen APKs.
    for target in (classes, dex, folder / 'assets'):
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
    shutil.copytree(ROOT / 'assets', folder / 'assets/primes')
    run('java', '-jar', COMPILER, '-1.8', '-proc:none', '-bootclasspath', ANDROID,
        '-d', classes, *sorted(ROOT.glob('src/**/*.java')))
    run(TOOLS / 'd8', '--min-api', '26', '--lib', ANDROID, '--output', dex, *sorted(classes.glob('**/*.class')))
    unsigned = folder / 'unsigned.apk'
    run(TOOLS / 'aapt', 'package', '-f', '-M', ROOT / 'AndroidManifest.xml', '-S', ROOT / 'res',
        '-I', ANDROID, '-A', folder / 'assets', '-F', unsigned)
    with zipfile.ZipFile(unsigned, 'a') as bundle:
        bundle.write(dex / 'classes.dex', 'classes.dex', compress_type=zipfile.ZIP_STORED)
    aligned = folder / 'aligned.apk'
    run(TOOLS / 'zipalign', '-f', '4', unsigned, aligned)
    key = folder / 'development-signing.p12'
    if not key.exists():
        run('keytool', '-genkeypair', '-keystore', key, '-storepass', 'android', '-keypass', 'android',
            '-alias', 'androiddebugkey', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650',
            '-dname', 'CN=World Foundry Prime Numbers Development')
    signed = folder / 'signed.apk'
    run(TOOLS / 'apksigner', 'sign', '--ks', key, '--ks-pass', 'pass:android', '--out', signed, aligned)
    run(TOOLS / 'apksigner', 'verify', '--verbose', signed)
    digest = hashlib.sha256(signed.read_bytes()).hexdigest()
    frozen = folder / ('primes-' + digest[:16] + '.apk')
    shutil.copyfile(signed, frozen)
    sources = {}
    for source in sorted(ROOT.rglob('*')):
        if source.is_file() and 'build' not in source.relative_to(ROOT).parts and '__pycache__' not in source.parts:
            sources[str(source.relative_to(ROOT))] = hashlib.sha256(source.read_bytes()).hexdigest()
    receipt = {'apk': str(frozen), 'sha256': digest, 'package': 'org.worldfoundry.wf_game.primes',
               'nativeCode': False, 'source': sources, 'compilerSha256': COMPILER_SHA}
    (folder / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
