"""The baseline's Utah teapot ladder: the vendored reference data and its tessellation.

Pure Python, no Blender. The level build and the device checks are covered by
wflevels/baseline/verify.py; this file guards the data and the geometry rules.
"""
import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "wflevels/baseline"
SPEC = importlib.util.spec_from_file_location("baseline_teapot", BASELINE / "teapot.py")
teapot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(teapot)
CONFIG = json.loads((BASELINE / "baseline.json").read_text())["teapots"]
LADDER = CONFIG["segments"]


def _area(vertices, triangle):
    return teapot._area(vertices, triangle)


def test_vendored_data_is_the_recorded_file():
    recorded = re.search(r"SHA-256 \| `([0-9a-f]{64})`", (BASELINE / "data/README.md").read_text()).group(1)
    assert hashlib.sha256((BASELINE / "data/teapotCGA.bpt").read_bytes()).hexdigest() == recorded


def test_reference_data_is_the_32_patch_blinn_teapot():
    patches = teapot.load_patches()
    assert len(patches) == 32 and all(len(p) == 16 for p in patches)
    points = [q for p in patches for q in p]
    for axis, low, high in ((0, -3.0, 3.525), (1, -2.0, 2.0), (2, 0.0, 3.15)):
        values = [q[axis] for q in points]
        assert (min(values), max(values)) == (low, high)


def test_loader_rejects_a_truncated_file(tmp_path):
    broken = tmp_path / "broken.bpt"
    broken.write_text("\n".join((BASELINE / "data/teapotCGA.bpt").read_text().splitlines()[:-3]))
    with pytest.raises(ValueError):
        teapot.load_patches(broken)


@pytest.mark.parametrize("n", LADDER)
def test_face_count_is_the_formula(n):
    vertices, triangles = teapot.tessellate(n)
    assert len(triangles) == teapot.face_count(n)
    if n > 1:
        assert len(triangles) == 64 * n * n - 8 * n  # 52 at n = 1: four collinear faces dropped too


@pytest.mark.parametrize("n", LADDER)
def test_no_degenerate_faces_and_no_unused_vertices(n):
    vertices, triangles = teapot.tessellate(n)
    assert all(len(set(t)) == 3 and _area(vertices, t) > 1e-12 for t in triangles)
    assert len(vertices) == len({i for t in triangles for i in t})


def _consistent(triangles):
    """True when no directed edge is used twice: neighbouring faces agree on orientation."""
    directed = Counter()
    for a, b, c in triangles:
        for edge in ((a, b), (b, c), (c, a)):
            directed[edge] += 1
    return max(directed.values()) == 1


def _shells(triangles):
    """Group triangles into vertex-connected shells."""
    parent = {}

    def find(i):
        parent.setdefault(i, i)
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for t in triangles:
        parent[find(t[0])] = find(t[1])
        parent[find(t[1])] = find(t[2])
    shells = {}
    for t in triangles:
        shells.setdefault(find(t[0]), []).append(t)
    return list(shells.values())


def _outward(vertices, shell):
    """True when the shell's face normals point away from its centre (positive volume)."""
    used = {i for t in shell for i in t}
    centre = tuple(sum(vertices[i][k] for i in used) / len(used) for k in range(3))
    volume = 0.0
    for t in shell:
        a, b, c = (vertices[i] for i in t)
        volume += teapot._dot(teapot._cross(teapot._sub(b, a), teapot._sub(c, a)), teapot._sub(a, centre))
    return volume > 0


@pytest.mark.parametrize("n", [m for m in LADDER if m > 1])
def test_winding_is_consistent_and_outward_on_every_shell(n):
    vertices, triangles = teapot.tessellate(n)
    assert _consistent(triangles)
    shells = _shells(triangles)
    assert len(shells) >= 2  # at least the lid apart from the body
    assert all(_outward(vertices, shell) for shell in shells)


def test_the_winding_checks_do_fail_on_broken_winding():
    vertices, triangles = teapot.tessellate(4)
    one_flipped = [t[::-1] if i == 0 else t for i, t in enumerate(triangles)]
    assert not _consistent(one_flipped)
    body = max(_shells(triangles), key=len)
    assert not _outward(vertices, [t[::-1] for t in body])
    # Reversing the winding of every face must also be caught.
    assert not all(_outward(vertices, shell) for shell in _shells([t[::-1] for t in triangles]))


def test_geometry_is_deterministic_and_scales():
    assert teapot.tessellate(4) == teapot.tessellate(4)
    vertices, _ = teapot.tessellate(3, 0.4)
    assert min(v[2] for v in vertices) == 0 and max(v[2] for v in vertices) == pytest.approx(3.15 * 0.4)


def test_rejects_bad_levels():
    for bad in (0, -1, 1.5):
        with pytest.raises(ValueError):
            teapot.tessellate(bad)


def test_ladder_config_rises_and_is_spaced_for_labels():
    counts = [teapot.face_count(n) for n in LADDER]
    assert counts == sorted(set(counts)) and len(counts) == 8
    assert CONFIG["spacing"] >= 3.0  # a 1.8-wide floor label plus margin fits under each teapot
    assert teapot.label_texts() == ["%d faces" % c for c in counts]
    assert len(LADDER) <= 8  # the label atlas holds 4 x 2 cells; vertices must fit signed 16-bit indices
    assert max(len(teapot.tessellate(n)[0]) for n in LADDER) < 32768
