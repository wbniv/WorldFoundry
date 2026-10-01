"""The phone controller page (wfsource/source/hal/phonepad/controller.html) against the real server, headless.

Plan: docs/plans/2026-09-30-aquarium-chromecast.md, Phase E (design item 3, mockups 2 and 4; verification
step 12's page half). The page is served by the same phonepad.cc the Android app links (tests/phonepad_harness.py),
loaded in Playwright's headless Chromium at a landscape phone size with touch, and driven with real pointer and
touch input. The host prints the mask the engine would get, so each check is end to end: finger on the page to
EJ_BUTTONF_* bits on the TV side.

Skips (does not fail) when Playwright or its Chromium is not installed.
Screenshots go to ~/tmp/phone-controller/ for the plan's comparison with mockup 2.

    python3 -m pytest tests/test_phone_controller_page.py -v
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from phonepad_harness import A, B, LAYOUTS, PAGE, PIN, RIGHT, UP, Host, build_host

sync_api = pytest.importorskip("playwright.sync_api")

SHOTS = Path.home() / "tmp" / "phone-controller"
VIEW = {"width": 844, "height": 390}           # an iPhone 13-class phone held sideways


@pytest.fixture(scope="module")
def host_exe(tmp_path_factory):
    return build_host(tmp_path_factory.mktemp("phonepad-page"))


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001 - any launch failure means "no browser here"
            pytest.skip(f"no headless Chromium: {e}")
        yield b
        b.close()


def open_page(browser, host, pin=PIN):
    ctx = browser.new_context(viewport=VIEW, has_touch=True, is_mobile=True, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{host.port}/?k={pin}")
    return ctx, page


def wait_state(page, state, timeout=5.0):
    page.wait_for_function(f"window.__wf && window.__wf.state() === {json.dumps(state)}", timeout=timeout * 1000)


def centre(page, selector):
    box = page.locator(selector).bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, box


@pytest.fixture
def condo(host_exe):
    h = Host(host_exe, app="condo")
    yield h
    h.close()


@pytest.fixture
def aquarium(host_exe):
    h = Host(host_exe, app="aquarium")
    yield h
    h.close()


def test_page_is_one_self_contained_file():
    html = PAGE.read_text()
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", html), "external reference"
    assert "<link" not in html and "@import" not in html
    assert all(u.startswith("data:") for u in re.findall(r"""url\(['"]?([^'")]+)""", html))
    assert "touch-action:none" in html
    assert "navigator.vibrate" in html and "keepawake" in html
    assert "tilt" not in html.lower(), "tilt is Phase E6 (https), not this page"
    assert len(html.encode()) < 64 * 1024


def test_condo_buttons_follow_its_layout(browser, condo):
    ctx, page = open_page(browser, condo)
    try:
        wait_state(page, "connected")
        condo.expect(r"^EVENT connected$")
        ids = page.eval_on_selector_all(".btn", "els => els.map(e => e.dataset.id)")
        layout = json.loads(LAYOUTS["condo"].read_text())
        assert ids == [b["id"] for b in layout["buttons"]] == ["A", "C", "D", "E", "F"]
        assert "doors / shade" in page.locator('.btn[data-id="A"]').inner_text()
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / "condo.png"))
    finally:
        ctx.close()


def test_button_press_reaches_the_engine_mask(browser, condo):
    ctx, page = open_page(browser, condo)
    try:
        wait_state(page, "connected")
        x, y, _ = centre(page, '.btn[data-id="A"]')
        page.mouse.move(x, y)
        page.mouse.down()
        condo.expect_mask(A)
        assert page.locator('.btn[data-id="A"]').get_attribute("class").split().count("on") == 1
        page.mouse.up()
        condo.expect_mask(0)
    finally:
        ctx.close()


def test_stick_maps_to_the_four_directions(browser, condo):
    ctx, page = open_page(browser, condo)
    try:
        wait_state(page, "connected")
        x, y, box = centre(page, ".stick")
        r = box["width"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 0.3 * r, y)               # inside the dead zone (threshold 0.5): nothing
        time.sleep(0.15)
        assert condo.state()["mask"] == 0
        page.mouse.move(x + 0.8 * r, y)
        condo.expect_mask(RIGHT)
        page.mouse.move(x, y - 0.8 * r)
        condo.expect_mask(UP)
        page.mouse.up()
        condo.expect_mask(0)
    finally:
        ctx.close()


