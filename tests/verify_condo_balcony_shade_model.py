"""Headless read of the assembled condo scene: the 639 balcony shade geometry (§ 7d).

Plan: docs/plans/2026-09-30-condo-balcony-shade.md, Verification 2 (shade on) and 3 (off).

    blender --background wflevels/condo_639_640/condo_639_640.blend \
        --python tests/verify_condo_balcony_shade_model.py -- on|off

Reads the saved scene (never writes it). Every z is reported in level metres relative to
the interior floor, i.e. with § 9b's UNIT_Z lift taken back out. Exits 1 on any FAIL.
"""

import os
import sys

import bpy
from mathutils import Vector

MODE = (sys.argv[sys.argv.index('--') + 1:] or ['on'])[0]
assert MODE in ('on', 'off'), MODE
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'wflevels', 'condo_639_640'))
from site_constants import UNIT_Z  # noqa: E402

RECT = (2.75, -1.95, 5.55, -0.10)          # the recess = the whole recessed patio, x0 y0 x1 y1
EPS = 1e-3
failures = []


def check(name, ok, detail):
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    if not ok:
        failures.append(name)


def wbox(o):
    c = [o.matrix_world @ Vector(v) for v in o.bound_box]
    return (Vector((min(p.x for p in c), min(p.y for p in c), min(p.z for p in c) - UNIT_Z)),
            Vector((max(p.x for p in c), max(p.y for p in c), max(p.z for p in c) - UNIT_Z)))


def shell_faces(pred):
    sh = bpy.data.objects['unit-639']
    mw = sh.matrix_world
    out = []
    for p in sh.data.polygons:
        vs = [mw @ sh.data.vertices[i].co - Vector((0, 0, UNIT_Z)) for i in p.vertices]
        n = (mw.to_3x3() @ p.normal).normalized()
        if pred(vs, n):
            out.append((vs, n, p.area))
    return out


def inside(vs, r=RECT, m=0.0):
    return all(r[0] - m - EPS <= v.x <= r[2] + m + EPS and r[1] - m - EPS <= v.y <= r[3] + m + EPS for v in vs)


# Floor over the frontage: upward faces whose centre lies in the recess rectangle.
floor = shell_faces(lambda vs, n: n.z > 0.9 and inside([sum(vs, Vector()) / len(vs)]) and max(v.z for v in vs) < 0.5)
fz = sorted({round(v.z, 4) for vs, _, _ in floor for v in vs})
farea = sum(a for _, _, a in floor)
want_area = (RECT[2] - RECT[0]) * (RECT[3] - RECT[1])
if MODE == 'on':
    check("floor over the frontage", fz == [-0.07] and abs(farea - want_area) < 1e-3,
          f"z values {fz}, area {farea:.4f} m² of {want_area:.4f} (x {RECT[0]}…{RECT[2]}, y {RECT[1]}…{RECT[3]})")
else:
    # Uncut: the floor is still the survey's big triangles, so look at every upward face
    # that overlaps the rectangle at all.
    over = shell_faces(lambda vs, n: n.z > 0.9 and max(v.z for v in vs) < 0.5
                       and min(v.x for v in vs) < RECT[2] and max(v.x for v in vs) > RECT[0]
                       and min(v.y for v in vs) < RECT[3] and max(v.y for v in vs) > RECT[1])
    oz = sorted({round(v.z, 4) for vs, _, _ in over for v in vs})
    check("floor over the frontage", oz == [0.0], f"z values {oz} over {len(over)} faces overlapping the frontage")

# Risers: vertical faces spanning z −0.07…0 on the rectangle's four sides.
risers = shell_faces(lambda vs, n: abs(n.z) < 0.1 and inside(vs)
                     and abs(min(v.z for v in vs) + 0.07) < EPS and abs(max(v.z for v in vs)) < EPS)
sides = {}
for vs, n, a in risers:
    key = ('x0' if all(abs(v.x - RECT[0]) < EPS for v in vs) else 'x1' if all(abs(v.x - RECT[2]) < EPS for v in vs)
           else 'y0' if all(abs(v.y - RECT[1]) < EPS for v in vs) else 'y1' if all(abs(v.y - RECT[3]) < EPS for v in vs)
           else '?')
    sides[key] = sides.get(key, 0.0) + a
