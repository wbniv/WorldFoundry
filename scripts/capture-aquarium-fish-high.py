#!/usr/bin/env python3
"""capture-aquarium-fish-high.py: capture the aquarium's camshot B (the fish resting in the anemone's crown) with the fish HIGHER.

Drives the aquarium harness (wflevels/aquarium/run_aquarium_checks.py), the same way tests/record_aquarium_motion_demo.py steers the fish
into the crown with held buttons, but aims DZ metres above the crown's host point, rests there, and takes the screenshot at 1920x1080 (the
engine is started through a wrapper that adds -width/-height). Used for the launcher icon: "move the fish up a bit higher, relative to the anemone".

Usage: scripts/capture-aquarium-fish-high.py OUT.png [--dz M] [--width W] [--height H] [-h]
"""
import argparse, os, shutil, stat, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
ap.add_argument("out"); ap.add_argument("--dz", type=float, default=0.5); ap.add_argument("--width", type=int, default=1920); ap.add_argument("--height", type=int, default=1080)
ap.add_argument("--port", type=int, default=7816)
args = ap.parse_args()

work = Path(tempfile.mkdtemp(prefix="aqhigh-"))
real = next(p for p in (os.environ.get("WF_GAME"), str(REPO / "engine" / "wf_game")) if p and Path(p).exists())
wrapper = work / "wf_game"
wrapper.write_text(f'#!/bin/sh\nexec "{real}" -width={args.width} -height={args.height} "$@"\n')
wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
os.environ.update(OUT=str(work), WF_BRIDGE_PORT=str(args.port), WF_GAME=str(wrapper))
os.environ["LD_LIBRARY_PATH"] = f"{Path(real).resolve().parent / 'libs'}:{os.environ.get('LD_LIBRARY_PATH', '')}"
sys.argv = sys.argv[:1]
sys.path.insert(0, str(REPO / "wflevels" / "aquarium")); sys.path.insert(0, str(REPO / "tests"))
import run_aquarium_checks as R                      # noqa: E402
import aquarium_constants as C                       # noqa: E402

r = R.Run(); g = r.g
try:
    g.step(30)
    x, y, z = R.host_point()
    R.navigate(r, (x, y, z + args.dz), lambda: g.v(r.dir, r.mb["aq-speed"]) or 0.0, C.TAU_GLIDE)
    g.inject(0)
    for _ in range(round(3.0 / R.DT)):
        g.step(1)
    pos = r.pos()
    fn = g.shot("fish-high")
    print(f"fish at {tuple(round(v, 3) for v in pos)} (host point {(x, y, z)}); shot {fn}")
    shot = Path(fn if os.path.isabs(fn) else work / fn)
    if not shot.exists():
        cands = sorted(work.glob("**/fish-high*.png")); shot = cands[-1] if cands else shot
    shutil.copy(shot, args.out)
finally:
    g.close()
sys.exit(0 if Path(args.out).exists() else 1)
