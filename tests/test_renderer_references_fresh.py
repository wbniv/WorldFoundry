#!/usr/bin/env python3
"""test_renderer_references_fresh.py — the committed Linux frame references must match what Linux renders now.

The macOS CI gates (`macos-desktop-debug` in codemagic.yaml) compare a Metal frame with a committed Linux
capture. When a rendering change lands on every platform (WF_CULL ON by default, 4c02b471) the reference goes
stale and the gate goes red on a Mac build that costs real Mac-minutes, although Metal is fine (2026-09-30: 35
pixels, found only in CI). This test renders the same frames on Linux with the same flags as CI and compares
them with the committed references, so a stale reference fails here for free.

Needs a built engine (engine/wf_game, or WF_GAME=) and the X display; it skips without them. If it fails after an
engine change: rebuild first (`task build`); if it still fails, regenerate the reference from the Linux capture
with the command in `_capture` below, look at the PNG, commit it, and let the macOS build confirm it.
"""
import os
import resource
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ENGINE = Path(os.environ.get('WF_GAME') or REPO / 'engine' / 'wf_game')
GAME_DIR = REPO / 'wfsource' / 'source' / 'game'

# (name, level, reference): the levels and references the macOS workflow compares.
CASES = [
    ('snowgoons', 'wflevels/snowgoons-blender/snowgoons-standalone.iff',
     'tests/fixtures/renderer/snowgoons-linux-frame20.png'),
    ('aquarium', 'wflevels/aquarium-standalone.iff',
     'tests/fixtures/renderer/aquarium-linux-frame20.png'),
]


def _display_ok():
    if not shutil.which('xdpyinfo'):
        return False
    return subprocess.run(['xdpyinfo'], capture_output=True).returncode == 0


def _no_core_dumps():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _capture(level, out):
    """The same command as the macOS workflow: frame 20 of a 30-step, 1-cycle, -rate20 run."""
    env = dict(os.environ, LD_LIBRARY_PATH=f"{REPO / 'engine' / 'libs'}:{os.environ.get('LD_LIBRARY_PATH', '')}")
    return subprocess.run(
        [str(ENGINE), '--frame-step-smoke=30', '--cycles=1', f'-L{REPO / level}', '-rate20',
         f'--capture-frame=20={out}'],
        cwd=GAME_DIR, env=env, capture_output=True, text=True, timeout=120, preexec_fn=_no_core_dumps)


@pytest.mark.parametrize('name,level,reference', CASES, ids=[c[0] for c in CASES])
def test_reference_matches_a_fresh_linux_capture(name, level, reference, tmp_path):
    if not ENGINE.exists():
        pytest.skip(f'no engine at {ENGINE} (task build, or set WF_GAME)')
    if not _display_ok():
        pytest.skip('needs the X display (DISPLAY / XAUTHORITY)')
    assert (REPO / level).exists() and (REPO / reference).exists()

    out = tmp_path / f'{name}.png'
    run = _capture(level, out)
    assert out.exists(), f'{name}: no frame captured\n{run.stdout[-800:]}\n{run.stderr[-800:]}'

    cmp = subprocess.run(
        [sys.executable, str(REPO / 'tests' / 'compare_renderer_frames.py'), str(REPO / reference), str(out),
         '--tolerance', '3'], capture_output=True, text=True)
    assert cmp.returncode == 0, (
        f'{name}: the committed Linux reference is stale (or the engine binary is older than the source):\n'
        f'{cmp.stdout}\nRebuild (task build), then if it still differs regenerate {reference}.')
