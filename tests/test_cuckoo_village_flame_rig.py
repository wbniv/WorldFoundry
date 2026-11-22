"""Option B of the candle flicker plan: the flame rig's chains and bindings, evaluated by the reference DFRM evaluator."""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("wflevels/cuckoo_village", "wftools/wf_blender", "wflevels/aquarium_tanks"):
    sys.path.insert(0, str(ROOT / sub))
import candles as cd  # noqa: E402
import dfrm_chunk as dc  # noqa: E402
import dfrm_ref  # noqa: E402
import flame_rig as fr  # noqa: E402

LOC, ROT, SCALE = (-9.0, 4.0, 0.6), 0.3, 0.9


def tree_mesh():
    feet = [(b[0], b[1], b[2] + cd.STICK_HEIGHT) for b in cd.candle_bases(2, LOC, ROT, SCALE)]
    parts = [cd.flame(f, cd.FLAME_RADIUS, fr.TALL) for f in feet]
    verts, faces = cd.merge(parts)
    return feet, verts, faces


def test_every_vertex_binds_and_the_foot_is_rigid():
    feet, verts, _ = tree_mesh()
    b = fr.bindings(verts, feet, dc.NONE, dc.ON_SAMPLE)
    assert len(b) == 60
    assert sum(k == dc.NONE for k, _, _ in b) == 10                      # one foot a flame
    assert sorted(s for k, s, _ in b if k == dc.ON_SAMPLE) == sorted([2 * n for n in range(10)] * 4 + [2 * n + 1 for n in range(10)])


def test_the_chunk_is_a_v2_with_ten_curves_of_two_bones():
    feet, verts, _ = tree_mesh()
    decoded = dc.decode(fr.payload(verts, feet, dc))
    assert decoded["version"] == 2
    assert [(c["first"], c["count"]) for c in decoded["curves"]] == [(2 * n, 2) for n in range(10)]


def test_a_flex_bias_leans_the_tip_toward_the_draught_and_leaves_the_foot_and_the_other_flames():
    feet, verts, faces = tree_mesh()
    decoded = dc.decode(fr.payload(verts, feet, dc))
    rig = dfrm_ref.Rig(decoded, verts, [])
    block = [0.0] * (40 + 4 * 10)
    for c in range(10):
        block[40 + 4 * c] = 1.0
    rest = dfrm_ref.evaluate(rig, block, 0.0)["positions"]
    block[40 + 4 * 3 + 3] = 6.0                                           # flame 3: flex bias +6 degrees
    leaned = dfrm_ref.evaluate(rig, block, 0.0)["positions"]
    for i, (a, b) in enumerate(zip(rest, leaned)):
        flame, role = divmod(i, 6)
        if flame != 3:
            assert a == b, i
        elif role == 4:                                                   # the foot vertex
            assert max(abs(a[k] - b[k]) for k in range(3)) < 1e-9
        elif role == 5:                                                   # the tip
            assert b[0] - a[0] > 0.012, (a, b)                           # leans toward +X by more than 12 mm at 6 degrees a bone
            assert b[2] < a[2] and abs(b[1] - a[1]) < 1e-6
    block[40 + 4 * 3 + 3] = -4.0
    away = dfrm_ref.evaluate(rig, block, 0.0)["positions"]
    assert away[3 * 6 + 5][0] < rest[3 * 6 + 5][0]


def test_a_scale_below_one_shortens_the_flame_about_its_foot():
    feet, verts, _ = tree_mesh()
    rig = dfrm_ref.Rig(dc.decode(fr.payload(verts, feet, dc)), verts, [])
    block = [0.0] * 80
    for c in range(10):
        block[40 + 4 * c] = 1.0
    rest = dfrm_ref.evaluate(rig, block, 0.0)["positions"]
    block[40 + 4 * 5] = 0.67
    short = dfrm_ref.evaluate(rig, block, 0.0)["positions"]
    tip_rest, tip_short = rest[5 * 6 + 5], short[5 * 6 + 5]
    foot = feet[5]
    assert abs((tip_short[2] - foot[2]) / (tip_rest[2] - foot[2]) - 0.67) < 0.01
