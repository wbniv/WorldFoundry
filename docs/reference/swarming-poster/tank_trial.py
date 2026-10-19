"""tank_trial.py: the Forth core (school.fth) in the aquarium tank's real box with the leader circling, to see whether the followers stay with it.

Units are body lengths (BL, a fish is 3.5 in). The box is the tank's INNER width and depth and the water above the sand, read from
wflevels/aquarium/aquarium_constants.py: 47 x 12 x 16.5 in = 13.4 x 3.4 x 4.7 BL, so the school lives in a slab only 3.4 BL front to back.
The leader circles in the front-view (x, z) plane, as a player steering with the stick would.
"""
import math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import couzin, forth_check as fc
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'wflevels' / 'aquarium'))
import aquarium_constants as AC

STARTLE_R = 4.0
BOX = (AC.INT_X / AC.FISH_LEN / 2, AC.INT_Y / AC.FISH_LEN / 2, (AC.WATER_Z - AC.SAND_TOP) / AC.FISH_LEN / 2)   # half extents, BL


def trial(dro, dra, w, seed, ticks=900, leader_speed=1.5, leader_turn_deg_s=48.0, wall=0.9, startle_at=None, n=11, h=None, **over):
    p = dict(couzin.PAPER, **over)
    rng = np.random.default_rng(seed)
    h = h or fc.make_host()
    fc.load_school(h, n)
    fc.set_params(h, dict(p, sigma=0.0), dro, dra, w, wall=wall)
    for k, b in enumerate(BOX):
        h.write(fc.PAR + 11 + k, -b); h.write(fc.PAR + 14 + k, b)
    pos = (rng.random((n, 3)) * 2 - 1) * np.array(BOX) * 0.9
    vel, _ = couzin.unit(rng.normal(size=(n, 3)))
    R = leader_speed / math.radians(leader_turn_deg_s)                # the leader's circle radius
    vel[0] = [0, 0, 1]; pos[0] = [R, 0, 0]
    for i in range(n):
        fc.put(h, i, pos[i], vel[i])
    a = -math.radians(leader_turn_deg_s * p["tau"])
    ds, als, ps, trace = [], [], [], []
    for t in range(ticks):
        # the leader: written from outside every tick (the game writes the player's fish here)
        v = vel[0]; c, s = math.cos(a), math.sin(a)
        vel[0] = [c * v[0] + s * v[2], 0.0, -s * v[0] + c * v[2]]
        pos[0] = pos[0] + vel[0] * leader_speed * p["tau"]
        fc.put(h, 0, pos[0], vel[0])
        if startle_at is not None and t == startle_at:
            assert h.eval(f"{STARTLE_R} sch-startle-all") == "ok"
        assert h.eval("sch-tick") == "ok"
        fp, fv = fc.get(h, n)
        pos[1:], vel[1:] = fp[1:], fv[1:]
        trace.append(float(np.median(np.linalg.norm(pos[1:] - pos[0], axis=1))))
        if t >= ticks - 300:
            d = np.linalg.norm(pos[1:] - pos[0], axis=1)
            ds.append(np.median(d)); als.append((vel[1:] * vel[0]).sum(1).mean()); ps.append(couzin.metrics(pos[1:], vel[1:])[0])
    out = dict(dist=float(np.mean(ds)), align=float(np.mean(als)), p_followers=float(np.mean(ps)), inside=bool((np.abs(pos) <= np.array(BOX) + 0.5).all()), trace=trace, pos=pos.tolist(), vel=vel.tolist())
    return out, h


if __name__ == "__main__":
    for wall in (0.6, 0.9, 1.2):
        for dro, dra in ((5, 6), (0, 10)):
            rs = [trial(dro, dra, 3, sd, wall=wall, s=2.0, theta=120.0)[0] for sd in (1, 2)]
            print(f"wall={wall} dro={dro} dra={dra} w=3: dist {np.mean([r['dist'] for r in rs]):.1f} BL, align {np.mean([r['align'] for r in rs]):+.2f}, p {np.mean([r['p_followers'] for r in rs]):.2f}, in box: {all(r['inside'] for r in rs)}", flush=True)
