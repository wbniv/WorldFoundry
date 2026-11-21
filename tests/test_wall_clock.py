"""WALL_HOUR / WALL_MINUTE / WALL_SECOND system mailboxes and WF_WALL_CLOCK, in the real engine.

Plan: docs/plans/2026-11-21-sixty-second-chain-reaction.md, Verification 1.

Run in the Linux container against the container-built Debug engine (assertions on):

    scripts/in-linux-container.sh scripts/build-wf-game-container.sh --dev
    WF_CONTAINER_ENV="WF_GAME=/build/wf-game-dev/src/engine/wf_game" \
      scripts/in-linux-container.sh bash -c 'timeout 400 xvfb-run -a -s "-screen 0 1280x720x24" \
      python3 -m pytest tests/test_wall_clock.py -v'

The clock logic itself is also covered, without an engine, by `task test-wall-clock`.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
WF_GAME = Path(os.environ.get("WF_GAME", REPO_ROOT / "engine" / "wf_game"))
GAME_CWD = REPO_ROOT / "wfsource" / "source" / "game"
LIB_DIR = REPO_ROOT / "engine" / "libs"
LEVEL = REPO_ROOT / "wflevels" / "aquarium_idle-standalone.iff"
WALL_HOUR, WALL_MINUTE, WALL_SECOND = 1922, 1923, 1924
PORT = 7791

needs_engine = pytest.mark.skipif(not WF_GAME.exists(), reason=f"wf_game not built: {WF_GAME}")
needs_display = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="no DISPLAY (run under xvfb-run)")


def engine_env(spec=None):
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB_DIR}:{env.get('LD_LIBRARY_PATH', '')}"
    env.pop("WF_WALL_CLOCK", None)
    if spec is not None:
        env["WF_WALL_CLOCK"] = spec
    return env


class Engine:
    """wf_game with the debug bridge, watching the three wall-clock mailboxes."""

    def __init__(self, spec=None, port=PORT):
        self.log = open(REPO_ROOT / "tests" / f".wf_wall_clock_{port}.log", "w")
        self.proc = subprocess.Popen(
            [str(WF_GAME), f"-L{LEVEL}", "--debug-port", str(port), "--debug-bind", "127.0.0.1"],
            cwd=str(GAME_CWD), env=engine_env(spec), stdout=self.log, stderr=subprocess.STDOUT)
        self.client = BridgeClient("127.0.0.1", port, timeout=20.0)
        self.client.ping()
        for box in (WALL_HOUR, WALL_MINUTE, WALL_SECOND):
            self.client.watch(idx=1, mailbox=box)

    def value(self, box):
        return self.client.mailbox_values.get((1, box))

    def wait(self, box, ok, timeout=10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            v = self.value(box)
            if v is not None and ok(v):
                return v
            time.sleep(0.05)
        return None

    def close(self):
        try:
            self.client.close()
        finally:
            if self.proc.poll() is None:
                self.proc.send_signal(signal.SIGTERM)
                try:
                    self.proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=3.0)
            self.log.close()


@pytest.fixture
def engine_factory():
    made = []

    def make(spec=None, port=PORT):
        e = Engine(spec, port)
        made.append(e)
        return e

    yield make
    for e in made:
        e.close()


@needs_engine
@needs_display
def test_frozen_override_reads_back_exactly(engine_factory):
    e = engine_factory("10:08:22.5@0")
    assert e.wait(WALL_HOUR, lambda v: v == 10) == 10
    assert e.wait(WALL_MINUTE, lambda v: v == 8) == 8
    sec = e.wait(WALL_SECOND, lambda v: abs(v - 22.5) < 1e-3)
    assert sec is not None, e.value(WALL_SECOND)


@needs_engine
@needs_display
def test_fast_clock_crosses_a_minute_an_hour_and_midnight(engine_factory):
    e = engine_factory("23:58:30@600", port=PORT + 1)      # ten minutes a second
    assert e.wait(WALL_HOUR, lambda v: v == 0, timeout=15.0) == 0, "never crossed midnight"
    assert e.wait(WALL_MINUTE, lambda v: 0 <= v <= 59) is not None
    assert e.wait(WALL_SECOND, lambda v: 0.0 <= v < 60.0) is not None
    # it keeps going: the hour reaches 1 within a few real seconds (one hour per 6 s at this rate)
    assert e.wait(WALL_HOUR, lambda v: v == 1, timeout=15.0) == 1


@needs_engine
@needs_display
def test_without_an_override_it_is_the_device_time(engine_factory):
    e = engine_factory(None, port=PORT + 2)
    hour = e.wait(WALL_HOUR, lambda v: True)
    minute = e.wait(WALL_MINUTE, lambda v: True)
    assert hour is not None and minute is not None
    now = time.localtime()
    drift = abs((hour * 60 + minute) - (now.tm_hour * 60 + now.tm_min)) % 1440
    assert min(drift, 1440 - drift) <= 2, (hour, minute, now)


@needs_engine
def test_a_malformed_override_stops_the_engine_at_startup():
    for bad in ("lunchtime", "25:00:00", "10:08:22@fast", "10:08"):
        r = subprocess.run([str(WF_GAME), f"-L{LEVEL}"], cwd=str(GAME_CWD), env=engine_env(bad),
                           capture_output=True, text=True, timeout=30)
        assert r.returncode == 2, (bad, r.returncode, r.stdout[-300:], r.stderr[-300:])
        assert "WF_WALL_CLOCK" in r.stderr and bad in r.stderr, r.stderr
