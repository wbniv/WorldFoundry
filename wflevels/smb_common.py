"""Shared SMB level-build machinery — builders + (later) parameterized script generators —
imported by every wflevels/smb_*/blender_create_*.py so the levels cannot drift.

Phase P1a: the 13 helpers that were byte-identical across W1-1 and W1-2, lifted verbatim.
The importing level script calls `init(scene, OAD_DIR)` once after creating its scene, then
uses these via `from smb_common import ...`. See
docs/plans/2026-06-02-smb-common-extraction-and-mesh-sharing.md.
"""
import bpy
import os
import math
import bmesh as _bmesh

T = 1.5  # NES tile size in WF metres (identical across all SMB levels)

# Cube face winding (shared by the box-mesh builders, e.g. _room_bounds_mesh).
_box_faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

# Set by the importing level script via init() before any builder is called.
scene = None      # bpy.context.scene
OAD_DIR = None    # path to the .oad schema dir


def init(scene_, oad_dir):
    """Bind the active Blender scene + OAD schema dir for the shared builders."""
    global scene, OAD_DIR
    scene = scene_
    OAD_DIR = oad_dir


def make_mat(name, rgb):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    mat.diffuse_color = (*rgb, 1.0)
    return mat


def attach_schema(obj, oad_name):
    obj['wf_schema_path'] = os.path.join(OAD_DIR, oad_name + '.oad')


# ── 4. Configure infrastructure actors ───────────────────────────────────────


def find_by_class(cn):
    for obj in bpy.data.objects:
        if get_class(obj) == cn:
            return obj
    return None


def get_class(obj):
    schema = obj.get('wf_schema_path', '')
    return os.path.splitext(os.path.basename(schema))[0] if schema else ''


def add_box(mesh_name, x0, y0, z0, x1, y1, z1, mat):
    """Add a box mesh [x0..x1]×[y0..y1]×[z0..z1], return the object."""
    cx, cy, cz = (x0+x1)/2, (y0+y1)/2, (z0+z1)/2
    sx, sy, sz = x1-x0, y1-y0, z1-z0
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
    obj = bpy.context.object
    obj.name      = mesh_name
    obj.data.name = mesh_name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    return obj


def add_statplat(mesh_name, x0, y0, z0, x1, y1, z1, mat):
    obj = add_box(mesh_name, x0, y0, z0, x1, y1, z1, mat)
    attach_schema(obj, 'statplat')
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Model Type'] = 'Mesh'
    return obj


