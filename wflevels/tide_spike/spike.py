#!/usr/bin/env python3
"""Tide Harbour Phase 0 spike: geometry, actor groups and the director (zForth) for four throwaway levels.

Plan: docs/plans/2026-11-21-tide-harbour-clock.md, Phase 0 (a) and (b). Nothing here ships: it answers two questions on cast1.

  (a) Can the Chromecast pose N rigid actors every frame, with the river as 36 separately posed bars? Variants:
        a  46 posed actors      b  100 posed actors      c  150 posed actors (D7's budget)
  (b) Can the day turn to dusk and night with no light control? Variant d is variant c on a fast clock (a day in four
      minutes) with a day-to-night look made of translucent "veils" of fixed opacity in front of the camera, one visible at
      a time, and glow overlays in front of the veils so lit windows stay bright.

Pure Python, no Blender (the Blender script imports it), so the geometry and the director can be tested. Metres, z up, x right,
y into the screen. The water is z = 0; the camera looks along +y.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "minute_machine"))
from parts import Mesh  # noqa: E402  (Minute Machine's mesh class: box, prism_xz, cylinder_y)

N_BARS = 36
QUADS = os.environ.get('TANK_SPIKE_QUAD') == '1'            # experiment: build veils, glows and the sky as zero-thickness quads
VARIANTS = {"a": 46, "b": 100, "c": 150, "d": 150, "n": 150, "v": 150, "g": 150}   # posed actors, not counting the veils and glows
CAMERA = (0.0, -22.0, 4.5)
LOOK_AT = (0.0, 12.0, 2.0)
VEIL_DISTANCE = 3.0                                             # the engine's near plane is 1.0 m, fixed
GLOW_DISTANCE = 2.0
N_VEILS = 9                                                     # 1..3 warm (golden hour), 4..9 night; 0 is no veil
VEIL_MAILBOX = 700                                              # 700..708: 1 when that veil is shown
GLOW_MAILBOX = 710                                              # 710..716
DAY_SECONDS_PER_HOUR = 10.0                                     # variant d: a day in 240 s
# The night probe (2026-11-21). On cast1 variant d ran 58 FPS in the morning but 29.97 FPS at night, with the dark veil and the
# lit-window glows on screen. n, v and g are d started at 21:00 (so a 30 s run is all night) with the veil and the glows switched
# on or off, to find what costs the time: n both (the control), v the veil only, g the glows only. d is unchanged (06:00).
FEATURES = {"d": dict(start=6, veils=True, glows=True), "n": dict(start=21, veils=True, glows=True),
            "v": dict(start=21, veils=True, glows=False), "g": dict(start=21, veils=False, glows=True)}

PALETTE: Dict[str, Tuple[float, float, float]] = {
    "sky": (0.44, 0.67, 0.88), "sun": (1.0, 0.93, 0.62), "moon": (0.93, 0.95, 1.0), "wood": (0.40, 0.27, 0.15),
    "wood_hi": (0.58, 0.40, 0.22), "roof": (0.55, 0.20, 0.14), "stone": (0.80, 0.77, 0.68), "gold": (0.80, 0.63, 0.22),
    "dial": (0.96, 0.93, 0.84), "hand": (0.08, 0.07, 0.06), "hull": (0.50, 0.24, 0.13), "canopy": (0.72, 0.58, 0.30),
    "leaf": (0.20, 0.45, 0.18), "cloud": (0.97, 0.97, 0.98), "bird": (0.10, 0.10, 0.12), "speck": (0.95, 0.85, 0.55),
    "glow": (1.0, 0.80, 0.42), "bank": (0.18, 0.28, 0.22),
}
for _k in range(N_BARS):                                       # far = pale, near = deep
    _u = _k / (N_BARS - 1)
    PALETTE[f"bar_{_k:02d}"] = (0.56 - 0.38 * _u, 0.72 - 0.38 * _u, 0.82 - 0.30 * _u)
# Veils: (colour, opacity). The first three are warm, for the hours either side of sunset and sunrise; the rest are night blue.
VEILS: List[Tuple[Tuple[float, float, float], float]] = [
    ((0.95, 0.55, 0.28), 0.14), ((0.92, 0.45, 0.30), 0.24), ((0.62, 0.30, 0.42), 0.36),
    ((0.10, 0.12, 0.30), 0.30), ((0.07, 0.09, 0.26), 0.42), ((0.05, 0.07, 0.22), 0.54),
    ((0.04, 0.05, 0.18), 0.64), ((0.03, 0.04, 0.15), 0.72), ((0.02, 0.03, 0.12), 0.80),
]
for _i, (_c, _o) in enumerate(VEILS):
    PALETTE[f"veil_{_i + 1}"] = _c
VEIL_OPACITY = {f"veil_{i + 1}": o for i, (_c, o) in enumerate(VEILS)}


WATER_NEAR, WATER_FAR = -26.0, 90.0                             # the water runs back behind the camera, so no black shows under it


def bar_y(k: int) -> float:
    """Bars run from behind the camera to the far bank; each one deeper than the last, so they look alike on screen."""
    return WATER_NEAR + (WATER_FAR - WATER_NEAR) * (k / N_BARS) ** 1.7


def bar_depth(k: int) -> float:
    return (bar_y(k + 1) if k + 1 < N_BARS else WATER_FAR) - bar_y(k)


def bar_mesh(k: int) -> Mesh:
    m = Mesh(f"bar_{k:02d}")
    d = bar_depth(k) * 0.5 * 1.18                              # overlap the next bar so a tilt shows no gap
    m.box((-140.0, -d, -0.30), (140.0, d, 0.0), f"bar_{k:02d}")
    return m


def to_camera_ray(target: Tuple[float, float, float], distance: float) -> Tuple[Tuple[float, float, float], float]:
    """The point `distance` metres along y from the camera on the ray through `target`, and the scale that maps the target's size to it."""
    s = distance / (target[1] - CAMERA[1])
    return (CAMERA[0] + (target[0] - CAMERA[0]) * s, CAMERA[1] + distance, CAMERA[2] + (target[2] - CAMERA[2]) * s), s


