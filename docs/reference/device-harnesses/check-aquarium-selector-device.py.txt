#!/usr/bin/env python3
"""Verify the five-tank Aquarium release selector on the local Chromecast."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--serial', required=True)
ap.add_argument('--apk', default=str(ROOT/'android/app/build/outputs/apk/aquarium/release/worldfoundry-aquarium-release.apk'))
a = ap.parse_args()
ADB = '/home/will/android-sdk-local/platform-tools/adb'
PKG = 'org.worldfoundry.wf_game.aquarium'
OUT = ROOT/'docs/plans/2026-10-02-aquarium-three-more-tanks/engine/menu/integrated-five/device'
OUT.mkdir(parents=True, exist_ok=True)

def adb(*args):
    return subprocess.check_output([ADB, '-s', a.serial, *args], timeout=60)

def key(code):
    adb('shell', 'input', 'keyevent', str(code))
    time.sleep(.3)

def shot(name):
    (OUT/(name+'.png')).write_bytes(adb('exec-out', 'screencap', '-p'))

def launch():
    adb('shell', 'am', 'start', '-n', PKG+'/android.app.NativeActivity')
    time.sleep(5)

adb('install', '-r', a.apk)
adb('shell', 'am', 'force-stop', PKG)
adb('logcat', '-c')
launch()
# Initial controller panel consumes the first Back; subsequent short Back exits.
key(4)
time.sleep(1)
shot('selector')
initial_pid = adb('shell', 'pidof', PKG).decode().strip()
started = []
for index, name in enumerate(['clownfish-tiger-barbs','blue-shrimp','betta','jellyfish','lionfish']):
    if index:
        adb('shell', 'am', 'force-stop', PKG)
        launch()
        key(4)
    pid = adb('shell', 'pidof', PKG).decode().strip()
    for _ in range(index): key(20)
    key(23)
    time.sleep(4)
    shot(name)
    log = adb('logcat', '-d', '--pid='+pid, '-v', 'brief').decode(errors='replace')
    (OUT/(name+'-logcat.log')).write_text(log)
    choices = [int(n) for n in re.findall(r'level-menu: level (\d+) starts', log)]
    assert choices == [index], (index, choices)
    assert not any(s in log for s in ['ASSERTION FAILED', 'zforth compile error', 'zforth eval error', 'Fatal signal']), log[-2000:]
    started.append(index)
# ADB's keycombination preserves a zero event timestamp even when wall time is
# held, so it cannot validate the real remote's >=1s Back condition. Desktop
# returns are checked separately; physical remote hold remains a manual check.
initial_pid = adb('shell', 'pidof', PKG).decode().strip()
key(3)
time.sleep(1)
launch()
resume_pid = adb('shell', 'pidof', PKG).decode().strip()
shot('resumed')
assert resume_pid == initial_pid, (initial_pid, resume_pid)
key(4)
time.sleep(2)
launch()
relaunch_pid = adb('shell', 'pidof', PKG).decode().strip()
shot('relaunched')
assert relaunch_pid and relaunch_pid != initial_pid, (initial_pid,relaunch_pid)
result = dict(status='PASS', serial=a.serial, package=PKG,
              apk_sha256=hashlib.sha256(Path(a.apk).read_bytes()).hexdigest(),
              started_indices=started, menu_returns='Desktop: 5; physical TV remote hold pending', initial_pid=initial_pid,
              resume_pid=resume_pid, relaunch_pid=relaunch_pid,
              held_back='Physical remote verification pending; ADB injection has zero held timestamp', profiling=False)
(OUT/'checks.json').write_text(json.dumps(result, indent=2)+'\n')
(OUT/'.gitignore').write_text('*.log\n')
print(json.dumps(result, indent=2))
