"""Tide Harbour geometry: every actor as a mesh around its pivot, and what each material does at night.

Pure Python, no Blender, so tests can check it. blender_create_tide_harbour.py turns these into
objects; the Thai and Roman dial numerals are the one exception, drawn from fonts inside Blender.
Every position comes from timeline.py, so poses and geometry cannot drift apart.

Low-poly flat colour (plan D9). A moving actor's pose is its mesh origin, so each moving mesh is
built around its pivot. The materials of a mesh are its colour keys in first-use order; the director
re-colours slots 0 to 2 (FACE_COLOR_TOP, _LIT, _SHADOW), so a re-coloured key must sit in one of
the first three slots (test_tide_harbour_parts.py checks).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import timeline as tl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clock_common"))
from clock_mesh import Mesh, face_normal  # noqa: E402

RGB = Tuple[float, float, float]
NONE: RGB = (0.0, 0.0, 0.0)

# key -> (kind, day colour, lit colour, argument). Kinds are timeline.colour_of's; "fixed" is never re-coloured.
MATERIALS: Dict[str, Tuple[str, RGB, RGB, float]] = {
    "land": ("k", (0.20, 0.30, 0.20), NONE, 0.0),
    "far_roof": ("k", (0.62, 0.30, 0.22), NONE, 0.0),
    "far_window": ("lit", (0.30, 0.30, 0.28), (1.00, 0.78, 0.42), 0.0),
    "deck": ("k", (0.58, 0.40, 0.24), NONE, 0.0),
    "post": ("k", (0.36, 0.25, 0.15), NONE, 0.0),
    "wall": ("k", (0.66, 0.50, 0.32), NONE, 0.0),
    "roof": ("k", (0.55, 0.20, 0.14), NONE, 0.0),
    "window": ("lit", (0.16, 0.18, 0.22), (1.00, 0.82, 0.45), 0.0),
    "stone": ("k", (0.86, 0.82, 0.72), NONE, 0.0),
    "gold": ("k", (0.84, 0.64, 0.22), NONE, 0.0),
    "arch": ("lit", (0.30, 0.26, 0.22), (1.00, 0.70, 0.36), 0.0),
    "board": ("soft", (0.95, 0.95, 0.90), NONE, 0.0),
    "marks": ("soft", (0.08, 0.08, 0.10), NONE, 0.0),
    "pointer": ("soft", (0.85, 0.15, 0.10), NONE, 0.0),
    "hull": ("k", (0.45, 0.22, 0.12), NONE, 0.0),
    "canopy": ("k", (0.74, 0.60, 0.32), NONE, 0.0),
    "trim": ("k", (0.12, 0.35, 0.55), NONE, 0.0),
    "barge": ("k", (0.30, 0.20, 0.12), NONE, 0.0),
    "rope": ("k", (0.80, 0.72, 0.55), NONE, 0.0),
    "raft": ("k", (0.62, 0.48, 0.30), NONE, 0.0),
    "leaf": ("k", (0.22, 0.48, 0.20), NONE, 0.0),
    "flower": ("k", (0.62, 0.45, 0.80), NONE, 0.0),
    "lantern": ("lit", (0.78, 0.13, 0.10), (1.00, 0.55, 0.25), 0.0),
    "lantern_cap": ("k", (0.20, 0.16, 0.10), NONE, 0.0),
    "cloud": ("cloud", (0.97, 0.97, 0.98), NONE, 0.0),
    "glint": ("glint", NONE, NONE, 0.0),
    "sun": ("sun", (1.00, 0.95, 0.75), NONE, 0.0),
    # never re-coloured: what tells the time stays readable at night (spike finding 4), and the moon stays bright
    "dial": ("fixed", (0.96, 0.93, 0.84), NONE, 0.0),
    "rim": ("fixed", (0.84, 0.64, 0.22), NONE, 0.0),
    "ink": ("fixed", (0.10, 0.08, 0.06), NONE, 0.0),
    "hand": ("fixed", (0.08, 0.07, 0.06), NONE, 0.0),
    "second": ("fixed", (0.75, 0.10, 0.08), NONE, 0.0),
    "moon": ("fixed", (0.93, 0.95, 1.00), NONE, 0.0),
    "bird": ("fixed", (0.10, 0.10, 0.12), NONE, 0.0),
}
SKY_EDGES = (-20.0, 4.0, 8.0, 13.0, 19.0, 26.0, 34.0, 44.0, 58.0, 80.0, 220.0)   # narrow near the horizon, where the colour changes fastest
for _i in range(len(SKY_EDGES) - 1):
    MATERIALS[f"sky_{_i}"] = ("sky", (0.6, 0.75, 0.9), NONE, (_i / (len(SKY_EDGES) - 2)) ** 0.8)
for _k in range(tl.N_BARS):
    MATERIALS[f"water_{_k:02d}"] = ("bar", (0.3, 0.4, 0.45), NONE, 1.0 - _k / (tl.N_BARS - 1))     # nearness: bar 0 is the nearest


def day_colour(key: str) -> RGB:
    """The authored (daytime) colour: what the level is built with, and what the look gives above LOOK_TOP."""
    kind, day, lit, arg = MATERIALS[key]
    if kind == "fixed":
        return day
    return tl.colour_of(kind, day, lit, tl.palette(tl.LOOK_TOP), arg)


# ---------------------------------------------------------------------------------------------
# Static scenery
def sky_meshes() -> List[Mesh]:
    out = []
    for i in range(len(SKY_EDGES) - 1):
        m = Mesh(f"sky_{i}")
        m.quad_y(-320.0, SKY_EDGES[i], 320.0, SKY_EDGES[i + 1], tl.SKY_Y, f"sky_{i}")
        out.append(m)
    return out


def bank_mesh() -> Mesh:
    m = Mesh("far_bank")
    y0, y1 = 84.0, 96.0
    m.box((-320.0, y0, -1.5), (320.0, y1, 2.2), "land")
    for i in range(34):                                    # trees: dark blocks of varied height
        x = -150.0 + 9.1 * i + (i * 37 % 5)
        h = 4.0 + (i * 53 % 7) * 0.8
        m.box((x, y0 + 1.0 + (i % 3), 2.2), (x + 5.0 + i % 3, y0 + 4.0 + (i % 3), 2.2 + h), "land")
    for i, x in enumerate((-95.0, -62.0, -18.0, 26.0, 58.0, 90.0)):    # houses on the far bank, each with two lit windows
        w = 7.0 + i % 3
        m.box((x, y0 + 0.5, 2.2), (x + w, y0 + 6.0, 6.2), "far_roof")
        for k in range(2):
            wx = x + 1.2 + k * (w - 3.4)
            m.box((wx, y0 + 0.45, 3.4), (wx + 1.0, y0 + 0.5, 4.6), "far_window")
    # a temple prang on the far bank, left of centre
    px, py = -42.0, y0 + 2.0
    for k, (half, z0, z1) in enumerate(((6.0, 2.2, 5.0), (4.2, 5.0, 9.0), (2.8, 9.0, 13.5), (1.5, 13.5, 17.0))):
        m.box((px - half, py, z0), (px + half, py + 2 * half, z1), "far_roof" if k % 2 else "land")
    m.prism_xz([(px - 1.2, 17.0), (px + 1.2, 17.0), (px, 21.5)], py + 0.3, py + 2.7, "far_roof")
    return m


PIER_X = (-30.0, -1.0)
PIER_BACK_Y = -6.0


def pier_mesh() -> Mesh:
    m = Mesh("pier")
    m.box((PIER_X[0], tl.PIER_FRONT_Y, tl.DECK_Z - 0.25), (PIER_X[1], PIER_BACK_Y, tl.DECK_Z), "deck")
    for x in range(int(PIER_X[0]) + 1, int(PIER_X[1]), 4):
        for y in (tl.PIER_FRONT_Y + 0.3, PIER_BACK_Y - 0.3):
            m.box((x - 0.18, y - 0.18, -1.5), (x + 0.18, y + 0.18, tl.DECK_Z - 0.25), "post")
    gx, gy = tl.GAUGE
    m.box((gx - 0.15, gy + 0.08, -1.5), (gx + 0.15, gy + 0.38, 5.2), "post")       # the gauge post, behind the board
    for dx in (-2.4, 2.4):                                                            # the raft's two guide posts
        m.box((tl.RAFT[0] + dx - 0.15, tl.RAFT[1] - 0.15, -1.5), (tl.RAFT[0] + dx + 0.15, tl.RAFT[1] + 0.15, 5.0), "post")
    # the wire the lanterns hang from, along the pier's front eave
    m.box((PIER_X[0] + 0.5, tl.PIER_FRONT_Y - 0.4, tl.DECK_Z + 2.55), (PIER_X[1] - 3.0, tl.PIER_FRONT_Y - 0.3, tl.DECK_Z + 2.62), "post")
    return m


HOUSES = ((-29.0, -22.0), (-20.5, -14.0), (-12.5, -6.5))


def houses_mesh() -> Mesh:
    m = Mesh("houses")
    y0, y1 = tl.PIER_FRONT_Y + 0.6, PIER_BACK_Y - 0.6
    z0 = tl.DECK_Z
    for x0, x1 in HOUSES:
        m.box((x0, y0, z0), (x1, y1, z0 + 3.0), "wall")
        m.prism_xz([(x0 - 0.8, z0 + 3.0), (x1 + 0.8, z0 + 3.0), ((x0 + x1) / 2, z0 + 5.2)], y0 - 0.8, y1 + 0.8, "roof")
        w = x1 - x0
        for k in range(2):
            wx = x0 + 0.9 + k * (w - 2.8)
            m.box((wx, y0 - 0.05, z0 + 1.1), (wx + 1.0, y0, z0 + 2.2), "window")
        m.box((x0 + w / 2 - 0.5, y0 - 0.05, z0), (x0 + w / 2 + 0.5, y0, z0 + 2.0), "roof")   # the door
    return m


def tower_mesh() -> Mesh:
    m = Mesh("tower")
    tx, ty = tl.TOWER
    front = tl.DIAL[1] + 0.08                           # the tower's front face, just behind the dial
    m.box((tx - 6.0, front - 2.0, -1.5), (tx + 6.0, ty + 5.0, tl.DECK_Z), "stone")          # the quay
    th = tl.TOWER_HALF
    top = tl.DIAL[2] + tl.DIAL_R + 1.2
    m.box((tx - th, front, tl.DECK_Z), (tx + th, ty + 3.0, top), "stone")                     # the tower
    m.box((tx - 1.1, front - 0.04, tl.DECK_Z), (tx + 1.1, front, tl.DECK_Z + 3.6), "arch")    # the arch, lit at dusk
    m.box((tx - th - 0.4, front - 0.4, top), (tx + th + 0.4, ty + 3.4, top + 0.6), "gold")    # cornice
    z = top + 0.6
    for k, (half, h) in enumerate(((3.2, 2.2), (2.2, 1.8), (1.2, 1.4))):
        m.box((tx - half, ty - half, z), (tx + half, ty + half, z + h), "stone" if k % 2 else "gold")
        z += h
    m.prism_xz([(tx - 0.7, z), (tx + 0.7, z), (tx, z + 4.0)], ty - 0.7, ty + 0.7, "gold")      # the spire
    return m


def dial_mesh() -> Mesh:
    """The face, its rim and the minute ticks; never re-coloured, so it reads at night."""
    m = Mesh("dial")
    cx, y, cz = tl.DIAL
    m.disc_y(cx, cz, tl.DIAL_R + 0.25, y + 0.03, "rim", sides=40)
    m.disc_y(cx, cz, tl.DIAL_R, y, "dial", sides=40)
    for k in range(60):
        a = k / 60.0 * math.tau
        r0, r1, w = (tl.DIAL_R - 0.42, tl.DIAL_R - 0.06, 0.09) if k % 5 == 0 else (tl.DIAL_R - 0.2, tl.DIAL_R - 0.06, 0.035)
        s, c = math.sin(a), math.cos(a)
        # a thin quad along the radius, clockwise from 12 seen from -y (x = r sin a, z = r cos a)
        quad = [(cx + r * s + d * c, y - 0.02, cz + r * c - d * s) for r, d in ((r0, -w / 2), (r0, w / 2), (r1, w / 2), (r1, -w / 2))]
        if face_normal(quad)[1] > 0:                      # make it face -y, the camera
            quad.reverse()
        m.face(quad, "ink")
    return m


GAUGE_TOP = 4.5


def gauge_board_mesh() -> Mesh:
    """A tide board on its post: metres from the datum, so the pointer reads the tide true to scale (Q6)."""
    m = Mesh("gauge_board")
    gx, gy = tl.GAUGE
    m.box((gx - 0.35, gy, 0.0), (gx + 0.35, gy + 0.06, GAUGE_TOP), "board")
    for k in range(int(GAUGE_TOP * 10) + 1):
        z = k * 0.1
        w = 0.6 if k % 10 == 0 else 0.36 if k % 5 == 0 else 0.18
        hgt = 0.06 if k % 10 == 0 else 0.03
        m.box((gx - 0.3, gy - 0.01, z - hgt / 2 if k else 0.0), (gx - 0.3 + w, gy, z + hgt / 2), "marks")
    return m


def static_meshes() -> List[Mesh]:
    return sky_meshes() + [bank_mesh(), pier_mesh(), houses_mesh(), tower_mesh(), dial_mesh()]


# Static actors the director shows or hides: built as platforms with a visibility mailbox
VISIBLE_STATICS = {"gauge_board": "gauge"}


def toggled_static_meshes() -> List[Mesh]:
    return [gauge_board_mesh()]


# ---------------------------------------------------------------------------------------------
# Moving actors (names are timeline.scene's pose keys)
def bar_mesh(k: int) -> Mesh:
    m = Mesh(f"bar_{k:02d}")
    d = tl.bar_depth(k) * 0.5 * tl.BAR_OVERLAP
    m.box((-tl.BAR_HALF_WIDTH, -d, -tl.BAR_THICK), (tl.BAR_HALF_WIDTH, d, 0.0), f"water_{k:02d}")
    return m


def boat_mesh(name: str, length: float, kind: str) -> Mesh:
    """Bow at the origin (where the rope's eye is), the hull running along +x, waterline at z = 0."""
    m = Mesh(name)
    L = length
    hull = "barge" if kind == "barge" else "hull"
    beam = 1.6 if kind == "barge" else 0.85
    m.prism_xz([(0.9, -0.3), (L - 0.6, -0.3), (L, 0.5), (L, 0.7), (0.0, 0.95)], -beam, beam, hull)
    if kind == "barge":
        m.prism_xz([(L * 0.2, 0.7), (L * 0.85, 0.7), (L * 0.85, 1.6), (L * 0.52, 2.3), (L * 0.2, 1.6)], -beam * 0.9, beam * 0.9, "canopy")
        m.box((L * 0.15, -beam - 0.02, 0.6), (L * 0.9, beam + 0.02, 0.72), "trim")
    else:
        m.box((L * 0.3, -beam * 0.85, 1.55), (L * 0.75, beam * 0.85, 1.7), "canopy")
        for x in (L * 0.32, L * 0.72):
            for y in (-beam * 0.75, beam * 0.75):
                m.box((x - 0.04, y - 0.04, 0.7), (x + 0.04, y + 0.04, 1.55), "canopy")
        m.box((0.6, -beam - 0.02, 0.62), (L - 0.3, beam + 0.02, 0.74), "trim")
    return m


def rope_mesh(name: str) -> Mesh:
    """A unit bar along +y; the director turns it about x and stretches it to the bow."""
    m = Mesh(name)
    m.box((-0.035, 0.0, -0.035), (0.035, 1.0, 0.035), "rope")
    return m


def raft_mesh() -> Mesh:
    m = Mesh("raft")
    for k in range(6):
        x0 = -1.8 + 0.6 * k
        m.box((x0 + 0.02, -1.2, -0.1), (x0 + 0.58, 1.2, 0.15 + 0.01 * (k % 2)), "raft")
    return m


def hyacinth_mesh(i: int) -> Mesh:
    m = Mesh(f"hyacinth_{i}")
    for k in range(4):
        dx, dy = ((k * 0.55) % 1.1) - 0.5, ((k * 0.83) % 1.0) - 0.5
        m.box((dx - 0.35, dy - 0.3, -0.05), (dx + 0.35, dy + 0.3, 0.22 + 0.08 * k), "leaf")
    m.box((-0.12, -0.12, 0.3), (0.12, 0.12, 0.62), "flower")
    return m


def pointer_mesh() -> Mesh:
    """An arrow to the right of the board, its tip at the tide height (z = 0 of the mesh)."""
    m = Mesh("gauge_pointer")
    m.prism_xz([(0.36, 0.0), (0.62, -0.12), (1.1, -0.12), (1.1, 0.12), (0.62, 0.12)], -0.08, 0.04, "pointer")
    return m


def hand_mesh(name: str) -> Mesh:
    m = Mesh(name)
    length = tl.HAND_LEN[name]
    half = {"hand_h": 0.13, "hand_m": 0.085, "hand_s": 0.03}[name]
    color = "second" if name == "hand_s" else "hand"
    m.box((-half, -0.05, -0.45), (half, 0.0, length), color)
    if name == "hand_s":
        m.disc_y(0.0, 0.0, 0.16, -0.055, color, sides=12)
    return m


def disc_mesh(name: str, r: float, color: str) -> Mesh:
    m = Mesh(name)
    m.disc_y(0.0, 0.0, r, 0.0, color, sides=20)
    return m


def cloud_mesh(i: int, half: float) -> Mesh:
    m = Mesh(f"cloud_{i}")
    for k, (dx, w, h) in enumerate(((0.0, half, 2.4), (-half * 0.35, half * 0.5, 4.2), (half * 0.3, half * 0.45, 3.4))):
        m.box((dx - w, -0.4 - 0.3 * k, -h / 2), (dx + w, 0.4 - 0.3 * k, h / 2), "cloud")
    return m


def bird_mesh(i: int) -> Mesh:
    m = Mesh(f"bird_{i}")
    m.beam((-0.65, 0.3), (0.0, 0.0), 0.09, -0.05, 0.05, "bird")
    m.beam((0.0, 0.0), (0.65, 0.3), 0.09, -0.05, 0.05, "bird")
    return m


def lantern_mesh(i: int) -> Mesh:
    """Hangs from its origin, so the sway turns it about the hook."""
    m = Mesh(f"lantern_{i}")
    m.box((-0.22, -0.22, -0.95), (0.22, 0.22, -0.4), "lantern")
    m.box((-0.15, -0.15, -1.02), (0.15, 0.15, -0.95), "lantern_cap")
    m.box((-0.15, -0.15, -0.4), (0.15, 0.15, -0.33), "lantern_cap")
    m.box((-0.015, -0.015, -0.33), (0.015, 0.015, 0.0), "lantern_cap")
    return m


def glint_mesh(i: int) -> Mesh:
    m = Mesh(f"glint_{i}")
    m.box((-1.4, -0.12, 0.0), (1.4, 0.12, 0.02), "glint")
    return m


def all_meshes() -> Dict[str, Mesh]:
    """Every moving actor, in the order the level places them (each group contiguous for the director's loops)."""
    out: Dict[str, Mesh] = {}
    for k in range(tl.N_BARS):
        out[f"bar_{k:02d}"] = bar_mesh(k)
    for name, _x, _y, length, moored, _ph in tl.BOATS:
        out[name] = boat_mesh(name, length, "barge" if name == "boat_2" else "longtail")
    for name in tl.ROPED:
        out["rope_" + name[-1]] = rope_mesh("rope_" + name[-1])
    out["raft"] = raft_mesh()
    for i in range(len(tl.HYACINTH)):
        out[f"hyacinth_{i}"] = hyacinth_mesh(i)
    out["gauge_pointer"] = pointer_mesh()
    for name in ("hand_h", "hand_m", "hand_s"):
        out[name] = hand_mesh(name)
    out["sun"] = disc_mesh("sun", 4.2, "sun")
    out["moon"] = disc_mesh("moon", 2.8, "moon")
    for i, (_z, _p, _ph, half) in enumerate(tl.CLOUDS):
        out[f"cloud_{i}"] = cloud_mesh(i, half)
    for i in range(len(tl.BIRDS)):
        out[f"bird_{i}"] = bird_mesh(i)
    for i in range(len(tl.LANTERNS)):
        out[f"lantern_{i}"] = lantern_mesh(i)
    for i in range(len(tl.GLINTS)):
        out[f"glint_{i}"] = glint_mesh(i)
    return out


# Which visibility group each moving actor belongs to (timeline.VIS); the rest are always shown
def visibility_group(name: str) -> str | None:
    if name in ("sun", "moon"):
        return name
    if name.startswith("bird_"):
        return "birds"
    if name.startswith("boat_") or name.startswith("rope_"):
        return "boats"
    if name == "gauge_pointer":
        return "gauge"
    return VISIBLE_STATICS.get(name)


def mesh_named(name: str) -> Mesh:
    meshes = {m.name: m for m in list(all_meshes().values()) + static_meshes() + toggled_static_meshes()}
    return meshes[name]


def recolour_keys(name: str) -> List[str]:
    """The material keys of an actor's mesh, slot by slot."""
    return mesh_named(name).material_keys()


def recolour_slots() -> Dict[str, List[Tuple[int, str, RGB, RGB, float]]]:
    """Every actor with a re-coloured material: [(slot, kind, day colour, lit colour, argument)]."""
    out: Dict[str, List[Tuple[int, str, RGB, RGB, float]]] = {}
    meshes = list(all_meshes().values()) + static_meshes() + toggled_static_meshes()
    for mesh in meshes:
        slots = []
        for slot, key in enumerate(mesh.material_keys()):
            kind, day, lit, arg = MATERIALS[key]
            if kind != "fixed":
                assert slot < 3, f"{mesh.name}: re-coloured material {key} is slot {slot}; only slots 0 to 2 have a mailbox"
                slots.append((slot, kind, day, lit, arg))
        if slots:
            out[mesh.name] = slots
    return out


tl.PARTS = sys.modules[__name__]      # timeline.scene's colours come from these materials (see timeline._recolour_table)
