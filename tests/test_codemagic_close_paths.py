"""Static guard for the macOS close-paths / -fullscreen step in codemagic.yaml.

Plan: docs/plans/2026-09-21-macos-close-paths.md ("CI step").

The step only means anything on a Codemagic Mac (Mac-minutes are budgeted), so this pins what
can be checked on Linux: the yaml parses, the step exists in macos-desktop-debug only and runs
after the windowed smoke, every file it names exists, its outputs are listed as artifacts, the
step and the script are valid bash, `-h` works, and the script's verdict logic produces
OK / FAIL correctly when driven with stubs for wf_game, osascript and the Swift probe.

    python3 -m pytest tests/test_codemagic_close_paths.py -v
"""
import os
import re
import subprocess
import textwrap

import pytest
import yaml

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
STEP = 'Close paths, fullscreen and bundle launch (⌘Q, red button, Esc, -fullscreen, open .app)'
WORKFLOW = 'macos-desktop-debug'
# Same steps and artifacts built Release (codemagic.yaml reuses them by YAML alias).
RELEASE_TWIN = 'macos-desktop-release'
SCRIPT = 'scripts/macos/close-paths-ci.sh'
PROBE = 'scripts/macos/wf_ui_probe.swift'
LEVEL = 'wflevels/snowgoons-blender/snowgoons-standalone.iff'
ARTIFACTS = ['macos-close-paths.log', 'macos-close-*.log', 'macos-fullscreen.png', 'macos-bundle-*',
             'cm-build.log']
VERDICTS = ['MACOS CMD-Q', 'MACOS RED BUTTON', 'MACOS ESC STAYS OPEN', 'MACOS FULLSCREEN',
            'MACOS BUNDLE LAUNCH']


@pytest.fixture(scope='module')
def config():
    with open(os.path.join(REPO, 'codemagic.yaml')) as f:
        return yaml.safe_load(f)


def _step(workflow):
    return next((s for s in workflow.get('scripts', []) if s.get('name') == STEP), None)


def _script_text():
    return open(os.path.join(REPO, SCRIPT)).read()


def test_step_only_in_macos_desktop_debug(config):
    assert _step(config['workflows'][WORKFLOW]) is not None
    for name, wf in config['workflows'].items():
        if name not in (WORKFLOW, RELEASE_TWIN):
            assert _step(wf) is None, f'{name} must not carry the close-paths step'


def test_step_follows_the_windowed_smoke(config):
    names = [s['name'] for s in config['workflows'][WORKFLOW]['scripts']]
    assert names.index(STEP) == names.index('Run windowed smoke (Phase 4 proxy gate)') + 1


def test_step_preamble_and_invocation(config):
    script = _step(config['workflows'][WORKFLOW])['script']
    assert script.startswith('set -euo pipefail')
    assert 'exec > >(tee -a "$CM_BUILD_DIR/cm-build.log") 2>&1' in script
    assert f'bash {SCRIPT}' in script
    assert 'CLOSE_PATHS_STRICT=' in script
    assert 'tee "$CM_BUILD_DIR/macos-close-paths.log"' in script


def test_referenced_files_exist(config):
    script = _step(config['workflows'][WORKFLOW])['script']
    assert SCRIPT in script
    body = _script_text()
    assert 'scripts/macos/wf_ui_probe.swift' in body and LEVEL in body
    for p in (SCRIPT, PROBE, LEVEL):
        assert os.path.isfile(os.path.join(REPO, p)), f'{p} is referenced but missing'


def test_artifacts_listed_and_not_in_other_workflows(config):
    for name, wf in config['workflows'].items():
        listed = wf.get('artifacts', [])
        for a in ARTIFACTS:
            if a == 'cm-build.log':
                continue  # other workflows may legitimately collect their own cm-build.log
            assert (a in listed) == (name in (WORKFLOW, RELEASE_TWIN)), f'{a} in {name}'
    assert 'cm-build.log' in config['workflows'][WORKFLOW]['artifacts']


def test_step_and_script_are_valid_bash(config):
    subprocess.run(['bash', '-n'], input=_step(config['workflows'][WORKFLOW])['script'],
                   text=True, check=True)
    subprocess.run(['bash', '-n', os.path.join(REPO, SCRIPT)], check=True)


def test_script_conventions():
    body = _script_text()
    assert body.splitlines()[1] == 'set -euo pipefail'
    p = subprocess.run(['bash', os.path.join(REPO, SCRIPT), '--help'], capture_output=True, text=True)
    assert p.returncode == 0 and 'usage:' in p.stdout
    for v in VERDICTS:
        assert f'echo "{v}: ' in body
    # The TCC grant must stay loud about being ephemeral-VM only.
    assert 'ephemeral' in body.lower()


# --- drive the script with stubs (no Mac) --------------------------------------------------------

