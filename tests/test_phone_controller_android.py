"""The phone as a gamepad, static checks on the Android side (Phase E; docs/plans/2026-09-30-aquarium-chromecast.md).

  * each app's layout.json uses the engine's real EJ_BUTTONF_* bits (read from wfsource/source/hal/sjoystic.h,
    not restated), and carries exactly the buttons the plan gives it: aquarium = stick + A + B; condo = stick +
    A (doors / shade) + C (teleport) + D (orbit, held) + E/F (zoom), and **no B** (since 2026-10-01, commit
    41742943, the condo's A toggles the doors and the shade and B does nothing on its own).
  * snowgoons ships no phone controller.

No device, no build. python3 -m pytest tests/test_phone_controller_android.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "android" / "app" / "src"
SJOYSTIC = REPO / "wfsource" / "source" / "hal" / "sjoystic.h"


def engine_bits() -> dict[str, int]:
    """EJ_BUTTONB_* from the live #if 1 block of sjoystic.h, as masks."""
    text = SJOYSTIC.read_text()
    live = text[text.index("#if 1"):text.index("#else", text.index("#if 1"))]
    return {m.group(1): 1 << int(m.group(2)) for m in re.finditer(r"#define\s+EJ_BUTTONB_(\w+)\s+(\d+)", live)
            if int(m.group(2)) < 16}


def layout(app: str) -> dict:
    return json.loads((SRC / app / "assets" / "layout.json").read_text())


@pytest.mark.parametrize("app", ["aquarium", "condo"])
def test_layout_uses_the_engine_bits(app):
    bits, lay = engine_bits(), layout(app)
    assert lay["app"] == app
    assert lay["stick"] == {"up": bits["UP"], "down": bits["DOWN"], "right": bits["RIGHT"], "left": bits["LEFT"]}
    assert lay["threshold"] == 0.5, "the engine's analog-stick threshold (kJoystickThreshold)"
    for b in lay["buttons"]:
        assert b["bit"] == bits[b["id"]], b
        assert 0 < b["x"] < 1 and 0 < b["y"] < 1, b
    mask = sum(b["bit"] for b in lay["buttons"]) | sum(lay["stick"].values())
    assert mask < 1 << 16, "the protocol carries a 16-bit mask"


def test_aquarium_is_stick_a_b():
    assert [b["id"] for b in layout("aquarium")["buttons"]] == ["A", "B"]


def test_condo_has_no_b_and_a_is_doors_and_shade():
    buttons = {b["id"]: b["label"] for b in layout("condo")["buttons"]}
    assert buttons == {"A": "doors / shade", "C": "teleport", "D": "orbit (hold)", "E": "zoom in", "F": "zoom out"}
    # E zooms in and F out: camera_controls.fth adds (F - E) to the camera's range (mailbox 137 -> 116).
    fth = (REPO / "wflevels" / "condo_639_640" / "camera_controls.fth").read_text()
    assert re.search(r"JOYSTICK_BUTTON_F cc-key if 1 else 0 then\s+JOYSTICK_BUTTON_E cc-key if 1 else 0 then -", fth)
    # ... and A, not B, fires the door / shade pulse (mailbox 119) outside the D-held branch.
    assert "A (not B) toggles the glass doors and the balcony shade" in fth


def test_snowgoons_has_no_phone_controller():
    names = {p.name for p in (SRC / "snowgoons" / "assets").iterdir()}
    assert not names & {"controller.html", "layout.json"}


# ---- E2: the Android wiring ------------------------------------------------------------------------

ENTRY = REPO / "wfsource" / "source" / "hal" / "android" / "native_app_entry.cc"
WINDOW = REPO / "wfsource" / "source" / "gfx" / "gl" / "android_window.cc"
APK = REPO / "android" / "app" / "build" / "outputs" / "apk"


def _case(src: str, cmd: str) -> str:
    start = src.index(f"case {cmd}:")
    return src[start:src.index("break;", start)]


def test_emit_ors_the_phone_mask_into_the_engine_input():
    src = ENTRY.read_text()
    assert "_HALSetJoystickButtons(gGamepadButtons | gTouchButtons | gPhoneButtons);" in src
    assert src.count("_HALSetJoystickButtons(") == 2, "one declaration, one call: Emit() is the only writer"


