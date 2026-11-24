"""Verify real desktop actor phases and capture the tourbillon."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

root=Path('/src');sys.path[:0]=[str(root/'tests'),str(root/'wflevels/triple_axis_tourbillon')]
from debug_bridge_client import BridgeClient
import model

stamp,output=sys.argv[1:3];args=sys.argv[3:]
ids=json.loads((root/'wflevels/triple_axis_tourbillon/actor-map.json').read_text())['indices']
path=root/'build-docker/tourbillon-captures'/output;path.parent.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
with path.with_suffix('.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/triple_axis_tourbillon-standalone.iff'),
        '--debug-port','17798','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',*args],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17798,timeout=90)
        for name,mb in (('OuterCage',3014),('MiddleCage',3014),('MiddleCage',3013),('InnerCage',3014),('InnerCage',3013),('InnerCage',3012),('HourHand',3013),('MinuteHand',3013),('SecondBead',3009),('SecondBead',3010)):
            c.watch(ids[name],mb)
        for name in ('cs_wide','LookAt'):
            for mb in (3009,3010,3011):c.watch(ids[name],mb)
        time.sleep(8);v=dict(c.mailbox_values)
        h,mi,s=map(float,re.match(r'(\d+):(\d+):(\d+(?:\.\d+)?)',stamp).groups())
        phase=model.phases(int(h),int(mi),s)
        for name,mb,key,sign in (('OuterCage',3014,'outer',1),('MiddleCage',3014,'outer',1),('MiddleCage',3013,'middle',1),('InnerCage',3014,'outer',1),('InnerCage',3013,'middle',1),('InnerCage',3012,'inner',1),('HourHand',3013,'hour',-1),('MinuteHand',3013,'minute',-1)):
            value=v[(ids[name],mb)];expected=sign*phase[key]
            assert abs((value-expected+.5)%1-.5)<.015,(name,value,expected)
        a=phase['outer']*math.tau
        assert math.dist((v[(ids['SecondBead'],3009)],v[(ids['SecondBead'],3010)]),(3*math.cos(a),3*math.sin(a)))<.04
        camera=model.CAMERA_STILL if '--property=TourbillonSettings.Camera drift=1' in args else model.camera_pose(s)
        for i,expected in enumerate(camera):
            name='cs_wide' if i<3 else 'LookAt'
            assert abs(v[(ids[name],3009+i%3)]-expected)<.04,(name,i,v,expected)
        c.send({'op':'screenshot','filename':str(path)})
        assert c.wait_for(lambda x:x.get('op')=='screenshot_done',timeout=30)
        print('verified',stamp,v,flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
