#!/usr/bin/env python3
"""Run a Tide Harbour spike level in the container engine: director sanity, frame pacing, screenshots.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md, Phase 0. In the Linux container, under xvfb, against the container-built engine:

  scripts/in-linux-container.sh scripts/build-wf-game-container.sh --dev
  WF_CONTAINER_ENV="WF_GAME=/build/wf-game-dev/src/engine/wf_game" scripts/in-linux-container.sh \
    bash -c 'timeout 500 xvfb-run -a -s "-screen 0 1280x720x24" python3 wflevels/tide_spike/run_desktop.py --variant d'

Software GL is not a Chromecast: absolute frame times mean nothing here. The look (banding, the veils) and the director's
correctness do, and so does the cost of one variant against another. Waits are on signals: the director's own time cell, and the
engine's TIME mailbox for the fast day of variant d.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from debug_bridge_client import BridgeClient  # noqa: E402
import spike as sp  # noqa: E402

WF_GAME = Path(os.environ.get("WF_GAME", ROOT / "engine" / "wf_game"))
GAME_CWD = ROOT / "wfsource" / "source" / "game"
TIME_MBX, TS_T, TS_H, TS_TIDE, TS_D, TS_K = 1906, 600, 601, 607, 605, 604
Z_POS = 3011


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--variant", default="c", choices=sorted(sp.VARIANTS))
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "shots")
    ap.add_argument("--hours", default="6,12,17,18.25,19.5,23,5", help="variant d: hours of the fast day to photograph")
    ap.add_argument("--port", type=int, default=7840)
    ap.add_argument("--seconds", type=float, default=6.0, help="how long to measure frame pacing")
    args = ap.parse_args()
    level = ROOT / "wflevels" / f"tide_spike_{args.variant}-standalone.iff"
    amap = json.loads((ROOT / "wflevels" / f"tide_spike_{args.variant}" / "actor-map.json").read_text())["indices"]
    watcher = amap["Player"]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = f"{ROOT / 'engine' / 'libs'}:{env.get('LD_LIBRARY_PATH', '')}"
    env["LSAN_OPTIONS"] = "detect_leaks=0"
    log_path = args.out_dir / f"engine-{args.variant}.log"
    log = open(log_path, "w")
    proc = subprocess.Popen([str(WF_GAME), f"-L{level}", "-width=1280", "-height=720", "--debug-port", str(args.port), "--debug-bind", "127.0.0.1"],
                            cwd=str(GAME_CWD), env=env, stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
    cli = BridgeClient("127.0.0.1", args.port, timeout=60.0)
    result = {"variant": args.variant, "posed_actors": sp.VARIANTS[args.variant]}
    try:
        def value(mbx):
            with cli._lock:
                return cli.mailbox_values.get((watcher, mbx))

        def wait_for(pred, timeout=60.0):
            end = time.monotonic() + timeout                     # a failure guard, never the success path
            while time.monotonic() < end:
                if pred():
                    return True
                time.sleep(0.01)
            return False

        for mbx in (TIME_MBX, TS_T, TS_H, TS_TIDE, TS_D, TS_K):
            cli.watch(idx=watcher, mailbox=mbx)
        bar = amap["bar_18"]
        cli.watch(idx=bar, mailbox=Z_POS)
        ok = wait_for(lambda: (value(TS_T) or 0) > 3.0)
        result["director_running"] = ok
        if not ok:
            print(json.dumps(result)); return 1
        # frame pacing from the engine's TIME mailbox: one new value per frame
        stamps, last = [], None
        end = time.monotonic() + args.seconds
        while time.monotonic() < end:
            v = value(TIME_MBX)
            if v is not None and v != last:
                stamps.append(time.monotonic()); last = v
            time.sleep(0.002)
        gaps = [(b - a) * 1000 for a, b in zip(stamps, stamps[1:])]
        result["frames_seen"] = len(stamps)
        result["frame_ms_median"] = round(statistics.median(gaps), 2) if gaps else None
        result["frame_ms_p90"] = round(sorted(gaps)[int(len(gaps) * .9)], 2) if len(gaps) > 10 else None
        # the pose really moves: bar 18's z changes over a second of engine time
        z0 = cli.mailbox_values.get((bar, Z_POS))
        t0 = value(TIME_MBX)
        wait_for(lambda: (value(TIME_MBX) or 0) > (t0 or 0) + 1.0)
        z1 = cli.mailbox_values.get((bar, Z_POS))
        result["bar_18_z_moved"] = z0 is not None and z1 is not None and abs(z1 - z0) > 1e-4

        def shot(name):
            path = args.out_dir / name
            cli.send({"op": "screenshot", "filename": str(path)})
            return bool(cli.wait_for(lambda m: m.get("op") == "screenshot_done", timeout=30))

        if args.variant != "d":
            result["screenshot"] = shot(f"spike_{args.variant}.png")
        else:
            shots = {}
            for h in [float(x) for x in args.hours.split(",")]:
                due = ((h - 6) % 24) * sp.DAY_SECONDS_PER_HOUR                  # engine seconds into the fast day
                cur = value(TIME_MBX) or 0
                target = due + 240.0 * (int(cur // 240) + (1 if cur % 240 > due else 0))
                if not wait_for(lambda: (value(TIME_MBX) or 0) >= target, timeout=300):
                    shots[str(h)] = "timeout"; continue
                shots[str(h)] = {"ok": shot(f"spike_d_{int(h):02d}{int(round((h % 1) * 60)):02d}.png"), "hour_cell": value(TS_H), "darkness": value(TS_D), "veil": value(TS_K)}
            result["shots"] = shots
        result["alive"] = proc.poll() is None
    finally:
        try:
            cli.close()
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
            log.close()
    text = log_path.read_text(errors="replace").lower()
    benign = ("do_assertions =", "cerror:")                  # a build-flags banner and a label the engine prints on every start
    result["log_problems"] = sum(1 for l in text.splitlines() if any(w in l for w in ("abort", "error", "unknown:", "assert")) and not any(b in l for b in benign))
    print(json.dumps(result, indent=1))
    return 0 if result.get("director_running") and result.get("alive", True) else 1


if __name__ == "__main__":
    sys.exit(main())
