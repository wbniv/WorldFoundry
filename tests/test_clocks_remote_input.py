"""WF Clocks' chooser takes the TV remote; nothing else does.

ClocksActivity maps up, down and OK to the engine's joystick bits and sends the held set through
TankPlayer.nativeButtons to dream_host.cc, which applies it on the game thread with the same
_HALSetJoystickButtons the NativeActivity glue uses. Back returns from a clock to the chooser, or
leaves the app (docs/plans/2026-10-01-level-menu-selector.md). Dreams and the preview never forward
keys, and flavors that never call nativeButtons leave the engine's buttons alone.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / 'android/screensaver/src/main/cpp/dream_host.cc').read_text()
JAVA = ROOT / 'android/screensaver/src/main/java/org/worldfoundry/screensaver'
ACTIVITY = (JAVA / 'ClocksActivity.java').read_text()
PLAYER = (JAVA / 'TankPlayer.java').read_text()
SJOYSTIC = (ROOT / 'wfsource/source/hal/sjoystic.h').read_text()


def header_bit(name):
    """The live (uncommented) `#define EJ_BUTTONB_<name> n` of hal/sjoystic.h."""
    values = re.findall(r'(?m)^#define\s+EJ_BUTTONB_' + name + r'\s+(\d+)\s*$', SJOYSTIC)
    assert len(values) == 1, (name, values)
    return int(values[0])


def test_jni_symbols_exist_on_both_sides():
    assert 'Java_org_worldfoundry_screensaver_TankPlayer_nativeButtons(JNIEnv*, jclass, jint mask)' in HOST
    assert 'Java_org_worldfoundry_screensaver_TankPlayer_nativeBackToMenu(JNIEnv*, jclass)' in HOST
    assert 'private static native void nativeButtons(int mask);' in PLAYER
    assert 'private static native boolean nativeBackToMenu();' in PLAYER
    assert 'extern "C" void _HALSetJoystickButtons(joystickButtonsF joystickButtons);' in HOST


def test_java_button_bits_are_sjoystic_bits():
    for java, header in [('BUTTON_A', 'A'), ('BUTTON_UP', 'UP'), ('BUTTON_DOWN', 'DOWN')]:
        m = re.search(r'static final int ' + java + r' = 1 << (\d+);', ACTIVITY)
        assert m and int(m.group(1)) == header_bit(header), (java, m and m.group(1), header_bit(header))
    assert 'constexpr uint32_t kRemoteButtons = EJ_BUTTONF_A | EJ_BUTTONF_UP | EJ_BUTTONF_DOWN;' in HOST
    assert 'static_assert(EJ_BUTTONF_A == (1u << EJ_BUTTONB_A)' in HOST


def test_key_table():
    body = re.search(r'static int buttonFor\(int keyCode\) \{(.*?)\n    \}', ACTIVITY, re.S).group(1)
    table, pending = {}, []
    for case, ret in re.findall(r'case KeyEvent\.(\w+):(?: return (\w+);)?', body):
        pending.append(case)
        if ret:
            table.update({c: ret for c in pending})
            pending = []
    assert table == {'KEYCODE_DPAD_UP': 'BUTTON_UP', 'KEYCODE_DPAD_DOWN': 'BUTTON_DOWN',
                     'KEYCODE_DPAD_CENTER': 'BUTTON_A', 'KEYCODE_ENTER': 'BUTTON_A',
                     'KEYCODE_NUMPAD_ENTER': 'BUTTON_A', 'KEYCODE_BUTTON_A': 'BUTTON_A'}, table
    assert 'default: return 0;' in body


def test_buttons_are_released_on_key_up_and_on_pause():
    assert 'if (event.getAction() == KeyEvent.ACTION_DOWN) held |= button;' in ACTIVITY
    assert 'else if (event.getAction() == KeyEvent.ACTION_UP) held &= ~button;' in ACTIVITY
    assert 'player.buttons(held);' in ACTIVITY
    pause = re.search(r'protected void onPause\(\) \{(.*?)\n    \}', ACTIVITY, re.S).group(1)
    assert 'held = 0;' in pause and 'player.buttons(0);' in pause
    assert pause.index('player.buttons(0);') < pause.index('player.stop();')
    # A fresh player run starts with nothing held and the remote off.
    prepare = re.search(r'TankPlayer_nativePrepare\(JNIEnv\*, jclass\) \{(.*?)\n\}', HOST, re.S).group(1)
    assert 'remoteButtons.store(0);' in prepare and 'remoteInput.store(false);' in prepare


def test_only_the_chooser_forwards_keys_and_back_follows_the_menu_rule():
    assert 'int button = chooser ? buttonFor(code) : 0;' in ACTIVITY
    assert ('if (event.getAction() == KeyEvent.ACTION_UP && !(chooser && player.backToMenu())) finish();'
            in ACTIVITY)
    back = re.search(r'TankPlayer_nativeBackToMenu\(JNIEnv\*, jclass\) \{(.*?)\n\}', HOST, re.S).group(1)
    assert 'if (!showMenu.load() || !levelmenu::MenuRunning() || levelmenu::SelectorVisible()) return JNI_FALSE;' in back
    assert 'levelmenu::RequestReturn();' in back


def test_dreams_preview_and_other_flavors_never_forward_input():
    callers = sorted(p.name for p in JAVA.glob('*.java')
                     if re.search(r'\.(buttons|backToMenu)\(', p.read_text()) and p.name != 'TankPlayer.java')
    assert callers == ['ClocksActivity.java'], callers
    for p in list(JAVA.glob('*DreamService.java')) + [JAVA / 'ScreensaverPreviewActivity.java']:
        text = p.read_text()
        assert 'dispatchKeyEvent' not in text and 'onKeyDown' not in text, p.name
    # The pump touches the engine's buttons only after nativeButtons turned the remote on.
    assert 'if (remoteInput.load()) _HALSetJoystickButtons(joystickButtonsF(remoteButtons.load()));' in HOST
    assert HOST.count('remoteInput.store(true);') == 1
