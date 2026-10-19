"""The seahorse tail against the plan's numbers, and the exported rig through the
DFRM reference evaluator (dfrm_ref.py, the engine's maths in Python).

docs/plans/2026-10-16-saltwater-seahorses.md: "The tail: 35 joints, one per
ring" (ring table and joint limits) and Phase 2.
"""
from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))
sys.path.insert(0, str(ROOT / 'wftools' / 'wf_blender'))
import dfrm_chunk as dc  # noqa: E402
import dfrm_ref  # noqa: E402
import seahorse as sh  # noqa: E402

HERE = ROOT / 'wflevels' / 'aquarium_plants'
MM = .01


def test_ring_lengths_widths_and_limits_equal_the_plan():
    L = [x / MM for x in sh.TAIL_LEN]
    W = [x / MM for x in sh.TAIL_WID]
    assert len(L) == 35 and len(W) == 36
    assert L[0] == pytest.approx(3.75) and L[34] == pytest.approx(1.67, abs=.01)    # geometric taper
    assert all(b < a for a, b in zip(L, L[1:]))
    assert sum(L) == pytest.approx(90, abs=.5)                                      # tail 90 mm
    assert W[0] == pytest.approx(9.0) and W[35] == pytest.approx(1.4)               # square, 9.0 -> 1.4 mm
    assert all(b < a for a, b in zip(W, W[1:]))
    base, tip = sh.TAIL_LIMITS[0], sh.TAIL_LIMITS[34]
    assert base == pytest.approx((12, 4, 8, 3))           # ventral, dorsal, lateral, twist (degrees)
    assert tip == pytest.approx((40, 12.5, 28, 8))
    sums = [sum(lim[k] for lim in sh.TAIL_LIMITS) for k in range(4)]
    assert sums[0] == pytest.approx(910) and sums[2] == pytest.approx(630) and sums[1] == pytest.approx(288.75)
    # The same table as the reference and the mockup.
    assert L == pytest.approx(dfrm_ref.LEN) and W == pytest.approx(dfrm_ref.WID)
    assert sh.TAIL_LIMITS == [dfrm_ref.LIM(i) for i in range(35)]


