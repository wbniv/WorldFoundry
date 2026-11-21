#!/usr/bin/env python3
"""Minute Machine on the desktop engine: captures at chosen times, and engine against reference.

Run inside the Linux container, against the container-built engine, under xvfb:

  scripts/in-linux-container.sh scripts/build-wf-game-container.sh --dev
  WF_CONTAINER_ENV="WF_GAME=/build/wf-game-dev/src/engine/wf_game" scripts/in-linux-container.sh \
    bash -c 'timeout 900 xvfb-run -a -s "-screen 0 1280x720x24" python3 scripts/check-minute-machine.py --compare'

  --compare            freeze the wall clock at several times, read every posed actor's position,
                       rotation and scale from the engine, and compare each with
                       wflevels/minute_machine/timeline.py (1 mm, 0.5 degrees, 0.1 % scale)
  --capture OUTDIR     one PNG per --times entry (default: the plan's six moments)
  --times T [T ...]    HH:MM:SS[.mmm] clock times for either mode

Plan: docs/plans/2026-11-21-sixty-second-chain-reaction.md (Verification 5 to 7).
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
sys.path.insert(0, str(ROOT / "wflevels" / "minute_machine"))
import forth  # noqa: E402
from debug_bridge_client import BridgeClient  # noqa: E402
import timeline as tl  # noqa: E402

WF_GAME = Path(os.environ.get("WF_GAME", ROOT / "engine" / "wf_game"))
LEVEL = ROOT / "wflevels" / "minute_machine-standalone.iff"
GAME_CWD = ROOT / "wfsource" / "source" / "game"
# mailboxes of an actor: position, rotation (revolutions), scale
X_POS, Y_POS, Z_POS, ROT_A, ROT_B, ROT_C, X_SCALE, Y_SCALE, Z_SCALE = 3009, 3010, 3011, 3012, 3013, 3014, 3040, 3041, 3042
FIELDS = (X_POS, Y_POS, Z_POS, ROT_A, ROT_B, ROT_C, X_SCALE, Y_SCALE, Z_SCALE)
TIME_MBX = 1906
MOMENTS = ["10:08:03", "10:08:15.2", "10:08:38", "10:08:57.6", "10:09:00.3", "13:00:00.4"]
COMPARE = ["10:08:22", "10:08:41.5", "10:08:57", "12:59:59.9", "13:00:00.3", "13:00:00.9", "00:00:00.6", "23:59:59.95"]
FRAME = 3276 / 65536      # the level clock advances this much per stepped frame at -rate20


def player_index() -> int:
    return json.loads((ROOT / "wflevels" / "minute_machine" / "actor-map.json").read_text())["indices"]["Player"]


def sod(spec: str) -> float:
    h, m, s = spec.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


class Engine:
    def __init__(self, clock: str, port: int):
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = f"{ROOT / 'engine' / 'libs'}:{env.get('LD_LIBRARY_PATH', '')}"
        env["LSAN_OPTIONS"] = "detect_leaks=0"
        env["WF_WALL_CLOCK"] = f"{clock}@0"
        self.log = open(ROOT / "tests" / f".wf_minute_machine_{port}.log", "w")
        self.proc = subprocess.Popen(
            [str(WF_GAME), f"-L{LEVEL}", "-width=1280", "-height=720", "-rate20",
             "--debug-port", str(port), "--debug-bind", "127.0.0.1"],
            cwd=str(GAME_CWD), env=env, stdout=self.log, stderr=subprocess.STDOUT,
            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
        self.client = BridgeClient("127.0.0.1", port, timeout=40.0)
        self.client.send({"op": "pause"})
        self.clock_actor = player_index()
        self.client.watch(idx=self.clock_actor, mailbox=TIME_MBX)

    def value(self, actor: int, mailbox: int) -> float:
        with self.client._lock:
            return self.client.mailbox_values.get((actor, mailbox), float("nan"))

    def step(self, frames: int) -> None:
        start = self.value(self.clock_actor, TIME_MBX)
        self.client.send({"op": "step", "frames": frames})
        until = time.monotonic() + 90
        while time.monotonic() < until:
            if self.proc.poll() is not None:
                raise RuntimeError(f"engine exited; see {self.log.name}")
            now = self.value(self.clock_actor, TIME_MBX)
            if not math.isnan(now) and (math.isnan(start) or now >= start + frames * FRAME - 2e-4):
                time.sleep(0.05)
                return
            time.sleep(0.01)
        raise TimeoutError("frame step timed out")

    def screenshot(self, path: Path) -> None:
        self.client.send({"op": "screenshot", "filename": str(path)})
        response = self.client.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=30)
        if not response or response.get("op") != "screenshot_done":
            raise RuntimeError(f"screenshot failed: {response}")

    def close(self) -> None:
        try:
            self.client.close()
        finally:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
            self.log.close()


def capture(outdir: Path, times: list[str], port: int) -> int:
    outdir = outdir.resolve()          # the engine runs from another directory
    outdir.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(times):
        e = Engine(spec, port + i)
        try:
            e.step(8)
            name = spec.replace(":", "")
            e.screenshot(outdir / f"{name}.png")
            print(f"captured {spec} -> {outdir / (name + '.png')}")
        finally:
            e.close()
    return 0


def compare(times: list[str], port: int) -> int:
    indices = json.loads((ROOT / "wflevels" / "minute_machine" / "actor-map.json").read_text())["indices"]
    failures = []
    for i, spec in enumerate(times):
        e = Engine(spec, port + i)
        try:
            poses = tl.all_poses(sod(spec))
            worst = {"pos": (0.0, ""), "rot": (0.0, ""), "scale": (0.0, "")}
            names = list(poses)
            # The bridge broadcasts a watch's first value in one write, and a batch of hundreds of
            # mailboxes at once loses its tail. Watch a dozen actors at a time.
            for g in range(0, len(names), 10):
                group = names[g:g + 10]
                watched = [(indices[forth.ACTOR_OF.get(name, name)], mbx) for name in group for mbx in FIELDS]
                for actor, mbx in watched:
                    e.client.watch(idx=actor, mailbox=mbx)
                e.step(3)
                # wait for the signal that every watched value has arrived; the deadline is only the failure guard
                end = time.monotonic() + 10.0
                while time.monotonic() < end and any(math.isnan(e.value(a, m)) for a, m in watched):
                    time.sleep(0.02)
                for name in group:
                    p = poses[name]
                    got = {mbx: e.value(indices[forth.ACTOR_OF.get(name, name)], mbx) for mbx in FIELDS}
                    want = dict(zip(FIELDS, p))
                    for mbx in FIELDS:
                        if math.isnan(got[mbx]):
                            failures.append(f"{spec} {name}: mailbox {mbx} never reported")
                            continue
                        d = abs(got[mbx] - want[mbx])
                        if mbx in (ROT_A, ROT_B, ROT_C):
                            d = abs((got[mbx] - want[mbx] + .5) % 1.0 - .5)          # revolutions, modulo 1
                            kind, limit = "rot", .5 / 360
                        elif mbx in (X_SCALE, Y_SCALE, Z_SCALE):
                            kind, limit = "scale", 1e-3 * max(1.0, abs(want[mbx])) + 2e-4
                        else:
                            kind, limit = "pos", 1e-3
                        if d > worst[kind][0]:
                            worst[kind] = (d, f"{name}/{mbx}")
                        if d > limit:
                            failures.append(f"{spec} {name} mailbox {mbx}: engine {got[mbx]:.6f} reference {want[mbx]:.6f} (off {d:.6f})")
                for actor, mbx in watched:
                    e.client.unwatch(idx=actor, mailbox=mbx)
            print(f"{spec}: {len(poses)} actors; worst position {worst['pos'][0]*1000:.3f} mm ({worst['pos'][1]}), "
                  f"rotation {worst['rot'][0]*360:.3f} deg ({worst['rot'][1]}), scale {worst['scale'][0]:.5f} ({worst['scale'][1]})")
        finally:
            e.close()
    for line in failures[:40]:
        print("FAIL", line)
    print("PASS" if not failures else f"FAIL: {len(failures)} mismatches")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--capture", type=Path, metavar="OUTDIR")
    ap.add_argument("--times", nargs="+")
    ap.add_argument("--port", type=int, default=7810)
    args = ap.parse_args()
    if not WF_GAME.exists():
        print(f"wf_game not built: {WF_GAME}", file=sys.stderr)
        return 2
    if not LEVEL.exists():
        print(f"level not built: {LEVEL} (task minute-machine-level)", file=sys.stderr)
        return 2
    if args.capture:
        return capture(args.capture, args.times or MOMENTS, args.port)
    if args.compare:
        return compare(args.times or COMPARE, args.port)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
