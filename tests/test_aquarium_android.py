"""Regression guard for the aquarium Android app (and the snowgoons app beside it).

Plan: docs/plans/2026-09-30-aquarium-chromecast.md

The Android build has one Gradle product flavor per game (android/app/build.gradle.kts): the
same libwf_game.so and Java glue, a different applicationId, launcher art and assets/cd.iff.
Everything here is static (no device, no display):

  * wflevels/aquarium-cd.iff (task build-cd-iff-aquarium) is a GAME bundle whose SHEL is
    wfsource/source/game/shell.fth and whose only level is today's wflevels/aquarium-standalone.iff,
    byte for byte, so a rebuilt level with a stale bundle fails here.
  * each flavor's assets: the aquarium ships the six-tank selector cd.iff (no level0.mid, so no music over the
    tank) plus the phone controller's page and layout (Phase E); snowgoons ships its snowgoons-only
    cd.iff, level0.mid and the soundfont and no phone controller; src/main/assets is gone.
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
AQ_MENU = REPO / "wflevels" / "aquarium-menu-cd.iff"
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
    # cdpack packs the UI font last (docs/plans/2026-10-17-settings-editor-font.md).
    assert [t[0] for t in toc] == [b"SHEL", AQ_LEVEL.read_bytes()[:4], b"UIFT"], toc
    (_, shel_off, shel_len), (_, lvl_off, lvl_len), (_, ui_off, ui_len) = toc
    shell = SHELL.read_bytes()
    assert (shel_off, shel_len) == (SECTOR, len(shell))
    assert data[shel_off:shel_off + 4] == b"SHEL"
    assert data[shel_off + 8:shel_off + 8 + shel_len] == shell
    level = AQ_LEVEL.read_bytes()
    assert (lvl_off, lvl_len) == (2 * SECTOR, len(level))
    assert data[lvl_off:lvl_off + lvl_len] == level, (
        "wflevels/aquarium-cd.iff is stale against wflevels/aquarium-standalone.iff: task build-cd-iff-aquarium")
    assert ui_off == lvl_off + -(-lvl_len // SECTOR) * SECTOR
    font = (REPO / "wfsource/source/game/ui-font.wfga").read_bytes()
    assert data[ui_off:ui_off + ui_len] == b"UIFT" + len(font).to_bytes(4, "little") + font
    assert len(data) == ui_off + -(-ui_len // SECTOR) * SECTOR


def test_shell_boots_toc_level_zero():
    # The aquarium bundle relies on shell.fth running TOC level 0 first (the aquarium is level 0).
    text = SHELL.read_text()
    assert re.search(r"\b0 INDEXOF_LEVEL_TO_RUN write-mailbox\b", text), text


# ---- flavor source sets ---------------------------------------------------------------------------

def _link(p: Path) -> Path:
    assert p.is_symlink(), f"{p} should be a symlink to a tracked file"
    return p.resolve()


PHONE_PAGE = REPO / "wfsource" / "source" / "hal" / "phonepad" / "controller.html"




def test_snowgoons_assets_and_main_has_none():
    assets = SRC / "snowgoons" / "assets"
    game = REPO / "wfsource" / "source" / "game"
    assert sorted(p.name for p in assets.iterdir()) == ["cd.iff", "florestan-subset.sf2", "level0.mid"]
    for name in ("florestan-subset.sf2", "level0.mid"):
        assert os.readlink(assets / name) == f"../../../../../wfsource/source/game/{name}"
        assert (assets / name).resolve() == (game / name).resolve()
    # The snowgoons-only bundle since docs/plans/2026-10-01-split-cd-iff-one-app-per-game.md (tests/test_game_apps_android.py).
    assert os.readlink(assets / "cd.iff") == "../../../../../wflevels/snowgoons-cd.iff"
    # main/assets ships in every app, so it holds only what every app needs: the runtime property editor's page.
    main_assets = SRC / "main" / "assets"
    assert not main_assets.exists() or sorted(p.name for p in main_assets.iterdir()) == ["runtime-property-ui.json"]


def test_gradle_flavors():
    g = GRADLE.read_text()
    assert re.search(r'flavorDimensions \+= "game"', g)
    sn = re.search(r'create\("snowgoons"\) \{(.*?)\n        \}', g, re.S)
    assert sn, "the snowgoons product flavor must exist"
    assert "applicationId" not in re.sub(r"//.*", "", sn.group(1)), "snowgoons keeps org.worldfoundry.wf_game"
    assert 'applicationId = "org.worldfoundry.wf_game"' in g
    assert '"worldfoundry-${variant.flavorName}-${variant.buildType.name}.apk"' in g
    # One native build for every flavor: no per-flavor externalNativeBuild.
    assert "externalNativeBuild" not in sn.group(1)


def test_the_standalone_aquarium_flavor_is_retired():
    """Will, 2026-11-22: one Aquarium APK, the combined app (docs/plans/2026-11-22-one-aquarium-apk.md)."""
    assert 'create("aquarium")' not in GRADLE.read_text()
    assert not (SRC / "aquarium").exists(), "android/app/src/aquarium came back"
    tasks = yaml.safe_load((REPO / "Taskfile.yml").read_text())["tasks"]
    assert "chromecast-aquarium" not in tasks and "build-apk-diagnostic" not in tasks


def test_no_live_file_starts_the_retired_package():
    live = [REPO / "Taskfile.yml", *sorted((REPO / "scripts").glob("*")), *sorted((REPO / "android" / "app" / "src").rglob("*.xml")),
            *sorted((REPO / "android" / "screensaver" / "src").rglob("*.xml")), GRADLE]
    hits = [str(p.relative_to(REPO)) for p in live if p.is_file() and "wf_game.aquarium" in p.read_text(errors="ignore")]
    assert hits == [], f"still names org.worldfoundry.wf_game.aquarium: {hits}"


def test_manifest_keeps_both_launchers_and_banner():
    m = MANIFEST.read_text()
    for s in ('android.intent.category.LAUNCHER', 'android.intent.category.LEANBACK_LAUNCHER',
              'android:banner="@drawable/tv_banner"', 'android:value="wf_game"',
              'android:name="android.app.NativeActivity"'):
        assert s in m, s
    for feat in ("android.software.leanback", "android.hardware.touchscreen", "android.hardware.gamepad"):
        assert re.search(rf'android:name="{re.escape(feat)}" android:required="false"', m), feat



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
    for name in ("build-cd-iff-aquarium", "install-apk"):
        assert name in tasks, name
    assert "build-cd-iff-aquarium" in str(tasks["aquarium-level"]["cmds"])


# ---- the remote / gamepad key map -----------------------------------------------------------------------

def _key_map() -> dict[str, str]:
    """AKEYCODE_* -> EJ_BUTTONF_* from the Android key table, which the entry point's MapKeyCode()
    and the screensaver's launcher menu share (hal/android/key_map.h, docs/plans/2026-11-21-one-aquarium-app.md)."""
    android = REPO / "wfsource" / "source" / "hal" / "android"
    entry = (android / "native_app_entry.cc").read_text()
    assert "return WFAndroidMapKeyCode(code);" in entry, "MapKeyCode no longer uses the shared table"
    src = (android / "key_map.h").read_text()
    body = re.search(r"inline uint32_t WFAndroidMapKeyCode\(int32_t code\)\s*\{(.*?)\n\}", src, re.S).group(1)
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
    assert bad.returncode == 2 and "snowgoons, condo, smb or qbert" in bad.stderr, bad
    assert "org.worldfoundry.wf_game" in body


