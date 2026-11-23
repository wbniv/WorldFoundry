"""Exercise the real engine across a minute boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root=Path('/src');sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient

idx=json.loads((root/'wflevels/bamboo_tipper_pond/actor-map.json').read_text())['indices']
env=dict(os.environ,WF_WALL_CLOCK='11:59:55@1',WF_REST_PORT='0')
with (root/'build-docker/bamboo-pond-captures/rollover.log').open('w') as log:
    p=subprocess.Popen([str(root/'build-docker/bamboo-pond/src/engine/wf_game'),
        '-L'+str(root/'wflevels/bamboo_tipper_pond-standalone.iff'),
        '--debug-port','17797','--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps'],
        env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c=BridgeClient(port=17797,timeout=60)
        c.watch(idx['Tipper'],3013);c.watch(idx['TubeWater'],3011)
        samples=[]
        for _ in range(30):
            time.sleep(.5);v=dict(c.mailbox_values)
            if (idx['Tipper'],3013) in v and (idx['TubeWater'],3011) in v:
                samples.append((v[(idx['Tipper'],3013)],v[(idx['TubeWater'],3011)]))
        print('tip and water samples:',samples,flush=True)
        assert any(.07<tip<.13 for tip,water in samples),samples
        assert any(water<1.405 for tip,water in samples),samples
        assert p.poll() is None,'engine exited during rollover'
        c.close()
    finally:
        if p.poll() is None: p.terminate()
        p.wait(timeout=30)
