#!/usr/bin/env python3
"""capture_idle_strip.py — real engine frames of the clownfish idle, tiled for the plan.

Runs wf_game once per frame with `-rate20 --capture-frame=N` (one capture per run is all
the flag supports) across one bob period, crops the fish and tiles the crops with their
tick numbers. Optionally tiles the debug-bridge screenshots that tests/test_aquarium_idle.py
leaves in ~/tmp/aquarium-idle (turn, swim, probe) into a second strip.

    python3 wflevels/aquarium_idle/capture_idle_strip.py [--out-dir DIR] [--first 60] [--step 7] [--count 8]

Needs a display, engine/wf_game and wflevels/aquarium_idle-standalone.iff (task aquarium-idle-level).
Plan: docs/plans/2026-09-30-clownfish-idle-animation.md
"""
import argparse
import os
import resource
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
WF = REPO / "engine" / "wf_game"
IFF = REPO / "wflevels" / "aquarium_idle-standalone.iff"
SHOTS = Path.home() / "tmp" / "aquarium-idle"
CROP = (130, 130, 490, 320)          # fish region of the 640×480 side-on frame

ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
ap.add_argument("--out-dir", default=str(REPO / "docs" / "plans" / "2026-09-30-clownfish-idle-animation"))
ap.add_argument("--first", type=int, default=60, help="first tick (idle has ramped in by ~24)")
ap.add_argument("--step", type=int, default=7, help="ticks between frames (0.35 s at -rate20)")
ap.add_argument("--count", type=int, default=8)
args = ap.parse_args()
out = Path(args.out_dir)
work = SHOTS / "strip"
work.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, LD_LIBRARY_PATH=str(REPO / "engine" / "libs"))


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


frames = []
for k in range(args.count):
    n = args.first + k * args.step
    png = work / f"f{n:03d}.png"
    png.unlink(missing_ok=True)
    subprocess.run([str(WF), f"--frame-step-smoke={n + 3}", "--cycles=1", "-rate20", "-record_video",
                    f"--capture-frame={n}={png}", f"-L{IFF}"],
                   cwd=str(REPO / "wfsource" / "source" / "game"), env=env, preexec_fn=no_core,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180, check=False)
    if not png.exists():
        sys.exit(f"no capture for frame {n} ({png})")
    frames.append((n, Image.open(png).convert("RGB").crop(CROP)))
    print(f"frame {n}: {png}")


def tile(items, cols, path, label_h=22):
    w, h = items[0][1].size
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols + 1) * 6, rows * (h + label_h) + (rows + 1) * 6), (13, 17, 23))
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(items):
        r, c = divmod(i, cols)
        x, y = 6 + c * (w + 6), 6 + r * (h + label_h + 6)
        sheet.paste(im, (x, y + label_h))
        d.text((x + 4, y + 5), label, fill=(230, 237, 243))
    sheet.save(path, optimize=True)
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


tile([(f"tick {n}  t = {n * 0.05:.2f} s", im) for n, im in frames], 4, out / "engine-idle-strip.png")

states = [("turn-mid.png", "LEFT held, 4 ticks: mid-turn"), ("swim-left.png", "swimming -x"),
          ("swim-right.png", "swimming +x"), ("probe.png", "probe: ROTATION_C 0.125 on Physics / statplat / platform")]
have = [(label, Image.open(SHOTS / f).convert("RGB")) for f, label in states if (SHOTS / f).exists()]
if len(have) == len(states):
    tile([(label, im.resize((400, 300))) for label, im in have], 2, out / "engine-states.png")
else:
    print(f"skipped engine-states.png: run tests/test_aquarium_idle.py first ({SHOTS})")
