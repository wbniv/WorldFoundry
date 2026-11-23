"""Run the standalone clock at a fixed local time and capture an engine frame."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path('/src')
sys.path[:0] = [str(root/'tests'), str(root/'wflevels/lava_lamp_digits')]
from debug_bridge_client import BridgeClient
import model

stamp, filename = sys.argv[1:3]
out = root/'build-docker/lava-lamp-captures'/filename
out.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, WF_WALL_CLOCK=stamp+'@0', WF_REST_PORT='0')
with out.with_suffix('.log').open('w') as log:
    p = subprocess.Popen([str(root/'build-docker/tourbillon/src/engine/wf_game'),
        '-L'+str(root/'wflevels/lava_lamp_digits-standalone.iff'), '--debug-port', '17798',
        '--debug-bind', '127.0.0.1', '-width=1280', '-height=720', '--no-fps', *sys.argv[3:]],
        env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        c = BridgeClient(port=17798, timeout=45)
        ids = json.loads((root/'wflevels/lava_lamp_digits/actor-map.json').read_text())['indices']
        watched = [(ids['cs_wide'], axis) for axis in (3009, 3010, 3011)]
        watched.append((ids['Blob0'], 3011))
        for actor, mailbox in watched:
            c.watch(actor, mailbox)
        time.sleep(8)
        assert p.poll() is None, 'level exited before capture'
        second = float(stamp.split(':')[2])
        still = '--property=LavaLampDigitsSettings.Camera drift=1' in sys.argv
        expected = (0., -8.5*48, 4.6*48) if still else model.camera(second)
        values = dict(c.mailbox_values)
        for i, axis in enumerate((3009, 3010, 3011)):
            assert abs(values[(ids['cs_wide'], axis)]-expected[i]) < .08, (values, expected)
        assert abs(values[(ids['Blob0'], 3011)] - (model.rise(0, second)*1.65+.48)*48) < .08, values
        c.send({'op':'screenshot', 'filename':str(out)})
        assert c.wait_for(lambda m:m.get('op')=='screenshot_done', timeout=30)
        print('captured', stamp, out, flush=True)
        c.close()
    finally:
        if p.poll() is None:
            p.terminate()
        p.wait(timeout=30)
