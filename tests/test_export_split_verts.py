"""Every unpack of the exporter's split_verts tuples must match their arity.

Regression guard: 09e9ff33 (vertex-light bake) added a packed colour to each
split_verts entry, but the DFRM path still unpacked three values, so any
Blender-rigged DFRM mesh failed to export (`ValueError: too many values to
unpack`) and the plants level could not build from 2026-11-03 to 2026-11-08.
"""
import ast
from pathlib import Path

EXPORTER = Path(__file__).resolve().parents[1] / 'wftools' / 'wf_blender' / 'export_level.py'


def _appended_arity(tree):
    sizes = {len(node.args[0].elts) for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == 'append' and isinstance(node.func.value, ast.Name)
             and node.func.value.id == 'split_verts' and isinstance(node.args[0], ast.Tuple)}
    assert len(sizes) == 1, sizes
    return sizes.pop()


def test_split_verts_unpacks_match_the_tuple_arity():
    tree = ast.parse(EXPORTER.read_text())
    arity = _appended_arity(tree)
    loops = [node for node in ast.walk(tree) if isinstance(node, (ast.For, ast.comprehension))
             and isinstance(node.iter, ast.Name) and node.iter.id == 'split_verts'
             and isinstance(node.target, ast.Tuple)]
    assert loops, 'expected at least one tuple unpack of split_verts'
    for loop in loops:
        assert len(loop.target.elts) == arity, ast.unparse(loop.target)
