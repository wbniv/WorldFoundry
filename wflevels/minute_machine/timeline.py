#!/usr/bin/env python3
"""Minute Machine: the one table of times and the pose of every piece.

Plan: docs/plans/2026-11-21-sixty-second-chain-reaction.md.  This module is the
single source of truth.  The Blender builder (parts.py, later) places geometry
from LAYOUT; the Forth director reads the times this module writes with
``--forth``; the engine check compares every frame with ``all_poses``.

Everything here is a pure function of the second of the day.  No state, no
engine, standard library only.

Frame: metres, z up, origin at the table's front-left corner on the table's
top surface, x to the right, y into the screen (depth).  The layout is a flat
side view, 1 px of the plan's mockups = 1 cm, so y is 0 for every piece until
the 3D builder fans the S-curve out.  Rotations are Euler (a, b, c) in
**revolutions**, as the engine writes them: a = pitch (about x), b = roll
(about y), c = heading (about z).  A positive b tips +z toward +x, so a
domino falling to the right has positive b.  A positive a tips +z toward -y,
toward the viewer, so a flap card falling forward has positive a.
"""
from __future__ import annotations

import argparse
import math
import sys
from typing import Dict, List, NamedTuple, Tuple

# ---------------------------------------------------------------------------
# The one table of times: seconds within the minute.  The plan quotes these.
TL = {
    "rail": (0.0, 12.0),
    "dominoes": (12.0, 20.0),
    "seesaw": (20.0, 22.0),
    "sand": (22.0, 52.0),
    "hold": (52.0, 55.0),
    "last": (55.0, 60.0),
    "bucket_empty": (1.0, 7.0),
    "sand_lift": (7.0, 20.0),
    "marble_lift": (30.0, 57.0),
    "comb": (41.0, 52.1),
    "push_in": (50.0, 58.0),
    "pull_back": (1.0, 5.0),
}
FLIP = 0.4          # one flap card falls in 0.4 s
CASCADE = 0.12      # a drum starts 0.12 s after the one to its right
FLIP_STEP = 0.12    # successive flips of a fluttering drum
DOMINO_RATE = 3.0   # dominoes fall three a second
COMB_REARM_EASE = 0.6
PUSH_IN = 0.10      # the camera pushes in 10 %
DRIFT_DEG = 8.0     # camera drift amplitude
DRIFT_PERIOD = 600.0
TEETH = 5
TOOTH_TIME = 0.15
TOOTH_TRAVEL_PX = 4.0

# ---------------------------------------------------------------------------
# Layout, in the mockups' pixels (y down, table top at y = TABLE).  PX is the
# metre value of one pixel.
PX = 0.01
TABLE = 520.0
MR = 12.0                                   # marble radius
RAILS = ((80.0, 118.0, 330.0, 158.0), (360.0, 200.0, 100.0, 244.0), (76.0, 290.0, 352.0, 520.0))
RAIL_TIMES = (4.2, 3.7, 2.9)                # seconds on each rail
GATE_X = 92.0
DOMINO_COUNT = 24
DOMINO_X0, DOMINO_PITCH, DOMINO_W, DOMINO_H = 390.0, 14.5, 5.0, 46.0
DOMINO_LEAN_DEG = math.degrees(math.acos(DOMINO_W / DOMINO_PITCH))
LAST_DOMINO_DEG = 80.0
SEESAW_PIVOT = (745.0, 508.0)
SEESAW_HALF = 50.0
SEESAW_TILT_DEG = 12.0
HOPPER_TOP, HOPPER_BOTTOM = 165.0, 245.0
BUCKET_X, BUCKET_TOP, BUCKET_H = 890.0, 330.0, 56.0
BUCKET_SINK = 46.0
SPRING_TOP_REST, PIN_TOP_REST, SPRING_REST = 170.0, 214.0, 44.0
PIN_X = 1031.0
PAWL = (1052.0, 300.0)
DISPLAY_CENTRE_X, DISPLAY_Z_PX = 1031.0, 390.0
LIFT_BASE_Y = TABLE + 40.0                  # the marble waits under the table
SAND_LIFT_LEN = 358.0
# Whole turns per ride, so each screw is back where it started: the thread pitch is length / turns.
MARBLE_LIFT_TURNS = 32
SAND_LIFT_TURNS = 26
MARBLE_LIFT_X = 60.0
BELL = (625.0, 126.0)
HAMMER = (600.0, 124.0)
DRUM_X = (958.0 + 15.5, 993.0 + 15.5, 1038.0 + 15.5, 1073.0 + 15.5)   # spindles
DRUM_SIZES = (3, 10, 6, 10)                  # tens of hours, hours, tens of minutes, minutes
CAMERA_R_PX = 1100.0                         # the wide camera's distance
SCENE_CENTRE = (560.0, 300.0)
LATCH_POINT = (1031.0, 300.0)

