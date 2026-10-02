#!/usr/bin/env python3
"""Actual-engine Arowana trajectories, complete conservative envelope and captures."""
import argparse
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--video',action='store_true')
a=ap.parse_args()
HERE=ROOT/'wflevels/aquarium_arowana'
OUT=ROOT/'docs/plans/2026-10-02-asian-arowana/engine'
OUT.mkdir(exist_ok=True)
mapping=json.loads((HERE/'actor-map.json').read_text());idx=mapping['indices'];mb=mapping['mailboxes']
player=idx['Player'];director=idx['Director'];body=idx['animal-00-ar_body']
env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs'),WF_REST_HOST='127.0.0.1',WF_REST_PORT='18927')
log=(OUT/'runtime.log').open('w')
proc=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/aquarium_arowana-standalone.iff'),'-rate20','--debug-port','17927','--debug-bind','127.0.0.1'],cwd=HERE,env=env,stdout=log,stderr=subprocess.STDOUT,
 preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_CORE,(0,0)))
client=None
try:
 client=BridgeClient(port=17927,timeout=20);client.send({'op':'pause'});client.inject_input('joystick1_raw',0,-1)
 for box in [1906,3009,3010,3011,3018,3019,3020]:client.watch(player,box)
 for box in sorted(set(mb.values())):client.watch(director,box)
 for part in mapping['parts']:
  for box in range(3009,3015):client.watch(idx['animal-00-'+part],box)
 def value(actor,box):
  with client._lock:return client.mailbox_values.get((actor,box),0)
 def state(name):return value(director,mb[name])
 def step(n):
  t=value(player,1906);client.send({'op':'step','frames':n});deadline=time.monotonic()+45
  while value(player,1906)<t+n*(3276/65536)-.002:
   if proc.poll() is not None:raise RuntimeError('engine exited')
   if time.monotonic()>deadline:raise RuntimeError('step timed out')
   time.sleep(.01)
  time.sleep(.04)
 def shot(name):
  client.send({'op':'screenshot','filename':str(OUT/(name+'.png'))})
  message=client.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),15)
  assert message and message['op']=='screenshot_done',message
 def pos():return [value(player,m) for m in (3009,3010,3011)]
 def reset(position=(0,0,6),yaw=0):
  client.inject_input('joystick1_raw',0,-1)
  for box,v in zip((3009,3010,3011),position):client.set_mailbox(box,v,player)
  for box in (3018,3019,3020):client.set_mailbox(box,0,player)
  for box in [*range(600,640),*sorted(set(mb.values()))]:client.set_mailbox(box,0,director)
  client.set_mailbox(mb['aq-yaw'],yaw,director)
  step(3)
 samples=[]
 def audit(label):
  p=pos();speed=state('aq-speed');turn=state('ar-turn');yaw_rate=state('aq-yaw-w');radius=state('ar-radius')
  assert abs(p[0])<=15.53 and abs(p[1])<=10.53 and 3.64<=p[2]<=8.36,(label,p)
  assert state('aq-pushed')==0,(label,'position correction')
  if not turn:assert abs(yaw_rate)<=speed/radius/math.tau+.0001,(label,speed,yaw_rate,radius)
  facing=[state(n) for n in ('aq-fx','aq-fy','aq-fz')]
  velocity=[value(player,box) for box in (3018,3019,3020)]
  assert all(abs(v-speed*f)<.025 for v,f in zip(velocity,facing)),(label,velocity,facing,speed)
  aa,bb,cc=[value(body,box)*math.tau for box in (3012,3013,3014)]
  sa,ca,sb,cb,sc,ccos=math.sin(aa),math.cos(aa),math.sin(bb),math.cos(bb),math.sin(cc),math.cos(cc)
  rotation=((cb*ccos,sb*sa*ccos-ca*sc,sb*ca*ccos+sa*sc),
            (cb*sc,sb*sa*sc+ca*ccos,sb*ca*sc-sa*ccos),(-sb,cb*sa,cb*ca))
  envelope=[sum(abs(r[i])*h for i,h in enumerate((3.70,1.50,1.19))) for r in rotation]
  root=[value(body,box) for box in (3009,3010,3011)]
  margins=[19.873-abs(root[0])-envelope[0],14.873-abs(root[1])-envelope[1],root[2]-.20-envelope[2],12-root[2]-envelope[2]]
  assert min(margins)>0,(label,'full animated box clips',margins)
  for part in mapping['parts']:
   actor=idx['animal-00-'+part]
   assert all(abs(value(actor,box)-value(body,box))<.0001 for box in range(3009,3015)),(label,'detached root',part)
  samples.append(dict(trace=label,position=p,speed=speed,yaw=state('aq-yaw'),pitch=state('aq-pitch'),yaw_rate=yaw_rate,radius=radius,low_speed_turn=turn,minimum_clearance=min(margins),bend=state('ar-bend')))
 def trace(label,bits,n):
  print('Checking',label,flush=True)
  client.inject_input('joystick1_raw',bits,-1)
  for frame in range(0,n,20):step(min(20,n-frame));audit(label)
 step(20);reset();step(25);shot('side-close')
 for name,bits in [('right',8192),('left',16384),('up',2048),('down',4096),('away',4),('toward',2)]:
  reset();trace(name,bits,360);shot(name)
 reset();trace('build-drive',8192,60)
 client.inject_input('joystick1_raw',16384,-1)
 for frame in range(40):
  step(10);audit('reverse-turn')
  if a.video:shot(f'reverse-{frame:03d}')
  if frame in (5,20,35):shot(f'reverse-turn-{frame:02d}')
 assert pos()[0]<0,'reversal never recovered forward swimming'
 trace('release',0,120);assert state('aq-speed')<.02
 reset((15.4,10.4,6),.125);trace('corner-recovery',16386,500);shot('corner-recovery')
 assert pos()[0]<13 and pos()[1]<8,'corner recovery failed'
 reset();trace('burst-held',8193,80)
 assert state('aq-dart-t')==0,'held action restarted burst'
 trace('burst-release',8192,1);trace('burst-again',8193,1)
 assert state('aq-dart-t')>.2,'fresh action did not burst'
 if mapping['profile']=='remote':
  reset();trace('chord-up',2048,1);trace('chord-mode',2049,1)
  assert state('aq-mode')==1 and state('ar-neutral')==1 and state('aq-dart-t')==0
  trace('chord-held-direction',8192,5);assert state('aq-dx')==0
  trace('chord-neutral',0,1);trace('depth-mode',2048,1);assert state('aq-dy')==1
 reset();client.set_mailbox(3009,8,player);step(30);audit('wide');shot('whole-tank-oblique')
 if a.video:
  subprocess.run(['ffmpeg','-y','-framerate','2','-i',str(OUT/'reverse-%03d.png'),'-c:v','libx264','-pix_fmt','yuv420p',str(OUT/'reverse-turn.mp4')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 result=dict(status='PASS',profile=mapping['profile'],samples=samples,
  note='Actual desktop engine: full conservative deformed-envelope bounds, root pose, curvature, reversal, corner recovery, six inputs, burst recovery, release and remote chord. Video is fixed simulation time, not a presented-frame performance measurement. Physical remote/Chromecast validation remains pending.')
 (OUT/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(status='PASS',profile=mapping['profile'],samples=len(samples),minimum_clearance=min(s['minimum_clearance'] for s in samples)),indent=2))
finally:
 if client:client.close()
 proc.terminate()
 try:proc.wait(timeout=5)
 except subprocess.TimeoutExpired:proc.kill();proc.wait()
 log.close()
 text=(OUT/'runtime.log').read_text(errors='replace')
 assert not any(x in text for x in ['zforth compile error','zforth eval error','ASSERTION FAILED']),text[-2000:]
