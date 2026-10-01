"""tank_results.py: run the Forth core (school.fth) in the tank box for the poster's measured panel; writes tank.json.

Game parameters (ours, NOT the paper's): speed 2 BL/s and turn rate 120 deg/s, because at the paper's 3 BL/s and 40 deg/s a fish needs about 6.75 BL
to turn round and leaves a 13.7 BL tank through the wall. Zone widths per mode: swarm (0, 10), torus (1, 10), school (5, 6). Box and wall zone (0.6 BL) as tank_trial.py.
Usage: python3 tank_results.py [-h]
"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tank_trial as tt

MODES = {"swarm": (0, 10), "torus": (1, 10), "school": (5, 6)}
GAME = dict(s=2.0, theta=120.0)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(__doc__); sys.exit(0)
    rows, snaps = [], {}
    for mode, (dro, dra) in MODES.items():
        for w in (1, 3, 6):
            rs = []
            for seed in (1, 2, 3):
                r, h = tt.trial(dro, dra, w, seed, wall=0.6, startle_at=500 if (w == 3 and seed == 1) else None, ticks=900, **GAME)
                h.close(); rs.append(r)
                if w == 3 and seed == 1:
                    snaps[mode] = dict(pos=r["pos"], vel=r["vel"], trace=r["trace"])
            rows.append(dict(mode=mode, dro=dro, dra=dra, w=w, dist=float(np.mean([r["dist"] for r in rs])), align=float(np.mean([r["align"] for r in rs])),
                             p=float(np.mean([r["p_followers"] for r in rs])), inside=all(r["inside"] for r in rs)))
            print(rows[-1], flush=True)
    Path(__file__).with_name("tank.json").write_text(json.dumps(dict(rows=rows, snaps=snaps, game=GAME, box=tt.BOX, startle_r=tt.STARTLE_R), indent=1))
    print("wrote tank.json")