LAYOUT = {k: v for k, v in dict(
    PX=PX, TABLE=TABLE, MR=MR, RAILS=RAILS, RAIL_TIMES=RAIL_TIMES, GATE_X=GATE_X,
    DOMINO_COUNT=DOMINO_COUNT, DOMINO_X0=DOMINO_X0, DOMINO_PITCH=DOMINO_PITCH,
    DOMINO_W=DOMINO_W, DOMINO_H=DOMINO_H, SEESAW_PIVOT=SEESAW_PIVOT, SEESAW_HALF=SEESAW_HALF,
    HOPPER_TOP=HOPPER_TOP, HOPPER_BOTTOM=HOPPER_BOTTOM, BUCKET_X=BUCKET_X, BUCKET_TOP=BUCKET_TOP,
    BUCKET_H=BUCKET_H, BUCKET_SINK=BUCKET_SINK, SPRING_TOP_REST=SPRING_TOP_REST,
    PIN_TOP_REST=PIN_TOP_REST, PIN_X=PIN_X, PAWL=PAWL, LIFT_BASE_Y=LIFT_BASE_Y,
    MARBLE_LIFT_X=MARBLE_LIFT_X, BELL=BELL, HAMMER=HAMMER, DRUM_X=DRUM_X, DRUM_SIZES=DRUM_SIZES,
    DISPLAY_Z_PX=DISPLAY_Z_PX, CAMERA_R_PX=CAMERA_R_PX, SAND_LIFT_LEN=SAND_LIFT_LEN,
    MARBLE_LIFT_TURNS=MARBLE_LIFT_TURNS, SAND_LIFT_TURNS=SAND_LIFT_TURNS).items()}