def veil_mesh(i: int) -> Mesh:
    m = Mesh(f"veil_{i}")
    w, h = 16.0, 9.0
    if QUADS:
        m.face([(-w, 0, -h), (w, 0, -h), (w, 0, h), (-w, 0, h)], f"veil_{i}")   # counter-clockwise seen from -y: faces the camera
    else:
        m.box((-w, 0.0, -h), (w, 0.5, h), f"veil_{i}")         # a box 0.5 m deep
    return m


def glow_mesh(i: int, w: float, h: float) -> Mesh:
    m = Mesh(f"glow_{i}")
    if QUADS:
        m.face([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], "glow")
    else:
        m.box((-w / 2, 0.0, -h / 2), (w / 2, 0.3, h / 2), "glow")
    return m


# Lit windows and lanterns: world position of the target and its size; the overlay is drawn in front of the veils.
GLOW_TARGETS = [((-40.0, -8.05, 2.6), 1.6, 1.8), ((-34.0, -8.05, 2.6), 1.6, 1.8), ((-28.0, -8.05, 2.6), 1.6, 1.8),
                ((19.0, 13.85, 2.6), 1.4, 2.4), ((-18.0, -8.05, 1.9), 0.7, 0.7), ((-10.0, -8.05, 1.9), 0.7, 0.7),
                ((-2.0, -8.05, 1.9), 0.7, 0.7)]


