#!/usr/bin/env python3
"""
Generate Marble Madness Level 1 (Beginner Race) course for marble-madness-2.
Creates mesh .iff files and rewrites marble-madness-2.lev.
Run from wflevels/marble-madness-2/.

Course overview (world coords, looking +Y = forward, +Z = up):

  Start platform       Y= 0..10   X=[-6,6]    Z=12   flat
  First ramp           Y=10..34   X=[-6,6]    Z=12→4 wide gentle slope
  Corner junction      Y=34..42   X=[-6,6]    Z=4    flat (turn point)
  X-bridge (left turn) Y=38..42   X=[-6..-26] Z=4    narrow, goes -X
  Left landing         Y=34..46   X=[-26..-18]Z=4    flat
  Final ramp           Y=34..46   X=[-18..-6] Z=4→0  narrower descent
  Goal platform        Y=34..46   X=[-6..6]   Z=0    flat
"""

import struct, math, sys, os

GREY = 0x00AAAAAA   # marble-madness grey, no texture

# ── IFF mesh helpers ──────────────────────────────────────────────────────────

def fx(v):
    return int(round(v * 65536))

def iff_chunk(tag, payload):
    b = tag.encode('ascii')[:4].ljust(4, b'\x00')
    sz = len(payload)
    pad = (4 - sz % 4) % 4
    return b + struct.pack('<I', sz) + payload + b'\x00' * pad

def make_grey_matl():
    """Untextured flat-shaded grey material."""
    flags = 0x00
    color = GREY
    tex   = b'\x00' * 256
    return struct.pack('<iI', flags, color) + tex

MATL = make_grey_matl()

def write_mesh(verts, faces, path):
    """verts=(u,v,x,y,z), faces=(i,j,k)."""
    vb = bytearray()
    for u, v, x, y, z in verts:
        vb += struct.pack('<iiIiii', fx(u), fx(v), GREY, fx(x), fx(y), fx(z))
    fb = bytearray()
    for i, j, k in faces:
        fb += struct.pack('<hhhh', i, j, k, 0)
    inner = iff_chunk('VRTX', bytes(vb)) + iff_chunk('MATL', MATL) + iff_chunk('FACE', bytes(fb))
    data  = iff_chunk('MODL', inner)
    with open(path, 'wb') as f:
        f.write(data)
    print(f"  {len(data):5d}B  {path}")

def both_sides(faces):
    return faces + [(c,b,a) for a,b,c in faces]

# ── Mesh builders: floor + side walls ────────────────────────────────────────
# All meshes centered at local origin. Object position placed in .lev.
# +Y is course-forward, +Z is up, +X is course-right.
# Side walls rise +wh above z=0 on the left (x=-hx) and right (x=+hx) edges.

WH = 0.4   # wall height

def flat_with_walls(hx, hy, wh=WH, path=None):
    """Flat floor ±hx wide ±hy long, with side walls."""
    verts = [
        # floor (z=0)
        (0.0, 0.0, -hx, -hy, 0.0),  # 0
        (1.0, 0.0,  hx, -hy, 0.0),  # 1
        (1.0, 1.0,  hx,  hy, 0.0),  # 2
        (0.0, 1.0, -hx,  hy, 0.0),  # 3
        # left wall top verts (x=-hx, z=wh)
        (0.0, 0.0, -hx, -hy, wh),   # 4
        (0.0, 1.0, -hx,  hy, wh),   # 5
        # right wall top verts (x=+hx, z=wh)
        (1.0, 0.0,  hx, -hy, wh),   # 6
        (1.0, 1.0,  hx,  hy, wh),   # 7
    ]
    faces = both_sides([
        # floor
        (0,1,2),(0,2,3),
        # left wall
        (0,5,4),(0,3,5),
        # right wall
        (1,6,7),(1,7,2),
    ])
    write_mesh(verts, faces, path)

