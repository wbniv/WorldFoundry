#!/usr/bin/env python3
"""Tide Harbour: the pose, colour and visibility of every moving thing, from the date and the time.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (Phase 2). This module is the single source of
truth: parts.py builds geometry from LAYOUT, forth.py emits a director that computes the same
numbers in zForth, and the tests compare the two (tests/verify_tide_harbour_forth.py in the VM,
scripts/check-tide-harbour.py in the engine).

Everything is a pure function of three inputs, no state:

    day      whole days since 2000-01-01 in the device's time zone (the engine's WALL_DAY, E1)
    sod      second of the day, 0 <= sod < 86400 (WALL_HOUR, WALL_MINUTE, WALL_SECOND)
    options  the clock's settings (OPTIONS below; all-zero is the default)

The device's clock is read as Thai time (plan Q7: "device time everywhere, as if Thai"), so the
UTC offset (WALL_UTC_OFFSET) is not used.

Slow things (the tide, the sun, the moon and the look of the light) are evaluated once per whole
second, from floor(sod); fast things (waves, bobbing, birds, hands, camera) every frame.

Frame: metres, z up, x right, y into the screen. The camera looks along +y, which is west across the
river, so +x is north. z = 0 is the tide datum (the table's "lowest low water"), so the water's
mean level is the tide height itself and the gauge board reads it true to scale (Q6).
Rotations are Euler (a, b, c) in revolutions, as the engine writes them: a about x, b about y,
c about z. A positive b is clockwise seen from the camera, which turns the hands.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple

HERE = Path(__file__).resolve().parent
CONSTANTS = json.loads((HERE / "tide_constants.json").read_text())

# ---------------------------------------------------------------------------------------------
# Time
DAY0 = dt.date(2000, 1, 1)                          # WALL_DAY counts from here (E1)
EPOCH_DAY = (dt.date(2026, 1, 1) - DAY0).days       # the tide constants' epoch, 2026-01-01 00:00 Thai time
assert EPOCH_DAY == 9497
TIDE_SPLIT = 64                                     # day = 64 q + r, so every product in the float sum stays small


def wall_day(d: dt.date) -> int:
    return (d - DAY0).days


def date_of(day: int) -> dt.date:
    return DAY0 + dt.timedelta(days=day)


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


def frac(x: float) -> float:
    return x - math.floor(x)


def sin_rev(r: float) -> float:
    return math.sin(2.0 * math.pi * r)


def cos_rev(r: float) -> float:
    return math.cos(2.0 * math.pi * r)


# ---------------------------------------------------------------------------------------------
# The tide: the 64 fitted constituents of tide_constants.json, summed.
Z0 = CONSTANTS["z0_m"]


def tide_terms() -> List[Tuple[float, float, float, float, float]]:
    """Per constituent: (amp, frac(64 * frac(cpd)), frac(cpd), cycles per hour, phase).

    cos(2 pi (cph * hours_since_epoch + phase)) with hours = 24 * day + h is, since the day is a whole
    number, cos(2 pi (frac(64 frac(cpd)) q + frac(cpd) r + cph h + phase)) with day = 64 q + r: the
    dropped parts are whole cycles. The director sums exactly this, so its float error stays small.
    """
    out = []
    for c in CONSTANTS["constituents"]:
        cpd = c["cycles_per_hour"] * 24.0
        a = frac(cpd)
        out.append((c["amp_m"], frac(TIDE_SPLIT * a), a, c["cycles_per_hour"], c["phase_rev"]))
    return out


TERMS = tide_terms()


def tide_m(day: int, sod: float) -> float:
    """Tide height in metres above the datum at Thai local time sod on day (the plain sum, in double)."""
    hours = (day - EPOCH_DAY) * 24.0 + sod / 3600.0
    return Z0 + sum(c["amp_m"] * math.cos(2.0 * math.pi * (c["cycles_per_hour"] * hours + c["phase_rev"]))
                    for c in CONSTANTS["constituents"])


def tide_split_m(day: int, sod: float) -> float:
    """The same sum in the director's form (day split as 64 q + r); equal to tide_m to rounding."""
    d = day - EPOCH_DAY
    q = math.floor(d / TIDE_SPLIT)
    r = d - TIDE_SPLIT * q
    h = sod / 3600.0
    return Z0 + sum(amp * cos_rev(a64 * q + a * r + cph * h + ph) for amp, a64, a, cph, ph in TERMS)


