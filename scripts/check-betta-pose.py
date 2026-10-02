#!/usr/bin/env python3
"""Capture the poster's exact runtime fin state in the GL engine (debug-authored pose)."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from debug_bridge_client import BridgeClient
OUT=ROOT/'docs/plans/2026-10-02-betta-poster-and-flowing-fins/engine'
idx=json.loads((ROOT/'wflevels/aquarium_betta/actor-map.json').read_text())['indices']['Director']
env=dict(os.environ,LD_LIBRARY_PATH=str(ROOT/'engine/libs'),ASAN_OPTIONS='detect_leaks=0',WF_REST_PORT='18937')
with (OUT/'poster-pose.log').open('w') as log:
 p=subprocess.Popen([str(ROOT/'engine/wf_game'),'-L'+str(ROOT/'wflevels/aquarium_betta-standalone.iff'),'-rate30','--debug-port','17937','--debug-bind','127.0.0.1'],cwd=ROOT/'wflevels/aquarium_betta',env=env,stdout=log,stderr=log)
 c=None
 try:
  c=BridgeClient(port=17937,timeout=20);c.send({'op':'pause'});c.inject_input('joystick1_raw',0,duration_frames=-1)
  for mb in range(660,667):c.watch(idx=idx,mailbox=mb)
  c.send({'op':'step','frames':3});time.sleep(.3)
  dt=2184/65536
  for mb,v in {660:0,661:0,662:0,663:.21-dt*.55,664:.39-dt*1.8,665:0,666:.72}.items():c.set_mailbox(mb,v,idx=idx)
  c.send({'op':'step','frames':1});time.sleep(.5)
  with c._lock:state={str(m):c.mailbox_values[(idx,m)] for m in range(660,667)}
  assert abs(state['663']-.21)<.001 and abs(state['664']-.39)<.001 and abs(state['666']-.72)<.001,state
  c.send({'op':'screenshot','filename':str(OUT/'poster-pose.png')})
  msg=c.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=10);assert msg and msg['op']=='screenshot_done',msg
  (OUT/'poster-pose.json').write_text(json.dumps({'status':'PASS','mailboxes':state,'note':'Debug-authored zero-drive pose matching studio settings to fixed-point precision. Actual native fin deformation; camera and lighting differ.'},indent=2)+'\n')
 finally:
  if c:c.close()
  p.terminate();p.wait(timeout=5)
print('PASS: actual native pose matches poster settings')