want_sides = {'x0': 1.85 * 0.07, 'x1': 1.85 * 0.07, 'y0': 2.80 * 0.07, 'y1': 2.80 * 0.07} if MODE == 'on' else {}
check("step risers close the recess", sides.keys() == want_sides.keys()
      and all(abs(sides[k] - want_sides[k]) < 1e-4 for k in want_sides),
      f"riser area by side {({k: round(v, 4) for k, v in sides.items()})}")

# The shell's 1.00 m parapet: present off, gone on.
old = shell_faces(lambda vs, n: n.z > 0.9 and all(abs(v.z - 1.0) < EPS for v in vs)
                  and all(2.65 - EPS <= v.x <= 5.85 + EPS and -0.10 - EPS <= v.y <= EPS for v in vs))
check("shell parapet cap at z 1.00", (len(old) > 0) == (MODE == 'off'),
      f"{len(old)} cap faces ({'expected' if MODE == 'off' else 'must be none'})")

objs = {o.name: o for o in bpy.data.objects}
if MODE == 'off':
    check("no grass", '639-patio-grass' not in objs, "absent")
else:
    g = wbox(objs['639-patio-grass']) if '639-patio-grass' in objs else None
    check("artificial grass covers the recess, top z −0.06",
          g is not None and all(abs(a - b) < EPS for a, b in zip((g[0].x, g[0].y, g[0].z, g[1].x, g[1].y, g[1].z),
                                                              (RECT[0], RECT[1], -0.07, RECT[2], RECT[3], -0.06))),
          "missing" if g is None else f"x {g[0].x:.3f}…{g[1].x:.3f} y {g[0].y:.3f}…{g[1].y:.3f} z {g[0].z:.3f}…{g[1].z:.3f} "
          f"→ step from the interior floor {-g[1].z * 100:.0f} cm")
names = ['639-balcony-pony-wall', '639-balcony-north-jamb', 'west-facade-ledge', '639-balcony-shade-cassette',
         '639-balcony-shade-guide-s', '639-balcony-shade-guide-n'] + \
        [f'639-balcony-shade-slat-{i}' for i in range(8)] + ['639-balcony-shade-bar']
present = [n for n in names if n in objs]
if MODE == 'off':
    check("no shade / beam actors", not present and '639-balcony-shade-switch' not in objs, f"present: {present}")
