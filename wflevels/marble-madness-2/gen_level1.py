#!/usr/bin/env python3
"""
Generate mm_practice course (S-curve trough, ~36 m × 18 m × 4 m drop).
Creates mesh .iff files and rewrites marble-madness-2.lev.
Run from wflevels/marble-madness-2/.

Course layout (world coords, +Y = course-forward, +Z = up):

  Spawn              Y=5    X=0    Z=13   (Player object, unchanged from M1)
  Start platform     Y= 3.. 7  X=[-5,5]   Z=12  flat
  Ramp A (+X lean)   Y= 7..15  X=[-3,9]   Z=12→10.5   (leans right)
  Bridge 1 (wide)    Y=15..19  X=[-7,7]   Z=10.5  flat
  Ramp B (-X lean)   Y=19..27  X=[-9,3]   Z=10.5→9    (leans left)
  Bridge 2 (wide)    Y=27..31  X=[-7,7]   Z=9     flat
  Final ramp         Y=31..35  X=[-5,5]   Z=9→8
  Goal platform      Y=35..39  X=[-5,5]   Z=8     flat

Z drop: 1.5 + 1.5 + 1.0 = 4 m total.
S-curve: course alternates right (+X) then left (-X) then center,
         funnelling marble through two direction changes.
"""

import struct, math, sys, os

GREY = 0x00AAAAAA

# ── IFF helpers ───────────────────────────────────────────────────────────────

def fx(v):
    return int(round(v * 65536))

def iff_chunk(tag, payload):
    b = tag.encode('ascii')[:4].ljust(4, b'\x00')
    sz = len(payload)
    pad = (4 - sz % 4) % 4
    return b + struct.pack('<I', sz) + payload + b'\x00' * pad

def make_grey_matl():
    return struct.pack('<iI', 0x00, GREY) + b'\x00' * 256

MATL = make_grey_matl()

def write_mesh(verts, faces, path):
    """verts = (u,v,x,y,z); faces = (i,j,k)."""
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
    return faces + [(c, b, a) for a, b, c in faces]

# ── Mesh builders ─────────────────────────────────────────────────────────────

WH = 0.4  # wall height above floor

def flat_with_walls(hx, hy, wh=WH, path=None):
    """Flat floor ±hx wide ±hy long, side walls of height wh."""
    verts = [
        (0.0, 0.0, -hx, -hy, 0.0),  # 0 near-left  floor
        (1.0, 0.0,  hx, -hy, 0.0),  # 1 near-right floor
        (1.0, 1.0,  hx,  hy, 0.0),  # 2 far-right  floor
        (0.0, 1.0, -hx,  hy, 0.0),  # 3 far-left   floor
        (0.0, 0.0, -hx, -hy,  wh),  # 4 near-left  wall top
        (0.0, 1.0, -hx,  hy,  wh),  # 5 far-left   wall top
        (1.0, 0.0,  hx, -hy,  wh),  # 6 near-right wall top
        (1.0, 1.0,  hx,  hy,  wh),  # 7 far-right  wall top
    ]
    faces = both_sides([
        (0, 1, 2), (0, 2, 3),   # floor
        (0, 5, 4), (0, 3, 5),   # left wall
        (1, 6, 7), (1, 7, 2),   # right wall
    ])
    write_mesh(verts, faces, path)

def slope_with_walls(hx, hy, z_drop, wh=WH, path=None):
    """
    Slope from z=0 (y=-hy) to z=-z_drop (y=+hy), with side walls.
    Walls follow the slope so their tops are at floor+wh.
    """
    verts = [
        (0.0, 0.0, -hx, -hy,         0.0),  # 0
        (1.0, 0.0,  hx, -hy,         0.0),  # 1
        (1.0, 1.0,  hx,  hy,    -z_drop),   # 2
        (0.0, 1.0, -hx,  hy,    -z_drop),   # 3
        (0.0, 0.0, -hx, -hy,         wh ),  # 4
        (0.0, 1.0, -hx,  hy, -z_drop+wh),   # 5
        (1.0, 0.0,  hx, -hy,         wh ),  # 6
        (1.0, 1.0,  hx,  hy, -z_drop+wh),   # 7
    ]
    faces = both_sides([
        (0, 1, 2), (0, 2, 3),
        (0, 5, 4), (0, 3, 5),
        (1, 6, 7), (1, 7, 2),
    ])
    write_mesh(verts, faces, path)