# ---- a built APK (skipped unless one exists) ----------------------------------------------------------

def _apk(flavor):
    build_type = os.environ.get("WF_TEST_ANDROID_BUILD_TYPE", "debug")
    assert build_type in {"debug", "release"}, build_type
    p = APP / "build" / "outputs" / "apk" / flavor / build_type / f"worldfoundry-{flavor}-{build_type}.apk"
    if not p.exists():
        pytest.skip(f"{p.relative_to(REPO)} not built")
    return p


def test_built_apk_contents():
    with zipfile.ZipFile(_apk("snowgoons")) as z:
        assert z.read("assets/cd.iff") == (REPO / "wflevels" / "snowgoons-cd.iff").read_bytes()
        assert "lib/arm64-v8a/libwf_game.so" in set(z.namelist())


def test_built_apks_badging():
    sdks = [Path(p) for p in (os.environ.get("ANDROID_HOME"), Path.home() / "android-sdk-local") if p]
    aapt = next((a for sdk in sdks for a in sorted(sdk.glob("build-tools/*/aapt"))), None) or shutil.which("aapt")
    if not aapt:
        pytest.skip("no aapt")
    for flavor, pkg, label in (("snowgoons", "org.worldfoundry.wf_game", "Snowgoons"),):
        out = subprocess.run([str(aapt), "dump", "badging", str(_apk(flavor))], capture_output=True,
                             text=True, check=True).stdout
        assert f"package: name='{pkg}'" in out
        assert f"leanback-launchable-activity: name='android.app.NativeActivity'  label='{label}'" in out
        banner = re.search(r"^application:.* banner='([^']+)'", out, re.M)
        assert banner, out
        # Release resource optimization renames paths; verify the actual banner.
        source_banner = SRC / flavor / "res/drawable/tv_banner.png"
        if not source_banner.exists():
            source_banner = SRC / "main/res/drawable/tv_banner.png"
        with zipfile.ZipFile(_apk(flavor)) as z:
            assert z.read(banner.group(1)) == source_banner.read_bytes()
        assert "native-code: 'arm64-v8a'" in out
