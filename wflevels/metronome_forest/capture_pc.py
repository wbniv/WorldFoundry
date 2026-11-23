"""Verify representative real-engine metronome positions and capture a frame."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

root=Path('/src');sys.path[:0]=[str(root/'tests'),str(root/'wflevels/metronome_forest')]
from debug_bridge_client import BridgeClient
import model

stamp,output=sys.argv[1:3];args=sys.argv[3:]
ids=json.loads((root/'wflevels/metronome_forest/actor-map.json').read_text())['indices']
path=root/'build-docker/metronome-forest-captures'/output;path.parent.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
with path.with_suffix('.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/metronome_forest-standalone.iff'),
        '--debug-port','17799','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',*args],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17799,timeout=90)
        for i in (0,7,25,59):
            for kind in ('Green','Plain'):c.watch(ids[kind+str(i)],3013)
        for name in ('cs_wide','LookAt'):
            for mb in (3009,3010,3011):c.watch(ids[name],mb)
        time.sleep(8);v=dict(c.mailbox_values)
        h,mi,s=map(float,re.match(r'(\d+):(\d+):(\d+(?:\.\d+)?)',stamp).groups())
        for i in (0,7,25,59):
            for kind in ('Green','Plain'):
                actual=v[(ids[kind+str(i)],3013)];expected=model.arm_angle(i,s)
                assert abs((actual-expected+.5)%1-.5)<.015,(kind,i,actual,expected)
        camera=model.CAMERA_STILL if '--property=MetronomeForestSettings.Camera drift=1' in args else model.camera_pose(s)
        for i,expected in enumerate(camera):
            name='cs_wide' if i<3 else 'LookAt'
            assert abs(v[(ids[name],3009+i%3)]-expected)<.05,(name,i,v,expected)
        c.send({'op':'screenshot','filename':str(path)})
        assert c.wait_for(lambda m:m.get('op')=='screenshot_done',timeout=30)
        print('verified',stamp,v,flush=True);c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
