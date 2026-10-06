#!/usr/bin/env python3
"""Source/compiled checks, plus an optional owned desktop movement session."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'build'
RESULTS=[]

def check(name,condition,**details):
    RESULTS.append(dict(check=name,passed=bool(condition),**details))
    print(name, bool(condition),flush=True)
    if not condition:raise AssertionError(name)

def structural():
    c=json.loads((HERE/'baseline.json').read_text())
    inventory=json.loads((OUT/'scene-inventory.json').read_text())
    objs={o['name']:o for o in inventory}
    preset=json.loads((HERE/'actor-map.json').read_text())['preset']
    half=c['floor_size']/2
    check('configured floor and collision bounds',objs['Floor']['bounds']==[-half,-half,-c['floor_depth'],half,half,0])
    check('explicit player bounds',objs['Player']['bounds']==c['player_bounds'])
    check('no imported adventure/scaffold content',not re.search(r'snowgoons|parmenides|goddess|temple',json.dumps(inventory),re.I))
    check('default excludes diagnostics',preset!='default' or all(o['collection']!='DIAGNOSTICS' for o in inventory))
    check('two independently addressed settings owners',objs['SampleSettings']['schema']=='target.oad' and objs['SampleSettings2']['schema']=='target.oad')
    check('default explicit runtime camera/room objects',all(n in objs for n in ['Level','Room','Camera','CameraOrigin','TargetFollow','TargetFirst','Follow','FirstPerson','Directional','Ambient','Background']))
    spec=json.loads((HERE/'settings-coverage.json').read_text())
    from settings_fixture import TYPES,SHOW
    check('every declared descriptor type accounted for',set(TYPES)=={f['type'] for f in spec['fields']}|set(spec['exclusions'])|set(spec['structural_types']))
    check('all presentation codes accounted for',set(range(len(SHOW)))<={f['show_code']&127 for f in spec['fields']})
    b=(HERE/'settings-gallery.oad').read_bytes()
    check('complete OAD framing',(len(b)-80)%1491==0)
    entries={}
    for o in range(80,len(b),1491):
        e=b[o:o+1491];key=e[1:65].split(b'\0')[0].decode()
        entries[key]=e
    for f in spec['fields']:
        e=entries[f['key']]
        check('compiled descriptor '+f['key'],e[0]==f['button_type'] and e[591]==f['show_code'] and struct.unpack_from('<iii',e,65)==(f['min'],f['max'],f['default']))
    data=(OUT/'settings.rprp').read_bytes()
    check('catalog contains two object instances',data[:4]==b'RP01' and struct.unpack_from('<I',data,4)[0]==2)
    check('standalone L4 and sector-aligned asset', (ROOT/'wflevels/baseline-standalone.iff').read_bytes()[:2]==b'L4' and (ROOT/'wflevels/baseline-standalone.iff').stat().st_size%2048==0)

def desktop():
    sys.path.insert(0,str(ROOT/'tests'))
    from debug_bridge_client import BridgeClient
    port=7785
    ids=json.loads((HERE/'actor-map.json').read_text())['indices'];player=ids['Player']
    capture=OUT/'desktop';capture.mkdir(exist_ok=True)
    env=dict(os.environ,DISPLAY=os.environ.get('DISPLAY',':0'),LD_LIBRARY_PATH=str(ROOT/'engine/libs'))
    log=(capture/'engine.log').open('w')
    args=[str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/baseline-standalone.iff'),'--debug-port',str(port),'--debug-bind','127.0.0.1','--debug-print-actors','-width=1280','-height=720','--vram-width=5120','--vram-height=2048','--vram-slot-width=1024','--vram-slot-height=1024','--vram-perm-width=1024','--vram-perm-height=1024']
    proc=subprocess.Popen(args,cwd=capture,env=env,stdout=log,stderr=subprocess.STDOUT)
    bridge=None
    try:
        bridge=BridgeClient(port=port,timeout=20)
        for m in [3009,3010,3011,3014,111]:bridge.watch(player,m)
        for m in [120,121,122,1921]:bridge.watch(ids['Director'],m)
        def position():return [bridge.mailbox_values.get((player,m)) for m in [3009,3010,3011]]
        def settle(seconds=1):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError('Runtime exited; see '+str(capture/'engine.log'))
                time.sleep(.05)
        def hold(bit,seconds=.8):
            bridge.inject_input('joystick1_raw',bit,-1)
            if not bridge.wait_for_mailbox(ids['Director'],121,bit,timeout=5):raise RuntimeError('Director did not observe injected press')
            settle(seconds)
            bridge.inject_input('joystick1_raw',0,-1)
            if not bridge.wait_for_mailbox(ids['Director'],121,0,timeout=5):raise RuntimeError('Director did not observe injected release')
            settle(.6)
        def shot(name):
            bridge.send(dict(op='screenshot',filename=str(capture/(name+'.png'))));settle(.3)
        settle(2)
        check('native script compilation succeeds','zforth compile error' not in (capture/'engine.log').read_text())
        start=position();check('native player grounded at spawn',all(v is not None for v in start) and abs(start[0])<.05 and abs(start[1]+5)<.05 and .85<start[2]<1.05,position=start)
        shot('spawn')
        hold(2048);forward=position();check('native held Up moves +Y',forward[1]>start[1]+.3,position=forward)
        settle(1);released=position();check('native release settles movement',sum((a-b)**2 for a,b in zip(forward,released))<.05,position=released)
        hold(2,.1);reset=position();check('B resets native player',abs(reset[0])<.05 and abs(reset[1]+5)<.05,position=reset)
        # Debug-assisted direction setup; actual movement remains native input.
        bridge.set_mailbox(3014,0,player);settle(.2);hold(2048);p=position()
        check('native Up with zero heading moves +X',abs(p[0])>.3,position=p)
        hold(2,.1)
        hold(4,.1);check('camera switches to first-person',bridge.mailbox_values.get((ids['Director'],122))==1)
        shot('first-person');hold(4,.2)
        check('camera switches back to follow',bridge.mailbox_values.get((ids['Director'],122))==0,mode=bridge.mailbox_values.get((ids['Director'],122)),previous_input=bridge.mailbox_values.get((ids['Director'],121)))
        shot('follow')
        # Debug-assisted collision approach: player starts facing the unit cube.
        bridge.send(dict(op='scene:set_transform',idx=player,pos=[5,-2,.92]));bridge.set_mailbox(3014,.25,player);settle(.3)
        hold(2048,1.2);p=position();check('unit cube blocks native movement',p[1]<-.65,position=p)
        shot('cube-collision')
        for x,y in [(-90,-90),(90,-90),(-90,90),(90,90)]:
            bridge.send(dict(op='scene:set_transform',idx=player,pos=[x,y,1.1]));settle(.7);p=position()
            check('quadrant floor support '+str((x,y)),abs(p[0]-x)<.1 and abs(p[1]-y)<.1 and .85<p[2]<1.05,position=p)
        bridge.send(dict(op='scene:set_transform',idx=player,pos=[102,0,-9]));settle(.8)
        p=position();check('fall reset restores spawn',abs(p[0])<.05 and abs(p[1]+5)<.05,position=p)
        hold(2049,.1);p=position();check('remote Up+OK resets without jumping',abs(p[1]+5)<.05 and .85<p[2]<1.05,position=p)
        check('runtime still running',proc.poll() is None)
    finally:
        if bridge:bridge.close()
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--desktop',action='store_true');args=ap.parse_args()
    try:
        structural()
        if args.desktop:desktop()
    finally:
        OUT.mkdir(exist_ok=True)
        (OUT/'verification.json').write_text(json.dumps(dict(desktop_requested=args.desktop,checks=RESULTS),indent=2)+'\n')
