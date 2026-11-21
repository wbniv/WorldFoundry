#!/usr/bin/env python3
"""Every Forth math word, through the real engine's own dispatcher.

Plan: docs/plans/2026-11-21-forth-trig-words.md, Verification 3. Starts the container-built Debug
engine on the Minute Machine level, hot-loads a script into its Director through the debug bridge
(the `reload_script` op, as tests/verify_forth_reload.py does), has it write each word's result to a
global mailbox, and reads them back. A second script feeds a word a bad argument: the engine must
print the named domain error, keep running, and recover when a good script is loaded again.

Run in the Linux container, under xvfb, against the Debug engine:

  scripts/in-linux-container.sh scripts/build-wf-game-container.sh --dev
  WF_CONTAINER_ENV="WF_GAME=/build/wf-game-dev/src/engine/wf_game" scripts/in-linux-container.sh \
    bash -c 'timeout 400 xvfb-run -a -s "-screen 0 1280x720x24" python3 tests/verify_forth_math_engine.py'
"""
from __future__ import annotations

import json
import math
import os
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from debug_bridge_client import BridgeClient  # noqa: E402

WF_GAME = Path(os.environ.get("WF_GAME", ROOT / "engine" / "wf_game"))
LEVEL = ROOT / "wflevels" / "minute_machine-standalone.iff"
GAME_CWD = ROOT / "wfsource" / "source" / "game"
PORT = 7830
TIME_MBX = 1906
BASE = 1500                      # global user mailboxes the test scripts write to
TAU = 2 * math.pi
failures = []


def check(ok: bool, what: str) -> None:
    if not ok:
        failures.append(what)
        print("FAIL", what)


def close(a: float, b: float, tol: float = 2e-6) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(b))


GOOD = f"""
0.125 sin-rev {BASE} write-mailbox
0.125 cos-rev {BASE + 1} write-mailbox
0.1 tan-rev {BASE + 2} write-mailbox
0.5 asin-rev {BASE + 3} write-mailbox
0.5 acos-rev {BASE + 4} write-mailbox
1 atan-rev {BASE + 5} write-mailbox
1 0 atan2-rev {BASE + 6} write-mailbox
0.3 sincos-rev {BASE + 8} write-mailbox {BASE + 7} write-mailbox
2 sqrt {BASE + 9} write-mailbox
0 -1 atan2-rev {BASE + 10} write-mailbox
0.25 tan-rev {BASE + 11} write-mailbox
"""
EXPECT = {BASE: math.sin(TAU * 0.125), BASE + 1: math.cos(TAU * 0.125), BASE + 2: math.tan(TAU * 0.1), BASE + 3: 1 / 12,
          BASE + 4: 1 / 6, BASE + 5: 0.125, BASE + 6: 0.25, BASE + 7: math.sin(TAU * 0.3), BASE + 8: math.cos(TAU * 0.3),
          BASE + 9: math.sqrt(2), BASE + 10: 0.5}
BAD = f"2 asin-rev {BASE + 20} write-mailbox\n"


def main() -> int:
    if not WF_GAME.exists() or not LEVEL.exists():
        print(f"needs {WF_GAME} and {LEVEL}", file=sys.stderr)
        return 2
    director = json.loads((ROOT / "wflevels/minute_machine/actor-map.json").read_text())["indices"]["Director"]
    watcher = json.loads((ROOT / "wflevels/minute_machine/actor-map.json").read_text())["indices"]["Player"]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{ROOT / 'engine' / 'libs'}:{env.get('LD_LIBRARY_PATH', '')}"
    env["LSAN_OPTIONS"] = "detect_leaks=0"
    env["WF_WALL_CLOCK"] = "10:08:22@0"
    log_path = ROOT / "tests" / ".wf_forth_math_engine.log"
    log = open(log_path, "w")
    proc = subprocess.Popen([str(WF_GAME), f"-L{LEVEL}", "-width=1280", "-height=720", "--debug-port", str(PORT), "--debug-bind", "127.0.0.1"],
                            cwd=str(GAME_CWD), env=env, stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    cli = BridgeClient("127.0.0.1", PORT, timeout=40.0)
    try:
        def value(mbx):
            with cli._lock:
                return cli.mailbox_values.get((watcher, mbx))

        def wait_for(pred, timeout=15.0):
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                if pred():
                    return True
                time.sleep(0.05)
            return False

        def load(source):
            cli.send({"op": "reload_script", "idx": director, "source": source})
            return cli.wait_for(lambda m: m.get("op") in ("script_reloaded", "error"), timeout=10)

        for mbx in list(range(BASE, BASE + 12)) + [BASE + 20, TIME_MBX]:
            cli.watch(idx=watcher, mailbox=mbx)

        # 1. every word, through the real dispatcher
        reply = load(GOOD)
        check(bool(reply) and reply.get("op") == "script_reloaded", f"the good script did not load: {reply}")
        check(wait_for(lambda: all(value(m) is not None for m in EXPECT)), "no results arrived")
        for mbx, want in EXPECT.items():
            got = value(mbx)
            check(got is not None and close(got, want), f"mailbox {mbx}: engine {got} expected {want}")
        pole = value(BASE + 11)
        check(pole is not None and math.isfinite(pole) and abs(pole) > 1e10, f"tan-rev at a pole should be huge and finite: {pole}")

        # 2. a domain error: named on stderr, the engine keeps running, and it recovers
        t0 = value(TIME_MBX)
        reply = load(BAD)
        check(bool(reply) and reply.get("op") == "script_reloaded", f"the bad script did not load: {reply}")
        check(wait_for(lambda: "asin-rev: argument is outside -1 to 1" in log_path.read_text(errors="replace")), "no named domain error in the engine log")
        check(value(BASE + 20) is None or value(BASE + 20) == 0.0, f"the refused word must not write a result: {value(BASE + 20)}")
        t1 = value(TIME_MBX)
        check(wait_for(lambda: (value(TIME_MBX) or 0) > (t1 or 0) + 0.5), "the engine stopped running after a domain error")
        check(proc.poll() is None, "the engine exited after a domain error")
        reply = load(GOOD.replace("0.125 sin-rev", "0.375 sin-rev", 1))
        want = math.sin(TAU * 0.375)
        check(wait_for(lambda: value(BASE) is not None and close(value(BASE), want)), f"no recovery after the error: {value(BASE)}")
    finally:
        try:
            cli.close()
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            log.close()
    n = len(EXPECT) + 1 + 6
    print(f"{n} engine checks:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