# ── Course geometry ───────────────────────────────────────────────────────────

def generate_meshes():
    print("Generating meshes:")
    flat_with_walls(5, 2,                  path="mm1_start.iff")    # 1. start
    slope_with_walls(6, 4, z_drop=1.5,    path="mm1_ramp1.iff")    # 2. ramp A
    flat_with_walls(7, 2,                  path="mm1_corner.iff")   # 3. bridge 1
    slope_with_walls(6, 4, z_drop=1.5,    path="mm1_xbridge.iff")  # 4. ramp B
    flat_with_walls(7, 2,                  path="mm1_landing.iff")  # 5. bridge 2
    slope_with_walls(5, 2, z_drop=1.0,    path="mm1_ramp2.iff")    # 6. final ramp
    flat_with_walls(5, 2,                  path="mm1_goal.iff")     # 7. goal


# ── Section placement ─────────────────────────────────────────────────────────

def _slope_fields(hy, drop):
    """Surface normal (sA,sB,sC,sD) for a slope rising in -Y, descending in +Y."""
    ny, nz = drop, 2.0 * hy
    m = math.sqrt(ny * ny + nz * nz)
    return 0.0, ny / m, nz / m, 0.0

FLAT = (0.0, 0.0, 1.0, 0.0)

#  World Y extents and Z for each section (all connected with no gaps):
#
#  1. Start:    Y= 3.. 7  Z=12      flat   px=0
#  2. Ramp A:   Y= 7..15  Z=12→10.5 slope  px=+3  (leans right)
#  3. Bridge 1: Y=15..19  Z=10.5    flat   px=0
#  4. Ramp B:   Y=19..27  Z=10.5→9  slope  px=-3  (leans left)
#  5. Bridge 2: Y=27..31  Z=9       flat   px=0
#  6. Ramp C:   Y=31..35  Z=9→8     slope  px=0   (straight to goal)
#  7. Goal:     Y=35..39  Z=8       flat   px=0

SECTIONS = [
    # 1. Start platform
    dict(name="MmpStart",   mesh="mm1_start.iff",
         px=0,  py=5,   pz=12,
         bb=(-5, -2, -0.5,  5,  2, WH + 0.1),
         slope=FLAT),

    # 2. Ramp A: hx=6, hy=4, z_drop=1.5; world X=-3..9, Y=7..15
    dict(name="MmpRampA",   mesh="mm1_ramp1.iff",
         px=3,  py=11,  pz=12,
         bb=(-6, -4, -2.0,  6,  4, WH + 0.1),
         slope=_slope_fields(4, 1.5)),

    # 3. Bridge 1: hx=7, hy=2; world X=-7..7, Y=15..19
    dict(name="MmpBridge1", mesh="mm1_corner.iff",
         px=0,  py=17,  pz=10.5,
         bb=(-7, -2, -0.5,  7,  2, WH + 0.1),
         slope=FLAT),

    # 4. Ramp B: hx=6, hy=4, z_drop=1.5; world X=-9..3, Y=19..27
    dict(name="MmpRampB",   mesh="mm1_xbridge.iff",
         px=-3, py=23,  pz=10.5,
         bb=(-6, -4, -2.0,  6,  4, WH + 0.1),
         slope=_slope_fields(4, 1.5)),

    # 5. Bridge 2: hx=7, hy=2; world X=-7..7, Y=27..31
    dict(name="MmpBridge2", mesh="mm1_landing.iff",
         px=0,  py=29,  pz=9.0,
         bb=(-7, -2, -0.5,  7,  2, WH + 0.1),
         slope=FLAT),

    # 6. Final ramp: hx=5, hy=2, z_drop=1.0; world X=-5..5, Y=31..35
    dict(name="MmpRampC",   mesh="mm1_ramp2.iff",
         px=0,  py=33,  pz=9.0,
         bb=(-5, -2, -1.5,  5,  2, WH + 0.1),
         slope=_slope_fields(2, 1.0)),

    # 7. Goal platform: hx=5, hy=2; world X=-5..5, Y=35..39
    dict(name="MmpGoal",    mesh="mm1_goal.iff",
         px=0,  py=37,  pz=8.0,
         bb=(-5, -2, -0.5,  5,  2, WH + 0.1),
         slope=FLAT),
]


# ── .lev helpers ──────────────────────────────────────────────────────────────

def fxs(v):
    return f"{v:.16f}(1.15.16)"

