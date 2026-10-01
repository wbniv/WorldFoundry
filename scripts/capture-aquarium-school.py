#!/usr/bin/env python3
"""capture-aquarium-school.py: screenshots of the aquarium WITH the ten followers (the level built by AQUARIUM_SCHOOL_N=10) on this PC.

Drives the aquarium harness (wflevels/aquarium/run_aquarium_checks.py) against wflevels/aquarium_school-standalone.iff: lets the school settle
(they swarm round the resting player's fish), swims the player's fish across the tank (they school behind it), then rests it again.
Writes OUTDIR/school-{rest,swim,rest2}.png, 1920x1080.

Usage: scripts/capture-aquarium-school.py OUTDIR [--port N] [-h]
"""
import argparse, os, shutil, stat, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
ap.add_argument("outdir"); ap.add_argument("--port", type=int, default=7817)
args = ap.parse_args()
out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)

work = Path(tempfile.mkdtemp(prefix="aqschool-"))
real = next(p for p in (os.environ.get("WF_GAME"), str(REPO / "engine" / "wf_game")) if p and Path(p).exists())
wrapper = work / "wf_game"
wrapper.write_text(f'#!/bin/sh\nexec "{real}" -width=1920 -height=1080 "$@"\n')
wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
os.environ.update(OUT=str(work), WF_BRIDGE_PORT=str(args.port), WF_GAME=str(wrapper), ASAN_OPTIONS="detect_leaks=0")
os.environ["LD_LIBRARY_PATH"] = f"{Path(real).resolve().parent / 'libs'}:{os.environ.get('LD_LIBRARY_PATH', '')}"
sys.argv = sys.argv[:1]
sys.path.insert(0, str(REPO / "wflevels" / "aquarium")); sys.path.insert(0, str(REPO / "tests"))
import run_aquarium_checks as R                      # noqa: E402
import aquarium_constants as C                       # noqa: E402

R.LEVEL_IFF = str(REPO / "wflevels" / "aquarium_school-standalone.iff")
r = R.Run(); g = r.g


def shot(name):
    fn = g.shot(name)
    p = Path(fn if os.path.isabs(fn) else work / fn)
    if not p.exists():
        c = sorted(work.glob(f"**/{name}*.png")); p = c[-1] if c else p
    shutil.copy(p, out / f"{name}.png"); print("wrote", out / f"{name}.png")


try:
    g.step(240)                                       # 4 s: the followers settle round the resting fish
    shot("school-rest")
    x, y, z = r.pos()
    R.navigate(r, (3.5, y, z), lambda: g.v(r.dir, r.mb["aq-speed"]) or 0.0, C.TAU_GLIDE)   # swim across
    shot("school-swim")
    g.inject(0)
    g.step(180)
    shot("school-rest2")
finally:
    g.close()