# ---------------------------------------------------------------------------------------------
# The sun (plan D12): NOAA's general solar position formulas (declination and the equation of
# time as Fourier series in the fractional year), for station HD and Thai time. No tables.
LAT_DEG = 13.0 + 44.0 / 60 + 36.0 / 3600            # station HD, Royal Thai Navy Headquarters
LON_DEG = 100.0 + 29.0 / 60 + 25.0 / 3600
ZONE_H = 7.0
YEAR_DAYS = 365.2422
SUNRISE_ZENITH_DEG = 90.833                         # the upper limb at the horizon, with refraction


class Sun(NamedTuple):
    decl: float          # declination, radians
    eqtime: float        # equation of time, minutes
    ha: float            # hour angle, revolutions, -0.5 .. 0.5, positive after solar noon
    north: float         # unit vector toward the sun
    west: float
    up: float
    alt_deg: float       # geometric altitude, degrees


def year_angle(day: int, sod: float) -> float:
    """The fractional year in revolutions: 0 at 2026-01-01 12:00, one per tropical year."""
    return (day - EPOCH_DAY + (sod / 3600.0 - 12.0) / 24.0) / YEAR_DAYS


def decl_eqtime(g: float) -> Tuple[float, float]:
    s1, c1 = sin_rev(g), cos_rev(g)
    s2, c2 = sin_rev(2 * g), cos_rev(2 * g)
    s3, c3 = sin_rev(3 * g), cos_rev(3 * g)
    eqtime = 229.18 * (0.000075 + 0.001868 * c1 - 0.032077 * s1 - 0.014615 * c2 - 0.040849 * s2)
    decl = 0.006918 - 0.399912 * c1 + 0.070257 * s1 - 0.006758 * c2 + 0.000907 * s2 - 0.002697 * c3 + 0.00148 * s3
    return decl, eqtime


def sun(day: int, sod: float) -> Sun:
    decl, eqtime = decl_eqtime(year_angle(day, sod))
    tst = sod / 60.0 + eqtime + 4.0 * LON_DEG - 60.0 * ZONE_H          # true solar time, minutes
    ha = tst / 1440.0 - 0.5                                              # revolutions
    phi = math.radians(LAT_DEG)
    sd, cd = math.sin(decl), math.cos(decl)
    sh, ch = sin_rev(ha), cos_rev(ha)
    up = math.sin(phi) * sd + math.cos(phi) * cd * ch
    north = math.cos(phi) * sd - math.sin(phi) * cd * ch
    west = cd * sh
    alt = 90.0 - math.degrees(math.acos(max(-1.0, min(1.0, up))))
    return Sun(decl, eqtime, ha, north, west, up, alt)


def sunrise_sunset(day: int) -> Tuple[float, float]:
    """Sunrise and sunset, minutes after local midnight (Thai time), for station HD."""
    decl, eqtime = decl_eqtime(year_angle(day, 12 * 3600.0))
    phi = math.radians(LAT_DEG)
    cosh0 = math.cos(math.radians(SUNRISE_ZENITH_DEG)) / (math.cos(phi) * math.cos(decl)) - math.tan(phi) * math.tan(decl)
    h0 = math.degrees(math.acos(cosh0))
    noon = 720.0 - 4.0 * LON_DEG - eqtime + 60.0 * ZONE_H
    return noon - 4.0 * h0, noon + 4.0 * h0


