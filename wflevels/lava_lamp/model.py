"""The lava lamp's wax model: the reference for the level's zForth (forth.py).

docs/plans/2026-11-26-lava-lamp.md, "How the wax moves". A port of the mockup's
model (docs/plans/2026-11-26-lava-lamp/build_mockups.py: M, envT, makeSim,
stepSim, simBalls), in 32-bit floats with the same order of operations as the
Forth words, so a trace of the level's script matches this module step for step.
Lengths are in globe heights (the globe's inside, bottom 0, cap 1), time in seconds.

Each blob: x, y, vx, vy, radius r, temperature T (0 cold, 1 coil-hot), stuck
(0 moving, 1 pooled on the coil, 2 resting under the cap) and two drift phase
offsets (a, b, in turns). Every fixed step of 1/30 s:

1. Heat exchange (exact Newton): T += (target - T)(1 - e^(-k dt)), k = K 0.06 / r,
   doubled in the pool, target the coil (1.1) in the pool, else the liquid
   0.3 + 0.75 e^(-y/0.08) - 0.08 y.
2. Hysteresis: a pooled blob leaves above 0.88; a resting one falls below 0.5.
3. Buoyancy and drag: vy += (0.55 (T - 0.6) - 1.6 vy) dt (0 while stuck).
4. Sideways: two slow sines; rising blobs drift to the centre, falling ones to
   the glass; pairs closer than 0.3 attract, overlapping pairs push apart and
   share heat.
5. Walls: |x| <= R(y) - 0.9 r; the bottom pools a cool blob, the cap stops a warm one.

The drift sines run on phases kept in turns and wrapped into 0..1, so a lamp left
on for days loses no precision (the mockup used raw seconds).
"""
from __future__ import annotations

import math
from typing import Dict, List

import numpy as np

import lamp as _lamp

F = np.float32
TWO_PI = 6.283185307179586476925286766559

N_BLOBS = 8
SEED = 7
DT = F(1.0) / F(30.0)              # the engine's DELTA_TIME, 1/30 s rounded to a float
MAX_STEPS = 4                      # steps per frame at most (a long frame drops the rest)
WARM_STEPS = 4500                  # D9: the level opens mid-flow (150 s, run at build time)

# The mockup's M, as 32-bit floats.
B, K, TN, LO, REL, DROP, DRAG, COIL = (F(v) for v in (0.55, 0.012, 0.6, 0.3, 0.88, 0.5, 1.6, 1.1))
RATE1 = F(0.11 / TWO_PI)           # drift phase rates, turns per second
RATE2 = F(0.27 / TWO_PI)
RATE3 = F(0.7 / TWO_PI)            # the wobble phase

FIELDS = ("x", "y", "vx", "vy", "r", "T", "stuck", "a", "b")


def lit(v: float) -> str:
    """A float32 constant as the shortest decimal that reads back as the same float (for Forth)."""
    s = np.format_float_positional(F(v), unique=True, trim='-')
    return s if s not in ('-0',) else '0'


# ---- the shipped maths words, as the engine computes them (engine/stubs/forth_math.hpp):
# the argument widened to double, libm in double, the result rounded to a float.
def expm1(x): return F(math.expm1(float(x)))
def exp(x): return F(math.exp(float(x)))
def hypot(x, y): return F(math.hypot(float(x), float(y)))
def cbrt(x): return F(math.cbrt(float(x)))
def floor(x): return F(math.floor(float(x)))


def sin_rev(turns):
    t = float(turns)
    return F(math.sin(TWO_PI * (t - math.floor(t))))


def cos_rev(turns):
    t = float(turns)
    return F(math.cos(TWO_PI * (t - math.floor(t))))


def globe_r(y):
    """R(y): the globe's inner radius at height y, widest a quarter of the way up."""
    q = F(0.25)
    if y < q:
        d = q - y
        return F(0.27) - F(0.72) * d * d
    d = y - q
    return F(0.27) - F(0.2) * d * d


def env(y):
    """The liquid's temperature: a hot layer over the coil, cooler above."""
    return LO + F(0.75) * exp(-(y / F(0.08))) - F(0.08) * y


