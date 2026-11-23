"""Minute Machine geometry: every piece as a mesh around its pivot.

Pure Python, no Blender, so tests can check it. The Blender script
(blender_create_minute_machine.py) turns these into objects. Every number comes
from timeline.LAYOUT, so the poses and the geometry cannot drift apart.

Conventions: metres, z up, x right, y into the screen. A moving piece's pose is
the position of its mesh origin, so each mesh is built with its pivot at (0, 0, 0).
Closed boxes use Blender's exterior winding, so no face disappears under the
engine's back-face cull and a flap card shows its art on both sides.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import timeline as tl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clock_common"))
from clock_mesh import BOX_FACES, V3, Mesh  # noqa: E402,F401  (the shared mesh builder, hoisted from here)

PX = tl.PX

PALETTE: Dict[str, Tuple[float, float, float]] = {
    "wood": (.45, .30, .17), "wood_hi": (.62, .43, .25), "table": (.23, .16, .11),
    "brass": (.78, .60, .22), "steel": (.50, .54, .60), "dark": (.10, .11, .14),
    "marble": (.82, .24, .15), "sand": (.89, .76, .48), "rope": (.85, .83, .76),
    "card": (.05, .055, .065), "digit": (.80, .78, .70), "housing": (.14, .15, .19),
    "bell": (.81, .65, .29),
}
DOMINO_COLORS = [f"domino_{i}" for i in range(tl.DOMINO_COUNT)]
for _i, _k in enumerate(DOMINO_COLORS):
    h = (_i * 15.0 + 8.0) / 360.0
    r = [abs(6 * ((h + o) % 1.0) - 3) - 1 for o in (0.0, -2.0 / 3.0 + 1, -1.0 / 3.0 + 1)]
    PALETTE[_k] = tuple(max(0.0, min(1.0, .35 + .55 * v)) for v in r)


def m(px: float) -> float:
    return px * PX


# ---------------------------------------------------------------------------
SEGMENTS = {0: "abcdef", 1: "bc", 2: "abdeg", 3: "abcdg", 4: "bcfg", 5: "acdfg", 6: "acdefg", 7: "abc", 8: "abcdefg", 9: "abcdfg"}
CARD_W, CARD_HALF, CARD_T = 0.31, 0.52, 0.008
ART_T = 0.004                 # how far a digit stands off its card
HOUSING_BACK_Y = 0.15         # the housing's back plate: behind the deepest fallen card
DIG_X, DIG_H, SEG = 0.095, 0.44, 0.052


def card_mesh(k: int, c: int) -> Mesh:
    """Card c of drum k. Front: top half of digit c. Back: bottom half of digit (c + 1) mod n."""
    n = tl.DRUM_SIZES[k]
    mesh = Mesh(f"card_{k}_{c}")
    mesh.box((-CARD_W / 2, -CARD_T / 2, 0.0), (CARD_W / 2, CARD_T / 2, CARD_HALF), "card")
    front, back = c, (c + 1) % n
    top_only = {"a", "f", "b"}
    bottom_only = {"d", "e", "c"}
    y_front, y_back = -CARD_T / 2, CARD_T / 2

    def half(digit, top, y, direction):
        segs = SEGMENTS[digit]
        thick = ART_T
        y0, y1 = (y - thick, y) if direction > 0 else (y, y + thick)
        t = SEG / 2
        spans = {"a": (-DIG_X, DIG_X, DIG_H - SEG, DIG_H), "g": (-DIG_X + SEG, DIG_X - SEG, 0.0, t),
                 "f": (-DIG_X, -DIG_X + SEG, 0.0, DIG_H), "b": (DIG_X - SEG, DIG_X, 0.0, DIG_H),
                 "e": (-DIG_X, -DIG_X + SEG, 0.0, DIG_H), "c": (DIG_X - SEG, DIG_X, 0.0, DIG_H),
                 "d": (-DIG_X, DIG_X, DIG_H - SEG, DIG_H)}
        for name in segs:
            if top and name in bottom_only:
                continue
            if not top and name in top_only:
                continue
            x0, x1, z0, z1 = spans[name]
            # z is the distance from the spindle outward (0 .. CARD_HALF) on both faces: the back
            # art is already mirrored, because the card has turned half a turn about x when it shows.
            mesh.box((x0, y0, z0), (x1, y1, z1), "digit")

    half(front, True, y_front, +1)
    half(back, False, y_back, -1)
    return mesh


def housing_static() -> Mesh:
    mesh = Mesh("display_housing")
    cx = [m(tl.DRUM_X[k]) for k in range(4)]
    z0, z1 = m(tl.TABLE - (tl.DISPLAY_Z_PX + 62.0)), m(tl.TABLE - (tl.DISPLAY_Z_PX - 62.0))
    mesh.box((m(951.0), HOUSING_BACK_Y, z0), (m(1113.0), HOUSING_BACK_Y + 0.06, z1), "housing")
    mesh.box((m(951.0), -0.06, z0), (m(960.0), HOUSING_BACK_Y + 0.06, z1), "housing")
    mesh.box((m(1103.0), -0.06, z0), (m(1113.0), HOUSING_BACK_Y + 0.06, z1), "housing")
    mesh.box((m(951.0), -0.06, z1 - 0.07), (m(1113.0), HOUSING_BACK_Y + 0.06, z1), "housing")
    mesh.box((m(951.0), -0.06, z0), (m(1113.0), HOUSING_BACK_Y + 0.06, z0 + 0.07), "housing")
    zc = m(tl.TABLE - tl.DISPLAY_Z_PX)
    for dz in (-0.14, 0.14):
        mesh.sphere((m(1031.0), 0.0, zc + dz), 0.035, "digit", 8, 6)
    for x in cx:
        mesh.cylinder_y(x, zc, 0.012, -0.05, HOUSING_BACK_Y, "steel", 6)
    return mesh


# ---------------------------------------------------------------------------
def hopper_walls() -> Mesh:
    mesh = Mesh("hopper_walls")
    z = lambda ypx: m(tl.TABLE - ypx)
    mesh.beam((m(780.0), z(165.0)), (m(812.0), z(245.0)), 0.035, -0.22, 0.22, "steel")
    mesh.beam((m(860.0), z(165.0)), (m(828.0), z(245.0)), 0.035, -0.22, 0.22, "steel")
    mesh.box((m(776.0), -0.22, z(168.0)), (m(864.0), -0.19, z(164.0)), "steel")
    for x in (788.0, 852.0):
        mesh.box((m(x) - 0.02, -0.12, 0.0), (m(x) + 0.02, -0.08, z(214.0)), "wood")
    mesh.beam((m(820.0), z(254.0)), (m(878.0), z(287.0)), 0.04, -0.12, 0.12, "steel")       # chute
    return mesh


def rails_static() -> Mesh:
    mesh = Mesh("rails")
    z = lambda ypx: m(tl.TABLE - ypx)
    for r in tl.RAILS:
        mesh.beam((m(r[0]), z(r[1])), (m(r[2]), z(r[3])), 0.07, -0.16, 0.16, "wood_hi")
    for x0, z0, z1 in ((366.0, 146.0, 208.0), (70.0, 234.0, 298.0)):
        mesh.box((m(x0) - 0.03, -0.16, z(z1)), (m(x0) + 0.03, 0.16, z(z0)), "wood")
    mesh.box((m(40.0), -0.2, z(520.0)), (m(80.0), 0.2, z(474.0)), "dark")
    return mesh


def frame_static() -> Mesh:
    mesh = Mesh("frame")
    z = lambda ypx: m(tl.TABLE - ypx)
    mesh.box((m(584.0) - 0.035, -0.04, 0.0), (m(584.0) + 0.035, 0.04, z(120.0)), "wood")
    mesh.box((m(584.0), -0.04, z(124.0)), (m(642.0), 0.04, z(120.0)), "wood")
    mesh.box((m(880.0), -0.06, z(66.0)), (m(1040.0), 0.06, z(58.0)), "wood")
    mesh.box((m(899.0) - 0.015, -0.04, z(92.0)), (m(899.0) + 0.015, 0.04, z(62.0)), "wood")
    mesh.box((m(1022.0) - 0.015, -0.04, z(92.0)), (m(1022.0) + 0.015, 0.04, z(62.0)), "wood")
    for x in (899.0, 1022.0):
        mesh.cylinder_y(m(x), z(92.0), 0.09, -0.07, 0.07, "brass", 14)
    mesh.beam((m(899.0), z(83.0)), (m(1022.0), z(83.0)), 0.014, -0.01, 0.01, "rope")
    mesh.box((m(745.0) - 0.05, -0.12, 0.0), (m(745.0) + 0.05, 0.12, z(508.0)), "wood")
    mesh.box((m(1050.0), -0.05, z(330.0)), (m(1058.0), 0.05, z(270.0)), "steel")
    mesh.box((m(1021.0), -0.06, z(214.0)), (m(1041.0), 0.0, z(100.0)), "dark")       # latch guide behind the pin
    mesh.box((m(830.0), -0.12, z(520.0)), (m(886.0), 0.12, z(506.0)), "steel")        # trough
    return mesh


def table_static() -> Mesh:
    mesh = Mesh("table")
    mesh.box((-0.8, -1.4, -1.1), (12.4, 1.6, 0.0), "table")
    mesh.box((-0.8, 1.55, 0.0), (12.4, 1.65, 7.2), "dark")
    return mesh


def marble_mesh() -> Mesh:
    mesh = Mesh("marble")
    mesh.sphere((0.0, 0.0, 0.0), m(tl.MR), "marble", 14, 9)
    return mesh


def domino_mesh(i: int) -> Mesh:
    mesh = Mesh(f"domino_{i:02d}")
    mesh.box((-m(tl.DOMINO_W), -0.1, 0.0), (0.0, 0.1, m(tl.DOMINO_H)), DOMINO_COLORS[i])
    return mesh


def seesaw_mesh() -> Mesh:
    mesh = Mesh("seesaw")
    mesh.box((-m(tl.SEESAW_HALF), -0.1, -0.03), (m(tl.SEESAW_HALF), 0.1, 0.03), "wood_hi")
    return mesh


def rod_mesh() -> Mesh:
    mesh = Mesh("rod")
    mesh.box((-0.015, -0.015, 0.0), (0.015, 0.015, 2.52), "steel")
    return mesh


def hopper_gate_mesh() -> Mesh:
    mesh = Mesh("hopper_gate")
    mesh.box((-0.12, -0.12, -0.025), (0.12, 0.12, 0.025), "brass")
    return mesh


def rail_gate_mesh() -> Mesh:
    mesh = Mesh("rail_gate")
    mesh.box((-0.025, -0.16, -0.30), (0.025, 0.16, 0.0), "brass")
    return mesh


def hopper_sand_mesh() -> Mesh:
    mesh = Mesh("hopper_sand")
    mesh.box((-0.07, -0.15, 0.0), (0.07, 0.15, m(80.0)), "sand")
    return mesh


def bucket_mesh() -> Mesh:
    mesh = Mesh("bucket")
    h, wt, wb = m(tl.BUCKET_H), 0.26, 0.19
    mesh.beam((-wt, 0.0), (-wb, -h), 0.035, -0.17, 0.17, "wood")
    mesh.beam((wt, 0.0), (wb, -h), 0.035, -0.17, 0.17, "wood")
    mesh.box((-wb, -0.17, -h - 0.03), (wb, 0.17, -h), "wood")
    mesh.box((-0.008, -0.01, 0.0), (0.008, 0.01, 0.18), "rope")
    return mesh


def bucket_sand_mesh() -> Mesh:
    mesh = Mesh("bucket_sand")
    mesh.box((-0.18, -0.16, 0.0), (0.18, 0.16, m(tl.BUCKET_H) - 0.06), "sand")
    return mesh


def trough_sand_mesh() -> Mesh:
    mesh = Mesh("trough_sand")
    mesh.box((-0.25, -0.1, 0.0), (0.25, 0.1, 0.11), "sand")
    return mesh


def stream_mesh(name: str, length: float) -> Mesh:
    mesh = Mesh(name)
    mesh.box((-0.012, -0.012, -length), (0.012, 0.012, 0.0), "sand")
    return mesh


def string_mesh(name: str) -> Mesh:
    mesh = Mesh(name)
    mesh.box((-0.006, -0.006, -1.0), (0.006, 0.006, 0.0), "rope")     # unit length, scaled in z
    return mesh


def spring_mesh() -> Mesh:
    mesh = Mesh("spring")
    n, w, h = 8, 0.07, m(tl.SPRING_REST)
    pts = [(0.0, 0.0)] + [(w if k % 2 == 0 else -w, -h * (k + 0.5) / n) for k in range(n)] + [(0.0, -h)]
    for a, b in zip(pts, pts[1:]):
        mesh.beam(a, b, 0.012, -0.012, 0.012, "brass")
    return mesh


def pin_mesh() -> Mesh:
    mesh = Mesh("pin")
    mesh.box((-0.04, -0.04, -1.10), (0.04, 0.04, 0.0), "steel")
    for k in range(tl.TEETH + 1):
        z = -0.84 - k * tl.TOOTH_TRAVEL_PX * PX
        mesh.prism_xz([(0.04, z), (0.085, z - 0.02), (0.04, z - 0.04)], -0.03, 0.03, "steel")
    return mesh


def pawl_mesh() -> Mesh:
    mesh = Mesh("pawl")
    mesh.prism_xz([(0.0, 0.0), (-0.13, -0.04), (-0.13, 0.04)][::-1], -0.04, 0.04, "brass")
    return mesh


def screw_mesh(name: str, length: float, turns: int, radius: float) -> Mesh:
    """A shaft with a helical fin, `turns` whole turns over `length`; pivot at the base."""
    mesh = Mesh(name)
    mesh.column_z(0.0, 0.0, 0.0, length, 0.05, "steel", 8)
    steps = turns * 8
    for s in range(steps):
        a0, a1 = math.tau * s / 8, math.tau * (s + 1) / 8
        z0, z1 = length * s / steps, length * (s + 1) / steps
        pts = [(radius * math.cos(a0), radius * math.sin(a0), z0), (radius * math.cos(a1), radius * math.sin(a1), z1)]
        w = 0.035
        mesh.face([(pts[0][0], pts[0][1], pts[0][2]), (pts[1][0], pts[1][1], pts[1][2]),
                   (pts[1][0] * .2, pts[1][1] * .2, pts[1][2] + w), (pts[0][0] * .2, pts[0][1] * .2, pts[0][2] + w)], "brass")
        mesh.face([(pts[0][0] * .2, pts[0][1] * .2, pts[0][2] + w), (pts[1][0] * .2, pts[1][1] * .2, pts[1][2] + w),
                   (pts[1][0], pts[1][1], pts[1][2]), (pts[0][0], pts[0][1], pts[0][2])], "brass")
    return mesh


def bell_mesh() -> Mesh:
    mesh = Mesh("bell")
    mesh.box((-0.012, -0.012, -0.10), (0.012, 0.012, 0.0), "steel")
    for j in range(5):
        a0, a1 = math.pi / 2 * j / 5, math.pi / 2 * (j + 1) / 5
        r0, r1 = 0.20 * math.sin(a0), 0.20 * math.sin(a1)
        z0, z1 = -0.10 - 0.36 * (1 - math.cos(a0)), -0.10 - 0.36 * (1 - math.cos(a1))
        sides = 12
        for i in range(sides):
            ang0, ang1 = math.tau * i / sides, math.tau * (i + 1) / sides
            mesh.face([(r0 * math.cos(ang1), r0 * math.sin(ang1), z0), (r0 * math.cos(ang0), r0 * math.sin(ang0), z0),
                       (r1 * math.cos(ang0), r1 * math.sin(ang0), z1), (r1 * math.cos(ang1), r1 * math.sin(ang1), z1)], "bell")
    mesh.sphere((0.0, 0.0, -0.46), 0.022, "steel", 6, 4)
    return mesh


def hammer_mesh() -> Mesh:
    mesh = Mesh("hammer")
    mesh.box((-0.015, -0.02, -0.36), (0.015, 0.02, 0.0), "steel")
    mesh.box((-0.04, -0.04, -0.40), (0.04, 0.04, -0.32), "steel")
    return mesh


def all_meshes() -> Dict[str, Mesh]:
    """Every dynamic piece's mesh, keyed by its timeline piece name."""
    out: Dict[str, Mesh] = {
        "marble": marble_mesh(), "seesaw": seesaw_mesh(), "rod": rod_mesh(), "hopper_gate": hopper_gate_mesh(),
        "rail_gate": rail_gate_mesh(), "hopper_sand": hopper_sand_mesh(), "bucket": bucket_mesh(),
        "bucket_sand": bucket_sand_mesh(), "trough_sand": trough_sand_mesh(),
        "stream": stream_mesh("stream", m(60.0)), "pour": stream_mesh("pour", m(60.0)),
        "string_l": string_mesh("string_l"), "string_r": string_mesh("string_r"),
        "spring": spring_mesh(), "pin": pin_mesh(), "pawl": pawl_mesh(),
        "marble_lift_screw": screw_mesh("marble_lift_screw", m(tl.LIFT_BASE_Y - tl.GATE_Y), tl.MARBLE_LIFT_TURNS, 0.20),
        "sand_lift_screw": screw_mesh("sand_lift_screw", m(tl.SAND_LIFT_LEN), tl.SAND_LIFT_TURNS, 0.17),
        "bell": bell_mesh(), "hammer": hammer_mesh(),
    }
    for i in range(tl.DOMINO_COUNT):
        out[f"domino_{i:02d}"] = domino_mesh(i)
    for k in range(4):
        for c in range(tl.DRUM_SIZES[k]):
            out[f"card_{k}_{c}"] = card_mesh(k, c)
    return out


def static_meshes() -> List[Mesh]:
    return [table_static(), rails_static(), frame_static(), hopper_walls(), housing_static()]
