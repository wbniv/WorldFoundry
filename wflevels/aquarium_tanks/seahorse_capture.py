#!/usr/bin/env python3
"""Desktop evidence for the seahorse asset (Phase 2): the saltwater planted tank,
wide and close, with the twelve seahorses animating their clips.

Runs the Release wf_game with the aquarium app's VRAM flags on an isolated debug
port, steps the simulation at a fixed 20 Hz, and takes bridge screenshots: a
wide sequence, then a close sequence with the urchin (the close camera's
subject) moved under each pair. It also records every seahorse's DFRM status
and tail-tip outputs (block + 36..39) per shot, so the JSON shows the poses
change. Starts Xvfb when no DISPLAY is set (the Linux test image).

    scripts/in-linux-container.sh python3 wflevels/aquarium_tanks/seahorse_capture.py \\
        --out docs/plans/2026-10-16-saltwater-seahorses/evidence/phase2
"""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'scripts'))
from debug_bridge_client import BridgeClient  # noqa: E402
from plant_settings_catalog import configure_level  # noqa: E402

VRAM = ['--vram-width=2048', '--vram-height=1024', '--vram-slot-width=512', '--vram-slot-height=512',
        '--vram-perm-width=1024', '--vram-perm-height=1024']   # android/app/src/aquarium/assets/wf_args.txt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--game', type=Path, default=ROOT / 'engine/wf_game')
    ap.add_argument('--port', type=int, default=17946)
    ap.add_argument('--settle', type=int, default=40, help='frames before the first shot')
    ap.add_argument('--shots', type=int, default=4, help='shots per view')
    ap.add_argument('--gap', type=int, default=8, help='frames between shots (20 Hz)')
    ap.add_argument('--seed', type=int, default=713)
    ap.add_argument('--age', type=float, default=150, help='plant age (the Phase 4 protocol: seed 713, age 150)')
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    here = ROOT / 'wflevels/aquarium_plants'
    mapping = json.loads((here / 'actor-map.json').read_text())
    idx, mb, sea = mapping['indices'], mapping['mailboxes'], mapping['seahorses']
    player, director = idx['Player'], idx['Director']
    # Saltwater, six visible pairs, mature plants, growth paused.
    level = out / 'configured-level.iff'
    data, receipt = configure_level((ROOT / 'wflevels/aquarium_plants-standalone.iff').read_bytes(),
                                    dict(seed=args.seed, water='saltwater', age=args.age, speed=0))
    level.write_bytes(data)
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(ROOT / 'engine/libs') + ':' + env.get('LD_LIBRARY_PATH', '')
    env.update(WF_REST_HOST='127.0.0.1', WF_REST_PORT=str(args.port + 1000))
    xvfb = None
    if not env.get('DISPLAY'):
        xvfb = subprocess.Popen(['Xvfb', ':79', '-screen', '0', '1280x960x24'], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        env['DISPLAY'] = ':79'
        time.sleep(1.0)
    log = (out / 'runtime.log').open('w')
    proc = subprocess.Popen([str(args.game), '-L' + str(level), *VRAM,
                             '-width=1280', '-height=720', '-rate20', '--debug-port', str(args.port),
                             '--debug-bind', '127.0.0.1'],
                            cwd=here, env=env, stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    cli = None
    results = {'level': 'aquarium_plants', 'settings': receipt['settings'], 'vram': VRAM, 'shots': [],
               'seahorses': sea['actors']}
    try:
        cli = BridgeClient(port=args.port, timeout=30)
        cli.send({'op': 'pause'})
        cli.inject_input('joystick1_raw', 0, duration_frames=-1)
        cli.watch(idx=player, mailbox=1906)
        for a in sea['actors']:
            for k in range(36, 40):
                cli.watch(idx=director, mailbox=a['block'] + k)
        cli.watch(idx=director, mailbox=mb['camera'])

        def value(a, m):
            with cli._lock:
                return cli.mailbox_values.get((a, m), 0.0)

        def step(n):
            start = value(player, 1906)
            cli.send({'op': 'step', 'frames': n})
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if value(player, 1906) >= start + n * (3276 / 65536) - .0002:
                    time.sleep(.05)
                    return
                if proc.poll() is not None:
                    raise RuntimeError('engine exited; see runtime.log')
                time.sleep(.005)
            raise RuntimeError('step timed out')

        def shot(name):
            path = out / (name + '.png')
            cli.send({'op': 'screenshot', 'filename': str(path)})
            msg = cli.wait_for(lambda m: m.get('op') in ('screenshot_done', 'error'), timeout=20)
            assert msg and msg.get('op') == 'screenshot_done', msg
            state = {'shot': name, 'time': round(value(player, 1906), 3), 'seahorses': []}
            for a in sea['actors']:
                state['seahorses'].append({'seahorse': a['seahorse'], 'status': value(director, a['block'] + 39),
                                           'tip': [round(value(director, a['block'] + k), 4) for k in (36, 37, 38)]})
            results['shots'].append(state)

        time.sleep(.3)
        step(args.settle)
        for k in range(args.shots):
            shot(f'wide-{k}')
            step(args.gap)
        # Close: the Director drives only the urchin's close camera, so keep the wide view and
        # move its camshot (cs_wide) and target (LookAt) to each pair instead.
        for pair, s in enumerate(range(0, len(sea['actors']), 2)):
            a, b = sea['actors'][s]['position'], sea['actors'][s + 1]['position']
            x, y, z = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2 - .45
            cam_x = x - .5 * (1 if x > 0 else -1)             # off-centre, away from the end glass
            for actor, pos in ((idx['LookAt'], (x, y, z)), (idx['cs_wide'], (cam_x, y - 3.6, z + .35))):
                for m, v in zip((3009, 3010, 3011), pos):
                    cli.set_mailbox(m, v, idx=actor)
            step(80)                  # the elastic camera settles
            for k in range(args.shots):
                shot(f'close-pair{pair}-{k}')
                step(args.gap)
        results['status'] = 'captured'
    finally:
        if cli:
            cli.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log.close()
        if xvfb:
            xvfb.terminate()
    text = (out / 'runtime.log').read_text(errors='replace')
    results['forth_errors'] = sum(text.count(s) for s in ('zforth compile error', 'zforth eval error', 'Unknown'))
    results['dfrm_load_failures'] = text.count('DFRM')
    level.unlink()
    (out / 'capture.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({'shots': len(results['shots']), 'forth_errors': results['forth_errors']}))


if __name__ == '__main__':
    main()
