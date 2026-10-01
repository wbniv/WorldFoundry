"""Regression guard for the aquarium Android app (and the snowgoons app beside it).

Plan: docs/plans/2026-09-30-aquarium-chromecast.md

The Android build has one Gradle product flavor per game (android/app/build.gradle.kts): the
same libwf_game.so and Java glue, a different applicationId, launcher art and assets/cd.iff.
Everything here is static (no device, no display):

  * wflevels/aquarium-cd.iff (task build-cd-iff-aquarium) is a GAME bundle whose SHEL is
    wfsource/source/game/shell.fth and whose only level is today's wflevels/aquarium-standalone.iff,
    byte for byte, so a rebuilt level with a stale bundle fails here.
  * each flavor's assets: the aquarium ships only its cd.iff (no level0.mid, so no Mario music
    over the tank); snowgoons keeps the three pre-flavor symlinks; src/main/assets is gone.
  * the flavors, ids and APK names in build.gradle.kts; the manifest keeps both launchers,
    the banner and the not-required TV / gamepad / touch features.
  * the aquarium's launcher art overrides main's with the same names and sizes.
  * the Android CI workflow publishes apk/<flavor>/debug/*.apk; no task or workflow points at
    the pre-flavor APK paths.
  * scripts/android-device-run.sh (task chromecast-aquarium) parses and answers -h.
  * with a built APK present (cd android && ./gradlew :app:assembleDebug), its contents.

    python3 -m pytest tests/test_aquarium_android.py -v
"""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "android" / "app"
SRC = APP / "src"
GRADLE = APP / "build.gradle.kts"
MANIFEST = SRC / "main" / "AndroidManifest.xml"
AQ_CD = REPO / "wflevels" / "aquarium-cd.iff"
AQ_LEVEL = REPO / "wflevels" / "aquarium-standalone.iff"
SHELL = REPO / "wfsource" / "source" / "game" / "shell.fth"
SCRIPT = REPO / "scripts" / "android-device-run.sh"
SECTOR = 2048
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def read_game_toc(data: bytes):
    """[(tag, offset, size)] from a cdpack GAME bundle (wftools/cdpack-rs/src/main.rs)."""
    assert data[:4] == b"GAME", data[:4]
    assert struct.unpack_from("<I", data, 4)[0] == len(data) - 8
    assert data[8:12] == b"TOC\0"
    n = struct.unpack_from("<I", data, 12)[0] // 12
    return [(data[16 + 12 * i:20 + 12 * i],) + struct.unpack_from("<II", data, 20 + 12 * i) for i in range(n)]


# ---- the aquarium-only cd.iff -----------------------------------------------------------------

