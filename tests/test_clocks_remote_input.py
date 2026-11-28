"""WF Clocks' chooser takes the TV remote; nothing else does.

The Clocks launcher's chooser uses the launcher menu mode it shares with the Aquarium
(docs/plans/2026-11-21-one-aquarium-app.md, docs/plans/2026-11-21-menu-key-latch.md): each remote key
goes through TankPlayer.key to dream_host.cc's MenuKeyLatch, so a tap shorter than one frame still
reaches the chooser, and Back goes through TankPlayer.back to applyMenuBack (a settings form closes
first, Back in a clock returns to the chooser, Back on the chooser leaves the app). The earlier
Clocks-only held-mask path (nativeButtons, nativeBackToMenu) is gone: a held mask read once a frame
loses a tap between two frames. Dreams and the preview never forward keys.
Ported 2026-11-28 from the parked `clocks-one-app` branch; the shared LauncherActivity landed in ac98d049.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / 'android/screensaver/src/main/cpp/dream_host.cc').read_text()
JAVA = ROOT / 'android/screensaver/src/main/java/org/worldfoundry/screensaver'
PLAYER = (JAVA / 'TankPlayer.java').read_text()


def key_forwarders():
    """The Java that forwards remote keys to the engine: every caller of TankPlayer.key/back."""
    return sorted(p.name for p in JAVA.glob('*.java')
                  if re.search(r'player\.(key|back)\(', p.read_text()))


def test_the_old_held_mask_path_is_gone():
    for gone in ('nativeButtons', 'nativeBackToMenu', '_HALSetJoystickButtons', 'remoteButtons', 'kShowMenu'):
        assert gone not in HOST, gone
    assert 'nativeButtons' not in PLAYER and 'backToMenu' not in PLAYER


def test_the_shared_latch_carries_the_chooser_keys():
    assert 'private static native boolean nativeKey(int keyCode, boolean down);' in PLAYER
    assert 'private static native void nativeBack();' in PLAYER
    key = re.search(r'TankPlayer_nativeKey\(.*?\n\}', HOST, re.S).group(0)
    assert 'if (!mask || !menuMode.load()) return JNI_FALSE;' in key
    assert 'menuKeys.keyDown(mask)' in key and 'menuKeys.keyUp(mask)' in key


def test_only_the_launcher_activities_forward_keys():
    callers = key_forwarders()
    assert callers, 'no launcher activity forwards the remote'
    for name in callers:
        assert name.endswith('Activity.java') and 'Preview' not in name, name
    for p in list(JAVA.glob('*DreamService.java')) + [JAVA / 'ScreensaverPreviewActivity.java']:
        text = p.read_text()
        assert 'dispatchKeyEvent' not in text and 'onKeyDown' not in text, p.name
