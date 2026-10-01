"""bench_cmds.py: print a zf_host command script that loads the engine's bootstrap, school.fth and a school-mode state of 11 fish, then times 200 sch-tick.
Used by device_bench.sh (and by measure.py for the x86 figure). Usage: python3 bench_cmds.py [-h]
"""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import couzin, forth_check as fc, zfhost

def main():
    if len(sys.argv) > 1:
        print(__doc__); return
    n = 11
    out = ["E " + zfhost.engine_bootstrap(), "E : read-mailbox 128 sys ;", "E : write-mailbox 129 sys ;", "E : r@ ' lit , 0 , ' pickr , ; immediate"]
    out += ["E " + l for l in zfhost.fish_trig().splitlines()]
    out += [f"E {fc.BASE} constant sch-base {fc.PAR} constant sch-par {fc.SCR} constant sch-scr", f"E {n} constant sch-n"]
    out += ["E " + l for l in (zfhost.ROOT / "wflevels/aquarium/school.fth").read_text().splitlines() if l.strip()]
    vals = {0: 1.0, 1: 5.0, 2: 6.0, 3: math.cos(math.radians(135)), 7: 3.0, 8: 1.5, 9: 0.5, 11: -6.85, 12: -4, 13: -3, 14: 6.85, 15: 4, 16: 3, 17: 0, 18: 10, 19: 5, 20: 6}
    out += [f"W {fc.PAR + k} {v}" for k, v in vals.items()]
    out.append("E 0.1 120 2 sch-set-dt")
    pos, vel = couzin.init(n, np.random.default_rng(1), 4.0)
    for i in range(n):
        for k in range(3):
            out.append(f"W {fc.BASE + i * fc.STRIDE + k} {pos[i][k]}")
            out.append(f"W {fc.BASE + i * fc.STRIDE + 3 + k} {vel[i][k]}")
    out.append("T 200 sch-tick")
    print("\n".join(out))

main()