def test_aquarium_cd_iff_is_shell_plus_the_current_level():
    data = AQ_CD.read_bytes()
    toc = read_game_toc(data)
    assert [t[0] for t in toc] == [b"SHEL", AQ_LEVEL.read_bytes()[:4]], toc
    (_, shel_off, shel_len), (_, lvl_off, lvl_len) = toc
    shell = SHELL.read_bytes()
    assert (shel_off, shel_len) == (SECTOR, len(shell))
    assert data[shel_off:shel_off + 4] == b"SHEL"
    assert data[shel_off + 8:shel_off + 8 + shel_len] == shell
    level = AQ_LEVEL.read_bytes()
    assert (lvl_off, lvl_len) == (2 * SECTOR, len(level))
    assert data[lvl_off:lvl_off + lvl_len] == level, (
        "wflevels/aquarium-cd.iff is stale against wflevels/aquarium-standalone.iff: task build-cd-iff-aquarium")
    assert len(data) == lvl_off + -(-lvl_len // SECTOR) * SECTOR


def test_shell_boots_toc_level_zero():
    # The aquarium bundle relies on shell.fth running TOC level 0 first (the aquarium is level 0).
    text = SHELL.read_text()
    assert re.search(r"\b0 INDEXOF_LEVEL_TO_RUN write-mailbox\b", text), text


# ---- flavor source sets ---------------------------------------------------------------------------

def _link(p: Path) -> Path:
    assert p.is_symlink(), f"{p} should be a symlink to a tracked file"
    return p.resolve()


def test_aquarium_assets_are_only_its_cd_iff():
    assets = SRC / "aquarium" / "assets"
    assert sorted(p.name for p in assets.iterdir()) == ["cd.iff"]
    assert _link(assets / "cd.iff") == AQ_CD.resolve()


def test_snowgoons_assets_unchanged_and_main_has_none():
    assets = SRC / "snowgoons" / "assets"
    game = REPO / "wfsource" / "source" / "game"
    assert sorted(p.name for p in assets.iterdir()) == ["cd.iff", "florestan-subset.sf2", "level0.mid"]
    for name in ("cd.iff", "florestan-subset.sf2", "level0.mid"):
        assert os.readlink(assets / name) == f"../../../../../wfsource/source/game/{name}"
        assert (assets / name).resolve() == (game / name).resolve()
    assert not (SRC / "main" / "assets").exists(), "main assets would ship in every app"


def test_gradle_flavors():
    g = GRADLE.read_text()
    assert re.search(r'flavorDimensions \+= "game"', g)
    sn = re.search(r'create\("snowgoons"\) \{(.*?)\n        \}', g, re.S)
    aq = re.search(r'create\("aquarium"\) \{(.*?)\n        \}', g, re.S)
    assert sn and aq, "both product flavors must exist"
    assert "applicationId" not in re.sub(r"//.*", "", sn.group(1)), "snowgoons keeps org.worldfoundry.wf_game"
    assert 'applicationIdSuffix = ".aquarium"' in aq.group(1)
    assert 'applicationId = "org.worldfoundry.wf_game"' in g
    assert '"worldfoundry-${variant.flavorName}-${variant.buildType.name}.apk"' in g
    # One native build for every flavor: no per-flavor externalNativeBuild.
    assert "externalNativeBuild" not in sn.group(1) + aq.group(1)


def test_manifest_keeps_both_launchers_and_banner():
    m = MANIFEST.read_text()
    for s in ('android.intent.category.LAUNCHER', 'android.intent.category.LEANBACK_LAUNCHER',
              'android:banner="@drawable/tv_banner"', 'android:value="wf_game"',
              'android:name="android.app.NativeActivity"'):
        assert s in m, s
    for feat in ("android.software.leanback", "android.hardware.touchscreen", "android.hardware.gamepad"):
        assert re.search(rf'android:name="{re.escape(feat)}" android:required="false"', m), feat
    assert not (SRC / "aquarium" / "AndroidManifest.xml").exists(), "the flavors share main's manifest"


def test_aquarium_launcher_art_overrides_main():
    from PIL import Image
    main, aq = SRC / "main" / "res", SRC / "aquarium" / "res"
    assert Image.open(aq / "drawable" / "tv_banner.png").size == Image.open(main / "drawable" / "tv_banner.png").size
    assert (aq / "drawable" / "tv_banner.png").read_bytes() != (main / "drawable" / "tv_banner.png").read_bytes()
    for d in DENSITIES:
        for name in ("ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png"):
            a, b = aq / f"mipmap-{d}" / name, main / f"mipmap-{d}" / name
            assert Image.open(a).size == Image.open(b).size, (a, b)
    strings = (aq / "values" / "strings.xml").read_text()
    assert re.search(r'name="app_name">WF Aquarium<', strings)
    assert 'name="log_viewer_label"' in strings
    assert 'name="ic_launcher_background"' in (aq / "values" / "colors.xml").read_text()


# ---- CI + tasks -----------------------------------------------------------------------------------------

def test_android_ci_publishes_every_flavor():
    text = (REPO / "codemagic.yaml").read_text()
    wf = yaml.safe_load(text)["workflows"]["android-apk-debug"]          # the effective (last) definition
    assert "android/app/build/outputs/apk/*/debug/*.apk" in wf["artifacts"], wf["artifacts"]
    assert "outputs/apk/debug/" not in text, "a pre-flavor APK glob is left in codemagic.yaml"
    assert any(":app:assembleDebug" in s.get("script", "") for s in wf["scripts"]), "assembleDebug builds every flavor"


def test_no_task_points_at_pre_flavor_apk_paths():
    t = (REPO / "Taskfile.yml").read_text()
    assert "apk/debug/worldfoundry-debug.apk" not in t and "apk/release/worldfoundry-release.apk" not in t
    tasks = yaml.safe_load(t)["tasks"]
    for name in ("build-cd-iff-aquarium", "chromecast-aquarium", "install-apk"):
        assert name in tasks, name
    assert "android-device-run.sh --app aquarium" in str(tasks["chromecast-aquarium"]["cmds"])
    assert "build-cd-iff-aquarium" in str(tasks["aquarium-level"]["cmds"])


# ---- the remote / gamepad key map -----------------------------------------------------------------------

def _key_map() -> dict[str, str]:
    """AKEYCODE_* -> EJ_BUTTONF_* from MapKeyCode() in the Android entry point."""
    src = (REPO / "wfsource" / "source" / "hal" / "android" / "native_app_entry.cc").read_text()
    body = re.search(r"uint32_t MapKeyCode\(int32_t code\)\s*\{(.*?)\n\}", src, re.S).group(1)
    return dict(re.findall(r"case (AKEYCODE_\w+):\s*return (EJ_BUTTONF_\w+);", body))


def test_remote_ok_is_button_a():
    # The Chromecast / Google TV remote's OK sends DPAD_CENTER (it has no BUTTON_A); unmapped, the
    # key was dropped. Plan: docs/plans/2026-10-01-chromecast-ok-button.md
    keys = _key_map()
    assert keys.get("AKEYCODE_DPAD_CENTER") == "EJ_BUTTONF_A"
    assert keys.get("AKEYCODE_BUTTON_A") == "EJ_BUTTONF_A"


def test_dpad_directions_stay_mapped():
    keys = _key_map()
    for d in ("LEFT", "RIGHT", "UP", "DOWN"):
        assert keys.get(f"AKEYCODE_DPAD_{d}") == f"EJ_BUTTONF_{d}"


# ---- the device hand-off script -------------------------------------------------------------------------

def test_device_script_parses_and_helps():
    body = SCRIPT.read_text()
    assert "set -euo pipefail" in body.splitlines()[:12]
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    h = subprocess.run(["bash", str(SCRIPT), "-h"], capture_output=True, text=True, timeout=30)
    assert h.returncode == 0 and h.stdout.startswith("Usage:"), h
    bad = subprocess.run(["bash", str(SCRIPT), "--app", "mario"], capture_output=True, text=True, timeout=30)
    assert bad.returncode == 2 and "aquarium, snowgoons or condo" in bad.stderr, bad
    for pkg in ("org.worldfoundry.wf_game.aquarium", "org.worldfoundry.wf_game"):
        assert pkg in body


# ---- a built APK (skipped unless one exists) ----------------------------------------------------------

def _apk(flavor):
    p = APP / "build" / "outputs" / "apk" / flavor / "debug" / f"worldfoundry-{flavor}-debug.apk"
    if not p.exists():
        pytest.skip(f"{p.relative_to(REPO)} not built (cd android && ./gradlew :app:assembleDebug)")
    return p


def test_built_aquarium_apk_contents():
    with zipfile.ZipFile(_apk("aquarium")) as z:
        names = set(z.namelist())
        assert z.read("assets/cd.iff") == AQ_CD.read_bytes()
        assert "lib/arm64-v8a/libwf_game.so" in names
        assert not {n for n in names if n.startswith("assets/")} - {"assets/cd.iff"}
    with zipfile.ZipFile(_apk("snowgoons")) as z:
        assert z.read("assets/cd.iff") == (REPO / "wfsource" / "source" / "game" / "cd.iff").read_bytes()


def test_built_apks_badging():
    sdks = [Path(p) for p in (os.environ.get("ANDROID_HOME"), Path.home() / "android-sdk-local") if p]
    aapt = next((a for sdk in sdks for a in sorted(sdk.glob("build-tools/*/aapt"))), None) or shutil.which("aapt")
    if not aapt:
        pytest.skip("no aapt")
    for flavor, pkg, label in (("aquarium", "org.worldfoundry.wf_game.aquarium", "WF Aquarium"),
                               ("snowgoons", "org.worldfoundry.wf_game", "World Foundry")):
        out = subprocess.run([str(aapt), "dump", "badging", str(_apk(flavor))], capture_output=True,
                             text=True, check=True).stdout
        assert f"package: name='{pkg}'" in out
        assert f"leanback-launchable-activity: name='android.app.NativeActivity'  label='{label}'" in out
        assert "banner='res/drawable/tv_banner.png'" in out
        assert "native-code: 'arm64-v8a'" in out
