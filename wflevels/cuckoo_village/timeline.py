#!/usr/bin/env python3
"""Reference timeline for Cuckoo Village, Classic mode (plan docs/plans/2026-11-21-cuckoo-village.md).

Every moving thing is a pure function of the wall-clock sample (hour, minute, second): no state,
so a start at any time, a clock correction or a pause shows the right pose. forth.py emits the same
formulas as zForth for the director; scripts/check-cuckoo-village.py compares the engine's actor
mailboxes against all_poses() here. Units are Blender/World Foundry units, angles are revolutions.

    all_poses(sod) -> {actor name: (x, y, z, a, b, c, sx, sy, sz)}
    window_states(sod) -> [bool] * 13   (the thirteen cottages)
    bird_visible(sod) -> bool
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

TAU = math.tau
Pose = Tuple[float, float, float, float, float, float, float, float, float]

# --- the tower: wflevels/cuckoo_village_layout (tower_art.py and generate.py), front facing -Y ----------
# The build asserts these against the scene it generates, so a change in the art fails loudly here.
TZ = 0.1888                         # the tower stands on the terrain: height(0, 0) - 0.08
DIAL = (0.0, -1.10, 4.08 + TZ)      # hand pivots at the dial centre
MINUTE_Y = -1.125                   # the minute hand sits in front of the hour hand: no z-fighting at 12:00
BIRD_NAME = "tower_bird"
BIRD_REST = (0.0, -1.27, 4.60 + TZ) # the bird's pivot, in the carved alcove above the dial
FIG_Z0 = 2.50 + TZ                  # figure pivots stand on the balcony floor
FIG_HOME_Y = -1.61
FIG_X = [-0.87, -0.29, 0.29, 0.87]  # alcove centres, left to right
FIG_NAMES = ["tower_figure_1", "tower_figure_2", "tower_figure_3", "tower_figure_4"]
FIG_B_NAMES = ["tower_figure_b1", "tower_figure_b2", "tower_figure_b3", "tower_figure_b4"]   # Bavaria mode: the cooper, the dirndl, the lederhosen figure and the brewer,
                                                                                              # on the same pivots, posed by the same formulas
LOOP_A, LOOP_B, LOOP_CX, LOOP_CY = 1.15, 0.18, 0.0, -1.45   # the parade oval on the balcony, between the wall and the rail
STEP_OUT = 0.08                     # a solo figure steps this far toward the rail (the rail is 0.26 in front of the pivots)

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
BIRD_SHOW_AT, BIRD_EASE = 0.2, 0.6   # the bird is shown (visibility mailbox) from the first call until the last
BIRD_LUNGE = 0.05                   # how far the bird leans toward the viewer on a call

# --- windows: local-time schedule, one stagger per house ---------------------------------------
DUSK_START, DUSK_LEN = 17.5 * 3600, 3600.0
DAWN_START, DAWN_LEN = 5.5 * 3600, 3600.0
HOUSES = 13                          # the thirteen cottages; the open-mechanism tower has no window glow


def stagger(i: int) -> float:
    return ((i * 5) % 13) / 13.0


# --- camera ------------------------------------------------------------------------------------
LAP = 225.0                         # seconds: 900 / 225 = 4, so a quarter boundary is always the start of a lap
HOLD_HOUR, HOLD_QUARTER = 26.0, 10.0
CAM_FRONT_R, CAM_FAR_R = 6.3, 16.0
CAM_FRONT_H, CAM_FAR_H = 3.6 + TZ, 10.5
CAM_X_STRETCH = 1.4
LOOK_FRONT = (0.0, -1.1, 3.7 + TZ)
LOOK_FAR = (0.0, 1.0, 1.2)
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


def figure(i: int, tm: float, sign: float = 1.0) -> Tuple[float, float, float, float, float]:
    """x, y, z, a, c of figure i at tm seconds into the hour. sign is -1 for Bavaria mode: the same parade timeline with its progress
    along the oval reversed, so each figure leaves its own alcove, travels the loop the other way and returns to it."""
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
        theta = theta0 + sign * clamp(tm - PARADE_LOOP_START, 0.0, PARADE_LOOP_SECONDS) * PARADE_RATE
        w = sm((tm - ENTRY_AT[i]) / ENTRY_LEN) * (1.0 - sm((tm - PARADE_EXIT_AT) / PARADE_EXIT_LEN))
        lx = LOOP_CX + LOOP_A * math.cos(TAU * theta)
        ly = LOOP_CY + LOOP_B * math.sin(TAU * theta)
        vx = -LOOP_A * math.sin(TAU * theta) * sign
        vy = LOOP_B * math.cos(TAU * theta) * sign
        c_loop = math.atan2(vx, -vy) / TAU
        hop = 0.03 * math.sin(TAU * theta * 6.0) ** 2
    x = home_x * (1.0 - w) + lx * w
    y = (FIG_HOME_Y - STEP_OUT * f) * (1.0 - w) + ly * w
    z = FIG_Z0 + 0.05 * math.sin(math.pi * f) + w * hop
    return x, y, z, bow * (1.0 - w), w * c_loop


def bird(hr: int, tm: float) -> Tuple[float, float]:
    """bird shown amount o (visible when above 0.02) and bob (0..1)."""
    n = calls_for(hr)
    t_end = CALL_FIRST + CALL_GAP * (n - 1) + 1.0
    o = 0.0
    bob = 0.0
    if 0.0 <= tm < PARADE_LEN:
        o = sm((tm - BIRD_SHOW_AT) / BIRD_EASE) * (1.0 - sm((tm - t_end) / BIRD_EASE))
        k = tm - CALL_FIRST
        if k >= 0.0 and k < CALL_GAP * n:
            p = (k % CALL_GAP) / CALL_GAP
            bob = math.sin(math.pi * clamp(p / 0.45, 0.0, 1.0))
    return o, bob


def bird_visible(sod: float) -> bool:
    hr, mi, sc = _split(sod)
    return bird(hr, mi * 60 + sc)[0] > 0.02


# Christmas candles (plan "Christmas candles"): always lit from 1 December through 6 January of the device's local calendar, in
# both modes, and lit the rest of the year only when the user turns on the "Candles all year" setting. WALL_DAY (the engine's E1) counts whole local days since 2000-01-01; the director reads it every frame, so the
# season is a function of the date, never accumulated state.
import datetime as _dt

DAY0 = _dt.date(2000, 1, 1)
BAVARIA_CELL, CLASSIC_CELL = 230, 231   # visibility mailboxes: 1 shows the Bavarian parts (Bavaria mode On) / the Classic parts that Bavaria replaces (Off)
CANDLE_CELL = 214                 # the visibility mailbox of the candle sticks: 1 in season, or when Candles all year is On
FLAME_CELL0 = 215                 # tree i's flames: FLAME_CELL0 + i, lit while the candles show and the window glow of house i % 13 is on
# The flicker (plan docs/plans/2026-11-22-cuckoo-village-candle-flicker.md, Option A): each tree's ten flames are two groups of five
# (the candles with j = 0 and j = 1 of candles.candle_bases), each group built in two shapes. Group index i = 2 * tree + group has two
# visibility cells, FLICKER_CELL0 + 2i (shape 1: tall, leaning one way) and the next (shape 2: short, leaning the other); exactly one is 1
# while the group is lit. Cells 232 to 279; the director's scratch cells start at 600.
FLICKER_CELL0 = 232
FLICKER_F1, FLICKER_F2 = 2.3, 3.7      # revolutions a second: whole cycles a minute (138 and 222), so the pattern repeats each minute
FLICKER_PHI = 0.618034
FLICKER_GROUPS = 2 * 12                # twelve trees, two groups each
TREES = 12
FLOWERS_CELL = 227                # cottage_flowers (the petunia and geranium boxes) shows when Detailed flowers is On
BLOCKS_CELL = 228                 # cottage_flower_blocks (today's blocks) shows when it is Off


def date_of(day: int) -> _dt.date:
    return DAY0 + _dt.timedelta(days=int(day))


def christmas_season(day: int) -> bool:
    """True from 1 December through 6 January inclusive; the range wraps the year boundary."""
    d = date_of(day)
    return d.month == 12 or (d.month == 1 and d.day <= 6)


# The settings object (CuckooVillageSettings, wfsource/source/oas/cuckoovillagesettings.oas): label -> (default, field read by the director).
SETTINGS_DEFAULTS = {"Bavaria mode": 0, "Seasonal events": 1, "Candles all year": 0, "Window lights": 1, "Sound": 1, "Camera motion": 0,
                     "Detailed flowers": 1}


def bavaria_sign(settings: Dict[str, int] = None) -> float:
    """+1 in Classic, -1 in Bavaria mode: the one sign the dial's hands and the parade's direction take (plan "Bavaria mode")."""
    return -1.0 if (settings or SETTINGS_DEFAULTS).get("Bavaria mode", 0) else 1.0


def window_states(sod: float, settings: Dict[str, int] = None) -> List[bool]:
    lights = (settings or SETTINGS_DEFAULTS).get("Window lights", 1)
    out = []
    for i in range(HOUSES):
        s = stagger(i)
        out.append(bool(lights) and (sod >= DUSK_START + s * DUSK_LEN or sod < DAWN_START + s * DAWN_LEN))
    return out


def camera(tm: float, still: bool = False) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    cycle = int(tm // LAP)
    lap_t = tm - cycle * LAP
    hold = HOLD_HOUR if cycle == 0 else (HOLD_QUARTER if cycle in (4, 8, 12) else 0.0)
    u = sm((lap_t - hold) / (LAP - hold))
    b = sm(u / RISE) * sm((1.0 - u) / RISE)
    if still:                       # Camera motion = Still: the wide establishing view from the front, always
        u, b = 0.0, 1.0
    phi = TAU * (-0.25 + u)
    r = CAM_FRONT_R + (CAM_FAR_R - CAM_FRONT_R) * b
    h = CAM_FRONT_H + (CAM_FAR_H - CAM_FRONT_H) * b
    pos = (CAM_X_STRETCH * r * math.cos(phi), r * math.sin(phi), h)
    look = tuple(LOOK_FRONT[k] + (LOOK_FAR[k] - LOOK_FRONT[k]) * b for k in range(3))
    return pos, look      # type: ignore[return-value]


def all_poses(sod: float, settings: Dict[str, int] = None) -> Dict[str, Pose]:
    hr, mi, sc = _split(sod)
    tm = mi * 60 + sc
    ONE = (1.0, 1.0, 1.0)
    poses: Dict[str, Pose] = {}
    sign = bavaria_sign(settings)      # Bavaria mode: the hands sweep anti-clockwise and the parade goes the other way round
    poses["hour_hand"] = (DIAL[0], DIAL[1], DIAL[2], 0.0, sign * hour_rev(hr, mi, sc), 0.0, *ONE)
    poses["minute_hand"] = (DIAL[0], MINUTE_Y, DIAL[2], 0.0, sign * minute_rev(mi, sc), 0.0, *ONE)
    for i, name in enumerate(FIG_NAMES):
        x, y, z, a, c = figure(i, tm, sign)
        poses[name] = poses[FIG_B_NAMES[i]] = (x, y, z, a, 0.0, c, *ONE)
    o, bob = bird(hr, tm)
    poses[BIRD_NAME] = (BIRD_REST[0], BIRD_REST[1] - BIRD_LUNGE * bob, BIRD_REST[2] + 0.04 * bob, 0.06 * bob, 0.0, 0.0, *ONE)
    still = bool((settings or SETTINGS_DEFAULTS).get("Camera motion", 0))
    (cx, cy, cz), (lx, ly, lz) = camera(tm, still)
    poses["cs_wide"] = (cx, cy, cz, 0.0, 0.0, 0.0, *ONE)
    poses["LookAt"] = (lx, ly, lz, 0.0, 0.0, 0.0, *ONE)
    return poses


if __name__ == "__main__":
    for spec in ("10:08:22", "12:00:00", "12:00:05", "15:15:03", "18:00:00"):
        h, m, s = (float(v) for v in spec.split(":"))
        poses = all_poses(h * 3600 + m * 60 + s)
        print(spec, {k: tuple(round(v, 3) for v in poses[k][:6]) for k in ("minute_hand", "hour_hand", "tower_figure_4", "cs_wide")})


def flicker_phase(group_index: int) -> float:
    """The group's phase, in revolutions: group_index is 2 * tree + group, so all 24 differ."""
    return (group_index * FLICKER_PHI) % 1.0


