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
  - Each segment has a heading angle extracted from the descriptor type field:
      heading = (type & 0xFF) / 256 * 2π  radians, CCW from +X axis (East = 0°)
  - Cross-sections are placed perpendicular to the heading direction at each
    segment boundary; positions accumulate via heading × SEG_LEN per segment.
  - Z = (h_value - H_ZERO) × GAME_UNIT  (H_ZERO=5 puts goal at Z=0)
  - h_left/h_right give wall/edge heights at PATH_HALF from path centre;
    when h_edge > h_center the edge rises above the floor (walled trough);
    when h_edge < h_center the edge drops below (crowned/open-sided section).
  - Face normals always have n_z = PATH_HALF × SEG_LEN > 0 regardless of heading.
  - Faces are doubled (top + back) so the physics mesh is two-sided.

Type field lower-byte heading table for Practice:
  Segs  0-8:  type=0x000D, lower=13 → 18.28° (ENE, mostly +X with slight +Y)
  Segs  9-10: type=0x0320, lower=32 → 45.00° (NE diagonal, walled downhill)
  Segs 11-12: type=0x0D20 (goal sentinel, h_center=5=H_ZERO, replaced by flat platform)

Calibration constants (tune via Blender MCP + MAME screenshot comparison):
  GAME_UNIT  — metres per game height unit above H_ZERO
  SEG_LEN    — metres per path segment (forward step per segment)
  PATH_HALF  — half-width of path in metres (centre to each edge vertex)
