"""Run the desktop engine at a fixed time, verify actors, capture a frame."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

root=Path('/src')
sys.path[:0]=[str(root/'tests'),str(root/'wflevels/bamboo_tipper_pond')]
from debug_bridge_client import BridgeClient
import model

stamp, output = sys.argv[1:3]
args=sys.argv[3:]
pond_ui='--test-pond-ui' in args
settings_ui='--test-settings-ui' in args or pond_ui
args=[a for a in args if a not in ('--test-settings-ui','--test-pond-ui')]
idx=json.loads((root/'wflevels/bamboo_tipper_pond/actor-map.json').read_text())['indices']
path=root/'build-docker/bamboo-pond-captures'/output;path.parent.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
with path.with_suffix('.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/bamboo-pond/src/engine/wf_game'),
        '-L'+str(root/'wflevels/bamboo_tipper_pond-standalone.iff'),
        '--debug-port','17797','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',*args],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17797,timeout=60)
        for name in ('FloatingLantern','Koi'):
            for mb in (3009,3010): c.watch(idx[name],mb)
        c.watch(idx['Tipper'],3013);c.watch(idx['TubeWater'],3011)
        for name in ('cs_wide','LookAt'):
            for mb in (3009,3010,3011): c.watch(idx[name],mb)
        c.watch(idx['Koi'],3040);c.watch(idx['PondWater'],3014)
        time.sleep(8)
        values=dict(c.mailbox_values)
        h,mi,s=map(float,re.match(r'(\d+):(\d+):(\d+(?:\.\d+)?)',stamp).groups())
        for name,radius,phase in zip(('FloatingLantern','Koi'),(3.55,2.85),model.phases(int(h),int(mi),s)):
            expected=model.orbit(radius,phase)
            actual=tuple(values[(idx[name],m)] for m in (3009,3010))
            assert math.dist(expected,actual)<.04,(name,actual,expected)
        tip=values[(idx['Tipper'],3013)]
        assert abs((tip-model.tip_angle(s)+.5)%1-.5)<.015,(tip,model.tip_angle(s))
        water=values[(idx['TubeWater'],3011)]
        assert abs(water-(1.39+model.fill(s)*.12))<.02,(water,model.fill(s))
        camera=model.CAMERA_STILL if '--property=BambooPondSettings.Camera drift=1' in args else model.camera_pose(s)
        for i,expected in enumerate(camera):
            target='cs_wide' if i<3 else 'LookAt'
            actual=values[(idx[target],3009+i%3)]
            assert abs(actual-expected)<.04,(target,i,actual,expected)
        if '--property=BambooPondSettings.Water motion=0' in args:
            assert abs(values[(idx['PondWater'],3014)])<.01
        for option,expected in (('0',.75),('1',1.),('2',1.35)):
            if '--property=BambooPondSettings.Koi size='+option in args:
                assert abs(values[(idx['Koi'],3040)]-expected)<.02,values
        if settings_ui:
            c.inject_input('joystick1_raw',1,-1);time.sleep(2)
            c.inject_input('joystick1_raw',0,-1);time.sleep(1)
        if pond_ui:
            for key in (16384,4096):
                c.inject_input('joystick1_raw',key,-1);time.sleep(.25)
                c.inject_input('joystick1_raw',0,-1);time.sleep(.4)
        c.send({'op':'screenshot','filename':str(path)})
        assert c.wait_for(lambda m:m.get('op')=='screenshot_done',timeout=30)
        print('verified',stamp,values,flush=True)
        c.close()
    finally:
        p.terminate();p.wait(timeout=30)
