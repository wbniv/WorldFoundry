"""Pytest fixtures for the wf debug-bridge tests.

Launches wf_game in a subprocess with the bridge enabled, on a per-session
basis. Skips the whole module if no DISPLAY is available — wf_game requires
an X server to run (no headless mode yet).
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from debug_bridge_client import BridgeClient

REPO_ROOT = Path(__file__).resolve().parent.parent
WF_GAME   = REPO_ROOT / "engine" / "wf_game"
GAME_CWD  = REPO_ROOT / "wfsource" / "source" / "game"
LIB_DIR   = REPO_ROOT / "engine" / "libs"
LEVEL     = REPO_ROOT / "wflevels" / "qbert_practice-standalone.iff"

# Use a non-default port so we don't collide with a Blender session.
BRIDGE_PORT = 7778


@pytest.fixture(scope="session")
def bridge():
    if not WF_GAME.exists():
        pytest.skip(f"wf_game not built: {WF_GAME} missing (run engine/build_game.sh)")
    if not LEVEL.exists():
        pytest.skip(f"qbert_practice level missing: {LEVEL}")
    if not os.environ.get("DISPLAY"):
        pytest.skip("no DISPLAY — wf_game requires X")

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB_DIR}:{env.get('LD_LIBRARY_PATH', '')}"

    proc = subprocess.Popen(
        [str(WF_GAME), f"-L{LEVEL}",
         "--debug-port", str(BRIDGE_PORT),
         "--debug-bind", "127.0.0.1"],
        cwd=str(GAME_CWD),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    client: BridgeClient | None = None
    try:
        # The engine boots quickly; the bridge listener comes up after init.
        client = BridgeClient("127.0.0.1", BRIDGE_PORT, timeout=15.0)
        # Sanity: ping/pong.
        client.ping()
        if client.wait_for(lambda m: m.get("op") == "pong", timeout=2.0) is None:
            pytest.fail("no pong from bridge")
        yield client
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)