def flame_drive(t: float, group_index: int) -> float:
    """The two-sine drive of a group's flame at t seconds into the minute: above 0 is shape 1, otherwise shape 2."""
    p = flicker_phase(group_index)
    return math.sin(math.tau * (FLICKER_F1 * t + p)) + math.sin(math.tau * (FLICKER_F2 * t + 2.0 * p))


def flame_shape(t: float, tree: int, group: int) -> int:
    """1 (tall, leaning toward the draught) or 2 (short, leaning away) for a tree's group (0 = A, 1 = B) at t seconds into the minute."""
    return 1 if flame_drive(t, 2 * tree + group) > 0.0 else 2


# Option B (a DFRM mesh a tree, ten curves; plan docs/plans/2026-11-22-cuckoo-village-candle-flicker.md): the same drive, as a smooth value
# u = clamp(drive / 1.4, -1, 1); a curve's scale is SCALE0 + SPAN u (0.67 to 1.0, the mesh is authored at its tallest) and its flex bias FLEX_DEG u.
FLICKER_SCALE0, FLICKER_SCALE_SPAN, FLICKER_FLEX_DEG = 0.835, 0.165, 5.0
DFRM_BASE, DFRM_BLOCK = 640, 80        # tree i's control block: 40 header cells, then ten 4-cell curve records


def flame_u(t: float, group_index: int) -> float:
    return max(-1.0, min(1.0, flame_drive(t, group_index) / 1.4))


def deform_cells(t: float, tree: int, curve: int):
    """(scale, flex bias in degrees) written to curve `curve` (0 to 9; its group is curve mod 2) of tree `tree` at t seconds into the minute."""
    u = flame_u(t, 2 * tree + curve % 2)
    return FLICKER_SCALE0 + FLICKER_SCALE_SPAN * u, FLICKER_FLEX_DEG * u