def slope_with_walls(hx, hy, z_drop, wh=WH, path=None):
    """
    Slope from z=0 (y=-hy) to z=-z_drop (y=+hy), with side walls.
    Walls follow the slope so their tops are at z+wh above the floor.
    """
    verts = [
        # floor
        (0.0, 0.0, -hx, -hy,        0.0),   # 0 top-left
        (1.0, 0.0,  hx, -hy,        0.0),   # 1 top-right
        (1.0, 1.0,  hx,  hy,    -z_drop),   # 2 bot-right
        (0.0, 1.0, -hx,  hy,    -z_drop),   # 3 bot-left
        # left wall tops
        (0.0, 0.0, -hx, -hy,        wh  ),  # 4
        (0.0, 1.0, -hx,  hy, -z_drop+wh ),  # 5
        # right wall tops
        (1.0, 0.0,  hx, -hy,        wh  ),  # 6
        (1.0, 1.0,  hx,  hy, -z_drop+wh ),  # 7
    ]
    faces = both_sides([
        (0,1,2),(0,2,3),
        (0,5,4),(0,3,5),
        (1,6,7),(1,7,2),
    ])
    write_mesh(verts, faces, path)

def x_flat_with_walls(hx_along, hy_width, wh=WH, path=None):
    """
    Flat section that extends along the X axis (long in X, narrow in Y).
    Walls run along Y edges (y=±hy_width).
    """
    verts = [
        # floor
        (-hx_along, -hy_width, 0.0),
        ( hx_along, -hy_width, 0.0),
        ( hx_along,  hy_width, 0.0),
        (-hx_along,  hy_width, 0.0),
        # near wall (y=-hy) top verts
        (-hx_along, -hy_width, wh),
        ( hx_along, -hy_width, wh),
        # far wall (y=+hy) top verts
        (-hx_along,  hy_width, wh),
        ( hx_along,  hy_width, wh),
    ]
    # convert (x,y,z) → (u,v,x,y,z) for write_mesh
    def v(x,y,z): return (0.0,0.0,x,y,z)
    verts2 = [v(*p) for p in verts]
    faces = both_sides([
        (0,1,2),(0,2,3),
        (0,4,5),(0,5,1),  # near wall
        (3,2,7),(3,7,6),  # far wall
    ])
    write_mesh(verts2, faces, path)

# ── Course layout ─────────────────────────────────────────────────────────────
#
# Course goes in two legs:
#   Leg 1: along +Y from Y=0..42, centered on X=0
#   Leg 2: along -X from X=0..-22, centered on Y=40
#
# (We stay within ±100 room bbox)

def generate_meshes():
    print("Generating meshes:")

    # 1. Start platform — wide, flat, 12×10
    flat_with_walls(6, 5,  path="mm1_start.iff")

    # 2. First wide ramp — gently descends from Z=12 to Z=4 over 24 units
    slope_with_walls(6, 12, z_drop=8, path="mm1_ramp1.iff")

    # 3. Corner junction — flat 12×8 (turn point, wide enough to manoeuvre)
    flat_with_walls(6, 4, path="mm1_corner.iff")

    # 4. X-bridge — goes left along -X axis; narrow (3 wide in Y), 11 long in X
    x_flat_with_walls(hx_along=11, hy_width=1.5, path="mm1_xbridge.iff")

    # 5. Left landing — flat 8×6 at end of bridge
    flat_with_walls(4, 3, path="mm1_landing.iff")

    # 6. Final ramp — descends from Z=4 to Z=0 over 10 units, medium width
    slope_with_walls(4, 5, z_drop=4, path="mm1_ramp2.iff")

    # 7. Goal platform — flat 10×8
    flat_with_walls(5, 4, path="mm1_goal.iff")


# ── Section placement ──────────────────────────────────────────────────────────
#
# Each entry: (name, mesh, px, py, pz, bbox_min, bbox_max, slopeA,B,C,D)
# slope{A,B,C} = surface normal; D = 0 (local coords, mesh passes through origin at z=0)

def _slope_normal(hy, drop):
    ny, nz = drop, 2.0*hy
    m = math.sqrt(ny*ny + nz*nz)
    return 0.0, ny/m, nz/m

FLAT  = (0.0, 0.0, 1.0, 0.0)   # sA,sB,sC,sD for a flat floor

def _slope_fields(hy, drop):
    sA, sB, sC = _slope_normal(hy, drop)
    return sA, sB, sC, 0.0