# ---------------------------------------------------------------------------------------------
# The look of the light. No light control (plan, "Runtime control of lights is deliberately not part
# of this plan"): the lights are fixed, and the director re-colours the materials of the day's
# actors through the per-material colour mailboxes (FACE_COLOR_TOP/LIT/SHADOW, 3037-3039). Nothing is
# translucent. The look is a function of the sun's altitude, quantised to whole degrees and held
# constant above LOOK_TOP, so by day nothing is re-coloured at all.
LOOK_BOTTOM, LOOK_TOP = -16, 12
KEYS = (-16.0, -9.0, -4.0, 0.0, 4.0, 12.0)
PALETTES: Dict[str, Tuple[Tuple[float, float, float], ...]] = {
    # K: what the day's colours are multiplied by (night blue, twilight, golden hour, day)
    "k":   ((0.14, 0.16, 0.28), (0.20, 0.21, 0.36), (0.42, 0.36, 0.50), (0.86, 0.62, 0.52), (1.00, 0.80, 0.66), (1.00, 1.00, 1.00)),
    "hor": ((0.05, 0.07, 0.15), (0.10, 0.12, 0.25), (0.55, 0.35, 0.40), (0.98, 0.60, 0.33), (0.98, 0.80, 0.55), (0.78, 0.87, 0.94)),
    "zen": ((0.02, 0.03, 0.08), (0.05, 0.06, 0.16), (0.20, 0.20, 0.38), (0.36, 0.40, 0.62), (0.42, 0.55, 0.78), (0.33, 0.56, 0.86)),
    "sun": ((1.00, 0.40, 0.18), (1.00, 0.40, 0.18), (1.00, 0.40, 0.18), (1.00, 0.52, 0.22), (1.00, 0.72, 0.36), (1.00, 0.95, 0.75)),
}
LIT_KEYS = (1.0, 1.0, 1.0, 0.25, 0.0, 0.0)          # how lit windows and lanterns are, at the same keys
WATER_FAR_DAY = (0.40, 0.52, 0.58)
WATER_NEAR_DAY = (0.16, 0.27, 0.33)
MOON_GLINT = (0.80, 0.85, 0.95)


def look_q(alt_deg: float) -> int:
    return int(max(LOOK_BOTTOM, min(LOOK_TOP, math.floor(alt_deg))))


def ramp_weights(q: float) -> List[float]:
    return [c01((q - KEYS[i]) / (KEYS[i + 1] - KEYS[i])) for i in range(len(KEYS) - 1)]


def keyed(values, w: List[float]) -> float:
    v = values[0]
    for i, wi in enumerate(w):
        v += (values[i + 1] - values[i]) * wi
    return v


def palette(q: float) -> Dict[str, Tuple[float, float, float]]:
    w = ramp_weights(q)
    out = {name: tuple(keyed([key[ch] for key in keys], w) for ch in range(3)) for name, keys in PALETTES.items()}
    out["lit"] = (keyed(LIT_KEYS, w),) * 3
    return out


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def mul(a, b):
    return tuple(x * y for x, y in zip(a, b))


def byte(v: float) -> int:
    return int(math.floor(c01(v) * 255.0 + 0.5))