class Pose(NamedTuple):
    """Position (m), Euler rotation (revolutions), scale."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    sx: float = 1.0
    sy: float = 1.0
    sz: float = 1.0


def c01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def seg(t: float, a: float, b: float) -> float:
    return c01((t - a) / (b - a))


def sm(u: float) -> float:
    u = c01(u)
    return u * u * (3.0 - 2.0 * u)


def lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def m(px: float) -> float:
    return px * PX


def zm(ypx: float) -> float:
    """Height in metres of a pixel row (y down, table top = 0)."""
    return (TABLE - ypx) * PX


def rev(deg: float) -> float:
    return deg / 360.0


def ry(r: Tuple[float, float, float, float], x: float) -> float:
    return r[1] + (x - r[0]) * (r[3] - r[1]) / (r[2] - r[0])


GATE_Y = ry(RAILS[0], GATE_X) - MR          # the marble's centre waiting at the gate

# ---------------------------------------------------------------------------
# The marble: one continuous path through the whole minute.


def marble_px(t: float) -> Tuple[float, float]:
    sq = lambda u: u * u
    T1, T2, T3 = RAIL_TIMES
    t1, t2, t3 = T1, T1 + 0.3 + T2, T1 + 0.3 + T2 + 0.3 + T3          # 4.2, 8.2, 11.4 (see below)
    # rail 1: from the gate to its end; a short drop to rail 2; rail 2; drop; rail 3
    a1, a2 = 4.2, 4.5
    b1, b2 = 8.2, 8.5
    c1 = 11.4
    if t < a1:
        x = lerp(GATE_X, 342.0, sq(t / a1)); return x, ry(RAILS[0], x) - MR
    if t < a2:
        return 342.0, lerp(ry(RAILS[0], 342.0), ry(RAILS[1], 342.0), sq((t - a1) / (a2 - a1))) - MR
    if t < b1:
        x = lerp(342.0, 88.0, sq((t - a2) / (b1 - a2))); return x, ry(RAILS[1], x) - MR
    if t < b2:
        return 88.0, lerp(ry(RAILS[1], 88.0), ry(RAILS[2], 88.0), sq((t - b1) / (b2 - b1))) - MR
    if t < c1:
        x = lerp(88.0, 352.0, sq((t - b2) / (c1 - b2))); return x, ry(RAILS[2], x) - MR
    if t < 12.0:
        return lerp(352.0, 378.0, (t - c1) / (12.0 - c1)), TABLE - MR
    if t < 12.5:                                 # recoils off domino 1
        return lerp(378.0, 362.0, sm((t - 12.0) / 0.5)), TABLE - MR
    if t < 13.2:                                 # drops through the table
        return 362.0, lerp(TABLE - MR, LIFT_BASE_Y, sq((t - 12.5) / 0.7))
    lo, hi = TL["marble_lift"]
    if t < lo:                                   # returns under the table
        return lerp(362.0, MARBLE_LIFT_X, (t - 13.2) / (lo - 13.2)), LIFT_BASE_Y
    if t < hi:                                   # rides the lift
        return MARBLE_LIFT_X, lerp(LIFT_BASE_Y, GATE_Y, (t - lo) / (hi - lo))
    if t < 58.0:
        return lerp(MARBLE_LIFT_X, GATE_X, sm(t - hi)), GATE_Y
    return GATE_X, GATE_Y


# ---------------------------------------------------------------------------
# Dominoes, comb, seesaw, hopper, bucket, spring, pin


def domino_start(i: int) -> float:
    return TL["dominoes"][0] + i / DOMINO_RATE


def domino_end(i: int) -> float:
    return domino_start(i) + (1.0 / DOMINO_RATE if i == DOMINO_COUNT - 1 else 2.0)


def comb_step() -> float:
    lo, hi = TL["comb"]
    return (hi - COMB_REARM_EASE - lo) / (DOMINO_COUNT - 1)


def domino_deg(i: int, t: float) -> float:
    last = i == DOMINO_COUNT - 1
    fin = LAST_DOMINO_DEG if last else DOMINO_LEAN_DEG
    f = domino_start(i)
    r = TL["comb"][0] + comb_step() * i
    if t < f:
        return 0.0
    if t < r:
        u = c01((t - f) / (1.0 / DOMINO_RATE if last else 2.0))
        return fin * (u * u if last else u)
    return fin * (1.0 - sm((t - r) / COMB_REARM_EASE))


def seesaw_u(t: float) -> float:
    return sm(seg(t, 20.3, 20.8)) - sm(seg(t, 52.1, 52.6))


def gate_open(t: float) -> float:
    return sm(seg(t, 21.0, 22.0)) - sm(seg(t, 52.1, 52.6))


def bucket_fill(t: float) -> float:
    s0, s1 = TL["sand"]
    return 1.0 - seg(t, 2.0, 5.5) if t < s0 else seg(t, s0, s1)


def hopper_fill(t: float) -> float:
    s0, s1 = TL["sand"]
    l0, l1 = TL["sand_lift"]
    if t < l0:
        return 0.0
    if t < l1:
        return seg(t, l0, l1)
    if t < s0:
        return 1.0
    return 1.0 - seg(t, s0, s1)


def trough_fill(t: float) -> float:
    if t < 2.0:
        return 0.0
    if t < 5.5:
        return seg(t, 2.0, 5.5)
    if t < 7.0:
        return 1.0
    return 1.0 - seg(t, 7.0, 20.0)


def bucket_tip(t: float) -> float:
    return sm(seg(t, 1.0, 2.5)) - sm(seg(t, 5.5, 7.0))


def pin_travel_px(t: float) -> float:
    if t < 5.5:
        return (TEETH * TOOTH_TRAVEL_PX) * bucket_fill(t)
    if t >= TL["last"][0]:
        return TOOTH_TRAVEL_PX * sum(sm(seg(t, 55.0 + k, 55.0 + k + TOOTH_TIME)) for k in range(TEETH))
    return 0.0


def pawl_click(t: float) -> float:
    if t < TL["last"][0]:
        return 0.0
    f = t - math.floor(t)
    return math.sin(f / 0.25 * math.pi) if f < 0.25 else 0.0


def gate_lift(t: float) -> float:
    return sm(seg(t, 0.0, 0.3)) - sm(seg(t, 1.5, 2.2))


# ---------------------------------------------------------------------------
# The display: four drums of flap cards.


def digits_at(base_sod: float) -> Tuple[int, int, int, int]:
    s = int(round(base_sod)) % 86400
    h, mi = s // 3600, (s // 60) % 60
    return h // 10, h % 10, mi // 10, mi % 10


def drum_pos(k: int, sod: float) -> float:
    """Continuous drum position: the digit shown, plus any flip in progress."""
    t = sod % 60.0
    base = sod - t
    cur, prev = digits_at(base)[k], digits_at(base - 60.0)[k]
    n = DRUM_SIZES[k]
    steps = (cur - prev) % n
    if steps == 0:
        return float(cur)
    tau = t - (3 - k) * CASCADE
    prog = sum(c01((tau - j * FLIP_STEP) / FLIP) for j in range(steps))
    return (prev + prog) % n


def card_deg(q: float, n: int) -> float:
    """Angle of a card whose place behind the drum's position is q (0 <= q < n)."""
    if q <= 1.0:
        u = q
        return 180.0 * u * u
    if q < n - 1.0:
        return 180.0
    return 180.0 * (1.0 - sm(2.0 * (q - (n - 1.0))))


