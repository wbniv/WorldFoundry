"""Static + stub-driven guard for the ios-simulator-debug workflow in codemagic.yaml.

Plan: docs/plans/2026-09-30-ios-ci-revival.md.

The workflow only runs on a Codemagic Mac (budgeted minutes), so this pins what can be
checked on Linux: the yaml parses, Jolt is extracted before configure (the 2026-09-30
configure failure), every step tees into cm-build.log, the logs and screenshots are listed
as artifacts, every script is valid bash, and the iPhone + iPad step prints the right
verdicts when driven with stub xcrun / plutil / sips / sleep binaries.

    python3 -m pytest tests/test_codemagic_ios_simulator.py -v
"""
import os
import re
import stat
import struct
import subprocess
import zlib

import pytest
import yaml

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
WORKFLOW = 'ios-simulator-debug'
RUN_STEP = 'Run on iPhone + iPad Simulators (screenshot, log, verdict)'
TEE = 'exec > >(tee -a "$CM_BUILD_DIR/cm-build.log") 2>&1'


@pytest.fixture(scope='module')
def wf():
    with open(os.path.join(REPO, 'codemagic.yaml')) as f:
        return yaml.safe_load(f)['workflows'][WORKFLOW]


def _names(wf):
    return [s['name'] for s in wf['scripts']]


def _script(wf, name):
    return next(s['script'] for s in wf['scripts'] if s['name'] == name)


def test_jolt_extracted_before_configure(wf):
    names = _names(wf)
    assert names.index('Extract Jolt vendor archive') < names.index(
        'Configure CMake for iOS Simulator (arm64)')
    assert 'tar -xzf jolt-physics-5.5.0.tar.gz' in _script(wf, 'Extract Jolt vendor archive')
    assert os.path.exists(os.path.join(REPO, 'engine/vendor/jolt-physics-5.5.0.tar.gz'))


def test_every_step_tees_into_cm_build_log(wf):
    for s in wf['scripts']:
        lines = s['script'].splitlines()
        assert lines[0] == 'set -euo pipefail', s['name']
        assert lines[1] == TEE, s['name']


def test_logs_and_screenshots_are_artifacts(wf):
    for a in ['cm-build.log', 'xcodebuild.log', 'ios-configure.log',
              'ios-iphone-screenshot.png', 'ios-ipad-screenshot.png',
              'ios-iphone-launch.log', 'ios-ipad-launch.log']:
        assert a in wf['artifacts'], a


def test_no_stale_phase0_claims(wf):
    text = '\n'.join(s['script'] for s in wf['scripts'])
    assert 'expected to fail' not in text
    assert 'no if(IOS) branch' not in text


def test_scripts_are_valid_bash(wf):
    for s in wf['scripts']:
        r = subprocess.run(['bash', '-n'], input=s['script'], text=True, capture_output=True)
        assert r.returncode == 0, f"{s['name']}: {r.stderr}"


# ── stub-driven run of the iPhone + iPad step ────────────────────────────────

def _png(w, h, pixel_fn):
    rows = b''.join(b'\x00' + b''.join(bytes(pixel_fn(x, y)) for x in range(w)) for y in range(h))
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


DEVICES_JSON = '''{"devices": {
  "com.apple.CoreSimulator.SimRuntime.iOS-17-5": [
    {"udid": "OLD-PHONE", "name": "iPhone 15", "isAvailable": true},
    {"udid": "OLD-PAD", "name": "iPad Air", "isAvailable": true}],
  "com.apple.CoreSimulator.SimRuntime.iOS-18-5": [
    {"udid": "PHONE-1", "name": "iPhone 16 Pro", "isAvailable": true},
    %s],
  "com.apple.CoreSimulator.SimRuntime.watchOS-11-0": [
    {"udid": "WATCH", "name": "Apple Watch", "isAvailable": true}]
}}'''
IPAD = '{"udid": "PAD-1", "name": "iPad Pro 13-inch (M4)", "isAvailable": true}'

