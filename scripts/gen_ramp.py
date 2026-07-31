#!/usr/bin/env python3
"""Generate ramp.iff for mm_practice — simple downward-sloping ramp surface."""

import struct
import sys


def fx(v):
    """Float to 1.15.16 fixed-point integer."""
    return int(round(v * 65536))


def iff_chunk(tag, payload):
    """Serialize one IFF chunk: 4-byte ASCII tag + LE uint32 size + payload + 4-byte pad."""
    tag_bytes = tag.encode('ascii')[:4].ljust(4, b'\x00')
    size = len(payload)
    pad = (4 - size % 4) % 4
    return tag_bytes + struct.pack('<I', size) + payload + b'\x00' * pad


# ── Ramp geometry (object-local coords; object placed at world (0, 10, 2)) ──
#
# World-space vertex positions (local + object_pos):
#  v0 (-5,-10, 2)+(0,10,2) = (-5, 0, 4)  ← top-left  (high / spawn end)
#  v1 ( 5,-10, 2)+(0,10,2) = ( 5, 0, 4)  ← top-right
#  v2 ( 5, 10,-2)+(0,10,2) = ( 5,20, 0)  ← bottom-right (low / goal end)
#  v3 (-5, 10,-2)+(0,10,2) = (-5,20, 0)  ← bottom-left
#
#  (u,  v,    x,     y,    z)
VERTS = [
    (0.0, 0.0,  -5.0, -10.0,  2.0),   # v0
    (1.0, 0.0,   5.0, -10.0,  2.0),   # v1
    (1.0, 1.0,   5.0,  10.0, -2.0),   # v2
    (0.0, 1.0,  -5.0,  10.0, -2.0),   # v3
]

# Two triangles (top face, CCW from above) + back-faces for double-sided
#  (v1, v2, v3, material_index)
FACES = [
    (0, 1, 2, 0),  # upper-right tri, top face
    (0, 2, 3, 0),  # lower-left  tri, top face
    (0, 2, 1, 0),  # upper-right tri, back face
    (0, 3, 2, 0),  # lower-left  tri, back face
]

# ── VRTX chunk ────────────────────────────────────────────────────────────────
vrtx = bytearray()
for u, v, x, y, z in VERTS:
    vrtx += struct.pack('<iiIiii',
                        fx(u), fx(v), 0x00FFFFFF,
                        fx(x), fx(y), fx(z))

# ── FACE chunk ────────────────────────────────────────────────────────────────
face_data = bytearray()
for v1, v2, v3, mat in FACES:
    face_data += struct.pack('<hhhh', v1, v2, v3, mat)

# ── MATL chunk — 1 material: textured G_SnowyGrass1.tga ───────────────────────
TEX_NAME = b'G_SnowyGrass1.tga'
mat_flags = 0x02                   # bit 1 = textured
mat_color = 0x00FFFFFF             # white tint
tex_bytes  = TEX_NAME[:255].ljust(256, b'\x00')
matl = struct.pack('<iI', mat_flags, mat_color) + tex_bytes

# ── Assemble MODL ─────────────────────────────────────────────────────────────
inner = (
    iff_chunk('VRTX', bytes(vrtx)) +
    iff_chunk('MATL', matl) +
    iff_chunk('FACE', bytes(face_data))
)
modl = iff_chunk('MODL', inner)

out = sys.argv[1] if len(sys.argv) > 1 else 'ramp.iff'
with open(out, 'wb') as f:
    f.write(modl)
print(f"Wrote {len(modl)} bytes → {out}")
