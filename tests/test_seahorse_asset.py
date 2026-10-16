"""The seahorse asset as the level ships it: budgets, rings, the tiny-triangle
margin, the DFRM rig and clips, the shared atlas (and the 1024-square permanent
page it needs), the hitching posts against their Forth include, and the minimal
level integration. docs/plans/2026-10-16-saltwater-seahorses.md, Phase 2.

Reads the exported files under wflevels/aquarium_plants/ (rebuild them with
``bash wflevels/aquarium_plants/build.sh``) and compares them with the
generator, wflevels/aquarium_tanks/seahorse.py.
"""
from __future__ import annotations

import json
import math
import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))
sys.path.insert(0, str(ROOT / 'wftools' / 'wf_blender'))
import dfrm_chunk as dc  # noqa: E402
import seahorse as sh  # noqa: E402

HERE = ROOT / 'wflevels' / 'aquarium_plants'
TRIANGLE_BUDGET = 1400
MARGIN = 2.0


def chunks(path: Path) -> dict:
    """The chunks inside a MODL IFF, by tag."""
    data = path.read_bytes()
    assert data[:4] == b'MODL'
    out, o = {}, 8
    while o < len(data):
        tag = data[o:o + 4].decode()
        size = struct.unpack_from('<I', data, o + 4)[0]
        out[tag] = data[o + 8:o + 8 + size]
        o += 8 + size + (-size % 4)
    return out