def _rig(sex):
    data = (HERE / f'seahorse_{sex}_body.iff').read_bytes()
    o, chunks = 8, {}
    while o < len(data):
        tag = data[o:o + 4].decode()
        size = struct.unpack_from('<I', data, o + 4)[0]
        chunks[tag] = data[o + 8:o + 8 + size]
        o += 8 + size + (-size % 4)
    verts = [struct.unpack_from('<iiIiii', chunks['VRTX'], 24 * i) for i in range(len(chunks['VRTX']) // 24)]
    rest = [[x / 65536, y / 65536, z / 65536] for _u, _v, _c, x, y, z in verts]
    faces = [struct.unpack_from('<hhhh', chunks['FACE'], 8 * i)[:3] for i in range(len(chunks['FACE']) // 8)]
    return dfrm_ref.Rig(dc.decode(chunks['DFRM']), rest, faces)


@pytest.fixture(scope='module', params=sh.SEXES)
def rig(request):
    return _rig(request.param)


def test_exported_samples_carry_the_table(rig):
    for i, smp in enumerate(rig.c['samples']):
        assert smp['length'] == pytest.approx(sh.TAIL_LEN[i], abs=2e-5)
        assert smp['half_width'] == pytest.approx(sh.TAIL_WID[i] / 2, abs=2e-5)
        assert smp['limits'] == pytest.approx(list(sh.TAIL_LIMITS[i]), abs=.006)
    # Rings are boxes at their width: square at the tip, bevelled on the 20 widest.
    for i in range(35):
        pts = [p for p, inf in zip(rig.rest, rig.c['influences']) if inf[0] == dc.ON_SAMPLE and inf[1] == i]
        offsets = {(round(inf[3], 4), round(inf[4], 4)) for inf in rig.c['influences'] if inf[0] == dc.ON_SAMPLE and inf[1] == i}
        assert max(max(abs(b), abs(c)) for b, c in offsets) == pytest.approx(sh.TAIL_WID[i] / 2, abs=2e-4)
        corners = {o for o in offsets if o != (0.0, 0.0)}
        assert len(corners) == (8 if i < sh.BEVEL_RINGS else 4) * (2 if i == 34 else 1), (i, len(corners))
        assert pts


def _block(clip, start=0.0):
    block = [0.0] * 40
    block[25], block[26] = float(sh.CLIP_IDS[clip]), start
    return block


def test_rest_pose_reproduces_the_mesh(rig):
    r = dfrm_ref.evaluate(rig, [0.0] * 40, 0.0)
    assert r['status'] == 0
    assert max(max(abs(a - b) for a, b in zip(p, q)) for p, q in zip(r['positions'], rig.rest)) < 1e-4


def test_rest_coil_curls_the_tip_ventrally(rig):
    for t in (0.0, .75, 1.5, 2.25):
        r = dfrm_ref.evaluate(rig, _block('rest_coil'), t)
        F, _L, _T = r['angles']
        assert r['status'] == 0
        assert sum(F) > 360, sum(F)                          # more than one full ventral coil
        assert all(f > 0 for f in F[18:]), 'the distal half curls ventrally'
        tip = r['outputs'][3:6]
        assert tip[0] > .05, tip                              # the tip sits on the ventral (+X) side
        lowest = min(j[2] for j in r['joints'])
        assert tip[2] > lowest + .05, (tip, lowest)          # and has curled back up


def test_swim_straightens_and_rudders(rig):
    tips = []
    for k in range(6):
        r = dfrm_ref.evaluate(rig, _block('swim'), k * .25)
        assert r['status'] == 0
        tips.append(r['outputs'][3:6])
        assert sum(r['angles'][0]) < 200                      # much straighter than the rest coil
    assert max(t[1] for t in tips) - min(t[1] for t in tips) > .05   # the rudder sweeps sideways


@pytest.mark.parametrize('clip', sorted(sh.CLIPS))
def test_no_clip_frame_exceeds_a_joint_limit(rig, clip):
    c = rig.c['clips'][sh.CLIP_IDS[clip] - 1]
    samples, transforms = rig.c['samples'], rig.c['transforms']
    worst = 0.0
    for k in range(c['frames']):
        row = rig.c['frames'][c['first'] + k]
        for i, smp in enumerate(samples):
            ven, dor, lat, tw = smp['limits']
            f, l, t = row[3 * i:3 * i + 3]
            assert -dor <= f <= ven and abs(l) <= lat and abs(t) <= tw, (clip, k, i, (f, l, t))
            worst = max(worst, f / ven if f > 0 else -f / dor, abs(l) / lat, abs(t) / tw)
        for j, tr in enumerate(transforms):
            assert tr['lo'] <= row[3 * 35 + j] <= tr['hi']
    assert worst <= sh.LIMIT_USE + 1e-3
    # The evaluator agrees: no frame reports a clamped joint (status 3).
    for k in sorted({0, c['frames'] // 2, c['frames'] - 1}):
        r = dfrm_ref.evaluate(rig, _block(clip), k / 30.0)
        assert r['status'] == 0, (clip, k)


def test_hold_idle_moves_only_the_rings_a_wrap_leaves_free(rig):
    c = rig.c['clips'][sh.CLIP_IDS['hold_idle'] - 1]
    rows = rig.c['frames'][c['first']:c['first'] + c['frames']]
    for i in range(35):
        moved = max(abs(r[3 * i + q]) for r in rows for q in range(3))
        if i >= sh.HOLD_FREE:
            assert moved == 0, i
    assert max(abs(r[0]) for r in rows) > 1.0


@pytest.mark.parametrize('clip', sorted(sh.CLIPS))
def test_posed_faces_keep_the_area_margin(rig, clip):
    """Rigid rings never squash: every face keeps 2x the engine's tiny-triangle limit
    in the posed mesh too (the head's blended neck faces included)."""
    c = rig.c['clips'][sh.CLIP_IDS[clip] - 1]
    for k in (0, c['frames'] // 2):
        r = dfrm_ref.evaluate(rig, _block(clip), k / 30.0)
        pos = r['positions']
        for a, b, cc in rig.faces:
            u = [pos[cc][i] - pos[a][i] for i in range(3)]
            v = [pos[b][i] - pos[a][i] for i in range(3)]
            x = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            assert math.sqrt(sum(t * t for t in x)) >= 2 * sh.MIN_CROSS, (clip, k)
