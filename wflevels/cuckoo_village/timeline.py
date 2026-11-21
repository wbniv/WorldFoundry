#!/usr/bin/env python3
"""Reference timeline for Cuckoo Village, Classic mode (plan docs/plans/2026-11-21-cuckoo-village.md).

Every moving thing is a pure function of the wall-clock sample (hour, minute, second): no state,
so a start at any time, a clock correction or a pause shows the right pose. forth.py emits the same
formulas as zForth for the director; scripts/check-cuckoo-village.py compares the engine's actor
mailboxes against all_poses() here. Units are Blender/World Foundry units, angles are revolutions.

    all_poses(sod) -> {actor name: (x, y, z, a, b, c, sx, sy, sz)}
    window_states(sod) -> [bool] * 13   (twelve houses, then the tower)
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

TAU = math.tau
Pose = Tuple[float, float, float, float, float, float, float, float, float]

# --- the tower (units: the asset README's tower, front facing -Y) ---------------------------
DIAL = (0.0, -1.10, 4.08)          # hand pivots at the dial centre
MINUTE_Y = -1.125                   # the minute hand sits in front of the hour hand: no z-fighting at 12:00
DOOR = (0.0, -1.04, 4.55)           # bird door hinge origin (left edge)
BIRD_REST = (0.0, -0.995, 4.60)     # behind the closed door
FIG_Z0 = 2.55                       # balcony floor
FIG_HOME_Y = -1.30
FIG_X = [-0.87, -0.29, 0.29, 0.87]  # alcove centres, left to right
FIG_NAMES = ["figure_1", "figure_2", "figure_3", "figure_4"]
LOOP_A, LOOP_B, LOOP_CX, LOOP_CY = 1.15, 0.18, 0.0, -1.50   # the parade oval on the balcony
STEP_OUT = 0.30                     # a solo figure steps this far toward the railing

# --- the schedule ------------------------------------------------------------------------------
SOLO_AT = [900.0, 1800.0, 2700.0]   # seconds into the hour, figures 1 to 3
SOLO_LEN = 8.0
PARADE_LEN = 24.0
PARADE_RATE = 40.0 / 360.0          # revolutions per second along the oval
PARADE_LOOP_START, PARADE_LOOP_SECONDS = 3.0, 18.0     # 18 s * 40 deg/s = two laps: every figure ends where it began
PARADE_EXIT_AT, PARADE_EXIT_LEN = 20.0, 3.5
ENTRY_AT = [2.0, 2.5, 3.0, 0.0]     # figure 4 steps forward first, then the others join
ENTRY_LEN = 2.0
CALL_FIRST, CALL_GAP = 1.0, 1.4
DOOR_OPEN_AT, DOOR_EASE = 0.2, 0.6
DOOR_SWING = 0.27                   # revolutions, outward (toward -Y)
BIRD_OUT = 0.30

# --- windows: local-time schedule, one stagger per house ---------------------------------------
DUSK_START, DUSK_LEN = 17.5 * 3600, 3600.0
DAWN_START, DAWN_LEN = 5.5 * 3600, 3600.0
HOUSES = 12


def stagger(i: int) -> float:
    return ((i * 5) % 13) / 13.0


# --- camera ------------------------------------------------------------------------------------
LAP = 225.0                         # seconds: 900 / 225 = 4, so a quarter boundary is always the start of a lap
HOLD_HOUR, HOLD_QUARTER = 26.0, 10.0
CAM_FRONT_R, CAM_FAR_R = 6.3, 16.0
CAM_FRONT_H, CAM_FAR_H = 3.6, 8.5
CAM_X_STRETCH = 1.1
LOOK_FRONT = (0.0, -1.1, 3.7)
LOOK_FAR = (0.0, 0.0, 1.5)
RISE = 0.12


def sm(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def asin_rev(x: float) -> float:
    return math.asin(clamp(x, -1.0, 1.0)) / TAU


def _split(sod: float) -> Tuple[int, int, float]:
    hr = int(sod // 3600) % 24
    mi = int((sod % 3600) // 60)
    return hr, mi, sod - hr * 3600 - mi * 60


def minute_rev(mi: int, sc: float) -> float:
    return (mi + sc / 60.0) / 60.0


def hour_rev(hr: int, mi: int, sc: float) -> float:
    return ((hr % 12) + mi / 60.0 + sc / 3600.0) / 12.0


def calls_for(hr: int) -> int:
    return (hr % 12) or 12


def figure(i: int, tm: float) -> Tuple[float, float, float, float, float]:
    """x, y, z, a, c of figure i at tm seconds into the hour."""
    home_x = FIG_X[i]
    f = bow = 0.0
    if i < 3:
        s = tm - SOLO_AT[i]
        if 0.0 <= s < SOLO_LEN:
            f = sm(s / 1.5) * (1.0 - sm((s - 6.0) / 1.5))
            bow = (25.0 / 360.0) * math.sin(math.pi * clamp((s - 2.0) / 3.0, 0.0, 1.0))
    w = 0.0
    lx = ly = c_loop = hop = 0.0
    if 0.0 <= tm < PARADE_LEN:
        theta0 = 0.75 + asin_rev(home_x / LOOP_A)
        theta = theta0 + clamp(tm - PARADE_LOOP_START, 0.0, PARADE_LOOP_SECONDS) * PARADE_RATE
        w = sm((tm - ENTRY_AT[i]) / ENTRY_LEN) * (1.0 - sm((tm - PARADE_EXIT_AT) / PARADE_EXIT_LEN))
        lx = LOOP_CX + LOOP_A * math.cos(TAU * theta)
        ly = LOOP_CY + LOOP_B * math.sin(TAU * theta)
        vx = -LOOP_A * math.sin(TAU * theta)
        vy = LOOP_B * math.cos(TAU * theta)
        c_loop = math.atan2(vx, -vy) / TAU
        hop = 0.03 * math.sin(TAU * theta * 6.0) ** 2
    x = home_x * (1.0 - w) + lx * w
    y = (FIG_HOME_Y - STEP_OUT * f) * (1.0 - w) + ly * w
    z = FIG_Z0 + 0.05 * math.sin(math.pi * f) + w * hop
    return x, y, z, bow * (1.0 - w), w * c_loop


def bird(hr: int, tm: float) -> Tuple[float, float, float]:
    """door opening o (0..1), bird forward travel, bird bob (0..1)."""
    n = calls_for(hr)
    t_end = CALL_FIRST + CALL_GAP * (n - 1) + 1.0
    o = 0.0
    bob = 0.0
    if 0.0 <= tm < PARADE_LEN:
        o = sm((tm - DOOR_OPEN_AT) / DOOR_EASE) * (1.0 - sm((tm - t_end) / DOOR_EASE))
        k = tm - CALL_FIRST
        if k >= 0.0 and k < CALL_GAP * n:
            p = (k % CALL_GAP) / CALL_GAP
            bob = math.sin(math.pi * clamp(p / 0.45, 0.0, 1.0))
    return o, o, bob


def window_states(sod: float) -> List[bool]:
    out = []
    for i in range(HOUSES + 1):
        s = stagger(i)
        out.append(sod >= DUSK_START + s * DUSK_LEN or sod < DAWN_START + s * DAWN_LEN)
    return out


def camera(tm: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    cycle = int(tm // LAP)
    lap_t = tm - cycle * LAP
    hold = HOLD_HOUR if cycle == 0 else (HOLD_QUARTER if cycle in (4, 8, 12) else 0.0)
    u = sm((lap_t - hold) / (LAP - hold))
    b = sm(u / RISE) * sm((1.0 - u) / RISE)
    phi = TAU * (-0.25 + u)
    r = CAM_FRONT_R + (CAM_FAR_R - CAM_FRONT_R) * b
    h = CAM_FRONT_H + (CAM_FAR_H - CAM_FRONT_H) * b
    pos = (CAM_X_STRETCH * r * math.cos(phi), r * math.sin(phi), h)
    look = tuple(LOOK_FRONT[k] + (LOOK_FAR[k] - LOOK_FRONT[k]) * b for k in range(3))
    return pos, look      # type: ignore[return-value]


def all_poses(sod: float) -> Dict[str, Pose]:
    hr, mi, sc = _split(sod)
    tm = mi * 60 + sc
    ONE = (1.0, 1.0, 1.0)
    poses: Dict[str, Pose] = {}
    poses["hour_hand"] = (DIAL[0], DIAL[1], DIAL[2], 0.0, hour_rev(hr, mi, sc), 0.0, *ONE)
    poses["minute_hand"] = (DIAL[0], MINUTE_Y, DIAL[2], 0.0, minute_rev(mi, sc), 0.0, *ONE)
    for i, name in enumerate(FIG_NAMES):
        x, y, z, a, c = figure(i, tm)
        poses[name] = (x, y, z, a, 0.0, c, *ONE)
    o, out, bob = bird(hr, tm)
    poses["bird_door"] = (DOOR[0], DOOR[1], DOOR[2], 0.0, 0.0, -DOOR_SWING * o, *ONE)
    poses["bird"] = (BIRD_REST[0], BIRD_REST[1] - BIRD_OUT * out - 0.05 * bob, BIRD_REST[2] + 0.04 * bob, 0.06 * bob, 0.0, 0.0, *ONE)
    (cx, cy, cz), (lx, ly, lz) = camera(tm)
    poses["cs_wide"] = (cx, cy, cz, 0.0, 0.0, 0.0, *ONE)
    poses["LookAt"] = (lx, ly, lz, 0.0, 0.0, 0.0, *ONE)
    return poses


if __name__ == "__main__":
    for spec in ("10:08:22", "12:00:00", "12:00:05", "15:15:03", "18:00:00"):
        h, m, s = (float(v) for v in spec.split(":"))
        poses = all_poses(h * 3600 + m * 60 + s)
        print(spec, {k: tuple(round(v, 3) for v in poses[k][:6]) for k in ("minute_hand", "hour_hand", "figure_4", "cs_wide")})