def mesh(path: Path):
    """(positions, uvs, faces, chunks) from an exported mesh, in model units."""
    c = chunks(path)
    verts = [struct.unpack_from('<iiIiii', c['VRTX'], 24 * i) for i in range(len(c['VRTX']) // 24)]
    positions = [(x / 65536, y / 65536, z / 65536) for _u, _v, _c, x, y, z in verts]
    uvs = [(u / 65536, v / 65536) for u, v, _c, _x, _y, _z in verts]
    faces = [struct.unpack_from('<hhhh', c['FACE'], 8 * i)[:3] for i in range(len(c['FACE']) // 8)]
    return positions, uvs, faces, c


def cross(a, b, c):
    u = [c[i] - a[i] for i in range(3)]
    v = [b[i] - a[i] for i in range(3)]
    x = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    return math.sqrt(sum(t * t for t in x))


@pytest.fixture(scope='module')
def mapping():
    return json.loads((HERE / 'actor-map.json').read_text())


@pytest.mark.parametrize('sex', sh.SEXES)
def test_triangle_and_vertex_budgets(sex):
    body, fins = mesh(HERE / f'seahorse_{sex}_body.iff'), mesh(HERE / f'seahorse_{sex}_fins.iff')
    triangles = len(body[2]) + len(fins[2])
    assert triangles <= TRIANGLE_BUDGET, triangles
    assert len(body[2]) == sum(len(f) - 2 for f in sh.body(sex).faces)
    assert len(fins[2]) == sum(len(f) - 2 for f in sh.fins(sex).faces)
    # About 900 vertices per body (the plan's E1 estimate); fins are small.
    assert 600 <= len(body[0]) <= 1000, len(body[0])
    assert len(fins[0]) <= 200, len(fins[0])


def test_two_actors_per_seahorse_and_four_seahorses(mapping):
    sea = mapping['seahorses']
    assert [a['sex'] for a in sea['actors']] == ['f', 'm', 'f', 'm']          # D3: two pairs
    for a in sea['actors']:
        s = a['seahorse']
        names = sorted(n for n in mapping['indices'] if n.startswith(f'seahorse-{s}-'))
        assert names == [f'seahorse-{s}-body', f'seahorse-{s}-fins']
        assert a['block'] == 1200 + 100 * s
    assert sea['visibility'] == 1160


def test_35_tail_rings_and_11_trunk_rings():
    assert sh.N_TAIL == 35 and sh.N_TRUNK == 11 and len(sh.TRUNK) == sh.N_TRUNK + 1
    for sex in sh.SEXES:
        positions, _uvs, _faces, c = mesh(HERE / f'seahorse_{sex}_body.iff')
        d = dc.decode(c['DFRM'])
        assert len(d['samples']) == 35
        bound = {i[1] for i in d['influences'] if i[0] == dc.ON_SAMPLE}
        assert bound == set(range(35)), 'every tail ring has its own rigid vertices'
        # Every trunk ring boundary (12 for 11 rings) is a loop of eight unbound (static)
        # vertices, found by its band in the atlas strip: V = trunk_v(k).
        positions, uvs, _faces, c = mesh(HERE / f'seahorse_{sex}_body.iff')
        for k in range(sh.N_TRUNK + 1):
            loop = {round(uv[0], 4) for uv, i in zip(uvs, d['influences'])
                    if i[0] == dc.NONE and abs(uv[1] - sh.trunk_v(k)) < 3 / 65536}
            assert len(loop) >= 8, (sex, k, len(loop))


@pytest.mark.parametrize('name', ['seahorse_f_body', 'seahorse_m_body', 'seahorse_f_fins', 'seahorse_m_fins',
                                  'seahorse_whip', 'seahorse_branch'])
def test_tiny_triangle_margin_on_every_face(name):
    positions, _uvs, faces, _c = mesh(HERE / f'{name}.iff')
    worst = min(cross(positions[a], positions[b], positions[c]) for a, b, c in faces)
    assert worst >= MARGIN * sh.MIN_CROSS, (name, worst / sh.MIN_CROSS)


@pytest.mark.parametrize('sex', sh.SEXES)
def test_dfrm_influences_match_vertices_and_bind_pose_is_straight(sex):
    positions, _uvs, _faces, c = mesh(HERE / f'seahorse_{sex}_body.iff')
    d = dc.decode(c['DFRM'])
    assert d['version'] == 1 and len(d['influences']) == len(positions)
    curve = d['curves'][0]
    assert curve['root'] == [0, 0, 0] and curve['d'] == [0, 0, -1] and curve['v'] == [1, 0, 0]
    assert curve['knots'] == [0, 6, 12, 18, 24, 30, 34]
    # Straight bind: joint i sits at -sum(lengths before i) on the root axis, and every
    # ring-bound vertex is that joint plus its offset in the root frame.
    joints = [0.0]
    for smp in d['samples']:
        joints.append(joints[-1] - smp['length'])
    for p, (kind, i, a, b, cc) in zip(positions, d['influences']):
        if kind == dc.ON_SAMPLE:
            rebuilt = (b, cc, joints[i] - a)            # d = -Z, v = +X, s = v x d = +Y
            assert max(abs(p[0] - rebuilt[0]), abs(p[1] - rebuilt[1]), abs(p[2] - rebuilt[2])) < 1e-4
            reach = 1.8 if i == 34 else 1 + sh.OVERLAP                 # the tip ring ends in its pointed cap
            assert -sh.ROOT_SLEEVE * d['samples'][i]['length'] - 1e-4 <= a <= reach * d['samples'][i]['length'] + 1e-4
        elif kind == dc.ON_TRANSFORM:
            assert 0 < a <= 1
    assert len(d['transforms']) == 3                # head, eye_l, eye_r
    head = d['transforms'][0]
    assert head['axis'] == [0, -1, 0] and (head['lo'], head['hi']) == sh.HEAD_LIMITS
    for t in d['transforms'][1:]:
        assert t['axis'] == [0, 0, 1] and (t['lo'], t['hi']) == sh.EYE_LIMITS
    # The eyes sit on the head's pitch axis, so a head pitch leaves them in their sockets.
    assert abs(d['transforms'][1]['pivot'][0] - head['pivot'][0]) < 1e-4
    assert abs(d['transforms'][1]['pivot'][2] - head['pivot'][2]) < 1e-4
    kinds = {k: sum(1 for i in d['influences'] if i[0] == k) for k in (0, 1, 2)}
    assert all(kinds.values()), kinds


@pytest.mark.parametrize('sex', sh.SEXES)
def test_all_eight_clips_with_lengths_and_loop_flags(sex):
    d = dc.decode(chunks(HERE / f'seahorse_{sex}_body.iff')['DFRM'])
    names = sorted(sh.CLIPS)
    assert len(names) == 8 and [c['hash'] for c in d['clips']] == [dc.fnv1a(n) for n in names]
    expected = {'rest_coil': (3.0, True), 'swim': (1.5, True), 'hold_idle': (3.0, True), 'probe': (2.0, False),
                'release': (1.0, False), 'startle': (0.5, False), 'greet_f': (6.0, True), 'greet_m': (6.0, True)}
    assert sh.CLIPS == expected
    total = 0
    for name, c in zip(names, d['clips']):
        seconds, loop = expected[name]
        assert c['fps'] == 30 and c['loop'] == loop
        assert c['frames'] == round(seconds * 30) + (0 if loop else 1), name
        assert sh.CLIP_IDS[name] == names.index(name) + 1
        # Exported frames are the authored ones, through Blender's armature and the
        # exporter's swing-twist decomposition (within int16 centidegree rounding).
        authored = sh.clip_frames(name)
        for k in range(c['frames']):
            row = d['frames'][c['first'] + k]
            assert max(abs(x - y) for x, y in zip(row, authored[k])) < .011, (name, k)
        total += c['frames']
    assert total == len(d['frames']) == 693


def test_clip_frames_move(mapping):
    """Every clip changes over time, and the male rig (whose actions were keyed on the
    female's armature) exported real motion: the Blender 4.4+ action-slot fix."""
    for sex in sh.SEXES:
        d = dc.decode(chunks(HERE / f'seahorse_{sex}_body.iff')['DFRM'])
        for c in d['clips']:
            rows = d['frames'][c['first']:c['first'] + c['frames']]
            spread = max(max(r[j] for r in rows) - min(r[j] for r in rows) for j in range(len(rows[0])))
            assert spread > 2.0, (sex, c)


def test_one_256_atlas_for_both_colourways_in_a_1024_permanent_page():
    from PIL import Image
    atlas = Image.open(HERE / sh.TEXTURE)
    assert atlas.size == (256, 256)
    for sex in sh.SEXES:
        for name in ('body', 'fins'):
            c = chunks(HERE / f'seahorse_{sex}_{name}.iff')
            assert sh.TEXTURE.encode() in c['MATL'], (sex, name)
    # Female yellow, male orange (ours): compare the body strips' mean colour.
    px = atlas.convert('RGB').load()

    def mean(x0):
        cells = [px[x, y] for x in range(x0 + 10, x0 + 86, 3) for y in range(10, 60, 3)]
        return [sum(c[i] for c in cells) / len(cells) for i in range(3)]
    f, m = mean(sh.STRIP_X['f']), mean(sh.STRIP_X['m'])
    assert f[1] > m[1] + 30 and f[0] > 150 and m[0] > 150, (f, m)
    # D5: the aquarium app's permanent page grows to 1024 square, and every desktop
    # and test entry point matches the app.
    flags = (HERE / 'textile.flags').read_text()
    assert 'PERMPAGEX=1024' in flags and 'PERMPAGEY=1024' in flags
    perm = Image.open(HERE / 'Perm.tga')
    assert perm.size[0] <= 1024 and perm.size[1] <= 1024 and perm.size[0] > 512
    args = (ROOT / 'android/app/src/aquarium/assets/wf_args.txt').read_text().split()
    assert '--vram-perm-width=1024' in args and '--vram-perm-height=1024' in args
    for tank in ('aquarium_plants', 'aquarium_lionfish'):
        run = (ROOT / 'wflevels' / tank / 'run.sh').read_text()
        assert '--vram-perm-width=1024 --vram-perm-height=1024' in run, tank
    cmake = (ROOT / 'CMakeLists.txt').read_text()
    assert '--vram-perm-width=1024 --vram-perm-height=1024)' in cmake


def _forth_segments(text):
    rows = re.findall(r'(?:dup \d+ = if drop|drop) ([-\d. ]+?) (?:exit then|;)', text)
    return [[float(x) for x in r.split()] for r in rows]


def test_posts_match_the_forth_include(mapping):
    text = (HERE / 'seahorse_posts.fth').read_text()
    assert text == sh.posts_forth()
    assert f': sh-seg-count {len(sh.post_segments())} ;' in text
    segs = _forth_segments(text)
    assert len(segs) == len(sh.post_segments()) == 3
    assert [s[-1] for s in segs] == [2, 2, 1]                   # whip and trunk vertical, arm horizontal
    by_post = {}
    for seg, g in zip(segs, mapping['seahorses']['grip_segments']):
        assert seg[:3] == pytest.approx(g['start'], abs=1e-4) and seg[3:6] == pytest.approx(g['end'], abs=1e-4)
        assert seg[6:8] == pytest.approx(g['radius'], abs=1e-4)
    k = 0
    for name, base, post_segs in sh.POSTS:
        by_post[name] = segs[k:k + len(post_segs)]
        k += len(post_segs)
    for post in mapping['seahorses']['posts']:
        positions, _uvs, faces, _c = mesh(HERE / post['mesh'])
        base = post['base']
        assert post['base'] == list(dict((n, b) for n, b, _s in sh.POSTS)[post['name']])
        for p in positions:
            w = [p[i] + base[i] for i in range(3)]
            ok = False
            for x0, y0, z0, x1, y1, z1, r0, r1, _mode in by_post[post['name']]:
                a, b = (x0, y0, z0), (x1, y1, z1)
                ab = [b[i] - a[i] for i in range(3)]
                L2 = sum(t * t for t in ab)
                t = sum((w[i] - a[i]) * ab[i] for i in range(3)) / L2
                if -1e-3 <= t <= 1 + 1e-3:
                    foot = [a[i] + ab[i] * t for i in range(3)]
                    dist = math.sqrt(sum((w[i] - foot[i]) ** 2 for i in range(3)))
                    r = r0 + (r1 - r0) * min(1.0, max(0.0, t))
                    if abs(dist - r) < 2e-4 or (dist < 2e-4 and abs(t - 1) < 1e-3):
                        ok = True
                        break
            assert ok, (post['name'], w)


def test_level_places_the_seahorses_in_saltwater_with_dfrm_blocks(mapping):
    lev = (HERE / 'aquarium_plants.lev').read_text()

    def field(obj, name):
        block = lev[lev.index(f'"{obj}"'):]
        block = block[:block.index("{ 'OBJ'")] if "{ 'OBJ'" in block else block
        m = re.search(r"'NAME' \"" + re.escape(name) + r"\" \} \{ '(?:DATA|STR)' ([^}]+)", block)
        return m.group(1).strip() if m else None
    sea = mapping['seahorses']
    for a in sea['actors']:
        for part in ('body', 'fins'):
            obj = f"seahorse-{a['seahorse']}-{part}"
            assert field(obj, 'Visibility Mailbox').startswith('1160'), obj
            assert field(obj, 'Mesh Name') == f'"seahorse_{a["sex"]}_{part}.iff"'
    for post in sea['posts']:
        assert field(post['name'], 'Visibility Mailbox').startswith('1160')
    director = lev[lev.index('tk-director-tick'):]
    for a in sea['actors']:
        assert f"{a['block']} {a['body']} dfrm-pose drop" in director
        assert f"{sh.CLIP_IDS[a['clip']]} {a['block'] + 25} tk!" in director
        assert f" {a['fins']} fin-deform" in director
    assert sorted(a['clip'] for a in sea['actors']) == ['rest_coil', 'rest_coil', 'swim', 'swim']
    # The seahorse blocks stay clear of every other mailbox the tank uses.
    used = set(range(600, 640)) | {747, 748, 1160, 1161} | set(range(800, 968)) | set(range(1000, 1112))
    blocks = {m for a in sea['actors'] for m in range(a['block'], a['block'] + 100)}
    assert not used & blocks and max(blocks) < 1900
