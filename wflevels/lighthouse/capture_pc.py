"""Run a fixed local-time frame and verify real-engine lighthouse motion."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path('/src')
sys.path[:0] = [str(root/'tests'),str(root/'wflevels/lighthouse')]
from debug_bridge_client import BridgeClient
import model

stamp, filename = sys.argv[1:3]
hours, minutes, seconds = map(float,stamp.split(':'))
out = root/'build-docker/lighthouse-captures'/filename
out.parent.mkdir(parents=True,exist_ok=True)
ids = json.loads((root/'wflevels/lighthouse/actor-map.json').read_text())['indices']
env = dict(os.environ,WF_WALL_CLOCK=stamp+'@0',WF_REST_PORT='0')
with out.with_suffix('.log').open('w') as log:
    p = subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/lighthouse-standalone.iff'), '--debug-port','17798',
        '--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',
        '--vram-width=2048','--vram-height=1024','--vram-slot-width=1024','--vram-slot-height=512',*sys.argv[3:]],
        env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c = BridgeClient(port=17798,timeout=60)
        watched = [(ids['Beam'],3014),(ids['Boat'],3009),(ids['Boat'],3010),(ids['Boat'],3014),(ids['Sea'],3012),
                   (ids['Wake'],3009),(ids['Wake'],3010),(ids['Wake'],3014)]
        watched += [(ids[name],axis) for name in ('cs_wide','LookAt') for axis in (3009,3010,3011)]
        for actor,mailbox in watched: c.watch(actor,mailbox)
        time.sleep(8)
        assert p.poll() is None,'level exited before capture'
        v = dict(c.mailbox_values)
        boat,beam = model.phases(minutes,seconds)
        bx,by = model.point(model.BOAT_RADIUS*2,boat)
        assert abs((v[(ids['Beam'],3014)]+beam+.5)%1-.5) < .01, v
        assert abs((v[(ids['Boat'],3014)]+boat+.5)%1-.5) < .01, v
        assert abs(v[(ids['Boat'],3009)]-bx)<.05 and abs(v[(ids['Boat'],3010)]-by)<.05, v
        assert abs(v[(ids['Wake'],3009)]-bx)<.05 and abs(v[(ids['Wake'],3010)]-by)<.05, v
        assert abs((v[(ids['Wake'],3014)]+boat+.5)%1-.5) < .01, v
        assert abs((v[(ids['Sea'],3012)]-.25+.5)%1-.5) < .01, v
        still = '--property=LighthouseSettings.Camera drift=1' in sys.argv
        camera = tuple(2*v for v in (model.CAMERA_STILL if still else model.camera_pose(seconds)))
        for i,expected in enumerate(camera):
            name='cs_wide' if i<3 else 'LookAt'
            assert abs(v[(ids[name],3009+i%3)]-expected)<.05,(name,i,v,expected)
        c.send({'op':'screenshot','filename':str(out)})
        assert c.wait_for(lambda msg:msg.get('op')=='screenshot_done',timeout=30)
        print('PASS',stamp,'boat',bx,by,'beam',beam,'camera',camera,flush=True)
        c.close()
    finally:
        if p.poll() is None: p.terminate()
        p.wait(timeout=30)