SECTIONS = [
    # 1. Start platform: flat 12×10 at Z=12, centred Y=5
    dict(name="Mm1Start",   mesh="mm1_start.iff",
         px=0, py=5,   pz=12,
         bb=((-6,-5,-0.5, 6, 5, WH+0.1)),
         slope=FLAT),

    # 2. First ramp: 12 wide, 24 long, drops 8; top Y=10, bot Y=34; obj at (0,22,12)
    dict(name="Mm1Ramp1",   mesh="mm1_ramp1.iff",
         px=0, py=22,  pz=12,
         bb=((-6,-12,-8.5, 6,12, WH+0.1)),
         slope=_slope_fields(12, 8)),

    # 3. Corner junction: flat 12×8 at Z=4, centred Y=38; Y=34..42
    dict(name="Mm1Corner",  mesh="mm1_corner.iff",
         px=0, py=38,  pz=4,
         bb=((-6,-4,-0.5, 6, 4, WH+0.1)),
         slope=FLAT),

    # 4. X-bridge: goes -X from corner, centred at X=-11 (X=-0..-22), Y=40
    dict(name="Mm1XBridge", mesh="mm1_xbridge.iff",
         px=-11, py=40, pz=4,
         bb=((-11,-1.5,-0.5, 11, 1.5, WH+0.1)),
         slope=FLAT),

    # 5. Left landing: flat 8×6 at Z=4, centred at X=-22, Y=40
    dict(name="Mm1Landing", mesh="mm1_landing.iff",
         px=-22, py=40, pz=4,
         bb=((-4,-3,-0.5, 4, 3, WH+0.1)),
         slope=FLAT),

    # 6. Final ramp: 8 wide, 10 long, drops 4; top Y=34 bot Y=44; centred X=-22,Y=39
    dict(name="Mm1Ramp2",   mesh="mm1_ramp2.iff",
         px=-22, py=39, pz=4,
         bb=((-4,-5,-4.5, 4, 5, WH+0.1)),
         slope=_slope_fields(5, 4)),

    # 7. Goal: flat 10×8 at Z=0, centred X=-22, Y=49
    dict(name="Mm1Goal",    mesh="mm1_goal.iff",
         px=-22, py=49, pz=0,
         bb=((-5,-4,-0.5, 5, 4, WH+0.1)),
         slope=FLAT),
]

# ── .lev text helpers ─────────────────────────────────────────────────────────

def fxs(v):
    return f"{v:.16f}(1.15.16)"

