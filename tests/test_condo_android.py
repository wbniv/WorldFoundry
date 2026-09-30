"""Regression guard for the condo Android app (Gradle flavor `condo`, beside aquarium + snowgoons).

Plan: docs/plans/2026-10-01-condo-chromecast.md (the pattern is tests/test_aquarium_android.py).
Static only (no device, no display):

  * wflevels/condo-cd.iff (task build-cd-iff-condo) is shell.fth + today's
    wflevels/condo_639_640-standalone.iff, byte for byte.
  * the condo flavor's assets: its cd.iff (symlink to the tracked bundle) and wf_args.txt, the
    VRAM overrides `task run-condo` passes on the desktop, read by hal/android/native_app_entry.cc.
  * the flavor, applicationId suffix, label and launcher art (same names and sizes as main's).
  * scripts/android-device-run.sh knows --app condo.

    python3 -m pytest tests/test_condo_android.py -v
"""

from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml

from test_aquarium_android import APP, DENSITIES, GRADLE, REPO, SCRIPT, SECTOR, SHELL, SRC, read_game_toc

CONDO_CD = REPO / "wflevels" / "condo-cd.iff"
CONDO_LEVEL = REPO / "wflevels" / "condo_639_640-standalone.iff"
ENTRY = REPO / "wfsource" / "source" / "hal" / "android" / "native_app_entry.cc"


def test_condo_cd_iff_is_shell_plus_the_current_level():
    data = CONDO_CD.read_bytes()
    toc = read_game_toc(data)
    level = CONDO_LEVEL.read_bytes()
    assert [t[0] for t in toc] == [b"SHEL", level[:4]], toc
    (_, shel_off, shel_len), (_, lvl_off, lvl_len) = toc
    assert (shel_off, shel_len) == (SECTOR, len(SHELL.read_bytes()))
    assert (lvl_off, lvl_len) == (2 * SECTOR, len(level))
    assert data[lvl_off:lvl_off + lvl_len] == level, (
        "wflevels/condo-cd.iff is stale against wflevels/condo_639_640-standalone.iff: task build-cd-iff-condo")


def test_condo_assets():
    assets = SRC / "condo" / "assets"
    assert sorted(p.name for p in assets.iterdir()) == ["cd.iff", "wf_args.txt"]
    assert (assets / "cd.iff").is_symlink() and (assets / "cd.iff").resolve() == CONDO_CD.resolve()


def test_condo_args_match_run_condo():
    args = (SRC / "condo" / "assets" / "wf_args.txt").read_text().split()
    run = str(yaml.safe_load((REPO / "Taskfile.yml").read_text())["tasks"]["run-condo"]["cmds"])
    assert args and all(a.startswith("--vram-") for a in args), args
    for a in args:
        assert a in run, f"{a} is not what task run-condo passes"
    entry = ENTRY.read_text()
    assert 'AAssetManager_open(gAssetMgr, "wf_args.txt"' in entry
    assert "HALStart(argc, argv" in entry
    # PIGSMain reads the pigsys globals; before this was set Android ran with argc = 0 and the
    # condo aborted in gfx/texture.cc (1024-px site atlas vs the default 256-px VRAM slot).
    assert "__argc = argc;" in entry and "__argv = argv;" in entry


def test_condo_flavor_and_art():
    from PIL import Image
    g = GRADLE.read_text()
    co = re.search(r'create\("condo"\) \{(.*?)\n        \}', g, re.S)
    assert co and 'applicationIdSuffix = ".condo"' in co.group(1)
    assert "externalNativeBuild" not in co.group(1)
    main, c = SRC / "main" / "res", SRC / "condo" / "res"
    assert Image.open(c / "drawable" / "tv_banner.png").size == Image.open(main / "drawable" / "tv_banner.png").size
    for d in DENSITIES:
        for name in ("ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png"):
            assert Image.open(c / f"mipmap-{d}" / name).size == Image.open(main / f"mipmap-{d}" / name).size
    assert re.search(r'name="app_name">WF Condo<', (c / "values" / "strings.xml").read_text())
    assert 'name="ic_launcher_background"' in (c / "values" / "colors.xml").read_text()


def test_condo_tasks_and_device_script():
    tasks = yaml.safe_load((REPO / "Taskfile.yml").read_text())["tasks"]
    assert "condo_639_640-standalone.iff" in str(tasks["build-cd-iff-condo"]["cmds"])
    assert "android-device-run.sh --app condo" in str(tasks["chromecast-condo"]["cmds"])
    body = SCRIPT.read_text()
    assert "condo)     PKG=org.worldfoundry.wf_game.condo" in body
    h = subprocess.run(["bash", str(SCRIPT), "-h"], capture_output=True, text=True, timeout=30)
    assert h.returncode == 0 and "condo" in h.stdout


def test_built_condo_apk_contents():
    p = APP / "build" / "outputs" / "apk" / "condo" / "release" / "worldfoundry-condo-release.apk"
    if not p.exists():
        pytest.skip(f"{p.relative_to(REPO)} not built (cd android && ./gradlew :app:assembleCondoRelease)")
    with zipfile.ZipFile(p) as z:
        names = set(z.namelist())
        assert z.read("assets/cd.iff") == CONDO_CD.read_bytes()
        assert {"lib/arm64-v8a/libwf_game.so", "lib/armeabi-v7a/libwf_game.so"} <= names
        assert {n for n in names if n.startswith("assets/")} == {"assets/cd.iff", "assets/wf_args.txt"}


def test_suspended_until_the_window_returns():
    """Home then reopen delivers APP_CMD_RESUME ~100 ms before APP_CMD_INIT_WINDOW; drawing in that gap aborted the app on
    the Chromecast HD (GL error 1286 at display.cc:866). HALIsSuspended must also wait for the window."""
    root = Path(__file__).resolve().parent.parent
    life = (root / "wfsource/source/hal/android/lifecycle.cc").read_text()
    entry = (root / "wfsource/source/hal/android/native_app_entry.cc").read_text()
    assert "WFAndroidHasWindow" in life.split("HALIsSuspended(void)")[1].split("}")[0]
    assert "WFAndroidHasWindow()" in entry and "gEglReady ? 1 : 0" in entry