def _add_textured_box(mesh_name, x0, y0, z0, x1, y1, z1, tex_path):
    """Box with a UV-mapped texture on all 6 faces (full [0,1]² per face).

    The front face (-Y, camera-side) gets vertex order chosen so the
    texture appears right-side-up when the camera is at Y≈-30 looking +Y.
    UV V=0 = top of the PIL image; V=1 = bottom — opposite of the Blender
    default but matching the WF/textile-rs VRAM convention where row 0 is
    the image top.
    """
    import bmesh

    mat = bpy.data.materials.new(name=f'{mesh_name}_mat')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf  = nodes['Principled BSDF']
    tex   = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(tex_path)
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')

    v = [
        bm.verts.new((x0, y0, z0)),  # 0
        bm.verts.new((x1, y0, z0)),  # 1
        bm.verts.new((x1, y1, z0)),  # 2
        bm.verts.new((x0, y1, z0)),  # 3
        bm.verts.new((x0, y0, z1)),  # 4
        bm.verts.new((x1, y0, z1)),  # 5
        bm.verts.new((x1, y1, z1)),  # 6
        bm.verts.new((x0, y1, z1)),  # 7
    ]

    # UV corners per face: (bottom-left, bottom-right, top-right, top-left)
    # viewed from outside, with V=0=image-top / V=1=image-bottom (WF VRAM convention).
    # Each face lists (vert, uv) pairs.
    face_defs = [
        # front -Y (camera-side): CCW from -Y; bl→br→tr→tl as seen by camera
        ([v[0], v[1], v[5], v[4]], [(0,1),(1,1),(1,0),(0,0)]),
        # back +Y: CCW from +Y
        ([v[2], v[3], v[7], v[6]], [(0,1),(1,1),(1,0),(0,0)]),
        # top +Z: CCW from +Z (camera looks along +Y, so "near" = -Y edge)
        ([v[4], v[5], v[6], v[7]], [(0,1),(1,1),(1,0),(0,0)]),
        # bottom -Z: CCW from -Z
        ([v[3], v[2], v[1], v[0]], [(0,1),(1,1),(1,0),(0,0)]),
        # left -X: CCW from -X
        ([v[3], v[0], v[4], v[7]], [(0,1),(1,1),(1,0),(0,0)]),
        # right +X: CCW from +X
        ([v[1], v[2], v[6], v[5]], [(0,1),(1,1),(1,0),(0,0)]),
    ]

    for verts, uvs in face_defs:
        f = bm.faces.new(verts)
        f.material_index = 0
        for loop, uv_coord in zip(f.loops, uvs):
            loop[uv].uv = uv_coord

    mesh = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)

    obj = bpy.data.objects.new(mesh_name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    return obj


def _make_qblock_tga(out_path, scale=2):
    """Generate a 32×32 NES-style ?-block texture and save as TGA.

    Each "NES pixel" is `scale`×`scale` output pixels so the block reads
    clearly on a 1.5 m face.  Output is always a power-of-2 square
    (32×32 at scale=2) per textile-rs bitmap.rs:507.

    Palette:
      0 = dark border  (101,  47,   0)
      1 = orange fill  (196, 106,   0)
      2 = bright edge  (252, 180,  36)  — lighter row inside top/bottom border
      3 = white mark   (252, 248, 200)  — ? glyph interior

    The ? glyph uses the classic NES double-arch style:
      rows 3-7  arch (two bumps, right arm closes into stem)
      row  8    stem
      row  9    gap
      rows 10-12 dot
    """
    from PIL import Image
    PALETTE = [
        (101,  47,   0),   # 0 dark border
        (196, 106,   0),   # 1 orange fill
        (252, 180,  36),   # 2 bright edge
        (252, 248, 200),   # 3 white mark
    ]
    # 16×16 NES pixel map (palette indices)
    MAP = [
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0],
        [0,2,1,1,1,1,1,1,1,1,1,1,1,2,0,0],
        [0,2,1,1,0,0,0,1,0,0,0,1,1,2,0,0],  # arch top
        [0,2,1,1,0,3,3,0,3,3,0,1,1,2,0,0],  # arch interior
        [0,2,1,1,0,0,0,0,3,3,0,1,1,2,0,0],  # left arm closes
        [0,2,1,1,1,1,1,0,3,3,0,1,1,2,0,0],  # right arm
        [0,2,1,1,1,1,0,0,0,1,1,1,1,2,0,0],  # arch closes into stem
        [0,2,1,1,1,1,0,3,0,1,1,1,1,2,0,0],  # stem
        [0,2,1,1,1,1,1,1,1,1,1,1,1,2,0,0],  # gap
        [0,2,1,1,1,1,0,0,0,1,1,1,1,2,0,0],  # dot top
        [0,2,1,1,1,1,0,3,0,1,1,1,1,2,0,0],  # dot centre
        [0,2,1,1,1,1,0,0,0,1,1,1,1,2,0,0],  # dot bottom
        [0,2,1,1,1,1,1,1,1,1,1,1,1,2,0,0],
        [0,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    ]
    size = 16 * scale
    img = Image.new('RGB', (size, size))
    px  = img.load()
    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            color = PALETTE[c]
            for dy in range(scale):
                for dx in range(scale):
                    px[x * scale + dx, y * scale + dy] = color
    img.save(out_path)
    return out_path


def _make_brick_tga(out_path, scale=2):
    """Generate a 32×32 NES-style breakable-brick texture and save as TGA.

    Classic SMB running-bond brick: four 4-pixel courses of orange bricks,
    each capped by a dark horizontal mortar line and a bright lit top edge,
    with the vertical mortar seams offset half a brick between alternating
    courses. Same palette family + scale convention as `_make_qblock_tga`
    so the brick reads next to the ? blocks. Output is power-of-2 square
    (32×32 at scale=2).

    Palette:
      0 = dark mortar  (101,  47,   0)  — shared with the ?-block border
      1 = orange fill  (196, 106,   0)
      2 = bright edge  (252, 180,  36)  — lit row just under each mortar line
    """
    from PIL import Image
    PALETTE = [
        (101,  47,   0),   # 0 dark mortar
        (196, 106,   0),   # 1 orange fill
        (252, 180,  36),   # 2 bright edge
    ]
    # 16×16 NES pixel map. Courses A (seams at cols 0,8) and B (seams at 4,12)
    # alternate to make the offset running-bond brickwork.
    A = [
        [0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0],   # horizontal mortar
        [0,2,2,2,2,2,2,2, 0,2,2,2,2,2,2,2],   # lit top edge + vertical seams
        [0,1,1,1,1,1,1,1, 0,1,1,1,1,1,1,1],
        [0,1,1,1,1,1,1,1, 0,1,1,1,1,1,1,1],
    ]
    B = [
        [0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0],   # horizontal mortar
        [2,2,2,2,0,2,2,2, 2,2,2,2,0,2,2,2],   # seams offset half a brick
        [1,1,1,1,0,1,1,1, 1,1,1,1,0,1,1,1],
        [1,1,1,1,0,1,1,1, 1,1,1,1,0,1,1,1],
    ]
    MAP = A + B + A + B
    size = 16 * scale
    img = Image.new('RGB', (size, size))
    px  = img.load()
    for y, row in enumerate(MAP):
        for x, c in enumerate(row):
            color = PALETTE[c]
            for dy in range(scale):
                for dx in range(scale):
                    px[x * scale + dx, y * scale + dy] = color
    img.save(out_path)
    return out_path


def _make_grid_tile_tga(out_path, width=256, height=32, cells_x=64, cells_y=8,
                         line_px=1):
    """Pre-tiled grid texture (one image, no mesh subdivision needed):
    `cells_x` × `cells_y` grid lines baked in, light brown fill with darker
    brown lines along the top + left edge of each cell.

    Dims forced to {16,32,64,128,256,512,1024}^2 (textile-rs power-of-2
    constraint at bitmap.rs:507). The whole texture is mapped UV [0, 1]
    across the ground top face — works around the renderer's atlas-UV
    uint8 overflow that breaks GL_REPEAT for mesh UVs above ~5
    (docs/investigations/2026-05-18-texture-uv-uint8-overflow.md).

    Defaults: 256×32 texture, 64 grid cells in X, 8 in Y. Mapped across the
    73.5 m ground that gives one grid line every 73.5/64 ≈ 1.15 m — close
    enough to a 1-metre grid for visual position estimation."""
    from PIL import Image
    BG = (143, 97, 38)
    FG = (102, 66, 23)
    cell_w = width // cells_x
    cell_h = height // cells_y
    img = Image.new('RGB', (width, height), BG)
    px = img.load()
    for y in range(height):
        for x in range(width):
            if (x % cell_w) < line_px or (y % cell_h) < line_px:
                px[x, y] = FG
    img.save(out_path)
    return out_path


def build_textured_ground_mesh(name, x0, y0, z0, x1, y1, z1, tex_path):
    """Box ground with a UV-mapped grid texture on the top face only. Sides
    and bottom use a solid-brown material (material 0). Top face uses the
    grid material (material 1). UV is 1:1 with world XY so the tile repeats
    every 1 m."""
    import bmesh

    mat_brown = make_mat('smb_ground_side', (0.56, 0.38, 0.15))

    mat_grid = bpy.data.materials.new('smb_ground_grid')
    mat_grid.use_nodes = True
    bsdf = mat_grid.node_tree.nodes['Principled BSDF']
    tex_node = mat_grid.node_tree.nodes.new('ShaderNodeTexImage')
    tex_node.image = bpy.data.images.load(tex_path)
    mat_grid.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    v000 = bm.verts.new((x0, y0, z0))
    v100 = bm.verts.new((x1, y0, z0))
    v110 = bm.verts.new((x1, y1, z0))
    v010 = bm.verts.new((x0, y1, z0))
    v001 = bm.verts.new((x0, y0, z1))
    v101 = bm.verts.new((x1, y0, z1))
    v111 = bm.verts.new((x1, y1, z1))
    v011 = bm.verts.new((x0, y1, z1))

    # Top face (+Z, grid material) — CCW from above.
    top = bm.faces.new((v001, v101, v111, v011))
    top.material_index = 1
    # Other faces (solid brown).
    sides = [
        bm.faces.new((v000, v010, v110, v100)),  # -Z bottom (CCW from below)
        bm.faces.new((v000, v100, v101, v001)),  # -Y front
        bm.faces.new((v110, v010, v011, v111)),  # +Y back
        bm.faces.new((v010, v000, v001, v011)),  # -X left
        bm.faces.new((v100, v110, v111, v101)),  # +X right
    ]
    for f in sides:
        f.material_index = 0

    bm.faces.ensure_lookup_table()
    # UV in [0, 1] — pre-tiled grid baked into the texture itself. Keeps
    # UV in the safe range to dodge the atlas-UV uint8 overflow that
    # breaks GL_REPEAT for mesh UVs above ~5
    # (docs/investigations/2026-05-18-texture-uv-uint8-overflow.md).
    top_uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
    for loop, uv_xy in zip(top.loops, top_uvs):
        loop[uv].uv = uv_xy

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat_brown)
    mesh.materials.append(mat_grid)
    return mesh


