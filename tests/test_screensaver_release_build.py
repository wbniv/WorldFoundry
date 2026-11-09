"""The Aquarium Dream ships as a Release build (docs/diagnostics/dream-release-2026-11-09).

A Debug Dream ran the reef at about 3 FPS on cast1. The Taskfile's Aquarium screensaver
build must assemble the Release variant, and the screensaver's release buildType must be
installable (signed like the game app's release) and build its native code as CMake Release.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _task(name):
    text = (ROOT / 'Taskfile.yml').read_text()
    match = re.search(rf'^  {re.escape(name)}:\n((?:    .*\n|\n)+)', text, re.M)
    assert match, f'no {name} task in Taskfile.yml'
    return match.group(1)


def test_aquarium_screensaver_task_builds_the_release_variant():
    body = _task('build-aquarium-screensaver-apk')
    assert ':screensaver:assembleAquariumRelease' in body
    assert 'Debug' not in re.findall(r'assemble\w+', body)[0]


def test_screensaver_release_build_type_is_signed_and_optimised():
    gradle = (ROOT / 'android/screensaver/build.gradle.kts').read_text()
    release = gradle[gradle.index('getByName("release")'):]
    release = release[:release.index('compileOptions')]
    assert 'signingConfig = signingConfigs.getByName("debug")' in release
    assert 'isDebuggable = false' in release
    assert '-DCMAKE_BUILD_TYPE=Release' in release
