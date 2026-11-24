"""Advent calendar: Tom of Finland-inspired concept scene (Blender 5.0, headless).

Builds a winter street with 24 numbered advent doors on four townhouses and four
clothed adult men (leather jackets, caps, scarves, boots), then renders the raw
shaded + Freestyle-inked image. `ink_post.py` turns that into the hatched drawing.

  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh blender -b -P \
      docs/plans/2026-11-21-advent-tom-of-finland-concept/tom-of-finland-src/build_scene.py -- \
      --out /build/advent/raw.png --width 2560 --samples 64
"""
import bpy, bmesh, math, random, sys
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default):
    return argv[argv.index(name) + 1] if name in argv else default
OUT = arg("--out", "/tmp/raw.png")          # "{view}" in the name is replaced per camera view
INK = arg("--ink", "1") == "1"               # Freestyle outlines (the hatched drawing needs them; plain renders do not)
VIEWS = arg("--views", "poster").split(",")  # poster, men_left, men_close, doors, high
WIDTH = int(arg("--width", "960"))
SAMPLES = int(arg("--samples", "24"))
HEIGHT = WIDTH * 9 // 16

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col_ink = bpy.data.collections.new("ink"); scene.collection.children.link(col_ink)
col_noink = bpy.data.collections.new("noink"); scene.collection.children.link(col_noink)

# ---------- helpers ----------
_mats = {}
def mat(name, color, rough=0.85, emit=0.0, spec=0.2):
    key = (name, color, rough, emit)
    if key in _mats: return _mats[key]
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if emit > 0:
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (*color, 1); e.inputs["Strength"].default_value = emit
        nt.links.new(e.outputs[0], out.inputs[0])
    else:
        b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        b.inputs["Base Color"].default_value = (*color, 1)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Specular IOR Level"].default_value = spec
        nt.links.new(b.outputs[0], out.inputs[0])
    _mats[key] = m
    return m

def to_obj(name, bm, m, ink=True, smooth=False, parent=None, loc=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    (col_ink if ink else col_noink).objects.link(ob)
    if parent is not None:
        ob.parent = parent
        if loc is not None: ob.location = loc
    return ob

def S(v): return Matrix.Diagonal((v[0], v[1], v[2], 1.0))

def b_box(bm, c, s, rot=None):
    M = Matrix.Translation(c) @ (rot.to_matrix().to_4x4() if rot else Matrix.Identity(4)) @ S(s)
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)

def b_ell(bm, c, r, rot=None, seg=16):
    M = Matrix.Translation(c) @ (rot.to_matrix().to_4x4() if rot else Matrix.Identity(4)) @ S(r)
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(8, seg // 2), radius=1.0, matrix=M)

def b_limb(bm, p1, p2, r1, r2, caps=True, seg=14):
    p1, p2 = Vector(p1), Vector(p2); d = p2 - p1
    if d.length < 1e-5: return
    q = d.to_track_quat("Z", "Y")
    M = Matrix.Translation((p1 + p2) / 2) @ q.to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r1, radius2=r2, depth=d.length, matrix=M)
    if caps:
        b_ell(bm, p1, (r1, r1, r1), seg=10); b_ell(bm, p2, (r2, r2, r2), seg=10)

def b_cone(bm, c, r1, r2, h, seg=18):
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=r1, radius2=r2, depth=h,
                          matrix=Matrix.Translation((c[0], c[1], c[2] + h / 2)))

def b_star(bm, c, R, r, depth):
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5; rr = R if i % 2 == 0 else r
        pts.append(bm.verts.new((c[0] + rr * math.cos(a), c[1], c[2] + rr * math.sin(a))))
    f = bm.faces.new(pts)
    ret = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)],
                        vec=(0, depth, 0))

# ---------- palette ----------
SNOW = mat("snow", (0.93, 0.95, 1.0), 1.0)
LEATHER = mat("leather", (0.04, 0.04, 0.045), 0.2, spec=1.0)
BOOT = mat("boot", (0.03, 0.03, 0.035), 0.35, spec=0.7)
JEANS = mat("jeans", (0.30, 0.38, 0.55), 0.9)
SKIN = mat("skin", (0.86, 0.62, 0.5), 0.6)
SCARF = mat("scarf", (0.72, 0.09, 0.09), 0.95)
SHIRT = mat("shirt", (0.9, 0.86, 0.78), 0.9)
HAIR = mat("hair", (0.12, 0.08, 0.05), 0.8)
GOLD = mat("gold", (0.9, 0.65, 0.18), 0.35, spec=0.8)
CREAM = mat("cream", (0.92, 0.86, 0.72), 0.9)
GREEN = mat("green", (0.08, 0.3, 0.14), 0.9)
RED = mat("red", (0.7, 0.08, 0.08), 0.8)
GLOW = mat("glow", (1.0, 0.72, 0.35), emit=3.0)
GLOW_HOT = mat("glowhot", (1.0, 0.85, 0.5), emit=9.0)
NUMBER = mat("number", (0.03, 0.03, 0.04), 0.8)
PLAQUE = mat("plaque", (1.0, 0.97, 0.88), emit=3.0)
DARKWOOD = mat("darkwood", (0.14, 0.09, 0.06), 0.8)
CAST = mat("castiron", (0.05, 0.06, 0.06), 0.5, spec=0.5)