def statplat_obj(s):
    bx0, by0, bz0, bx1, by1, bz1 = s['bb']
    sA, sB, sC, sD = s['slope']
    px, py, pz = s['px'], s['py'], s['pz']

    def F(n, v, l=None):
        return f"\t\t{{ 'FX32' {{ 'NAME' \"{n}\" }} {{ 'DATA' {fxs(v)} }} {{ 'STR' \"{l or v}\" }} }}"
    def I(n, v, l):
        return f"\t\t{{ 'I32'  {{ 'NAME' \"{n}\" }} {{ 'DATA' {v}l }} {{ 'STR' \"{l}\" }} }}"
    def Ie(n, l):
        return f"\t\t{{ 'I32'  {{ 'NAME' \"{n}\" }} {{ 'STR' \"{l}\" }} }}"
    def S(n, v):
        return f"\t\t{{ 'STR'  {{ 'NAME' \"{n}\" }} {{ 'DATA' \"{v}\" }} }}"
    def Sr(n, v):
        return f"\t\t{{ 'STR'  {{ 'NAME' \"{n}\" }} {{ 'STR'  \"{v}\" }} }}"
    def Fi(n, v):
        return f"\t\t{{ 'FILE' {{ 'NAME' \"{n}\" }} {{ 'STR'  \"{v}\" }} }}"

    lines = [
        f"\t{{ 'OBJ' ",
        f"\t\t{{ 'NAME' \"{s['name']}\" }}",
        f"\t\t{{ 'VEC3' {{ 'NAME' \"Position\" }} {{ 'DATA' {fxs(px)} {fxs(py)} {fxs(pz)}  //x,y,z\n\t\t\t}} }}",
        f"\t\t{{ 'EULR' {{ 'NAME' \"Orientation\" }} {{ 'DATA' {fxs(0)} {fxs(0)} {fxs(0)}  //a,b,c\n\t\t\t}} }}",
        f"\t\t{{ 'BOX3' {{ 'NAME' \"Global Bounding Box\" }} {{ 'DATA' {fxs(bx0)} {fxs(by0)} {fxs(bz0)} {fxs(bx1)} {fxs(by1)} {fxs(bz1)}  //min-max\n\t\t\t}} }}",
        S("Class Name", "statplat"),
        Fi("Mesh Name", s['mesh']),
        I("Model Type", 1, "Mesh"),
        I("MovementClass", 5, "5"),
        Ie("Mobility", "Anchored"),
        F("Mass", 0.0, "0.0"),
        I("Moves Between Rooms", 0, "False"),
        I("Movement Mailbox", 1, "1"),
        F("Step Size", 0.55, "0.55"),
        F("Vertical Elasticity", 0.5, "0.5"),
        F("Horizontal Elasticity", 0.5, "0.5"),
        F("Surface Friction", 0.5, "0.5"),
        Ie("At End Of Path", "Ping-Pong"),
        Sr("Object To Follow", ""),
        Sr("Follow Offset", ""),
        F("Running Acceleration", 1.0, "1.0"),
        F("Running Deceleration", 0.9, "0.9"),
        F("Max Ground Speed", 10.0, "10.0"),
        F("hp", 32767.0, "32767.0"),
        I("Number Of Local Mailboxes", 0, "0"),
        Fi("Mesh Name", s['mesh']),    # duplicate matches marble-madness.lev pattern
        I("Model Type", 1, "Mesh"),
        I("Animation Mailbox", 1, "1"),
        I("Visibility Mailbox", 1, "1"),
        F("slopeA", sA, f"{sA:.6f}"),
        F("slopeB", sB, f"{sB:.6f}"),
        F("slopeC", sC, f"{sC:.6f}"),
        F("slopeD", sD, f"{sD:.6f}"),
        "\t}",
    ]
    return "\n".join(lines)


# ── .lev generation ───────────────────────────────────────────────────────────