# ---------------------------------------------------------------------------------------------
# Layout
N_BARS = 36
WATER_NEAR, WATER_FAR = -70.0, 92.0                 # the water runs back behind the camera, and past it: the river panel pulls the camera back to y = -56
BAR_HALF_WIDTH = 260.0                              # wide enough for the frame's far corners at full drift
BAR_THICK = 0.45
BAR_OVERLAP = 1.18
WAVE_F = (0.11, 0.07)                               # Hz; times 3600 a whole number, so the hour wraps cleanly
WAVE_K = (0.07, 0.11)                               # cycles per bar
LOOK_AT = (-2.0, 10.0, 8.0)
CAMERA_R = 54.0                                     # horizontal distance from the look-at point
CAMERA_Z = 12.5
DRIFT_DEG = 6.0
DRIFT_PERIOD = 600.0                                # divides 86400: no jump at midnight
CAMERA_REF = (LOOK_AT[0], LOOK_AT[1] - CAMERA_R, CAMERA_Z)
DECK_Z = 4.1                                        # the pier deck: above the year's highest listed water (3.33 m)
PIER_FRONT_Y = -13.0
CLEAT_Z = DECK_Z + 0.15
BOATS = (  # (name, bow x, bow y, length, moored, swing phase)
    ("boat_0", -24.0, -16.6, 7.0, True, 0.0),
    ("boat_1", -12.0, -16.4, 5.5, True, 0.37),
    ("boat_2", 9.0, 14.0, 9.0, True, 0.71),          # the rice barge at anchor mid-river (no rope drawn)
    ("boat_3", 0.0, 34.0, 6.5, False, 0.0),          # the long-tail crossing the river
)
ROPED = ("boat_0", "boat_1")
BOW_RISE = 0.85                                     # rope eye above the waterline
FERRY_PERIOD = 300.0                                # seconds per crossing; divides 3600
FERRY_SPAN = 150.0
RAFT = (4.0, -9.0)
GAUGE = (-3.0, -13.6)                               # the gauge post, in front of the pier's end
HYACINTH = [(-8.0 + 7.3 * i, 2.0 + (i * 11) % 23, 0.27 * i) for i in range(6)]
HYACINTH_DRIFT = 9.0                                # metres of drift per metre of tide (flood goes upstream)
TOWER = (15.0, -5.0)                                # tower centre (x, y): the tower stands on a quay on the right
TOWER_HALF = 4.2
DIAL = (15.0, -9.28, 14.6)                          # dial centre; its face looks along -y, at the camera
DIAL_R = 3.7                                        # D8: the digits must read across a room; the dial is drawn large
HAND_LEN = {"hand_h": 2.0, "hand_m": 2.95, "hand_s": 3.2}
HAND_Y = {"hand_h": DIAL[1] - 0.10, "hand_m": DIAL[1] - 0.16, "hand_s": DIAL[1] - 0.22}
SKY_Y = 118.0
SUN_Y = 112.0                                       # the sun and moon discs: in front of the sky, behind the far bank
CLOUD_Y = 106.0
CLOUDS = [(30.0 + 7 * i, 86400.0 / (72 + 12 * i), 0.19 * i, 14.0 + 3 * i) for i in range(6)]   # (z, period, phase, half-length)
CLOUD_SPAN = 230.0
BIRDS = [(120.0, 0.0, 11.0, 24.0), (150.0, 0.31, 12.5, 18.0), (180.0, 0.55, 10.0, 30.0),
         (200.0, 0.12, 13.5, 12.0), (240.0, 0.83, 11.8, 36.0), (300.0, 0.44, 12.8, 22.0)]   # (period s, phase, z, y)
BIRD_SPAN = 140.0
LANTERNS = [(-27.0 + 3.0 * i, PIER_FRONT_Y - 0.35, DECK_Z + 2.55) for i in range(8)]
GLINTS = [(-30.0 + 13.0 * i, 26.0 + (i * 17) % 50, 0.29 * i, 0.4 + 0.1 * (i % 4)) for i in range(10)]   # (x, y, phase, Hz)
PARK = (0.0, SUN_Y, -40.0)                          # a hidden disc waits here, inside the room
ROOM = (-360.0, -80.0, -60.0, 360.0, 140.0, 240.0)    # one room holds everything, the sky included

# Visibility mailboxes (global cells the director writes; 1 shows the actor)
VIS = {"sun": 700, "moon": 701, "birds": 702, "boats": 703, "gauge": 704, "numerals_thai": 705, "numerals_roman": 706,
       "arrow_up": 707, "arrow_dn": 708, "panel": 709}
