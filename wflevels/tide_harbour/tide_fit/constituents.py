"""Tidal constituents by Doodson number: speed = d1*tau + d2*s + d3*h + d4*p + d5*N' + d6*ps (degrees per hour)."""
TAU, S, H, P, NP, PS = 14.4920521, 0.5490165, 0.0410686, 0.0046418, -0.0022064, 0.0000020
D = {  # name: (d1, d2, d3, d4, d5, d6)
 "Sa": (0,0,1,0,0,-1), "Ssa": (0,0,2,0,0,0), "Mm": (0,1,0,-1,0,0), "MSf": (0,2,-2,0,0,0), "Mf": (0,2,0,0,0,0),
 "2Q1": (1,-3,0,2,0,0), "SIG1": (1,-3,2,0,0,0), "Q1": (1,-2,0,1,0,0), "RHO1": (1,-2,2,-1,0,0), "O1": (1,-1,0,0,0,0),
 "M1": (1,0,0,1,0,0), "CHI1": (1,0,2,-1,0,0), "PI1": (1,1,-3,0,0,1), "P1": (1,1,-2,0,0,0), "S1": (1,1,-1,0,0,1),
 "K1": (1,1,0,0,0,0), "PSI1": (1,1,1,0,0,-1), "PHI1": (1,1,2,0,0,0), "THE1": (1,2,-2,1,0,0), "J1": (1,2,0,-1,0,0),
 "SO1": (1,3,-2,0,0,0), "OO1": (1,3,0,0,0,0),
 "EPS2": (2,-3,2,1,0,0), "2N2": (2,-2,0,2,0,0), "MU2": (2,-2,2,0,0,0), "N2": (2,-1,0,1,0,0), "NU2": (2,-1,2,-1,0,0),
 "M2": (2,0,0,0,0,0), "LAM2": (2,1,-2,1,0,0), "L2": (2,1,0,-1,0,0), "T2": (2,2,-3,0,0,1), "S2": (2,2,-2,0,0,0),
 "R2": (2,2,-1,0,0,-1), "K2": (2,2,0,0,0,0), "ETA2": (2,3,0,-1,0,0),
 "MO3": (3,-1,0,0,0,0), "M3": (3,0,0,0,0,0), "SO3": (3,1,-2,0,0,0), "MK3": (3,1,0,0,0,0), "SK3": (3,2,-2,0,0,0),
 "MN4": (4,-1,0,1,0,0), "M4": (4,0,0,0,0,0), "SN4": (4,1,-2,1,0,0), "MS4": (4,2,-2,0,0,0), "MK4": (4,2,0,0,0,0),
 "S4": (4,4,-4,0,0,0), "SK4": (4,4,-2,0,0,0),
 "2MN6": (6,-1,0,1,0,0), "M6": (6,0,0,0,0,0), "MSN6": (6,1,-2,1,0,0), "2MS6": (6,2,-2,0,0,0), "2MK6": (6,2,0,0,0,0),
 "2SM6": (6,4,-4,0,0,0), "MSK6": (6,4,-2,0,0,0), "M8": (8,0,0,0,0,0),
}
SPEEDS = {k: v[0]*TAU + v[1]*S + v[2]*H + v[3]*P + v[4]*NP + v[5]*PS for k, v in D.items()}
if __name__ == "__main__":
    known = {"M2": 28.9841042, "K1": 15.0410686, "O1": 13.9430356, "S2": 30.0, "MK3": 44.0251729, "M4": 57.9682084, "N2": 28.4397295, "P1": 14.9589314, "Q1": 13.3986609, "K2": 30.0821373, "M6": 86.9523127}
    for k, v in known.items():
        print(f"{k:4s} computed {SPEEDS[k]:.7f} known {v:.7f} diff {SPEEDS[k]-v:+.2e}")
    print(len(SPEEDS), "constituents")


def compound(order=3, min_sep=0.03, max_speed=130.0):
    """Shallow-water compound tides: integer combinations (sum of |coefficients| <= order) of the main constituents.
    Near-duplicates (closer than min_sep deg/h, about 3/4 of a cycle a year apart is the resolution of one year) are dropped."""
    import itertools
    base = {k: SPEEDS[k] for k in ("O1", "K1", "M2", "S2", "N2", "K2", "Q1", "P1")}
    names = list(base)
    out = dict(SPEEDS)
    cands = {}
    for coefs in itertools.product(range(-order, order + 1), repeat=len(names)):
        if not coefs or sum(abs(c) for c in coefs) > order:
            continue
        sp = sum(c * base[n] for c, n in zip(coefs, names))
        if sp <= 0.05 or sp > max_speed:
            continue
        label = "".join(f"{'+' if c > 0 else '-'}{abs(c) if abs(c) > 1 else ''}{n}" for c, n in zip(coefs, names) if c)
        cands[label] = sp
    for label, sp in sorted(cands.items(), key=lambda kv: (sum(1 for ch in kv[0] if ch in "+-"), kv[0])):
        if all(abs(sp - v) >= min_sep for v in out.values()):
            out[label] = sp
    return out
