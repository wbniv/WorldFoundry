#!/usr/bin/env python3
"""Rebuild and archive a named aquarium variant for reproducible device comparisons."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--asset', choices=['clownfish','barb_quad','barb_mesh'], required=True)
ap.add_argument('--count', type=int, required=True)
ap.add_argument('--updates', type=int, default=5)
ap.add_argument('--static', action='store_true')
ap.add_argument('--frozen', action='store_true')
ap.add_argument('--profile', action='store_true')
ap.add_argument('--name', required=True)
ap.add_argument('--out', default='/tmp/aquarium-barb-baselines')
a=ap.parse_args()
ROOT=Path(__file__).resolve().parents[1]
env=dict(os.environ,AQUARIUM_FOLLOWER_ASSET=a.asset,AQUARIUM_SCHOOL_N=str(a.count),
         AQUARIUM_BARB_UPDATES=str(a.updates),AQUARIUM_BARB_ANIMATE='0' if a.static else '1',
         AQUARIUM_BARB_FROZEN='1' if a.frozen else '0')
subprocess.run(['task','--force','aquarium-level'],cwd=ROOT,env=env,check=True)
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
out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
for source,suffix in [('android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk','.apk'),
                      ('wflevels/aquarium/aquarium.lev','.lev'),('wflevels/aquarium-cd.iff','-cd.iff'),
                      ('wflevels/aquarium-standalone.iff','-standalone.iff')]:
    shutil.copyfile(ROOT/source,out/(a.name+suffix))
(out/(a.name+'.json')).write_text(json.dumps(vars(a),indent=2))
print(f'Archived {a.name}',flush=True)