# ── 5. Ground platform ────────────────────────────────────────────────────────
# Texture-mapped 1-unit grid on top of the ground so screenshots can be read
# off the floor (e.g. camera at X=9 sits at the 9th grid line from origin).
# Single 32×32 tile, single mesh quad on top, UV scaled so 1 UV unit = 1
# world metre (relies on GL_REPEAT — see TODO.md § SCRIPTING ENGINES for
# the atlas-UV-uint8-overflow bug that may bite at high UV).


def _room_bounds_mesh(name, b):
    """Build a box-bounds mesh from a (x0,y0,z0,x1,y1,z1) rel-bbox tuple."""
    x0,y0,z0,x1,y1,z1 = b
    verts = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
             (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    m = bpy.data.meshes.new(name)
    m.from_pydata(verts, [], _box_faces)
    m.update()
    return m


def _build_mario():
    mat_red  = make_mat('mario_red',  (0.87, 0.14, 0.07))
    mat_blue = make_mat('mario_blue', (0.18, 0.34, 0.76))
    mat_skin = make_mat('mario_skin', (0.96, 0.73, 0.41))

    parts = []

    # Hat+head — red sphere upper half (origin at ground level = 0)
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.38*T, segments=8, ring_count=5,
        location=(0, 0, 0.80*T))
    parts.append((bpy.context.object, mat_red))

    # Face — skin band
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, radius=0.33*T, depth=0.14*T,
        location=(0, 0, 0.64*T))
    parts.append((bpy.context.object, mat_skin))

    # Body — blue overalls cylinder
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8, radius=0.33*T, depth=0.28*T,
        location=(0, 0, 0.34*T))
    parts.append((bpy.context.object, mat_blue))

    # Legs — two small red cylinders
    for yo in (-0.18*T, 0.18*T):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=6, radius=0.12*T, depth=0.18*T,
            location=(0, yo, 0.09*T))
        parts.append((bpy.context.object, mat_red))

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0
            p.use_smooth = True

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    # Bake body.location into the mesh verts so mesh-local origin sits at the
    # feet (the lowest leg z = 0), not at the head-sphere's location (z=0.80T).
    # WF's actor.pos = feet convention requires mesh-local feet at z=0;
    # otherwise Physics-mobility settling leaves Mario buried in the ground.
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name      = 'player'
    body.data.name = 'player'
    return body


# ── Shared mesh datablocks: build once per type, instance many (P2a) ──────────
# Identical actors must SHARE one Blender mesh datablock so the exporter writes a
# single .iff per type (it dedups by obj.data.name). These helpers build the
# geometry the first time a type is requested, cache the datablock, and return a
# fresh *object* referencing it for every later instance — no per-instance
# datablock names (so no `koopa_green_0.001.iff` churn) and far fewer room-pool
# entries. See docs/plans/2026-06-02-smb-common-extraction-and-mesh-sharing.md.
_shared_mesh = {}   # type key -> bpy mesh datablock


def _setmat(obj, mat):
    """Assign one material to every (smooth) face of obj's mesh."""
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
        p.use_smooth = True
    return obj


