"""Classic Snowgoons: the shipped acre has tiled, visible geometry and usable colliders."""
import importlib.util
import hashlib
from pathlib import Path
import re
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "wflevels/snowgoons-blender"
sys.path.insert(0, str(ROOT / "scripts"))
from audit_face_hand import chunks, cross, find_models, sub
from add_ambient_light import _split_objects


def parts(data):
    return {tag: data[a:b] for tag, _, a, b in chunks(data, 8, len(data))}


def mesh(data):
    p = parts(data)
    verts = [struct.unpack_from("<iiIiii", p[b"VRTX"], i) for i in range(0, len(p[b"VRTX"]), 24)]
    faces = [struct.unpack_from("<hhhh", p[b"FACE"], i) for i in range(0, len(p[b"FACE"]), 8)]
    return verts, faces


def objects():
    text = (HERE / "snowgoons.lev").read_text()
    lines = text.splitlines(keepends=True)
    return {re.search(r"'NAME'\s+\"([^\"]+)\"", block)[1]: block
            for a, b in _split_objects(text) for block in ["".join(lines[a:b])]}


def field(block, name):
    m = re.search(r'"' + re.escape(name) + r'"\s*\}\s*\{\s*\x27DATA\x27\s+([^}\n]+)', block)
    assert m, name
    return tuple(float(v) for v in re.findall(r'(-?\d+\.\d+)\(1\.15\.16\)', m[1]))


def bounds(block):
    p, b = field(block, "Position"), field(block, "Global Bounding Box")
    return tuple(p[i % 3] + v for i, v in enumerate(b))


def test_lawn_area_winding_and_tiling():
    verts, faces = mesh((HERE / "yard01.iff").read_bytes())
    assert len(verts) < 1000, "share hedge seam vertices to retain the planned mesh budget"
    assert all(0 < uv < 65536 for v in verts for uv in v[:2])
    area = 0
    for a, b, c, mat in faces:
        points = [tuple(v/65536 for v in verts[i][3:]) for i in [a, b, c]]
        normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
        assert sum(v*v for v in normal) > 0
        if len({p[2] for p in points}) == 1:
            assert normal[2] > 0, (mat, points)
        if mat == 5:
            assert all(p[2] == 0 for p in points)
            area += normal[2] / 2
            # Every triangle spans one inset tile; none crosses a tile boundary.
            for axis in [0,1]:
                uv = {verts[i][axis] for i in [a,b,c]}
                assert len(uv) == 2 and max(uv)-min(uv) > .9*65536
        if mat == 2:
            centre = tuple(sum(p[j] for p in points)/3 for j in range(3))
            assert normal[0]*-centre[0] + normal[1]*-centre[1] > 0
    print(f"Measured yard lawn: {area:.2f} m²")
    assert 4046.86 <= area <= 4128
    assert area == 4080
    assert parts((HERE / "yard01.iff").read_bytes())[b"MATL"] == parts((HERE / "quadpatch01.iff").read_bytes())[b"MATL"]


def test_layout_matches_geometry_and_does_not_hide_floor_from_spawn():
    obj = objects()
    yard = obj["statplat_2"]
    assert re.search(r'"Class Name"\s*\}\s*\{\s*\x27DATA\x27\s+"platform"', yard)
    assert field(yard, "Orientation") == (0,0,0)
    assert field(yard, "Position") == (0,-12,-0.62)
    verts, _ = mesh((HERE / "yard01.iff").read_bytes())
    actual = tuple(op(v[j]/65536 for v in verts) for op in [min,max] for j in [3,4,5])
    authored = field(yard, "Global Bounding Box")
    assert authored == pytest.approx(actual, abs=1/65536)
    assert '"yard01.iff"' in yard
    spawn = field(obj["player_33"], "Position")
    assert spawn[2] == pytest.approx(-0.60)
    assert -30 < spawn[0] < 30 and -46 < spawn[1] < 22
    slab = bounds(obj["statplat_15"])
    assert slab == pytest.approx((-32,-48,-1.62,32,24,-0.62))
    spawnbox = bounds(obj["player_33"])
    for name in ["statplat_15", "statplat_19", "statplat_20", "statplat_21", "statplat_22"]:
        assert field(obj[name], "Orientation") == (0,0,0)
        box = bounds(obj[name])
        local = field(obj[name], "Global Bounding Box")
        assert all(abs(local[i]+local[i+3]) < 1/65536 for i in range(3)), name
        assert not all(box[i] <= spawnbox[i] and box[i+3] >= spawnbox[i+3] for i in range(3)), name
    assert bounds(obj["statplat_19"])[4] == -46
    assert bounds(obj["statplat_20"])[0] == 30
    assert bounds(obj["statplat_21"])[3] == -30
    assert bounds(obj["statplat_22"])[1] == 22
    assert field(obj["camera_8"], "FoggingStartDistance") == (40,)
    assert field(obj["camera_8"], "FoggingCompleteDistance") == (100,)