# ---------- sky ----------
sky = bpy.data.meshes.new("sky"); bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=300.0)
bmesh.ops.reverse_faces(bm, faces=bm.faces[:]); bm.to_mesh(sky); bm.free()
skym = bpy.data.materials.new("skym"); skym.use_nodes = True; nt = skym.node_tree; nt.nodes.clear()
geo = nt.nodes.new("ShaderNodeNewGeometry"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
cr = nt.nodes.new("ShaderNodeValToRGB"); em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
mp = nt.nodes.new("ShaderNodeMapRange"); mp.inputs["From Min"].default_value = 0.0; mp.inputs["From Max"].default_value = 300.0
nt.links.new(geo.outputs["Position"], sep.inputs[0]); nt.links.new(sep.outputs["Z"], mp.inputs["Value"])
nt.links.new(mp.outputs[0], cr.inputs[0]); nt.links.new(cr.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
cr.color_ramp.elements[0].position = 0.0; cr.color_ramp.elements[0].color = (0.42, 0.44, 0.54, 1)
cr.color_ramp.elements[1].position = 0.75; cr.color_ramp.elements[1].color = (0.08, 0.09, 0.18, 1)
em.inputs["Strength"].default_value = 0.8
sky.materials.append(skym); sk = bpy.data.objects.new("sky", sky); col_noink.objects.link(sk)

# ---------- ground ----------
bm = bmesh.new(); b_box(bm, (0, -20, -0.5), (140, 90, 1.0)); to_obj("ground", bm, SNOW, ink=False)
bm = bmesh.new(); b_box(bm, (0, -2.0, 0.12), (140, 4.0, 0.24)); to_obj("pavement", bm, SNOW, ink=True)
bm = bmesh.new(); b_box(bm, (0, -4.15, 0.1), (140, 0.3, 0.3)); to_obj("curb", bm, mat("curb", (0.45, 0.45, 0.5), 0.9), ink=True)

# ---------- townhouses with 24 advent doors ----------
rng = random.Random(24)
numbers = list(range(1, 25)); rng.shuffle(numbers)
DOOR_COLS = [(0.55, 0.10, 0.10), (0.12, 0.36, 0.20), (0.16, 0.26, 0.50), (0.62, 0.45, 0.10)]
OPEN = set(range(1, 7))     # days 1-6 shown open
W = 9.2; GROUND_H = 7.4; STOREY = 4.2; WALL_T = 0.6
BUILDINGS = [
    dict(cx=-13.8, col=(0.62, 0.48, 0.28), roof="gable", gh=3.2),
    dict(cx=-4.6, col=(0.80, 0.74, 0.62), roof="flat", gh=1.9),
    dict(cx=4.6, col=(0.50, 0.20, 0.15), roof="gable", gh=3.6),
    dict(cx=13.8, col=(0.62, 0.66, 0.74), roof="flat", gh=2.2),
]
OPW, OPH, OPZ = 2.1, 2.9, 0.7
item_builders = {}
doors_log = []

def build_item(kind, cx, zb):
    y = 0.32
    if kind == 0:      # little fir with star
        bm = bmesh.new()
        for i, (r, h) in enumerate([(0.5, 0.55), (0.4, 0.5), (0.3, 0.45)]):
            b_cone(bm, (cx, y, zb + 0.08 + i * 0.38), r, 0.02, h)
        to_obj("fir", bm, GREEN, smooth=True)
        bm = bmesh.new(); b_star(bm, (cx - 0.0, y, zb + 1.28), 0.17, 0.07, 0.04); to_obj("firstar", bm, GLOW_HOT, ink=False)
        bm = bmesh.new()
        for dx, dz in [(-0.22, 0.3), (0.2, 0.55), (-0.05, 0.85), (0.12, 0.2)]:
            b_ell(bm, (cx + dx, y - 0.2, zb + dz), (0.05, 0.05, 0.05), seg=8)
        to_obj("baubles", bm, RED)
    elif kind == 1:    # wrapped gift
        bm = bmesh.new(); b_box(bm, (cx, y, zb + 0.35), (0.75, 0.6, 0.7)); to_obj("gift", bm, RED)
        bm = bmesh.new(); b_box(bm, (cx, y - 0.31, zb + 0.35), (0.14, 0.04, 0.72)); b_box(bm, (cx, y - 0.01, zb + 0.71), (0.14, 0.62, 0.04))
        b_box(bm, (cx, y - 0.3, zb + 0.35), (0.76, 0.04, 0.14)); to_obj("ribbon", bm, CREAM)
    elif kind == 2:    # candle
        bm = bmesh.new(); b_limb(bm, (cx, y, zb), (cx, y, zb + 0.75), 0.13, 0.13, caps=False, seg=16); to_obj("candle", bm, CREAM, smooth=True)
        bm = bmesh.new(); b_ell(bm, (cx, y, zb + 0.9), (0.07, 0.07, 0.16), seg=10); to_obj("flame", bm, GLOW_HOT, ink=False)
    elif kind == 3:    # tiny snowman
        bm = bmesh.new(); b_ell(bm, (cx, y, zb + 0.32), (0.34, 0.34, 0.34)); b_ell(bm, (cx, y, zb + 0.82), (0.25, 0.25, 0.25))
        b_ell(bm, (cx, y, zb + 1.2), (0.17, 0.17, 0.17)); to_obj("snowman", bm, SNOW, smooth=True)
        bm = bmesh.new(); b_limb(bm, (cx, y - 0.15, zb + 1.2), (cx, y - 0.42, zb + 1.18), 0.04, 0.005, caps=False, seg=8); to_obj("carrot", bm, mat("carrot", (0.9, 0.4, 0.05)))
        bm = bmesh.new(); b_cone(bm, (cx, y, zb + 1.33), 0.14, 0.14, 0.2); to_obj("snowhat", bm, LEATHER)
    elif kind == 4:    # bell
        bm = bmesh.new(); b_cone(bm, (cx, y, zb + 0.55), 0.38, 0.1, 0.55); b_ell(bm, (cx, y, zb + 0.55), (0.38, 0.38, 0.08), seg=14)
        to_obj("bell", bm, GOLD, smooth=True)
        bm = bmesh.new(); b_ell(bm, (cx, y, zb + 0.5), (0.1, 0.1, 0.1), seg=8); to_obj("clapper", bm, GOLD)
    else:              # star on a stand
        bm = bmesh.new(); b_star(bm, (cx, y, zb + 0.7), 0.5, 0.2, 0.08); to_obj("star", bm, GLOW_HOT, ink=False)
        bm = bmesh.new(); b_limb(bm, (cx, y, zb), (cx, y, zb + 0.3), 0.04, 0.04, caps=False, seg=8); to_obj("stand", bm, GOLD)

def make_number(text, parent, loc, size=0.95):
    cu = bpy.data.curves.new("n" + text, "FONT"); cu.body = text; cu.size = size
    cu.align_x = "CENTER"; cu.align_y = "CENTER"; cu.extrude = 0.015
    cu.materials.append(NUMBER)
    o = bpy.data.objects.new("num" + text, cu); col_noink.objects.link(o)
    o.parent = parent; o.location = loc; o.rotation_euler = (math.pi / 2, 0, 0)
    return o

ni = 0
for bi, B in enumerate(BUILDINGS):
    cx = B["cx"]; wallm = mat(f"wall{bi}", B["col"], 0.95)
    TOTAL_H = GROUND_H + 3 * STOREY
    # solid body behind the facade
    bm = bmesh.new(); b_box(bm, (cx, WALL_T + 2.7, TOTAL_H / 2), (W, 5.4, TOTAL_H)); to_obj(f"body{bi}", bm, wallm)
    # ground floor facade + shop windows, door
    bm = bmesh.new(); b_box(bm, (cx, WALL_T / 2, GROUND_H / 2), (W, WALL_T, GROUND_H)); to_obj(f"ground{bi}", bm, mat("gfloor", tuple(c * 0.8 for c in B["col"]), 0.95))
    bm = bmesh.new()
    for sx in (-3.0, 3.0): b_box(bm, (cx + sx, -0.03, 2.6), (2.3, 0.05, 3.6))
    to_obj(f"shop{bi}", bm, GLOW, ink=False)
    bm = bmesh.new()
    for sx in (-3.0, 3.0):          # shop frames + mullions
        for dx in (-1.2, 1.2): b_box(bm, (cx + sx + dx, -0.1, 2.6), (0.12, 0.14, 3.75))
        for dz in (-1.85, 1.85): b_box(bm, (cx + sx, -0.1, 2.6 + dz), (2.5, 0.14, 0.12))
        b_box(bm, (cx + sx, -0.08, 2.6), (0.07, 0.1, 3.6))
    b_box(bm, (cx, -0.12, 2.2), (1.5, 0.14, 4.4)); b_box(bm, (cx, -0.2, 4.5), (1.9, 0.3, 0.14))
    b_box(bm, (cx, -0.2, 6.5), (W + 0.2, 0.3, 1.5)); b_box(bm, (cx, -0.24, 5.75), (W + 0.1, 0.34, 0.14))
    to_obj(f"shopframe{bi}", bm, DARKWOOD)
    # awning stripes
    for k in range(8):
        bm = bmesh.new(); b_box(bm, (cx - 4.3 + k * 1.15 + 0.575, -0.9, 5.0), (1.15, 1.7, 0.1), rot=Euler((0.35, 0, 0)))
        to_obj(f"awn{bi}_{k}", bm, RED if k % 2 == 0 else CREAM)
    # upper storeys with openings
    for si in range(3):
        z0 = GROUND_H + si * STOREY
        xs = [cx - 2.35, cx + 2.35]
        bm = bmesh.new()
        edges = [cx - W / 2] + [v for x in xs for v in (x - OPW / 2, x + OPW / 2)] + [cx + W / 2]
        for a, b in [(edges[0], edges[1]), (edges[2], edges[3]), (edges[4], edges[5])]:
            b_box(bm, ((a + b) / 2, WALL_T / 2, z0 + STOREY / 2), (b - a, WALL_T, STOREY))
        for x in xs:
            b_box(bm, (x, WALL_T / 2, z0 + OPZ / 2), (OPW, WALL_T, OPZ))
            top = OPZ + OPH
            b_box(bm, (x, WALL_T / 2, z0 + (top + STOREY) / 2), (OPW, WALL_T, STOREY - top))
        to_obj(f"storey{bi}_{si}", bm, wallm)
        # cornice + snow ledge
        bm = bmesh.new(); b_box(bm, (cx, -0.12, z0 + STOREY - 0.05), (W + 0.3, 0.45, 0.2)); to_obj(f"cornice{bi}_{si}", bm, CREAM)
        bm = bmesh.new(); b_box(bm, (cx, -0.12, z0 + STOREY + 0.1), (W + 0.3, 0.4, 0.1)); to_obj(f"cornsnow{bi}_{si}", bm, SNOW)
        for x in xs:
            num = numbers[ni]; ni += 1
            zb = z0 + OPZ; zc = zb + OPH / 2
            # glowing back plate (visible when open)
            bm = bmesh.new(); b_box(bm, (x, WALL_T - 0.01, zc), (OPW - 0.02, 0.02, OPH)); to_obj(f"back{num}", bm, GLOW, ink=False)
            # frame
            bm = bmesh.new()
            for dx in (-1, 1): b_box(bm, (x + dx * (OPW / 2 + 0.1), -0.06, zc), (0.2, 0.2, OPH + 0.4))
            b_box(bm, (x, -0.06, zb + OPH + 0.1), (OPW + 0.5, 0.22, 0.22)); b_box(bm, (x, -0.1, zb - 0.1), (OPW + 0.6, 0.3, 0.2))
            to_obj(f"frame{num}", bm, CREAM)
            bm = bmesh.new(); b_box(bm, (x, -0.1, zb + OPH + 0.28), (OPW + 0.7, 0.3, 0.1)); to_obj(f"framesnow{num}", bm, SNOW)
            # hinged advent door
            hinge = bpy.data.objects.new(f"hinge{num}", None); col_ink.objects.link(hinge)
            hinge.location = (x - OPW / 2 - 0.02, -0.2, zc)
            if num in OPEN: hinge.rotation_euler = (0, 0, -math.radians(100))
            dm = mat(f"door{num % 4}", DOOR_COLS[(num * 7) % 4], 0.6)
            bm = bmesh.new(); b_box(bm, (OPW / 2 + 0.02, 0, 0), (OPW + 0.04, 0.07, OPH + 0.02))
            for dx in (-1, 1):
                for dz in (-1, 1): b_box(bm, (OPW / 2 + 0.02 + dx * 0.55, -0.045, dz * 0.62), (0.7, 0.025, 0.7))
            to_obj(f"door{num}", bm, dm, parent=hinge)
            bm = bmesh.new(); b_ell(bm, (OPW / 2 + 0.02, -0.085, 0.0), (0.7, 0.012, 0.7), seg=28); to_obj(f"plaque{num}", bm, PLAQUE, parent=hinge)
            make_number(str(num), hinge, (OPW / 2 + 0.02, -0.105, 0.0), size=1.15 if num < 10 else 0.9)
            bm = bmesh.new(); b_ell(bm, (OPW - 0.18, -0.07, -0.05), (0.07, 0.05, 0.07), seg=8); to_obj(f"knob{num}", bm, GOLD, parent=hinge)
            if num in OPEN:
                build_item((num - 1) % 6, x, zb)
                # the swung-open door shows only its edge, so repeat the number on the niche's back wall
                bm = bmesh.new(); b_ell(bm, (x, WALL_T - 0.035, zb + 2.3), (0.42, 0.01, 0.42), seg=24); to_obj(f"stk{num}", bm, PLAQUE)
                make_number(str(num), None, (x, WALL_T - 0.055, zb + 2.3), size=0.8)
            doors_log.append((num, bi, si, round(x, 1), num in OPEN))
    # roof
    if B["roof"] == "gable":
        gh = B["gh"]; bm = bmesh.new()
        vs = [bm.verts.new(p) for p in [(cx - W / 2 - 0.3, -0.3, TOTAL_H), (cx + W / 2 + 0.3, -0.3, TOTAL_H), (cx, -0.3, TOTAL_H + gh)]]
        f = bm.faces.new(vs); r = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, verts=[v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)], vec=(0, 6.6, 0))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        to_obj(f"roof{bi}", bm, mat("roof", (0.18, 0.17, 0.2), 0.9))
        # snow on roof slopes
        for sgn in (-1, 1):
            ang = math.atan2(gh, W / 2 + 0.3); L = math.hypot(W / 2 + 0.3, gh)
            bm = bmesh.new(); b_box(bm, (cx + sgn * (W / 4 + 0.15), 3.0, TOTAL_H + gh / 2 + 0.12),
                                    (L, 6.8, 0.22), rot=Euler((0, sgn * ang, 0)))
            to_obj(f"roofsnow{bi}_{sgn}", bm, SNOW)
        bm = bmesh.new(); b_box(bm, (cx + 1.4, 3.0, TOTAL_H + gh * 0.55 + 0.6), (0.8, 0.8, 1.8)); to_obj(f"chimney{bi}", bm, mat("brick", (0.4, 0.17, 0.12)))
        bm = bmesh.new(); b_box(bm, (cx + 1.4, 3.0, TOTAL_H + gh * 0.55 + 1.55), (1.0, 1.0, 0.18)); to_obj(f"chimsnow{bi}", bm, SNOW)
        # round attic light
        bm = bmesh.new(); b_ell(bm, (cx, -0.12, TOTAL_H + gh * 0.38), (0.8, 0.12, 0.8), seg=20); to_obj(f"attic{bi}", bm, GLOW, ink=False)
        bm = bmesh.new(); b_ell(bm, (cx, -0.2, TOTAL_H + gh * 0.38), (0.95, 0.08, 0.95), seg=20); to_obj(f"atticring{bi}", bm, CREAM)
    else:
        gh = B["gh"]; bm = bmesh.new()
        b_box(bm, (cx, 0.0, TOTAL_H + 0.3), (W + 0.4, 0.5, 0.6))
        to_obj(f"parapet{bi}", bm, CREAM)
        bm = bmesh.new(); b_box(bm, (cx, 3.2, TOTAL_H + 0.1), (W, 6.4, 0.2)); to_obj(f"flatroof{bi}", bm, SNOW)
        bm = bmesh.new(); b_box(bm, (cx, 0.0, TOTAL_H + 0.64), (W + 0.4, 0.5, 0.16)); to_obj(f"paprsnow{bi}", bm, SNOW)
        vs = None; bm = bmesh.new()
        tv = [bm.verts.new(p) for p in [(cx - 2.6, -0.2, TOTAL_H + 0.6), (cx + 2.6, -0.2, TOTAL_H + 0.6), (cx, -0.2, TOTAL_H + 0.6 + gh)]]
        f = bm.faces.new(tv); r = bmesh.ops.extrude_face_region(bm, geom=[f])
        bmesh.ops.translate(bm, verts=[v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)], vec=(0, 0.6, 0))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        to_obj(f"pediment{bi}", bm, wallm)
        bm = bmesh.new(); b_ell(bm, (cx, -0.45, TOTAL_H + 0.6 + gh * 0.42), (0.55, 0.08, 0.55), seg=20); to_obj(f"pedlight{bi}", bm, GLOW, ink=False)
        bm = bmesh.new(); b_box(bm, (cx + 2.5, 3.0, TOTAL_H + 1.1), (0.9, 0.9, 1.8)); to_obj(f"chimney{bi}", bm, mat("brick", (0.4, 0.17, 0.12)))
        bm = bmesh.new(); b_box(bm, (cx + 2.5, 3.0, TOTAL_H + 2.05), (1.1, 1.1, 0.18)); to_obj(f"chimsnow{bi}", bm, SNOW)

