"""Guards the GPU skinning evidence tooling.

1. The strict analyzer rejects a measured case whose app-layer capture is
   missing, blank or undersized. Before this check, `analyze-gpu-skinning.py`
   validated timing, hashes and logs but never looked at a capture, so a
   committed record without captures (the cast2 profile sessions) passed.
2. The curator scopes engine logs to the final level-load marker, writes
   deterministic gzip copies and never lists private session files.
"""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


analyzer = load('analyze-gpu-skinning')


def test_visual_capture_accepts_a_rendered_frame(tmp_path):
    image = Image.new('RGB', (1920, 1080))
    image.putpixel((900, 500), (200, 180, 40))
    image.save(tmp_path / 'idle.png')
    analyzer.require_visual_capture(tmp_path)


@pytest.mark.parametrize('case', ['missing', 'blank', 'undersized', 'corrupt'])
def test_visual_capture_rejects_unusable_evidence(tmp_path, case):
    if case == 'blank':
        Image.new('RGB', (1920, 1080)).save(tmp_path / 'idle.png')
    elif case == 'undersized':
        image = Image.new('RGB', (320, 180))
        image.putpixel((1, 1), (255, 255, 255))
        image.save(tmp_path / 'idle.png')
    elif case == 'corrupt':
        (tmp_path / 'idle.png').write_bytes(b'\x89PNG\r\n\x1a\nnot an image')
    with pytest.raises(ValueError, match='visual capture'):
        analyzer.require_visual_capture(tmp_path)


def test_curator_scopes_logs_and_lists_only_allowed_files(tmp_path):
    session = tmp_path / 'view' / 'gpu' / 'round-1'
    run = session / 'pair1' / 'run-1'
    run.mkdir(parents=True)
    marker = b'zforth: INDEXOF_CAMSHOT = 1921 (expect 1921)'
    log = b'older session\n' + marker + b'\nold\n' + marker + b'\ncurrent run\n'
    (run / 'wf.log').write_bytes(log)
    (run / 'meminfo.txt').write_text('TOTAL PSS: 1\n')
    (run / 'summary.json').write_text('{}')
    for private in ['logcat.txt', 'commands.json', 'connection-attempts.json', 'cleanup-commands.json']:
        (session / private).write_text('{}')
    (tmp_path / 'device-evidence-scope.json').write_text(json.dumps(dict(logs=[], excluded='local')))
    command = [sys.executable, str(ROOT / 'scripts/curate-gpu-skinning-evidence.py'),
               '--evidence', str(tmp_path), 'view/gpu/round-1']
    listed = subprocess.run(command, check=True, capture_output=True, text=True).stdout.split()
    assert sorted(listed) == ['device-evidence-scope.json', 'view/gpu/round-1/pair1/run-1/meminfo.txt.gz',
                              'view/gpu/round-1/pair1/run-1/summary.json', 'view/gpu/round-1/pair1/run-1/wf.log.gz']
    scoped = gzip.decompress((run / 'wf.log.gz').read_bytes())
    assert scoped == marker + b'\ncurrent run\n'
    assert (run / 'wf.log.gz').read_bytes()[4:8] == b'\0\0\0\0'  # deterministic mtime
    entry, = json.loads((tmp_path / 'device-evidence-scope.json').read_text())['logs']
    assert entry['original_sha256'] == hashlib.sha256(log).hexdigest()
    assert entry['scoped_sha256'] == hashlib.sha256(scoped).hexdigest()


def panel_capture(path):
    """A 1920x1080 frame with the phone panel's QR field: white with black modules."""
    image = Image.new('RGB', (1920, 1080), (40, 90, 60))
    image.paste((255, 255, 255), (132, 232, 706, 806))
    for y in range(240, 800, 48):
        for x in range(140, 700, 48):
            image.paste((0, 0, 0), (x, y, x + 24, y + 24))
    image.save(path)


def test_panel_detector_separates_panel_from_scene(tmp_path):
    panel = load('audit-gpu-skinning-panel')
    panel_capture(tmp_path / 'panel.png')
    Image.new('RGB', (1920, 1080), (40, 90, 60)).save(tmp_path / 'scene.png')
    assert panel.capture_shows_panel(tmp_path / 'panel.png')
    assert not panel.capture_shows_panel(tmp_path / 'scene.png')