def statplat_obj(s):
    bx0,by0,bz0,bx1,by1,bz1 = s['bb']
    sA,sB,sC,sD = s['slope']
    px,py,pz = s['px'],s['py'],s['pz']
    def F(n,v,l=None): return f"\t\t{{ 'FX32' {{ 'NAME' \"{n}\" }} {{ 'DATA' {fxs(v)} }} {{ 'STR' \"{l or v}\" }} }}"
    def I(n,v,l):      return f"\t\t{{ 'I32'  {{ 'NAME' \"{n}\" }} {{ 'DATA' {v}l }} {{ 'STR' \"{l}\" }} }}"
    def Ie(n,l):       return f"\t\t{{ 'I32'  {{ 'NAME' \"{n}\" }} {{ 'STR' \"{l}\" }} }}"
    def S(n,v):        return f"\t\t{{ 'STR'  {{ 'NAME' \"{n}\" }} {{ 'DATA' \"{v}\" }} }}"
    def Sr(n,v):       return f"\t\t{{ 'STR'  {{ 'NAME' \"{n}\" }} {{ 'STR'  \"{v}\" }} }}"
    def Fi(n,v):       return f"\t\t{{ 'FILE' {{ 'NAME' \"{n}\" }} {{ 'STR'  \"{v}\" }} }}"
    lines = [
        f"\t{{ 'OBJ' ",
        f"\t\t{{ 'NAME' \"{s['name']}\" }}",
        f"\t\t{{ 'VEC3' {{ 'NAME' \"Position\" }} {{ 'DATA' {fxs(px)} {fxs(py)} {fxs(pz)}  //x,y,z\n\t\t\t}} }}",
        f"\t\t{{ 'EULR' {{ 'NAME' \"Orientation\" }} {{ 'DATA' {fxs(0)} {fxs(0)} {fxs(0)}  //a,b,c\n\t\t\t}} }}",
        f"\t\t{{ 'BOX3' {{ 'NAME' \"Global Bounding Box\" }} {{ 'DATA' {fxs(bx0)} {fxs(by0)} {fxs(bz0)} {fxs(bx1)} {fxs(by1)} {fxs(bz1)}  //min-max\n\t\t\t}} }}",
        S("Class Name","statplat"),
        Fi("Mesh Name", s['mesh']),
        I("Model Type",1,"Mesh"),
        I("MovementClass",5,"5"),
        Ie("Mobility","Anchored"),
        F("Mass",0.0,"0.0"),
        I("Moves Between Rooms",0,"False"),
        I("Movement Mailbox",1,"1"),
        F("Step Size",0.55,"0.55"),
        F("Vertical Elasticity",0.5,"0.5"),
        F("Horizontal Elasticity",0.5,"0.5"),
        F("Surface Friction",0.5,"0.5"),
        Ie("At End Of Path","Ping-Pong"),
        Sr("Object To Follow",""),
        Sr("Follow Offset",""),
        F("Running Acceleration",1.0,"1.0"),
        F("Running Deceleration",0.9,"0.9"),
        F("Max Ground Speed",10.0,"10.0"),
        F("hp",32767.0,"32767.0"),
        I("Number Of Local Mailboxes",0,"0"),
        Fi("Mesh Name", s['mesh']),    # duplicate matches marble-madness.lev pattern
        I("Model Type",1,"Mesh"),
        I("Animation Mailbox",1,"1"),
        I("Visibility Mailbox",1,"1"),
        F("slopeA",sA,f"{sA:.6f}"),
        F("slopeB",sB,f"{sB:.6f}"),
        F("slopeC",sC,f"{sC:.6f}"),
        F("slopeD",sD,f"{sD:.6f}"),
        "\t}",
    ]
    return "\n".join(lines)


def generate_lev():
    src = "../marble-madness/marble-madness.lev"
    dst = "marble-madness-2.lev"

    with open(src) as f:
        lines = f.readlines()

    def patch_pos(obj_name, x, y, z):
        tag = f'\t\t{{ \'NAME\' "{obj_name}" }}'
        for i, line in enumerate(lines):
            if line.rstrip() == tag:
                for j in range(i, min(i+6, len(lines))):
                    if "'VEC3'" in lines[j] and '"Position"' in lines[j]:
                        lines[j] = (f"\t\t{{ 'VEC3' {{ 'NAME' \"Position\" }} "
                                    f"{{ 'DATA' {fxs(x)} {fxs(y)} {fxs(z)}  //x,y,z\n")
                        print(f"  patched {obj_name} @ ({x},{y},{z})")
                        return
        print(f"  WARNING: {obj_name} not found")

    # Marble spawns at top of start platform
    patch_pos("Player",    0.0,  5.0, 13.0)
    # Camera: behind-left-above the start, angled down onto course
    patch_pos("Camera",    10.0, -8.0, 22.0)
    patch_pos("CamShot01", 10.0, -8.0, 22.0)
    # Target01 (follow anchor): at marble spawn
    patch_pos("Target01",  0.0,  5.0, 12.5)
    # Target02 (look-at): aimed at start platform surface
    patch_pos("Target02",  0.0,  5.0, 12.0)

    # Cut off old Ramp+Floor, keep 11 infrastructure objects
    obj_starts = [i for i, l in enumerate(lines) if l.strip().startswith("{ 'OBJ'")]
    cut_idx = obj_starts[11]
    print(f"  cutting at line {cut_idx+1}")

    kept = lines[:cut_idx]
    new_objs = "\n".join(statplat_obj(s) for s in SECTIONS)
    out = "".join(kept) + new_objs + "\n}\n"

    # sanity-check brace balance
    depth = sum(1 if c=='{' else -1 if c=='}' else 0 for c in out)
    if depth != 0:
        print(f"  WARNING: brace imbalance {depth:+d}")
    else:
        print(f"  braces balanced ✓")

    with open(dst,'w') as f:
        f.write(out)
    print(f"  wrote {dst} ({len(out)} bytes)")


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    generate_meshes()
    generate_lev()
    print("Done.")