def card_angle_deg(k: int, c: int, sod: float) -> float:
    n = DRUM_SIZES[k]
    q = (drum_pos(k, sod) - c) % n
    return card_deg(q, n)


# ---------------------------------------------------------------------------
# Bell, camera


def bell_swing_deg(t: float) -> float:
    if t <= 0.5 or t >= 7.5:
        return 0.0
    q = t - 0.5
    return 16.0 * (1.0 - q / 7.0) ** 2 * math.sin(2.0 * math.pi * 1.3 * q)


def hammer_deg(t: float) -> float:
    return 24.0 * (1.0 - sm(seg(t, 0.3, 0.5))) + 24.0 * sm(seg(t, 0.5, 1.2))


def push(t: float) -> float:
    """0 wide, 1 fully pushed in toward the latch."""
    return sm(seg(t, *TL["push_in"])) if t >= TL["push_in"][0] else 1.0 - sm(seg(t, *TL["pull_back"]))


# ---------------------------------------------------------------------------
PIECE_ROWS = {      # the plan's pose table: row -> the pieces that implement it
    "Marble on a rail": ["marble"],
    "Domino i": [f"domino_{i:02d}" for i in range(DOMINO_COUNT)],
    "Seesaw, rod, gate": ["seesaw", "rod", "hopper_gate", "rail_gate"],
    "Sand": ["hopper_sand", "bucket_sand", "trough_sand", "stream", "pour"],
    "Spring": ["spring"],
    "Latch pin": ["pin", "pawl"],
    "Flap card": [f"card_{k}_{c}" for k in range(4) for c in range(DRUM_SIZES[k])],
    "Bell": ["bell", "hammer"],
    "Screw lifts": ["marble_lift_screw", "sand_lift_screw"],
    "Camera": ["camera_proxy", "camera_look"],
    "Bucket": ["bucket"],
}


