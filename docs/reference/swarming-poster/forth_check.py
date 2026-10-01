"""forth_check.py: run wflevels/aquarium/school.fth in the standalone zForth host and compare it with couzin.py (sigma = 0).

The same N fish, the same start; fish 0 is the leader and is moved by the caller each tick (the game moves it from the player's input).
Reports the per-tick error of every follower's position and heading, so the poster can quote a measured number rather than a claim.
"""
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import couzin
import zfhost

BASE, PAR, SCR = 1000, 100, 200
STRIDE = 14
SCHOOL_FTH = zfhost.ROOT / "wflevels/aquarium/school.fth"


def make_host():
    h = zfhost.Host()
    tmp = Path(tempfile.gettempdir()) / "zf_trig.fth"
    tmp.write_text(zfhost.fish_trig() + "\n")
    assert h.load(tmp) == "ok"
    assert h.eval(f"{BASE} constant sch-base {PAR} constant sch-par {SCR} constant sch-scr") == "ok"
    return h


def load_school(h, n):
    assert h.eval(f"{n} constant sch-n") == "ok"
    before = h.size()
    r = h.load(SCHOOL_FTH)
    assert r == "ok", r
    return h.size() - before


def set_params(h, p, dro, dra, w_leader=1.0, wall=0.0, box=1000.0, startle=0.5):
    cos_blind = math.cos(math.radians(p["alpha"] / 2))
    vals = {0: p["rr"], 1: dro, 2: dra, 3: cos_blind, 7: w_leader, 8: wall, 9: startle,
            11: -box, 12: -box, 13: -box, 14: box, 15: box, 16: box, 17: dro, 18: dra, 19: dro, 20: dra}
    for k, v in vals.items():
        h.write(PAR + k, v)
    # sch-set-dt ( dt turn-deg-per-s speed -- )
    assert h.eval(f"{p['tau']} {p['theta']} {p['s']} sch-set-dt") == "ok"


def put(h, i, pos, vel):
    for k in range(3):
        h.write(BASE + i * STRIDE + k, float(pos[k]))
        h.write(BASE + i * STRIDE + 3 + k, float(vel[k]))
    h.write(BASE + i * STRIDE + 12, 0.0)


def get(h, n):
    pos = np.zeros((n, 3)); vel = np.zeros((n, 3))
    for i in range(n):
        v = h.read(BASE + i * STRIDE, 6)
        pos[i] = v[:3]; vel[i] = v[3:]
    return pos, vel


def compare(n=11, ticks=40, seed=3, dro=8.0, dra=10.0, w_leader=1.0, leader_turn=0.0):
    """One-tick equivalence: each tick both start from the SAME state (the reference's), run one step, and are compared.

    Returns ([(max position error, max heading error) per tick], dictionary bytes). Comparing one step at a time keeps float32 rounding from
    being amplified by the model's own sensitivity (a zone boundary crossed by 1e-7 changes a whole step), so the number is the Forth's error.
    """
    p = dict(couzin.PAPER, sigma=0.0)
    rng = np.random.default_rng(seed)
    pos, vel = couzin.init(n, rng, radius=4.0)
    h = make_host()
    size = load_school(h, n)
    set_params(h, p, dro, dra, w_leader)
    errs = []
    for t in range(ticks):
        for i in range(n):
            put(h, i, pos[i], vel[i])
        pos, vel = couzin.step(pos, vel, dro, dra, rng, p, leader=0, w_leader=w_leader)
        if leader_turn:                                               # the leader steers: rotate its heading about z, like a player turning
            a = math.radians(leader_turn)
            c, s = math.cos(a), math.sin(a)
            vel[0] = np.array([c * vel[0][0] - s * vel[0][1], s * vel[0][0] + c * vel[0][1], vel[0][2]])
        assert h.eval("sch-tick") == "ok"
        fpos, fvel = get(h, n)
        errs.append((float(np.abs(fpos[1:] - pos[1:]).max()), float(np.abs(fvel[1:] - vel[1:]).max())))
    h.close()
    return errs, size


if __name__ == "__main__":
    errs, size = compare(ticks=60)
    print(f"school.fth compiled to {size} bytes of dictionary")
    ep = np.array([e[0] for e in errs]); ev = np.array([e[1] for e in errs])
    print(f"60 one-tick comparisons: position error median {np.median(ep):.1e} max {ep.max():.1e}; heading error median {np.median(ev):.1e} max {ev.max():.1e}")
    print("ticks with heading error > 0.05:", [i for i, e in enumerate(ev) if e > 0.05])