XCRUN = r'''#!/usr/bin/env bash
set -euo pipefail
echo "xcrun $*" >> "$STUB_CALLS"
[ "$1" = simctl ] || exit 0
shift
case "$1" in
  list) if [ "${2:-}" = -j ]; then cat "$STUB_DEVICES"; else echo "(device list)"; fi ;;
  launch)
    for a in "$@"; do case "$a" in --stdout=*) echo "engine stdout" > "${a#--stdout=}";; esac; done
    [ -n "${STUB_LAUNCH_FAIL:-}" ] && exit 1
    echo "org.worldfoundry.wf-game: $STUB_PID" ;;
  io) udid="$2"; out="$4"
      if [ "$udid" = "${STUB_BLANK_UDID:-}" ]; then cp "$STUB_BLANK" "$out"; else cp "$STUB_SHOT" "$out"; fi ;;
  spawn) echo "wf_game: engine thread spawned" ;;
  *) : ;;
esac
'''
SIPS = r'''#!/usr/bin/env bash
set -euo pipefail
src=""; out=""
while [ $# -gt 0 ]; do
  case "$1" in -Z|-s) shift 2;; --out) out="$2"; shift 2;; *) src="$1"; shift;; esac
done
cp "$src" "$out"
'''


def _exe(path, body):
    with open(path, 'w') as f:
        f.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


def _run(wf, tmp_path, ipad=True, blank_udid='', launch_fail=False, app=True, devices=None,
         blank_fn=lambda x, y: (0, 0, 0)):
    build = tmp_path / 'build'
    stubs = tmp_path / 'stubs'
    build.mkdir()
    stubs.mkdir()
    os.symlink(os.path.join(REPO, 'tests'), build / 'tests')
    if app:
        (build / 'engine/Debug-iphonesimulator/wf_game.app').mkdir(parents=True)
    (tmp_path / 'devices.json').write_text(devices or DEVICES_JSON % (IPAD if ipad else
        '{"udid": "PHONE-2", "name": "iPhone SE", "isAvailable": true}'))
    (tmp_path / 'shot.png').write_bytes(_png(40, 40, lambda x, y: (x * 6, y * 6, 90)))
    (tmp_path / 'blank.png').write_bytes(_png(40, 40, blank_fn))
    _exe(stubs / 'xcrun', XCRUN)
    _exe(stubs / 'sips', SIPS)
    _exe(stubs / 'plutil', '#!/bin/sh\necho "CFBundleIdentifier => org.worldfoundry.wf-game"\n')
    _exe(stubs / 'sleep', '#!/bin/sh\nexit 0\n')
    env = dict(os.environ,
               PATH=f"{stubs}:{os.environ['PATH']}", HOME=str(tmp_path),
               CM_BUILD_DIR=str(build), STUB_CALLS=str(tmp_path / 'calls'),
               STUB_DEVICES=str(tmp_path / 'devices.json'), STUB_PID=str(os.getpid()),
               STUB_SHOT=str(tmp_path / 'shot.png'), STUB_BLANK=str(tmp_path / 'blank.png'),
               STUB_BLANK_UDID=blank_udid, STUB_LAUNCH_FAIL='1' if launch_fail else '')
    r = subprocess.run(['bash', '-c', _script(wf, RUN_STEP)], env=env, cwd=build,
                       text=True, capture_output=True, timeout=120)
    calls = (tmp_path / 'calls').read_text() if (tmp_path / 'calls').exists() else ''
    return r, build, calls


def test_iphone_and_ipad_ok(wf, tmp_path):
    r, build, calls = _run(wf, tmp_path)
    assert 'IOS IPHONE: OK' in r.stdout and 'IOS IPAD: OK' in r.stdout, r.stdout + r.stderr
    assert r.returncode == 0
    # newest runtime with both device kinds, same .app on both
    assert 'boot PHONE-1' in calls and 'boot PAD-1' in calls and 'OLD-' not in calls
    assert calls.count('engine/Debug-iphonesimulator/wf_game.app') == 2
    for label in ('iphone', 'ipad'):
        assert (build / f'ios-{label}-screenshot.png').exists()
        log = (build / f'ios-{label}-launch.log').read_text()
        assert 'engine stdout' in log and 'engine thread spawned' in log
    assert 'IOS IPAD: OK' in (build / 'cm-build.log').read_text()