def lo_of(r): return F(0.03) + r * F(0.45)
def hi_of(r): return F(1.0) - r * F(0.8) - F(0.012)


def mulberry32(seed: int):
    """The mockup's rng(seed), bit for bit."""
    state = [seed & 0xFFFFFFFF]

    def imul(a, b):
        return (a * b) & 0xFFFFFFFF

    def rnd():
        state[0] = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        s = state[0]
        t = imul(s ^ (s >> 15), 1 | s)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return rnd


class Lamp:
    """Model state: the blobs and the three phases (turns, 0..1)."""

    def __init__(self, blobs: List[Dict[str, np.float32]], p1=F(0), p2=F(0), p3=F(0)):
        self.blobs = blobs
        self.p1, self.p2, self.p3 = F(p1), F(p2), F(p3)

    def copy(self) -> "Lamp":
        return Lamp([dict(b) for b in self.blobs], self.p1, self.p2, self.p3)

    @staticmethod
    def seeded(seed: int = SEED, n: int = N_BLOBS) -> "Lamp":
        """makeSim(seed, n) without the warm-up: the same random draws in the same order."""
        r = mulberry32(seed)
        blobs = []
        for _ in range(n):
            rad = 0.042 + r() * 0.042
            x = (r() - 0.5) * 0.25
            y = 0.06 + r() * 0.86
            T = 0.35 + r() * 0.5
            ph = r() * 60
            blobs.append({"x": F(x), "y": F(y), "vx": F(0), "vy": F(0), "r": F(rad), "T": F(T), "stuck": F(0),
                          "a": F((ph / TWO_PI) % 1.0), "b": F((ph * 1.9 / TWO_PI) % 1.0)})
        return Lamp(blobs)

    # ------------------------------------------------------------------ one step
    def step(self, dt=DT) -> None:
        blobs = self.blobs
        for b in blobs:
            hot = b["stuck"] == F(1)
            k = F(0.06) / b["r"] * K
            if hot:
                k = k * F(2)
            target = COIL if hot else env(b["y"])
            T = b["T"]
            T = T + (target - T) * -expm1(-(k * dt))
            b["T"] = T
            if b["stuck"] == F(1) and T > REL:
                b["stuck"] = F(0)
            if b["stuck"] == F(2) and T < DROP:
                b["stuck"] = F(0)
            stuck = b["stuck"] != F(0)
            buoy = F(0) if stuck else (T - TN) * B
            vy = b["vy"] + (buoy - DRAG * b["vy"]) * dt
            if stuck:
                vy = F(0)
            b["vy"] = vy
            drift = F(0.010) * sin_rev(self.p1 + b["a"]) + F(0.006) * sin_rev(self.p2 + b["b"])
            x = b["x"]
            if vy > F(0):
                conv = F(-0.05) * x
            elif vy < F(-0.01):
                conv = F(-0.035) if x < F(0) else F(0.035)
            else:
                conv = F(0)
            b["vx"] = b["vx"] + (drift + conv - F(1.2) * b["vx"]) * dt
        n = len(blobs)
        for i in range(n):
            for j in range(i + 1, n):
                self.pair(blobs[i], blobs[j], dt)
        for b in blobs:
            self.integrate(b, dt)
        self.p1 = wrap(self.p1 + RATE1 * dt)
        self.p2 = wrap(self.p2 + RATE2 * dt)
        self.p3 = wrap(self.p3 + RATE3 * dt)

    @staticmethod
    def pair(a, c, dt) -> None:
        dx = c["x"] - a["x"]
        dy = c["y"] - a["y"]
        d = hypot(dx, dy)
        if d == F(0):
            d = F(1e-6)
        s0 = (a["r"] + c["r"]) * F(0.85)
        if d < s0:
            f = (s0 - d) * F(1.5) * dt / d
            fx, fy = dx * f, dy * f
            a["vx"] = a["vx"] - fx
            a["vy"] = a["vy"] - fy
            c["vx"] = c["vx"] + fx
            c["vy"] = c["vy"] + fy
            dT = (c["T"] - a["T"]) * F(0.08) * dt
            a["T"] = a["T"] + dT
            c["T"] = c["T"] - dT
        elif d < F(0.3):
            f = (F(1) - d / F(0.3)) * F(0.004) * dt / d
            fx, fy = dx * f, dy * f
            a["vx"] = a["vx"] + fx
            a["vy"] = a["vy"] + fy
            c["vx"] = c["vx"] - fx
            c["vy"] = c["vy"] - fy

    @staticmethod
    def integrate(b, dt) -> None:
        x = b["x"] + b["vx"] * dt
        y = b["y"] + b["vy"] * dt
        r = b["r"]
        lo = lo_of(r)
        hi = hi_of(r)
        if not y > lo:
            y = lo
            if b["vy"] < F(0):
                b["vy"] = F(0)
            if b["T"] < REL:
                b["stuck"] = F(1)
        if not y < hi:
            y = hi
            if b["vy"] > F(0):
                b["vy"] = F(0)
            if b["T"] > DROP:
                b["stuck"] = F(2)
        lim = globe_r(y) - r * F(0.9)
        if abs(x) > lim:
            x = -lim if x < F(0) else lim
            b["vx"] = b["vx"] * F(-0.2)
        b["x"], b["y"] = x, y

    def frame(self, acc, delta=DT):
        """One engine frame: add DELTA_TIME to the accumulator and run the whole steps it holds, at most
        MAX_STEPS (the remainder of a long frame is dropped). Returns the new accumulator."""
        acc = acc + delta
        steps = 0
        while not acc < DT and steps < MAX_STEPS:
            self.step()
            acc = acc - DT
            steps += 1
        if not acc < DT:
            acc = F(0)
        return acc


