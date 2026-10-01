"""The TV overlay of the phone controller (wfsource/source/hal/phonepad/phonepad_overlay.cc), on Linux with a fake clock.

Plan: docs/plans/2026-09-30-aquarium-chromecast.md, Phase E (design item 4, mockup 3). The Android app draws exactly
these rectangles over the game (gfx/gl/android_window.cc), so the states and the geometry are checked here and the
composited pictures go to ~/tmp/phone-controller/ for comparison with mockup 3:

  * no address (paused, no Wi-Fi): nothing drawn;
  * waiting: the dimmed panel with the address and the PIN (in the mockup's green), "Waiting for a phone...";
  * a phone connects: panel gone, "Phone connected" for 3 s, then nothing;
  * the phone drops: "Phone lost" at once, the panel again 5 s later; Back hides the panel (and only the panel);
  * the rectangle list is rebuilt only when something visible changes (the GL side re-uploads only then).

    python3 -m pytest tests/test_phone_overlay.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phonepad_harness import REPO, Host, build_host, overlay_rects, render_rects

SHOTS = Path.home() / "tmp" / "phone-controller"
URL, HOSTPORT, PIN = "http://192.168.4.37:8765/?k=482913", "192.168.4.37:8765", "482913"
GREEN, AMBER, DIM = (0x56, 0xD3, 0x64, 255), (0xFF, 0xB4, 0x54, 255), (0, 0, 0, 0xAA)


@pytest.fixture(scope="module")
def host_exe(tmp_path_factory):
    return build_host(tmp_path_factory.mktemp("phonepad-overlay"))


@pytest.fixture
def host(host_exe):
    h = Host(host_exe)
    yield h
    h.close()


def state(host, t):
    host.command(f"ov-state {t}")
    m = host.expect(r"^OVSTATE panel=(\d) toast=(.*)$")
    return m.group(1) == "1", m.group(2)


def colours(rects):
    return {r[4] for r in rects}


def test_nothing_without_an_address(host):
    assert state(host, 0) == (False, "")
    assert overlay_rects(host, 1920, 1080, 0)[1] == []


def test_waiting_panel(host):
    host.command(f"ov-endpoint {URL} {HOSTPORT} {PIN}")
    assert state(host, 0) == (True, "")
    changed, rects = overlay_rects(host, 1920, 1080, 0)
    assert changed and rects[0] == (0.0, 0.0, 1920.0, 1080.0, DIM), "the game is dimmed behind the panel"
    assert {GREEN, AMBER} <= colours(rects), "the PIN in green and 'Waiting for a phone...' in amber"
    assert all(0 <= x0 < x1 <= 1920 and 0 <= y0 < y1 <= 1080 for x0, y0, x1, y1, _ in rects)
    assert len(rects) < 4000, "a few thousand quads at most: one upload, not one per frame"
    assert overlay_rects(host, 1920, 1080, 16) == (False, rects), "unchanged: no re-upload"
    SHOTS.mkdir(parents=True, exist_ok=True)
    render_rects(rects, 1920, 1080, REPO / "docs/porting-status/chromecast-hd-aquarium.png").save(SHOTS / "tv-waiting.png")


def test_scales_to_a_720p_surface(host):
    host.command(f"ov-endpoint {URL} {HOSTPORT} {PIN}")
    _, big = overlay_rects(host, 1920, 1080, 0)
    _, small = overlay_rects(host, 1280, 720, 0)
    assert len(small) == len(big)
    assert all(abs(s[2] - b[2] * 2 / 3) < 0.05 and abs(s[3] - b[3] * 2 / 3) < 0.05 for s, b in zip(small, big))


def test_connect_toast_then_nothing(host):
    host.command(f"ov-endpoint {URL} {HOSTPORT} {PIN}")
    host.command("ov-event connected 1000")
    assert state(host, 1000) == (False, "Phone connected")
    _, rects = overlay_rects(host, 1920, 1080, 1000)
    assert DIM not in colours(rects) and GREEN in colours(rects)
    SHOTS.mkdir(parents=True, exist_ok=True)
    render_rects(rects, 1920, 1080, REPO / "docs/porting-status/chromecast-hd-condo.png").save(SHOTS / "tv-connected.png")
    assert state(host, 3999) == (False, "Phone connected")
    assert state(host, 4000) == (False, "")
    assert overlay_rects(host, 1920, 1080, 4000) == (True, [])


def test_drop_shows_lost_then_the_panel_after_five_seconds(host):
    host.command(f"ov-endpoint {URL} {HOSTPORT} {PIN}")
    host.command("ov-event connected 1000")
    host.command("ov-event lost 10000")
    assert state(host, 10000) == (False, "Phone lost")
    assert state(host, 14999) == (False, "")
    assert state(host, 15000) == (True, "")


def test_back_hides_the_panel_and_only_the_panel(host):
    host.command(f"ov-endpoint {URL} {HOSTPORT} {PIN}")
    host.command("ov-back 100")
    assert host.expect(r"^BACK (\d)$").group(1) == "1"
    assert state(host, 200) == (False, "")
    host.command("ov-back 300")                          # nothing showing: Back is the system's again
    assert host.expect(r"^BACK (\d)$").group(1) == "0"
    host.command("ov-event connected 1000")              # a phone after all, and it drops: panel comes back
    host.command("ov-event lost 2000")
    assert state(host, 7000) == (True, "")


def test_replacement_ends_connected(host):
    host.command(f"ov-endpoint {URL} {HOSTPORT} {PIN}")
    host.command("ov-event connected 1000")
    host.command("ov-event lost 2000")
    host.command("ov-event connected 2000")
    assert state(host, 9000) == (False, "")

