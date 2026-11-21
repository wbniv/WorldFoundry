"""One Aquarium app: the screensaver package also carries the playable tank menu.

docs/plans/2026-11-21-one-aquarium-app.md. `org.worldfoundry.screensaver` launched normally shows the
engine's tank menu over the playable bundle (the Aquarium game app's aquarium-menu-cd.iff, shipped as
assets/menu-cd.iff); the Dream, the preview and any LEVEL or DREAM start play the autopilot bundle
(assets/cd.iff) as before. These are source and packaging guards; the mode decision itself is
LaunchModeTest (`task test-aquarium-launch-mode`).
"""
from pathlib import Path
import os
import re
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCREENSAVER = ROOT / "android/screensaver"
ASSETS = SCREENSAVER / "src/aquarium/assets"
HOST = (SCREENSAVER / "src/main/cpp/dream_host.cc").read_text()
ACCESSOR = (ROOT / "wfsource/source/hal/android/asset_accessor_aasset.cc").read_text()
GAME_HOST = (ROOT / "wfsource/source/hal/android/native_app_entry.cc").read_text()
APK = SCREENSAVER / "build/outputs/apk/aquarium/release/screensaver-aquarium-release.apk"


def test_the_menu_bundle_is_the_game_apps_bundle_and_the_dream_keeps_cd_iff():
    assert os.readlink(ASSETS / "menu-cd.iff") == "../../../../../wflevels/aquarium-menu-cd.iff"
    assert os.readlink(ASSETS / "cd.iff") == "../../../../../wflevels/aquarium-screensaver-cd.iff"
    game = ROOT / "android/app/src/aquarium/assets/cd.iff"
    assert (ASSETS / "menu-cd.iff").resolve() == game.resolve(), "one menu bundle for both packages"


def test_the_host_runs_the_menu_from_menu_cd_iff_only_in_menu_mode():
    assert 'constexpr const char* kMenuBundleAsset = "menu-cd.iff";' in HOST
    assert "WFAndroidSetBundleAsset(menu ? kMenuBundleAsset : nullptr);" in HOST
    # The accessor redirects exactly the engine's "cd.iff", and only when a host asked for it.
    assert 'if (!gBundleAsset.empty() && std::strcmp(path, "cd.iff") == 0)' in ACCESSOR
    assert "WFAndroidSetBundleAsset" not in GAME_HOST, "the game app keeps its one cd.iff"


def test_one_key_table_for_both_hosts():
    assert "#include <hal/android/key_map.h>" in HOST and "#include <hal/android/key_map.h>" in GAME_HOST
    assert "WFAndroidMapKeyCode(keyCode)" in HOST
    assert "return WFAndroidMapKeyCode(code);" in GAME_HOST
    for source in (HOST, GAME_HOST):
        assert "case AKEYCODE_DPAD_CENTER" not in source, "a second copy of the key table"


def test_back_follows_the_game_app():
    """Back in a tank returns to the menu; Back on the menu leaves; an open form closes first."""
    body = re.search(r"void applyMenuBack\(\) \{(.*?)\n\}", HOST, re.S).group(1)
    order = [body.index(s) for s in ("wfprops::host().modal", "levelmenu::SelectorVisible()",
                                     "levelmenu::MenuRunning()")]
    assert order == sorted(order), body
    assert "closing.store(true)" in body and "levelmenu::RequestReturn()" in body
    game = GAME_HOST[GAME_HOST.index("keyCode == AKEYCODE_BACK && levelmenu::MenuRunning()"):]
    assert "levelmenu::RequestReturn()" in game[:1200] and "ANativeActivity_finish" in game[:1200]


def test_the_manifest_entries_keep_their_contract():
    manifest = (SCREENSAVER / "src/aquarium/AndroidManifest.xml").read_text()
    assert re.search(r'<activity android:name="\.AquariumActivity".*?android\.intent\.category\.LEANBACK_LAUNCHER',
                     manifest, re.S)
    assert 'android:name=".AquariumDreamService"' in manifest
    assert 'android:authorities="org.worldfoundry.screensaver.settings"' in manifest
    main = (SCREENSAVER / "src/main/AndroidManifest.xml").read_text()
    assert 'android:name=".ScreensaverPreviewActivity"' in main


@pytest.mark.skipif(not APK.exists(), reason="build the APK first: task build-aquarium-screensaver-apk")
def test_the_apk_carries_both_bundles():
    with zipfile.ZipFile(APK) as z:
        names = set(z.namelist())
        assert {"assets/cd.iff", "assets/menu-cd.iff", "assets/levels.manifest"} <= names
        assert z.read("assets/menu-cd.iff") == (ROOT / "wflevels/aquarium-menu-cd.iff").read_bytes()
        assert z.read("assets/levels.manifest") == (ROOT / "wflevels/aquarium-menu.manifest").read_bytes()
        screensaver = ROOT / "wflevels/aquarium-screensaver-cd.iff"
        if screensaver.exists():
            assert z.read("assets/cd.iff") == screensaver.read_bytes()
