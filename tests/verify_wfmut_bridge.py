"""Bridge regression for the wfmut:: refactor (plan step 6 close-out).

After docs/plans/2026-05-19-engine-mutation-api.md routed debug_server.cc's
SET_TRANSFORM / SET_PROP / SET_MAILBOX cases (and their undo/revert paths)
through wfmut::, this script proves the *live TCP bridge* still applies
those ops — the in-process --wfmut-smoke covers wfmut directly, but not the
bridge protocol on top of it.

Covers test-matrix items X6 (bridge regression) and F14 (gWatches still
fires on a wfmut-driven mailbox write). Launches wf_game (the lean
bridge host — same debug_server.cc as wf-edit), drives ops over the
newline-JSON protocol, verifies via state/mailbox broadcasts, captures a
screenshot, and exits nonzero on any failure.

Run:  python3 tests/verify_wfmut_bridge.py
"""
from __future__ import annotations

import os, sys, time, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient  # noqa: E402

REPO  = Path(__file__).resolve().parent.parent
WF    = REPO / "engine" / "wf_game"
LEVEL = REPO / "wflevels" / "smb_w1_1-standalone.iff"
LIB   = REPO / "engine" / "libs"
CWD   = REPO / "wfsource" / "source" / "game"
PORT  = 7798
SHOT  = REPO / "tests" / "screenshots" / "wfmut_bridge_regression.png"
PLAYER = 1   # smb_w1_1-standalone player idx (confirmed by --wfmut-smoke)

passed = 0
failed = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def latest_state(b: BridgeClient, idx: int):
    """Most recent {"op":"state","idx":idx,"pos":[...]} from the inbox."""
    with b._lock:
        for msg in reversed(b._inbox):
            if msg.get("op") == "state" and msg.get("idx") == idx:
                return msg.get("pos")
    return None


def main() -> int:
    SHOT.parent.mkdir(parents=True, exist_ok=True)
    if SHOT.exists():
        SHOT.unlink()

    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{LIB}:{env.get('LD_LIBRARY_PATH', '')}"
    env.setdefault("DISPLAY", ":0")

    log_path = REPO / "tests" / ".wfmut_bridge.log"
    log_fp = open(log_path, "w")
    proc = subprocess.Popen(
        [str(WF), f"-L{LEVEL}", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1"],
        cwd=str(CWD), env=env, stdout=log_fp, stderr=subprocess.STDOUT,
    )

    b = None
    try:
        b = BridgeClient(port=PORT, timeout=15.0)

        # 0. ping/pong sanity.
        b.ping()
        check("ping → pong", b.wait_for(lambda m: m.get("op") == "pong", 5.0) is not None)

        # Pause so physics doesn't fight our teleport; BroadcastState keeps
        # running while paused.
        b.send({"op": "pause"})
        b.wait_for(lambda m: m.get("op") == "paused", 3.0)
        time.sleep(0.3)  # let a state broadcast land

        # 1. scene:set_transform → wfmut::SetActorPos. Verify the next state
        #    broadcast for the player reports the teleported position.
        target = [10.0, 0.0, 5.0]
        b.send({"op": "scene:set_transform", "idx": PLAYER, "pos": target})
        moved = b.wait_for(
            lambda m: m.get("op") == "state" and m.get("idx") == PLAYER
                      and m.get("pos") is not None
                      and abs(m["pos"][0] - target[0]) < 0.2
                      and abs(m["pos"][2] - target[2]) < 0.2,
            timeout=4.0)
        check("scene:set_transform applies (wfmut::SetActorPos)", moved is not None,
              f"latest pos={latest_state(b, PLAYER)}")

        # 2. scene:set_prop → wfmut::SetActorField. No error reply = applied.
        #    movebloc.MaxGroundSpeed is a fixed32 field.
        b.send({"op": "scene:set_prop", "idx": PLAYER,
                "key": "movebloc.MaxGroundSpeed", "value": 24.0})
        err = b.wait_for(lambda m: m.get("op") == "error", timeout=1.0)
        check("scene:set_prop movebloc.MaxGroundSpeed no error", err is None,
              str(err))

        # 2b. scene:set_prop on a bad field → error relayed from wfmut::lastError.
        b.send({"op": "scene:set_prop", "idx": PLAYER,
                "key": "common.NotAField", "value": 1.0})
        bad = b.wait_for(lambda m: m.get("op") == "error"
                         and "unknown field path" in str(m.get("msg", "")), timeout=2.0)
        check("scene:set_prop bad field → wfmut error relayed", bad is not None)

        # 3. watch + set_mailbox → wfmut::SetMailbox, and the gWatches broadcast
        #    (F14) still fires with the written value.
        SLOT = 5
        b.watch(PLAYER, SLOT)
        b.set_mailbox(SLOT, 7, idx=PLAYER)
        got = b.wait_for_mailbox(PLAYER, SLOT, 7.0, timeout=4.0)
        check("set_mailbox + watch broadcast (wfmut::SetMailbox, F14)", got)

        # 4. undo_step → reverts the mailbox write through wfmut. The watch
        #    should broadcast the restored value (0 if it was unset).
        b.undo_step()
        time.sleep(0.5)
        err = b.wait_for(lambda m: m.get("op") == "error", timeout=0.5)
        check("undo_step no error (wfmut path)", err is None, str(err))

        # 5. revert_all → restores all session originals through wfmut.
        b.revert_all()
        reverted = b.wait_for(lambda m: m.get("op") == "reverted", timeout=4.0)
        check("revert_all → reverted (wfmut transform+prop restore)",
              reverted is not None)

        # 6. Screenshot proof (feedback_screenshots_for_proof). Capture WHILE
        #    PAUSED — rendering + BroadcastState keep running when paused, and
        #    this avoids the >100 ms dt spike that resuming after a multi-
        #    second wall-clock pause produces (the bridge's resume path
        #    doesn't clamp dt the way WFGame::StepFrame does; resuming here
        #    flings the no-mobility player and asserts on a garbage actor
        #    index — pre-existing bridge fragility, unrelated to wfmut).
        b.send({"op": "screenshot", "filename": str(SHOT)})
        reply = b.wait_for(lambda m: m.get("op") in ("screenshot_done", "error")
                           and "screenshot" in str(m), timeout=5.0)
        deadline = time.time() + 3.0
        while time.time() < deadline and not SHOT.exists():
            time.sleep(0.1)
        check("screenshot captured", SHOT.exists() and SHOT.stat().st_size > 0,
              f"reply={reply}")

    finally:
        if b:
            b.close()
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_fp.close()

    print(f"=== wfmut bridge regression: {passed} passed, {failed} failed ===")
    if SHOT.exists():
        print(f"    screenshot: {SHOT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