def wrap(p):
    return p - floor(p)


def warmed(seed: int = SEED, n: int = N_BLOBS, steps: int = WARM_STEPS) -> Lamp:
    """D9: the state the level opens with, the seeded lamp after the warm-up (baked by the generator)."""
    lamp = Lamp.seeded(seed, n)
    for _ in range(steps):
        lamp.step()
    return lamp


# ---------------------------------------------------------------------- shapes
def smoothstep(e0, e1, x):
    t = (x - e0) / (e1 - e0)
    t = min(max(t, F(0)), F(1))
    return t * t * (F(3) - F(2) * t)


def shape(lamp: Lamp, b) -> Dict[str, np.float32]:
    """The blob's morph weights (rise, fall, squash, neck, wobble_a, wobble_b), from the model as simBalls draws it:
    stretched along vy, a pancake under the cap, a tower while it heats in the pool, a slow lumpy wobble."""
    st = min(max(b["vy"] * F(8), F(-0.6)), F(0.6))
    rise = max(st, F(0)) / F(0.6)
    fall = max(-st, F(0)) / F(0.6)
    if b["stuck"] == F(2):
        squash = F(1)
    else:
        squash = smoothstep(F(0.03), F(0), hi_of(b["r"]) - b["y"]) * F(0.6)
    if b["stuck"] == F(1):
        rise = smoothstep(F(0.75), REL, b["T"])
    w = lamp.p3 + b["a"]
    return {"rise": rise, "fall": fall, "squash": squash, "neck": F(0),
            "wobble_a": sin_rev(w) * F(0.5) + F(0.5), "wobble_b": cos_rev(w) * F(0.5) + F(0.5)}


def merged_radius(r1, r2):
    """D5: a merged blob keeps the wax's volume, r = cbrt(r1^3 + r2^3)."""
    return cbrt(r1 * r1 * r1 + r2 * r2 * r2)


# ------------------------------------------------------------------ one frame's pose
N_MERGED = 4
G = F(_lamp.G)             # one globe height in world units
GZ0 = F(_lamp.GZ0)         # the globe's bottom in world units
NECK_SPAN = F(1.26)        # the neck target's lobes are 1.26 merged radii apart


def glow_of(y):
    """Lit from below: wax high in the lamp is darker."""
    return F(1.2) - F(0.5) * y


