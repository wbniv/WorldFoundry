"""Observe the beam and boat passing a live noon boundary in the PC engine."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path('/src')
sys.path.insert(0,str(root/'tests'))
from debug_bridge_client import BridgeClient

ids = json.loads((root/'wflevels/lighthouse/actor-map.json').read_text())['indices']
env = dict(os.environ,WF_WALL_CLOCK='11:59:54@1',WF_REST_PORT='0')
log_path = root/'build-docker/lighthouse-captures/rollover.log'
with log_path.open('w') as log:
    p = subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/lighthouse-standalone.iff'), '--debug-port','17798',
        '--debug-bind','127.0.0.1','-width=1280','-height=720','--no-fps',
        '--vram-width=2048','--vram-height=1024','--vram-slot-width=1024','--vram-slot-height=512'],
        env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        c = BridgeClient(port=17798,timeout=60)
        watches = [(ids['Beam'],3014),(ids['Boat'],3009),(ids['Boat'],3010),(ids['Glint0'],3009)]
        for actor,mailbox in watches: c.watch(actor,mailbox)
        samples=[]
        end=time.monotonic()+15
        while time.monotonic()<end:
            time.sleep(.1)
            v=dict(c.mailbox_values)
            if all(key in v for key in watches): samples.append(tuple(v[key] for key in watches))
        assert p.poll() is None and samples, 'engine stopped or returned no samples'
        phases=[row[0]%1 for row in samples]
        assert min(phases)<.02 and max(phases)>.98, (min(phases),max(phases))
        assert max(row[1] for row in samples)-min(row[1] for row in samples)>.1, samples
        glints = [row[3] for row in samples]
        assert max(glints)-min(glints)>.1, samples
        assert max(abs(b-a) for a,b in zip(glints,glints[1:]))<.2, samples
        print('PASS live noon rollover and continuous water glint:',len(samples),'samples',flush=True)
        c.close()
    finally:
        if p.poll() is None: p.terminate()
        p.wait(timeout=30)