def _join(parts, dbname):
    """Join `parts` (first is the keeper) into one mesh object named `dbname`."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = o.data.name = dbname
    return o


def shared_mesh(key, name, build_geo):
    """Return a NEW object `name` sharing the cached `key` datablock (built once
    via build_geo(), which returns the first object — its mesh becomes canonical)."""
    db = _shared_mesh.get(key)
    if db is None:
        obj = build_geo()
        obj.data.name = key
        _shared_mesh[key] = obj.data
        obj.name = name
        return obj
    obj = bpy.data.objects.new(name, db)
    scene.collection.objects.link(obj)
    return obj


# ── Per-type geometry (built once; actor props/scripts/position set by caller) ─
def _koopa_geo(red):
    shell = make_mat('koopa_red_shell' if red else 'koopa_green_shell',
                     (0.78, 0.12, 0.10) if red else (0.14, 0.56, 0.20))
    skin = make_mat('koopa_red_skin' if red else 'koopa_green_skin', (0.90, 0.76, 0.34))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.48*T, segments=10, ring_count=6, location=(0, 0, 0.52*T))
    bpy.context.object.scale.z = 0.80
    bpy.ops.object.transform_apply(scale=True)
    p0 = _setmat(bpy.context.object, shell)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22*T, segments=8, ring_count=5, location=(0.30*T, 0, 0.90*T))
    p1 = _setmat(bpy.context.object, skin)
    return _join([p0, p1], 'koopa_red' if red else 'koopa_green')


def koopa_mesh(name, red=False):
    """One green + one red Koopa datablock, shared across all instances."""
    return shared_mesh('koopa_red' if red else 'koopa_green', name, lambda: _koopa_geo(red))


def _piranha_geo():
    stem = make_mat('piranha_stem', (0.10, 0.62, 0.16))
    head = make_mat('piranha_head', (0.85, 0.10, 0.10))
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.18*T, depth=0.9*T, location=(0, 0, 0.0))
    p0 = _setmat(bpy.context.object, stem)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.40*T, segments=10, ring_count=6, location=(0, 0, 0.55*T))
    p1 = _setmat(bpy.context.object, head)
    return _join([p0, p1], 'piranha')


def piranha_mesh(name):
    """One Piranha datablock, shared across all instances."""
    return shared_mesh('piranha', name, _piranha_geo)


# ── Shared SMB constants + Forth scripts (single source) ─────────────────────
# Geometry/colour/timing axioms + the generator/enemy/template actor scripts that
# were duplicated verbatim in every level. Constants first so the f-string scripts
# below resolve. (Levels keep their own copies of layout constants; these mirror
# them — stable axioms, not logic.)
GROUND_TOP_Z = 0.0
BSIZE        = T / 2
BLOCK_Z      = GROUND_TOP_Z + 4*T + T/2
GROUND_Y     = T
MARIO_Z      = GROUND_TOP_Z + T
MB_SMB_QBLOCK_ACTIVATE = 2010
QBLOCK_TAN   = 0xC77D2E
FLOWER_TINT  = 0xF2731A
SHELL_SPEED      = 14.0
ENEMY_WALK_SPEED = 4.0
CASTLE_TOP        = 3 * T
SPARK_DESPAWN_Z   = CASTLE_TOP + 1.5
PIRANHA_HIDDEN_Z  = GROUND_TOP_Z + 0.5*T
PIRANHA_EMERGED_Z = GROUND_TOP_Z + 3.2*T
PIRANHA_PIPE_TOP  = GROUND_TOP_Z + 2*T
PIRANHA_RATE      = 4.0
PIRANHA_DWELL     = 2.0


QBLOCK_SCRIPT = (
    "\\ wf\n"
    f"INDEXOF_SMB_QBLOCK_USED read-mailbox 0<> if\n"
    f"  0x{QBLOCK_TAN:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
    "else\n"
    "  INDEXOF_SMB_QBLOCK_ACTIVATE read-mailbox 0<> if\n"
    "    0 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "  then\n"
    "  INDEXOF_SMB_QBLOCK_DIE read-mailbox dup not if\n"
    "    drop\n"
    "    INDEXOF_COLLIDER_IDX read-mailbox 0<> if\n"
    "      INDEXOF_COLLISION_NORMAL_Z read-mailbox 0 > if\n"
    "        INDEXOF_TIME read-mailbox 4.0 +\n"
    "        INDEXOF_SMB_QBLOCK_DIE write-mailbox\n"
    "        1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "      then\n"
    "    then\n"
    "  else\n"
    "    INDEXOF_TIME read-mailbox > if\n"
    "      INDEXOF_COLLIDER_IDX read-mailbox 0<> if\n"
    "        INDEXOF_COLLISION_NORMAL_Z read-mailbox 0 > if\n"
    "          1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "        then\n"
    "      then\n"
    "    else\n"
    f"      0x{QBLOCK_TAN:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
    "      1 INDEXOF_SMB_QBLOCK_USED write-mailbox\n"
    "    then\n"
    "  then\n"
    "then\n"
)

DEBRIS_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"
    "INDEXOF_ACTOR_INDEX read-mailbox 4 % 1.5 - 3.0 * INDEXOF_XSPEED write-mailbox\n"
    "INDEXOF_Z_POS read-mailbox -20.0 < if\n"
    "  0 INDEXOF_ALIVE write-mailbox\n"
    "then\n"
)

SPARK_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"                       # tumble
    "INDEXOF_ACTOR_INDEX read-mailbox 9 % 4 - 3.0 * INDEXOF_XSPEED write-mailbox\n"      # fan -12..12 m/s
    f"INDEXOF_Z_POS read-mailbox {SPARK_DESPAWN_Z:.1f} < if 0 INDEXOF_ALIVE write-mailbox then\n"
)

BRICK_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_SMB_BRICK_BREAK_END read-mailbox 0<> if\n"
    "  INDEXOF_TIME read-mailbox INDEXOF_SMB_BRICK_BREAK_END read-mailbox > if\n"
    "    0 INDEXOF_ALIVE write-mailbox\n"
    "  else\n"
    "    1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "  then\n"
    "else\n"
    "  INDEXOF_SMB_BRICK_BUMP_END read-mailbox 0<> if\n"
    "    INDEXOF_TIME read-mailbox INDEXOF_SMB_BRICK_BUMP_END read-mailbox > if\n"
    "      0 INDEXOF_Z_POS write-mailbox\n"
    "      0 INDEXOF_SMB_BRICK_BUMP_END write-mailbox\n"
    "    else\n"
    "      INDEXOF_TIME read-mailbox INDEXOF_SMB_BRICK_BUMP_PEAK read-mailbox > if\n"
    "        0.10 INDEXOF_Z_POS write-mailbox\n"
    "      else\n"
    "        0.30 INDEXOF_Z_POS write-mailbox\n"
    "      then\n"
    "    then\n"
    "  else\n"
    "    INDEXOF_COLLIDER_IDX read-mailbox 0<> if\n"
    "      INDEXOF_COLLISION_NORMAL_Z read-mailbox 0 > if\n"
    "        INDEXOF_SMB_MARIO_STATE read-mailbox 0<> if\n"
    "          INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
    "          INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
    "          1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "          INDEXOF_SMB_SCORE read-mailbox 50 + INDEXOF_SMB_SCORE write-mailbox\n"
    "          INDEXOF_TIME read-mailbox 0.4 + INDEXOF_SMB_BRICK_BREAK_END write-mailbox\n"
    "          1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "        else\n"
    "          INDEXOF_TIME read-mailbox 0.05 + INDEXOF_SMB_BRICK_BUMP_PEAK write-mailbox\n"
    "          INDEXOF_TIME read-mailbox 0.10 + INDEXOF_SMB_BRICK_BUMP_END write-mailbox\n"
    "        then\n"
    "      then\n"
    "    then\n"
    "  then\n"
    "then\n"
)

POPUP_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_SMB_POPUP_TRIGGER read-mailbox 0<> if\n"
    "  INDEXOF_SMB_POPUP_X read-mailbox INDEXOF_X_POS write-mailbox\n"
    "  0 INDEXOF_Y_POS write-mailbox\n"
    "  INDEXOF_SMB_POPUP_Z read-mailbox 1.5 + INDEXOF_Z_POS write-mailbox\n"
    "  INDEXOF_TIME read-mailbox 0.75 + INDEXOF_SMB_POPUP_UNTIL write-mailbox\n"
    "  0 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "then\n"
    "INDEXOF_SMB_POPUP_UNTIL read-mailbox 0<> if\n"
    "  INDEXOF_TIME read-mailbox INDEXOF_SMB_POPUP_UNTIL read-mailbox < if\n"
    "    INDEXOF_Z_POS read-mailbox 3.0 INDEXOF_DELTA_TIME read-mailbox * + INDEXOF_Z_POS write-mailbox\n"
    "  else\n"
    "    0.0 INDEXOF_X_POS write-mailbox\n"
    "    -5.0 INDEXOF_Z_POS write-mailbox\n"
    "    0 INDEXOF_SMB_POPUP_UNTIL write-mailbox\n"
    "  then\n"
    "then\n"
)

ENEMY_SCRIPT = (
    "\\ wf\n"
    # Faithful SMB: stay DORMANT until we scroll into the camera frame, then do the
    # dumb leftward walk (so we no longer pre-walk into pit 0 before Mario arrives).
    # SMB_MAX_CAM_X is the Director's one-way camera ratchet; +12 is the half-frustum,
    # so (SMB_MAX_CAM_X + 12) is the screen's right edge. Once it passes our X we are
    # revealed — and since the ratchet only ever increases, this latches on for good
    # (no per-actor state flag needed).
    "INDEXOF_SMB_MAX_CAM_X read-mailbox 12.0 + INDEXOF_X_POS read-mailbox > if\n"
    f"  {-ENEMY_WALK_SPEED} INDEXOF_XSPEED write-mailbox\n"   # on-screen: walk left toward Mario
    # Proximity to the player. Player<->enemy contacts (both CharacterVirtual) do NOT
    # fire the Jolt collision dispatch (neither is in gBodies — same reason Gold uses
    # proximity), so compare the broadcast player X/Z to our own position.
    "  INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox -\n"    # dx = playerX - myX
    "  dup * 1.0 <\n"                                                       # dx^2 < 1  (close horizontally)
    "  if\n"
    # Star active? touching Mario defeats us — no bounce, no hurt. Else the normal dz logic.
    "    INDEXOF_TIME read-mailbox INDEXOF_SMB_STAR_UNTIL read-mailbox < if\n"
    "      0 INDEXOF_ALIVE write-mailbox\n"                # invincible Mario: defeated by touch
    "    else\n"
    "      INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox -\n"  # dz = playerZ - myZ
    "      dup 0.7 >\n"                                                       # player clearly ABOVE us?
    "      if\n"
    "        drop\n"
    "        INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
    "        INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
    "        1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "        0 INDEXOF_ALIVE write-mailbox\n"              # stomped -> die
    "        1 INDEXOF_SMB_STOMP write-mailbox\n"          # tell the player to bounce
    "      else\n"
    "        -1.5 >\n"                                     # roughly level (not far below) = side hit
    "        if 1 INDEXOF_SMB_PLAYER_HURT write-mailbox then\n"
    "      then\n"
    "    then\n"
    "  then\n"
    "else\n"
    "  0 INDEXOF_XSPEED write-mailbox\n"                 # dormant: stand still until revealed
    "then\n"
    # Fireball defeat (independent of the player block — a fireball can hit us anywhere).
    # Only while a fireball is FRESH (TIME < LIVE_UNTIL); else LIVE_X/Z are stale and ignored.
    "INDEXOF_TIME read-mailbox INDEXOF_SMB_FIREBALL_LIVE_UNTIL read-mailbox < if\n"
    "  INDEXOF_SMB_FIREBALL_LIVE_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"  # dx^2
    "  INDEXOF_SMB_FIREBALL_LIVE_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"  # dz^2
    "  + 2.5 < if\n"                                     # dx^2 + dz^2 < 2.5 (waist-height fireball vs ground enemy)
    "    INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
    "    INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
    "    1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "    INDEXOF_SMB_SCORE read-mailbox 200 + INDEXOF_SMB_SCORE write-mailbox\n"
    "    0 INDEXOF_ALIVE write-mailbox\n"                # fireball kill: die, no bounce, no hurt
    "  then\n"
    "then\n"
    # Sliding-shell defeat — same fresh-broadcast proximity idiom as the fireball, reading the
    # Koopa shell's live position (docs/plans/2026-05-27-smb-koopa-shell-kick.md).
    "INDEXOF_TIME read-mailbox INDEXOF_SMB_SHELL_LIVE_UNTIL read-mailbox < if\n"
    "  INDEXOF_SMB_SHELL_LIVE_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "  INDEXOF_SMB_SHELL_LIVE_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "  + 1.5 < if\n"                                     # both on the ground -> tighter radius
    "    INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
    "    INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
    "    1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "    INDEXOF_SMB_SCORE read-mailbox 100 + INDEXOF_SMB_SCORE write-mailbox\n"
    "    0 INDEXOF_ALIVE write-mailbox\n"
    "  then\n"
    "then\n"
)

KOOPA_SCRIPT = (
    "\\ wf\n"
    # --- movement by state ---
    "INDEXOF_SMB_KOOPA_STATE_L read-mailbox not if\n"                # state 0: walk (dormant-until-onscreen)
    "  INDEXOF_SMB_MAX_CAM_X read-mailbox 12.0 + INDEXOF_X_POS read-mailbox > if\n"
    f"    {-ENEMY_WALK_SPEED} INDEXOF_XSPEED write-mailbox\n"
    "  else\n"
    "    0 INDEXOF_XSPEED write-mailbox\n"
    "  then\n"
    "then\n"
    "INDEXOF_SMB_KOOPA_STATE_L read-mailbox 1 = if 0 INDEXOF_XSPEED write-mailbox then\n"   # state 1: parked
    "INDEXOF_SMB_KOOPA_STATE_L read-mailbox 2 = if\n"                # state 2: sliding shell
    # reverse off a wall (|NORMAL_X| > 0.5), consume the normal (Starman idiom)
    "  INDEXOF_COLLISION_NORMAL_X read-mailbox dup * 0.25 > if\n"
    "    0 INDEXOF_XSPEED read-mailbox - INDEXOF_XSPEED write-mailbox\n"
    "    0 INDEXOF_COLLISION_NORMAL_X write-mailbox\n"
    "  then\n"
    # broadcast the live shell position + freshness so the goomba can die to it
    "  INDEXOF_X_POS read-mailbox INDEXOF_SMB_SHELL_LIVE_X write-mailbox\n"
    "  INDEXOF_Z_POS read-mailbox INDEXOF_SMB_SHELL_LIVE_Z write-mailbox\n"
    "  INDEXOF_TIME read-mailbox 0.1 + INDEXOF_SMB_SHELL_LIVE_UNTIL write-mailbox\n"
    "then\n"
    # --- player interaction (proximity), mirroring the goomba's stack discipline ---
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox -\n"   # dx
    "dup * 1.0 <\n"
    "if\n"
    "  INDEXOF_TIME read-mailbox INDEXOF_SMB_STAR_UNTIL read-mailbox < if\n"
    "    0 INDEXOF_ALIVE write-mailbox\n"                # invincible Mario: dies regardless
    "  else\n"
    "    INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox -\n"   # dz
    "    dup 0.7 >\n"
    "    if\n"                                           # STOMP (player above)
    "      drop\n"
    "      INDEXOF_SMB_KOOPA_STATE_L read-mailbox 2 < if 0.5 INDEXOF_Z_SCALE write-mailbox then\n"  # walk->shell: squash
    "      INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
    "      INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
    "      1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "      1 INDEXOF_SMB_KOOPA_STATE_L write-mailbox\n"    # retract to a resting shell (NOT death)
    "      0 INDEXOF_XSPEED write-mailbox\n"
    "      1 INDEXOF_SMB_STOMP write-mailbox\n"          # bounce Mario
    "    else\n"                                         # side touch (roughly level)
    "      -1.5 >\n"
    "      if\n"
    "        INDEXOF_SMB_KOOPA_STATE_L read-mailbox 1 = if\n"   # KICK a resting shell, away from Mario
    "          INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - 0 < if\n"
    f"            {SHELL_SPEED} INDEXOF_XSPEED write-mailbox\n"        # player on the left -> slide right
    "          else\n"
    f"            {-SHELL_SPEED} INDEXOF_XSPEED write-mailbox\n"       # player on the right -> slide left
    "          then\n"
    "          2 INDEXOF_SMB_KOOPA_STATE_L write-mailbox\n"
    "        else\n"
    "          1 INDEXOF_SMB_PLAYER_HURT write-mailbox\n"  # walking koopa OR moving shell -> hurt Mario
    "        then\n"
    "      then\n"
    "    then\n"
    "  then\n"
    "then\n"
    # --- fireball defeat (any state) ---
    "INDEXOF_TIME read-mailbox INDEXOF_SMB_FIREBALL_LIVE_UNTIL read-mailbox < if\n"
    "  INDEXOF_SMB_FIREBALL_LIVE_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "  INDEXOF_SMB_FIREBALL_LIVE_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "  + 2.5 < if\n"
    "    INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
    "    INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
    "    1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "    INDEXOF_SMB_SCORE read-mailbox 200 + INDEXOF_SMB_SCORE write-mailbox\n"
    "    0 INDEXOF_ALIVE write-mailbox\n"
    "  then\n"
    "then\n"
)

POWERUP_BLOCK_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_SMB_QBLOCK_USED read-mailbox 0<> if\n"
    f"  0x{QBLOCK_TAN:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
    "else\n"
    "  INDEXOF_SMB_QBLOCK_ACTIVATE read-mailbox 0<> if\n"
    "    0 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"          # generator consumed the pulse last tick
    f"    0x{QBLOCK_TAN:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
    "    1 INDEXOF_SMB_QBLOCK_USED write-mailbox\n"              # one mushroom only -> latch used
    "  else\n"
    "    INDEXOF_COLLIDER_IDX read-mailbox 0<> if\n"
    "      INDEXOF_COLLISION_NORMAL_Z read-mailbox 0 > if\n"     # bump-from-below
    "        1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox\n"
    "      then\n"
    "    then\n"
    "  then\n"
    "then\n"
)

POWERUP_SCRIPT = (
    "\\ wf\n"
    # Identity from Mario's current tier (Super+ -> flower: orange + stationary).
    "INDEXOF_SMB_MARIO_STATE read-mailbox 0 > if\n"
    "  0 INDEXOF_XSPEED write-mailbox\n"
    f"  0x{FLOWER_TINT:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
    "then\n"
    # Proximity pickup (dx^2 + dz^2 < 1.5^2) -> raise the signal for Mario's tier.
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "+ 2.25 < if\n"
    "  INDEXOF_SMB_MARIO_STATE read-mailbox 0 > if\n"
    "    1 INDEXOF_SMB_FIREFLOWER_PICKUP write-mailbox\n"
    "  else\n"
    "    1 INDEXOF_SMB_MUSHROOM_PICKUP write-mailbox\n"
    "  then\n"
    "then\n"
)

STAR_SCRIPT = (
    "\\ wf\n"
    # Starman bounce: re-launch upward on a real floor contact. Landing on static
    # ground routes through Actor::JoltStaticCollision -> COLLIDER_IDX=0 (no actor)
    # and COLLISION_NORMAL_Z < 0 (the normal points DOWN, the way the char pushes
    # into the floor). We gate on that, then ZERO the normal to consume it: it is
    # NOT cleared per-frame (only COLLIDER_IDX is, actor.cc:1106), so without the
    # consume the stale value would re-fire mid-air. Ground-aware: over a pit there
    # is no contact, the normal stays 0, and the star falls in.
    "INDEXOF_COLLISION_NORMAL_Z read-mailbox -0.5 < if\n"
    "  6.0 INDEXOF_ZSPEED write-mailbox\n"
    "  0 INDEXOF_COLLISION_NORMAL_Z write-mailbox\n"
    "then\n"
    # Wall/pipe/flagpole reversal: a side contact gives |COLLISION_NORMAL_X| ~ 1 (and
    # NORMAL_Z ~ 0). Negate XSPEED and consume the X-normal, same idiom as the bounce.
    # `dup * 0.25 >` tests NX^2 > 0.25 i.e. |NX| > 0.5 (avoids needing abs).
    "INDEXOF_COLLISION_NORMAL_X read-mailbox dup * 0.25 > if\n"
    "  0 INDEXOF_XSPEED read-mailbox - INDEXOF_XSPEED write-mailbox\n"
    "  0 INDEXOF_COLLISION_NORMAL_X write-mailbox\n"
    "then\n"
    # Proximity pickup -> raise the Star signal; Gold::update removes the actor.
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "+ 2.25 < if\n"
    "  1 INDEXOF_SMB_STAR_PICKUP write-mailbox\n"
    "then\n"
)

ONEUP_SCRIPT = (
    "\\ wf\n"
    # Proximity pickup (dx^2 + dz^2 < 1.5^2 = 2.25) -> signal for +1 life.
    # gold.cc TryPickup also fires at radius 1.5 and calls SetPendingRemove (despawn).
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "+ 2.25 < if\n"
    "  1 INDEXOF_SMB_ONEUP_PICKUP write-mailbox\n"
    "then\n"
)

FIREBALL_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_X_POS read-mailbox INDEXOF_SMB_FIREBALL_LIVE_X write-mailbox\n"
    "INDEXOF_Z_POS read-mailbox INDEXOF_SMB_FIREBALL_LIVE_Z write-mailbox\n"
    "INDEXOF_TIME read-mailbox 0.1 + INDEXOF_SMB_FIREBALL_LIVE_UNTIL write-mailbox\n"
)

FIREBALL_GEN_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_SMB_FIREBALL_X read-mailbox INDEXOF_X_POS write-mailbox\n"
    "INDEXOF_SMB_FIREBALL_Y read-mailbox INDEXOF_Y_POS write-mailbox\n"
    "INDEXOF_SMB_FIREBALL_Z read-mailbox INDEXOF_Z_POS write-mailbox\n"
)

PIRANHA_SCRIPT = (
    "\\ wf\n"
    # Seed the per-actor next-toggle deadline once; stagger by ACTOR_INDEX so the four
    # plants are out of phase (index*0.4 s offset). `%` casts to int.
    "INDEXOF_SMB_PIRANHA_NEXT_L read-mailbox not if\n"
    f"  INDEXOF_TIME read-mailbox INDEXOF_ACTOR_INDEX read-mailbox 5 % 0.4 * + {PIRANHA_DWELL} +\n"
    "  INDEXOF_SMB_PIRANHA_NEXT_L write-mailbox\n"
    "  1 INDEXOF_SMB_PIRANHA_UP_L write-mailbox\n"
    "then\n"
    # Phase toggle on the TIME deadline: flip UP, push the next deadline out by DWELL.
    "INDEXOF_TIME read-mailbox INDEXOF_SMB_PIRANHA_NEXT_L read-mailbox > if\n"
    "  INDEXOF_SMB_PIRANHA_UP_L read-mailbox not INDEXOF_SMB_PIRANHA_UP_L write-mailbox\n"
    f"  INDEXOF_TIME read-mailbox {PIRANHA_DWELL} + INDEXOF_SMB_PIRANHA_NEXT_L write-mailbox\n"
    "then\n"
    # GO = phase-up AND Mario not standing on the pipe mouth (|dx|<1.2 AND playerZ>2.0).
    "INDEXOF_SMB_PIRANHA_UP_L read-mailbox\n"
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup * 1.44 < if\n"
    "  INDEXOF_SMB_PLAYER_Z read-mailbox 2.0 > if drop 0 then\n"
    "then\n"
    # Slide toward the limit at RATE*dt.
    "if\n"
    f"  INDEXOF_Z_POS read-mailbox {PIRANHA_EMERGED_Z} < if\n"
    f"    INDEXOF_Z_POS read-mailbox {PIRANHA_RATE} INDEXOF_DELTA_TIME read-mailbox * + INDEXOF_Z_POS write-mailbox\n"
    "  then\n"
    "else\n"
    f"  INDEXOF_Z_POS read-mailbox {PIRANHA_HIDDEN_Z} > if\n"
    f"    INDEXOF_Z_POS read-mailbox {PIRANHA_RATE} INDEXOF_DELTA_TIME read-mailbox * - INDEXOF_Z_POS write-mailbox\n"
    "  then\n"
    "then\n"
    # Hurt: emerged (Z above pipe top) AND Mario in contact (close in X AND Z).
    f"INDEXOF_Z_POS read-mailbox {PIRANHA_PIPE_TOP} > if\n"
    "  INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "  INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "  + 2.0 < if\n"
    "    1 INDEXOF_SMB_PLAYER_HURT write-mailbox\n"
    "  then\n"
    "then\n"
    # Fireball defeat (any height) — same idiom as the goomba.
    "INDEXOF_TIME read-mailbox INDEXOF_SMB_FIREBALL_LIVE_UNTIL read-mailbox < if\n"
    "  INDEXOF_SMB_FIREBALL_LIVE_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "  INDEXOF_SMB_FIREBALL_LIVE_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "  + 2.5 < if\n"
    "    INDEXOF_SMB_SCORE read-mailbox 200 + INDEXOF_SMB_SCORE write-mailbox\n"
    "    0 INDEXOF_ALIVE write-mailbox\n"
    "  then\n"
    "then\n"
)


# ── Self-contained builders (geometry/actor setup; deps already in smb_common) ─
def _apply_enemy_movement(obj):
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 1.0
    obj['wf_Turn Rate']            = 0.0     # → MarbleHandler (no input, carries velocity)
    obj['wf_Running Deceleration'] = 0.0     # frictionless: keeps walk velocity
    obj['wf_Max Ground Speed']     = 8.0
    obj['wf_Max Air Speed']        = 50.0    # don't let the speed cap zero gravity (marble bug)
    obj['wf_Falling Acceleration'] = 12.0
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Script']               = ENEMY_SCRIPT


def _build_goomba():
    mat_br = make_mat('goomba_brown', (0.55, 0.27, 0.06))
    mat_tn = make_mat('goomba_tan',   (0.83, 0.65, 0.34))

    parts = []

    # Body — flattened brown sphere
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.48*T, segments=10, ring_count=6,
        location=(0, 0, 0.44*T))
    bpy.context.object.scale.z = 0.72
    bpy.ops.object.transform_apply(scale=True)
    parts.append((bpy.context.object, mat_br))

    # Face band — tan strip for eyes
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=10, radius=0.34*T, depth=0.09*T,
        location=(0, 0, 0.54*T))
    parts.append((bpy.context.object, mat_tn))

    # Feet — two brown spheres
    for yo in (-0.19*T, 0.19*T):
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.14*T, segments=6, ring_count=4,
            location=(0, yo, 0.10*T))
        parts.append((bpy.context.object, mat_br))

    for obj, mat in parts:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for p in obj.data.polygons:
            p.material_index = 0
            p.use_smooth = True

    bpy.ops.object.select_all(action='DESELECT')
    for obj, _ in parts:
        obj.select_set(True)
    body = parts[0][0]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name      = 'goomba_00'
    body.data.name = 'goomba_00'
    return body


def _make_target(name, loc):
    t = bpy.data.objects.new(name, None)
    scene.collection.objects.link(t)
    attach_schema(t, 'target')
    t.location = loc
    t['wf_Model Type'] = 'None'
    return t

# Entry landing (where Down warps Mario) + cs_coin look-at point.


def _make_popup_template():
    POP_W = T * 0.35
    POP_H = T * 0.45
    POP_T = 0.12
    bm = _bmesh.new()
    tf = bm.verts.new((0,      POP_T,  POP_H))
    rf = bm.verts.new((POP_W,  POP_T,  0))
    bf = bm.verts.new((0,      POP_T, -POP_H))
    lf = bm.verts.new((-POP_W, POP_T,  0))
    tb = bm.verts.new((0,     -POP_T,  POP_H))
    rb = bm.verts.new((POP_W, -POP_T,  0))
    bb = bm.verts.new((0,     -POP_T, -POP_H))
    lb = bm.verts.new((-POP_W,-POP_T,  0))
    bm.faces.new([tf, rf, bf, lf])
    bm.faces.new([tb, lb, bb, rb])
    bm.faces.new([tf, tb, rb, rf])
    bm.faces.new([rf, rb, bb, bf])
    bm.faces.new([bf, bb, lb, lf])
    bm.faces.new([lf, lb, tb, tf])
    mesh = bpy.data.meshes.new('popup_score')
    bm.to_mesh(mesh); bm.free()
    mat = make_mat('smb_popup', (1.0, 0.95, 0.2))
    mesh.materials.append(mat)
    for p in mesh.polygons:
        p.material_index = 0
    obj = bpy.data.objects.new('popup_score', mesh)
    obj.location = (0.0, 0.0, -5.0)   # underground inside room bbox so script runs
    scene.collection.objects.link(obj)
    attach_schema(obj, 'enemy')
    obj['wf_Mobility']             = 'Anchored'
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Mesh Name']            = 'popup_score.iff'
    obj['wf_Script']               = POPUP_SCRIPT
    return obj


def _make_fireball_generator(name, fire_mb, vx):
    # Empty (no mesh) -> the exporter emits no mesh + Model Type stays the generator
    # default (Box, not Mesh) -> NO Jolt static body (actor.cc:803) -> non-solid, so the
    # generator parked on/near Mario never blocks or shoves him.
    g = bpy.data.objects.new(name, None)
    scene.collection.objects.link(g)
    attach_schema(g, 'generator')
    g.location = (-64.0, 0.0, 0.0)        # parked off-screen until the self-park script tracks Mario
    g['wf_Mobility']           = 'Anchored'
    g['wf_Model Type']         = 'None'   # documents intent; the Empty already exports meshless
    g['wf_Visibility Mailbox'] = 0        # invisible spawner
    g['wf_Activation MailBox'] = fire_mb  # GLOBAL mailbox: Mario pulses it, no actor-index needed
    g['wf_Object To Throw']    = 'fireball_template'
    g['wf_Generation Rate']    = 20.0     # fast: a one-tick activation pulse throws exactly one
    g['wf_Object X Velocity']  = vx
    g['wf_Object Y Velocity']  = 0.0
    g['wf_Object Z Velocity']  = 0.0
    g['wf_Script']             = FIREBALL_GEN_SCRIPT
    return g