# The stub game logs Right (GLFW 262) and Esc (GLFW 256) presses on its own when STUB_KEYS=works,
# standing in for the engine's WF_MACOS_KEYLOG output; it cannot tell which mechanism sent them.
GAME = r'''#!/bin/bash
echo $$ > "$CM_BUILD_DIR/game.pid"
trap 'echo "Calling PIGSExit()"; exit 0' USR1
trap 'exit 143' TERM
[ $# -eq 0 ] && echo "macos: launched with no arguments (Finder / LaunchServices): windowed"
echo "macos: window 640x480 points, 640x480 pixels (scale 1.0), CAMetalLayer attached"
[ "${WF_MACOS_KEYLOG:-}" = 1 ] && echo "macos: keylog on; window focus 1, key window 1, app active 1"
while true; do
  if [ "${WF_MACOS_KEYLOG:-}" = 1 ] && [ "$STUB_KEYS" = works ]; then
    echo "macos: key 262 scancode 124 action 1 mods 0"
    echo "macos: key 256 scancode 53 action 1 mods 0"
  fi
  sleep 0.3
done
'''

# open / Finder stub: start the bundle's executable detached with no arguments, as LaunchServices
# would, honouring open's --env/--stdout/--stderr. STUB_LAUNCH=broken makes it fail like a
# bundle whose CFBundleExecutable names no file.
OPEN = r'''#!/bin/bash
[ "$STUB_LAUNCH" = works ] || { echo "The application cannot be opened (-10827)" >&2; exit 1; }
out=/dev/null err=/dev/null envs=()
while [ $# -gt 1 ]; do
  case "$1" in --env) envs+=("$2"); shift 2 ;; --stdout) out=$2; shift 2 ;; --stderr) err=$2; shift 2 ;; *) shift ;; esac
done
app=$1
env "${envs[@]}" "$app/Contents/MacOS/wf_game" >"$out" 2>"$err" </dev/null &
exit 0
'''

# pgrep stub: only ever "finds" the stub game, never a real wf_game on the host.
PGREP = r'''#!/bin/bash
f="$CM_BUILD_DIR/game.pid"
[ -s "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null && cat "$f"
exit 0
'''

# osascript stub: ⌘Q and the red-button click "quit" the stub game (SIGUSR1 -> exit 0) when the
# test says the path works; everything else is a no-op that succeeds.
OSASCRIPT = r'''#!/bin/bash
all="$*"
case "$all" in
  *"UI elements enabled"*) echo true ;;
  *'keystroke "q" using command down'*) [ "$STUB_CMDQ" = works ] && kill -USR1 "$(cat "$CM_BUILD_DIR/game.pid")" ;;
  *AXCloseButton*click*|*click*AXCloseButton*) [ "$STUB_RED" = works ] && kill -USR1 "$(cat "$CM_BUILD_DIR/game.pid")" ;;
  *'"Finder" to open'*) app=$(sed -n 's/.*POSIX file "\([^"]*\)".*/\1/p' <<< "$all")
                        [ "$STUB_FINDER" = works ] && open "$app" ;;
esac
exit 0
'''

# swiftc stub: "compiles" a probe that reports a 1920x1080 display and a window of $STUB_WIN.
SWIFTC = r'''#!/bin/bash
out=""
while [ $# -gt 0 ]; do [ "$1" = -o ] && out=$2; shift; done
cat > "$out" <<'EOF'
#!/bin/bash
case "$1" in
  screen) echo "probe: main display id=1 bounds=0,0 1920x1080"
          echo "probe: main display mode 1920x1080 points, 1920x1080 pixels, refresh 60.0"
          echo "probe: NSScreen[0] frame=0,0 1920x1080 backingScaleFactor=1.0" ;;
  windows) echo "probe: window layer=0 onscreen=true bounds=$STUB_WIN" ;;
  axclose|axbutton) exit 1 ;;
esac
exit 0
EOF
chmod +x "$out"
'''


def _exe(path, body):
    path.write_text(body)
    path.chmod(0o755)


def _run(tmp_path, strict='', cmdq='works', red='works', win='0,0 1920x1080', keys='works',
         finder='works', launch='works'):
    build = tmp_path / 'build'
    (build / 'wfsource' / 'source' / 'game').mkdir(parents=True)
    (build / 'engine/wf_game.app/Contents/MacOS').mkdir(parents=True)
    for d in ('scripts', 'wflevels'):
        os.symlink(os.path.join(REPO, d), build / d)
    _exe(build / 'engine/wf_game.app/Contents/MacOS/wf_game', GAME)
    stubs = tmp_path / 'bin'
    stubs.mkdir()
    _exe(stubs / 'osascript', OSASCRIPT)
    _exe(stubs / 'swiftc', SWIFTC)
    _exe(stubs / 'open', OPEN)
    _exe(stubs / 'pgrep', PGREP)
    _exe(stubs / 'plutil', '#!/bin/bash\necho wf_game\n')
    for name in ('sw_vers', 'csrutil', 'screencapture', 'killall'):
        _exe(stubs / name, '#!/bin/bash\nexit 0\n')
    _exe(stubs / 'sudo', '#!/bin/bash\nexit 1\n')  # no sudo: TCC grants are skipped
    env = dict(os.environ, CM_BUILD_DIR=str(build), CLOSE_PATHS_STRICT=strict,
               PATH=f'{stubs}:{os.environ["PATH"]}', STUB_CMDQ=cmdq, STUB_RED=red, STUB_WIN=win,
               STUB_KEYS=keys, STUB_FINDER=finder, STUB_LAUNCH=launch)
    p = subprocess.run(['bash', os.path.join(REPO, SCRIPT)], cwd=build, env=env,
                       capture_output=True, text=True, timeout=240)
    return p


