"""Capture a frozen wall-clock view through the real desktop engine."""
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path('/src')
sys.path.insert(0, str(root/'tests'))
from debug_bridge_client import BridgeClient

stamp = sys.argv[1]
out = root/'build-docker/quick-test'/sys.argv[2]
env = dict(os.environ, WF_WALL_CLOCK=stamp if '@' in stamp else stamp+'@0', WF_REST_PORT='0')
log = out.with_suffix('.log').open('w')
args = [str(root/'build-docker/wf-game/src/engine/wf_game'),
                      '-L'+str(root/'wflevels/anamorphic_shards-standalone.iff'),
                      '-rate20', '--debug-port', '17777', '--debug-bind', '127.0.0.1',
                      '-width=1280', '-height=720', '--no-fps']
if len(sys.argv) > 4:
    args.append(sys.argv[4])
p = subprocess.Popen(args, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
try:
    cli = BridgeClient(port=17777, timeout=120)
    for idx in (5, 6, 7, 12, 54, 66):
        cli.watch(idx, 3009)
    time.sleep(float(sys.argv[3]) if len(sys.argv) > 3 else 5)
    print('actor positions', cli.mailbox_values, flush=True)
    cli.send({'op':'screenshot', 'filename':str(out)})
    result = cli.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=60)
    assert result and result.get('op') == 'screenshot_done', result
    if len(sys.argv) > 5:
        time.sleep(float(sys.argv[5]))
        cli.send({'op':'screenshot', 'filename':str(out.with_name(out.stem + '-later.png'))})
        result = cli.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=60)
        assert result and result.get('op') == 'screenshot_done', result
    cli.close()
finally:
    p.terminate()
    p.wait(timeout=30)
    log.close()
