"""Host tests for scripts/ios_touch_uitest.py (layer 3 of finding-your-way
docs/plans/2026-11-08-ios-touch-parity.md): the TOUCHTEST summary that turns the
XCUITest transcript into one verdict per device and orientation."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ios_touch_uitest", REPO / "scripts" / "ios_touch_uitest.py")
uitest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uitest)


def transcript(orientation: str, fail: str | None = None, stop_after: str | None = None) -> str:
    lines = []
    for name in uitest.EXPECTED:
        lines.append(f"TOUCHTEST {orientation} {name} {'FAIL' if name == fail else 'PASS'} held=0x0000 seen=0x080e reading=0")
        if name == stop_after:
            break
    return "Test Case '-[WFTouchUITests testRealTaps]' started.\n" + "\n".join(lines) + "\n"


def test_every_check_passing_is_ok():
    s = uitest.summarize(transcript("landscape") + transcript("portrait"))
    assert s["landscape"]["ok"] and s["portrait"]["ok"]
    assert s["landscape"]["checks"]["b-d-up"] == (True, "held=0x0000 seen=0x080e reading=0")


def test_one_failure_or_an_early_stop_is_not_ok():
    s = uitest.summarize(transcript("landscape", fail="hidden-b-ignored"))
    assert not s["landscape"]["ok"]
    s = uitest.summarize(transcript("portrait", stop_after="card-narrows"))
    assert not s["portrait"]["ok"] and "c-closes-card" in s["portrait"]["missing"]
    assert uitest.summarize("** TEST FAILED **") == {}


def test_the_swift_tests_print_every_expected_check():
    swift = (REPO / "ios" / "uitests" / "tests" / "WFTouchUITests.swift").read_text()
    printed = re.findall(r'report\(orientation, "([\w-]+)"', swift)
    assert printed == uitest.EXPECTED
