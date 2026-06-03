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
