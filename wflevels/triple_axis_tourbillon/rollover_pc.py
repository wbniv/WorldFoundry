"""Watch the three real engine cage phases across a six-minute boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient

idx=json.loads((root/'wflevels/triple_axis_tourbillon/actor-map.json').read_text())['indices']
env=dict(os.environ,WF_WALL_CLOCK='11:59:55@1',WF_REST_PORT='0')
with (root/'build-docker/tourbillon-captures/rollover.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/triple_axis_tourbillon-standalone.iff'),
        '--debug-port','17798','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps'],
        env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17798,timeout=60)
        watches=[(idx['OuterCage'],3014),(idx['MiddleCage'],3013),(idx['InnerCage'],3012)]
        for a,b in watches:c.watch(a,b)
        samples=[]
        for _ in range(30):
            time.sleep(.5);v=dict(c.mailbox_values)
            if all(key in v for key in watches): samples.append(tuple(v[key] for key in watches))
        print('cage phase samples:',samples,flush=True)
        assert any(all(x>.9 for x in row) for row in samples),samples
        assert any(all(x<.1 for x in row) for row in samples),samples
        assert p.poll() is None,'engine exited during rollover'
        c.close()
    finally:
        if p.poll() is None:p.terminate()
        p.wait(timeout=30)
