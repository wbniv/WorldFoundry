#!/usr/bin/env python3
"""Real engine controls, animation, cameras and evidence on an isolated debug port."""
import argparse
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('kind',choices=['betta','jellyfish','lionfish','plants'])
ap.add_argument('--video',action='store_true')
ap.add_argument('--cost',action='store_true')
ap.add_argument('--out',type=Path)
ap.add_argument('--port',type=int)
args=ap.parse_args()
level='aquarium_'+args.kind
here=ROOT/'wflevels'/level
out=(args.out or ROOT/'docs/plans/2026-10-02-aquarium-three-more-tanks/engine'/args.kind).resolve()
out.mkdir(parents=True,exist_ok=True)
mapping=json.loads((here/'actor-map.json').read_text())
idx=mapping['indices']; mb=mapping['mailboxes']
player,director=idx['Player'],idx['Director']
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(ROOT/'engine/libs')+':'+env.get('LD_LIBRARY_PATH','')
log=(out/'runtime.log').open('w')
port=args.port or {'betta':17921,'jellyfish':17922,'lionfish':17923,'plants':17926}[args.kind]
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
    time.sleep(.2)
    step(20)
    assert value(director,mb['init'])==1,'Forth initialization failed'
    teleport((3.4 if args.kind=='betta' else -3.4,-.2,(mapping['bottom']+mapping['top'])/2));step(100)
    assert value(director,mb['camera'])==0
    shot('whole-tank')
    teleport(mapping['spawn']);step(100)
    if args.kind=='plants':inject(1);step(2);inject(0);step(3)
    assert value(director,mb['camera'])==1
    shot('close-up')
    if args.kind=='plants':
        assert mapping['count']==1 and mapping['animal']=='sea_urchin' and mapping['parts']==[] and mapping['rows']==[]
        assert not any(n.startswith('animal-') for n in idx)
        results['static_plant_groups']=[n for n in idx if n.startswith('plant_')]
        assert len(results['static_plant_groups'])==8
        print('PASS: sea urchin, static plants and both cameras',flush=True)
    else:
        before={k:value(*k) for k in watches};step(9);after={k:value(*k) for k in watches}
        changed=[(a,m) for a,m in watches if a not in (player,director) and abs(after[a,m]-before[a,m])>.0005]
        assert changed,'No visual animation'
        if mapping['count']>1:
            assert any(a==idx['animal-01-'+mapping['parts'][0]] and m in [3009,3010,3011] for a,m in changed),'Resident did not move'
        results['animated_mailboxes_changed']=len(changed)
        if args.kind=='jellyfish':
            bell=idx['animal-00-bell'];arms=idx['animal-00-arms']
            assert abs(after[bell,3042]-before[bell,3042])>.02,'Bell did not deform'
            assert abs(after[arms,3012]-before[arms,3012])>.001,'Oral arms did not lag/sway'
            scales=[value(idx[f'animal-{k:02d}-bell'],3042) for k in range(mapping['count'])]
            results['bell_z_scales']=scales
            assert max(scales)-min(scales)>.10,'Jellies pulsed in unison'
        print('PASS:',args.kind,'animation and both cameras',flush=True)
    directions={'right':(8192,16384,0,mapping['limits'][0]),'left':(16384,8192,0,-mapping['limits'][0]),
                'up':(2048,4096,2,mapping['top']),'down':(4096,2048,2,mapping['bottom']),
                'away':(4,2,1,mapping['limits'][1]),'toward':(2,4,1,-mapping['limits'][1])}
    if args.kind=='plants':
        for n in ['up','down']:directions.pop(n)
    for name,(bits,opposite,axis,limit) in directions.items():
        start_pos=[0,0,(mapping['bottom']+mapping['top'])/2]
        if args.kind=='plants':start_pos[axis]=limit-(.06 if limit>0 else -.06)
        teleport(start_pos);step(3);inject(bits)
        # Slow tanks take up to ten seconds to traverse the entire clear corridor.
        step(200 if args.kind=='plants' else 220)
        pos=position()
        assert abs(pos[axis]-limit)<.08,(name,pos,limit)
        assert value(player,1909)==bits,'Input isolation failed'
        assert 0<=value(director,mb['pulse'])<1,'Phase is unbounded'
        inject(opposite);step(48 if args.kind=='plants' else 24)
        assert abs(position()[axis]-pos[axis])>(.02 if args.kind=='plants' else .40),('Cannot leave wall',name,position())
        results['wall_'+name]=pos
        print('PASS:',name,'reach and leave',flush=True)
    teleport(mapping['spawn']);step(3)
    if args.kind=='plants':
        camera=value(director,mb['camera']);inject(1);step(2)
        assert value(director,mb['camera'])==1-camera
        step(15);assert value(director,mb['camera'])==1-camera,'Held action repeats'
        inject(0);step(2);inject(1);step(2);inject(0)
        assert value(director,mb['camera'])==camera
        results['view_toggle_and_input_release']='PASS'
        inject(2048);step(20);assert abs(position()[2]-mapping['bottom'])<.01
        inject(0)
        results['urchin_stays_on_substrate']='PASS'
    else:
        cli.set_mailbox(mb['heading'],0,idx=director)
        inject(1);step(2);inject(0)
        velocity=value(director,mb['vz' if args.kind=='jellyfish' else 'vx'])
        assert velocity>.25,('Action did not move player',velocity)
        assert value(director,mb['cooldown'])>.5
        results['action_velocity']=velocity
        step(25);shot('action')
    if args.video:
        (out/'frames').mkdir(exist_ok=True);teleport(mapping['spawn']);step(100)
        for k in range(100):
            if k==35:inject(8192)
            if k==55:inject(16384)
            if k==75:inject(0)
            step(1);shot(f'frames/frame-{k:04d}')
        subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate','20','-i',str(out/'frames/frame-%04d.png'),
                        '-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'motion.mp4')],check=True)
    results['status']='PASS'
finally:
    if cli:cli.close()
    proc.terminate()
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log.close()
    txt=(out/'runtime.log').read_text(errors='replace')
    if any(s in txt for s in ['zforth compile error','zforth eval error','ASSERTION FAILED']):
        raise RuntimeError('Engine script/assertion failure: '+str(out/'runtime.log'))
if args.cost:
    timings={};env.update(__GL_SYNC_TO_VBLANK='0',vblank_mode='0')
    for frames in [30,130]:
        started=time.monotonic()
        with (out/f'cost-{frames}.log').open('w') as f:
            subprocess.run([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels'/(level+'-standalone.iff')),
                            f'--frame-step-smoke={frames}'],cwd=here,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
        timings[frames]=time.monotonic()-started
    results['desktop_debug_ms_per_frame_estimate']=(timings[130]-timings[30])*10
    results['cost_note']='Two-point local debug wall-time estimate without vsync; not release/device frame distributions.'
(out/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
(out/'.gitignore').write_text('frames/\n*.log\n')
print(json.dumps(results,indent=2),flush=True)