def test_curator_refuses_panel_capture(tmp_path):
    session = tmp_path / 'check'
    session.mkdir()
    panel_capture(session / 'screenshot.png')
    (tmp_path / 'device-evidence-scope.json').write_text(json.dumps(dict(logs=[])))
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/curate-gpu-skinning-evidence.py'),
                             '--evidence', str(tmp_path), 'check'], capture_output=True, text=True)
    assert result.returncode != 0 and 'phone-controller panel' in result.stderr


def test_curator_refuses_connection_details(tmp_path):
    session = tmp_path / 'check'
    session.mkdir()
    (session / 'receipt.json').write_text(json.dumps(dict(endpoint='10.0.0.2:5555')))
    (tmp_path / 'device-evidence-scope.json').write_text(json.dumps(dict(logs=[])))
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/curate-gpu-skinning-evidence.py'),
                             '--evidence', str(tmp_path), 'check'], capture_output=True, text=True)
    assert result.returncode != 0 and 'Connection detail' in result.stderr


def required_session(tmp_path, visibilities, policy='require-hidden', cases=('1', '4')):
    session = tmp_path / 'population' / 'gpu' / 'round-1'
    for case in cases:
        (session / case / 'run-1').mkdir(parents=True)
        image = Image.new('RGB', (1920, 1080), (40, 90, 60))
        image.save(session / case / 'run-1' / 'idle.png')
    history = [dict(schema=2, policy=policy, variant=case, panel_visibility=visibility, reason='test')
               for case, visibility in zip(cases, visibilities)]
    (session / 'panel-dismissal.json').write_text(json.dumps(dict(history[-1], history=history)))
    return session


def test_require_hidden_accepts_verified_sessions(tmp_path):
    panel = load('audit-gpu-skinning-panel')
    session = required_session(tmp_path, ['verified-hidden', 'verified-absent'])
    assert panel.verify_required_hidden(session, ['1', '4']) == {'1': 'verified-hidden', '4': 'verified-absent'}


@pytest.mark.parametrize('problem', ['unverified', 'best-effort', 'missing-case', 'panel-capture', 'no-record'])
def test_require_hidden_rejects_unproven_sessions(tmp_path, problem):
    panel = load('audit-gpu-skinning-panel')
    visibilities = ['verified-hidden', 'could-not-verify' if problem == 'unverified' else 'verified-hidden']
    session = required_session(tmp_path, visibilities, 'best-effort' if problem == 'best-effort' else 'require-hidden')
    cases = ['1', '4', '16'] if problem == 'missing-case' else ['1', '4']
    if problem == 'missing-case':
        (session / '16' / 'run-1').mkdir(parents=True)
    if problem == 'panel-capture':
        panel_capture(session / '4' / 'run-1' / 'idle.png')
    if problem == 'no-record':
        (session / 'panel-dismissal.json').unlink()
    with pytest.raises(ValueError):
        panel.verify_required_hidden(session, cases)


def test_legacy_session_needs_audited_back_and_clean_capture(tmp_path):
    panel = load('audit-gpu-skinning-panel')
    session = required_session(tmp_path, ['verified-hidden', 'verified-hidden'])
    hidden = dict(capture_shows_panel=False, back_hid_panel=True)
    audit = dict(sessions={'s': dict(job='J-1', cases={'1': hidden, '4': hidden})})
    panel.verify_legacy(session, 's', 'J-1', ['1', '4'], audit)
    audit['sessions']['s']['cases']['4'] = dict(capture_shows_panel=False, back_hid_panel=False)
    with pytest.raises(ValueError, match='lacks a hidden panel'):
        panel.verify_legacy(session, 's', 'J-1', ['1', '4'], audit)
    with pytest.raises(ValueError, match='No panel audit'):
        panel.verify_legacy(session, 's', 'J-2', ['1'], audit)


def test_derived_recipe_adds_only_the_panel_policy(tmp_path):
    runner = load('run-gpu-skinning-campaign')
    frozen = tmp_path / 'population-gpu-round-1.json'
    frozen.write_text(json.dumps(dict(workflow='variant-benchmark', duration=60)))
    recipe = dict(path=str(frozen), sha256=hashlib.sha256(frozen.read_bytes()).hexdigest())
    before = frozen.read_bytes()
    path, digest = runner.derive_recipe(recipe, 'require-hidden', tmp_path / 'submitted')
    assert frozen.read_bytes() == before
    assert json.loads(path.read_text()) == dict(workflow='variant-benchmark', duration=60, panel='require-hidden')
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    frozen.write_text('{"workflow": "changed"}')
    with pytest.raises(ValueError, match='Frozen recipe changed'):
        runner.derive_recipe(recipe, 'require-hidden', tmp_path / 'submitted')