def generate_lev():
    src = "../marble-madness/marble-madness.lev"
    dst = "marble-madness-2.lev"

    with open(src) as f:
        lines = f.readlines()

    def patch_pos(obj_name, x, y, z):
        tag = f'\t\t{{ \'NAME\' "{obj_name}" }}'
        for i, line in enumerate(lines):
            if line.rstrip() == tag:
                for j in range(i, min(i + 6, len(lines))):
                    if "'VEC3'" in lines[j] and '"Position"' in lines[j]:
                        lines[j] = (f"\t\t{{ 'VEC3' {{ 'NAME' \"Position\" }} "
                                    f"{{ 'DATA' {fxs(x)} {fxs(y)} {fxs(z)}  //x,y,z\n")
                        print(f"  patched {obj_name} pos @ ({x},{y},{z})")
                        return
        print(f"  WARNING: {obj_name} not found")

    def patch_orient(obj_name, a, b, c):
        tag = f'\t\t{{ \'NAME\' "{obj_name}" }}'
        for i, line in enumerate(lines):
            if line.rstrip() == tag:
                for j in range(i, min(i + 8, len(lines))):
                    if "'EULR'" in lines[j] and '"Orientation"' in lines[j]:
                        lines[j] = (f"\t\t{{ 'EULR' {{ 'NAME' \"Orientation\" }} "
                                    f"{{ 'DATA' {fxs(a)} {fxs(b)} {fxs(c)}  //a,b,c\n")
                        print(f"  patched {obj_name} orient a={a:.4f} b={b:.4f} c={c:.4f}")
                        return
        print(f"  WARNING: {obj_name} orient not found")

    def patch_script(obj_name, new_script_file_text):
        """Replace the Script STR value of obj_name.
        new_script_file_text is the exact bytes that go between the quotes in the .lev file
        (use raw strings: r'\\' stays as two backslashes, r'\n' stays as backslash-n).
        """
        tag = f'\t\t{{ \'NAME\' "{obj_name}" }}'
        for i, line in enumerate(lines):
            if line.rstrip() == tag:
                for j in range(i, min(i + 60, len(lines))):
                    if '"Script"' in lines[j] and "{ 'STR'" in lines[j]:
                        lines[j] = (f"\t\t{{ 'STR' {{ 'NAME' \"Script\" }}"
                                    f" {{ 'STR' \"{new_script_file_text}\" }} }}\n")
                        print(f"  patched {obj_name} Script")
                        return
        print(f"  WARNING: {obj_name} Script not found")

    # ── Marble spawn and camera (unchanged from M1) ───────────────────────────
    patch_pos("Player",    0.0,  5.0, 13.0)
    # C = π/4 so fwd=(sin C,cos C)=(√2/2,√2/2): UP+LEFT = pure +Y.
    patch_orient("Player", 0.0,  0.0, math.pi / 4)
    patch_pos("Camera",    -18.0, -13.0, 28.0)
    patch_pos("CamShot01", -18.0, -13.0, 28.0)
    patch_pos("Target01",   0.0,   5.0, 13.5)
    patch_pos("Target02",   0.0,   5.0, 13.5)

    # ── Player script: input + goal detection + death respawn ───────────────────
    # Spawn: (0, 5, 13). Death trigger: Z < -90 (room floor is Z = -97).
    player_script = (
        r'\\ wf'
        r'\n: respawn  0 INDEXOF_X_POS write-mailbox  5 INDEXOF_Y_POS write-mailbox  13 INDEXOF_Z_POS write-mailbox  0 INDEXOF_XSPEED write-mailbox  0 INDEXOF_YSPEED write-mailbox  0 INDEXOF_ZSPEED write-mailbox  1 13 write-mailbox ;'
        r'\nINDEXOF_HARDWARE_JOYSTICK1_RAW read-mailbox INDEXOF_INPUT write-mailbox'
        r'\nINDEXOF_Y_POS read-mailbox 34 > if 1 INDEXOF_END_OF_LEVEL write-mailbox then'
        r'\nINDEXOF_Z_POS read-mailbox -90 < if respawn then'
        r'\n'
    )
    patch_script("Player", player_script)

    # ── Cut old course objects, append new sections ───────────────────────────
    obj_starts = [i for i, l in enumerate(lines) if l.strip().startswith("{ 'OBJ'")]
    cut_idx = obj_starts[11]
    print(f"  cutting at line {cut_idx + 1} (keeping {11} infrastructure objects)")

    kept = lines[:cut_idx]
    new_objs = "\n".join(statplat_obj(s) for s in SECTIONS)
    out = "".join(kept) + new_objs + "\n}\n"

    depth = sum(1 if c == '{' else -1 if c == '}' else 0 for c in out)
    if depth != 0:
        print(f"  WARNING: brace imbalance {depth:+d}")
    else:
        print(f"  braces balanced ✓")

    with open(dst, 'w') as f:
        f.write(out)
    print(f"  wrote {dst} ({len(out)} bytes)")


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    generate_meshes()
    generate_lev()
    print("Done.")
