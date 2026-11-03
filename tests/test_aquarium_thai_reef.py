"""Checks for the shared reef blockout; runtime acceptance is separate."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_thai_reef'))
sys.path.insert(0, str(ROOT / 'wflevels' / 'aquarium_tanks'))

from mesh import Mesh
from reef.geometry import build_groups, triangles
from reef.scene import ANCHORS, TANK, anchor_map


def test_scene_anchors_are_unique_and_inside_tank():
    assert len(anchor_map()) == len(ANCHORS)
    for x, y, z in anchor_map().values():
        assert -TANK[0] / 2 <= x <= TANK[0] / 2
        assert -TANK[1] / 2 <= y <= TANK[1] / 2
        assert 0 <= z <= TANK[2]


def test_blockout_geometry_is_deterministic_and_within_group_budget():
    first = build_groups(Mesh)
    second = build_groups(Mesh)
    assert len(first) <= 8
    assert sum(map(triangles, first.values())) <= 48000
    for name, mesh in first.items():
        other = second[name]
        assert (mesh.vertices, mesh.faces, mesh.colors) == (
            other.vertices, other.faces, other.colors)
        assert len(mesh.faces) == len(mesh.colors)
