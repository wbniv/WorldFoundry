"""Creature skins for the Thai reef (plan 2026-11-08 W2).

Regression guard for Will's 2026-11-08 report that several actors had no
textures: small creatures borrowed sponge, sand and rock tiles at a world
projection of about 87 texels per unit, or sampled one flat texel, so they
rendered as flat colour. Each now samples its own atlas cell densely.
"""
import math
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_thai_reef'))
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))

from mesh import Mesh  # noqa: E402
from reef import corals, invertebrates, life, uvmap  # noqa: E402
from reef.atlas import CELL, write_atlas  # noqa: E402
from reef.geometry import build_groups  # noqa: E402

CREATURES = {  # actor: (builder, the cells its skin keys must sample)
    'GuardCrab': (invertebrates.guard_crab, {10}),
    'Shrimp': (invertebrates.banded_shrimp, {11}),
    'HermitCrab': (invertebrates.hermit_crab, {13}),
    'Nudibranch': (life._nudibranch, {12}),
    'FeatherDusters': (life.feather_dusters, {9}),
}


def _mesh(builder):
    m = Mesh('m')
    builder(m, (0, 0, 0))
    return m


def _area(points):
    a = [0.0, 0.0, 0.0]
    for i in range(1, len(points) - 1):
        u = [points[i][k] - points[0][k] for k in range(3)]
        w = [points[i + 1][k] - points[0][k] for k in range(3)]
        c = (u[1]*w[2]-u[2]*w[1], u[2]*w[0]-u[0]*w[2], u[0]*w[1]-u[1]*w[0])
        a = [a[k] + c[k] for k in range(3)]
    return .5 * math.sqrt(sum(x * x for x in a))


def _flat_share(m):
    """Share of face area whose exported UVs span under 3 texels."""
    total = flat = 0.0
    for face, uv in zip(m.faces, uvmap.face_uvs(m)):
        a = _area([m.vertices[i] for i in face])
        total += a
        extent = max(max(u for u, _ in uv) - min(u for u, _ in uv),
                     max(v for _, v in uv) - min(v for _, v in uv)) * 1024
        flat += a if extent < 3 else 0
    return flat / total


@pytest.mark.parametrize('name', sorted(CREATURES))
def test_creatures_no_longer_render_flat(name):
    builder, _ = CREATURES[name]
    assert _flat_share(_mesh(builder)) <= .20


@pytest.mark.parametrize('name', sorted(CREATURES))
def test_creature_skins_sample_their_own_cell(name):
    builder, cells = CREATURES[name]
    m = _mesh(builder)
    used = set()
    for key, uv in zip(m.colors, uvmap.face_uvs(m)):
        if key in uvmap.SKINS:
            for u, v in uv:
                used.add(int(v * 1024) // CELL * 4 + int(u * 1024) // CELL)
    assert used == cells
    assert not {'sponge', 'sand', 'rock', 'clam', 'fish'} & set(m.colors)


def test_zoanthid_carpets_show_texture():
    groups = build_groups(Mesh)
    for name in ('reef_life', 'reef_life_1'):
        assert _flat_share(groups[name]) <= .20, name


@pytest.mark.parametrize('style', ['realistic', 'anime'])
def test_creature_cells_are_painted(style, tmp_path):
    path = tmp_path / 'atlas.tga'
    write_atlas(path, style=style)
    data = path.read_bytes()[18:]
    for cell in range(9, 15):
        x0, y0 = (cell % 4) * CELL, (cell // 4) * CELL
        texels = {data[3 * ((y0 + y) * 1024 + x0 + x):3 * ((y0 + y) * 1024 + x0 + x) + 3]
                  for y in range(0, CELL, 16) for x in range(0, CELL, 16)}
        # Anime cells are posterised to a few tones; realistic ones vary more.
        assert bytes((128, 128, 128)) not in texels and len(texels) > (1 if style == "anime" else 4), cell


def test_every_reef_key_has_a_uv_rule():
    meshes = list(build_groups(Mesh).values())
    meshes += [_mesh(b) for b, _ in CREATURES.values()]
    for builder in (life._sea_fan, life._feather_star, life._clam, corals.flowerpot, corals.leather_coral):
        meshes.append(_mesh(builder))
    for m in meshes:
        assert len(uvmap.face_uvs(m)) == len(m.faces)
