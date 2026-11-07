"""Checks for the shared reef blockout; runtime acceptance is separate."""
import sys
import json
from pathlib import Path
import struct
import subprocess
import math
import re
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_thai_reef'))
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))
sys.path.insert(0, str(ROOT / 'wftools' / 'wf_blender'))

from mesh import Mesh
from reef.geometry import build_groups, triangles
from reef.scene import ANCHORS, TANK, anchor_map
from config import ANIME_HULL_TRIANGLES_MAX, STATIC_GROUPS_MAX, STATIC_TRIANGLES_MAX
import dfrm_chunk


@pytest.mark.parametrize('level', ['aquarium_thai_reef', 'aquarium_thai_reef_anime'])
@pytest.mark.parametrize('model,curves', [('guardcrab', 10), ('hermitcrab', 6),
                                          ('shrimpone', 6), ('shrimptwo', 6),
                                          ('featherstar', 10), ('reef_boxfish', 5),
                                          ('giantclam', 3), ('featherdusters', 4),
                                          ('flowerpotcoral', 12)])
def test_exported_animal_rigs_have_independent_curves(level, model, curves):
    data = (ROOT / 'wflevels' / level / (model + '.iff')).read_bytes()
    offset = 8
    payload = None
    while offset < len(data):
        tag, size = struct.unpack_from('<4sI', data, offset)
        if tag == b'DFRM':
            payload = data[offset + 8:offset + 8 + size]
            break
        offset += 8 + ((size + 3) & ~3)
    assert payload is not None
    rig = dfrm_chunk.decode(payload)
    assert len(rig['curves']) == curves
    bound = {entry[1] // 2 for entry in rig['influences'] if entry[0] == dfrm_chunk.ON_SAMPLE}
    assert bound == set(range(curves))


@pytest.mark.parametrize('level', ['aquarium_thai_reef', 'aquarium_thai_reef_anime'])
def test_leather_coral_has_a_bound_deflation_curve(level):
    data = (ROOT / 'wflevels' / level / 'leathercoral.iff').read_bytes()
    offset = 8
    while offset < len(data):
        tag, size = struct.unpack_from('<4sI', data, offset)
        if tag == b'DFRM':
            rig = dfrm_chunk.decode(data[offset+8:offset+8+size])
            assert len(rig['curves']) == 2
            assert any(entry[0] == dfrm_chunk.ON_SAMPLE and entry[1] == 0 for entry in rig['influences'])
            return
        offset += 8 + ((size+3) & ~3)
    pytest.fail('leather coral has no deformation data')


@pytest.mark.parametrize('model,curves,posed', [
    ('featherdusters', 4, 'scale'), ('flowerpotcoral', 12, 'flex'),
    ('leathercoral', 2, 'scale'),
])
def test_colony_rigs_move_exported_vertices(model, curves, posed):
    import dfrm_ref
    data = (ROOT/'wflevels/aquarium_thai_reef'/(model+'.iff')).read_bytes()
    offset, chunks = 8, {}
    while offset < len(data):
        tag, size = struct.unpack_from('<4sI', data, offset)
        chunks[tag] = data[offset+8:offset+8+size]
        offset += 8 + ((size+3) & ~3)
    vertices = [tuple(v/65536 for v in struct.unpack_from('<iii', chunks[b'VRTX'], i+12))
                for i in range(0, len(chunks[b'VRTX']), 24)]
    faces = [struct.unpack_from('<hhh', chunks[b'FACE'], i) for i in range(0, len(chunks[b'FACE']), 8)]
    rig = dfrm_ref.Rig(dfrm_chunk.decode(chunks[b'DFRM']), vertices, faces)
    neutral = [0.] * (40 + curves*4)
    for i in range(curves):
        neutral[40+4*i] = 1
    posed_block = neutral.copy()
    posed_block[40 if posed == 'scale' else 43] = (.85 if model == 'leathercoral' else .35) if posed == 'scale' else 7
    before = dfrm_ref.evaluate(rig, neutral, 0)['positions']
    after = dfrm_ref.evaluate(rig, posed_block, 0)['positions']
    assert max(math.dist(a, b) for a,b in zip(before, after)) > .02


def test_scene_anchors_are_unique_and_inside_tank():
    assert len(anchor_map()) == len(ANCHORS)
    for x, y, z in anchor_map().values():
        assert -TANK[0] / 2 <= x <= TANK[0] / 2
        assert -TANK[1] / 2 <= y <= TANK[1] / 2
        assert 0 <= z <= TANK[2]


def test_same_anchors_in_both_exported_styles():
    maps = [json.loads((ROOT/'wflevels'/name/'actor-map.json').read_text())
            for name in ('aquarium_thai_reef', 'aquarium_thai_reef_anime')]
    assert maps[0]['anchors'] == maps[1]['anchors']
    assert maps[0]['anchors'] == {k: list(v) for k, v in anchor_map().items()}
    assert sum(maps[0]['hull_triangles'].values()) == 0
    assert 0 < sum(maps[1]['hull_triangles'].values()) <= ANIME_HULL_TRIANGLES_MAX
    assert all(len(m['animated_triangles']) <= 16 for m in maps)


def test_blockout_geometry_is_deterministic_and_within_group_budget():
    first = build_groups(Mesh)
    second = build_groups(Mesh)
    assert len(first) <= STATIC_GROUPS_MAX
    assert sum(map(triangles, first.values())) <= STATIC_TRIANGLES_MAX
    for name, mesh in first.items():
        other = second[name]
        assert (mesh.vertices, mesh.faces, mesh.colors) == (
            other.vertices, other.faces, other.colors)
        assert len(mesh.faces) == len(mesh.colors)


def test_reef_room_pages_fit_aquarium_texture_slots():
    args = dict(line.removeprefix('--').split('=', 1) for line in
                (ROOT / 'android/app/src/aquarium/assets/wf_args.txt').read_text().splitlines())
    for level in ('aquarium_thai_reef', 'aquarium_thai_reef_anime'):
        header = (ROOT / 'wflevels' / level / 'Room0.tga').read_bytes()[:18]
        width, height = struct.unpack_from('<HH', header, 12)
        assert width <= int(args['vram-slot-width'])
        assert height <= int(args['vram-slot-height'])
        assert width < int(args['vram-width'])
        assert height < int(args['vram-height'])


def test_screensaver_native_host_accepts_both_reef_choices_and_texture_pages():
    java = (ROOT / 'android/screensaver/src/main/java/org/worldfoundry/screensaver/TankChoice.java').read_text()
    ids = re.search(r'static final String\[\] IDS = \{(.*?)\};', java, re.S).group(1)
    choices = re.findall(r'"([a-z_]+)"', ids)
    assert choices[-2:] == ['aquarium_thai_reef', 'aquarium_thai_reef_anime']
    host = (ROOT / 'android/screensaver/src/main/cpp/dream_host.cc').read_text()
    maximum = int(re.search(r'if \(level < 0 \|\| level > (\d+)\) return;', host).group(1))
    assert maximum >= len(choices) - 1
    height = int(re.search(r'--vram-height=(\d+)', host).group(1))
    for level in choices[-2:]:
        page_height = struct.unpack_from('<H', (ROOT / 'wflevels' / level / 'Room0.tga').read_bytes(), 14)[0]
        assert height > page_height


def test_exported_reef_triangles_preserve_small_nondegenerate_faces():
    for level in ('aquarium_thai_reef', 'aquarium_thai_reef_anime'):
        small = 0
        for path in (ROOT / 'wflevels' / level).glob('*.iff'):
            data = path.read_bytes()
            if data[:4] != b'MODL':
                continue
            chunks, pos = {}, 8
            while pos + 8 <= len(data):
                tag, size = struct.unpack_from('<4sI', data, pos)
                chunks[tag] = data[pos + 8:pos + 8 + size]
                pos += 8 + ((size + 3) & ~3)
            if b'VRTX' not in chunks or b'FACE' not in chunks:
                continue
            vertices = [struct.unpack_from('<iii', chunks[b'VRTX'], i + 12)
                        for i in range(0, len(chunks[b'VRTX']), 24)]
            for i in range(0, len(chunks[b'FACE']), 8):
                a, b, c = (vertices[index] for index in struct.unpack_from('<hhh', chunks[b'FACE'], i))
                ab, ac = ([b[j] - a[j] for j in range(3)], [c[j] - a[j] for j in range(3)])
                cross = (ab[1]*ac[2] - ab[2]*ac[1], ab[2]*ac[0] - ab[0]*ac[2],
                         ab[0]*ac[1] - ab[1]*ac[0])
                cross_squared = sum(v*v for v in cross)
                assert cross_squared > 0, (path, i // 8)
                if cross_squared < (2 * .00008 * 65536**2)**2:
                    small += 1
        assert small > 0, (level, 'valid small faces were discarded')


@pytest.mark.parametrize('level', ['aquarium_thai_reef', 'aquarium_thai_reef_anime'])
def test_static_reef_exports_prelit_vertex_colors(level):
    for name in ('reef_left', 'reef_right', 'reef_arch', 'reef_hard',
                 'reef_soft', 'reef_sponges', 'reef_life'):
        data = (ROOT / 'wflevels' / level / (name + '.iff')).read_bytes()
        chunks, pos = {}, 8
        while pos + 8 <= len(data):
            tag, size = struct.unpack_from('<4sI', data, pos)
            chunks[tag] = data[pos + 8:pos + 8 + size]
            pos += 8 + ((size + 3) & ~3)
        flags = struct.unpack_from('<I', chunks[b'MATL'])[0]
        colors = {struct.unpack_from('<I', chunks[b'VRTX'], i + 8)[0]
                  for i in range(0, len(chunks[b'VRTX']), 24)}
        assert flags & 0x27 == 0x27, (level, name, flags)
        assert len(colors) > 1 and any(c != 0xffffff for c in colors), (level, name)


def test_reef_render_actors_do_not_create_solid_player_overlap():
    for level in ('aquarium_thai_reef', 'aquarium_thai_reef_anime'):
        text = (ROOT / 'wflevels' / level / (level + '.lev')).read_text()
        blocks = text.split("\t{ 'OBJ'")
        for name, kind in (('BoxfishVisual', 'platform'), ('reef_shell', 'platform'),
                           ('RockColliderLeft', 'statplat'), ('RockColliderRight', 'statplat')):
            block, = (part for part in blocks if f'{{ \'NAME\' "{name}" }}' in part)
            assert f'{{ \'NAME\' "Class Name" }} {{ \'DATA\' "{kind}" }}' in block


def test_worm_mesh_preserves_texture_and_binds_all_fifteen_curves():
    for level in ('aquarium_thai_reef', 'aquarium_thai_reef_anime'):
        data = (ROOT/'wflevels'/level/'wormcrowns.iff').read_bytes()
        assert data[:4] == b'MODL' and struct.unpack_from('<I', data, 4)[0] == len(data) - 8
        chunks, pos = {}, 8
        while pos < len(data):
            tag, size = struct.unpack_from('<4sI', data, pos)
            chunks[tag] = data[pos+8:pos+8+size]
            pos += 8 + ((size + 3) & ~3)
        assert {b'VRTX', b'MATL', b'FACE', b'DFRM'} <= chunks.keys()
        rig = dfrm_chunk.decode(chunks[b'DFRM'])
        assert rig['version'] == 2 and len(rig['curves']) == 15
        assert len(rig['influences']) == len(chunks[b'VRTX']) // 24
        assert {entry[1] // 2 for entry in rig['influences']} == set(range(15))


def test_worm_engine_pose_leaves_other_crowns_unchanged(tmp_path):
    binary = ROOT/'build-docker/jelly-engine/dfrm_strand_test'
    if not binary.exists():
        pytest.skip('requires the built dfrm_strand_test engine harness')
    path = ROOT/'wflevels/aquarium_thai_reef/wormcrowns.iff'
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 12)[0] // 24
    original = [tuple(v / 65536 for v in struct.unpack_from('<iii', data, 28 + i * 24))
                for i in range(count)]
    block = [0.0] * 100
    for i in range(15):
        block[40 + 4*i] = 1
    closed = block.copy()
    closed[40] = .12
    blocks = tmp_path/'blocks.txt'
    blocks.write_text('0 ' + ' '.join(map(str, block)) + '\n1 ' + ' '.join(map(str, closed)) + '\n')
    result = subprocess.run([str(binary), '--eval', str(path), str(blocks)],
                            check=True, text=True, capture_output=True)
    assert [line for line in result.stdout.splitlines() if line.startswith('S ')] == ['S 0', 'S 0']
    vertices = [tuple(map(float, line.split()[2:])) for line in result.stdout.splitlines() if line.startswith('V ')]
    rest, pose = vertices[:count], vertices[count:]
    assert len(pose) == count
    assert max(math.dist(a, b) for a, b in zip(original, rest)) < .0001
    moved = sum(math.dist(a, b) > .001 for a, b in zip(rest, pose))
    assert 0 < moved < count // 5
