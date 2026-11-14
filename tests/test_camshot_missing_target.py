"""A CamShot whose Target names no object stops the level with an assertion, not a segfault.

Regression guard for docs/plans/2026-11-14-qbert-blender-pipeline-repair.md. A regenerated
Q*bert level named its CamShots' Target `target_14`, an object that was not exported; levcomp
writes 0 for a name it cannot resolve, and the engine's `assert(shotData->Target)` is compiled
out of Release (DO_ASSERTIONS=0 since 191c4c90), so SetCameraParametersFromShot dereferenced a
null actor: SIGSEGV on the first camera update. The check now fires in every build.

Builds a variant of the Q*bert level with every CamShot's Target pointing at a name that does
not exist, runs it headless, and expects the assertion report and exit status 255 (`exit(-1)`
in _sys_assert); the unmodified level must run its frames and exit 0.

Needs the engine and the Rust level tools built for this machine, and xvfb-run; run it in the
linux-test container. WF_GAME=<path> selects the engine binary (default engine/wf_game).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WF_GAME = Path(os.environ.get('WF_GAME', REPO / 'engine' / 'wf_game'))
GAME_CWD = REPO / 'wfsource' / 'source' / 'game'
LEVEL = 'qbert_practice'
TOOLS = [REPO / 'wftools' / c / 'target' / 'release' / b
         for c, b in (('iffcomp-rs', 'iffcomp'), ('levcomp-rs', 'levcomp'), ('textile-rs', 'textile'))]

pytestmark = [
    pytest.mark.skipif(not WF_GAME.exists(), reason=f'engine not built: {WF_GAME}'),
    pytest.mark.skipif(not all(t.exists() for t in TOOLS), reason='Rust level tools not built (task build-level-tools)'),
    pytest.mark.skipif(shutil.which('xvfb-run') is None, reason='xvfb-run missing (run in the linux-test container)'),
]

OBJ_SPLIT = "{ 'OBJ'"


def camshot_indices(lev: str) -> list[int]:
    """1-based actor indices (levcomp's numbering) of the CamShots in a .lev."""
    blocks = lev.split(OBJ_SPLIT)[1:]
    return [i for i, b in enumerate(blocks, start=1) if '"Class Name" } { \'DATA\' "camshot" }' in b]


def build_variant(tmp_path: Path, dangling: bool) -> tuple[Path, list[int]]:
    src = REPO / 'wflevels' / LEVEL
    dst = tmp_path / LEVEL
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('*.blend', '*.blend1', '__pycache__'))
    lev_path = dst / f'{LEVEL}.lev'
    lev = lev_path.read_text()
    shots = camshot_indices(lev)
    assert shots, 'the Q*bert level has CamShots'
    if dangling:
        lev, n = re.subn(r'(\{ \'STR\' \{ \'NAME\' "Target" \} \{ \'STR\' )"[^"]*"', r'\1"no_such_target"', lev)
        assert n == len(shots)
        lev_path.write_text(lev)
    env = dict(os.environ, WF_LEVEL_DIR=str(dst), WF_LEVEL_OUT_DIR=str(tmp_path))
    subprocess.run(['bash', str(REPO / 'wftools/wf_blender/build_level_binary.sh'), LEVEL],
                   env=env, check=True, stdout=subprocess.DEVNULL)
    return tmp_path / f'{LEVEL}-standalone.iff', shots


def run_level(level: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['timeout', '120', 'xvfb-run', '-a', '-s', '-screen 0 1280x720x24', str(WF_GAME),
         '--frame-step-smoke=30', '--cycles=1', '-rate20', '--no-fps', f'-L{level}'],
        cwd=GAME_CWD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')


def test_a_camshot_target_that_names_no_object_fires_the_assertion(tmp_path):
    level, shots = build_variant(tmp_path, dangling=True)
    run = run_level(level)
    m = re.search(r'CamShot actor (\d+): Target is object 0, which is not an actor', run.stdout)
    assert m, f'no assertion naming the shot; exit {run.returncode}, tail:\n{run.stdout[-1500:]}'
    assert int(m.group(1)) in shots, f'actor {m.group(1)} is not one of the CamShots {shots}'
    assert 'ASSERTION FAILED' in run.stdout
    assert 'Segmentation' not in run.stdout
    assert run.returncode == 255, f'expected exit(-1) from _sys_assert, got {run.returncode}'


def test_the_unmodified_level_runs(tmp_path):
    level, _ = build_variant(tmp_path, dangling=False)
    run = run_level(level)
    assert 'ASSERTION FAILED' not in run.stdout
    assert run.returncode == 0, f'exit {run.returncode}, tail:\n{run.stdout[-1500:]}'
