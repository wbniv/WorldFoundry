"""Observe a live minute rollover in the real PC engine."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path('/src')
sys.path.insert(0, str(root/'tests'))
from debug_bridge_client import BridgeClient

ids = json.loads((root/'wflevels/lava_lamp_digits/actor-map.json').read_text())['indices']
env = dict(os.environ, WF_WALL_CLOCK='09:59:54@1', WF_REST_PORT='0')
log_path = root/'build-docker/lava-lamp-captures/live-rollover.log'
with log_path.open('w') as log:
    p = subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/lava_lamp_digits-standalone.iff'),
        '--debug-port', '17798', '--debug-bind', '127.0.0.1', '-width=1280', '-height=720', '--no-fps'],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        c = BridgeClient(port=17798, timeout=45)
        watched = [(ids['Segment1_a'], 3011), (ids['Blob0'], 3011), (ids['cs_wide'], 3009)]
        for actor, mailbox in watched:
            c.watch(actor, mailbox)
        samples = []
        end = time.monotonic()+15
        while time.monotonic() < end:
            time.sleep(.1)
            values = dict(c.mailbox_values)
            if all(key in values for key in watched):
                samples.append(tuple(values[key] for key in watched))
        assert p.poll() is None, 'level exited during rollover'
        assert samples, 'no bridge samples'
        for i, minimum_span in enumerate((30, 10, 2)):
            span = max(row[i] for row in samples)-min(row[i] for row in samples)
            assert span > minimum_span, (i, span, samples)
        print('PASS live rollover, wax stroke, blob and camera move:', len(samples), 'samples', flush=True)
        c.close()
    finally:
        if p.poll() is None:
            p.terminate()
        p.wait(timeout=30)
