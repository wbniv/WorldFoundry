#!/usr/bin/env python3
"""Tide Harbour on the desktop engine: the director against the model, the settings, and captures.

Run inside the Linux container, against the container-built engine, under xvfb:

  scripts/in-linux-container.sh scripts/build-wf-game-container.sh --dev
  WF_CONTAINER_ENV="WF_GAME=/build/wf-game-dev/src/engine/wf_game" scripts/in-linux-container.sh \\
    bash -c 'timeout 1500 xvfb-run -a -s "-screen 0 1280x720x24" python3 scripts/check-tide-harbour.py --compare'

  --compare            freeze the wall clock (WF_WALL_CLOCK, dated) at eight dates and times, read every posed
                       actor's position, rotation and scale, the tide cell and the visibility cells from the
                       engine, and compare each with wflevels/tide_harbour/timeline.py (1 mm, 0.5 degrees,
                       0.1 % scale; the tide within 1 cm)
  --options            for every value of every setting, start the engine with it as a launch override
                       (--property="TideHarbourSettings.<field>=<value>", the path the Dream's saved settings take),
                       and compare the camera, the visibility cells and the settings cells with the model; the
                       director's count of fields property@ answered must be 4 (plan Verification 13, engine half)
  --capture OUTDIR     one PNG per --times entry (default: the plan's six moments)
  --times T [T ...]    YYYY-MM-DDTHH:MM:SS[.mmm] Thai times for either mode
  --no-fps             with --capture: hide the engine's frame-rate counter (the poster's picture)

The colours the director writes (FACE_COLOR 3037-3039) are write-only in the engine, so they are checked in the
VM (tests/verify_tide_harbour_forth.py) and seen in the captures. Plan: docs/plans/2026-11-21-tide-harbour-clock.md
(Verification 3, 8 and 13).
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
sys.path.insert(0, str(ROOT / "wflevels" / "tide_harbour"))
import forth  # noqa: E402
from debug_bridge_client import BridgeClient  # noqa: E402
import timeline as tl  # noqa: E402

WF_GAME = Path(os.environ.get("WF_GAME", ROOT / "engine" / "wf_game"))
LEVEL = ROOT / "wflevels" / "tide_harbour-standalone.iff"
GAME_CWD = ROOT / "wfsource" / "source" / "game"
X_POS, Y_POS, Z_POS, ROT_A, ROT_B, ROT_C, X_SCALE, Y_SCALE, Z_SCALE = 3009, 3010, 3011, 3012, 3013, 3014, 3040, 3041, 3042
FIELDS = (X_POS, Y_POS, Z_POS, ROT_A, ROT_B, ROT_C, X_SCALE, Y_SCALE, Z_SCALE)
TIME_MBX = 1906
TIDE_CELL = 600 + forth.CELLS.index("tide")
ANSWERED_CELL = 600 + forth.CELLS.index("sv")
# The plan's six moments (the mockups): dawn at low tide (1.36 m), noon, the sunset of the concept art, dusk, night (1.96 m),
# deep night at another tide (2.56 m)
MOMENTS = ["2026-11-17T06:20:00", "2026-11-21T12:00:00", "2026-11-21T17:38:00", "2026-11-21T18:10:00",
           "2026-11-21T21:30:00", "2026-11-24T04:40:00"]
COMPARE = ["2026-11-21T10:08:22", "2026-11-21T17:40:00", "2026-11-21T18:12:30.5", "2026-11-21T23:59:59.9",
           "2026-11-22T00:00:00.4", "2027-03-02T02:45:00", "2026-06-21T18:30:12", "2030-07-04T16:20:05.5"]
SETTLE = 200              # frames before a comparison: the camera eases towards its shot (about 10 % of the way a frame, so 200
                          # frames leave nothing) and the river panel, pinned to the camera and the next-turn scan, has caught up
FRAME = 3276 / 65536      # the level clock advances this much per stepped frame at -rate20
WRAP = {**{f"cloud_{i}": tl.CLOUD_SPAN for i in range(len(tl.CLOUDS))}, **{f"bird_{i}": tl.BIRD_SPAN for i in range(len(tl.BIRDS))},
        "boat_3": tl.FERRY_SPAN}


def indices() -> dict:
    return json.loads((ROOT / "wflevels" / "tide_harbour" / "actor-map.json").read_text())["indices"]


class Engine:
    def __init__(self, when: str, port: int, extra: list[str] | None = None):
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = f"{ROOT / 'engine' / 'libs'}:{env.get('LD_LIBRARY_PATH', '')}"
        env["LSAN_OPTIONS"] = "detect_leaks=0"
        env["WF_WALL_CLOCK"] = f"{when}+07:00@0"
        self.log = open(ROOT / "tests" / f".wf_tide_harbour_{port}.log", "w")
        self.proc = subprocess.Popen(
            [str(WF_GAME), f"-L{LEVEL}", "-width=1280", "-height=720", "-rate20",
             "--debug-port", str(port), "--debug-bind", "127.0.0.1", *(extra or [])],
            cwd=str(GAME_CWD), env=env, stdout=self.log, stderr=subprocess.STDOUT,
            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
        self.client = BridgeClient("127.0.0.1", port, timeout=60.0)
        self.client.send({"op": "pause"})
        self.clock_actor = indices()["Player"]
        self.client.watch(idx=self.clock_actor, mailbox=TIME_MBX)

    def value(self, actor: int, mailbox: int) -> float:
        with self.client._lock:
            return self.client.mailbox_values.get((actor, mailbox), float("nan"))

    def step(self, frames: int) -> None:
        start = self.value(self.clock_actor, TIME_MBX)
        if math.isnan(start):
            # the clock has not reported yet (the watch was only just set), so there is no start to count frames from and the
            # wait below would return at the first value: that made every 'step(N)' of a fresh engine about one frame long
            # (found 2026-11-21: the camera was still easing in and the next-turn scan unfinished in every capture)
            self.client.send({"op": "step", "frames": 1})
            until = time.monotonic() + 60
            while math.isnan(self.value(self.clock_actor, TIME_MBX)):
                if time.monotonic() > until or self.proc.poll() is not None:
                    raise TimeoutError("the level clock never reported")
                time.sleep(0.01)
            frames = max(frames - 1, 0)
            start = self.value(self.clock_actor, TIME_MBX)
            if frames == 0:
                return
        self.client.send({"op": "step", "frames": frames})
        until = time.monotonic() + 120
        while time.monotonic() < until:
            if self.proc.poll() is not None:
                raise RuntimeError(f"engine exited; see {self.log.name}")
            now = self.value(self.clock_actor, TIME_MBX)
            if not math.isnan(now) and (math.isnan(start) or now >= start + frames * FRAME - 2e-4):
                time.sleep(0.05)
                return
            time.sleep(0.01)
        raise TimeoutError("frame step timed out")

    def read(self, watched: list[tuple[int, int]], frames: int = 3) -> dict:
        for actor, mbx in watched:
            self.client.watch(idx=actor, mailbox=mbx)
        self.step(frames)
        end = time.monotonic() + 15.0              # the failure guard; the success path is every value arriving
        while time.monotonic() < end and any(math.isnan(self.value(a, m)) for a, m in watched):
            time.sleep(0.02)
        got = {(a, m): self.value(a, m) for a, m in watched}
        for actor, mbx in watched:
            self.client.unwatch(idx=actor, mailbox=mbx)
            with self.client._lock:
                self.client.mailbox_values.pop((actor, mbx), None)
        return got

    def screenshot(self, path: Path) -> None:
        self.client.send({"op": "screenshot", "filename": str(path)})
        response = self.client.wait_for(lambda m: m.get("op") in ("screenshot_done", "error"), timeout=60)
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


def check_scene(e: Engine, spec: str, options: dict | None, names: list[str] | None, failures: list[str]) -> dict:
    ix = indices()
    day, sod = tl.parse_when(spec)
    # the engine's clock has advanced by the frames stepped so far; the model is asked about the same instant
    sc = tl.scene(day, sod, options)
    worst = {"pos": (0.0, ""), "rot": (0.0, ""), "scale": (0.0, "")}
    names = names or list(sc.poses)
    # The bridge broadcasts a watch's first value in one write; a batch of hundreds of mailboxes loses its tail.
    for g in range(0, len(names), 10):
        group = names[g:g + 10]
        got = e.read([(ix[n], m) for n in group for m in FIELDS], frames=1)
        for n in group:
            for mbx, want in zip(FIELDS, sc.poses[n]):
                v = got[(ix[n], mbx)]
                if math.isnan(v):
                    failures.append(f"{spec} {n}: mailbox {mbx} never reported")
                    continue
                d = abs(v - want)
                if mbx in (ROT_A, ROT_B, ROT_C):
                    d, kind, limit = abs((v - want + .5) % 1.0 - .5), "rot", .5 / 360
                elif mbx in (X_SCALE, Y_SCALE, Z_SCALE):
                    kind, limit = "scale", 1e-3 * max(1.0, abs(want)) + 2e-4
                else:
                    kind, limit = "pos", 1e-3
                    if mbx == X_POS and n in WRAP:
                        d = min(d, abs(d - WRAP[n]))
                if d > worst[kind][0]:
                    worst[kind] = (d, f"{n}/{mbx}")
                if d > limit:
                    failures.append(f"{spec} {options or ''} {n} mailbox {mbx}: engine {v:.6f} reference {want:.6f} (off {d:.6f})")
    cells = ([(ix["Player"], TIDE_CELL), (ix["Player"], ANSWERED_CELL)] + [(ix["Player"], c) for c in sc.visible]
             + [(ix["Player"], c) for c in tl.OPTION_CELLS.values()])
    got = e.read(cells, frames=1)
    answered = got[(ix["Player"], ANSWERED_CELL)]
    if answered != len(tl.FIELD_LABELS):
        failures.append(f"{spec} {options or ''}: property@ answered {answered} of {len(tl.FIELD_LABELS)} TideHarbourSettings fields")
    for name, cell in tl.OPTION_CELLS.items():
        want = (options or {}).get(name, 0)
        if got[(ix["Player"], cell)] != want:
            failures.append(f"{spec} {options or ''} setting {name} (cell {cell}): engine {got[(ix['Player'], cell)]} wanted {want}")
    tide = got[(ix["Player"], TIDE_CELL)]
    if not abs(tide - sc.tide) <= 0.01:
        failures.append(f"{spec} tide: engine {tide:.5f} reference {sc.tide:.5f}")
    for cell, want in sc.visible.items():
        if got[(ix["Player"], cell)] != want:
            failures.append(f"{spec} {options or ''} visibility {cell}: engine {got[(ix['Player'], cell)]} reference {want}")
    print(f"{spec} {options or ''}: {len(names)} actors; settings answered {answered:g}; tide {tide:.4f} m (model {sc.tide:.4f}); worst position "
          f"{worst['pos'][0]*1000:.3f} mm ({worst['pos'][1]}), rotation {worst['rot'][0]*360:.3f} deg ({worst['rot'][1]}), "
          f"scale {worst['scale'][0]:.5f} ({worst['scale'][1]})", flush=True)
    return sc.visible


def compare(times: list[str], port: int) -> int:
    failures: list[str] = []
    for i, spec in enumerate(times):
        e = Engine(spec, port + i)
        try:
            e.step(SETTLE)         # the wall clock is frozen, so the model's time does not move while the engine settles
            check_scene(e, spec, None, None, failures)
        finally:
            e.close()
    for line in failures[:40]:
        print("FAIL", line)
    print("PASS" if not failures else f"FAIL: {len(failures)} mismatches")
    return 1 if failures else 0


def options(port: int) -> int:
    """Each setting's every value as a launch override of the level's TideHarbourSettings object."""
    failures: list[str] = []
    spec = "2026-11-21T15:02:30"
    touched = ["cs_wide", "LookAt"] + [f"boat_{i}" for i in range(4)]
    k = 0
    for name, values in tl.OPTIONS.items():
        for value in range(len(values)):
            e = Engine(spec, port + k, [f"--property={tl.SETTINGS_ACTOR}.{tl.FIELD_LABELS[name]}={value}"])
            k += 1
            try:
                e.step(4)
                check_scene(e, spec, {name: value}, touched, failures)
            finally:
                e.close()
    for line in failures[:40]:
        print("FAIL", line)
    print("PASS" if not failures else f"FAIL: {len(failures)} mismatches")
    return 1 if failures else 0


def capture(outdir: Path, times: list[str], port: int, frames: int = 40, no_fps: bool = False) -> int:
    outdir = outdir.resolve()          # the engine runs from another directory
    outdir.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(times):
        e = Engine(spec, port + i, ["--no-fps"] if no_fps else None)
        try:
            e.step(frames)          # enough for the next-turn scan (ten frames) and the panel to settle
            name = spec.replace(":", "").replace("-", "")
            e.screenshot(outdir / f"{name}.png")
            print(f"captured {spec} -> {outdir / (name + '.png')}")
        finally:
            e.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--options", action="store_true")
    ap.add_argument("--capture", type=Path, metavar="OUTDIR")
    ap.add_argument("--times", nargs="+")
    ap.add_argument("--frames", type=int, default=40, help="frames to step before each capture (default 40)")
    ap.add_argument("--no-fps", action="store_true", help="--capture: hide the engine's frame-rate counter (for the poster)")
    ap.add_argument("--port", type=int, default=7830)
    args = ap.parse_args()
    if not WF_GAME.exists():
        print(f"wf_game not built: {WF_GAME}", file=sys.stderr)
        return 2
    if not LEVEL.exists():
        print(f"level not built: {LEVEL} (task tide-harbour-level)", file=sys.stderr)
        return 2
    if args.capture:
        return capture(args.capture, args.times or MOMENTS, args.port, args.frames, args.no_fps)
    rc = 0
    if args.compare:
        rc |= compare(args.times or COMPARE, args.port)
    if args.options:
        rc |= options(args.port + 50)
    if not (args.compare or args.options):
        ap.print_help()
        return 2
    return rc


if __name__ == "__main__":
    sys.exit(main())
