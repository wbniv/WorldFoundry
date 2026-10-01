"""sweep.py: compute the poster's phase diagram (p_group, m_group, fragmentation over the zone widths dro x dra) and the hysteresis sweep,
with couzin.py. Writes sweep.json next to this file. Parameters are the paper's Fig. 3 values (N=100); fewer replicates and steps than the paper (it used 30),
so the numbers are noisier: the poster says so.
Usage: python3 sweep.py [--reps 3] [--steps 700] [-h]
"""
import argparse, json, multiprocessing as mp, sys, time
from pathlib import Path
import numpy as np
import couzin as C

GRID = [0, 1, 2, 3, 4, 6, 8, 10, 12, 15]

def cell(args):
    dro, dra, reps, steps = args
    ps, ms, fr = [], [], 0
    for k in range(reps):
        _, _, p, m, f = C.run(float(dro), float(dra), steps=steps, seed=100 + k)
        ps.append(p); ms.append(m); fr += bool(f)
    return dict(dro=dro, dra=dra, p=float(np.mean(ps)), m=float(np.mean(ms)), frag=fr / reps)

def hysteresis(args):
    """Sweep dro up then down at a fixed dra, carrying the group's state along (the paper's collective memory)."""
    dra, steps_each, ladder = args
    rng = np.random.default_rng(7)
    pos, vel = C.init(100, rng)
    out = []
    for direction, seq in (("up", ladder), ("down", ladder[::-1])):
        for dro in seq:
            ps = []
            for t in range(steps_each):
                pos, vel = C.step(pos, vel, float(dro), float(dra), rng)
                if t >= steps_each - 60:
                    ps.append(C.metrics(pos, vel))
            out.append(dict(dir=direction, dro=dro, p=float(np.mean([a for a, b in ps])), m=float(np.mean([b for a, b in ps]))))
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--reps", type=int, default=3); ap.add_argument("--steps", type=int, default=700)
    a = ap.parse_args()
    t0 = time.time()
    jobs = [(x, y, a.reps, a.steps) for y in GRID for x in GRID]
    with mp.Pool(mp.cpu_count()) as pool:
        cells = pool.map(cell, jobs, chunksize=1)
        hyst = pool.map(hysteresis, [(8, 350, [0, 1, 2, 3, 4, 5, 6, 7, 8, 10]), (4, 350, [0, 1, 2, 3, 4, 5, 6, 7, 8, 10])])
    Path(__file__).with_name("sweep.json").write_text(json.dumps(dict(grid=GRID, cells=cells, hysteresis=dict(dra8=hyst[0], dra4=hyst[1]), reps=a.reps, steps=a.steps, seconds=round(time.time() - t0)), indent=1))
    print("wrote sweep.json in", round(time.time() - t0), "s")
