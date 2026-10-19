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


def _unit_box_geo(mat):
    """A 1×1×1 cube at the origin with `mat` on every (flat) face — the canonical
    datablock shared by all `add_box` instances of this material (P2b)."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    obj = bpy.context.object
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    return obj


def add_box(mesh_name, x0, y0, z0, x1, y1, z1, mat):
    """Add a box [x0..x1]×[y0..y1]×[z0..z1], return the object.

    All boxes of one material share a single unit-cube datablock and carry their
    size as live `obj.scale` (no transform_apply) — the export pipeline emits that
    scale (P2-pre) so N differently-sized boxes cost ONE room-pool mesh, not N.
    Scale drives the render mesh; the exporter scales the collision BOX3 to match.
    """
    cx, cy, cz = (x0+x1)/2, (y0+y1)/2, (z0+z1)/2
    sx, sy, sz = x1-x0, y1-y0, z1-z0
    obj = shared_mesh('unit_box::' + mat.name, mesh_name, lambda: _unit_box_geo(mat))
    obj.location = (cx, cy, cz)
    obj.scale    = (sx, sy, sz)
    return obj


def add_statplat(mesh_name, x0, y0, z0, x1, y1, z1, mat):
    obj = add_box(mesh_name, x0, y0, z0, x1, y1, z1, mat)
    attach_schema(obj, 'statplat')
    obj['wf_Visibility Mailbox'] = 1
    obj['wf_Model Type'] = 'Mesh'
    return obj


def _textured_box_geo(tex_path):
    """Canonical 1×1×1 UV-textured box at the origin (full [0,1]² per face), shared
    by every `_add_textured_box` instance of this texture (P2b).

    The front face (-Y, camera-side) gets vertex order chosen so the texture appears
    right-side-up when the camera is at Y≈-30 looking +Y. UV V=0 = top of the PIL
    image; V=1 = bottom — matching the WF/textile-rs VRAM convention where row 0 is
    the image top. UVs are per-loop so they are unaffected by the instances' scale.
    """
    import bmesh

    mat = bpy.data.materials.new(name='tex_' + os.path.basename(tex_path))
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf  = nodes['Principled BSDF']
    tex   = nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(tex_path)
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')

    h = 0.5  # unit cube ±0.5; instances carry the real size as obj.scale
    v = [
        bm.verts.new((-h, -h, -h)),  # 0
        bm.verts.new(( h, -h, -h)),  # 1
        bm.verts.new(( h,  h, -h)),  # 2
        bm.verts.new((-h,  h, -h)),  # 3
        bm.verts.new((-h, -h,  h)),  # 4
        bm.verts.new(( h, -h,  h)),  # 5
        bm.verts.new(( h,  h,  h)),  # 6
        bm.verts.new((-h,  h,  h)),  # 7
    ]

    # UV corners per face: (bottom-left, bottom-right, top-right, top-left)
    # viewed from outside, with V=0=image-top / V=1=image-bottom (WF VRAM convention).
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

    mesh = bpy.data.meshes.new('tex_box')
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)

    obj = bpy.data.objects.new('tex_box', mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _add_textured_box(mesh_name, x0, y0, z0, x1, y1, z1, tex_path):
    """Add a UV-textured box, sharing one canonical unit datablock per texture.

    All bricks share one mesh, all ?-blocks/power-up blocks another (they key on
    `tex_path`); per-instance size rides as live `obj.scale` (P2-pre emits it). The
    distinguishing generator script/mailboxes live in each object's OAS, not the mesh.
    """
    cx, cy, cz = (x0+x1)/2, (y0+y1)/2, (z0+z1)/2
    sx, sy, sz = x1-x0, y1-y0, z1-z0
    # Key on the texture basename (one brick + one ?-block texture per level) so the
    # shared datablock name stays short (Blender truncates names at 63 chars).
    obj = shared_mesh('tex_box::' + os.path.basename(tex_path), mesh_name,
                      lambda: _textured_box_geo(tex_path))
    obj.location = (cx, cy, cz)
    obj.scale    = (sx, sy, sz)
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
                         line_px=1, bg=(143, 97, 38), fg=(102, 66, 23)):
    """Pre-tiled grid texture (one image, no mesh subdivision needed):
    `cells_x` × `cells_y` grid lines baked in, `bg` fill with `fg` lines along
    the top + left edge of each cell (default: light brown / darker brown for
    the overworld grounds; pass a gray pair for the castle floors).

    Dims forced to {16,32,64,128,256,512,1024}^2 (textile-rs power-of-2
    constraint at bitmap.rs:507). The whole texture is mapped UV [0, 1]
    across the ground top face — works around the renderer's atlas-UV
    uint8 overflow that breaks GL_REPEAT for mesh UVs above ~5
    (docs/investigations/2026-05-18-texture-uv-uint8-overflow.md).

    Defaults: 256×32 texture, 64 grid cells in X, 8 in Y. Mapped across the
    73.5 m ground that gives one grid line every 73.5/64 ≈ 1.15 m — close
    enough to a 1-metre grid for visual position estimation."""
    from PIL import Image
    BG = bg
    FG = fg
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


def _paratroopa_geo():
    """Green Koopa body (same shell+head as _koopa_geo) plus two white wings spread to
    either side so it reads as a Paratroopa from the side camera."""
    shell = make_mat('koopa_green_shell', (0.14, 0.56, 0.20))
    skin  = make_mat('koopa_green_skin',  (0.90, 0.76, 0.34))
    wing  = make_mat('paratroopa_wing',   (0.96, 0.96, 0.98))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.48*T, segments=10, ring_count=6, location=(0, 0, 0.52*T))
    bpy.context.object.scale.z = 0.80
    bpy.ops.object.transform_apply(scale=True)
    p0 = _setmat(bpy.context.object, shell)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22*T, segments=8, ring_count=5, location=(0.30*T, 0, 0.90*T))
    p1 = _setmat(bpy.context.object, skin)
    parts = [p0, p1]
    for sx in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(sx*0.52*T, 0.0, 0.74*T))
        w = bpy.context.object
        w.scale = (0.14*T, 0.30*T, 0.44*T)
        bpy.ops.object.transform_apply(scale=True)
        w.rotation_euler = (0.0, sx*0.5, 0.0)   # tilt each wing outward (radians)
        bpy.ops.object.transform_apply(rotation=True)
        parts.append(_setmat(w, wing))
    return _join(parts, 'paratroopa')


def paratroopa_mesh(name):
    """One Paratroopa datablock, shared across all instances."""
    return shared_mesh('paratroopa', name, _paratroopa_geo)


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
# Koopa Paratroopa (W1-3): a green Koopa that bounces in place over the tree-tops.
# Vertical triangle-wave between PARA_LOW_Z and PARA_HIGH_Z at PARA_RATE m/s; reuses the
# per-actor local SMB_PIRANHA_UP_L (2016) as the up/down phase flag (generic oscillator
# slot — no piranhas in W1-3). Anchored, hurts on side contact, despawns when stomped.
PARA_LOW_Z   = MARIO_Z + 1.0*T
PARA_HIGH_Z  = MARIO_Z + 3.0*T
PARA_RATE    = 5.0
COIN_PICK_R2 = 1.5            # coin proximity-pickup radius^2 (dx^2+dz^2 < this)


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


def firebar_segment_script(px, pz, omega):
    """One SMB castle fire-bar segment (W1-4). An Anchored actor that orbits the
    pivot (px, pz) in the XZ plane at angular velocity `omega` rad/s and hurts the
    player on contact (no stomp — fire-bars are pure hazards).

    Motion uses **symplectic Euler** (update X from the OLD Z, then Z from the
    NEW X). The per-frame map has determinant 1, so the orbit stays a bounded
    closed ellipse forever; plain explicit Euler would spiral every segment
    outward over the level's lifetime. All segments of one bar share the same
    omega → identical per-frame map → they rotate in lockstep and stay collinear
    through the pivot, so the bar reads as a rigid spinning rod.

    The pivot is baked in as a literal, so segments need no per-actor mailbox
    (every bar gets its own script string; ~7 unique strings for the level).
    `omega` sign sets spin direction (+ = counter-clockwise in screen XZ)."""
    return (
        "\\ wf\n"
        # new_x = X_POS - (omega*dt) * (Z_POS - pz)
        "INDEXOF_X_POS read-mailbox\n"
        f"  {omega:.5f} INDEXOF_DELTA_TIME read-mailbox *\n"
        f"  INDEXOF_Z_POS read-mailbox {pz:.4f} -\n"
        "  *\n"
        "- INDEXOF_X_POS write-mailbox\n"
        # new_z = Z_POS + (omega*dt) * (X_POS - px)   [X_POS already updated → symplectic]
        "INDEXOF_Z_POS read-mailbox\n"
        f"  {omega:.5f} INDEXOF_DELTA_TIME read-mailbox *\n"
        f"  INDEXOF_X_POS read-mailbox {px:.4f} -\n"
        "  *\n"
        "+ INDEXOF_Z_POS write-mailbox\n"
        # lethal proximity: hurt the player within ~1 m (no stomp branch)
        "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
        "INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
        "+ 1.0 < if\n"
        "  1 INDEXOF_SMB_PLAYER_HURT write-mailbox\n"
        "then\n"
    )


# ── SMB W1-4 castle boss: Fake Bowser + axe ────────────────────────────────────
# The axe (end of the boss bridge): on player proximity it raises SMB_CELEBRATE —
# the same end-of-level signal the flagpole uses — then despawns. The Director's
# celebration sequencer runs the cutscene and fires END_OF_LEVEL. Fake Bowser
# also watches SMB_CELEBRATE and despawns ("falls in the lava") when the axe is hit.
AXE_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "+ 2.5 < if\n"
    "  1 INDEXOF_SMB_CELEBRATE write-mailbox\n"
    "  0 INDEXOF_ALIVE write-mailbox\n"
    "then\n"
)

# Bowser's fireball: a Physics missile thrown leftward by the boss's generator on
# the SMB_BOWSER_FIRE pulse. Unlike Mario's fireball (which defeats enemies), this
# one HURTS the player on proximity, then despawns.
BOWSER_FB_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    "+ 1.7 < if\n"
    "  1 INDEXOF_SMB_PLAYER_HURT write-mailbox\n"
    "  0 INDEXOF_ALIVE write-mailbox\n"
    "then\n"
)


def fakebowser_script(bridge_l, bridge_r, walk_speed=1.5, fire_interval=2.5):
    """Fake Bowser (W1-4 boss) — a big Physics enemy patrolling the boss bridge.
    Walks back and forth between [bridge_l, bridge_r], lobs a fireball leftward
    every `fire_interval` s (pulses SMB_BOWSER_FIRE for its generator), hurts the
    player on contact (no stomp — you can't jump on Bowser), and tracks 5 hit
    points: each fresh Mario fireball within range knocks one off (0.5 s debounce
    so one fireball isn't counted on consecutive frames). Defeated at 0 HP OR when
    the axe raises SMB_CELEBRATE — either way it despawns and the level ends."""
    return (
        "\\ wf\n"
        # defeat by the axe (celebration) — Bowser falls
        "INDEXOF_SMB_CELEBRATE read-mailbox if 0 INDEXOF_ALIVE write-mailbox then\n"
        # seed 5 HP once
        "INDEXOF_LOCAL_BOWSER_HP read-mailbox not if 5 INDEXOF_LOCAL_BOWSER_HP write-mailbox then\n"
        # walk: kick off / keep moving if (near) stopped, then bounce at the rail ends
        f"INDEXOF_XSPEED read-mailbox dup * 0.01 < if {-walk_speed:.2f} INDEXOF_XSPEED write-mailbox then\n"
        f"INDEXOF_X_POS read-mailbox {bridge_r:.2f} > if {-walk_speed:.2f} INDEXOF_XSPEED write-mailbox then\n"
        f"INDEXOF_X_POS read-mailbox {bridge_l:.2f} < if {walk_speed:.2f} INDEXOF_XSPEED write-mailbox then\n"
        # fire timer: accumulate dt; on overflow pulse SMB_BOWSER_FIRE and reset
        "INDEXOF_LOCAL_BOWSER_FIRE_T read-mailbox INDEXOF_DELTA_TIME read-mailbox +\n"
        f"dup {fire_interval:.2f} > if\n"
        "  drop 0.0\n"
        "  1 INDEXOF_SMB_BOWSER_FIRE write-mailbox\n"
        "else\n"
        "  0 INDEXOF_SMB_BOWSER_FIRE write-mailbox\n"
        "then\n"
        "INDEXOF_LOCAL_BOWSER_FIRE_T write-mailbox\n"
        # decay the hit-debounce cooldown
        "INDEXOF_LOCAL_BOWSER_HIT_COOL read-mailbox 0 > if\n"
        "  INDEXOF_LOCAL_BOWSER_HIT_COOL read-mailbox INDEXOF_DELTA_TIME read-mailbox -\n"
        "  dup 0 < if drop 0 then INDEXOF_LOCAL_BOWSER_HIT_COOL write-mailbox\n"
        "then\n"
        # Mario's fireball knocks off 1 HP (only while fresh AND not debouncing)
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_FIREBALL_LIVE_UNTIL read-mailbox < if\n"
        "  INDEXOF_LOCAL_BOWSER_HIT_COOL read-mailbox 0.01 < if\n"
        "    INDEXOF_SMB_FIREBALL_LIVE_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
        "    INDEXOF_SMB_FIREBALL_LIVE_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
        "    + 4.0 < if\n"
        "      INDEXOF_LOCAL_BOWSER_HP read-mailbox 1 - dup INDEXOF_LOCAL_BOWSER_HP write-mailbox\n"
        "      1 < if 1 INDEXOF_SMB_CELEBRATE write-mailbox 0 INDEXOF_ALIVE write-mailbox then\n"
        "      0.5 INDEXOF_LOCAL_BOWSER_HIT_COOL write-mailbox\n"
        "    then\n"
        "  then\n"
        "then\n"
        # hurt the player on contact — big body, no stomp branch
        "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
        "INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
        "+ 3.0 < if 1 INDEXOF_SMB_PLAYER_HURT write-mailbox then\n"
    )


def _make_bowser_fireball_template():
    """Bowser's projectile — a Physics missile (frictionless, flat flight, 2 s TTL)
    that hurts the player. Mirrors _make_fireball_template but runs BOWSER_FB_SCRIPT
    (hurt-the-player, not defeat-enemies) and parks at its own off-screen spot."""
    bm = _bmesh.new()
    _bmesh.ops.create_cube(bm, size=1.0)
    _bmesh.ops.scale(bm, vec=(FB*2.4, FB*2.4, FB*2.4), verts=bm.verts)
    mesh = bpy.data.meshes.new('bowser_fireball_template')
    bm.to_mesh(mesh); bm.free()
    mesh.materials.append(mat_fireball())
    for p in mesh.polygons:
        p.material_index = 0
    obj = bpy.data.objects.new('bowser_fireball_template', mesh)
    obj.location = (-78.0, 0.0, 0.0)
    scene.collection.objects.link(obj)
    attach_schema(obj, 'missile')
    obj['wf_Template Object']      = 'True'
    obj['wf_Moves Between Rooms']  = 'True'
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 0.001
    obj['wf_Falling Acceleration'] = 0.0
    obj['wf_Max Air Speed']        = 50.0
    obj['wf_Surface Friction']     = 0.0
    obj['wf_Horiz Air Drag']       = 0.0
    obj['wf_Vert Air Drag']        = 0.0
    obj['wf_Running Deceleration'] = 0.0
    obj['wf_Explosion Delay']      = 2.0
    obj['wf_Explode On Impact']    = 'True'
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Mesh Name']            = 'bowser_fireball_template.iff'
    obj['wf_Script']               = BOWSER_FB_SCRIPT
    return obj


def _make_bowser_fireball_generator(name, x, z, vx=-8.0):
    """Fixed generator on the boss bridge: throws one bowser_fireball_template
    leftward each time Fake Bowser pulses SMB_BOWSER_FIRE."""
    g = bpy.data.objects.new(name, None)
    scene.collection.objects.link(g)
    attach_schema(g, 'generator')
    g.location = (x, 0.0, z)
    g['wf_Mobility']           = 'Anchored'
    g['wf_Model Type']         = 'None'
    g['wf_Visibility Mailbox'] = 0
    g['wf_Activation MailBox'] = 1872   # INDEXOF_SMB_BOWSER_FIRE
    g['wf_Object To Throw']    = 'bowser_fireball_template'
    g['wf_Generation Rate']    = 20.0   # fast → one pulse throws exactly one
    g['wf_Object X Velocity']  = vx
    g['wf_Object Y Velocity']  = 0.0
    g['wf_Object Z Velocity']  = 0.0
    return g


# Koopa Paratroopa — airborne green Koopa bouncing over the tree-tops (W1-3). Vertical
# triangle wave via the per-actor SMB_PIRANHA_UP_L phase flag (1=rising, 0=falling); flips
# at PARA_HIGH_Z / PARA_LOW_Z. Player interaction mirrors the Koopa: Star kills it; a stomp
# (player clearly above) pops a score + bounces Mario + despawns it; a side touch hurts.
PARATROOPA_SCRIPT = (
    "\\ wf\n"
    # --- vertical bounce ---
    "INDEXOF_SMB_PIRANHA_UP_L read-mailbox if\n"
    f"  INDEXOF_Z_POS read-mailbox {PARA_HIGH_Z} < if\n"
    f"    INDEXOF_Z_POS read-mailbox {PARA_RATE} INDEXOF_DELTA_TIME read-mailbox * + INDEXOF_Z_POS write-mailbox\n"
    "  else\n"
    "    0 INDEXOF_SMB_PIRANHA_UP_L write-mailbox\n"
    "  then\n"
    "else\n"
    f"  INDEXOF_Z_POS read-mailbox {PARA_LOW_Z} > if\n"
    f"    INDEXOF_Z_POS read-mailbox {PARA_RATE} INDEXOF_DELTA_TIME read-mailbox * - INDEXOF_Z_POS write-mailbox\n"
    "  else\n"
    "    1 INDEXOF_SMB_PIRANHA_UP_L write-mailbox\n"
    "  then\n"
    "then\n"
    # --- player interaction (proximity), same stack discipline as KOOPA_SCRIPT ---
    "INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox -\n"   # dx
    "dup * 1.0 <\n"
    "if\n"
    "  INDEXOF_TIME read-mailbox INDEXOF_SMB_STAR_UNTIL read-mailbox < if\n"
    "    INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
    "    INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
    "    1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "    INDEXOF_SMB_SCORE read-mailbox 100 + INDEXOF_SMB_SCORE write-mailbox\n"
    "    0 INDEXOF_ALIVE write-mailbox\n"                # invincible Mario: dies regardless
    "  else\n"
    "    INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox -\n"   # dz
    "    dup 0.7 >\n"
    "    if\n"                                           # STOMP (player above)
    "      drop\n"
    "      INDEXOF_X_POS read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
    "      INDEXOF_Z_POS read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
    "      1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
    "      INDEXOF_SMB_SCORE read-mailbox 100 + INDEXOF_SMB_SCORE write-mailbox\n"
    "      1 INDEXOF_SMB_STOMP write-mailbox\n"          # bounce Mario
    "      0 INDEXOF_ALIVE write-mailbox\n"              # defeated -> despawn (no shell stage)
    "    else\n"                                         # side touch (roughly level)
    "      -1.5 >\n"
    "      if 1 INDEXOF_SMB_PLAYER_HURT write-mailbox then\n"
    "    then\n"
    "  then\n"
    "then\n"
)

# Open-air collectible coin (W1-3) — an Anchored Enemy spinning disc that collects itself
# on player proximity: +200 score then ALIVE=0 (despawn, like a stomped enemy). The
# per-actor SMB_COIN_TAKEN_L latch gates the proximity test so the score adds exactly once
# even if the despawn settles a frame later. No parking (parked actors leak into frame —
# project_smb_parked_helper_visibility) and no per-coin global: the player X/Z it reads are
# the existing SMB_PLAYER_X/SMB_PLAYER_Z broadcasts.
COIN_PICKUP_SCRIPT = (
    "\\ wf\n"
    "INDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"   # spin in place
    "INDEXOF_SMB_COIN_TAKEN_L read-mailbox not if\n"
    "  INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *\n"
    "  INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *\n"
    f"  + {COIN_PICK_R2} < if\n"
    "    INDEXOF_SMB_SCORE read-mailbox 200 + INDEXOF_SMB_SCORE write-mailbox\n"
    "    1 INDEXOF_SMB_COIN_TAKEN_L write-mailbox\n"
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
    body.name      = 'goomba'
    body.data.name = 'goomba'   # canonical type name (one shared mesh, all instances)
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
    # Gate visibility on SMB_POPUP_UNTIL (1845): its value is 0 while idle/parked and
    # nonzero only during the 0.75 s score-pop window (mailbox.inc: "0 = idle/parked").
    # Was hard-wired to 1 (always visible) — that left the parked yellow diamond rendered
    # at (0,0,-5), in-frame near Mario's spawn (the "stray gold coin" on W1-1). With the
    # gate it only draws while it animates upward. See project_smb_parked_helper_visibility.
    obj['wf_Visibility Mailbox']   = 1845   # INDEXOF_SMB_POPUP_UNTIL
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


# ── Builder deps: dimensions, COIN_SCRIPT, lazy material getters (P2a/#1 batch B2) ─
COIN_X = T * 0.25
COIN_Z = T * 0.5
COIN_T = 0.2
MUSH_X = T * 0.40
MUSH_Z = T * 0.40
MUSH_T = 0.25
FB       = 0.2
SPARK_H  = 0.16
DEBRIS_H = 0.18

COIN_SCRIPT = "\\ wf\nINDEXOF_TIME read-mailbox INDEXOF_ROTATION_C write-mailbox\n"

_mat_cache = {}


def _mat(key, name, rgb):
    """Lazily create + cache one material per key (shared by builders + level layout)."""
    m = _mat_cache.get(key)
    if m is None:
        m = make_mat(name, rgb)
        _mat_cache[key] = m
    return m


def mat_coin():     return _mat('coin', 'smb_coin', (1.0, 0.84, 0.0))
def mat_debris():   return _mat('debris', 'smb_debris', (0.77, 0.42, 0.0))
def mat_spark():    return _mat('spark', 'smb_spark', (1.0, 0.95, 0.55))
def mat_fireball(): return _mat('fireball', 'fireball_orange', (0.98, 0.45, 0.05))
def mat_hard():     return _mat('hard', 'smb_hard_block', (0.48, 0.25, 0.05))
def mat_pipe():     return _mat('pipe', 'smb_pipe_green', (0.0, 0.62, 0.0))
def mat_treetop():  return _mat('treetop', 'smb_treetop_green', (0.16, 0.62, 0.18))   # canopy
def mat_treestem(): return _mat('treestem', 'smb_tree_stem', (0.55, 0.32, 0.10))      # trunk
def mat_castle():   return _mat('castle',  'smb_castle',     (0.60, 0.55, 0.50))      # gray stone
def mat_lava():     return _mat('lava',    'smb_lava',       (1.00, 0.27, 0.00))      # lava orange-red
def mat_axe():      return _mat('axe',     'smb_axe',        (1.00, 0.85, 0.00))      # gold axe


# ── Builders with material/dim deps (materials via getters above) ─────────────
def _make_coin_template():
    bm = _bmesh.new()
    _bmesh.ops.create_cube(bm, size=1.0)
    _bmesh.ops.scale(bm, vec=(COIN_X*2, COIN_T*2, COIN_Z*2), verts=bm.verts)
    mesh = bpy.data.meshes.new('coin_template')
    bm.to_mesh(mesh); bm.free()
    mesh.materials.append(mat_coin())
    for p in mesh.polygons:
        p.material_index = 0
    obj = bpy.data.objects.new('coin_template', mesh)
    obj.location = (-50.0, 0.0, 0.0)
    scene.collection.objects.link(obj)
    attach_schema(obj, 'gold')
    obj['wf_Template Object']      = 'True'
    obj['wf_Moves Between Rooms']  = 'True'
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 0.001
    obj['wf_Falling Acceleration'] = 12.0
    obj['wf_Max Air Speed']        = 50.0
    # NOTE: under Jolt, Surface Friction / Air Drag are DEAD (the old wheel-friction
    # path never runs). The live ground-friction knob for a doom-stick/MarbleHandler
    # actor is Running Deceleration (movebloc default 0.90 ≈ full stop per frame).
    # Set it to 0 so the coin keeps its generator-imparted +X drift on the ground
    # instead of freezing the instant it lands.
    obj['wf_Surface Friction']     = 0.0
    obj['wf_Horiz Air Drag']       = 0.0
    obj['wf_Vert Air Drag']        = 0.0
    obj['wf_Running Deceleration'] = 0.0    # frictionless ground → coin slides right
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Mesh Name']            = 'coin_template.iff'
    obj['wf_Script']               = COIN_SCRIPT
    return obj


def _make_debris_template():
    bm = _bmesh.new()
    _bmesh.ops.create_cube(bm, size=1.0)
    _bmesh.ops.scale(bm, vec=(DEBRIS_H*2, DEBRIS_H*2, DEBRIS_H*2), verts=bm.verts)
    mesh = bpy.data.meshes.new('debris_template')
    bm.to_mesh(mesh); bm.free()
    mesh.materials.append(mat_debris())
    for p in mesh.polygons:
        p.material_index = 0
    obj = bpy.data.objects.new('debris_template', mesh)
    obj.location = (-60.0, 0.0, 0.0)   # parking spot; generator overrides pos/vel on spawn
    scene.collection.objects.link(obj)
    attach_schema(obj, 'generator')
    obj['wf_Template Object']      = 'True'
    obj['wf_Moves Between Rooms']  = 'True'
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 0.001
    obj['wf_Falling Acceleration'] = 12.0
    obj['wf_Max Air Speed']        = 50.0
    obj['wf_Surface Friction']     = 0.0
    obj['wf_Horiz Air Drag']       = 0.0
    obj['wf_Vert Air Drag']        = 0.0
    obj['wf_Running Deceleration'] = 0.0
    obj['wf_Activation MailBox']   = 0      # mailbox[0] = always-false → never spawns anything
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Mesh Name']            = 'debris_template.iff'
    obj['wf_Script']               = DEBRIS_SCRIPT
    return obj


def _make_spark_template():
    bm = _bmesh.new()
    _bmesh.ops.create_cube(bm, size=1.0)
    _bmesh.ops.scale(bm, vec=(SPARK_H*2, SPARK_H*2, SPARK_H*2), verts=bm.verts)
    mesh = bpy.data.meshes.new('spark_template')
    bm.to_mesh(mesh); bm.free()
    mesh.materials.append(mat_spark())
    for p in mesh.polygons:
        p.material_index = 0
    obj = bpy.data.objects.new('spark_template', mesh)
    obj.location = (-72.0, 0.0, 0.0)   # parking spot; generator overrides pos/vel on spawn
    scene.collection.objects.link(obj)
    attach_schema(obj, 'generator')
    obj['wf_Template Object']      = 'True'
    obj['wf_Moves Between Rooms']  = 'True'
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 0.001
    obj['wf_Falling Acceleration'] = 12.0
    obj['wf_Max Air Speed']        = 50.0
    obj['wf_Surface Friction']     = 0.0
    obj['wf_Horiz Air Drag']       = 0.0
    obj['wf_Vert Air Drag']        = 0.0
    obj['wf_Running Deceleration'] = 0.0
    obj['wf_Activation MailBox']   = 0      # mailbox[0] = always-false → the template never spawns
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Mesh Name']            = 'spark_template.iff'
    obj['wf_Script']               = SPARK_SCRIPT
    return obj


def _make_fireball_template():
    bm = _bmesh.new()
    _bmesh.ops.create_cube(bm, size=1.0)
    _bmesh.ops.scale(bm, vec=(FB*2, FB*2, FB*2), verts=bm.verts)
    mesh = bpy.data.meshes.new('fireball_template')
    bm.to_mesh(mesh); bm.free()
    mesh.materials.append(mat_fireball())
    for p in mesh.polygons:
        p.material_index = 0
    obj = bpy.data.objects.new('fireball_template', mesh)
    obj.location = (-66.0, 0.0, 0.0)   # parking spot off-screen; generator velocity overrides on spawn
    scene.collection.objects.link(obj)
    attach_schema(obj, 'missile')
    obj['wf_Template Object']      = 'True'
    obj['wf_Moves Between Rooms']  = 'True'
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 0.001
    obj['wf_Falling Acceleration'] = 0.0     # flat travel (v1); a ground-bounce arc is polish
    obj['wf_Max Air Speed']        = 50.0    # don't let the speed cap zero the velocity (marble bug)
    obj['wf_Surface Friction']     = 0.0
    obj['wf_Horiz Air Drag']       = 0.0
    obj['wf_Vert Air Drag']        = 0.0
    obj['wf_Running Deceleration'] = 0.0     # frictionless: keeps its launch velocity
    obj['wf_Explosion Delay']      = 2.0     # built-in TTL despawn (SetPendingRemove)
    obj['wf_Explode On Impact']    = 'True'
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Mesh Name']            = 'fireball_template.iff'
    obj['wf_Script']               = FIREBALL_SCRIPT   # broadcast live position for enemy proximity-defeat
    return obj


def _make_powerup_template(name, mat, script, running_decel, park_x):
    bm = _bmesh.new()
    _bmesh.ops.create_cube(bm, size=1.0)
    _bmesh.ops.scale(bm, vec=(MUSH_X*2, MUSH_T*2, MUSH_Z*2), verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh); bm.free()
    mesh.materials.append(mat)
    for p in mesh.polygons:
        p.material_index = 0
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (park_x, 0.0, 0.0)   # parking spot; generator velocity overrides on spawn
    scene.collection.objects.link(obj)
    attach_schema(obj, 'gold')
    obj['wf_Template Object']      = 'True'
    obj['wf_Moves Between Rooms']  = 'True'
    obj['wf_Mobility']             = 'Physics'
    obj['wf_Mass']                 = 0.001
    obj['wf_Falling Acceleration'] = 12.0
    obj['wf_Max Air Speed']        = 50.0
    obj['wf_Surface Friction']     = 0.0
    obj['wf_Horiz Air Drag']       = 0.0
    obj['wf_Vert Air Drag']        = 0.0
    obj['wf_Running Deceleration'] = running_decel
    obj['wf_Gold Value']           = 0
    obj['wf_Model Type']           = 'Mesh'
    obj['wf_Visibility Mailbox']   = 1
    obj['wf_Mesh Name']            = name + '.iff'
    obj['wf_Script']               = script
    return obj

# Power-up dispensing block: a one-shot Generator (bump from below -> throw one
# collectible -> latch tan), using POWERUP_BLOCK_SCRIPT.


def _add_pyramid(name_base, base_col, steps=4):
    """Left-to-right ascending staircase: col 0 = 1T tall, col n-1 = n*T tall."""
    for _s in range(steps):
        add_statplat(f'{name_base}_{_s}',
                     (base_col + _s)*T - BSIZE, -GROUND_Y, GROUND_TOP_Z,
                     (base_col + _s)*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + (_s + 1)*T,
                     mat_hard())


def _add_staircase(name_base, base_col, steps=8):
    """Left-to-right ascending staircase: col 0 = 1*T tall, col n-1 = steps*T tall."""
    for _s in range(steps):
        _h = (_s + 1) * T
        add_statplat(f'{name_base}_{_s}',
                     (base_col + _s)*T - BSIZE, -GROUND_Y, GROUND_TOP_Z,
                     (base_col + _s)*T + BSIZE,  GROUND_Y, GROUND_TOP_Z + _h,
                     mat_hard())


def _add_pipe(name, col, height_tiles, width_tiles=2):
    """Decorative green pipe statplat. col = centre column; width 2 tiles (X col±1)."""
    add_statplat(name,
                 col*T - width_tiles/2*T, -GROUND_Y, GROUND_TOP_Z,
                 col*T + width_tiles/2*T,  GROUND_Y, GROUND_TOP_Z + height_tiles*T,
                 mat_pipe())


def add_treetop(name, col, top_z, width_tiles=3):
    """A SMB-3-style tree-top (mushroom) island: a green canopy slab you stand on plus a
    narrow brown trunk hanging beneath it. `col` = centre column, `top_z` = canopy top Z.
    The canopy is the collision/standing surface; the stem is decorative (well below it).
    All canopies share one green datablock, all stems one brown datablock (add_statplat
    keys the shared mesh on the material)."""
    cx   = col * T
    half = width_tiles * T / 2.0
    add_statplat(f'{name}_canopy',
                 cx - half, -GROUND_Y, top_z - 0.5*T,
                 cx + half,  GROUND_Y, top_z,            mat_treetop())
    add_statplat(f'{name}_stem',
                 cx - 0.4*T, -0.6*GROUND_Y, top_z - 0.5*T - 2.0*T,
                 cx + 0.4*T,  0.6*GROUND_Y, top_z - 0.5*T,  mat_treestem())


# ── Texture paths for the textured-box builders (set by the level after it
#    generates the per-level TGAs via _make_brick_tga / _make_qblock_tga) ──────
_brick_tex = None
_qblock_tex = None


def set_textures(brick=None, qblock=None):
    global _brick_tex, _qblock_tex
    if brick is not None: _brick_tex = brick
    if qblock is not None: _qblock_tex = qblock


def _add_brick(name, x, z=BLOCK_Z):
    blk = _add_textured_box(name,
                            x - BSIZE, -BSIZE, z - BSIZE,
                            x + BSIZE,  BSIZE, z + BSIZE,
                            _brick_tex)
    attach_schema(blk, 'generator')
    blk['wf_Mobility']           = 'Anchored'
    blk['wf_Model Type']         = 'Mesh'
    blk['wf_Visibility Mailbox'] = 1
    blk['wf_Number Of Local Mailboxes'] = 16   # 2000..2015 (qblock slots + brick timers)
    blk['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
    blk['wf_Object To Throw']    = 'debris_template'
    blk['wf_Generation Rate']    = 10.0   # 10/s is the generator.oas max; ~4 fragments over the 0.4 s burst
    blk['wf_Object X Velocity']  = 0.0
    blk['wf_Object Y Velocity']  = 0.0    # OAS default is 1.0 — zero it or debris drifts into +Y
    blk['wf_Object Z Velocity']  = 7.0    # pop up; fragments fall back through the floor
    # NB: no Random Displacement — the engine's Scalar::Random() asserts (RangeCheck
    # integer-casts a fractional Scalar). The debris fan is done deterministically in
    # DEBRIS_SCRIPT via the fragment's actor index instead.
    blk['wf_Script']             = BRICK_SCRIPT
    return blk

# Faithful W1-1 brick layout (docs/smb-level-layouts.md §1-1):
#   Cols 20, 22, 24 — cluster flanking the coin ? blocks at cols 21, 23
#   Cols 91-98     — extended overhead brick row (8 wide)
#   Cols 108, 110  — hi-row bricks flanking the flower ? block at col 109 (row 6)


def _make_powerup_block(name, x, throw, vx, z=None):
    if z is None:
        z = BLOCK_Z
    b = _add_textured_box(name, x - BSIZE, -BSIZE, z - BSIZE,
                                x + BSIZE,  BSIZE, z + BSIZE, _qblock_tex)
    attach_schema(b, 'generator')
    b['wf_Mobility']           = 'Anchored'
    b['wf_Model Type']         = 'Mesh'
    b['wf_Visibility Mailbox'] = 1
    b['wf_Number Of Local Mailboxes'] = 13   # 2000..2012, same as the qblocks
    b['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
    b['wf_Object To Throw']    = throw
    b['wf_Generation Rate']    = 10.0
    b['wf_Object X Velocity']  = vx
    b['wf_Object Y Velocity']  = 0.0
    b['wf_Object Z Velocity']  = 6.0
    b['wf_Script']             = POWERUP_BLOCK_SCRIPT
    return b

# Mushroom-or-flower: ONE self-determining power-up. A Generator's Object To Throw is
# fixed at load (generator.cc:84), so rather than two templates the single
# `powerup_template` reads SMB_MARIO_STATE LIVE and BECOMES the right item: Small (0)
# stays the red mushroom that slides; Super+ (>0) repaints orange and forces stationary
# (the flower). On pickup it raises the signal for Mario's current tier (mushroom ->
# Super, flower -> Fire) = the existing player handlers. One-shot blocks mean Mario's
# tier can't change between bump and catch, so the live read always matches the item.


def _add_qblock(name, x, z=BLOCK_Z):
    """Coin ?-block: a Generator that throws coin_template on bump-from-below (4 s window)."""
    blk = _add_textured_box(name, x - BSIZE, -BSIZE, z - BSIZE,
                                  x + BSIZE,  BSIZE, z + BSIZE, _qblock_tex)
    attach_schema(blk, 'generator')
    blk['wf_Mobility']           = 'Anchored'
    blk['wf_Model Type']         = 'Mesh'
    blk['wf_Visibility Mailbox'] = 1
    blk['wf_Number Of Local Mailboxes'] = 13
    blk['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE
    blk['wf_Object To Throw']    = 'coin_template'
    blk['wf_Generation Rate']    = 10.0
    blk['wf_Object X Velocity']  = 1.5
    blk['wf_Object Y Velocity']  = 0.0
    blk['wf_Object Z Velocity']  = 6.0
    blk['wf_Script']             = QBLOCK_SCRIPT
    return blk


# ── Parameterized actor-script generators (#1 batch C) ────────────────────────
def director_script(cfg):
    """SMB scroll + countdown + celebration-sequencer Director script."""
    FLAGPOLE_X = cfg['FLAGPOLE_X']
    TIMER_UNITS = cfg['TIMER_UNITS']
    TIMER_REAL_SECONDS = cfg['TIMER_REAL_SECONDS']
    _cam_x_max = FLAGPOLE_X - 12.0
    return (
        "\\ wf\n"
        "INDEXOF_SMB_MAX_CAM_X read-mailbox not if "
        "4.5 INDEXOF_SMB_MAX_CAM_X write-mailbox then\n"
        "INDEXOF_SMB_PLAYER_X read-mailbox 1.5 +\n"
        "dup INDEXOF_SMB_MAX_CAM_X read-mailbox -\n"
        "1.5 <\n"
        "if drop INDEXOF_SMB_MAX_CAM_X read-mailbox\n"
        "else 1.5 - "
        "dup 9.0 < if drop 9.0 then "
        f"dup {_cam_x_max:.1f} > if drop {_cam_x_max:.1f} then "
        "dup INDEXOF_SMB_MAX_CAM_X write-mailbox\n"
        "then\n"
        "INDEXOF_SMB_TARGET_CAM_X write-mailbox\n"
        # ── level countdown timer ───────────────────────────────────────────
        # display = TIMER_UNITS - elapsed*RATE (clamped >=0) -> HUD_TIMER slot.
        # SMB_TIMER_START anchors the current life; reaching 0 = "TIME UP" fires
        # SMB_PLAYER_HURT (Mario dies, loses a life via the player respawn) and
        # restarts the clock. The player respawn also re-anchors it on every death.
        # ── celebration sequencer (gates on SMB_CELEBRATE) OR normal countdown ──
        # On SMB_CELEBRATE: seed START once, then phase off elapsed = TIME-START.
        #   phase D (elapsed>1.5): drain HUD_TIMER toward 0 (visual; the player already
        #     credited HUD_TIMER*50 to the score on the rising edge).
        #   phase E (elapsed>=3.5): fire END_OF_LEVEL -> meta-loop loads the next level.
        # While celebrating the normal countdown is suspended (it also owns HUD_TIMER).
        "INDEXOF_SMB_CELEBRATE read-mailbox if\n"
        "  INDEXOF_SMB_CELEBRATE_START read-mailbox not if "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START write-mailbox then\n"
        # Frame the flag + the castle to its right (overrides the scroll target, which
        # clamps at the pole and would leave the castle off the right edge).
        f"  {FLAGPOLE_X:.1f} INDEXOF_SMB_TARGET_CAM_X write-mailbox\n"
        "  INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox -\n"   # elapsed
        "  dup 1.5 > if "                                       # phase D: drain the timer
        "INDEXOF_HUD_TIMER read-mailbox 250.0 INDEXOF_DELTA_TIME read-mailbox * - "
        "dup 0 < if drop 0 then INDEXOF_HUD_TIMER write-mailbox then\n"
        "  4.5 > if 1 INDEXOF_END_OF_LEVEL write-mailbox then\n"  # phase G: finale (after the last firework burst ~4.35)
        "else\n"
        "  INDEXOF_SMB_TIMER_START read-mailbox not if "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox then\n"
        f"  {TIMER_UNITS} INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START read-mailbox - "
        f"{TIMER_UNITS / TIMER_REAL_SECONDS:.5f} * -\n"        # 400 - elapsed*RATE
        "  dup 0 <= if "
        "1 INDEXOF_SMB_PLAYER_HURT write-mailbox "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox "
        "drop 0 then\n"                                        # clamp display to 0
        "  INDEXOF_HUD_TIMER write-mailbox\n"
        "then\n"
    )


def player_script(cfg):
    """The full SMB player tick: input, stomp/hurt, power-ups, fireball, the
    level-box confinement, the flagpole celebration, and the coin-room pickups."""
    CR_ENTRY_X = cfg['CR_ENTRY_X']
    CR_ENTRY_Z = cfg['CR_ENTRY_Z']
    FIRE_TINT = cfg['FIRE_TINT']
    FLAGPOLE_X = cfg['FLAGPOLE_X']
    GROUND_X0 = cfg['GROUND_X0']
    GROUND_X1 = cfg['GROUND_X1']
    GROUND_Y = cfg['GROUND_Y']
    MARIO_DEFAULT_TINT = cfg['MARIO_DEFAULT_TINT']
    MARIO_SPAWN_X = cfg['MARIO_SPAWN_X']
    MARIO_SPAWN_Z = cfg['MARIO_SPAWN_Z']
    STAR_FLASH_A = cfg['STAR_FLASH_A']
    STAR_FLASH_B = cfg['STAR_FLASH_B']
    return (
        "\\ wf\n"
        "1 INDEXOF_SMB_MARIO_VIS write-mailbox\n"   # default visible; celebration hides Mario in the castle
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox "
        "dup 16384 & 256 / over 8192 & 64 / | | "
        "INDEXOF_INPUT write-mailbox\n"
        "INDEXOF_X_POS read-mailbox INDEXOF_SMB_PLAYER_X write-mailbox\n"
        "INDEXOF_Z_POS read-mailbox INDEXOF_SMB_PLAYER_Z write-mailbox\n"   # enemies use proximity
        # ── Confine the player to the level box (ends + sides) ───────────────
        # Fixed walls at the level's ENDS (X: left edge GROUND_X0, right edge GROUND_X1)
        # and SIDES (Y: the ground half-depth ±GROUND_Y). Z stays free so pits + tubes/
        # warps still work. The X clamp is surface-only (z > -8; the coin room has its own
        # walls + X range). Without this you run/jump off the ends or sides of the level.
        "INDEXOF_Z_POS read-mailbox -8.0 > if\n"
        f"  INDEXOF_X_POS read-mailbox {GROUND_X0:.2f} < if {GROUND_X0:.2f} INDEXOF_X_POS write-mailbox 0 INDEXOF_XSPEED write-mailbox then\n"
        f"  INDEXOF_X_POS read-mailbox {GROUND_X1:.2f} > if {GROUND_X1:.2f} INDEXOF_X_POS write-mailbox 0 INDEXOF_XSPEED write-mailbox then\n"
        "then\n"
        f"INDEXOF_Y_POS read-mailbox {-GROUND_Y:.2f} < if {-GROUND_Y:.2f} INDEXOF_Y_POS write-mailbox 0 INDEXOF_YSPEED write-mailbox then\n"
        f"INDEXOF_Y_POS read-mailbox {GROUND_Y:.2f} > if {GROUND_Y:.2f} INDEXOF_Y_POS write-mailbox 0 INDEXOF_YSPEED write-mailbox then\n"
        # seed lives once (guarded so game-over at LIVES=0 never re-seeds)
        "INDEXOF_SMB_LIVES_INIT read-mailbox not if "
        "3 INDEXOF_LIVES write-mailbox 1 INDEXOF_SMB_LIVES_INIT write-mailbox then\n"
        # bounce up when we stomped an enemy this frame; award 100 pts
        "INDEXOF_SMB_STOMP read-mailbox 0<> if\n"
        "  8.0 INDEXOF_ZSPEED write-mailbox\n"
        "  INDEXOF_SMB_SCORE read-mailbox 100 + INDEXOF_SMB_SCORE write-mailbox\n"
        "  0 INDEXOF_SMB_STOMP write-mailbox\n"
        "then\n"
        # Super Mushroom pickup -> grow to Super. Small(0)->Super(1) only; already-Super
        # stays Super. Visual scale only (hitbox-resize deferred); the feet-origin mesh
        # scales up cleanly from the floor. `not` = state == 0.
        "INDEXOF_SMB_MUSHROOM_PICKUP read-mailbox 0<> if\n"
        "  INDEXOF_SMB_MARIO_STATE read-mailbox not if\n"
        "    1 INDEXOF_SMB_MARIO_STATE write-mailbox\n"
        "    1.25 INDEXOF_X_SCALE write-mailbox 1.25 INDEXOF_Y_SCALE write-mailbox "
        "1.9 INDEXOF_Z_SCALE write-mailbox\n"
        "  then\n"
        "  0 INDEXOF_SMB_MUSHROOM_PICKUP write-mailbox\n"
        "then\n"
        # Fire Flower -> Fire (state 2). From Small OR Super, jump to Fire + super-size
        # (faithful: a flower picked up small makes you big + fire directly). >=Fire stays.
        "INDEXOF_SMB_FIREFLOWER_PICKUP read-mailbox 0<> if\n"
        "  INDEXOF_SMB_MARIO_STATE read-mailbox 2 < if\n"
        "    2 INDEXOF_SMB_MARIO_STATE write-mailbox\n"
        "    1.25 INDEXOF_X_SCALE write-mailbox 1.25 INDEXOF_Y_SCALE write-mailbox "
        "1.9 INDEXOF_Z_SCALE write-mailbox\n"
        f"    0x{FIRE_TINT:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
        "  then\n"
        "  0 INDEXOF_SMB_FIREFLOWER_PICKUP write-mailbox\n"
        "then\n"
        # Star -> ~10 s invincibility. Orthogonal to size: do NOT touch state/scale.
        # Reuse the existing INVULN gate for damage-immunity (no edit to the hurt logic);
        # SMB_STAR_UNTIL drives the enemy defeat-on-touch + the flicker.
        "INDEXOF_SMB_STAR_PICKUP read-mailbox 0<> if\n"
        "  INDEXOF_TIME read-mailbox 10.0 + INDEXOF_SMB_STAR_UNTIL write-mailbox\n"
        "  INDEXOF_TIME read-mailbox 10.0 + INDEXOF_SMB_INVULN_UNTIL write-mailbox\n"
        "  0 INDEXOF_SMB_STAR_PICKUP write-mailbox\n"
        "then\n"
        # Flicker Mario's tint while the Star window is open; restore once when it closes.
        # `%` casts to int in zForth; (TIME*8)%2 -> 0/1 toggle.
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_STAR_UNTIL read-mailbox < if\n"
        f"  INDEXOF_TIME read-mailbox 8.0 * 2 % if 0x{STAR_FLASH_A:06X} else 0x{STAR_FLASH_B:06X} then "
        "INDEXOF_FACE_COLOR_TOP write-mailbox\n"
        "  1 INDEXOF_SMB_STAR_FLICKER_LATCH write-mailbox\n"
        "else\n"
        "  INDEXOF_SMB_STAR_FLICKER_LATCH read-mailbox 0<> if\n"
        f"    INDEXOF_SMB_MARIO_STATE read-mailbox 2 = if 0x{FIRE_TINT:06X} else 0x{MARIO_DEFAULT_TINT:06X} then "
        "INDEXOF_FACE_COLOR_TOP write-mailbox\n"
        "    0 INDEXOF_SMB_STAR_FLICKER_LATCH write-mailbox\n"
        "  then\n"
        "then\n"
        # enemy side-hit -> if Super, power down to Small (no life lost); if Small, lose
        # a life + respawn at spawn. Both gated on i-frames (unless still invulnerable).
        "INDEXOF_SMB_PLAYER_HURT read-mailbox 0<> if\n"
        "  INDEXOF_TIME read-mailbox INDEXOF_SMB_INVULN_UNTIL read-mailbox > if\n"
        "    INDEXOF_SMB_MARIO_STATE read-mailbox 0 > if\n"
        # Super (or Fire) -> drop one power level; keep the life, brief i-frames.
        # Scale-aware: Fire->Super stays big (1.25/1.9); Super->Small shrinks to 1.0.
        # `dup` keeps newstate on the stack to branch the scale; clear the fire tint either way.
        "      INDEXOF_SMB_MARIO_STATE read-mailbox 1 - dup INDEXOF_SMB_MARIO_STATE write-mailbox\n"
        "      0 > if\n"
        "        1.25 INDEXOF_X_SCALE write-mailbox 1.25 INDEXOF_Y_SCALE write-mailbox "
        "1.9 INDEXOF_Z_SCALE write-mailbox\n"
        "      else\n"
        "        1.0 INDEXOF_X_SCALE write-mailbox 1.0 INDEXOF_Y_SCALE write-mailbox "
        "1.0 INDEXOF_Z_SCALE write-mailbox\n"
        "      then\n"
        f"      0x{MARIO_DEFAULT_TINT:06X} INDEXOF_FACE_COLOR_TOP write-mailbox\n"
        "      INDEXOF_TIME read-mailbox 1.5 + INDEXOF_SMB_INVULN_UNTIL write-mailbox\n"
        "    else\n"
        # Small -> die: lose a life + respawn at spawn.
        "      INDEXOF_LIVES read-mailbox 1 - INDEXOF_LIVES write-mailbox\n"
        f"      {MARIO_SPAWN_X} INDEXOF_X_POS write-mailbox\n"
        "      0 INDEXOF_Y_POS write-mailbox\n"
        f"      {MARIO_SPAWN_Z} INDEXOF_Z_POS write-mailbox\n"
        "      0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox "
        "0 INDEXOF_ZSPEED write-mailbox\n"
        # restart the countdown for the new life (any death resets the timer, SMB-faithful)
        "      INDEXOF_TIME read-mailbox INDEXOF_SMB_TIMER_START write-mailbox\n"
        "      INDEXOF_TIME read-mailbox 2.0 + INDEXOF_SMB_INVULN_UNTIL write-mailbox\n"
        "      INDEXOF_LIVES read-mailbox 1 < if 1 INDEXOF_END_OF_LEVEL write-mailbox then\n"
        "    then\n"
        "  then\n"
        "  0 INDEXOF_SMB_PLAYER_HURT write-mailbox\n"
        "then\n"
        # pipe warp: standing on a pipe mouth (entry ActBox set SMB_AT_PIPE) AND
        # pressing Down -> drop into the underground coin room. Reuses the proven
        # respawn teleport (X/Y/Z_POS write + zero velocity); 4096 = EJ_BUTTONF_DOWN.
        "INDEXOF_SMB_AT_PIPE read-mailbox 0<> if\n"
        "  INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox 4096 & 0<> if\n"
        f"    {CR_ENTRY_X} INDEXOF_X_POS write-mailbox\n"
        "    0 INDEXOF_Y_POS write-mailbox\n"
        f"    {CR_ENTRY_Z} INDEXOF_Z_POS write-mailbox\n"
        "    0 INDEXOF_XSPEED write-mailbox 0 INDEXOF_YSPEED write-mailbox "
        "0 INDEXOF_ZSPEED write-mailbox\n"
        "  then\n"
        "then\n"
        # 1UP mushroom pickup: raise +1 life, clear signal
        "INDEXOF_SMB_ONEUP_PICKUP read-mailbox 0<> if\n"
        "  INDEXOF_LIVES read-mailbox 1 + INDEXOF_LIVES write-mailbox\n"
        "  0 INDEXOF_SMB_ONEUP_PICKUP write-mailbox\n"
        "then\n"
        # Flagpole celebration — fires on SMB_CELEBRATE's rising edge (the flag ActBox
        # sets it). One-shot height+time bonus, then pin Mario at the pole for the show.
        # Height tiers: Z≥9→5000, ≥6→2000, ≥4.5→800, ≥3→400, ≥1.5→200, else→100.
        # Time bonus: HUD_TIMER remaining × 50 (read once, before the Director drains it —
        # the player runs in the main loop, the Director runs last).
        # EOL_LATCH guards the credit so it fires once across the multi-second celebration.
        "INDEXOF_SMB_CELEBRATE read-mailbox 0<> if\n"
        # Seed SMB_CELEBRATE_START here (the player runs before the flag enemies), so the
        # flag/castle-flag scripts read a valid START the same frame and animate from
        # elapsed≈0 instead of snapping to the end (the Director also seeds it, but runs
        # last, so on frame 1 the flags would otherwise see START=0 → elapsed=TIME → frac=1).
        "  INDEXOF_SMB_CELEBRATE_START read-mailbox not if "
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START write-mailbox then\n"
        "  INDEXOF_SMB_EOL_LATCH read-mailbox not if\n"
        "    1 INDEXOF_SMB_EOL_LATCH write-mailbox\n"
        "    INDEXOF_Z_POS read-mailbox\n"
        "    dup 9.0 > if drop 5000\n"
        "    else dup 6.0 > if drop 2000\n"
        "    else dup 4.5 > if drop 800\n"
        "    else dup 3.0 > if drop 400\n"
        "    else dup 1.5 > if drop 200\n"
        "    else drop 100\n"
        "    then then then then then\n"
        "    INDEXOF_SMB_SCORE read-mailbox + INDEXOF_SMB_SCORE write-mailbox\n"
        "    INDEXOF_HUD_TIMER read-mailbox 50 *\n"
        "    INDEXOF_SMB_SCORE read-mailbox + INDEXOF_SMB_SCORE write-mailbox\n"
        # Faithful firework count: last digit of the remaining timer, but only 1/3/6 give
        # fireworks (else none). Latched here, once, BEFORE the Director drains HUD_TIMER.
        "    INDEXOF_HUD_TIMER read-mailbox 10 %\n"   # `%` casts to int → last digit 0..9
        "    dup 1 = if drop 1 else dup 3 = if drop 3 else dup 6 = if drop 6 else drop 0 then then then\n"
        "    INDEXOF_SMB_FIREWORK_COUNT write-mailbox\n"
        "  then\n"
        # Walk Mario into the castle, then hide him (the SMB "enters the castle door" beat):
        #   elapsed < 0.9  → hold at the pole (clamp overshoot; the flag is sliding);
        #   0.9 – 1.6      → walk right FLAGPOLE_X → FLAGPOLE_X+2 (the castle door), visible;
        #   ≥ 1.6          → entered → hide (SMB_MARIO_VIS=0) + hold at the door.
        # Writing X_POS each frame overrides input; the 2 m walk is gentle so the bungee tracks.
        "  INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox -\n"   # elapsed
        f"  dup 0.9 < if drop INDEXOF_X_POS read-mailbox {FLAGPOLE_X:.1f} > if "
        f"{FLAGPOLE_X:.1f} INDEXOF_X_POS write-mailbox then\n"
        "  else dup 1.6 < if "
        f"0.9 - 1.42857 * dup 1.0 > if drop 1.0 then 2.0 * {FLAGPOLE_X:.1f} + INDEXOF_X_POS write-mailbox\n"
        f"  else drop 0 INDEXOF_SMB_MARIO_VIS write-mailbox {FLAGPOLE_X + 2.0:.1f} INDEXOF_X_POS write-mailbox\n"
        "  then then\n"
        "then\n"
        # coin-room coins: seed visible once, then proximity pickup. The Z test
        # (player z near -46) disambiguates the coin room from the surface, where
        # the same X range exists but z ~ 1.5. dup* = squared distance (no abs).
        # 19 coins in 3 rows — faithful W1-1 layout (SMBDIS.ASM L_UndergroundArea3).
        # Pickup is X-only per column; three stacked coins at the same column are
        # all collected in the same pass (by design — no per-height check needed).
        "INDEXOF_SMB_COIN_INIT read-mailbox not if\n"
        "  1 INDEXOF_SMB_COIN_0 write-mailbox 1 INDEXOF_SMB_COIN_1 write-mailbox "
        "1 INDEXOF_SMB_COIN_2 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_3 write-mailbox 1 INDEXOF_SMB_COIN_4 write-mailbox "
        "1 INDEXOF_SMB_COIN_5 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_6 write-mailbox 1 INDEXOF_SMB_COIN_7 write-mailbox "
        "1 INDEXOF_SMB_COIN_8 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_9 write-mailbox 1 INDEXOF_SMB_COIN_10 write-mailbox "
        "1 INDEXOF_SMB_COIN_11 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_12 write-mailbox 1 INDEXOF_SMB_COIN_13 write-mailbox "
        "1 INDEXOF_SMB_COIN_14 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_15 write-mailbox 1 INDEXOF_SMB_COIN_16 write-mailbox "
        "1 INDEXOF_SMB_COIN_17 write-mailbox 1 INDEXOF_SMB_COIN_18 write-mailbox\n"
        "  1 INDEXOF_SMB_COIN_INIT write-mailbox\n"
        "then\n"
        # coin-room pickup: TRUE XZ contact (dx^2+dz^2 < 1.0, == gold.cc
        # kGoldPickupRadius^2) against each coin's real row Z. No underground-band
        # gate -- the per-coin Z test subsumes it (surface is z~1.5, far from any
        # coin row at z~-35..-41). Player poke (a coin can't write the player's GOLD).
        "INDEXOF_SMB_COIN_0 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 6.75 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_0 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_1 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 8.25 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_1 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_2 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 9.75 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_2 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_3 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 11.25 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_3 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_4 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 12.75 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_4 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_5 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 14.25 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_5 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_6 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 15.75 - dup * INDEXOF_Z_POS read-mailbox -41.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_6 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_7 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 6.75 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_7 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_8 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 8.25 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_8 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_9 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 9.75 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_9 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_10 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 11.25 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_10 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_11 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 12.75 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_11 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_12 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 14.25 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_12 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_13 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 15.75 - dup * INDEXOF_Z_POS read-mailbox -38.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_13 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_14 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 8.25 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_14 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_15 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 9.75 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_15 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_16 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 11.25 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_16 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_17 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 12.75 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_17 write-mailbox\n"
        "  then then\n"
        "INDEXOF_SMB_COIN_18 read-mailbox 0<> if\n"
        "  INDEXOF_X_POS read-mailbox 14.25 - dup * INDEXOF_Z_POS read-mailbox -35.25 - dup * + 1.0 < if\n"
        "    INDEXOF_GOLD read-mailbox 1 + INDEXOF_GOLD write-mailbox 0 INDEXOF_SMB_COIN_18 write-mailbox\n"
        "  then then\n"
        # Coin delta scoring + 100-coin 1UP.
        # delta = GOLD − LAST_GOLD catches both gold.cc coin pickups and coin-room
        # script pickups. Score 200 pts per coin. At each 100-coin boundary (GOLD
        # crosses a multiple of 100, edge-detected via LAST_GOLD mod), grant +1 life.
        "INDEXOF_GOLD read-mailbox INDEXOF_SMB_LAST_GOLD read-mailbox -\n"  # delta
        "dup 0 > if\n"
        "  INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_SMB_POPUP_X write-mailbox\n"
        "  INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_SMB_POPUP_Z write-mailbox\n"
        "  1 INDEXOF_SMB_POPUP_TRIGGER write-mailbox\n"
        "  200 * INDEXOF_SMB_SCORE read-mailbox + INDEXOF_SMB_SCORE write-mailbox\n"
        "  INDEXOF_GOLD read-mailbox 100 % not if\n"            # GOLD now a multiple of 100
        "    INDEXOF_SMB_LAST_GOLD read-mailbox 100 % 0<> if\n"  # LAST_GOLD was not
        "      INDEXOF_GOLD read-mailbox 0 > if\n"               # skip the initial 0
        "        INDEXOF_LIVES read-mailbox 1 + INDEXOF_LIVES write-mailbox\n"
        "      then\n"
        "    then\n"
        "  then\n"
        "else\n"
        "  drop\n"
        "then\n"
        "INDEXOF_GOLD read-mailbox INDEXOF_SMB_LAST_GOLD write-mailbox\n"
        # HUD score: display the accumulated SMB_SCORE (coins×200 + bonus points).
        "INDEXOF_SMB_SCORE read-mailbox INDEXOF_HUD_SCORE write-mailbox\n"
        # ── Fire Mario fireball ───────────────────────────────────────────────
        # docs/plans/2026-05-26-fire-mario-fireball-pooled-generator.md
        # Facing latch: RIGHT -> +1, LEFT -> -1, else keep (seed +1 while still 0).
        "INDEXOF_SMB_MARIO_FACING read-mailbox not if "
        "1 INDEXOF_SMB_MARIO_FACING write-mailbox then\n"
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox JOYSTICK_BUTTON_RIGHT & 0<> if "
        "1 INDEXOF_SMB_MARIO_FACING write-mailbox then\n"
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox JOYSTICK_BUTTON_LEFT & 0<> if "
        "-1 INDEXOF_SMB_MARIO_FACING write-mailbox then\n"
        # Publish the spawn point each tick so the generators self-park on it:
        #  X: own X + facing*1.8 — well in front, so the missile's box reliably clears Mario's
        #     body. (1.2 was marginal: Mario's slow +X idle drift intermittently closed the gap,
        #     so the spawn pre-check rejected the fireball inside Mario ~2/3 of the time.)
        #  Z: own Z + 0.8 (waist height) — clears the ground slab (top at 0), else the
        #     spawn pre-check rejects the missile for touching the floor; also where a
        #     fireball should come from. (Mario's origin is at his feet, Z_POS ~ 0 at rest.)
        "INDEXOF_X_POS read-mailbox INDEXOF_SMB_MARIO_FACING read-mailbox 1.8 * + "
        "INDEXOF_SMB_FIREBALL_X write-mailbox\n"
        "INDEXOF_Y_POS read-mailbox INDEXOF_SMB_FIREBALL_Y write-mailbox\n"
        "INDEXOF_Z_POS read-mailbox 0.8 + INDEXOF_SMB_FIREBALL_Z write-mailbox\n"
        # Clear both activation pulses every tick; set one only on the firing tick so
        # the Generator sees a one-tick pulse and throws exactly one fireball.
        "0 INDEXOF_SMB_FIREBALL_FIRE_R write-mailbox "
        "0 INDEXOF_SMB_FIREBALL_FIRE_L write-mailbox\n"
        # Fire: Fire state (2) + B held + not already latched + cooldown elapsed.
        "INDEXOF_SMB_MARIO_STATE read-mailbox 2 = if\n"
        "  INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox JOYSTICK_BUTTON_B & 0<> if\n"
        "    INDEXOF_SMB_FIRE_LATCH read-mailbox not if\n"
        "      INDEXOF_TIME read-mailbox INDEXOF_SMB_FIRE_COOLDOWN read-mailbox > if\n"
        "        INDEXOF_SMB_MARIO_FACING read-mailbox 0 > if\n"
        "          1 INDEXOF_SMB_FIREBALL_FIRE_R write-mailbox\n"
        "        else\n"
        "          1 INDEXOF_SMB_FIREBALL_FIRE_L write-mailbox\n"
        "        then\n"
        "        1 INDEXOF_SMB_FIRE_LATCH write-mailbox\n"
        "        INDEXOF_TIME read-mailbox 0.5 + INDEXOF_SMB_FIRE_COOLDOWN write-mailbox\n"
        "      then\n"
        "    then\n"
        "  then\n"
        "then\n"
        # Release the latch when B is up -> one fireball per distinct press.
        "INDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox JOYSTICK_BUTTON_B & not if "
        "0 INDEXOF_SMB_FIRE_LATCH write-mailbox then\n"
    )

SMB_FIREWORK = [1865, 1866, 1867, 1868, 1869, 1870]  # firework-generator activation mailboxes


def celebration(cfg):
    """Flagpole + castle + rising flags + radial fireworks + end-of-level/advance
    triggers. cfg: FLAGPOLE_X, NEXT_LEVEL_INDEX."""
    FLAGPOLE_X = cfg['FLAGPOLE_X']
    # ── 10. Flagpole ──────────────────────────────────────────────────────────────
    mat_pole = make_mat('smb_pole', (0.72, 0.72, 0.72))
    mat_flag = make_mat('smb_flag', (0.10, 0.65, 0.16))

    POLE_HEIGHT = 10 * T
    POLE_RADIUS = 0.18 * T   # 0.27 m — a real round pole, not a thin sliver from the side cam

    # Pole — a proper round cylinder (16 sides) from ground to 10 tiles high
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16, radius=POLE_RADIUS, depth=POLE_HEIGHT,
        location=(FLAGPOLE_X, 0, POLE_HEIGHT / 2))
    pole_obj = bpy.context.object
    pole_obj.name      = 'flagpole_pole'
    pole_obj.data.name = 'flagpole_pole'
    pole_obj.data.materials.clear()
    pole_obj.data.materials.append(mat_pole)
    attach_schema(pole_obj, 'statplat')
    pole_obj['wf_Visibility Mailbox'] = 1
    pole_obj['wf_Model Type'] = 'Mesh'

    # Flag — flat plane near the pole top. A scriptable Anchored 'enemy' (statplats can't
    # tick a script) so it SLIDES DOWN the pole during the celebration: phase A
    # (elapsed 0–0.5 s) lerps its Z from the top to the base. Before SMB_CELEBRATE it sits
    # at the authored top. Anchored = no Jolt body, no collision; the script owns its Z.
    FLAG_TOP_Z  = POLE_HEIGHT - T        # 13.5 — authored start (near pole top)
    FLAG_BASE_Z = T * 0.7                # ~1.05 — slide target (pole base, the "grab")
    # Thin VERTICAL slab (a flat plane lies in XY → edge-on/invisible to the side camera).
    # Shared unit-box mesh + size-as-scale (position-independent, dedups game-wide); half-extents
    # (0.5T, 0.03, 0.4T) about (FLAGPOLE_X - T, 0, FLAG_TOP_Z). Runtime raise drives Z_POS.
    flag_obj = add_box('flagpole_flag',
                       (FLAGPOLE_X - T) - 0.5 * T, -0.03, FLAG_TOP_Z - 0.4 * T,
                       (FLAGPOLE_X - T) + 0.5 * T,  0.03, FLAG_TOP_Z + 0.4 * T,
                       mat_flag)
    attach_schema(flag_obj, 'enemy')
    flag_obj['wf_Mobility'] = 'Anchored'
    flag_obj['wf_Model Type'] = 'Mesh'
    flag_obj['wf_Visibility Mailbox'] = 1
    flag_obj['wf_Script'] = (
        "\\ wf\n"
        "INDEXOF_SMB_CELEBRATE read-mailbox if\n"
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox - 1.1 *\n"  # frac = elapsed/0.9
        "dup 1.0 > if drop 1.0 then\n"
        f"{FLAG_TOP_Z - FLAG_BASE_Z:.2f} * {FLAG_TOP_Z:.2f} swap - INDEXOF_Z_POS write-mailbox\n"  # Z = top - span*frac
        "then\n"
    )

    # ── 10a. Castle + rising castle flag + door + fireworks (celebration) ─────────
    # A small stone castle just past the flagpole. Mario walks into its door and vanishes
    # (Player phases B/D); its rooftop flag RAISES (phase C, 0.8–1.4 s — the "flag which
    # raises" beat); then 3 fireworks pop above it (phase F, staggered 2.4/2.9/3.4 s). The
    # flags + fireworks are scriptable Anchored 'enemy' actors driving their own Z /
    # visibility off the celebration clock (elapsed = TIME − SMB_CELEBRATE_START).
    mat_castle = make_mat('smb_castle', (0.60, 0.55, 0.50))
    CASTLE_X0, CASTLE_X1 = FLAGPOLE_X + 1.5 * T, FLAGPOLE_X + 4.5 * T   # 317.25 .. 321.75 (on the ground)
    CASTLE_TOP   = 3 * T                                               # 4.5 m tall
    CASTLE_MID_X = (CASTLE_X0 + CASTLE_X1) / 2
    add_statplat('castle', CASTLE_X0, -GROUND_Y, GROUND_TOP_Z, CASTLE_X1, GROUND_Y, CASTLE_TOP, mat_castle)
    add_statplat('castle_pole', CASTLE_MID_X - 0.1, -0.1, CASTLE_TOP,
                 CASTLE_MID_X + 0.1, 0.1, CASTLE_TOP + 2 * T, mat_pole)

    CFLAG_BASE_Z = CASTLE_TOP                          # 4.5 — authored low (rooftop base)
    CFLAG_TOP_Z  = CASTLE_TOP + 2.0 * T - 0.35 * T     # flag TOP (not center) meets the pole top 7.5
    # Thin VERTICAL slab (same reason as the pole flag — a flat plane is edge-on to the camera).
    # X so the flag's right edge overlaps the pole centre (CASTLE_MID_X) — attached, not floating beside it.
    # Shared unit-box mesh + size-as-scale; half-extents (0.45T, 0.03, 0.35T) about
    # (CASTLE_MID_X - 0.45T, 0, CFLAG_BASE_Z). Same green mat as the pole flag → shares its datablock.
    cflag = add_box('castle_flag',
                    (CASTLE_MID_X - 0.45 * T) - 0.45 * T, -0.03, CFLAG_BASE_Z - 0.35 * T,
                    (CASTLE_MID_X - 0.45 * T) + 0.45 * T,  0.03, CFLAG_BASE_Z + 0.35 * T,
                    mat_flag)
    attach_schema(cflag, 'enemy')
    cflag['wf_Mobility'] = 'Anchored'
    cflag['wf_Model Type'] = 'Mesh'
    cflag['wf_Visibility Mailbox'] = 1
    cflag['wf_Script'] = (
        "\\ wf\n"
        "INDEXOF_SMB_CELEBRATE read-mailbox if\n"
        "INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox - 0.8 -\n"  # elapsed - 0.8 (phase C)
        "dup 0.0 < if drop 0.0 then 1.667 *\n"   # frac = (elapsed-0.8)/0.6, clamped >=0
        "dup 1.0 > if drop 1.0 then\n"
        f"{CFLAG_TOP_Z - CFLAG_BASE_Z:.2f} * {CFLAG_BASE_Z:.2f} + INDEXOF_Z_POS write-mailbox\n"  # Z = base + span*frac
        "then\n"
    )

    # Castle door — a dark face on the castle's left/front where Mario walks in (he stops at
    # FLAGPOLE_X+2 ≈ the door, then SMB_MARIO_VIS=0 hides him → "entered the castle").
    mat_door = make_mat('smb_castle_door', (0.05, 0.04, 0.06))
    add_statplat('castle_door', CASTLE_X0 + 0.15, -GROUND_Y - 0.06, GROUND_TOP_Z,
                 CASTLE_X0 + 1.35, -GROUND_Y - 0.02, GROUND_TOP_Z + 2.2, mat_door)

    # ── Radial spark-burst fireworks (debris idiom, replaces the flat slabs) ──────
    # A parked Physics `spark_template` is THROWN by 6 invisible `generator` actors arranged
    # in an arc in the open sky above the castle (clear of the flag at Z 7.5). Each generator
    # pulses its global activation mailbox during a staggered elapsed window, but ONLY if its
    # index < SMB_FIREWORK_COUNT — the faithful SMB count (remaining-timer last digit 1/3/6,
    # else 0) the Player latches at celebration start. The generator's up-launch (Object Z
    # Velocity) + gravity arc the sparks; SPARK_SCRIPT fans XSPEED by actor index for the
    # radial spread; the spark despawns once it falls back below the burst height.
    # LOCAL_SYSTEM mailboxes only on the template (a LOCAL_USER write on a default-sized
    # template overflows its array → crash); no Random Displacement (Scalar::Random() asserts)
    # — the fan is deterministic via the fragment's actor index, like the brick debris.
    # (the spark material is created inside _make_spark_template via mat_spark())
    SPARK_H = 0.16                                          # ~0.32 m spark cube
    SPARK_DESPAWN_Z = CASTLE_TOP + 1.5                     # 6.0 — fallen back below the burst → vanish


    _make_spark_template()

    # 6 invisible generators in an arc in the open sky above the castle. Burst n fires in its
    # window iff n < SMB_FIREWORK_COUNT, so a count of 1/3/6 lights 1/3/6 bursts.
    FW_SKY_Z = CASTLE_TOP + 5.0   # 9.5 — burst origins above the flag (7.5), in open sky
    FW_ARC = [   # (x, z) arc above the castle, centre highest
        (CASTLE_MID_X - 3.0 * T, FW_SKY_Z - 0.5 * T),
        (CASTLE_MID_X - 1.8 * T, FW_SKY_Z + 0.3 * T),
        (CASTLE_MID_X - 0.6 * T, FW_SKY_Z + 0.8 * T),
        (CASTLE_MID_X + 0.6 * T, FW_SKY_Z + 0.8 * T),
        (CASTLE_MID_X + 1.8 * T, FW_SKY_Z + 0.3 * T),
        (CASTLE_MID_X + 3.0 * T, FW_SKY_Z - 0.5 * T),
    ]
    for _i, (_fx, _fz) in enumerate(FW_ARC):
        _t0 = 2.0 + _i * 0.35   # staggered; 0.6 s window → last burst ends ~4.35 (finale 4.5)
        _t1 = _t0 + 0.6
        g = bpy.data.objects.new(f'firework_gen_{_i}', None)   # Empty → meshless, non-solid spawner
        scene.collection.objects.link(g)
        attach_schema(g, 'generator')
        g.location = (_fx, 0.0, _fz)
        g['wf_Mobility']           = 'Anchored'
        g['wf_Model Type']         = 'None'              # invisible
        g['wf_Visibility Mailbox'] = 0
        g['wf_Activation MailBox'] = SMB_FIREWORK[_i]    # global; the script pulses it in-window
        g['wf_Object To Throw']    = 'spark_template'
        g['wf_Generation Rate']    = 10.0               # generator.oas cap; ~6 sparks over the 0.6 s window
        g['wf_Object X Velocity']  = 0.0
        g['wf_Object Y Velocity']  = 0.0                # OAS default 1.0 drifts into +Y — zero it
        g['wf_Object Z Velocity']  = 4.0               # up-launch; gravity arcs the sparks back down
        g['wf_Script'] = (
            "\\ wf\n"
            f"0 INDEXOF_SMB_FIREWORK_{_i} write-mailbox\n"            # default: don't spawn
            "INDEXOF_SMB_CELEBRATE read-mailbox if\n"
            f"  {_i} INDEXOF_SMB_FIREWORK_COUNT read-mailbox < if\n"  # this burst enabled by the count?
            "    INDEXOF_TIME read-mailbox INDEXOF_SMB_CELEBRATE_START read-mailbox -\n"   # elapsed
            f"    dup {_t0:.2f} > swap {_t1:.2f} < & if 1 INDEXOF_SMB_FIREWORK_{_i} write-mailbox then\n"
            "  then\n"
            "then\n"
        )

    # ── 10b. Flagpole end-of-level trigger ────────────────────────────────────────
    # Composition, NOT a class: an invisible ActBox sensor volume over the flagpole.
    # On Player overlap it writes SMB_CELEBRATE=1 → the Director runs the end-of-level
    # celebration (pole-flag slide, castle flag raise, timer→score drain) and fires
    # END_OF_LEVEL itself at the end. No script, no coordinate baked into a script (the
    # box's placement IS the trigger region). See docs/plans/2026-05-31-smb-flagpole-
    # celebration.md + 2026-05-25-smb-flagpole-end-of-level.md.
    END_OF_LEVEL  = 1905  # INDEXOF_END_OF_LEVEL (wfsource/source/mailbox/mailbox.inc:31)
    SMB_CELEBRATE = 1862  # INDEXOF_SMB_CELEBRATE — flag touch starts the celebration cutscene
    # Flag-driven level advance: a SECOND ActBox at the flag writes LEVEL_TO_RUN, the
    # persistent mailbox the meta-loop reads to pick the next level. shell.fth only seeds
    # it on first boot, so the value persists across the reload. mailbox.inc:247 documents
    # 5000 as "written by a flagpole ActBox to advance"; a level-side write to 5000 routes
    # to WFGame::WriteSystemMailbox (mailbox.cc:90-102) -> _desiredLevelNum (game.cc:705).
    # See docs/plans/2026-05-31-smb-flag-next-level-transition-and-w1-2-scaffold.md.
    LEVEL_TO_RUN     = 5000   # INDEXOF_LEVEL_TO_RUN (wfsource/source/mailbox/mailbox.inc:247)
    NEXT_LEVEL_INDEX = cfg['NEXT_LEVEL_INDEX']

    # Invisible activator volumes (actbox) — shared unit-box mesh + size-as-scale. Both triggers
    # are the same box about (FLAGPOLE_X, 0, 2T) with half-extents (1.5, T, 2.5T) → one datablock.
    mat_trigger = make_mat('smb_trigger', (0.5, 0.5, 0.5))
    flagtrig = add_box('flagpole_trigger',
                       FLAGPOLE_X - 1.5, -T, 2 * T - 2.5 * T,
                       FLAGPOLE_X + 1.5,  T, 2 * T + 2.5 * T,
                       mat_trigger)
    attach_schema(flagtrig, 'actbox')
    flagtrig['wf_MailBox']            = SMB_CELEBRATE  # start the celebration (Director fires END_OF_LEVEL at the end)
    flagtrig['wf_MailBoxValue']       = 1
    flagtrig['wf_Activated By Actor'] = 'Player'       # ActivatedBy defaults to 1 (Actor)
    # ActBox::activate unconditionally writes the activator's index to "Activated Actor
    # Mailbox"; its default 0 is a RESERVED mailbox (mailbox.cc asserts >= 2) → abort.
    # We don't need the activator, so send it to a scratch slot (SCRATCH_USER_START=4005).
    flagtrig['wf_Activated Actor Mailbox'] = 4005
    # ActBox DEFAULT_VISIBILITY=0 → invisible; bbox (activation volume) comes from the cube mesh.

    # ── 10c. Flagpole ADVANCE trigger (invisible ActBox → next level) ─────────────
    # Second ActBox at the SAME volume as flagpole_trigger. On Player overlap it writes
    # LEVEL_TO_RUN = NEXT_LEVEL_INDEX so the meta-loop loads the next level after this one
    # unloads. Same bbox as the END_OF_LEVEL trigger so both fire on the same frame; order
    # is irrelevant because the meta-loop reads _desiredLevelNum only after RunLevel()
    # returns. Death sets END_OF_LEVEL without touching LEVEL_TO_RUN, so dying restarts the
    # same level — only the flag advances.
    flagadv = add_box('flagpole_advance',
                      FLAGPOLE_X - 1.5, -T, 2 * T - 2.5 * T,
                      FLAGPOLE_X + 1.5,  T, 2 * T + 2.5 * T,
                      mat_trigger)   # identical box to flagpole_trigger → shares its datablock
    attach_schema(flagadv, 'actbox')
    flagadv['wf_MailBox']            = LEVEL_TO_RUN
    flagadv['wf_MailBoxValue']       = NEXT_LEVEL_INDEX
    flagadv['wf_Activated By Actor'] = 'Player'
    flagadv['wf_Activated Actor Mailbox'] = 4005   # scratch sink (same reserved-mb-0 gotcha)