"""

import json
import math
import os
import sys

import bpy

# --------------------------------------------------------------------------
# Calibration (adjust and re-run via MCP to iterate)
# --------------------------------------------------------------------------

H_ZERO     = 5      # goal-zone h_center; subtracted so goal sits at Z=0
GAME_UNIT  = 0.05   # metres per game unit above H_ZERO
            # Calibrated against arcade screenshots: Beginner trough walls at
            # ΔH≈46–89 units over PATH_HALF=4.0 m give 30–48° slope angles,
            # matching the ~30–50° trough profiles visible in MAME captures.
            # (0.1 m/unit gave 49–66°, visually too steep in the WF perspective view.)
SEG_LEN    = 2.5    # metres per path segment
PATH_HALF  = 4.0    # metres from path centre to each edge vertex


def scale(h):
    """Convert a game-unit height value to WF world metres (Z)."""
    return (h - H_ZERO) * GAME_UNIT


def heading_angle(type_u16: int) -> float:
    """Path heading angle in radians from descriptor type field.

    Lower byte of the 16-bit descriptor type = heading in 256ths of a
    full revolution, CCW from the +X axis (East = 0°, North = 64/256 = 90°).
    Confirmed via cross-level type-field analysis: type groups with the same
    lower byte run in the same direction; lower-byte changes mark path turns.
    """
    lower = type_u16 & 0xFF
    return (lower / 256.0) * (2.0 * math.pi)


def load_levels() -> dict:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'levels.json')
    with open(json_path) as f:
        return json.load(f)


def build_path_mesh(level_name: str, levels: dict) -> bpy.types.Object:
    """
    Build a trough mesh for one level and link it into the current scene.

    Cross-section at each segment joint (3 vertices, perpendicular to heading):
      left   (centre - PATH_HALF × right_perp,  scale(h_left))
      center (centre,                             scale(h_center))
      right  (centre + PATH_HALF × right_perp,  scale(h_right))

    where right_perp = (sin θ, −cos θ, 0) for heading angle θ.

    Segment positions accumulate: pos_{i+1} = pos_i + SEG_LEN × (cos θ_i, sin θ_i).

    Face normals always have n_z = PATH_HALF × SEG_LEN > 0, so the ball can
    rest on all faces regardless of heading direction.

    Goal segments (h_center ≤ H_ZERO) are replaced by a flat goal platform at Z=0.
    """
    segs = [s for s in levels[level_name]['segments'] if 'error' not in s]
    if not segs:
        print(f'[rom_to_blender] No valid segments for {level_name}')
        return None

    # Classify segments: leading h_center≤H_ZERO = start platform,
    # trailing h_center≤H_ZERO = goal platform, everything else = path.
    # A simple is_goal filter would misclassify Beginner seg 0 (h_center=3)
    # as a goal because it sits below H_ZERO — but it is the start, not the end.
    first_path = 0
    while first_path < len(segs) and segs[first_path]['h_center'] <= H_ZERO:
        first_path += 1
    last_path = len(segs)
    while last_path > first_path and segs[last_path - 1]['h_center'] <= H_ZERO:
        last_path -= 1

    start_segs = segs[:first_path]
    path_segs  = segs[first_path:last_path]
    goal_segs  = segs[last_path:]

    verts = []
    faces = []

    def add_cross_section(px, py, seg, theta):
        """Add 3 vertices for one cross-section perpendicular to heading theta."""
        rx = math.sin(theta)   # right direction: 90° CW from forward
        ry = -math.cos(theta)
        base = len(verts)
        verts.append((px - PATH_HALF * rx, py - PATH_HALF * ry, scale(seg['h_left'])))
        verts.append((px,                  py,                   scale(seg['h_center'])))
        verts.append((px + PATH_HALF * rx, py + PATH_HALF * ry, scale(seg['h_right'])))
        return base

    def add_flat_platform(near_x, near_y, far_x, far_y, theta, z_val):
        rx = math.sin(theta)
        ry = -math.cos(theta)
        gw = PATH_HALF * 1.5
        b = len(verts)
        verts.extend([
            (near_x - gw * rx, near_y - gw * ry, z_val),
            (near_x + gw * rx, near_y + gw * ry, z_val),
            (far_x  + gw * rx, far_y  + gw * ry, z_val),
            (far_x  - gw * rx, far_y  - gw * ry, z_val),
        ])
        faces.append((b, b + 1, b + 2, b + 3))
        faces.append((b + 3, b + 2, b + 1, b))

    # Accumulate segment positions and build cross-sections
    pos_x, pos_y = 0.0, 0.0

    # Start platform (leading low-h_center segments)
    for s in start_segs:
        theta  = heading_angle(s['type'])
        end_x  = pos_x + math.cos(theta) * SEG_LEN
        end_y  = pos_y + math.sin(theta) * SEG_LEN
        add_flat_platform(pos_x, pos_y, end_x, end_y, theta, scale(s['h_center']))
        pos_x, pos_y = end_x, end_y
    if start_segs:
        print(f'[rom_to_blender] {level_name}: {len(start_segs)} start seg(s) → '
              f'flat start platform, path begins at ({pos_x:.2f},{pos_y:.2f})')

    if not path_segs:
        print(f'[rom_to_blender] No path segments for {level_name}')
        return None

    first_theta = heading_angle(path_segs[0]['type'])
    prev_base   = add_cross_section(pos_x, pos_y, path_segs[0], first_theta)

    for i, seg in enumerate(path_segs[1:], 1):
        # Advance position along previous segment's heading
        prev_theta = heading_angle(path_segs[i - 1]['type'])
        pos_x += math.cos(prev_theta) * SEG_LEN
        pos_y += math.sin(prev_theta) * SEG_LEN

        theta     = heading_angle(seg['type'])
        curr_base = add_cross_section(pos_x, pos_y, seg, theta)

        p0, p1, p2 = prev_base,     prev_base + 1, prev_base + 2
        c0, c1, c2 = curr_base,     curr_base + 1, curr_base + 2

        # Top faces (n_z = PATH_HALF × SEG_LEN > 0 always)
        faces.append((p0, p1, c1, c0))   # left half-floor
        faces.append((p1, p2, c2, c1))   # right half-floor
        # Back faces (double-sided: physics collision from both sides)
        faces.append((c0, c1, p1, p0))
        faces.append((c1, c2, p2, p1))

        prev_base = curr_base

    # Final cross-section at end of last segment
    last_theta = heading_angle(path_segs[-1]['type'])
    pos_x += math.cos(last_theta) * SEG_LEN
    pos_y += math.sin(last_theta) * SEG_LEN
    curr_base = add_cross_section(pos_x, pos_y, path_segs[-1], last_theta)
    p0, p1, p2 = prev_base,     prev_base + 1, prev_base + 2
    c0, c1, c2 = curr_base,     curr_base + 1, curr_base + 2
    faces.append((p0, p1, c1, c0)); faces.append((p1, p2, c2, c1))
    faces.append((c0, c1, p1, p0)); faces.append((c1, c2, p2, p1))

    # Flat goal platform at Z=0, one segment forward from path end
    if goal_segs:
        final_theta = heading_angle(path_segs[-1]['type'])
        goal_x = pos_x + math.cos(final_theta) * SEG_LEN
        goal_y = pos_y + math.sin(final_theta) * SEG_LEN
        add_flat_platform(pos_x, pos_y, goal_x, goal_y, final_theta, 0.0)
        pos_x, pos_y = goal_x, goal_y

        print(f'[rom_to_blender] {level_name}: {len(goal_segs)} goal seg(s) → '
              f'flat goal platform at ({pos_x:.2f},{pos_y:.2f})')

    print(f'[rom_to_blender] {level_name}: path end pos=({pos_x:.2f},{pos_y:.2f}), '
          f'{len(segs)} segs → {len(verts)} verts, {len(faces)} faces')

    mesh = bpy.data.meshes.new(f'{level_name}_path')
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(f'{level_name}_path', mesh)
    bpy.context.scene.collection.objects.link(obj)

    # Flat-shaded material — no texture atlas entry needed; avoids invisible mesh
    mat = bpy.data.materials.new(f'{level_name}_path_mat')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.4, 0.6, 0.3, 1.0)
    mesh.materials.append(mat)

    # Attach statplat OAD so the WF exporter emits it as a static platform
    repo = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    statplat_oad = os.path.join(
        repo, 'wftools', 'wf_oad', 'tests', 'fixtures', 'statplat.oad')
    obj['wf_schema_path']    = statplat_oad
    obj['wf_Mesh Name']      = f'{level_name.lower()}_path.iff'
    obj['wf_Model Type']     = 'Mesh'
    obj['wf_Mobility']       = 'Anchored'
    obj['wf_Surface Friction'] = 0.5
    obj['wf_Mass']           = 0.0

    return obj


# --------------------------------------------------------------------------
# Entry point — run for one level (default: Practice)
# --------------------------------------------------------------------------

if __name__ == '__main__':
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    level_name = argv[0] if argv else 'Practice'

    levels = load_levels()
    if level_name not in levels:
        print(f'[rom_to_blender] Unknown level "{level_name}". '
              f'Available: {list(levels.keys())}')
    else:
        build_path_mesh(level_name, levels)
