#!/usr/bin/env python3
"""Capture matched condo door/shade states through the engine debug bridge."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
from debug_bridge_client import BridgeClient
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--level', type=Path, default=ROOT/'wflevels/condo_639_640-standalone.iff')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--port', type=int, default=7795)
p.add_argument('--legacy-geometry', action='store_true', help='baseline shade uses world-baked, unscaled strips')
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
log = a.out/'runtime.txt'
env = dict(os.environ, DISPLAY=os.environ.get('DISPLAY', ':0'), LD_LIBRARY_PATH=str(ROOT/'engine/libs'), LSAN_OPTIONS='detect_leaks=0')
flags = (ROOT/'android/app/src/condo/assets/wf_args.txt').read_text().split()
with log.open('w') as f:
    proc = subprocess.Popen([str(ROOT/'engine/wf_game'), '-L'+str(a.level.resolve()), *flags,
                             '-width=1280', '-height=720', '--debug-port', str(a.port),
                             '--debug-bind', '127.0.0.1', '--debug-print-actors'],
                            env=env, cwd=ROOT/'wfsource/source/game', stdout=f, stderr=subprocess.STDOUT)
    try:
        cli = BridgeClient(port=a.port, timeout=15)
        time.sleep(1)
        def actor(mesh):
            match = re.search(r'actor idx=(\d+) mesh='+re.escape(mesh)+r'\b', log.read_text())
            if not match:
                raise RuntimeError('Actor not found: '+mesh)
            return int(match[1])
        player = actor('player.iff')
        # Capture-only override stops the normal inspection policy from rewriting
        # the fixed shot. The shipped player script is never changed.
        cli.send({'op':'reload_script','idx':player,'source':'\\ wf\n0 INDEXOF_INPUT write-mailbox\n'})
        time.sleep(.3)
        # Nonmesh actors are found in the exported level's ordered actor list.
        lev = (ROOT/'wflevels/condo_639_640/condo_639_640.lev').read_text()
        names = re.findall(r'^\t\t\{ \'NAME\' "([^"]+)"', lev, re.MULTILINE)
        # The debug log lists camera shot/target actors by mesh-less index; derive
        # directly from the saved level, whose actor order is invariant in this change.
        def named(name):
            return names.index(name) + 1
        shot, look = named('cs_dollhouse'), named('LookAt')
        # Freeze motion for exactly matched stills; interaction tests exercise
        # the shipped Director separately. Only this running process is patched.
        cli.send({'op':'reload_script','idx':named('Director'),'source':'\\ wf\n0 drop\n'})
        time.sleep(.2)
        print('CAMERA_ACTORS',shot,look,flush=True)
        for idx in (1,shot,look):
            for mb in (3009,3010,3011): cli.watch(idx,mb)
        states = [('raised-open',0,0), ('half-open',.5,0), ('closed-open',1,0),
                  ('closed-partial',1,.5), ('closed-closed',1,1)]
        for view, offset in [('inside',(0,-2.8,1.7)), ('outside',(0,3.8,1.7)),
                             ('oblique',(-1.8,-2.8,1.7))]:
            cli.send({'op':'scene:set_transform','idx':player,'pos':[4.35,-1.3,16.0]})
            for idx, pos in ((shot,(offset[0],offset[1],15.75+offset[2])), (look,(0,0,17.45))):
                for mb, val in zip((3009,3010,3011),pos):
                    cli.set_mailbox(mb,val,idx=idx)
            time.sleep(6)
            print(view, cli.mailbox_values,flush=True)
            for label, shade, door in states:
                for i in range(2):
                    cli.set_mailbox(3009, (-2.6667 if i == 0 else -1.3333)*door,
                                    idx=named(f'639-project-door-panel-{i}'))
                h = (2.05-1.072)/8
                for i in range(8):
                    idx = named(f'639-balcony-shade-slat-{i}')
                    base = 15.75 if a.legacy_geometry else round(15.75+2.05-(i+1)*h,4)
                    cli.set_mailbox(3011, base+round((i+1)*h+.035,5)*(1-shade),idx=idx)
                    if not a.legacy_geometry:
                        cli.set_mailbox(3042,shade,idx=idx)
                cli.set_mailbox(3011,15.75+(8*h+.035)*(1-shade),idx=named('639-balcony-shade-bar'))
                time.sleep(.5)
                dest = (a.out/f'{view}-{label}.png').resolve()
                started = time.time()
                cli.send({'op':'screenshot','filename':str(dest)})
                deadline = time.monotonic()+5
                while (not dest.exists() or dest.stat().st_mtime < started) and time.monotonic()<deadline:
                    time.sleep(.05)
                if not dest.exists() or dest.stat().st_mtime < started:
                    raise RuntimeError('Capture failed: '+str(dest))
                print(dest, flush=True)
        cli.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