KRATHONG_MAX = 70     # Will 2026-11-26: "cap the count at about 70" (cast1 at night: 24.58 FPS at 100, 30 FPS breaks near 75-80)
VIS.update({f"krathong_{i}": 1100 + i for i in range(KRATHONG_MAX)})
# Settings (plan D13, Q9): the TideHarbourSettings object's fields (wfsource/source/oas/tideharboursettings.oas,
# with the clocks' shared clocksettings.inc). The director copies each field into its cell every frame with
# property@; 0, a field's first choice, is the default.
SETTINGS_ACTOR = "TideHarbourSettings"
FIELD_LABELS = {"drift": "Camera drift", "numerals": "Dial numerals", "gauge": "Gauge board", "life": "Boats and birds",
                "panel": "River panel", "krathong_mode": "River krathongs", "krathong_count": "Krathong count"}
OPTION_CELLS = {"drift": 690, "numerals": 691, "gauge": 692, "life": 693, "panel": 694, "krathong_mode": 695, "krathong_count": 696}
OPTIONS = {   # name -> the values, default first (the cell holds the index)
    "drift": ("Slow", "Off"),
    "numerals": ("Roman", "Thai", "None"),     # Roman is the default (Will, 2026-11-21, reversing Q2)
    "gauge": ("On", "Off"),
    "life": ("On", "Off"),          # boats and birds
    "panel": ("On", "Off"),         # the river panel: Off hides it and gives the harbour the whole screen
    "krathong_mode": ("Festival nights", "Every night"),
    "krathong_count": tuple(str(i) for i in range(KRATHONG_MAX + 1)),
}
DEFAULT_OPTIONS = {k: 0 for k in OPTIONS}
DEFAULT_OPTIONS["krathong_count"] = 30


def bar_y(k: int) -> float:
    """Bars from behind the camera to the far bank; each deeper than the last, so they look alike on screen."""
    return WATER_NEAR + (WATER_FAR - WATER_NEAR) * (k / N_BARS) ** 1.7


def bar_depth(k: int) -> float:
    return (bar_y(k + 1) if k + 1 < N_BARS else WATER_FAR) - bar_y(k)


def bar_amp(k: int) -> float:
    u = 1.0 - k / (N_BARS - 1)
    return 0.03 + 0.14 * u * u


def bar_heave(k: int, t: float) -> float:
    """Height of bar k above the mean water at second-of-the-hour t: two waves running opposite ways."""
    w = 0.6 * sin_rev(WAVE_F[0] * t + WAVE_K[0] * k) + 0.4 * sin_rev(WAVE_F[1] * t - WAVE_K[1] * k)
    return bar_amp(k) * w + 0.01 * (N_BARS - 1 - k)          # nearer bars sit a centimetre higher each: no shared plane


# ---------------------------------------------------------------------------------------------
class Scene(NamedTuple):
    poses: Dict[str, Pose]
    colours: Dict[Tuple[str, int], Tuple[int, int, int]]
    visible: Dict[int, int]
    tide: float
    q: int
    sun: Sun


def slow(day: int, sod: float):
    """What the director evaluates once per whole second."""
    s0 = math.floor(sod)
    return tide_split_m(day, s0), sun(day, s0)


def moon_phase(ha: float) -> float:
    """0 at six hours after solar noon, 1 at six hours before the next: the night's progress (no lunar claim)."""
    return 2.0 * frac(ha - 0.25)


# What each re-coloured material is, per actor: (slot, kind, day colour, lit colour)
RECOLOUR: Dict[str, list] = {}       # actor -> [(slot, kind, day colour, lit colour, argument)], from parts.py


PARTS = None                # parts.py sets this when it is imported (it imports this module, so not the other way round)


def _recolour_table() -> None:
    parts = PARTS
    if parts is None:       # the materials are the geometry's
        import parts
    RECOLOUR.clear()
    for name, slots in parts.recolour_slots().items():
        RECOLOUR[name] = slots


