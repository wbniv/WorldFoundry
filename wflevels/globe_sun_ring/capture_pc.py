"""Capture a selected local wall-clock time through the desktop engine."""
import os
import json
from pathlib import Path
import subprocess
import sys
import time

root = Path('/src')
sys.path.insert(0, str(root / 'tests'))
from debug_bridge_client import BridgeClient

stamp, output = sys.argv[1:3]
out = root / 'build-docker/globe-sun-ring-captures' / output
out.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, WF_WALL_CLOCK=stamp if '@' in stamp else stamp + '@0', WF_REST_PORT='0')
with out.with_suffix('.log').open('w') as log:
    args = [str(root/'build-docker/globe-sun-ring/src/engine/wf_game'),
        '-L'+str(root/'wflevels/globe_sun_ring-standalone.iff'), '-rate20',
        '--debug-port', '17777', '--debug-bind', '127.0.0.1', '-width=1280', '-height=720', '--no-fps',
        '--vram-slot-width=1024', '--vram-slot-height=512']
    settings_ui = '--test-settings-ui' in sys.argv[3:]
    args.extend(arg for arg in sys.argv[3:] if arg != '--test-settings-ui')
    proc = subprocess.Popen(args, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        client = BridgeClient(port=17777, timeout=120)
        actor_map = json.loads((root / 'wflevels/globe_sun_ring/actor-map.json').read_text())['indices']
        client.watch(actor_map['Director'], 650)
        client.watch(actor_map['Earth'], 3014)
        client.watch(actor_map['cs_wide'], 3009)
        client.watch(actor_map['Director'], 700)  # Bangkok city lights
        time.sleep(8)
        print('home longitude in turns and Earth rotation:', client.mailbox_values, flush=True)
        if '@' in stamp and not stamp.endswith('@0'):
            before = client.mailbox_values[(actor_map['Earth'], 3014)]
            time.sleep(2)
            after = client.mailbox_values[(actor_map['Earth'], 3014)]
            print('Earth rotation after two seconds:', after, flush=True)
            assert abs(after-before) > .0001, 'the globe did not advance with the clock'
        if settings_ui:
            client.inject_input('joystick1_raw', 1, -1)
            time.sleep(2)
            client.inject_input('joystick1_raw', 0, -1)
            time.sleep(1)
        client.send({'op':'screenshot', 'filename':str(out)})
        response = client.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=60)
        assert response and response.get('op') == 'screenshot_done', response
        client.close()
    finally:
        proc.terminate()
        proc.wait(timeout=30)