assert ni == 24, ni
# bake the text curves to meshes (one depsgraph update for all 24)
bpy.context.view_layer.update()
_dg = bpy.context.evaluated_depsgraph_get()
for _o in [o for o in col_noink.objects if o.type == 'FONT']:
    _me = bpy.data.meshes.new_from_object(_o.evaluated_get(_dg)); _me.materials.clear(); _me.materials.append(NUMBER)
    _n = bpy.data.objects.new(_o.name + 'm', _me); col_noink.objects.link(_n)
    _n.parent = _o.parent; _n.location = _o.location; _n.rotation_euler = _o.rotation_euler
    bpy.data.objects.remove(_o)

# ---------- men ----------
def man(name, base, yaw, J, extras=None, sc=1.2):
    T = Matrix.Translation(base) @ Matrix.Rotation(yaw, 4, "Z") @ S((sc, sc, sc))
    W_ = lambda p: T @ Vector(p)
    bj = {k: bmesh.new() for k in ("leather", "boot", "jeans", "skin", "scarf", "shirt", "hair", "gold")}
    def ell(k, c, r, rot=None, seg=16):
        M = T @ Matrix.Translation(c) @ (rot.to_matrix().to_4x4() if rot else Matrix.Identity(4)) @ S(r)
        bmesh.ops.create_uvsphere(bj[k], u_segments=seg, v_segments=max(8, seg // 2), radius=1.0, matrix=M)
    def box(k, c, s, rot=None):
        M = T @ Matrix.Translation(c) @ (rot.to_matrix().to_4x4() if rot else Matrix.Identity(4)) @ S(s)
        bmesh.ops.create_cube(bj[k], size=1.0, matrix=M)
    def limb(k, p1, p2, r1, r2, caps=True): b_limb(bj[k], W_(p1), W_(p2), r1, r2, caps)
    # pelvis, waist, chest, shoulders
    ell("jeans", (0, 0, 2.2), (0.64, 0.44, 0.46))
    ell("leather", (0, 0, 2.78), (0.56, 0.37, 0.52))
    ell("leather", (0, 0, 3.3), (1.0, 0.54, 0.7), seg=24)
    ell("shirt", (0, -0.34, 3.5), (0.34, 0.2, 0.42))
    ell("leather", (-0.33, -0.43, 3.55), (0.3, 0.16, 0.4), Euler((0, 0, 0.5)))
    ell("leather", (0.33, -0.43, 3.55), (0.3, 0.16, 0.4), Euler((0, 0, -0.5)))
    ell("gold", (0, -0.4, 2.62), (0.12, 0.08, 0.08), seg=10)
    ell("leather", (0, 0, 2.6), (0.6, 0.41, 0.09))      # belt
    for s in (-1, 1): ell("leather", (s * 0.95, 0, 3.56), (0.31, 0.3, 0.3))
    # neck + head
    limb("skin", (0, 0, 3.8), (0, 0, 4.1), 0.2, 0.19, caps=False)
    ell("skin", (0, -0.03, 4.3), (0.35, 0.37, 0.42))
    ell("skin", (0, -0.11, 4.08), (0.33, 0.3, 0.28))
    ell("skin", (0, -0.4, 4.2), (0.08, 0.1, 0.09), seg=8)
    for s in (-1, 1):
        ell("skin", (s * 0.36, 0, 4.27), (0.06, 0.09, 0.12), seg=8)
        ell("hair", (s * 0.16, -0.36, 4.33), (0.07, 0.04, 0.025), seg=8)
        ell("hair", (s * 0.15, -0.36, 4.4), (0.12, 0.04, 0.03), Euler((0, s * -0.2, 0)), seg=8)
    ell("hair", (0, -0.4, 4.07), (0.22, 0.08, 0.06), seg=10)       # moustache
    ell("shirt", (0, -0.39, 3.96), (0.12, 0.05, 0.03), seg=8)       # grin
    ell("hair", (0, 0.2, 4.4), (0.36, 0.3, 0.3))                    # hair under cap
    # peaked cap
    ell("leather", (0, -0.02, 4.58), (0.42, 0.43, 0.2), seg=18)
    box("leather", (0, -0.12, 4.42), (0.86, 0.5, 0.1))
    box("leather", (0, -0.46, 4.4), (0.5, 0.34, 0.05), Euler((-0.25, 0, 0)))
    ell("gold", (0, -0.42, 4.6), (0.07, 0.03, 0.07), seg=8)
    # scarf
    ell("scarf", (0, -0.02, 3.93), (0.34, 0.31, 0.13), seg=18)
    limb("scarf", (0.12, -0.3, 3.86), (0.2, -0.42, 3.0), 0.11, 0.1)
    limb("scarf", (0.12, -0.3, 3.86), (0.28, -0.38, 3.35), 0.12, 0.1)
    # arms
    for s, (sh, el, ha) in (( -1, J["armL"]), (1, J["armR"])):
        limb("leather", sh, el, 0.3, 0.25); limb("leather", el, ha, 0.24, 0.19)
        ell("leather", ha, (0.19, 0.19, 0.17), seg=10)
    # legs + boots
    for key in ("legL", "legR"):
        hip, kn, ft = J[key]
        limb("jeans", hip, kn, 0.37, 0.28); limb("jeans", kn, (ft[0], ft[1], 0.5), 0.27, 0.23)
        limb("boot", (ft[0], ft[1], 0.25), (ft[0], ft[1], 1.1), 0.27, 0.3, caps=False)
        ell("boot", (ft[0], ft[1], 1.1), (0.31, 0.31, 0.05), seg=14)
        box("boot", (ft[0], ft[1] - 0.22, 0.2), (0.44, 0.9, 0.32)); box("boot", (ft[0], ft[1] - 0.22, 0.04), (0.5, 0.96, 0.1))
    mats = dict(leather=LEATHER, boot=BOOT, jeans=JEANS, skin=SKIN, scarf=SCARF, shirt=SHIRT, hair=HAIR, gold=GOLD)
    for k, bm in bj.items():
        for f in bm.faces: f.smooth = True
        to_obj(f"{name}_{k}", bm, mats[k], smooth=True)
    return T

def Wp(T, p): return T @ Vector(p)

SH = 0.98
JOINTS = {
 "wreath": dict(  # raising a wreath toward the lamp
    armL=((-SH, 0, 3.55), (-1.45, 0.1, 2.9), (-0.72, -0.5, 2.55)),
    armR=((SH, 0, 3.55), (1.5, -0.2, 3.95), (1.45, -0.45, 4.45)),
    legL=((-0.32, 0, 2.15), (-0.4, -0.2, 1.25), (-0.5, 0.05, 0.1)),
    legR=((0.32, 0, 2.15), (0.45, -0.28, 1.2), (0.62, -0.3, 0.1))),
 "gift": dict(    # gift box on the shoulder, candy cane in the other hand
    armL=((-SH, 0, 3.55), (-1.55, -0.3, 3.2), (-1.25, -0.05, 3.95)),
    armR=((SH, 0, 3.55), (1.45, -0.25, 2.85), (1.4, -0.55, 2.15)),
    legL=((-0.32, 0, 2.15), (-0.42, -0.1, 1.2), (-0.45, 0.0, 0.1)),
    legR=((0.32, 0, 2.15), (0.5, -0.35, 1.25), (0.75, -0.75, 0.1))),
 "lantern": dict(  # lantern in one hand, other tucked in the pocket, ankles crossed
    armL=((-SH, 0, 3.55), (-1.3, -0.15, 2.9), (-0.7, -0.5, 2.4)),
    armR=((SH, 0, 3.55), (1.45, -0.25, 3.0), (1.5, -0.6, 2.5)),
    legL=((-0.32, 0, 2.15), (-0.2, -0.15, 1.2), (-0.1, 0.0, 0.1)),
    legR=((0.32, 0, 2.15), (0.1, -0.4, 1.2), (-0.45, -0.55, 0.1))),
 "snowball": dict(  # holding a snowball, grinning, weight on one hip
    armL=((-SH, 0, 3.55), (-1.25, -0.55, 3.0), (-0.3, -1.0, 3.15)),
    armR=((SH, 0, 3.55), (1.25, -0.55, 3.0), (0.3, -1.0, 3.15)),
    legL=((-0.32, 0, 2.15), (-0.6, -0.1, 1.2), (-0.8, 0.1, 0.1)),
    legR=((0.32, 0, 2.15), (0.4, -0.4, 1.2), (0.45, -0.5, 0.1))),
}
Y0 = -16.0
T1 = man("wreathman", (-7.0, Y0 - 0.6, 0.24), 0.35, JOINTS["wreath"])
T2 = man("giftman", (-1.6, Y0 + 0.7, 0.24), -0.22, JOINTS["gift"])
T3 = man("lanternman", (3.4, Y0 - 0.9, 0.24), 0.12, JOINTS["lantern"])
T4 = man("snowballman", (8.2, Y0 + 0.5, 0.24), -0.42, JOINTS["snowball"])

# props held by the men
wp = Wp(T1, (1.45, -0.55, 4.75))
bm = bmesh.new()
bmesh.ops.create_torus = None if not hasattr(bmesh.ops, "create_torus") else bmesh.ops.create_torus
for i in range(26):
    a = i / 26 * math.tau
    b_ell(bm, wp + Vector((0.5 * math.cos(a), 0, 0.5 * math.sin(a))), (0.17, 0.17, 0.17), seg=8)
to_obj("wreath", bm, GREEN, smooth=True)
bm = bmesh.new(); b_ell(bm, wp + Vector((0, -0.08, -0.5)), (0.3, 0.12, 0.16)); b_ell(bm, wp + Vector((0, -0.05, -0.62)), (0.1, 0.1, 0.3))
to_obj("wreathbow", bm, RED)
bm = bmesh.new(); b_ell(bm, wp + Vector((0.3, -0.25, 0.3)), (0.07, 0.07, 0.07), seg=8); b_ell(bm, wp + Vector((-0.35, -0.25, 0.1)), (0.07, 0.07, 0.07), seg=8)
to_obj("wreathbaubles", bm, GOLD)
# gift on shoulder
gp = Wp(T2, (-1.4, 0.0, 4.55))
bm = bmesh.new(); b_box(bm, gp, (1.3, 1.2, 1.2), rot=Euler((0, 0, -0.22 + 0.2))); to_obj("bigbox", bm, RED)
bm = bmesh.new(); b_box(bm, gp + Vector((0, -0.01, 0)), (0.2, 1.24, 1.24), rot=Euler((0, 0, -0.02))); b_box(bm, gp + Vector((0, 0, 0)), (1.34, 0.2, 1.24), rot=Euler((0, 0, -0.02)))
b_ell(bm, gp + Vector((0, -0.5, 0.75)), (0.4, 0.15, 0.2)); to_obj("bigribbon", bm, CREAM)
cp = Wp(T2, (1.4, -0.58, 2.1))                       # candy cane
bm = bmesh.new(); b_limb(bm, cp, cp + Vector((0, 0, 1.4)), 0.07, 0.07, caps=False, seg=10)
for a in range(1, 8): b_ell(bm, cp + Vector((0.1 * math.sin(a / 8 * math.pi) * 0.0 + (0.28 - 0.28 * math.cos(a / 8 * math.pi)) * 0.5, 0, 1.4 + 0.28 * math.sin(a / 8 * math.pi))), (0.07, 0.07, 0.07), seg=6)
to_obj("candycane", bm, RED)
# lantern
lp = Wp(T3, (1.5, -0.6, 2.05))
bm = bmesh.new(); b_box(bm, lp, (0.36, 0.36, 0.5)); to_obj("lantern", bm, GLOW_HOT, ink=False)
bm = bmesh.new(); b_box(bm, lp + Vector((0, 0, 0.31)), (0.44, 0.44, 0.1)); b_box(bm, lp + Vector((0, 0, -0.3)), (0.44, 0.44, 0.08))
b_limb(bm, lp + Vector((0, 0, 0.36)), lp + Vector((0, 0, 0.6)), 0.03, 0.03, caps=False, seg=6)
for dx in (-0.2, 0.2):
    for dy in (-0.2, 0.2): b_limb(bm, lp + Vector((dx, dy, -0.3)), lp + Vector((dx, dy, 0.3)), 0.025, 0.025, caps=False, seg=6)
to_obj("lanterncage", bm, CAST)
# snowball + a little snowman buddy
sp = Wp(T4, (0.0, -1.1, 3.2))
bm = bmesh.new(); b_ell(bm, sp, (0.42, 0.42, 0.42), seg=16); to_obj("snowball", bm, SNOW, smooth=True)
bx, by = 11.6, Y0 + 2.2
bm = bmesh.new(); b_ell(bm, (bx, by, 0.24 + 0.7), (0.75, 0.75, 0.7)); b_ell(bm, (bx, by, 0.24 + 1.8), (0.55, 0.55, 0.52)); b_ell(bm, (bx, by, 0.24 + 2.65), (0.4, 0.4, 0.4))
to_obj("bigsnowman", bm, SNOW, smooth=True)
bm = bmesh.new(); b_limb(bm, (bx, by - 0.3, 2.9), (bx, by - 0.95, 2.82), 0.07, 0.01, caps=False, seg=8); to_obj("bigcarrot", bm, mat("carrot", (0.9, 0.4, 0.05)))
bm = bmesh.new(); b_cone(bm, (bx, by, 3.05), 0.3, 0.3, 0.42); b_ell(bm, (bx, by, 3.05), (0.5, 0.5, 0.05)); to_obj("bigsnowhat", bm, LEATHER)
bm = bmesh.new(); b_ell(bm, (bx, by, 2.1), (0.62, 0.6, 0.12)); b_limb(bm, (bx + 0.35, by - 0.5, 2.05), (bx + 0.55, by - 0.55, 1.2), 0.1, 0.09); to_obj("bigscarf", bm, SCARF)
bm = bmesh.new()
for dz in (1.0, 1.7, 2.3): b_ell(bm, (bx - 0.06 * (dz > 1.5) - 0.0, by - 0.7 - 0.0, 0.24 + dz), (0.07, 0.06, 0.07), seg=6)
for sx in (-0.14, 0.14): b_ell(bm, (bx + sx, by - 0.35, 3.0), (0.05, 0.04, 0.05), seg=6)
to_obj("coal", bm, LEATHER)

# ---------- lamp posts, garland, tree ----------
lamps = []
def lamp(x, y):
    bm = bmesh.new(); b_limb(bm, (x, y, 0.24), (x, y, 4.2), 0.12, 0.08, caps=False, seg=10); b_limb(bm, (x, y, 0.24), (x, y, 0.9), 0.24, 0.12, caps=False, seg=10)
    b_limb(bm, (x, y, 3.8), (x + 0.5, y, 4.3), 0.05, 0.05, caps=False, seg=6)
    to_obj(f"lamp{x}", bm, CAST)
    bm = bmesh.new(); b_ell(bm, (x, y, 4.55), (0.3, 0.3, 0.38), seg=12); to_obj(f"lampglow{x}", bm, GLOW_HOT, ink=False)
    bm = bmesh.new(); b_cone(bm, (x, y, 4.9), 0.4, 0.08, 0.3, seg=12); to_obj(f"lampcap{x}", bm, CAST)
    lamps.append((x, y, 4.55))
    ld = bpy.data.lights.new(f"lampL{x}", "POINT"); ld.energy = 900; ld.color = (1.0, 0.75, 0.45); ld.shadow_soft_size = 0.4
    lo = bpy.data.objects.new(f"lampL{x}", ld); lo.location = (x, y - 0.6, 4.5); scene.collection.objects.link(lo)
lamp(wp.x + 0.9, Y0 + 1.6); lamp(0.9, Y0 + 2.4); lamp(-12.2, Y0 + 3.5); lamp(12.6, Y0 + 3.8)
# string lights between building cornices and lamps
def garland(p1, p2, sag, n, name):
    bm = bmesh.new()
    for i in range(n + 1):
        t = i / n; p = Vector(p1).lerp(Vector(p2), t); p.z -= sag * 4 * t * (1 - t)
        b_ell(bm, p, (0.1, 0.1, 0.1), seg=6)
    to_obj(name, bm, GLOW_HOT, ink=False)
    bm = bmesh.new(); prev = None
    for i in range(n + 1):
        t = i / n; p = Vector(p1).lerp(Vector(p2), t); p.z -= sag * 4 * t * (1 - t)
        if prev is not None: b_limb(bm, prev, p, 0.015, 0.015, caps=False, seg=4)
        prev = p
    to_obj(name + "wire", bm, CAST)
ls = sorted(lamps)
for i in range(len(ls) - 1):
    a, b = ls[i], ls[i + 1]
    garland((a[0], a[1], a[2] - 0.4), (b[0], b[1], b[2] - 0.4), 1.1, 14, f"garl{i}")
garland((-18.4, -0.2, 15.7), (-9.2, -0.2, 15.8), 0.5, 20, "garbA"); garland((-9.2, -0.2, 15.8), (0.0, -0.2, 15.9), 0.5, 20, "garbB")
garland((0.0, -0.2, 15.9), (9.2, -0.2, 15.8), 0.5, 20, "garbC"); garland((9.2, -0.2, 15.8), (18.4, -0.2, 15.7), 0.5, 20, "garbD")
# street fir at the left edge
fx, fy = -15.3, -12.0
bm = bmesh.new()
for i, (r, h) in enumerate([(1.9, 2.3), (1.6, 2.1), (1.25, 1.9), (0.9, 1.7), (0.55, 1.5)]):
    b_cone(bm, (fx, fy, 1.04 + i * 1.4), r, 0.05, h, seg=22)
to_obj("streetfir", bm, GREEN, smooth=True)
bm = bmesh.new(); b_star(bm, (fx, fy - 0.1, 8.3), 0.5, 0.22, 0.12); to_obj("streetfirstar", bm, GLOW_HOT, ink=False)
bm = bmesh.new(); r2 = random.Random(5)
for i in range(30):
    z = r2.uniform(1.4, 6.6); rad = max(0.1, 1.9 - (z - 1.0) * 0.26); a = r2.uniform(0, math.tau)
    b_ell(bm, (fx + rad * 0.95 * math.cos(a), fy + rad * 0.95 * math.sin(a) * 0.9 - 0.2, z), (0.12, 0.12, 0.12), seg=6)
to_obj("firlights", bm, GLOW_HOT, ink=False)

# ---------- snowfall ----------
bm = bmesh.new(); r3 = random.Random(11)
for i in range(520):
    p = (r3.uniform(-24, 24), r3.uniform(-45, 3), r3.uniform(0.5, 22)); s = r3.uniform(0.04, 0.09) * (1 + (p[1] + 36) / 60 * 0)
    b_ell(bm, p, (s, s, s), seg=6)
to_obj("flakes", bm, mat("flake", (1, 1, 1), emit=6.0), ink=False)

# ---------- lighting ----------
sd = bpy.data.lights.new("moon", "SUN"); sd.energy = 2.2; sd.color = (0.78, 0.84, 1.0); sd.angle = 0.05
so = bpy.data.objects.new("moon", sd); so.rotation_euler = (math.radians(62), 0, math.radians(-38)); scene.collection.objects.link(so)
for pos, e in (((-2.0, -12.0, 4.5), 1500), ((3.4 + 1.5, Y0 - 1.5, 3.0), 500), ((-12.6, -7, 4.0), 600)):
    ld = bpy.data.lights.new("warm", "POINT"); ld.energy = e; ld.color = (1.0, 0.72, 0.4); ld.shadow_soft_size = 0.6
    lo = bpy.data.objects.new("warm", ld); lo.location = pos; scene.collection.objects.link(lo)
# key light (front-left) and warm rim light (back-right) so black leather shows gloss
for nm, pos, rot, e, colr in (("key", (-12, -30, 11), (math.radians(78), 0, math.radians(-22)), 4000, (1.0, 0.96, 0.9)),
                              ("rim", (14, -6, 9), (math.radians(-80), 0, math.radians(-30)), 3000, (1.0, 0.78, 0.5))):
    ld = bpy.data.lights.new(nm, "AREA"); ld.energy = e; ld.color = colr; ld.size = 6.0
    lo = bpy.data.objects.new(nm, ld); lo.location = pos; lo.rotation_euler = rot; scene.collection.objects.link(lo)
# glow from the shop windows onto the pavement
for bx0 in (-12.6, -4.2, 4.2, 12.6):
    ld = bpy.data.lights.new("shop", "AREA"); ld.energy = 900; ld.color = (1.0, 0.75, 0.45); ld.size = 5.5; ld.size_y = 2.2
    lo = bpy.data.objects.new("shop", ld); lo.location = (bx0, -2.0, 2.2); lo.rotation_euler = (math.radians(90), 0, 0); scene.collection.objects.link(lo)

# ---------- camera ----------
cd = bpy.data.cameras.new("cam"); cd.lens = 35; cd.clip_end = 1000; cd.shift_y = 0.17
cam = bpy.data.objects.new("cam", cd); scene.collection.objects.link(cam)
cam.location = (0.0, -46.0, 2.8); cam.rotation_euler = (math.radians(90.0), 0, 0)
scene.camera = cam

# ---------- render ----------
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
scene.cycles.sample_clamp_indirect = 4.0   # tame fireflies from the many small emitters
scene.cycles.max_bounces = 4; scene.cycles.diffuse_bounces = 2; scene.cycles.glossy_bounces = 2
scene.render.resolution_x = WIDTH; scene.render.resolution_y = HEIGHT; scene.render.resolution_percentage = 100
scene.view_settings.view_transform = "Standard"; scene.view_settings.look = "None"
scene.render.image_settings.file_format = "PNG"; scene.render.filepath = OUT
# Freestyle ink lines
scene.render.use_freestyle = INK
vl = bpy.context.view_layer; vl.use_freestyle = INK
ls_ = vl.freestyle_settings.linesets.new("ink") if not vl.freestyle_settings.linesets else vl.freestyle_settings.linesets[0]
ls_.select_silhouette = True; ls_.select_border = True; ls_.select_crease = True; ls_.select_material_boundary = False
ls_.select_by_collection = True; ls_.collection = col_ink; ls_.select_by_visibility = True
vl.freestyle_settings.crease_angle = math.radians(105)
if ls_.linestyle is None: ls_.linestyle = bpy.data.linestyles.new("inkstyle")
lst = ls_.linestyle; lst.thickness = max(1.2, WIDTH / 2560 * 3.2); lst.color = (0, 0, 0)
scene.render.line_thickness_mode = "ABSOLUTE"; scene.render.line_thickness = lst.thickness

# camera views: (location, look-at target, focal length, shift_y). "poster" is the framing the hatched drawing uses.
CAMERAS = {
    "poster":    ((0.0, -46.0, 2.8), None, 35, 0.17),
    "men_left":  ((-15.0, -27.0, 1.7), (1.0, -16.0, 3.4), 35, 0.0),
    "men_close": ((0.9, -25.0, 3.3), (0.9, -16.0, 3.7), 28, 0.0),
    "doors":     ((-11.0, -20.0, 10.5), (-11.0, 0.0, 14.0), 50, 0.0),
    "high":      ((17.0, -31.0, 17.0), (0.0, -10.0, 6.0), 35, 0.0),
}
bpy.context.view_layer.update()
_dg = bpy.context.evaluated_depsgraph_get()
_tris = 0
for _o in scene.objects:
    if _o.type in ("MESH", "FONT"):
        _m = _o.evaluated_get(_dg).to_mesh(); _tris += sum(len(p.vertices) - 2 for p in _m.polygons); _o.evaluated_get(_dg).to_mesh_clear()
print("STATS blender", bpy.app.version_string, "objects", len(scene.objects), "meshes", len([o for o in scene.objects if o.type in ("MESH", "FONT")]),
      "triangles", _tris, "materials", len(bpy.data.materials), "lights", len([o for o in scene.objects if o.type == "LIGHT"]),
      "images", len(bpy.data.images), "textures", len(bpy.data.textures), "fonts", [f.name for f in bpy.data.fonts], flush=True)
for v in [v for v in VIEWS if v != "none"]:
    loc, tgt, lens, shy = CAMERAS[v]
    cam.location = loc; cd.lens = lens; cd.shift_y = shy
    if tgt is None:
        cam.rotation_euler = (math.radians(90.0), 0, 0)
    else:
        cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    path = OUT.replace("{view}", v)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path, flush=True)
print("DOORS", sorted(doors_log))
