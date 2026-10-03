#!/usr/bin/env python3
"""Rebuild and archive a named aquarium variant for reproducible device comparisons."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--asset', choices=['clownfish','barb_quad','barb_mesh','barb_refined'], required=True)
ap.add_argument('--count', type=int, required=True)
ap.add_argument('--updates', type=int, default=5)
ap.add_argument('--static', action='store_true')
ap.add_argument('--frozen', action='store_true')
ap.add_argument('--profile', action='store_true')
ap.add_argument('--name', required=True)
ap.add_argument('--out', default='/tmp/aquarium-barb-baselines')
ap.add_argument('--base-apk', type=Path, help='Reuse the exact native libraries and app resources; replace only cd.iff and profiling args, then align/sign with the local debug key')
a=ap.parse_args()
ROOT=Path(__file__).resolve().parents[1]
env=dict(os.environ,AQUARIUM_FOLLOWER_ASSET=a.asset,AQUARIUM_SCHOOL_N=str(a.count),
         AQUARIUM_BARB_UPDATES=str(a.updates),AQUARIUM_BARB_ANIMATE='0' if a.static else '1',
         AQUARIUM_BARB_FROZEN='1' if a.frozen else '0')
if a.base_apk:
    # Existing host tools suffice for asset-only experiments. Their outputs are
    # confined to this checkout; no shared Cargo/Gradle build cache is mutated.
    subprocess.run(['blender','--background','--python-exit-code','1','--python',
                    'wflevels/aquarium/blender_create_aquarium.py'],cwd=ROOT,env=env,check=True)
    subprocess.run(['bash','wftools/wf_blender/build_level_binary.sh','aquarium'],cwd=ROOT,check=True)
    subprocess.run(['wftools/cdpack-rs/target/release/cdpack','wfsource/source/game/shell.fth',
                    'wflevels/aquarium-standalone.iff','-o','wflevels/aquarium-cd.iff'],cwd=ROOT,check=True)
else:
    subprocess.run(['task','--force','aquarium-level'],cwd=ROOT,env=env,check=True)
out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
if a.base_apk:
    import hashlib
    properties=ROOT/'android/local.properties'
    configured=next((line.split('=',1)[1] for line in properties.read_text().splitlines()
                     if line.startswith('sdk.dir=')), '') if properties.exists() else ''
    sdk=Path(configured or os.environ.get('ANDROID_HOME',str(Path.home()/'android-sdk-local')))
    build_tools=sdk/'build-tools/34.0.0'
    unsigned=out/(a.name+'-unsigned.apk'); aligned=out/(a.name+'-aligned.apk')
    with zipfile.ZipFile(a.base_apk) as src, zipfile.ZipFile(unsigned,'w') as dst:
        for entry in src.infolist():
            if entry.filename.startswith('META-INF/') or entry.filename in ('assets/cd.iff','assets/wf_args.txt'):
                continue
            dst.writestr(entry,src.read(entry.filename))
        dst.write(ROOT/'wflevels/aquarium-cd.iff','assets/cd.iff',compress_type=zipfile.ZIP_DEFLATED)
        if a.profile: dst.writestr('assets/wf_args.txt','--frame-profile\n')
    subprocess.run([str(build_tools/'zipalign'),'-f','-p','4',str(unsigned),str(aligned)],check=True)
    subprocess.run([str(build_tools/'apksigner'),'sign','--ks',str(Path.home()/'.android/debug.keystore'),
                    '--ks-pass','pass:android','--key-pass','pass:android','--out',str(out/(a.name+'.apk')),str(aligned)],check=True)
    unsigned.unlink(); aligned.unlink()
    receipt=vars(a).copy()
    receipt['base_apk']=str(a.base_apk.resolve())
    receipt['base_apk_sha256']=hashlib.sha256(a.base_apk.read_bytes()).hexdigest()
    receipt['revision']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    receipt['source_diff_sha256']=hashlib.sha256(subprocess.check_output(['git','diff'],cwd=ROOT)).hexdigest()
    for source,suffix in [('wflevels/aquarium/aquarium.lev','.lev'),('wflevels/aquarium-cd.iff','-cd.iff'),('wflevels/aquarium-standalone.iff','-standalone.iff')]:
        shutil.copyfile(ROOT/source,out/(a.name+suffix))
    (out/(a.name+'.json')).write_text(json.dumps(receipt,indent=2,default=str))
    print(f'Archived {a.name}',flush=True)
    raise SystemExit(0)
argsfile=ROOT/'android/app/src/aquarium/assets/wf_args.txt'
if a.profile: argsfile.write_text('--frame-profile\n')
else: argsfile.unlink(missing_ok=True)
# Benchmarks launch the selected tank directly, even after the app adopts its selector.
asset=ROOT/'android/app/src/aquarium/assets/cd.iff'
original_target=os.readlink(asset)
try:
    asset.unlink()
    asset.symlink_to('../../../../../wflevels/aquarium-cd.iff')
    subprocess.run(['./gradlew',':app:assembleAquariumRelease','--console=plain'],cwd=ROOT/'android',check=True)
finally:
    asset.unlink(missing_ok=True)
    asset.symlink_to(original_target)
for source,suffix in [('android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk','.apk'),
                      ('wflevels/aquarium/aquarium.lev','.lev'),('wflevels/aquarium-cd.iff','-cd.iff'),
                      ('wflevels/aquarium-standalone.iff','-standalone.iff')]:
    shutil.copyfile(ROOT/source,out/(a.name+suffix))
(out/(a.name+'.json')).write_text(json.dumps(vars(a),indent=2,default=str))
print(f'Archived {a.name}',flush=True)
