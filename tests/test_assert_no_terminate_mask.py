"""Regression: an engine assert must NOT be terminate-masked.

Before the debug-bridge / REST-API listener-thread fix, an `AssertMsg` →
`_sys_assert` → `exit(-1)` would run C++ static destructors that destroyed the
*joinable* `gListenerThread` (debug_server) / `gServerThread` (rest_api), calling
`std::terminate()` — which tacked a bogus "terminate called without an active
exception" + SIGABRT onto every assert, burying the real cause. Both threads are
now detached, so the assert exits cleanly (255) with the real ASSERTION message
as the last output and no terminate.

Trigger: an out-of-range mailbox read via the debug bridge (asserts in
mailbox.cc). GL + DISPLAY needed (wf_game opens a window). Uses the bridge build
`engine/wf_game-dev` (WF_ENABLE_EDITOR). Plan:
docs/plans/2026-06-02-debug-bridge-listener-teardown-deassert.md
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WF = REPO / "engine" / "wf_game-dev"          # bridge build (task build-editor)
LEVEL = REPO / "wflevels" / "qbert_practice-standalone.iff"
GAME_CWD = REPO / "wfsource" / "source" / "game"
LIBS = REPO / "engine" / "libs"
sys.path.insert(0, str(REPO / "tests"))


def test_assert_not_terminate_masked():
    if not WF.exists():
        pytest.skip(f"{WF} missing (run: task build-editor)")
    if not LEVEL.exists():
        pytest.skip(f"{LEVEL} missing")
    if not os.environ.get("DISPLAY"):
        pytest.skip("no DISPLAY — wf_game needs X")

    from debug_bridge_client import BridgeClient

    port = 7799
    log = REPO / "tests" / ".assert_no_terminate.log"
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIBS}:" + env.get("LD_LIBRARY_PATH", "")
    with open(log, "w") as fp:
        proc = subprocess.Popen(
            [str(WF), f"-L{LEVEL}", "--debug-port", str(port), "--debug-bind", "127.0.0.1"],
            cwd=str(GAME_CWD), env=env, stdout=fp, stderr=subprocess.STDOUT)
        try:
            c = BridgeClient("127.0.0.1", port, timeout=20.0)
            c.ping()
            try:
                c.set_mailbox(99999, 1, idx=1)   # out-of-range → AssertMsg → exit(-1)
            except Exception:
                pass
            for _ in range(60):
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
        finally:
            if proc.poll() is None:
                proc.terminate(); time.sleep(0.5)
                if proc.poll() is None:
                    proc.kill()

    rc = proc.poll()
    txt = log.read_text(errors="replace")
    assert "AssertMsg" in txt, "the real assert message must be present"
    assert "terminate called" not in txt, \
        "assert was terminate-masked — a joinable static thread destructor terminated on exit(-1)"
    assert rc != -6, f"process died via SIGABRT (terminate), exit={rc} (want a clean exit)"
