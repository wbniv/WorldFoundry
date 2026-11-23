#!/usr/bin/env python3
"""Desktop evidence for the Discus tank: the real engine renders the level, the player swims, the group follows.

Run INSIDE the Linux test container, under Xvfb, with a container-built engine
(docs/plans/2026-11-22-discus-tank.md, Verification):

  scripts/in-linux-container.sh scripts/build-wf-game-container.sh
  scripts/in-linux-container.sh xvfb-run -a -s '-screen 0 1280x720x24' \\
      python3 docs/diagnostics/aquarium-discus-2026-11-22/capture.py

The engine runs paused and is stepped frame by frame through the debug bridge (-rate20), each
step confirmed by the Player's clock mailbox, so no wall-clock delay decides anything. VRAM
switches are the Aquarium app's own (wflevels/aquarium-wf_args.txt). Writes rest.png,
swim-right.png, group.png, engine.log and results.json beside this file. Desktop llvmpipe frames
show that the level loads and animates; they are not device performance.
"""
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
from debug_bridge_client import BridgeClient  # noqa: E402

FRAME = 3276 / 65536          # simulated seconds per frame at -rate20
CLOCK = 1906                  # the Player's elapsed-time mailbox
POS = (3009, 3010, 3011)
RIGHT = 8192                  # JOYSTICK_BUTTON_RIGHT
LEVEL = 'aquarium_discus'


def main():
    engine = ROOT / 'build-docker/wf-game/src/engine/wf_game'
    if not engine.is_file():
        sys.exit(f'no engine at {engine}; build it with scripts/build-wf-game-container.sh')
    mapping = json.loads((ROOT / f'wflevels/{LEVEL}/actor-map.json').read_text())
    idx = mapping['indices']
    player = idx['Player']
    fish = ['discus-player'] + [f'discus-{k}' for k in range(1, mapping['fish_count'])]
    vram = [line.strip() for line in (ROOT / 'wflevels/aquarium-wf_args.txt').read_text().splitlines() if line.strip()]
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    env = dict(os.environ, WF_REST_HOST='127.0.0.1', WF_REST_PORT='0')
    log = (OUT / 'engine.log').open('w')
    proc = subprocess.Popen([str(engine), '-L' + str(ROOT / f'wflevels/{LEVEL}-standalone.iff'), '-rate20',
                             '--debug-port', str(port), '--debug-bind', '127.0.0.1', '-width=1280', '-height=720', *vram],
                            cwd=ROOT / f'wflevels/{LEVEL}', env=env, stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    cli = None
    results = {'level': LEVEL, 'engine_args': vram, 'shots': {}}
    try:
        cli = BridgeClient(port=port, timeout=300)   # a level load under llvmpipe can take a minute
        cli.send({'op': 'pause'})
        cli.inject_input('joystick1_raw', 0, duration_frames=-1)
        cli.watch(player, CLOCK)
        for name in fish:
            for box in POS:
                cli.watch(idx[name], box)

        def value(actor, box):
            with cli._lock:
                return cli.mailbox_values.get((actor, box), 0.0)

        def step(n):
            start = value(player, CLOCK)
            cli.send({'op': 'step', 'frames': n})
            deadline = time.monotonic() + 120   # failure guard only
            while value(player, CLOCK) < start + n * FRAME - .0002:
                if proc.poll() is not None:
                    raise RuntimeError('engine exited')
                if time.monotonic() > deadline:
                    raise RuntimeError('frame stepping timed out')
                time.sleep(.005)

        def positions():
            return {name: [round(value(idx[name], b), 3) for b in POS] for name in fish}

        def shot(name):
            path = OUT / f'{name}.png'
            cli.send({'op': 'screenshot', 'filename': str(path)})
            msg = cli.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=60)
            assert msg and msg.get('op') == 'screenshot_done', msg
            results['shots'][name] = {'clock_s': round(value(player, CLOCK), 3), 'fish': positions()}

        step(40); shot('rest')
        cli.inject_input('joystick1_raw', RIGHT, duration_frames=-1)
        step(40); shot('swim-right')
        cli.inject_input('joystick1_raw', 0, duration_frames=-1)
        step(80); shot('group')
    finally:
        if cli:
            cli.close()
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=30)
        log.close()
    rest, right = results['shots']['rest']['fish'], results['shots']['swim-right']['fish']
    results['player_dx_while_right_held'] = round(right['discus-player'][0] - rest['discus-player'][0], 3)
    results['residents_moved'] = sum(1 for n in fish[1:] if right[n] != rest[n])
    (OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({k: v for k, v in results.items() if k != 'shots'}, indent=2))
    if results['player_dx_while_right_held'] <= 0.5 or results['residents_moved'] < len(fish) - 1:
        sys.exit('the player did not swim right, or a resident never moved')


if __name__ == '__main__':
    main()
