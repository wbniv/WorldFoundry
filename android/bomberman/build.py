#!/usr/bin/env python3
"""Build an offline Bomberman TV APK from the frozen assets with the installed SDK."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

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
        raise SystemExit('Install the pinned ecj 3.39.0 compiler at /tmp/patchwork-ecj.jar first; see Quilt Night tv/build.py.')
    folder = ROOT / 'build'
    classes, dex = folder / 'classes', folder / 'dex'
    classes.mkdir(parents=True, exist_ok=True); dex.mkdir(exist_ok=True)
    assets = folder / 'assets/bomberman'
    shutil.copytree(ROOT / 'assets', assets, dirs_exist_ok=True)
    for filename in ('tv.css', 'tv-controls.js'):
        shutil.copy2(ROOT / filename, assets / filename)
    html = (assets / 'solo-game.html').read_text()
    html = html.replace('</head>', '<link rel="stylesheet" href="tv.css"></head>')
    html = html.replace('</body>', '<script src="tv-controls.js"></script></body>')
    (assets / 'solo-game.html').write_text(html)
    run('java', '-jar', COMPILER, '-1.8', '-proc:none', '-bootclasspath', ANDROID, '-d', classes, *ROOT.glob('src/**/*.java'))
    run(TOOLS / 'd8', '--min-api', '26', '--lib', ANDROID, '--output', dex, *classes.glob('**/*.class'))
    unsigned = folder / 'unsigned.apk'
    run(TOOLS / 'aapt', 'package', '-f', '-M', ROOT / 'AndroidManifest.xml', '-S', ROOT / 'res', '-I', ANDROID, '-A', folder / 'assets', '-F', unsigned)
    with zipfile.ZipFile(unsigned, 'a') as bundle:
        bundle.write(dex / 'classes.dex', 'classes.dex', compress_type=zipfile.ZIP_STORED)
    aligned = folder / 'aligned.apk'
    run(TOOLS / 'zipalign', '-f', '4', unsigned, aligned)
    key = folder / 'development-signing.p12'
    if not key.exists():
        run('keytool', '-genkeypair', '-keystore', key, '-storepass', 'android', '-keypass', 'android', '-alias', 'androiddebugkey', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650', '-dname', 'CN=World Foundry Bomberman Development')
    signed = folder / 'signed.apk'
    run(TOOLS / 'apksigner', 'sign', '--ks', key, '--ks-pass', 'pass:android', '--out', signed, aligned)
    run(TOOLS / 'apksigner', 'verify', '--verbose', signed)
    digest = hashlib.sha256(signed.read_bytes()).hexdigest()
    frozen = folder / f'bomberman-{digest[:16]}.apk'
    shutil.copyfile(signed, frozen)
    receipt = {'apk': str(frozen), 'sha256': digest, 'package': 'org.worldfoundry.wf_game.bomberman', 'nativeCode': False,
               'source': json.loads((ROOT / 'source-checksums.json').read_text()), 'compilerSha256': COMPILER_SHA}
    (folder / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