def static_meshes() -> List[Mesh]:
    sky = Mesh("sky")
    if QUADS:
        sky.face([(-300, 90, -10), (300, 90, -10), (300, 90, 140), (-300, 90, 140)], "sky")
    else:
        sky.box((-300, 90, -10), (300, 92, 140), "sky")
    bank = Mesh("bank"); bank.box((-200, 78, -0.3), (200, 90, 2.6), "bank")
    pier = Mesh("pier")
    pier.box((-47, -8, 0.9), (6, -2, 1.15), "wood_hi")
    for x in range(-44, 8, 8):
        pier.box((x - 0.3, -6.2, -1.2), (x + 0.3, -5.6, 0.9), "wood")
    for x0 in (-44.0, -30.0):
        pier.box((x0, -8, 1.15), (x0 + 10, -2, 4.4), "wood")
        pier.prism_xz([(x0 - 1, 4.4), (x0 + 11, 4.4), (x0 + 8, 6.6), (x0 + 2, 6.6)], -8.6, -1.4, "roof")
    tower = Mesh("tower")
    tower.box((16, 14, 0), (22, 20, 9.6), "stone")
    tower.prism_xz([(15.2, 9.6), (22.8, 9.6), (20.2, 12.4), (17.8, 12.4)], 13.2, 20.8, "gold")
    tower.prism_xz([(18.4, 12.4), (20.6, 12.4), (19.5, 14.4)], 16.0, 18.0, "gold")
    dial = Mesh("dial"); dial.cylinder_y(0, 0, 2.0, 0, 0.12, "dial", sides=24)
    return [sky, bank, pier, tower, dial]


DIAL = (19.0, 13.85, 7.2)


def hand_mesh(name: str, length: float, half_width: float) -> Mesh:
    m = Mesh(name)
    m.box((-half_width, -0.14, -0.15), (half_width, 0.0, length), "hand")
    return m


def sphere(name: str, r: float, color: str) -> Mesh:
    m = Mesh(name); m.sphere((0, 0, 0), r, color, segments=14, rings=8)
    return m


def hull_mesh(name: str, length: float) -> Mesh:
    m = Mesh(name)
    h = length / 2
    m.prism_xz([(-h, 0.7), (h, 0.9), (h * 0.7, -0.05), (-h * 0.7, -0.05)], -0.8, 0.8, "hull")
    m.box((-h * 0.45, -0.7, 0.7), (h * 0.35, 0.7, 1.9), "canopy")
    return m


def speck_mesh(name: str, size: float, color: str) -> Mesh:
    m = Mesh(name)
    m.box((-size, -size, -size), (size, size, size), color)
    return m


# Animated actor groups, in director order. Each group's actors are contiguous so one loop poses them.
def groups(variant: str) -> Dict[str, List[Tuple[str, Mesh, Tuple[float, float, float]]]]:
    """name -> list of (actor name, mesh, start position). Bars, then bobbers (boats, raft, hyacinth), then specks."""
    total = VARIANTS[variant]
    g: Dict[str, List] = {"bars": [(f"bar_{k:02d}", bar_mesh(k), (0.0, bar_y(k) + bar_depth(k) / 2, 0.0)) for k in range(N_BARS)]}
    bob = [("boat_0", hull_mesh("boat_0", 6.0), (-14.0, 8.0, 0.0)), ("boat_1", hull_mesh("boat_1", 4.5), (8.0, 14.0, 0.0)),
           ("boat_2", hull_mesh("boat_2", 5.0), (-26.0, 22.0, 0.0))]
    hands = [("hand_h", hand_mesh("hand_h", 1.1, 0.10), DIAL), ("hand_m", hand_mesh("hand_m", 1.7, 0.07), DIAL),
             ("hand_s", hand_mesh("hand_s", 1.85, 0.03), DIAL)]
    sky = [("sun", sphere("sun", 3.0, "sun"), (0, 80, 30)), ("moon", sphere("moon", 2.2, "moon"), (0, 80, -30))]
    used = N_BARS + len(bob) + len(hands) + len(sky)
    extra_bob, specks = [], []
    # fillers stand for the harbour's future detail: ropes, hyacinth, birds, clouds, lanterns, ripples
    want = max(0, total - used)
    for i in range(want):
        x = -52 + (i * 37) % 104
        y = 2 + (i * 53) % 70
        extra_bob.append((f"speck_{i:03d}", speck_mesh(f"speck_{i:03d}", 0.25 + 0.15 * (i % 3), "speck" if i % 2 else "leaf"), (float(x), float(y), 0.6)))
    g["bobbers"] = bob + extra_bob
    g["hands"] = hands
    g["sky"] = sky
    return g


