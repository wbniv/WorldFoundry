"""Static guard for the aquarium Metal-vs-GL parity step in codemagic.yaml.

Plan: docs/plans/2026-09-30-aquarium-level.md (Verification step 21).

The macOS half runs only on Codemagic (Mac-minutes are budgeted), so this pins everything that
can be checked without a Mac: the yaml parses, the step exists in macos-desktop-debug only,
every repo file it names exists, its artifacts are listed, its script is valid bash, and its
verdict block prints MATCH / DIFFERS correctly when driven with a stub wf_game (no display).

    python3 -m pytest tests/test_codemagic_aquarium_parity.py -v
"""
import os
import re
import struct
import subprocess
import zlib

import pytest
import yaml

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
STEP = 'Compare aquarium capture with Linux reference (informational)'
WORKFLOW = 'macos-desktop-debug'
# Same steps and artifacts built Release (codemagic.yaml reuses them by YAML alias).
RELEASE_TWIN = 'macos-desktop-release'
REFERENCE = 'tests/fixtures/renderer/aquarium-linux-frame20.png'
ARTIFACTS = ['macos-aquarium-frame20.png', 'macos-aquarium-comparison.log']


@pytest.fixture(scope='module')
def config():
    with open(os.path.join(REPO, 'codemagic.yaml')) as f:
        return yaml.safe_load(f)


def _step(workflow):
    return next((s for s in workflow.get('scripts', []) if s.get('name') == STEP), None)


def _png(w, h, rgb):
    row = b'\x00' + bytes(rgb) * w
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(row * h)) + chunk(b'IEND', b''))


def test_step_only_in_macos_desktop_debug(config):
    assert _step(config['workflows'][WORKFLOW]) is not None
    for name, wf in config['workflows'].items():
        if name not in (WORKFLOW, RELEASE_TWIN):
            assert _step(wf) is None, f'{name} must not carry the aquarium parity step'


def test_step_follows_the_snowgoons_comparison(config):
    names = [s['name'] for s in config['workflows'][WORKFLOW]['scripts']]
    assert names.index(STEP) == names.index('Compare deterministic capture with Linux reference') + 1


def test_step_uses_the_snowgoons_method(config):
    script = _step(config['workflows'][WORKFLOW])['script']
    assert script.startswith('set -euo pipefail')
    assert 'exec > >(tee -a "$CM_BUILD_DIR/cm-build.log") 2>&1' in script
    assert '--frame-step-smoke=30 --cycles=1' in script and '-rate20' in script
    assert '--capture-frame=20=' in script
    assert '$CM_BUILD_DIR/wflevels/aquarium-standalone.iff' in script
    assert f'python3 tests/compare_renderer_frames.py' in script and REFERENCE in script
    assert '--tolerance 3' in script
    assert 'AQUARIUM PARITY: MATCH' in script and 'AQUARIUM PARITY: DIFFERS' in script


def test_every_referenced_repo_file_exists(config):
    script = _step(config['workflows'][WORKFLOW])['script']
    paths = re.findall(r'(?:tests/[\w./-]+\.(?:py|png)|wflevels/[\w./-]+\.iff)', script)
    assert {'wflevels/aquarium-standalone.iff', REFERENCE, 'tests/compare_renderer_frames.py'} <= set(paths)
    for p in paths:
        assert os.path.isfile(os.path.join(REPO, p)), f'{p} is referenced by the step but missing'


def test_artifacts_listed_and_not_in_other_workflows(config):
    for name, wf in config['workflows'].items():
        listed = wf.get('artifacts', [])
        for a in ARTIFACTS:
            assert (a in listed) == (name in (WORKFLOW, RELEASE_TWIN)), f'{a} in {name}'


def test_reference_is_a_full_640x480_png():
    d = open(os.path.join(REPO, REFERENCE), 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II', d[16:24]) == (640, 480)


def test_script_is_valid_bash(config):
    script = _step(config['workflows'][WORKFLOW])['script']
    subprocess.run(['bash', '-n'], input=script, text=True, check=True)


# --- run the step's script against a stub wf_game -----------------------------------------------

def _run_step(config, tmp_path, capture):
    """Run the step with a stub Mach-O that writes `capture` (bytes) as the frame, or nothing."""
    build = tmp_path / 'build'
    (build / 'wfsource/source/game').mkdir(parents=True)
    (build / 'engine/wf_game.app/Contents/MacOS').mkdir(parents=True)
    for d in ('tests', 'wflevels'):
        os.symlink(os.path.join(REPO, d), build / d)
    payload = tmp_path / 'capture.png'
    stub = build / 'engine/wf_game.app/Contents/MacOS/wf_game'
    body = 'set -euo pipefail\n'
    if capture is not None:
        payload.write_bytes(capture)
        body += f'for a in "$@"; do case "$a" in --capture-frame=20=*) cp {payload} "${{a#--capture-frame=20=}}";; esac; done\n'
    stub.write_text('#!/bin/bash\n' + body)
    stub.chmod(0o755)
    script = _step(config['workflows'][WORKFLOW])['script']
    p = subprocess.run(['bash', '-c', script], cwd=build, text=True, capture_output=True,
                       env=dict(os.environ, CM_BUILD_DIR=str(build)))
    return p, build


def test_verdict_match(config, tmp_path):
    ref = open(os.path.join(REPO, REFERENCE), 'rb').read()
    p, build = _run_step(config, tmp_path, ref)
    assert p.returncode == 0, p.stderr
    assert 'AQUARIUM PARITY: MATCH' in p.stdout
    assert 'differing pixels: 0 of 307200' in p.stdout
    assert 'maximum channel delta: 0' in p.stdout
    assert (build / 'macos-aquarium-frame20.png').is_file()
    assert (build / 'macos-aquarium-comparison.log').is_file()


def test_verdict_differs_but_step_does_not_fail(config, tmp_path):
    p, _ = _run_step(config, tmp_path, _png(640, 480, (10, 200, 30)))
    assert p.returncode == 0, 'informational step must not fail the build'
    assert 'AQUARIUM PARITY: DIFFERS' in p.stdout and 'AQUARIUM PARITY: MATCH' not in p.stdout
    m = re.search(r'differing pixels: (\d+) of 307200', p.stdout)
    assert m and int(m.group(1)) > 0
    assert re.search(r'maximum channel delta: [1-9]\d*', p.stdout)


def test_verdict_differs_on_size_mismatch(config, tmp_path):
    p, _ = _run_step(config, tmp_path, _png(2, 2, (0, 0, 0)))
    assert p.returncode == 0
    assert 'AQUARIUM PARITY: DIFFERS' in p.stdout
    assert 'differing pixels: n/a' in p.stdout


def test_verdict_differs_when_no_capture(config, tmp_path):
    p, _ = _run_step(config, tmp_path, None)
    assert p.returncode == 0
    assert 'no capture written' in p.stdout
    assert 'AQUARIUM PARITY: DIFFERS' in p.stdout
