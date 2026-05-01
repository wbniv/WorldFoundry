#!/usr/bin/env python3
"""
rom_to_blender.py — Convert decoded MM ROM level data to Blender path geometry.

Execute inside a live Blender session via MCP:
    exec(open('/path/to/rom_to_blender.py').read())

Or headless:
    blender --background --python rom_to_blender.py -- Practice

Reads wflevels/marble-madness/levels.json (produced by decode_levels.py) and
creates a trough-shaped path mesh for the specified level in the current scene.

Coordinate mapping:
  - Path runs along +Y axis (same as mm_practice ramp direction)
  - Z = (h_value - H_ZERO) × GAME_UNIT  (H_ZERO=5 puts goal at Z=0)
  - X = ±PATH_HALF  (left/right edges of the trough)
  - Faces are doubled (top + back) so the physics mesh is two-sided

Calibration constants (tune via Blender MCP + MAME screenshot comparison):
  GAME_UNIT  — metres per game height unit above H_ZERO
  SEG_LEN    — metres per path segment
  PATH_HALF  — half-width of path in metres (centre to edge)
"""

import json
import os
import sys

import bpy

# --------------------------------------------------------------------------
# Calibration (adjust and re-run via MCP to iterate)
# --------------------------------------------------------------------------

H_ZERO     = 5      # goal-zone h_center; subtracted so goal sits at Z=0
GAME_UNIT  = 0.5    # metres per game unit above H_ZERO
SEG_LEN    = 2.5    # metres per path segment along +Y
PATH_HALF  = 4.0    # metres from path centre to each edge


def scale(h):
    """Convert a game-unit height value to WF world metres (Z)."""
    return (h - H_ZERO) * GAME_UNIT


def load_levels() -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'levels.json')
    with open(json_path) as f:
        return json.load(f)


def build_path_mesh(level_name: str, levels: dict) -> bpy.types.Object:
    """
    Build a trough mesh for one level and link it into the current scene.

    Cross-section at each segment joint (3 vertices):
      left   (-PATH_HALF, y, scale(h_left))
      center (0,          y, scale(h_center))
      right  (+PATH_HALF, y, scale(h_right))

    When h_edge > h_center: edge rises above floor → wall/lip geometry.
    When h_edge < h_center: edge drops below floor → open/fall-off side.

    Adjacent cross-sections are connected with quads (×2 for double-sided).
    """
    segs = [s for s in levels[level_name]['segments'] if 'error' not in s]
    if not segs:
        print(f'[rom_to_blender] No valid segments for {level_name}')
        return None

    verts = []
    faces = []

    def add_cross_section(seg, y):
        base = len(verts)
        verts.append((-PATH_HALF, y, scale(seg['h_left'])))    # base+0: left
        verts.append((0.0,        y, scale(seg['h_center'])))  # base+1: centre
        verts.append(( PATH_HALF, y, scale(seg['h_right'])))   # base+2: right
        return base

    prev = add_cross_section(segs[0], 0.0)

    for i, seg in enumerate(segs[1:], 1):
        curr = add_cross_section(seg, i * SEG_LEN)
        p0, p1, p2 = prev, prev + 1, prev + 2
        c0, c1, c2 = curr, curr + 1, curr + 2

        # Top faces (normal roughly upward)
        faces.append((p0, p1, c1, c0))   # left half-floor
        faces.append((p1, p2, c2, c1))   # right half-floor

        # Back faces (double-sided: marble can hit from below too)
        faces.append((c0, c1, p1, p0))
        faces.append((c1, c2, p2, p1))

        prev = curr

    mesh = bpy.data.meshes.new(f'{level_name}_path')
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(f'{level_name}_path', mesh)
    bpy.context.scene.collection.objects.link(obj)

    # Attach statplat OAD so the WF exporter knows this is a static platform
    repo = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    statplat_oad = os.path.join(
        repo, 'wftools', 'wf_oad', 'tests', 'fixtures', 'statplat.oad')
    obj['wf_schema_path'] = statplat_oad
    obj['wf_Mesh Name']       = f'{level_name.lower()}_path.iff'
    obj['wf_Model Type']      = 'Mesh'
    obj['wf_Mobility']        = 'Anchored'
    obj['wf_Surface Friction'] = 0.5
    obj['wf_Mass']            = 0.0

    print(
        f'[rom_to_blender] {level_name}: {len(segs)} segs → '
        f'{len(verts)} verts, {len(faces)} faces'
    )
    return obj


# --------------------------------------------------------------------------
# Entry point — run for one level (default: Practice)
# --------------------------------------------------------------------------

if __name__ == '__main__' or 'bpy' in dir():
    argv = sys.argv
    # Blender passes script args after '--'
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    level_name = argv[0] if argv else 'Practice'

    levels = load_levels()
    if level_name not in levels:
        print(f'[rom_to_blender] Unknown level "{level_name}". '
              f'Available: {list(levels.keys())}')
    else:
        build_path_mesh(level_name, levels)
