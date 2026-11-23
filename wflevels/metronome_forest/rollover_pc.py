"""Observe real-engine pendulums through a running minute boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path('/src')
sys.path.insert(0, str(root / 'tests'))
from debug_bridge_client import BridgeClient

ids = json.loads((root / 'wflevels/metronome_forest/actor-map.json').read_text())['indices']
env = dict(os.environ, WF_WALL_CLOCK='11:59:50@1', WF_REST_PORT='0')
log_path = root / 'build-docker/metronome-forest-captures/rollover.log'
with log_path.open('w') as log:
    p = subprocess.Popen([str(root / 'build-docker/tourbillon/src/engine/wf_game'),
        '-L' + str(root / 'wflevels/metronome_forest-standalone.iff'),
        '--debug-port', '17798', '--debug-bind', '127.0.0.1',
        '-width=1280', '-height=720', '--no-fps'], env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        c = BridgeClient(port=17798, timeout=60)
        watches = [(ids['Plain0'], 3013), (ids['Plain59'], 3013)]
        for actor, mailbox in watches:
            c.watch(actor, mailbox)
        samples = []
        end = time.monotonic() + 15
        while time.monotonic() < end:
            time.sleep(.05)
            values = dict(c.mailbox_values)
            if all(key in values for key in watches):
                samples.append(tuple((values[key] + .5) % 1 - .5 for key in watches))
        assert p.poll() is None, 'engine exited during rollover'
        assert samples and all(max(row[i] for row in samples) - min(row[i] for row in samples) > .05 for i in range(2)), samples
        assert any(max(abs(v) for v in row) < .025 for row in samples), samples
        print('live rollover: watched both pendulums move and converge; samples:', len(samples), flush=True)
        c.close()
    finally:
        if p.poll() is None:
            p.terminate()
        p.wait(timeout=30)