def test_listens_only_while_resumed():
    src = ENTRY.read_text()
    assert "PhoneStop();" in _case(src, "APP_CMD_PAUSE")
    assert "PhoneStart();" in _case(src, "APP_CMD_RESUME")
    stop = src[src.index("void PhoneStop()"):src.index("void PhonePoll()")]
    assert "gPhoneButtons = 0;" in stop and "Emit();" in stop, "pause releases whatever the phone held"


def test_polled_every_frame_and_logged_per_change():
    src = ENTRY.read_text()
    pump = src[src.index("WFAndroidPumpEvents()\n{"):src.index("WFAndroidPhoneOverlayRects")]
    assert "PhonePoll();" in pump
    assert 'WFLOG("phone mask=0x%x"' in src
    assert 'WFLOG("key code=%d action=%d mask=0x%x%s"' in src, "the remote's key-edge line stays"


def test_binds_the_lan_address_only():
    src = ENTRY.read_text()
    start = src[src.index("void PhoneStart()"):src.index("void PhoneStop()")]
    assert "DiscoverLanAddress(&addr)" in start and "IsPrivateIPv4(addr)" in start
    assert "cfg.bindAddr   = addr;" in start


def test_back_hides_the_panel_before_the_key_is_dropped():
    src = ENTRY.read_text()
    key = src[src.index("if (type == AINPUT_EVENT_TYPE_KEY)"):src.index("if (type == AINPUT_EVENT_TYPE_MOTION)")]
    assert key.index("AKEYCODE_BACK && gPhoneOverlay.PanelVisible") < key.index("if (mask == 0) return 0;")


def test_overlay_drawn_after_the_hud_on_every_swap():
    src = WINDOW.read_text()
    swap = src[src.index("void AndroidSwapBuffers()"):]
    assert swap.index("WFAndroidDrawHUD();") < swap.index("WFAndroidDrawPhoneOverlay();") < swap.index("eglSwapBuffers")
    draw = src[src.index("WFAndroidDrawPhoneOverlay()\n{"):src.index("void AndroidSwapBuffers()")]
    assert "gHudEnabled" not in draw, "the HUD is off on TV; the phone overlay must not be"
    assert "if (changed || gPhoneVerts == 0)" in draw, "re-upload only when the overlay changed"


def test_cmake_builds_phonepad_into_the_android_library():
    cm = (REPO / "CMakeLists.txt").read_text()
    block = cm[cm.index("list(APPEND WF_PLATFORM_SHELL_SOURCES\n        ${SRC}/hal/android/native_app_entry.cc"):]
    block = block[:block.index(")")]
    assert "${SRC}/hal/phonepad/phonepad.cc" in block and "${SRC}/hal/phonepad/phonepad_overlay.cc" in block
    assert "${VENDOR}/qrcodegen-3c6d0b3c/qrcodegen.c" in block, "the overlay's QR encoder (E3)"


def test_internet_only_for_the_phone_flavors():
    main = (SRC / "main" / "AndroidManifest.xml").read_text()
    assert "uses-permission" not in main
    for app in ("aquarium", "condo"):
        perms = re.findall(r'<uses-permission android:name="([^"]+)"', (SRC / app / "AndroidManifest.xml").read_text())
        assert perms == ["android.permission.INTERNET"], (app, perms)
    assert not (SRC / "snowgoons" / "AndroidManifest.xml").exists()


@pytest.mark.parametrize("app", ["aquarium", "condo"])
def test_built_release_apk_has_the_controller(app):
    import zipfile
    p = APK / app / "release" / f"worldfoundry-{app}-release.apk"
    if not p.exists():
        pytest.skip(f"{p.relative_to(REPO)} not built (cd android && ./gradlew :app:assemble{app.title()}Release)")
    with zipfile.ZipFile(p) as z:
        assert z.read("assets/controller.html") == (REPO / "wfsource/source/hal/phonepad/controller.html").read_bytes()
        assert z.read("assets/layout.json") == (SRC / app / "assets" / "layout.json").read_bytes()
        for abi in ("armeabi-v7a", "arm64-v8a"):
            assert b"phone controller: open" in z.read(f"lib/{abi}/libwf_game.so"), abi
