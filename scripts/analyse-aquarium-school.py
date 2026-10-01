#!/usr/bin/env python3
"""analyse-aquarium-school.py: do the ten followers actually school? Measured on the real engine, in the aquarium level built with AQUARIUM_SCHOOL_N=10.

Drives the aquarium harness (wflevels/aquarium/run_aquarium_checks.py) at 20 ticks a second, reads school.fth's state out of the mailboxes
(fish f, slot s at 800 + 14 f + s: position, then a unit heading) and prints, per phase, the Couzin metrics of the followers (p_group: how aligned,
m_group: how much they rotate about their centre), the mean nearest-neighbour distance and distance to the leader (body lengths), and how well the
followers' headings line up with the leader's. Phases: REST (the fish idles: they should swarm), SWIM (the fish swims to and fro: they should school).

Usage: scripts/analyse-aquarium-school.py [--level PATH] [--port N] [-h]
"""
import argparse, math, os, shutil, stat, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
ap.add_argument("--level", default=str(REPO / "wflevels" / "aquarium-standalone.iff")); ap.add_argument("--port", type=int, default=7818)
ap.add_argument("--trace", action="store_true", help="print every sample"); ap.add_argument("--rest", type=int, default=400, help="ticks of rest"); ap.add_argument("--swim", type=int, default=600, help="ticks of swimming")
args = ap.parse_args()

work = Path(tempfile.mkdtemp(prefix="aqan-"))
real = next(p for p in (os.environ.get("WF_GAME"), str(REPO / "engine" / "wf_game")) if p and Path(p).exists())
os.environ.update(OUT=str(work), WF_BRIDGE_PORT=str(args.port), WF_GAME=real, ASAN_OPTIONS="detect_leaks=0")
os.environ["LD_LIBRARY_PATH"] = f"{Path(real).resolve().parent / 'libs'}:{os.environ.get('LD_LIBRARY_PATH', '')}"
sys.argv = sys.argv[:1]
sys.path.insert(0, str(REPO / "wflevels" / "aquarium")); sys.path.insert(0, str(REPO / "tests"))
import run_aquarium_checks as R                      # noqa: E402
import aquarium_constants as C                       # noqa: E402
import numpy as np                                   # noqa: E402

R.LEVEL_IFF = str(Path(args.level).resolve())
r = R.Run(); g = r.g
N = 11
g.watch([(r.dir, 800 + 14 * i + s) for i in range(N) for s in range(6)] + [(r.dir, 1024), (r.dir, 1023), (r.dir, 1031)])


def state():
    P = np.zeros((N, 3)); V = np.zeros((N, 3))
    for i in range(N):
        for k in range(3):
            P[i, k] = g.v(r.dir, 800 + 14 * i + k) or 0.0
            V[i, k] = g.v(r.dir, 800 + 14 * i + 3 + k) or 0.0
    return P, V


def metrics(P, V):
    F, FV = P[1:], V[1:]
    pg = float(np.linalg.norm(FV.mean(0)))
    c = F.mean(0); rc = F - c; rc /= np.maximum(np.linalg.norm(rc, axis=1, keepdims=True), 1e-9)
    mg = float(np.linalg.norm(np.cross(rc, FV).mean(0)))
    d = np.linalg.norm(F[:, None] - F[None], axis=-1); np.fill_diagonal(d, 1e9)
    lead = V[0] / max(np.linalg.norm(V[0]), 1e-9)
    return dict(p=pg, m=mg, nn=float(d.min(1).mean()), dl=float(np.linalg.norm(F - P[0], axis=1).mean()), al=float((FV * lead).sum(1).mean()))


def phase(name, ticks, drive=None):
    rows = []
    for t in range(0, ticks, 10):
        if drive: drive(t)
        g.step(10)
        P, V = state(); m = metrics(P, V); m["mode"] = g.v(r.dir, 1024) or 0; m["blend"] = g.v(r.dir, 1023) or 0; m["lead_speed"] = g.v(r.dir, 1031) or 0
        rows.append(m)
    last = rows[len(rows) // 2:]
    mean = lambda k: sum(x[k] for x in last) / len(last)
    print(f"{name:5s} (second half of {ticks} ticks): p_group {mean('p'):.2f}  m_group {mean('m'):.2f}  nearest neighbour {mean('nn'):.2f} BL  to leader {mean('dl'):.2f} BL  "
          f"alignment with leader {mean('al'):+.2f}  mode {mean('mode'):.2f} blend {mean('blend'):.2f}  leader speed {mean('lead_speed'):.2f} BL/s")
    return rows


def measure(rows, name, ticks):
    if args.trace:
        for i, x in enumerate(rows):
            print(f"  {name} t={i * 10:4d}: p {x['p']:.2f} m {x['m']:.2f} nn {x['nn']:.2f} to-leader {x['dl']:.2f} align {x['al']:+.2f} mode {x['mode']:.0f} blend {x['blend']:.2f} speed {x['lead_speed']:.2f}")
    last = rows[len(rows) // 2:]
    mean = lambda k: sum(x[k] for x in last) / len(last)
    print(f"{name:5s} (second half of {ticks} ticks): p_group {mean('p'):.2f}  m_group {mean('m'):.2f}  nearest neighbour {mean('nn'):.2f} BL  to leader {mean('dl'):.2f} BL  "
          f"alignment with leader {mean('al'):+.2f}  mode {mean('mode'):.2f} blend {mean('blend'):.2f}  leader speed {mean('lead_speed'):.2f} BL/s", flush=True)


def run(ticks, drive=None):
    rows = []
    for t in range(0, ticks, 10):
        if drive:
            drive(t)
        g.step(10)
        P, V = state(); m = metrics(P, V)
        m["mode"] = g.v(r.dir, 1024) or 0; m["blend"] = g.v(r.dir, 1023) or 0; m["lead_speed"] = g.v(r.dir, 1031) or 0
        rows.append(m)
    return rows


try:
    g.step(60)
    measure(run(args.rest), "REST", args.rest)
    # SWIM: right for 6 s, then left for 6 s, repeating, held with the injected D-pad
    measure(run(args.swim, lambda t: g.inject(R.BTN["RIGHT"] if (t // 120) % 2 == 0 else R.BTN["LEFT"]) if t % 120 == 0 else None), "SWIM", args.swim)
    g.inject(0)
finally:
    g.close()