def veil_actors() -> List[Tuple[str, Mesh, Tuple[float, float, float]]]:
    ray, _ = to_camera_ray((0.0, 12.0, 2.0), VEIL_DISTANCE)
    return [(f"veil_{i + 1}", veil_mesh(i + 1), ray) for i in range(N_VEILS)]


def glow_actors() -> List[Tuple[str, Mesh, Tuple[float, float, float]]]:
    out = []
    for i, (t, w, h) in enumerate(GLOW_TARGETS):
        pos, s = to_camera_ray(t, GLOW_DISTANCE)
        out.append((f"glow_{i}", glow_mesh(i, w * s, h * s), pos))
    return out


# ── The director ─────────────────────────────────────────────────────────────
def n(x: float) -> str:
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def director_script(variant: str, ix: Dict[str, int]) -> str:
    """zForth. Cells 600.. are scratch. Variant d runs a day in 240 s; the others follow the wall clock."""
    cells = ["t", "h", "i", "p", "k", "d", "v", "tide", "az", "m"]
    out = ["\\ Tide Harbour spike director (generated by wflevels/tide_spike/spike.py; do not edit)",
           ": ts@ read-mailbox ; : ts! write-mailbox ;"]
    for i, c in enumerate(cells):
        out.append(f": ts-{c} {600 + i} ;")
    out += [
        ": ts-x INDEXOF_X_POS swap write-actor-mailbox ;", ": ts-y INDEXOF_Y_POS swap write-actor-mailbox ;",
        ": ts-z INDEXOF_Z_POS swap write-actor-mailbox ;", ": ts-a INDEXOF_ROTATION_A swap write-actor-mailbox ;",
        ": ts-b INDEXOF_ROTATION_B swap write-actor-mailbox ;",
        ": ts-frac dup floor - ;",                                    # the engine's floor (docs/forth-math-words.md)
        ": ts-mod ( a b -- r ) over over / floor * - ;",            # floored: takes the divisor's sign, unlike fmod
        ": ts-sin sin-rev ; : ts-cos cos-rev ;",
    ]
    if variant in FEATURES:
        clock = f"INDEXOF_TIME ts@ {n(1 / DAY_SECONDS_PER_HOUR)} * {FEATURES[variant]['start']} + 24 ts-mod ts-h ts!"
    else:
        clock = "INDEXOF_WALL_HOUR ts@ INDEXOF_WALL_MINUTE ts@ 60 / + INDEXOF_WALL_SECOND ts@ 3600 / + ts-h ts!"
    # seconds for the swells, from the level clock; hours of the day from the line above
    body = [clock, "  INDEXOF_TIME ts@ ts-t ts!",
            # the tide: a slow swing of 0.6 m, one cycle a minute so it is visible on a screen
            f"  ts-t ts@ {n(1 / 60)} * ts-sin 0.6 * ts-tide ts!"]
    bars = ix["bar_00"]
    body += ["  0 ts-i ts!", "  begin",
             # heave: two waves, bigger toward the camera; the second runs the other way
             f"    ts-t ts@ 0.11 * ts-i ts@ 0.07 * + ts-sin 0.18 *",
             f"    ts-t ts@ 0.07 * ts-i ts@ 0.11 * - ts-sin 0.12 * +",
             f"    0.3 ts-i ts@ {n(1.4 / (N_BARS - 1))} * + * ts-tide ts@ +",
             f"    {n(0.01 * (N_BARS - 1))} ts-i ts@ 0.01 * - +",                  # nearer bars sit 1 cm higher: no coplanar overlap
             f"    {bars} ts-i ts@ + ts-z",
             f"    ts-t ts@ 0.11 * ts-i ts@ 0.07 * + ts-sin 0.003 * {bars} ts-i ts@ + ts-a",
             f"    ts-i ts@ 1 + dup ts-i ts! {N_BARS} =", "  until"]
    nb = len(groups(variant)["bobbers"])
    bob = ix["boat_0"]
    body += ["  0 ts-i ts!", "  begin",
             f"    ts-t ts@ 0.2 * ts-i ts@ 0.137 * + ts-sin 0.14 * ts-tide ts@ + {bob} ts-i ts@ + ts-z",
             f"    ts-t ts@ 0.16 * ts-i ts@ 0.31 * + ts-sin 0.012 * {bob} ts-i ts@ + ts-b",
             f"    ts-i ts@ 1 + dup ts-i ts! {nb} =", "  until"]
    hh, hm, hs = ix["hand_h"], ix["hand_m"], ix["hand_s"]
    body += [f"  ts-h ts@ 12 ts-mod 12 / {hh} ts-b",                  # positive roll about y is clockwise seen from the camera
             f"  ts-h ts@ ts-frac {hm} ts-b",
             f"  ts-t ts@ 60 ts-mod 60 / {hs} ts-b"]
    # the sun and moon on opposite sides of an arc over the harbour
    body += [f"  ts-h ts@ 12 - 24 / ts-az ts!",
             f"  ts-az ts@ ts-sin 70 * {ix['sun']} ts-x", f"  ts-az ts@ ts-cos 40 * 4 - {ix['sun']} ts-z",
             f"  ts-az ts@ ts-sin -70 * {ix['moon']} ts-x", f"  ts-az ts@ ts-cos -40 * 4 - {ix['moon']} ts-z"]
    if variant in FEATURES:
        # darkness d: 0 by day, 1 by night; ramps over 17:00-19:30 and 04:30-07:00
        body += ["  0 ts-d ts!",
                 "  ts-h ts@ 17 >= if ts-h ts@ 17 - 2.5 / 0 max 1 min ts-d ts! then",
                 "  ts-h ts@ 19.5 >= if 1 ts-d ts! then",
                 "  ts-h ts@ 7 < if 1 ts-h ts@ 4.5 - 2.5 / 0 max 1 min - ts-d ts! then",
                 f"  ts-d ts@ {N_VEILS} * 0.5 + floor ts-k ts!"]
        if FEATURES[variant]["veils"]:
            body += ["  0 ts-i ts!", "  begin",
                     f"    ts-k ts@ ts-i ts@ 1 + = if 1 else 0 then {VEIL_MAILBOX} ts-i ts@ + ts!",
                     f"    ts-i ts@ 1 + dup ts-i ts! {N_VEILS} =", "  until"]
        if FEATURES[variant]["glows"]:
            body += ["  0 ts-i ts!", "  begin",
                     f"    ts-d ts@ 0.45 > if 1 else 0 then {GLOW_MAILBOX} ts-i ts@ + ts!",
                     f"    ts-i ts@ 1 + dup ts-i ts! {len(GLOW_TARGETS)} =", "  until"]
    out.append(": ts-tick")
    out += body
    out.append(";")
    out.append("ts-tick")
    return "\n".join(out) + "\n"


def default_indices(variant: str = "c") -> Dict[str, int]:
    names = [name for grp in groups(variant).values() for name, _m, _p in grp]
    return {name: 100 + i for i, name in enumerate(names)}


if __name__ == "__main__":
    for v in VARIANTS:
        gs = groups(v)
        total = sum(len(x) for x in gs.values())
        print(f"variant {v}: {total} posed actors ({', '.join(f'{k} {len(x)}' for k, x in gs.items())}); director {len(director_script(v, default_indices(v)))} chars")
