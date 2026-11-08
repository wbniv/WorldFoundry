"""Christmas tree worm placement, model and rig (plan 2026-11-08 W1).

Regression guard for Will's 2026-11-08 report: the worms floated 9-14 cm in
front of the Porites boulder on a rigid grid, all pointing straight up, and
retracted toward a point below the coral instead of into their tubes.
"""
import json
import math
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_thai_reef'))
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))
sys.path.insert(0, str(ROOT / 'wftools' / 'wf_blender'))

from mesh import Mesh  # noqa: E402
from config import WORM_TRIANGLES_MAX  # noqa: E402
from reef import life  # noqa: E402
from reef.atlas import WORM_CELL, WORM_MORPHS  # noqa: E402
from reef.geometry import triangles  # noqa: E402
from reef.scene import (PORITES_LOBES, WORM_COUNT, anchor_map, inside_lobe,  # noqa: E402
                        porites_relief, worm_mouths, worm_origin)
import dfrm_chunk  # noqa: E402

LEVELS = ('aquarium_thai_reef', 'aquarium_thai_reef_anime')


def _surface_error(lobe, p):
    """World-space distance of p from the relief-displaced lobe surface."""
    c, r = PORITES_LOBES[lobe]
    q = [(p[i] - c[i]) / r[i] for i in range(3)]
    k = math.sqrt(sum(x * x for x in q))
    u = [x / k for x in q]
    return abs(porites_relief(u) - k) * min(r)


def test_every_worm_mouth_sits_on_the_porites_surface():
    worms = worm_mouths()
    assert len(worms) == WORM_COUNT == 15
    for w in worms:
        assert _surface_error(w['lobe'], w['surface']) < 1e-6
        assert math.dist(w['mouth'], w['surface']) == pytest.approx(.005, abs=1e-6)
        assert not inside_lobe(1 - w['lobe'], w['surface'])


def test_worms_face_the_camera_out_of_the_surface():
    for w in worm_mouths():
        n, a = w['normal'], w['axis']
        assert n[1] <= -.35 and n[2] >= .3 and abs(n[0]) <= .55
        assert sum(x * y for x, y in zip(n, a)) >= .8      # within 37 degrees
        assert a[2] > n[2]                                  # leans toward the light


def test_worm_mouths_are_spaced_and_not_a_grid():
    worms = worm_mouths()
    pairs = [math.dist(a['surface'], b['surface']) for i, a in enumerate(worms) for b in worms[i + 1:]]
    assert min(pairs) >= .14
    # The old grid repeated three z rows and five x columns exactly.
    assert len({round(w['mouth'][2], 2) for w in worms}) > 10


def test_worm_morphs_alternate_between_neighbours():
    worms = worm_mouths()
    assert {w['morph'] for w in worms} == set(range(len(WORM_MORPHS)))
    for w in worms:
        near = sorted(worms, key=lambda o: math.dist(w['surface'], o['surface']))[1:4]
        assert all(o['morph'] != w['morph'] for o in near)


def test_worm_crowns_stay_out_of_the_coral_and_in_budget():
    mesh = Mesh('wormcrowns')
    origin = worm_origin()
    life.worm_crowns(mesh, origin)
    assert triangles(mesh) <= WORM_TRIANGLES_MAX
    for v in mesh.vertices:
        p = [v[i] + origin[i] for i in range(3)]
        for lobe, (c, r) in enumerate(PORITES_LOBES):
            q = [(p[i] - c[i]) / r[i] for i in range(3)]
            k = math.sqrt(sum(x * x for x in q))
            depth = (porites_relief([x / k for x in q]) - k) * min(r)
            assert depth < .01, f'crown vertex {p} is {depth:.3f} inside lobe {lobe}'


def test_worm_crown_uvs_stay_inside_their_morph_row():
    mesh = Mesh('wormcrowns')
    life.worm_crowns(mesh, worm_origin())
    assert len(mesh.face_uvs) == len(mesh.faces)
    u0, v0 = (WORM_CELL % 4) * 256, (WORM_CELL // 4) * 256
    rows = set()
    for uvs in mesh.face_uvs.values():
        xs = [u * 1024 for u, _ in uvs]
        ys = [v * 1024 for _, v in uvs]
        assert u0 <= min(xs) and max(xs) <= u0 + 256
        row = int((min(ys) - v0) // 32)
        assert 0 <= row < 8 and max(ys) <= v0 + 32 * (row + 1)
        rows.add(row)
    assert rows == set(range(8))


def test_worm_anchor_is_the_actor_origin():
    assert anchor_map()['tree_worms'] == worm_origin()


@pytest.mark.parametrize('level', LEVELS)
def test_built_level_places_and_drives_worms_from_the_mouths(level):
    folder = ROOT / 'wflevels' / level
    actor_map = json.loads((folder / 'actor-map.json').read_text())
    assert tuple(actor_map['anchors']['tree_worms']) == worm_origin()
    text = (folder / f'{level}.lev').read_text()
    for i, w in enumerate(worm_mouths()):
        x, y, z = w['mouth']
        assert f'{x:.6f} {y:.6f} {z:.6f} {i} reef-worm' in text


@pytest.mark.parametrize('level', LEVELS)
def test_worm_curves_are_rooted_at_the_tube_mouths(level):
    data = (ROOT / 'wflevels' / level / 'wormcrowns.iff').read_bytes()
    pos, rig = 8, None
    while pos < len(data):
        tag, size = struct.unpack_from('<4sI', data, pos)
        if tag == b'DFRM':
            rig = dfrm_chunk.decode(data[pos + 8:pos + 8 + size])
        pos += 8 + ((size + 3) & ~3)
    assert rig is not None and len(rig['curves']) == 15
    origin = worm_origin()
    for curve, w in zip(rig['curves'], worm_mouths()):
        local = [w['mouth'][i] - origin[i] for i in range(3)]
        assert math.dist(curve['root'], local) < 1e-3
        assert sum(a * b for a, b in zip(curve['d'], w['axis'])) > .999