def _verdict(out, label):
    m = re.search(rf'^{re.escape(label)}: (\w+)', out, re.M)
    return m and m.group(1)


def test_all_paths_ok_with_working_stubs(tmp_path):
    p = _run(tmp_path, strict='cmdq red esc fullscreen bundle')
    assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-2000:]
    for v in VERDICTS:
        assert _verdict(p.stdout, v) == 'OK', (v, p.stdout[-3000:])
    assert 'via system-events' in p.stdout
    assert 'exit status 0' in p.stdout
    assert 'Retina NOT testable' in p.stdout
    assert re.search(r'^MACOS BUNDLE LAUNCH: OK \(via finder; .*arguments \[\]', p.stdout, re.M), p.stdout[-3000:]
    assert re.search(r'^MACOS BUNDLE KEYS: Right presses logged: .*Esc presses logged [1-9]', p.stdout, re.M)
    assert 'Esc reached the key callback' in p.stdout


def test_bundle_falls_back_to_open_when_finder_fails(tmp_path):
    p = _run(tmp_path, strict='bundle', finder='broken')
    assert p.returncode == 0, p.stdout[-3000:]
    assert 'MACOS BUNDLE LAUNCH: OK (via launchservices-open;' in p.stdout


def test_bundle_that_cannot_launch_fails_strict(tmp_path):
    p = _run(tmp_path, strict='bundle', finder='broken', launch='broken')
    assert p.returncode == 1
    assert _verdict(p.stdout, 'MACOS BUNDLE LAUNCH') == 'FAIL'
    assert 'STRICT: bundle failed' in p.stdout


def test_esc_unproven_without_key_log(tmp_path):
    # Still running after Esc means nothing unless Esc is seen in the key callback.
    p = _run(tmp_path, keys='broken')
    assert _verdict(p.stdout, 'MACOS ESC STAYS OPEN') == 'FAIL'
    assert 'no Esc press reached the key callback' in p.stdout


def test_failures_are_reported_not_swallowed(tmp_path):
    p = _run(tmp_path, cmdq='broken', red='broken', win='100,100 640x480')
    assert p.returncode == 0, 'informational (no strict checks) must not fail the step'
    assert _verdict(p.stdout, 'MACOS CMD-Q') == 'FAIL'
    assert _verdict(p.stdout, 'MACOS RED BUTTON') == 'FAIL'
    assert _verdict(p.stdout, 'MACOS FULLSCREEN') == 'FAIL'
    # The stub game logs Esc presses on its own, so Esc is OK here even with ⌘Q broken.
    assert _verdict(p.stdout, 'MACOS ESC STAYS OPEN') == 'OK'


def test_strict_check_fails_the_step(tmp_path):
    p = _run(tmp_path, strict='cmdq', cmdq='broken')
    assert p.returncode == 1
    assert 'STRICT: cmdq failed' in p.stdout


def test_release_twin_is_the_debug_workflow_built_release(config):
    debug, release = config['workflows'][WORKFLOW], config['workflows'][RELEASE_TWIN]
    assert release['scripts'] == debug['scripts']
    assert release['artifacts'] == debug['artifacts']
    assert release['environment']['vars']['WF_BUILD_TYPE'] == 'Release'
    configure = next(s['script'] for s in debug['scripts'] if s['name'].startswith('Configure CMake'))
    assert '-DCMAKE_BUILD_TYPE="${WF_BUILD_TYPE:-Debug}"' in configure


def test_macos_info_plist_uses_cmake_variables_only():
    # The macOS bundle is built by Ninja, not Xcode: CMake's configure_file expands ${VAR} and
    # @VAR@ but leaves Xcode's $(VAR) literal. A literal CFBundleExecutable of "$(EXECUTABLE_NAME)"
    # shipped until 2026-11-16; LaunchServices then finds no executable, so a double-click (or
    # `open`) cannot start the app even though running Contents/MacOS/wf_game directly works.
    body = open(os.path.join(REPO, 'macos', 'Info.plist')).read()
    assert '$(' not in body
    assert '<string>${MACOSX_BUNDLE_EXECUTABLE_NAME}</string>' in body
