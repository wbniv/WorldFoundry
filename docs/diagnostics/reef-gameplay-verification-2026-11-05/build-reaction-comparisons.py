import copy
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

root = Path('/home/will/WorldFoundry-wbniv')
source = root/'wflevels/aquarium_thai_reef'
work = Path('/tmp/reef-reactions-verification')
work.mkdir(exist_ok=True)
iff = root/'wftools/iffcomp-rs/target/release/iffcomp'
lev = root/'wftools/levcomp-rs/target/release/levcomp'
textile = root/'wftools/textile-rs/target/release/textile'
oad = root/'wfsource/source/oas'
build = Path('/home/will/android-sdk-local/build-tools/34.0.0')
variants = []
for label in ('clam-near', 'clam-far', 'crab-near', 'crab-far', 'shrimp-near', 'shrimp-far'):
    parent = work/label
    parent.mkdir(exist_ok=True)
    level = parent/'aquarium_thai_reef'
    shutil.copytree(source, level, dirs_exist_ok=True)
    shutil.copyfile(Path('/tmp/reef-'+label)/'aquarium_thai_reef.lev', level/'aquarium_thai_reef.lev')
    def run(args):
        subprocess.run([str(x) for x in args], cwd=level, check=True, stdout=subprocess.DEVNULL)
    run([iff, '-binary', '-o=aquarium_thai_reef.lev.bin', 'aquarium_thai_reef.lev'])
    run([lev, 'aquarium_thai_reef.lev.bin', oad/'objects.lc', 'aquarium_thai_reef.lvl', oad,
         '--mesh-dir', '.', '--iff-txt', 'aquarium_thai_reef.iff.txt', '--textile-ini', 'aquarium_thai_reef.ini'])
    run([textile, '-ini=aquarium_thai_reef.ini', '-Tlinux', '-transparent=0,0,0', '-pagex=1024', '-pagey=1024',
         '-permpagex=1024', '-permpagey=1024', '-palx=256', '-paly=8', '-alignx=w', '-aligny=h', '-flipyout', '-powerof2size'])
    run([iff, '-binary', '-o=../aquarium_thai_reef.iff', 'aquarium_thai_reef.iff.txt'])
    run([iff, '-binary', '-o=../aquarium_thai_reef-standalone.iff', 'aquarium_thai_reef-standalone.iff.txt'])
    cd = parent/'cd.iff'
    run([root/'wftools/cdpack-rs/target/release/cdpack', root/'wfsource/source/game/shell.fth',
         parent/'aquarium_thai_reef-standalone.iff', '-o', cd])
    unsigned, aligned, apk = parent/'unsigned.apk', parent/'aligned.apk', parent/'candidate.apk'
    with zipfile.ZipFile('/tmp/reef-flora-2026-11-05.apk') as src, zipfile.ZipFile(unsigned, 'w') as dst:
        for info in src.infolist():
            if not info.filename.startswith('META-INF/'):
                dst.writestr(copy.copy(info), cd.read_bytes() if info.filename == 'assets/cd.iff' else src.read(info))
    run([build/'zipalign', '-f', '-p', '4', unsigned, aligned])
    run([build/'apksigner', 'sign', '--ks', '/home/will/.android/debug.keystore', '--ks-pass', 'pass:android',
         '--key-pass', 'pass:android', '--out', apk, aligned])
    variants.append({'label': label, 'apk': str(apk)})
recipe = {'workflow': 'variant-benchmark', 'app': 'aquarium', 'trace': 'idle', 'duration': 10,
          'warmup': 5, 'runs': 1, 'panel': 'require-hidden',
          'restore_apk': '/tmp/reef-flora-2026-11-05.apk', 'variants': variants}
(work/'recipe.json').write_text(json.dumps(recipe))
print(work/'recipe.json')