@pytest.mark.parametrize("name", ["snowgoons.iff", "snowgoons-standalone.iff", "snowgoons-cd.iff"])
def test_shipped_bundle_contains_exact_generated_yard(name):
    expected = (HERE / "yard01.iff").read_bytes()
    models = [m for _, m in find_models((ROOT / "wflevels" / name).read_bytes())]
    assert models.count(expected) == 1, f"{name}: yard missing or stale; run task snowgoons-level"
    # Also measure the shipping model, rather than accepting only the loose source.
    verts, faces = mesh(next(m for m in models if m == expected))
    area = sum(cross(sub(verts[b][3:], verts[a][3:]), sub(verts[c][3:], verts[a][3:]))[2]
               for a,b,c,mat in faces if mat == 5) / (2*65536**2)
    print(f"{name}: {area:.2f} m²")
    assert area == 4080


def test_generator_is_deterministic_and_patcher_idempotent():
    spec = importlib.util.spec_from_file_location("snowgoons_yard", HERE / "make_yard.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert generator.mesh_bytes() == (HERE / "yard01.iff").read_bytes()
    text = (HERE / "snowgoons.lev").read_text()
    assert generator.patch_level(text) == text
    scaffold = (HERE / "snowgoons-blender.lev").read_text()
    assert '"quadpatch01.iff"' in scaffold and '"yard01.iff"' not in scaffold


def test_classic_atlas_is_isolated_from_shared_scaffold():
    includes = (HERE / "snowgoons.iff.txt").read_text()
    assert '[ "classic-atlas/Room0.tga" ]' in includes
    assert '[ "classic-atlas/Room1.ruv" ]' in includes
    # These shared authoring outputs must still match the retained Blender build.
    for name, digest in {
        "Room1.tga": "330e5c00403b76f1b2de34fa79f22ac1b69f694134f29d58ad4d77688f152706",
        "Room1.ruv": "f87b5cdd6a23be963434981069162fff3f81b73419f7f8039b8077d00bb91063",
    }.items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest


def test_one_original_snowgoon_is_shipped_and_placed_on_the_lawn():
    spec = importlib.util.spec_from_file_location("snowgoon_asset", HERE / "make_snowgoon.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    expected, box = generator.model()
    assert expected == (HERE / "snowgoon.iff").read_bytes()
    assert box[2] == 0 and 2 < box[5] < 2.5
    assert parts(expected)[b"MATL"] == parts((HERE / "snowman01.iff").read_bytes())[b"MATL"]
    obj = objects()["Snowgoon"]
    assert field(obj, "Position") == (5,-3,-0.60)
    assert field(obj, "Global Bounding Box") == box
    assert '"enemy"' in obj and '"Physics"' in obj and '"snowgoon.iff"' in obj
    text = (HERE / "snowgoons.lev").read_text()
    assert text.count('"Snowgoon"') == 1
    assert generator.patch_level(text,box) == text
    for name in ["snowgoons.iff", "snowgoons-standalone.iff", "snowgoons-cd.iff"]:
        assert [m for _,m in find_models((ROOT / "wflevels" / name).read_bytes())].count(expected) == 1