def test_two_fingers_stick_and_button_together(browser, condo):
    ctx, page = open_page(browser, condo)
    try:
        wait_state(page, "connected")
        sx, sy, box = centre(page, ".stick")
        ax, ay, _ = centre(page, '.btn[data-id="A"]')
        cdp = ctx.new_cdp_session(page)
        pts = [{"x": sx, "y": sy, "id": 1}, {"x": ax, "y": ay, "id": 2}]
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pts})
        pts[0]["x"] = sx + 0.8 * box["width"] / 2
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pts})
        condo.expect_mask(RIGHT | A)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        condo.expect_mask(0)
    finally:
        ctx.close()


def test_held_button_survives_past_the_timeout_thanks_to_the_heartbeat(browser, condo):
    ctx, page = open_page(browser, condo)
    try:
        wait_state(page, "connected")
        x, y, _ = centre(page, '.btn[data-id="A"]')
        page.mouse.move(x, y)
        page.mouse.down()
        condo.expect_mask(A)
        time.sleep(2.2)                               # > 2 x the TV's 1 s timeout; nothing changes on the page
        assert condo.state() == {"mask": A, "phone": True, "running": True}
        assert re.match(r"rtt \d+ ms", page.locator("#rtt").inner_text())
        page.mouse.up()
        condo.expect_mask(0)
    finally:
        ctx.close()


def test_closing_the_page_releases(browser, condo):
    ctx, page = open_page(browser, condo)
    wait_state(page, "connected")
    x, y, _ = centre(page, '.btn[data-id="A"]')
    page.mouse.move(x, y)
    page.mouse.down()
    condo.expect_mask(A)
    ctx.close()                                       # the phone's tab is gone, mid-press
    condo.expect(r"^EVENT lost$", timeout=2)
    assert condo.state()["mask"] == 0


def test_second_phone_takes_over_and_the_first_says_so(browser, condo):
    ctx1, first = open_page(browser, condo)
    ctx2 = None
    try:
        wait_state(first, "connected")
        ctx2, second = open_page(browser, condo)
        wait_state(second, "connected")
        wait_state(first, "replaced")
        assert first.locator("#stext").inner_text() == "Another phone took over"
        assert first.locator("#take").is_visible()
        time.sleep(1.5)                                # the first page must not fight back on its own
        assert second.evaluate("window.__wf.state()") == "connected"
        first.locator("#take").click()                 # ... only when asked
        wait_state(first, "connected")
        wait_state(second, "replaced")
    finally:
        ctx1.close()
        if ctx2:
            ctx2.close()


def test_wrong_pin_page(browser, condo):
    ctx, page = open_page(browser, condo, pin="000000" if PIN != "000000" else "111111")
    try:
        assert "Wrong code. Scan the TV again." in page.content()
        assert page.locator(".btn").count() == 0
        assert condo.state()["phone"] is False
    finally:
        ctx.close()


def test_tv_gone_shows_reconnecting_with_buttons_off(browser, condo):
    ctx, page = open_page(browser, condo)
    try:
        wait_state(page, "connected")
        condo.command("pause")                         # the TV app goes to the background
        condo.expect(r"^PAUSED$")
        wait_state(page, "lost")
        assert "Reconnecting" in page.locator("#stext").inner_text()
        assert "off" in page.evaluate("document.body.className")
        condo.command("resume")
        condo.expect(r"^LISTEN \d+$")
        wait_state(page, "connected", timeout=4)       # the page retries every second
    finally:
        ctx.close()


def test_aquarium_layout_is_stick_a_b(browser, aquarium):
    ctx, page = open_page(browser, aquarium)
    try:
        wait_state(page, "connected")
        assert page.eval_on_selector_all(".btn", "els => els.map(e => e.dataset.id)") == ["A", "B"]
        x, y, _ = centre(page, '.btn[data-id="B"]')
        page.mouse.move(x, y)
        page.mouse.down()
        aquarium.expect_mask(B)
        page.mouse.up()
        aquarium.expect_mask(0)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / "aquarium.png"))
    finally:
        ctx.close()
