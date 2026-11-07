"""Package scratch camera-only level variants for textured in-game review.

The generator output in /tmp/reef-leather-close/<style>-generated must already
exist. Production meshes and textures are copied unchanged; only the level
camera/player setup comes from the diagnostic .lev.
"""
import copy
import shutil
import subprocess
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
work = Path('/tmp/reef-leather-close')
build_tools = Path('/home/will/android-sdk-local/build-tools/34.0.0')
iff = root/'wftools/iffcomp-rs/target/release/iffcomp'
lev = root/'wftools/levcomp-rs/target/release/levcomp'
textile = root/'wftools/textile-rs/target/release/textile'
oad = root/'wfsource/source/oas'
apk = Path('/tmp/reef-leather-restored-full.apk')
for style, name in [('realistic', 'aquarium_thai_reef'), ('anime', 'aquarium_thai_reef_anime')]:
    parent = work/style
    parent.mkdir(exist_ok=True)
    level = parent/name
    shutil.copytree(root/'wflevels'/name, level, dirs_exist_ok=True)
    shutil.copyfile(work/(style+'-generated')/(name+'.lev'), level/(name+'.lev'))
    def run(args):
        subprocess.run([str(value) for value in args], cwd=level, check=True, stdout=subprocess.DEVNULL)
    run([iff, '-binary', '-o='+name+'.lev.bin', name+'.lev'])
    run([lev, name+'.lev.bin', oad/'objects.lc', name+'.lvl', oad,
         '--mesh-dir', '.', '--iff-txt', name+'.iff.txt', '--textile-ini', name+'.ini'])
    run([textile, '-ini='+name+'.ini', '-Tlinux', '-transparent=0,0,0', '-pagex=1024',
         '-pagey=1024', '-permpagex=1024', '-permpagey=1024', '-palx=256', '-paly=8',
         '-alignx=w', '-aligny=h', '-flipyout', '-powerof2size'])
    run([iff, '-binary', '-o=../'+name+'.iff', name+'.iff.txt'])
    run([iff, '-binary', '-o=../'+name+'-standalone.iff', name+'-standalone.iff.txt'])
    cd = parent/'cd.iff'
    run([root/'wftools/cdpack-rs/target/release/cdpack', root/'wfsource/source/game/shell.fth',
         parent/(name+'-standalone.iff'), '-o', cd])
    unsigned, aligned, final = parent/'unsigned.apk', parent/'aligned.apk', parent/'candidate.apk'
    with zipfile.ZipFile(apk) as src, zipfile.ZipFile(unsigned, 'w') as dst:
        for info in src.infolist():
            if not info.filename.startswith('META-INF/'):
                dst.writestr(copy.copy(info), cd.read_bytes() if info.filename == 'assets/cd.iff'
                             else src.read(info.filename))
    run([build_tools/'zipalign', '-f', '-p', '4', unsigned, aligned])
    run([build_tools/'apksigner', 'sign', '--ks', '/home/will/.android/debug.keystore',
         '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', final, aligned])
    run([build_tools/'apksigner', 'verify', final])
    print(style, final)
