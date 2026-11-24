"""Continuous normal-input Parmenides walkthrough; no state writes."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/home/will/WorldFoundry-wbniv')
BUILD = Path('/tmp/rooms-production-build-scene9')
sys.path.insert(0, str(ROOT/'tests'))
sys.path.insert(0, '/home/will/finding-your-way/game/parmenides-slice')
from debug_bridge_client import BridgeClient
from texture_slots import runtime_args

p = argparse.ArgumentParser()
p.add_argument('--out', required=True)
p.add_argument('--record', action='store_true')
p.add_argument('--stop-after', default='end')
args = p.parse_args()
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
ids = json.loads((BUILD/'actors.json').read_text())['ids']
content = json.loads((BUILD/'content.json').read_text())
player = ids['Player']
log = (OUT/'engine.log').open('w')
proc = subprocess.Popen([str(ROOT/'engine/wf_game'), '-L'+str(BUILD/'parmenides_slice-standalone.iff'),
                         *(['-record_video'] if args.record else []), '--debug-port','7819',
                         '--debug-bind','127.0.0.1','-width=1280','-height=720',*runtime_args(BUILD)],
                        cwd=OUT,env=dict(os.environ,DISPLAY=':255',LD_LIBRARY_PATH=str(ROOT/'engine/libs')),
                        stdout=log,stderr=subprocess.STDOUT)
b = None
events=[]
def val(m): return b.mailbox_values.get((player,m))
def state():
    return dict(realm=val(102), card=val(140), focus=val(130),
                x=val(3009), y=val(3010), heading=val(114), ready=val(129))
def event(label, buttons=''):
    row=dict(time=time.time(),label=label,buttons=buttons,**state())
    events.append(row)
    if label not in ('press','release'):
        print(json.dumps(row),flush=True)
    return row
def wait(predicate, timeout=30, label='condition'):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline and proc.poll() is None:
        if predicate(): return
        time.sleep(.03)
    raise RuntimeError(f'Timed out waiting for {label}: {state()}')
def press(bits,frames=5,label=None):
    label=label or str(bits)
    event('press',label)
    b.inject_input('joystick1_raw',bits,frames)
    wait(lambda: val(111) is not None and int(val(111))&bits==bits, max(15,frames*.3), 'pressed '+label)
    wait(lambda: val(111) is not None and int(val(111))&bits==0, max(20,frames*.3), 'released '+label)
    event('release',label)
def read_sheet(expected=None, stop_at_completion=False):
    wait(lambda: val(140) is not None and int(val(140))!=0, label='sheet open')
    if expected:
        assert int(val(140))==content['groups'][expected][0],(expected,state())
    start=event('sheet '+str(int(val(140))))
    steps=0
    while val(140) and int(val(140))!=0:
        current=int(val(140))
        wait(lambda: int(val(129) or 0)!=0 and int(val(632) or 0)==current,
             timeout=35,label='sheet ready')
        if stop_at_completion and current==content['groups']['ending_complete'][0] and int(val(225) or 0)==1:
            event('completed Being ending visible')
            time.sleep(3)
            return
        press(1,5,'Select')
        time.sleep(.12)
        steps+=1
        if steps>40: raise RuntimeError('Sheet did not finish: '+str(state()))
    event('sheet closed '+str(start['card']))
def heading_delta(target):
    actual=float(val(114) or 0)
    return (target-actual+.5)%1-.5
def walk_to(x,y,label):
    event('walk toward '+label)
    for step in range(100):
        s=state(); dx=x-float(s['x']);dy=y-float(s['y']);dist=math.hypot(dx,dy)
        if dist<1.5:
            event('arrived '+label);return
        target=math.atan2(dy,dx)/(2*math.pi)%1
        delta=heading_delta(target)
        if abs(delta)>.035:
            press(16384 if delta>0 else 8192,max(2,min(12,round(abs(delta)*120))),
                  'Left' if delta>0 else 'Right')
        s=state();dx=x-float(s['x']);dy=y-float(s['y']);dist=math.hypot(dx,dy)
        press(2048,max(2,min(6,round(dist*2))),'Up')
    raise RuntimeError('Could not reach '+label+': '+str(state()))
def interact(x,y,label,expected=None,realm=None):
    walk_to(x,y,label)
    event('interact '+label)
    press(1,5,'Select')
    if expected: read_sheet(expected)
    if realm is not None: wait(lambda: val(102) is not None and int(val(102))==realm,label='realm '+str(realm))
def route():
    wait(lambda: int(val(100) or 0)==1, label='chapter init')
    read_sheet('intro')
    interact(0,8,'Love gate',realm=1)
    if args.stop_after=='love':return
    interact(96,2,'First Love','first')
    interact(104,3,'Starlet','starlet')
    interact(100,7,'Advice Column','paper')
    interact(94,12,'Love Being gate','affirm',realm=0)
    interact(7,8,'Reason gate',realm=2)
    interact(196,1,'White Self','white')
    if args.stop_after=='reason':return
    interact(200,3,'Weather apparatus','apparatus_order')
    interact(204,7,'Wild Self','wild')
    interact(200,11,'Younger Self','child')
    interact(193,14,'Reason Being gate','reason_affirm',realm=0)
    interact(-7,8,'Truth gate',realm=3)
    read_sheet('truth_intro')
    if args.stop_after=='truth':return
    interact(294,1,'Prosecutor','prosecutor')
    interact(306,1,'Defence','defence')
    interact(300,6,'Student','student')
    interact(294,7,'Facts','facts')
    interact(306,7,'Interpretations','interpretations')
    interact(300,11,'Presentation','present')
    interact(293,17,'Truth Being gate','truth_affirm',realm=0)
    interact(0,-9,'Goddess gate',realm=4)
    read_sheet('god_intro')
    if args.stop_after=='god':return
    interact(400,1,'Young Man','young_man')
    interact(397,6,'Poster','poster')
    interact(400,13,'Holy Man','holy_man')
    interact(403,18,'Icon','icon')
    interact(397,24,'Question','god_question')
    interact(396,32,'God Being gate','god_affirm',realm=0)
    interact(-7,-12,'Final Being gate')
    read_sheet('ending_confirm_10a',stop_at_completion=True)
    assert int(val(225) or 0)==1,state()
try:
    b=BridgeClient(port=7819,timeout=25)
    for m in (100,101,102,103,104,105,106,107,110,111,114,129,130,140,150,151,152,
              153,154,155,157,170,171,172,173,174,175,176,177,188,189,190,191,192,
              193,194,195,196,197,198,225,629,630,632,3009,3010,3011):b.watch(player,m)
    route()
    event('route segment complete')
finally:
    (OUT/'events.json').write_text(json.dumps(events,indent=2)+'\n')
    if b:b.close()
    if proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log.close()
    receipt=dict(recorded=args.record,exit_code=proc.returncode,level_sha256=hashlib.sha256((BUILD/'cd.iff').read_bytes()).hexdigest(),
                 runtime_sha256=hashlib.sha256((ROOT/'engine/wf_game').read_bytes()).hexdigest(),events=len(events))
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
