#!/usr/bin/env python3
"""Verify installed Arowana movement/recovery through timed Android D-pad events.

Uses the release engine's position log, so no debug bridge is required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--serial',required=True)
ap.add_argument('--apk',required=True,type=Path)
a=ap.parse_args()
ADB='/home/will/android-sdk-local/platform-tools/adb'
PKG='org.worldfoundry.wf_game.aquarium'
LOG=f'/sdcard/Android/data/{PKG}/files/wf.log'
OUT=ROOT/'docs/plans/2026-10-02-asian-arowana/device/2026-10-03-response'
OUT.mkdir(parents=True,exist_ok=True)
def adb(*args):return subprocess.check_output([ADB,'-s',a.serial,*args],timeout=45)
def key(code,ms=120):adb('shell','input','keycombination','-t',str(ms),str(code),'59')
def screenshot(name):(OUT/(name+'.png')).write_bytes(adb('exec-out','screencap','-p'))
def offset():return int(adb('shell','stat','-c','%s',LOG).decode().strip())
def positions(mark):
 text=adb('shell','tail','-c','+'+str(mark+1),LOG).decode(errors='replace')
 assert not any(word in text for word in ('zforth compile error','zforth eval error','ASSERTION FAILED')),text[-3000:]
 rows=[list(map(float,row)) for row in re.findall(r'ball pos: \(([-\d.]+), ([-\d.]+), ([-\d.]+)\)',text)]
 assert rows,'No native position samples were logged'
 return rows
installed=adb('shell','pm','path',PKG).decode().strip().removeprefix('package:')
actual=adb('shell','sha256sum',installed).decode().split()[0]
assert actual==hashlib.sha256(a.apk.read_bytes()).hexdigest(),'TV is running a different APK'
adb('shell','am','force-stop',PKG)
start_log=offset()
adb('shell','am','start','-n',PKG+'/android.app.NativeActivity');time.sleep(3)
adb('shell','input','keyevent','4');time.sleep(.5) # Cold-start phone panel.
for _ in range(6):key(20);time.sleep(.15)
key(23);time.sleep(3)
pid=adb('shell','pidof',PKG).decode().strip();assert pid
log=adb('logcat','-d','--pid='+pid,'-v','brief').decode(errors='replace')
assert 'level-menu: level 6 starts' in log,'Arowana selection was not delivered'
mark=offset();key(22,2500);time.sleep(.7);cruise=positions(mark)
assert cruise[-1][0]>4,'D-pad movement is too slow'
mark=offset();key(22,7000);time.sleep(.7);wall=positions(mark)
assert wall[-1][0]>14.5,'Right hold did not reach the wall approach'
mark=offset();key(21,6000);time.sleep(.7);recovery=positions(mark)
assert recovery[-1][0]<wall[-1][0]-3,'Left request remained stuck at the right wall'
assert all(abs(x)<15.54 and abs(y)<10.54 and 3.63<z<8.37 for x,y,z in cruise+wall+recovery),'Native position left its clearance reserve'
screenshot('ready-for-remote')
# Check the whole current launch for script/runtime errors, not just movement.
positions(start_log)
report=dict(status='PASS',apk_sha256=actual,serial=a.serial,right_hold_ms=2500,cruise_end=cruise[-1],wall_end=wall[-1],left_recovery_ms=6000,recovery_end=recovery[-1],cruise_samples=cruise,wall_samples=wall,recovery_samples=recovery,
 note='Chromecast HD release engine, timed Android D-pad events and native position log. Confirms sustained movement and recovery after reaching the wall. Physical remote repeat/chord behavior is not established by injected events. App left in Arowana ready for the remote.')
(OUT/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if not k.endswith('samples')},indent=2))
adb('forward','--remove','tcp:17928')
