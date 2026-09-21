"""Exercise real shell/level teardown, including VM cleanup under ASan/LSan.

Run with DISPLAY set to an X server with GLX support. The bundled case uses
the same cd.iff as `task run`; the standalone cases bypass the shell.
"""
import os
import subprocess
import time
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
GAME_CWD = REPO / "wfsource/source/game"
BINARY = Path(os.environ.get("WF_SHUTDOWN_BINARY", REPO / "engine/wf_game"))
LEVEL = REPO / "wflevels/qbert_practice-standalone.iff"


@pytest.mark.parametrize("mode", ["bundle", "standalone", "cycles"])
def test_game_shutdown(mode, tmp_path):
    if not BINARY.exists():
        pytest.skip("build engine/wf_game first")
    if not os.environ.get("DISPLAY"):
        pytest.skip("requires an X display with GLX")
    asset = GAME_CWD / "cd.iff" if mode == "bundle" else LEVEL
    if not asset.exists():
        pytest.skip(f"missing level bundle: {asset}")

    xdisplay = pytest.importorskip("Xlib.display")
    event = pytest.importorskip("Xlib.protocol.event")
    display = xdisplay.Display()
    root = display.screen().root
    existing = {window.id for window in root.query_tree().children}
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(REPO / "engine/libs") + ":" + env.get("LD_LIBRARY_PATH", "")
    env["ASAN_OPTIONS"] = env.get("ASAN_OPTIONS", "") + ":detect_leaks=1"
    env["UBSAN_OPTIONS"] = env.get("UBSAN_OPTIONS", "") + ":halt_on_error=1"
    args = [str(BINARY), "-pps", "--debug-port", "0"]
    if mode != "bundle":
        args.append(f"-L{LEVEL}")
    if mode == "cycles":
        args.extend(["--frame-step-smoke=3", "--cycles=3"])

    log_path = tmp_path / "shutdown.log"
    try:
        with log_path.open("w") as log:
            proc = subprocess.Popen(args, cwd=GAME_CWD, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
            try:
                if mode != "cycles":
                    deadline = time.monotonic() + 30
                    closed = False
                    while proc.poll() is None and time.monotonic() < deadline:
                        for window in root.query_tree().children:
                            if window.id not in existing and window.get_wm_name() == "World Foundry":
                                window.send_event(event.ClientMessage(
                                    window=window,
                                    client_type=display.intern_atom("WM_PROTOCOLS"),
                                    data=(32, [display.intern_atom("WM_DELETE_WINDOW"), 0, 0, 0, 0]),
                                ))
                                display.flush()
                                closed = True
                                break
                        if closed:
                            break
                        time.sleep(0.05)
                    assert closed, log_path.read_text(errors="replace")
                proc.wait(timeout=30)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
    finally:
        display.close()

    output = log_path.read_text(errors="replace")
    assert proc.returncode == 0, output
    if mode == "cycles":
        assert output.count("Level::Level: leveldata=") == 3, output
    else:
        assert "_curLevel->done()" in output, output
    for diagnostic in ("ASSERTION FAILED", "AddressSanitizer", "LeakSanitizer", "runtime error:"):
        assert diagnostic not in output, output
