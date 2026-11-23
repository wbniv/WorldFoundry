"""Capture the real desktop engine and verify every train's track position."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

root = Path('/src')
sys.path[:0] = [str(root/'tests'), str(root/'wflevels/train_loops')]
from debug_bridge_client import BridgeClient
import model

stamp, output = sys.argv[1:3]
settings_ui = '--test-settings-ui' in sys.argv[3:]
rollover = '--test-rollover' in sys.argv[3:]
out = root/'build-docker/train-loops-captures'/output
out.parent.mkdir(parents=True, exist_ok=True)
spec = stamp if '@' in stamp else stamp+'@0'
env = dict(os.environ, WF_WALL_CLOCK=spec, WF_REST_PORT='0')
registry = json.loads((root/'wflevels/train_loops/actor-map.json').read_text())
idx = registry['indices']
args = [str(root/'build-docker/train-loops/src/engine/wf_game'),
        '-L'+str(root/'wflevels/train_loops-standalone.iff'), '-rate20',
        '--debug-port','17778','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps']
args.extend(a for a in sys.argv[3:] if a not in ('--test-settings-ui','--test-rollover'))
with out.with_suffix('.log').open('w') as log:
    proc=subprocess.Popen(args,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        client=BridgeClient(port=17778,timeout=120)
        for vehicle in registry['vehicles']:
            for mailbox in (3009,3010,3014):
                client.watch(idx[vehicle['name']],mailbox)
        for mailbox in (3009,3010,3011):
            client.watch(idx['cs_wide'],mailbox)
            client.watch(idx['LookAt'],mailbox)
        if rollover:
            time.sleep(1)
            before_rollover=client.mailbox_values[(idx['Express'],3009)]
            time.sleep(6)
            after_rollover=client.mailbox_values[(idx['Express'],3009)]
            print('express X across rollover:',before_rollover,after_rollover,flush=True)
            assert before_rollover < 0 < after_rollover, 'express did not pass twelve across rollover'
        else:
            time.sleep(8)
        observed=dict(client.mailbox_values)
        print('train positions:', observed, flush=True)
        # Frozen wall time makes the comparison exact; accelerated captures are
        # used separately to check continuous movement across a rollover.
        if spec.endswith('@0'):
            h,mi,s=map(float,re.match(r'(\d+):(\d+):(\d+(?:\.\d+)?)',stamp).groups())
            phases=model.phases(int(h),int(mi),s)
            for vehicle in registry['vehicles']:
                name,loop=vehicle['name'],vehicle['loop']
                phase=model.trailing_phase(phases[loop],vehicle['offset_radians'])
                x,y,angle=model.pose(model.RADII[loop],phase)
                actual=[observed[(idx[name],m)] for m in (3009,3010,3014)]
                assert abs(actual[0]-x)<.03 and abs(actual[1]-y)<.03, (name,actual,(x,y,angle))
                assert abs((actual[2]-angle+.5)%1-.5)<.01, (name,actual,angle)
            still = '--property=TrainLoopsSettings.Camera drift=1' in args
            camera = model.CAMERA_STILL if still else model.camera_pose(s)
            for component,expected in enumerate(camera):
                target = 'cs_wide' if component < 3 else 'LookAt'
                actual=observed[(idx[target],3009+component%3)]
                assert abs(actual-expected)<.03, (target,component,actual,expected)
        else:
            before=observed[(idx['Express'],3009)]
            time.sleep(2)
            after=client.mailbox_values[(idx['Express'],3009)]
            print('express X after two seconds:',after,flush=True)
            assert abs(after-before)>.01, 'express did not move'
        if settings_ui:
            client.inject_input('joystick1_raw',1,-1)
            time.sleep(2)
            client.inject_input('joystick1_raw',0,-1)
            time.sleep(1)
        client.send({'op':'screenshot','filename':str(out)})
        response=client.wait_for(lambda m:m.get('op') in ('screenshot_done','error'),timeout=60)
        assert response and response.get('op')=='screenshot_done',response
        client.close()
    finally:
        proc.terminate()
        proc.wait(timeout=30)
