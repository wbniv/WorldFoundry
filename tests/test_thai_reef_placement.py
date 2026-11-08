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


# ── W3: nothing floats, everything attaches ─────────────────────────────────
# Regression guard for the 2026-11-08 audit: zoanthid carpets, cup corals,
# crusts and several actors floated 0.3-1.3 world units (1 unit = 1 m at the
# tank's x10 scale) in front of or above their rock or sand, the hermit crab
# was buried under the sand, and the cleaner shrimp hung in mid-air.
from reef import placement  # noqa: E402
from reef.geometry import build_groups  # noqa: E402
from reef.surface import SAND_Z, rock_gap  # noqa: E402

ROCK_TOL = .05    # flat bases on curved rock; analytic vs exported rock is about 0.01


@pytest.fixture(scope='module')
def static_groups():
    return build_groups(Mesh)


def _life_vertices(groups):
    out = []
    for name, m in groups.items():
        if name.startswith('reef_life'):
            out += [(m.vertices[i], key) for face, key in zip(m.faces, m.colors) for i in face]
    return out


def test_crusts_lie_on_the_rock(static_groups):
    crust = [v for v, key in _life_vertices(static_groups) if key.startswith('crust_')]
    assert crust
    gaps = [rock_gap(v) for v in crust[::7]]
    assert max(gaps) <= .02 and min(gaps) >= -.03


@pytest.mark.parametrize('x,z', [(-3.55, 1.55), (2.0, 1.55), (4.0, 1.70),
                                 (-4.4, 1.18), (-3.6, 1.25), (-1.9, 1.5), (1.75, 1.5), (3.1, 1.22), (4.4, 1.34)])
def test_zoanthid_and_cup_clusters_touch_the_rock(static_groups, x, z):
    near = [v for v, key in _life_vertices(static_groups)
            if key in ('zoanthid_column', 'sponge') and abs(v[0] - x) < .2 and abs(v[2] - z) < .2]
    assert near, (x, z)
    deepest = sorted(near, key=lambda v: -v[1])[:12]      # the vertices furthest into the scene
    assert min(abs(rock_gap(v)) for v in deepest) <= ROCK_TOL


@pytest.mark.parametrize('name', sorted(set(placement.UPRIGHT) - set(placement.HOST_LOCAL_MIN)))
def test_upright_actors_stand_on_their_host(name):
    host = placement.UPRIGHT[name][0]
    base = placement.actor_position(name) if name in placement.ANCHOR_ACTORS.values() else None
    surface, _ = placement.surface_for(name)
    local_min = placement._local_min_z(name)
    position = base or placement.upright_position(name, local_min)
    lowest = position[2] + local_min
    if host == 'sand':
        assert SAND_Z - .07 <= lowest <= SAND_Z + .005, (name, lowest)
    else:
        assert surface[2] - .06 <= lowest <= surface[2] + .005, (name, lowest)
        assert rock_gap(surface) == pytest.approx(0, abs=.02)


def test_clam_is_sunk_and_hermit_is_on_the_sand():
    clam = placement.actor_position('GiantClam')[2] + placement._local_min_z('GiantClam')
    hermit = placement.actor_position('HermitCrab')[2] + placement._local_min_z('HermitCrab')
    assert clam == pytest.approx(SAND_Z - .052, abs=.002)   # valves buried to 40 % of their height
    assert SAND_Z - .04 <= hermit <= SAND_Z     # was 0.31 under the sand


def test_moving_ground_animals_rest_on_the_sand():
    for name in ('Nudibranch', 'Shrimp'):
        lowest = placement.actor_position(name)[2] + placement._local_min_z(name)
        assert SAND_Z - .015 <= lowest <= SAND_Z + .001, (name, lowest)


@pytest.mark.parametrize('level', LEVELS)
def test_built_level_uses_the_resolved_positions(level):
    folder = ROOT / 'wflevels' / level
    anchors = json.loads((folder / 'actor-map.json').read_text())['anchors']
    for anchor, actor in placement.ANCHOR_ACTORS.items():
        assert tuple(anchors[anchor]) == pytest.approx(placement.actor_position(actor), abs=1e-6), anchor
    text = (folder / f'{level}.lev').read_text()
    assert '1.05 751 tk@ .25 + tk-sin .07 *' not in text        # the slug no longer bobs
    assert f'{placement.actor_position("Nudibranch")[2]} INDEXOF_Z_POS' in text


@pytest.mark.parametrize('name', ['PocilloporaHead', 'TableCoral'])
def test_static_host_corals_stand_on_the_rock(name, static_groups):
    centre = placement.coral_centre(name)
    surface, _ = placement.surface_for(name)
    lowest = centre[2] + placement.HOST_LOCAL_MIN[name]
    assert surface[2] - .06 <= lowest <= surface[2] + .005
    hard = static_groups['reef_hard']
    region = [v for v in hard.vertices if abs(v[0] - centre[0]) < .35 and abs(v[1] - centre[1]) < .3
              and v[2] > lowest - .1]      # this coral only, not the boulder below
    assert min(v[2] for v in region) == pytest.approx(lowest, abs=.02)


def test_coral_head_residents_move_with_their_host():
    from reef.scene import ANCHORS
    authored = {a.name: a.position for a in ANCHORS}
    anchors = anchor_map()
    shift = placement.host_shift()
    for name in ('guard_crab', 'humbug_pair'):
        assert anchors[name] == pytest.approx(tuple(authored[name][i] + shift[i] for i in range(3)), abs=1e-5)


# Found by the W5 R0 spike: rotation writes from scripts went into one Euler
# shared by every actor and applied only on a C write, so the sea fan's sway
# (A only) never applied and leaked into the feather star and nudibranch, and
# the guard crab's threat tilt (A only) pitched the boxfish about 58 degrees.
# The engine now applies each axis to its own actor (tests/test_actor_rotation_mailboxes.py);
# the reef still writes whole rotations. Headings are revolutions: the
# nudibranch's old 3.141593 turned it ~51 degrees, not half a turn.
@pytest.mark.parametrize('level', LEVELS)
def test_every_rotation_is_written_whole_and_committed(level):
    import re
    text = (ROOT / 'wflevels' / level / f'{level}.lev').read_text()
    writes = re.findall(r'INDEXOF_ROTATION_([ABC]) (\d+) write-actor-mailbox', text)
    assert writes
    pending = {}
    for axis, actor in writes:
        if axis in 'AB':
            pending.setdefault(actor, set()).add(axis)
        else:
            assert pending.pop(actor, set()) == {'A', 'B'}, f'actor {actor} commits C without A and B'
        others = [a for a in pending if a != actor]
        assert not others, f'rotation for actor(s) {others} left uncommitted before actor {actor}'
    assert not pending
    nudibranch = json.loads((ROOT / 'wflevels' / level / 'actor-map.json').read_text())['actors']['Nudibranch']
    assert f'if .5 else 0 then INDEXOF_ROTATION_C {nudibranch}' in text
    assert '3.141593' not in text
