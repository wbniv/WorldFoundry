#!/usr/bin/env python3
"""Capture two desktop frames of the separate seahorse grid level."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from debug_bridge_client import BridgeClient  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18946)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(ROOT / "engine/libs") + ":" + env.get("LD_LIBRARY_PATH", "")
    env["LSAN_OPTIONS"] = "detect_leaks=0"
    env.update(WF_REST_HOST="127.0.0.1", WF_REST_PORT=str(args.port + 1000))
    xvfb = subprocess.Popen(["Xvfb", ":78", "-screen", "0", "1280x960x24"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env["DISPLAY"] = ":78"
    time.sleep(1)
    level = ROOT / "wflevels/seahorse_grid-standalone.iff"
    log = (out / "runtime.log").open("w")
    proc = subprocess.Popen([
        str(ROOT / "engine/wf_game"), "-L" + str(level),
        "--vram-width=2048", "--vram-height=1024", "--vram-slot-width=512",
        "--vram-slot-height=512", "--vram-perm-width=1024", "--vram-perm-height=1024",
        "-width=1280", "-height=720", "-rate20", "--debug-port", str(args.port),
        "--debug-bind", "127.0.0.1",
    ], cwd=ROOT / "wflevels/seahorse_grid", env=env, stdout=log,
        stderr=subprocess.STDOUT,
        preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    cli = None
    try:
        cli = BridgeClient(port=args.port, timeout=30)
        cli.send({"op": "pause"})
        cli.watch(idx=9, mailbox=1906)  # Player; the level generator asserts core order
        cli.watch(idx=4, mailbox=90)    # Director setup flag
        for n in range(24):
            cli.watch(idx=4, mailbox=100 + 40 * n + 39)  # DFRM status
        def value(actor: int, mailbox: int) -> float:
            with cli._lock:
                return cli.mailbox_values.get((actor, mailbox), 0.0)
        def step(frames: int) -> None:
            initial = value(9, 1906)
            cli.send({"op": "step", "frames": frames})
            until = time.monotonic() + 90
            while time.monotonic() < until:
                if value(9, 1906) >= initial + frames * (3276 / 65536) - .0002:
                    time.sleep(.05)
                    return
                if proc.poll() is not None:
                    raise RuntimeError("engine exited; see runtime.log")
                time.sleep(.01)
            raise TimeoutError("frame step timed out")
        shots = []
        for frames, name in ((40, "initial"), (40, "later")):
            step(frames)
            path = out / (name + ".png")
            cli.send({"op": "screenshot", "filename": str(path)})
            response = cli.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=20)
            if not response or response.get("op") != "screenshot_done":
                raise RuntimeError(f"capture failed: {response}")
            shots.append({"name": name, "time": value(9, 1906), "setup": value(4, 90),
                          "statuses": [value(4, 100 + 40 * n + 39) for n in range(24)]})
        (out / "capture.json").write_text(json.dumps(shots, indent=2) + "\n")
    finally:
        if cli is not None:
            cli.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log.close()
        if xvfb is not None:
            xvfb.terminate()
            xvfb.wait()


if __name__ == "__main__":
    main()
