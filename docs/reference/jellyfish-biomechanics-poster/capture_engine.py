#!/usr/bin/env python3
"""Real engine controls, animation, cameras and evidence on an isolated debug port."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('kind',choices=['jellyfish'])
ap.add_argument('--out',type=Path)
ap.add_argument('--port',type=int)
args=ap.parse_args()
level='aquarium_'+args.kind
here=ROOT/'wflevels'/level
out=(args.out or Path(__file__).resolve().parent/'engine').resolve()
out.mkdir(parents=True,exist_ok=True)
mapping=json.loads((here/'actor-map.json').read_text())
idx=mapping['indices']; mb=mapping['mailboxes']
player,director=idx['Player'],idx['Director']
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(ROOT/'engine/libs')+':'+env.get('LD_LIBRARY_PATH','')
log=(out/'runtime.log').open('w')
port=args.port or 17932
env.update(WF_REST_HOST='127.0.0.1',WF_REST_PORT=str(port+1000))
proc=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels'/(level+'-standalone.iff')),
                       '-rate20','--debug-port',str(port),'--debug-bind','127.0.0.1','--debug-print-actors'],
                      cwd=here,env=env,stdout=log,stderr=subprocess.STDOUT,
                      preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
cli=None
results={'level':level,'animals':mapping['count'],'actors':len(idx),'profile':mapping['profile']}
try:
    cli=BridgeClient(port=port,timeout=20);cli.send({'op':'pause'})
    def inject(bits):cli.inject_input('joystick1_raw',bits,duration_frames=-1)
    inject(0)
    watches=[(player,m) for m in [1906,1909,3009,3010,3011]]+[(director,mb[n]) for n in ['init','camera','heading','pulse','vx','vy','vz','cooldown']]
    for name,a in idx.items():
        if name.startswith('animal-'):
            watches += [(a,m) for m in [3009,3010,3011,3012,3013,3014,3040,3041,3042]]
    for a,m in watches:cli.watch(idx=a,mailbox=m)
    def value(a,m):
        with cli._lock:return cli.mailbox_values.get((a,m),0)
    def step(n):
        start=value(player,1906);cli.send({'op':'step','frames':n});deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if value(player,1906)>=start+n*(3276/65536)-.0002:
                time.sleep(.025);return
            if proc.poll() is not None:raise RuntimeError('engine exited; see runtime.log')
            time.sleep(.005)
        raise RuntimeError('step timed out')
    def position():return [value(player,m) for m in (3009,3010,3011)]
    def teleport(pos):
        inject(0)
        for m,v in zip((3009,3010,3011),pos):cli.set_mailbox(m,v,idx=player)
        for n in ['vx','vy','vz','dart']:cli.set_mailbox(mb[n],0,idx=director)
    def shot(name):
        cli.send({'op':'screenshot','filename':str(out/(name+'.png'))})
        msg=cli.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=15)
        assert msg and msg.get('op')=='screenshot_done',msg
    js=mapping['movement']['jelly_states']
    for name in ['phase','player-phase','contraction']:
        cli.watch(idx=director,mailbox=js[name])
    time.sleep(.2)
    step(20)
    assert value(director,mb['init'])==1,'Forth initialization failed'
    teleport((-3.4,-.2,(mapping['bottom']+mapping['top'])/2));step(100)
    assert value(director,mb['camera'])==0
    shot('whole-tank')
    teleport(mapping['spawn']);step(100)
    assert value(director,mb['camera'])==1
    shot('close-up')
    pulse=[]
    for k in range(100):
        step(1)
        pulse.append(value(director,js['contraction']))
    assert max(pulse)>.9 and min(pulse)<.01, pulse
    results['native_contraction_range']=[min(pulse),max(pulse)]
    results['opacity_materials']={'bell':.22,'margin_and_arms':.32,'fringe':.12,'internal_motifs':.72}
    results['status']='PASS'
    print(json.dumps(results,indent=2),flush=True)
    (out/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
finally:
    if cli:cli.close()
    proc.terminate()
    proc.wait(timeout=15)
    log.close()