def colour_of(kind: str, day_rgb, lit_rgb, pal, arg: float = 0.0):
    k, hor, zen, lit = pal["k"], pal["hor"], pal["zen"], pal["lit"][0]
    if kind == "k":
        return mul(day_rgb, k)
    if kind == "lit":
        return mix(mul(day_rgb, k), lit_rgb, lit)
    if kind == "soft":
        return mul(day_rgb, tuple(0.5 + 0.5 * x for x in k))
    if kind == "sky":
        return mix(hor, zen, arg)
    if kind == "bar":
        far = tuple(0.55 * h + 0.45 * kk * f for h, kk, f in zip(hor, k, WATER_FAR_DAY))
        near = tuple(kk * n + 0.25 * z for kk, n, z in zip(k, WATER_NEAR_DAY, zen))      # the near water mirrors the sky overhead
        return mix(far, near, arg)
    if kind == "cloud":
        return mix(mul(day_rgb, k), hor, 0.35)
    if kind == "glint":
        return mix(tuple(0.25 + 0.8 * h for h in hor), MOON_GLINT, lit)
    if kind == "sun":
        return pal["sun"]
    if kind in ("panel", "ptext"):          # the river panel: dimmed at night (panel.DIM), the readings less (panel.PTEXT_DIM)
        return mul(day_rgb, (1.0 - (1.0 - (pn.DIM if kind == "panel" else pn.PTEXT_DIM)) * lit,) * 3)
    raise ValueError(kind)


def camera_poses(sod: float, opt: Dict[str, int]):
    """(cs_wide, LookAt, the panel is at the left, how much of it is on screen): where the camera shot is told to be."""
    az = DRIFT_DEG / 360.0 * sin_rev(sod / DRIFT_PERIOD) if opt["drift"] == 0 else 0.0
    left, vis = pn.slide(sod)
    if opt["panel"] != 0:
        vis = 0.0                                       # the panel is switched off: none of it is on screen, so the harbour has the whole screen
    dist = CAMERA_R / pn.harbour_scale(vis)
    lx = LOOK_AT[0] + pn.camera_shift_m(left, vis, dist)
    return (Pose(lx + dist * sin_rev(az), LOOK_AT[1] - dist * cos_rev(az), CAMERA_Z), Pose(lx, LOOK_AT[1], LOOK_AT[2]), left, vis)


DISPLAY_16_9 = (16.0 / 9.0, 60.0)                  # (DISPLAY_ASPECT, DISPLAY_VFOV) the panel was drawn for: a 16:9 television


