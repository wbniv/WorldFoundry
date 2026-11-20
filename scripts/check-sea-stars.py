#!/usr/bin/env python3
"""Verify the real engine's Sea Stars planes, input release and resident reactions.

Run in the Linux test container under xvfb-run. Saves runtime.log, trace.json,
results.json and screenshots under docs/diagnostics/sea-stars-2026-11-20.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'wflevels/aquarium_sea_stars')]
from debug_bridge_client import BridgeClient
from controller import CELLS
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--wf-game',type=Path,default=ROOT/'build-docker/sea-stars-wf-game')
p.add_argument('--out',type=Path,default=ROOT/'docs/diagnostics/sea-stars-2026-11-20')
p.add_argument('--port',type=int,default=17993)
p.add_argument('--video',action='store_true',help='also save a sequence of corner frames')
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
indices=json.loads((ROOT/'wflevels/aquarium_sea_stars/actor-map.json').read_text())['indices']
player=indices['Player'];director=indices['Director'];trace=[]
log=(out/'runtime.log').open('w')
env=dict(os.environ,WF_REST_HOST='127.0.0.1',WF_REST_PORT=str(a.port+1000))
proc=subprocess.Popen([str(a.wf_game),'-L'+str(ROOT/'wflevels/aquarium_sea_stars-standalone.iff'),'-rate20',
    '--debug-port',str(a.port),'--debug-bind','127.0.0.1','-width=1280','-height=720',
    '--vram-width=4096','--vram-height=2048','--vram-slot-width=1024','--vram-slot-height=1024',
    '--vram-perm-width=1024','--vram-perm-height=1024'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
    preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
cli=None
try:
    cli=BridgeClient(port=a.port,timeout=45)
    cli.send({'op':'pause'})
    for actor,boxes in ((player,(1906,3009,3010,3011,3018,3019,3020)),(director,(*CELLS.values(),745,746,751,752))):
        for box in boxes:cli.watch(actor,box)
    def value(actor,box):
        with cli._lock:return cli.mailbox_values.get((actor,box),0.)
    def cell(box):return value(director,box)
    def step(frames,bits=0):
        cli.inject_input('joystick1_raw',bits,duration_frames=-1)
        start=value(player,1906)
        cli.send({'op':'step','frames':frames})
        deadline=time.monotonic()+45
        while value(player,1906)<start+frames*(3276/65536)-.002:
            if proc.poll() is not None:raise RuntimeError('engine exited')
            if time.monotonic()>deadline:raise RuntimeError('step timed out')
            time.sleep(.01)
        time.sleep(.04)
        row=dict(time=value(player,1906),position=[value(player,b) for b in (3009,3010,3011)],
            surface=cell(CELLS['surface']),roll=cell(CELLS['roll']),state=[cell(CELLS[k]) for k in ('x','y','z')],
            sand=[cell(745),cell(746)],brittle=cell(751))
        trace.append(row);return row
    def shot(name):
        cli.send({'op':'screenshot','filename':str(out/(name+'.png'))})
        msg=cli.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=20)
        assert msg and msg.get('op')=='screenshot_done',msg
    def place(x,y,z,surface=0):
        for box,v in zip((CELLS['x'],CELLS['y'],CELLS['z'],CELLS['surface'],CELLS['roll'],CELLS['idle']),(x,y,z,surface,0,0)):
            cli.set_mailbox(box,v,director)
        for box,v in zip((3009,3010,3011),(x,y,z)):cli.set_mailbox(box,v,player)
    step(2);shot('wide')
    place(0,-1,.8);r=step(20,8192);assert r['position'][0]>.3,r
    stopped=step(10);stopped2=step(10)
    assert max(abs(x-y) for x,y in zip(stopped['position'],stopped2['position']))<.001
    place(0,-2.65,.8);step(1,4096)
    for i in range(26):
        r=step(1,4096)
        if a.video and i%4==0:shot('corner-'+str(i))
    r=step(100,2048);assert r['surface']==1 and r['position'][2]>2,r
    shot('front-glass-underside')
    step(12,2048|8192);shot('front-glass-diagonal')
    # Side-wall transitions exercise actual Jolt synchronization, not just VM math.
    for start,surface,destination in (((5.64,-2.65,2.8),1,2),((5.65,2.64,2.8),2,3),((-5.64,2.65,2.8),3,4),((-5.65,-2.64,2.8),4,1)):
        place(*start,surface);r=step(30,8192);assert r['surface']==destination,r
        assert max(abs(x-y) for x,y in zip(r['position'],r['state']))<.001,r
    # Reaction thresholds are 25 cm for brittle, 8 cm for sand.
    place(3.3,.25,.8);r=step(8);assert r['brittle']>.3,r;shot('brittle-retreat')
    # Wake a sand star before approaching it; a nearby player forces a <1 s sink.
    cli.set_mailbox(CELLS['clock'],70,director)
    place(-1.8,-1.55,.8);r=step(20);assert r['sand'][0]<.05,r;shot('sand-buried')
    place(0,0,.8);step(60,1);shot('reach')
    results=dict(status='PASS',checks=['actual engine movement and release','front-glass climb','four side corners','Jolt/script positions agree','brittle escape','sand contact burial'])
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results))
finally:
    (out/'trace.json').write_text(json.dumps(trace,indent=2)+'\n')
    if cli:cli.close()
    proc.terminate()
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log.close()
