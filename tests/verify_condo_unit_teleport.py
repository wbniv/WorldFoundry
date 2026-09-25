#!/usr/bin/env python3
"""Exercise C / keyboard 3 apartment switching in the actual condo engine.

Run after ``task condo-level``: python3 tests/verify_condo_unit_teleport.py
Uses a separate debug port, captures both units, and checks reload defaults.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import subprocess
import time

from debug_bridge_client import BridgeClient

REPO = Path(__file__).resolve().parent.parent
WORK = Path('/tmp/condo-unit-teleport')
SHOTS = REPO / 'docs/plans/2026-09-25-condo-unit-teleport'
PORT = int(os.environ.get('WF_BRIDGE_PORT', '7797'))
POS = (3009, 3010, 3011)
SPEED = (3018, 3019, 3020)
CURRENT, LATCH = 81, 82
SAVED = {639: (83, 84, 85), 640: (86, 87, 88)}
C, UP = 1 << 2, 1 << 11
failures = []


def check(name, ok, detail=''):
    print(f'{"PASS" if ok else "FAIL"}: {name} {detail}', flush=True)
    if not ok:
        failures.append(name)


def value(cli, idx, mb):
    with cli._lock:
        return cli.mailbox_values.get((idx, mb))


def values(cli, idx, mbs):
    return tuple(value(cli, idx, mb) for mb in mbs)


def wait(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.025)
    return False


def near(a, b, tol=0.08):
    return all(x is not None and abs(x-y) < tol for x, y in zip(a, b))


def release(cli):
    cli.inject_input('joystick1_raw', 0, duration_frames=-1)
    assert wait(lambda: value(cli, 1, LATCH) == 0), 'C latch did not release'


def switch(cli, dest):
    release(cli)
    cli.inject_input('joystick1_raw', C, duration_frames=-1)
    assert wait(lambda: value(cli, 1, CURRENT) == dest), f'did not switch to {dest}'
    release(cli)
    time.sleep(0.25)


def walk(cli, player):
    start = value(cli, player, POS[1])
    cli.inject_input('joystick1_raw', UP, duration_frames=-1)
    assert wait(lambda: value(cli, player, POS[1]) > start + 0.65), 'walking did not advance'
    release(cli)
    assert wait(lambda: abs(value(cli, player, SPEED[1]) or 0) < 0.03), 'did not stop'
    return values(cli, player, POS)


def place(cli, player, pos):
    cli.send({'op': 'scene:set_transform', 'idx': player, 'pos': list(pos)})
    assert wait(lambda: near(values(cli, player, POS)[:2], pos[:2])), f'did not reach {pos}'
    time.sleep(0.3)


def screenshot(cli, name):
    cli.send({'op': 'screenshot', 'filename': str(SHOTS / name)})
    assert cli.wait_for(lambda m: m.get('op') == 'screenshot_done', timeout=8), 'capture failed'


@contextmanager
def game(label):
    WORK.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(REPO / 'engine/libs')
    env.setdefault('DISPLAY', ':0')
    env['vblank_mode'] = '0'
    env['__GL_SYNC_TO_VBLANK'] = '0'
    env['LSAN_OPTIONS'] = 'detect_leaks=0'
    log = WORK / f'{label}.log'
    cli = None
    with log.open('w') as out:
        proc = subprocess.Popen([
            str(REPO/'engine/wf_game'),
            f'-L{REPO}/wflevels/{os.environ.get("CONDO_TEST_LEVEL", "condo_639_640")}-standalone.iff',
            '--vram-width=4096', '--vram-height=2048',
            '--vram-slot-width=1024', '--vram-slot-height=1024',
            '--vram-perm-width=1024', '--vram-perm-height=1024',
            '--debug-port', str(PORT), '--debug-bind', '127.0.0.1', '--debug-print-actors',
        ], cwd=REPO/'wfsource/source/game', env=env, stdout=out, stderr=subprocess.STDOUT)
        try:
            cli = BridgeClient(port=PORT, timeout=15)
            assert wait(lambda: re.search(r'actor idx=(\d+) mesh=player\.iff', log.read_text(errors='replace')))
            player = int(re.search(r'actor idx=(\d+) mesh=player\.iff', log.read_text()).group(1))
            for mb in (*POS, *SPEED):
                cli.watch(player, mb)
            for mb in (CURRENT, LATCH, *SAVED[639], *SAVED[640], 93):
                cli.watch(1, mb)
            assert wait(lambda: all(value(cli, player, mb) is not None for mb in (*POS, *SPEED)))
            assert wait(lambda: value(cli, 1, SAVED[640][2]) is not None)
            time.sleep(0.35)
            yield cli, player
            check(f'{label} script health', proc.poll() is None and not re.search(
                r'assertion.*failed|assert.*failed|FATAL|zforth.*error', log.read_text(), re.I))
        finally:
            if cli:
                cli.close()
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=4)


if __name__ == '__main__':
    with game('switch') as (cli, player):
        start = values(cli, player, POS)
        check('639 starts inside front doors', near(start[:2], (4.65625, -14.5)), str(start))
        check('unvisited 640 seeded inside front doors', near(values(cli, 1, SAVED[640]), (-3.875, -14.5, 16.05)))
        screenshot(cli, '639.png')
        cli.inject_input('joystick1_raw', C, duration_frames=-1)
        assert wait(lambda: value(cli, 1, CURRENT) == 640), 'initial C press failed'
        time.sleep(0.6)
        check('held C switches once to 640', value(cli, 1, CURRENT) == 640
              and near(values(cli, player, POS)[:2], (-3.875, -14.5)))
        release(cli)
        screenshot(cli, '640.png')
        saved640 = walk(cli, player)
        check('640 can walk after teleport', saved640[1] > -13.85, str(saved640))
        switch(cli, 639)
        check('return restores 639 position', near(values(cli, player, POS), start))
        saved639 = walk(cli, player)
        switch(cli, 640)
        check('return restores moved 640 position', near(values(cli, player, POS), saved640))
        # Inject motion immediately before the press; it must not carry into 639.
        cli.set_mailbox(SPEED[0], 4, idx=player)
        switch(cli, 639)
        check('return restores moved 639 position', near(values(cli, player, POS), saved639))
        check('teleport stops horizontal momentum', all(abs(v or 0) < 0.03 for v in values(cli, player, SPEED[:2])))
        # The shell's negative-X rooms joined to 639 must count as 639, not 640.
        place(cli, player, (-5, -4, 16.05))
        check('joined master suite counts as 639', value(cli, 1, CURRENT) == 639)
        joined = values(cli, player, POS)
        switch(cli, 640)
        switch(cli, 639)
        check('joined-room position remembered', near(values(cli, player, POS), joined))
        # Enter 640 without using the button, then leave into the shared corridor.
        place(cli, player, (-3.875, -14.2, 16.05))
        check('entering 640 updates active unit', value(cli, 1, CURRENT) == 640)
        remembered640 = values(cli, 1, SAVED[640])
        place(cli, player, (-3.875, -16.2, 16.05))
        check('corridor preserves indoor position', near(values(cli, 1, SAVED[640]), remembered640))
        switch(cli, 639)
        switch(cli, 640)
        check('return from corridor lands indoors', near(values(cli, player, POS), remembered640))
        door_target = value(cli, 1, 93)
        for name, button in (('A', 1), ('B', 2)):
            cli.inject_input('joystick1_raw', button, duration_frames=3)
            time.sleep(0.25)
            check(f'{name} does not teleport', value(cli, 1, CURRENT) == 640)
        check('C does not toggle project doors', value(cli, 1, 93) == door_target)

    with game('reload') as (cli, player):
        check('reload resets 639 entry', near(values(cli, player, POS)[:2], (4.65625, -14.5)))
        switch(cli, 640)
        check('reload resets 640 entry', near(values(cli, player, POS)[:2], (-3.875, -14.5)))

    print('RESULT:', 'PASS' if not failures else f'FAIL {failures}')
    raise SystemExit(bool(failures))