def scene(day: int, sod: float, options: Dict[str, int] | None = None, display: Tuple[float, float] = DISPLAY_16_9) -> Scene:
    opt = dict(DEFAULT_OPTIONS, **(options or {}))
    sod = sod % 86400.0
    t = sod % 3600.0                                  # second of the hour: every fast motion's period divides it
    h, s = slow(day, sod)
    q = look_q(s.alt_deg)
    P: Dict[str, Pose] = {}

    # the river
    for k in range(N_BARS):
        P[f"bar_{k:02d}"] = Pose(0.0, bar_y(k) + bar_depth(k) / 2, h + bar_heave(k, t),
                                 a=0.004 * sin_rev(WAVE_F[0] * t + WAVE_K[0] * k + 0.25))

    # boats: bob, rock and swing about the bow; the long-tail crosses
    for i, (name, bx, by, length, moored, ph) in enumerate(BOATS):
        bob = 0.06 * sin_rev(0.2 * t + 0.137 * i)
        roll = 0.008 * sin_rev(0.15 * t + 0.31 * i)
        if moored:
            swing = 0.012 * sin_rev(t / 90.0 + ph)
            P[name] = Pose(bx, by, h + bob, b=roll, c=swing)
        else:
            x = -FERRY_SPAN / 2 + FERRY_SPAN * frac(t / FERRY_PERIOD)
            P[name] = Pose(x, by, h + bob, b=roll)
    # ropes: from the cleat on the pier's edge to the bow's eye, a unit bar along +y turned about x and stretched
    for name in ROPED:
        b = P[name]
        dy, dz = b.y - PIER_FRONT_Y, (b.z + BOW_RISE) - CLEAT_Z
        P["rope_" + name[-1]] = Pose(b.x, PIER_FRONT_Y, CLEAT_Z, a=math.atan2(dz, dy) / (2 * math.pi),
                                     sy=math.hypot(dy, dz))

    P["raft"] = Pose(RAFT[0], RAFT[1], h + 0.03 * sin_rev(0.13 * t), a=0.006 * sin_rev(0.09 * t + 0.2))
    for i, (x0, y0, ph) in enumerate(HYACINTH):
        P[f"hyacinth_{i}"] = Pose(x0 + HYACINTH_DRIFT * (h - Z0), y0, h + 0.02 * sin_rev(0.17 * t + ph),
                                  c=frac(t / 1800.0 + ph))
    P["gauge_pointer"] = Pose(GAUGE[0], GAUGE[1], h)

    # the clock
    hr, mi = int(sod // 3600), int(sod // 60) % 60
    sec = sod % 60.0
    P["hand_h"] = Pose(DIAL[0], HAND_Y["hand_h"], DIAL[2], b=((hr % 12) + mi / 60.0 + sec / 3600.0) / 12.0)
    P["hand_m"] = Pose(DIAL[0], HAND_Y["hand_m"], DIAL[2], b=(mi + sec / 60.0) / 60.0)
    P["hand_s"] = Pose(DIAL[0], HAND_Y["hand_s"], DIAL[2], b=sec / 60.0)

    # the sun: hidden behind the camera or below the bank (it is placed below, once the camera is known)
    sun_on = s.west > 0.5 and -2.0 < s.alt_deg < 25.0        # within 60 degrees of west and low: in or near the frame
    # the moon: a disc on an arc across the night, right to left; no claim about its phase or place
    f = moon_phase(s.ha)
    moon_on = 0.0 < f < 1.0 and s.alt_deg < -4.0
    P["moon"] = Pose(60.0 - 120.0 * f, SUN_Y, 4.0 + 30.0 * sin_rev(0.5 * f)) if moon_on else Pose(*PARK)

    for i, (z, period, ph, _half) in enumerate(CLOUDS):
        P[f"cloud_{i}"] = Pose(-CLOUD_SPAN / 2 + CLOUD_SPAN * frac(sod / period + ph), CLOUD_Y - 2 * i, z)
    for i, (period, ph, z, y) in enumerate(BIRDS):
        P[f"bird_{i}"] = Pose(BIRD_SPAN / 2 - BIRD_SPAN * frac(t / period + ph), y, z + 1.2 * sin_rev(t / 36.0 + ph),
                              sz=0.3 + 0.7 * abs(sin_rev(2.5 * t + ph)))
    for i, (x, y, z) in enumerate(LANTERNS):
        P[f"lantern_{i}"] = Pose(x, y, z, b=0.012 * sin_rev(0.3 * t + i / 8.0))
    for i, (x, y, ph, hz) in enumerate(GLINTS):
        P[f"glint_{i}"] = Pose(x, y, h + 0.14, sx=max(0.05, sin_rev(hz * t + ph)))
    for i in range(KRATHONG_MAX):
        y = 14 + (i * 7 % 18) if i % 5 == 0 else (-32 + (i % 4) if i % 2 else -18 + (i % 4))
        P[f"krathong_{i}"] = Pose(-24 if i % 5 else -80, y, h + 0.1)

    # the camera: drifts slowly round the look-at point (burn-in, D10), or stands still. The river panel takes a side of
    # the screen (panel.py): the camera pulls back and shifts so the harbour sits in what the panel leaves, and the panel's
    # parts are posed from the camera's frame.
    P["cs_wide"], P["LookAt"], left, vis = camera_poses(sod, opt)
    # the sun sits on the ray from the camera the shot really has, not from a reference position: the panel pulls the camera
    # back and shifts it sideways and the drift swings it, and the disc is only about 150 m away, so a ray from CAMERA_REF
    # puts the sun a few degrees off its true bearing as the camera sees it
    cam = P["cs_wide"]
    if sun_on:
        k = (SUN_Y - cam.y) / s.west
        P["sun"] = Pose(cam.x + s.north * k, SUN_Y, max(-40.0, cam.z + s.up * k))
    else:
        P["sun"] = Pose(*PARK)
    reading = turns.panel_reading(day, sod)
    P.update(pn.panel_poses(pn.frame_from(P["cs_wide"], P["LookAt"]), sod, left, vis, reading, h, pn.half_w(*display)))

    # colours
    if not RECOLOUR:
        _recolour_table()
    pal = palette(q)
    colours = {}
    for name, slots in RECOLOUR.items():
        for slot, kind, day_rgb, lit_rgb, arg in slots:
            colours[(name, slot)] = tuple(byte(v) for v in colour_of(kind, day_rgb, lit_rgb, pal, arg))

    life = opt["life"] == 0
    visible = {VIS["sun"]: int(sun_on), VIS["moon"]: int(moon_on), VIS["birds"]: int(life and s.alt_deg > 0.0),
               VIS["boats"]: int(life), VIS["gauge"]: int(opt["gauge"] == 0),
               VIS["numerals_thai"]: int(opt["numerals"] == 1), VIS["numerals_roman"]: int(opt["numerals"] == 0),
               VIS["arrow_up"]: int(reading.rise and opt["panel"] == 0), VIS["arrow_dn"]: int(not reading.rise and opt["panel"] == 0),
               VIS["panel"]: int(opt["panel"] == 0)}
    visible.update({VIS[f"krathong_{i}"]: 0 for i in range(KRATHONG_MAX)})
    return Scene(P, colours, visible, h, q, s)


def all_poses(day: int, sod: float, options: Dict[str, int] | None = None, display: Tuple[float, float] = DISPLAY_16_9) -> Dict[str, Pose]:
    return scene(day, sod, options, display).poses


def piece_names() -> List[str]:
    return list(all_poses(EPOCH_DAY, 0.0))


def parse_when(spec: str) -> Tuple[int, float]:
    """'2026-11-21T17:40:00' -> (WALL_DAY, second of the day)."""
    d, t = spec.split("T")
    y, m, dd = (int(x) for x in d.split("-"))
    hh, mm, ss = t.split(":")
    return wall_day(dt.date(y, m, dd)), int(hh) * 3600 + int(mm) * 60 + float(ss)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--at", metavar="YYYY-MM-DDTHH:MM:SS", help="print the tide, the sun and every pose at that Thai time")
    ap.add_argument("--sun", metavar="YYYY-MM-DD", help="print sunrise and sunset for that date")
    args = ap.parse_args(argv)
    if args.sun:
        y, m, d = (int(x) for x in args.sun.split("-"))
        rise, sett = sunrise_sunset(wall_day(dt.date(y, m, d)))
        print(f"sunrise {int(rise // 60):02d}:{rise % 60:04.1f}  sunset {int(sett // 60):02d}:{sett % 60:04.1f}")
    if args.at:
        day, sod = parse_when(args.at)
        sc = scene(day, sod)
        print(f"tide {sc.tide:.3f} m; sun altitude {sc.sun.alt_deg:.2f} deg (look {sc.q}); west {sc.sun.west:.3f}")
        for name, p in sc.poses.items():
            print(f"{name:16s}", " ".join(f"{v:9.4f}" for v in p))
    return 0


# The river panel and the next-turn search use this module (and it uses them): imported last, so each finds this module
# complete in sys.modules whichever of the three was imported first.
import panel as pn  # noqa: E402
import turns  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