def test_blank_ipad_screenshot_fails(wf, tmp_path):
    r, _, _ = _run(wf, tmp_path, blank_udid='PAD-1')
    assert 'IOS IPHONE: OK' in r.stdout and 'IOS IPAD: FAIL' in r.stdout, r.stdout
    assert 'centre_colours=1' in r.stdout
    assert r.returncode != 0


def _letterboxed_clear(x, y):
    """Build 6abd3f6b's iPad frame: cornflower clear colour between black bars, plus a few
    blended edge pixels. The old whole-crop "more than 1 colour" rule called this OK."""
    if y < 9 or y >= 31:
        return (0, 0, 0)
    if y in (9, 30):
        return (38 + x % 3, 57, 92)
    return (99, 148, 237)


def test_letterboxed_clear_colour_fails(wf, tmp_path):
    # Regression guard for the false-positive "IOS IPAD: OK" on a solid clear colour.
    r, _, _ = _run(wf, tmp_path, blank_udid='PAD-1', blank_fn=_letterboxed_clear)
    assert 'IOS IPHONE: OK' in r.stdout and 'IOS IPAD: FAIL' in r.stdout, r.stdout + r.stderr
    assert re.search(r'ipad: .* centre_colours=1 dominant_pct=100', r.stdout), r.stdout
    assert r.returncode != 0


def test_few_colours_are_not_a_scene(wf, tmp_path):
    # 16 distinct colours in the centre crop is still below the > 50 bar.
    r, _, _ = _run(wf, tmp_path, blank_udid='PAD-1', blank_fn=lambda x, y: (x % 4 * 60, y % 4 * 60, 0))
    assert 'IOS IPAD: FAIL' in r.stdout, r.stdout
    assert 'centre_colours=16 ' in r.stdout


def test_alive_window_outlasts_coreaudio_abort(wf):
    # The simulator CoreAudio RPC abort hit ~11 s after launch; an 8 s liveness check passed it.
    script = _script(wf, RUN_STEP)
    assert 'sleep 20' in script and 'sleep 8' not in script
    assert 'alive_after_20s' in script
    assert '-gt 50' in script and '-gt 1 ' not in script


def test_no_ipad_runtime_fails_ipad_and_prints_list(wf, tmp_path):
    r, _, calls = _run(wf, tmp_path, ipad=False)
    # the older runtime has both kinds, so it is chosen over an iPhone-only newer one
    assert 'boot OLD-PHONE' in calls and 'boot OLD-PAD' in calls, r.stdout
    assert 'IOS IPAD: OK' in r.stdout


def test_no_ipad_anywhere_fails_ipad_and_prints_list(wf, tmp_path):
    r, _, calls = _run(wf, tmp_path, devices='{"devices": {"com.apple.CoreSimulator.SimRuntime.'
                       'iOS-18-5": [{"udid": "PHONE-1", "name": "iPhone 16", "isAvailable": true}]}}')
    assert 'IOS IPHONE: OK' in r.stdout, r.stdout + r.stderr
    assert 'IOS IPAD: FAIL (no ipad simulator available)' in r.stdout
    assert 'simctl list devices available' in calls and '(device list)' in r.stdout
    assert r.returncode != 0


def test_launch_failure_fails_both(wf, tmp_path):
    r, _, _ = _run(wf, tmp_path, launch_fail=True)
    assert 'IOS IPHONE: FAIL' in r.stdout and 'IOS IPAD: FAIL' in r.stdout, r.stdout
    assert r.returncode != 0


def test_missing_app_fails_loudly(wf, tmp_path):
    r, _, _ = _run(wf, tmp_path, app=False)
    assert 'no wf_game.app' in r.stdout and 'IOS IPHONE: FAIL' in r.stdout
    assert r.returncode != 0