else:
    check("all shade actors present", len(present) == len(names), f"{len(present)}/{len(names)}")
    pony, jamb, ledge = (wbox(objs[n]) for n in names[:3])
    south = wbox(objs['639-bath-N-E-wall'])
    width = jamb[0].x - south[1].x
    check("pony-wall cap z 1.04", abs(pony[1].z - 1.04) < EPS and abs(pony[0].y + 0.10) < EPS and abs(pony[1].y) < EPS,
          f"cap z {pony[1].z:.3f}, y {pony[0].y:.3f}…{pony[1].y:.3f}")
    check("soffit z 2.15", abs(ledge[0].z - 2.15) < EPS and abs(ledge[1].z - 2.70) < EPS and abs(ledge[0].y + 0.35) < EPS,
          f"west-facade-ledge z {ledge[0].z:.3f}…{ledge[1].z:.3f}, y {ledge[0].y:.3f}…{ledge[1].y:.3f}")
    lo = objs['west-facade-ledge']
    lv = [lo.matrix_world @ v.co for v in lo.data.vertices]
    over = [v for v in lv if 2.75 - EPS <= v.x <= 5.43 + EPS]
    check("ledge runs the whole west façade, full depth over the opening",
          ledge[0].x < -4.2 and ledge[1].x > 7.89 and over and abs(min(v.y for v in over) + 0.35) < EPS
          and abs(max(v.y for v in over)) < EPS,
          f"x {ledge[0].x:.2f}…{ledge[1].x:.2f} (640's rounded corner → 639's north wall); over the opening y "
          f"{min(v.y for v in over):.3f}…{max(v.y for v in over):.3f}; {len(lo.data.polygons)} tris")
    # Regression guard (Will, 2026-09-30: the ledge came out ochre over blue walls): every ledge
    # top face must carry the material of the façade wall at its x — the outer-face polygon that
    # spans the ledge's mid-height, or the nearest one along x across a gap in the wall.
    facade = []
    for sh in (objs['unit-639'], objs['unit-640']):
        for vs, n, _a, mat in [(vs, n, a, sh.data.materials[p.material_index])
                               for p in sh.data.polygons
                               for vs, n, a in [([sh.matrix_world @ sh.data.vertices[i].co - Vector((0, 0, UNIT_Z))
                                                  for i in p.vertices], (sh.matrix_world.to_3x3() @ p.normal).normalized(),
                                                 p.area)]]:
            if n.y > 0.9 and all(abs(v.y) < 0.03 for v in vs) and max(v.z for v in vs) > 2.15:
                facade.append((min(v.x for v in vs), max(v.x for v in vs), min(v.z for v in vs), max(v.z for v in vs), mat.name))
    zm = (2.15 + 2.70) / 2
    wrong = []
    for p in lo.data.polygons:
        c = lo.matrix_world @ p.center
        if p.normal.z < 0.9:
            continue
        f = min(facade, key=lambda f: (max(f[0] - c.x, c.x - f[1], 0.0), 0 if f[2] <= zm <= f[3] else 1))
        got = lo.data.materials[p.material_index].name
        if got != f[4]:
            wrong.append((round(c.x, 2), got, f[4]))
    names_used = sorted({m.name for m in lo.data.materials})
    check("ledge colour matches the wall it sits on (no ochre over blue)", not wrong,
          f"ledge materials {names_used}; mismatches {wrong[:4]}{' …' if len(wrong) > 4 else ''}")
    check("clear opening width 2.680 m", abs(width - 2.68) < EPS,
          f"south wall face x {south[1].x:.3f} → north jamb x {jamb[0].x:.3f} = {width:.3f} m")
    slats = [wbox(objs[f'639-balcony-shade-slat-{i}']) for i in range(8)]
    bar = wbox(objs['639-balcony-shade-bar'])
    cass = wbox(objs['639-balcony-shade-cassette'])
    gaps = [slats[i][0].z - slats[i + 1][1].z for i in range(7)] + [slats[7][0].z - bar[1].z]
    ys = [round((s[0].y + s[1].y) / 2, 4) for s in slats]
    # Each slat runs 2 mm past its nominal edges (SLAT_OVERLAP): neighbours overlap by 4 mm, the
    # last one 2 mm into the bar, slat 0 2 mm up into the cassette — no seam can open a pixel crack.
    check("8 slats + bar tile the drop (baked closed), overlapping at every seam",
          abs(slats[0][1].z - (cass[0].z + 0.002)) < 1e-4 and all(abs(g + 0.004) < 1e-4 for g in gaps[:-1])
          and abs(gaps[-1] + 0.002) < 1e-4 and abs(bar[0].z - 1.042) < EPS and len(set(ys)) == 8,
          f"slat 0 top {slats[0][1].z:.3f} (cassette bottom {cass[0].z:.3f}), seam overlaps "
          f"{sorted({round(-g * 1000, 1) for g in gaps})} mm, bar {bar[0].z:.3f}…{bar[1].z:.3f}, slat y centres {ys}")
    sw = objs.get('639-balcony-shade-switch')
    swb = wbox(sw) if sw else None
    check("wall switch on the south jamb beside the opening",
          sw is not None and abs(swb[0].x - 2.75) < EPS and -0.40 < (swb[0].y + swb[1].y) / 2 < -0.10
          and abs((swb[0].z + swb[1].z) / 2 - 1.14) < 0.01 and sw.get('wf_Mass') == 0.0,
          "missing" if sw is None else f"x {swb[0].x:.3f}…{swb[1].x:.3f} y {swb[0].y:.3f}…{swb[1].y:.3f} "
          f"z {swb[0].z:.3f}…{swb[1].z:.3f}, Mass {sw.get('wf_Mass')}")
    mats = [m.name for m in objs['639-balcony-shade-cassette'].data.materials]
    check("cassette carries the solar-strip material", mats == ['shade-cassette', 'shade-solar'], str(mats))

print("RESULT:", "PASS" if not failures else f"FAIL {failures}")
sys.exit(1 if failures else 0)