def all_poses(sod: float) -> Dict[str, Pose]:
    """The pose of every piece at second-of-day ``sod`` (0 <= sod < 86400)."""
    sod = sod % 86400.0
    t = sod % 60.0
    minute = int(sod // 60) % 60
    P: Dict[str, Pose] = {}

    mx, my = marble_px(t)
    P["marble"] = Pose(m(mx), 0.0, zm(my))

    for i in range(DOMINO_COUNT):
        P[f"domino_{i:02d}"] = Pose(m(DOMINO_X0 + DOMINO_PITCH * i + DOMINO_W), 0.0, 0.0,
                                    b=rev(domino_deg(i, t)))

    see = seesaw_u(t)
    sa = math.radians(lerp(-SEESAW_TILT_DEG, SEESAW_TILT_DEG, see))
    P["seesaw"] = Pose(m(SEESAW_PIVOT[0]), 0.0, zm(SEESAW_PIVOT[1]), b=-sa / (2.0 * math.pi))
    right_end = SEESAW_PIVOT[1] - SEESAW_HALF * math.sin(sa)
    P["rod"] = Pose(m(795.0), 0.0, zm(right_end))
    P["hopper_gate"] = Pose(m(808.0 - 22.0 * gate_open(t)), 0.0, zm(246.0))
    P["rail_gate"] = Pose(m(107.5), 0.0, zm(GATE_Y - 16.0) + m(22.0 * gate_lift(t)))

    hop, buck, tro = hopper_fill(t), bucket_fill(t), trough_fill(t)
    P["hopper_sand"] = Pose(m(820.0), 0.0, zm(HOPPER_BOTTOM), sz=max(hop, 1e-4))
    sink = BUCKET_SINK * buck
    P["bucket"] = Pose(m(BUCKET_X), 0.0, zm(BUCKET_TOP + sink), b=-rev(105.0 * bucket_tip(t)))
    P["bucket_sand"] = Pose(m(BUCKET_X), 0.0, zm(BUCKET_TOP + sink + BUCKET_H), sz=max(buck, 1e-4))
    P["trough_sand"] = Pose(m(858.0), 0.0, zm(TABLE - 1.0), sz=max(tro, 1e-4))
    s0, s1 = TL["sand"]
    P["stream"] = Pose(m(878.0), 0.0, zm(283.0),
                       sz=max(sm(seg(t, s0, s0 + 0.3)) - sm(seg(t, s1, s1 + 0.3)), 1e-4))
    P["pour"] = Pose(m(862.0), 0.0, zm(BUCKET_TOP + sink + 14.0),
                     sz=max(sm(seg(t, 2.0, 2.3)) - sm(seg(t, 5.5, 5.8)), 1e-4))

    pin = pin_travel_px(t)
    spring_top = SPRING_TOP_REST - BUCKET_SINK * buck
    spring_len = (PIN_TOP_REST - pin) - spring_top
    P["spring"] = Pose(m(PIN_X), 0.0, zm(spring_top), sz=spring_len / SPRING_REST)
    P["pin"] = Pose(m(PIN_X), 0.0, zm(PIN_TOP_REST - pin))
    P["pawl"] = Pose(m(PAWL[0]), 0.0, zm(PAWL[1]), b=-rev(22.0 * pawl_click(t)))

    lo, hi = TL["marble_lift"]
    P["marble_lift_screw"] = Pose(m(MARBLE_LIFT_X), 0.0, zm(LIFT_BASE_Y), c=seg(t, lo, hi) * MARBLE_LIFT_TURNS)
    l0, l1 = TL["sand_lift"]
    P["sand_lift_screw"] = Pose(m(850.0), 0.0, zm(508.0), c=seg(t, l0, l1) * SAND_LIFT_TURNS)

    for k in range(4):
        n = DRUM_SIZES[k]
        for c in range(n):
            P[f"card_{k}_{c}"] = Pose(m(DRUM_X[k]), 0.0, zm(DISPLAY_Z_PX), a=rev(card_angle_deg(k, c, sod)))

    hour_strike = minute == 0
    P["bell"] = Pose(m(BELL[0]), 0.0, zm(BELL[1]), b=rev(bell_swing_deg(t)) if hour_strike else 0.0)
    P["hammer"] = Pose(m(HAMMER[0]), 0.0, zm(HAMMER[1]), b=rev(hammer_deg(t)) if hour_strike else rev(24.0))

    p = push(t)
    az = math.radians(DRIFT_DEG) * math.sin(2.0 * math.pi * sod / DRIFT_PERIOD)
    tx = lerp(SCENE_CENTRE[0], LATCH_POINT[0], p * PUSH_IN * 4.0)
    tz = lerp(SCENE_CENTRE[1], LATCH_POINT[1], p * PUSH_IN * 4.0)
    dist = CAMERA_R_PX / (1.0 + PUSH_IN * p)
    P["camera_look"] = Pose(m(tx), 0.0, zm(tz))
    P["camera_proxy"] = Pose(m(tx + dist * math.sin(az)), -m(dist * math.cos(az)), zm(tz))
    return P


def pose(piece: str, sod: float) -> Pose:
    return all_poses(sod)[piece]


def piece_names() -> List[str]:
    return list(all_poses(0.0))


# ---------------------------------------------------------------------------
def forth_constants() -> str:
    lines = ["\\ generated by wflevels/minute_machine/timeline.py; do not edit"]
    for k, (a, b) in TL.items():
        name = k.replace("_", "-")
        lines.append(f"{a:g} constant mm-{name}-start")
        lines.append(f"{b:g} constant mm-{name}-end")
    lines.append(f"{FLIP:g} constant mm-flip")
    lines.append(f"{CASCADE:g} constant mm-cascade")
    lines.append(f"{DOMINO_COUNT} constant mm-dominoes")
    return "\n".join(lines) + "\n"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--forth", metavar="OUT.fth", help="write the act times as Forth constants")
    ap.add_argument("--at", metavar="HH:MM:SS", help="print every piece's pose at a time of day")
    args = ap.parse_args(argv)
    if args.forth:
        with open(args.forth, "w", encoding="utf-8") as f:
            f.write(forth_constants())
        print(f"wrote {args.forth}")
    if args.at:
        h, mi, s = args.at.split(":")
        for name, ps in all_poses(int(h) * 3600 + int(mi) * 60 + float(s)).items():
            print(f"{name:20s}", " ".join(f"{v:9.4f}" for v in ps))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
