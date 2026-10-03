#!/usr/bin/env python3
"""Profile archived planted-tank APKs and restore the normal menu release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--variants-dir',type=Path,required=True)
ap.add_argument('--restore-apk',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
ap.add_argument('--variants',nargs='+',default=['baseline','density','detailed'])
ap.add_argument('--cpu-variants',nargs='+',default=['baseline','density','detailed'])
ap.add_argument('--runs',type=int,default=3)
ap.add_argument('--serial',default='')
args=ap.parse_args()
args.out.mkdir(parents=True,exist_ok=True)
ADB=os.environ.get('ADB',str(Path.home()/'android-sdk-local/platform-tools/adb'))
A=[ADB]+(['-s',args.serial] if args.serial else [])
PKG='org.worldfoundry.wf_game.aquarium'
def adb(*words):return subprocess.check_output(A+list(words),timeout=30)
def key(code):adb('shell','input','keyevent',code)
def capture(label,cpu=False):
    apk=args.variants_dir/(label+('-cpu' if cpu else '')+'.apk')
    out=args.out/(label+('-cpu' if cpu else ''))
    subprocess.run([sys.executable,str(ROOT/'scripts/profile-aquarium-chromecast.py'),
                    '--apk',str(apk),'--out',str(out),'--menu-index','5',
                    '--scenario','plants','--warmup','30','--runs',str(1 if cpu else args.runs),
                    '--serial',args.serial],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/analyse-aquarium-profile.py'),str(out)],cwd=ROOT,check=True)
    for run in out.glob('run-*'):
        log=(run/'wf.log').read_text(errors='replace')
        if any(s in log.lower() for s in ('assertion failed','fatal signal','forth error')):
            raise RuntimeError('Runtime error in '+str(run))
try:
    for label in args.variants:capture(label)
    for label in args.cpu_variants:capture(label,cpu=True)
finally:
    print('Restoring normal eight-tank release',flush=True)
    adb('install','-r',str(args.restore_apk))
    installed=adb('shell','pm','path',PKG).decode().strip().removeprefix('package:')
    actual=adb('shell','sha256sum',installed).decode().split()[0]
    assert actual==hashlib.sha256(args.restore_apk.read_bytes()).hexdigest()
    adb('shell','am','force-stop',PKG)
    adb('shell','am','start','-n',PKG+'/android.app.NativeActivity')
    time.sleep(9);key('KEYCODE_BACK');time.sleep(1)
    (args.out/'restored-selector.png').write_bytes(adb('exec-out','screencap','-p'))
    for _ in range(5):key('KEYCODE_DPAD_DOWN');time.sleep(.15)
    key('KEYCODE_DPAD_CENTER');time.sleep(5)
    (args.out/'restored-plants.png').write_bytes(adb('exec-out','screencap','-p'))
    (args.out/'restored.json').write_text(json.dumps({'apk_sha256':actual,'normal_menu_release_restored':True,'profile_enabled':False},indent=2)+'\n')