def pose(lamp: Lamp, wax=(F(1), F(1), F(1))):
    """What the director shows this frame (D5): blobs that overlap are hidden and one merged mesh shows at their
    volume-weighted centre, its radius cbrt(r1^3 + r2^3), its neck weight from their distance (pairs taken greedily in
    index order, at most four). Returns {'blobs': [None or (X, Z, scale, block)], 'merged': [None or (X, Z, scale,
    roll, block)], 'pool': block}; a block is the ten deform cells, roll is in turns."""
    blobs = lamp.blobs
    n = len(blobs)
    taken = [False] * n
    merged = [None] * N_MERGED
    k = 0
    for i in range(n):
        for j in range(i + 1, n):
            if taken[i] or taken[j] or k >= N_MERGED:
                continue
            a, c = blobs[i], blobs[j]
            dx = c["x"] - a["x"]
            dy = c["y"] - a["y"]
            d = hypot(dx, dy)
            if d < a["r"] + c["r"]:
                taken[i] = taken[j] = True
                ca = a["r"] * a["r"] * a["r"]
                cc = c["r"] * c["r"] * c["r"]
                R = cbrt(ca + cc)
                cx = (a["x"] * ca + c["x"] * cc) / (ca + cc)
                cy = (a["y"] * ca + c["y"] * cc) / (ca + cc)
                neck = min(d / (NECK_SPAN * R), F(1))
                vy = (a["vy"] + c["vy"]) * F(0.5)
                st = min(max(vy * F(8), F(-0.6)), F(0.6))
                w = lamp.p3 + a["a"]
                block = [max(st, F(0)) / F(0.6), max(-st, F(0)) / F(0.6), F(0), neck,
                         sin_rev(w) * F(0.5) + F(0.5), cos_rev(w) * F(0.5) + F(0.5),
                         wax[0], wax[1], wax[2], glow_of(cy)]
                roll = -atan2_rev(dy, dx)
                merged[k] = (cx * G, GZ0 + cy * G, R * G, roll, block)
                k += 1
    out = []
    pooled = F(0)
    tower = F(0)
    for i, b in enumerate(blobs):
        if b["stuck"] == F(1):
            pooled = pooled + F(1)
            tower = max(tower, smoothstep(F(0.75), REL, b["T"]))
        if taken[i]:
            out.append(None)
            continue
        s = shape(lamp, b)
        block = [s["rise"], s["fall"], s["squash"], s["neck"], s["wobble_a"], s["wobble_b"],
                 wax[0], wax[1], wax[2], glow_of(b["y"])]
        out.append((b["x"] * G, GZ0 + b["y"] * G, b["r"] * G, block))
    pool = [min(pooled * F(0.25), F(1)), tower, F(0), F(0), F(0), F(0), wax[0], wax[1], wax[2], F(1.15)]
    return {"blobs": out, "merged": merged, "pool": pool}


def atan2_rev(y, x):
    """atan2-rev ( y x -- rev ), as engine/stubs/forth_math.hpp computes it."""
    return F(math.atan2(float(y), float(x)) / TWO_PI)


# ------------------------------------------------------------------ character
def character(seconds: float = 1200.0, lamp: Lamp | None = None) -> Dict[str, float]:
    """Verification 5: the share of blob time pooled, resting and moving, the mean cycle (one release from the pool to
    the next, per blob) and the fastest climb (globe heights per second), over `seconds` of model time."""
    lamp = (lamp or warmed()).copy()
    steps = int(round(seconds * 30))
    n = len(lamp.blobs)
    pooled = resting = 0
    peak = 0.0
    releases: List[List[int]] = [[] for _ in range(n)]
    was = [b["stuck"] for b in lamp.blobs]
    for s in range(steps):
        lamp.step()
        for i, b in enumerate(lamp.blobs):
            if b["stuck"] == F(1):
                pooled += 1
            elif b["stuck"] == F(2):
                resting += 1
            peak = max(peak, float(b["vy"]))
            if was[i] == F(1) and b["stuck"] != F(1):
                releases[i].append(s)
            was[i] = b["stuck"]
    gaps = [(r[k + 1] - r[k]) / 30.0 for r in releases for k in range(len(r) - 1)]
    total = steps * n
    return {"pooled": pooled / total, "resting": resting / total, "moving": 1 - (pooled + resting) / total,
            "cycle": sum(gaps) / len(gaps) if gaps else float("inf"), "peak_climb": peak,
            "cycles": len(gaps)}


if __name__ == "__main__":
    import json
    print(json.dumps(character(), indent=2))
