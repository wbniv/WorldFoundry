#!/usr/bin/env python3
"""Candle flicker spike: capture consecutive frames of a Cuckoo Village level on the desktop engine (plan docs/plans/2026-11-22-cuckoo-village-candle-flicker.md).

Run inside the Linux container against the container-built dev engine, under xvfb:

  WF_CONTAINER_ENV="WF_GAME=/build/wf-game-dev/src/engine/wf_game" scripts/in-linux-container.sh \\
    bash -c 'xvfb-run -a -s "-screen 0 2048x1200x24" python3 scripts/capture-candle-study.py --level build/candle-spike/swap-study/cuckoo_village-standalone.iff --out OUTDIR'

  --level FILE   a standalone level (a spike build: normal, or study with its fixed camera)
  --out DIR      write frame-0000.png, frame-0001.png ... here
  --frames N     consecutive frames to capture, one stepped frame apart (default 8; at -rate30 they are 1/30 s apart)
  --warm N       frames to step first, for the camera and the first scan to settle (default 60)
  --size WxH     window size (default 1280x720)
  --clock SPEC   WF_WALL_CLOCK for the run (default 2026-12-25T22:00:00+07:00@0: in season, at night, frozen)
  --step N       step N frames between captures (default 1)

A study build's flicker follows the level clock, so the frames are deterministic. A normal build's follows the wall second, which the frozen
clock holds still: use a study build for strips and clips.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from debug_bridge_client import BridgeClient  # noqa: E402

WF_GAME = Path(os.environ.get("WF_GAME", ROOT / "engine" / "wf_game"))
GAME_CWD = ROOT / "wfsource" / "source" / "game"
TIME_MBX = 1906


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--warm", type=int, default=60)
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--clock", default="2026-12-25T22:00:00+07:00@0")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--probe", action="store_true", help="print the Camera, cs_wide and LookAt actors' position and rotation after the warm-up")
    ap.add_argument("--port", type=int, default=7860)
    args = ap.parse_args()
    width, height = (int(v) for v in args.size.lower().split("x"))
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{ROOT / 'engine' / 'libs'}:{env.get('LD_LIBRARY_PATH', '')}"
    env["LSAN_OPTIONS"] = "detect_leaks=0"
    env["WF_WALL_CLOCK"] = args.clock
    log = open(out / "engine.log", "w")
    proc = subprocess.Popen([str(WF_GAME), f"-L{args.level.resolve()}", f"-width={width}", f"-height={height}", "-rate30",
                             "--vram-width=4096", "--vram-height=2048", "--vram-slot-width=2048", "--vram-slot-height=2048",
                             "--vram-perm-width=1024", "--vram-perm-height=1024",
                             "--debug-port", str(args.port), "--debug-bind", "127.0.0.1"],
                            cwd=str(GAME_CWD), env=env, stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    client = BridgeClient("127.0.0.1", args.port, timeout=60.0)
    try:
        client.send({"op": "pause"})

        player = json.loads((ROOT / "wflevels" / "cuckoo_village" / "actor-map.json").read_text())["indices"]["Player"]
        client.watch(idx=player, mailbox=TIME_MBX)

        def clock() -> float:
            with client._lock:
                return client.mailbox_values.get((player, TIME_MBX), float("nan"))

        def step(n: int) -> None:
            start = clock()
            client.send({"op": "step", "frames": n})
            until = time.monotonic() + 120
            while time.monotonic() < until:
                if proc.poll() is not None:
                    raise RuntimeError(f"engine exited; see {log.name}")
                now = clock()
                if not math.isnan(now) and (math.isnan(start) or now >= start + n / 30.0 * 0.9):
                    return
                time.sleep(0.01)
            raise TimeoutError("frame step timed out")

        def shot(path: Path) -> None:
            client.send({"op": "screenshot", "filename": str(path)})
            r = client.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=60)
            if not r or r.get("op") != "screenshot_done":
                raise RuntimeError(f"screenshot failed: {r}")

        step(args.warm)
        if args.probe:
            indices = json.loads((ROOT / "wflevels" / "cuckoo_village" / "actor-map.json").read_text())["indices"]
            for name in ("Camera", "cs_wide", "LookAt"):
                for mb in (3009, 3010, 3011, 3012, 3013, 3014):
                    client.watch(idx=indices[name], mailbox=mb)
            step(1)
            for name in ("Camera", "cs_wide", "LookAt"):
                with client._lock:
                    vals = [client.mailbox_values.get((indices[name], mb), float("nan")) for mb in (3009, 3010, 3011, 3012, 3013, 3014)]
                print(f"{name:8s} pos {vals[0]:8.3f} {vals[1]:8.3f} {vals[2]:8.3f}  rot(rev) {vals[3]:7.4f} {vals[4]:7.4f} {vals[5]:7.4f}")
        for k in range(args.frames):
            shot(out / f"frame-{k:04d}.png")
            step(args.step)
        print(f"captured {args.frames} frames of {args.level.name} at {args.size} into {out}")
    finally:
        client.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
