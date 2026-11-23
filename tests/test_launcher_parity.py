"""WF Aquarium and WF Clocks behave exactly the same (Will, 2026-11-21: "both clocks and aquarium should
behave exactly the same (shell): app and screensaver bundled apk; starting app presents chooser menu, system
running screensaver chooses randomly unless LEVEL set").

One launcher activity holds that behaviour (LauncherActivity); each pack's activity only names itself in
its manifest. One host path serves the menu for both packs (dream_host.cc). The pure LaunchMode function
and its JVM test (task test-aquarium-launch-mode) hold the table of what each kind of start does.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "android/screensaver"
JAVA = APP / "src/main/java/org/worldfoundry/screensaver"
HOST = (APP / "src/main/cpp/dream_host.cc").read_text()
PACKS = {"aquarium": "AquariumActivity", "clocks": "ClocksActivity"}
DREAMS = {"aquarium": "AquariumDreamService", "clocks": "ClocksDreamService"}


def test_each_pack_launcher_only_extends_the_shared_one():
    for flavor, name in PACKS.items():
        src = (JAVA / f"{name}.java").read_text()
        code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        assert re.search(rf"public final class {name} extends LauncherActivity \{{\s*\}}", code), name


def test_the_shared_launcher_follows_launch_mode_for_every_kind_of_start():
    src = (JAVA / "LauncherActivity.java").read_text()
    assert "LaunchMode.forLauncherActivity(" in src
    assert "case MENU:" in src and "player.startMenu();" in src          # normal start: the chooser
    assert "case PLAY_LEVEL:" in src and "LevelLaunch.startChosen(this, player, mode.level)" in src   # LEVEL set
    assert "LevelLaunch.startChosen(this, player, null)" in src          # DREAM: the saved choice, random by default
    assert "ScreensaverPreviewActivity.EXTRA_DREAM" in src


def test_the_dreams_never_show_the_menu_and_play_the_saved_choice():
    for flavor, name in DREAMS.items():
        src = (JAVA / f"{name}.java").read_text()
        assert "LevelLaunch.startChosen(this, player, null);" in src, name
        assert "startMenu" not in src and "start(-1)" not in src and "MENU" not in src, name


def test_both_manifests_declare_their_launcher_activity_as_a_leanback_launcher():
    for flavor, name in PACKS.items():
        manifest = (APP / f"src/{flavor}/AndroidManifest.xml").read_text()
        assert re.search(rf'<activity android:name="\.{name}".*?LEANBACK_LAUNCHER', manifest, re.S), flavor


def test_one_menu_path_in_the_host_for_both_packs():
    assert "nativeButtons" not in HOST and "nativeBackToMenu" not in HOST
    assert "showMenu" not in HOST and "remoteInput" not in HOST and "kShowMenu" not in HOST
    assert "constexpr int kMenuLevel = -1;" in HOST
    assert "menuMode.store(menu);" in HOST                              # either pack's menu takes the remote
    # Only an APK that carries menu-cd.iff (the Aquarium) runs the menu from that second bundle.
    assert "WFAndroidSetBundleAsset(secondBundle ? kMenuBundleAsset : nullptr);" in HOST
    player = (JAVA / "TankPlayer.java").read_text()
    assert "nativeButtons" not in player and "backToMenu" not in player
    for symbol in ("nativeKey", "nativeBack"):
        assert f"native {'boolean' if symbol == 'nativeKey' else 'void'} {symbol}(" in player
        assert f"TankPlayer_{symbol}(" in HOST


def test_the_pack_howto_describes_the_shared_launch_behaviour():
    howto = (ROOT / "docs/howto/combine-levels-chooser-and-screensaver-launch.md").read_text()
    assert "LauncherActivity" in howto and "behave" in howto
