#!/usr/bin/env python3
"""Generate the classic Snowgoons one-acre yard without changing the Blender scaffold."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from add_ambient_light import _split_objects
from relight_level import _fx, set_euler
from audit_face_hand import chunks

# Metres; all level placement and geometry derive from these dimensions.
WIDTH, DEPTH, TILE = 60, 68, 4
ORIGIN = (0, -12, -0.62)
HEDGE_WIDTH, HEDGE_HEIGHT, SEGMENT = 2, 2.1, 2
PILLAR_WIDTH, PILLAR_HEIGHT = 0.8, 4.2
WALL_THICKNESS, SLAB_DEPTH = 0.25, 1
FOG_START, FOG_END = 40, 100
# These three existing textures are 32². The legacy primitive path quantizes
# atlas coordinates to integer pixels; stay a full texel inside each edge so
# bilinear filtering cannot pull a neighbour's colour into the tiled seams.
UV_INSET = 1 / 31 + 1 / 65536
HERE = Path(__file__).resolve().parent


def fixed(value):
    return round(value * 65536)


def chunk(tag, body):
    return tag + struct.pack("<I", len(body)) + body + b"\0" * (-len(body) % 4)


def mesh_bytes():
    source = (HERE / "quadpatch01.iff").read_bytes()
    size = struct.unpack_from("<I", source, 4)[0]
    materials = next(source[a:b] for tag, _, a, b in chunks(source, 8, size + 8) if tag == b"MATL")
    vertices, faces, vertex_ids = [], [], {}

    def vertex(point, uv):
        uv = tuple(UV_INSET + v*(1-2*UV_INSET) for v in uv)
        packed = struct.pack("<iiIiii", fixed(uv[0]), fixed(uv[1]), 0xFFFFFF,
                             *(fixed(v) for v in point))
        if packed in vertex_ids:
            return vertex_ids[packed]
        vertex_ids[packed] = len(vertices)
        vertices.append(packed)
        return len(vertices) - 1

    def quad(points, material, flip_u=False, flip_v=False):
        uvs = [(1-u if flip_u else u, 1-v if flip_v else v)
               for u,v in [(0, 0), (1, 0), (1, 1), (0, 1)]]
        ids = [vertex(p, uv) for p, uv in zip(points, uvs)]
        faces.extend([(ids[0], ids[1], ids[2], material), (ids[0], ids[2], ids[3], material)])

    nx, ny = WIDTH // TILE, DEPTH // TILE
    for j in range(ny + 1):
        for i in range(nx + 1):
            vertex((-WIDTH / 2 + i * TILE, -DEPTH / 2 + j * TILE, 0), (i % 2, j % 2))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.extend([(a, a + 1, a + nx + 2, 5), (a, a + nx + 2, a + nx + 1, 5)])

    # Walk counterclockwise around the lawn: left of each segment is inward.
    corners = [(-WIDTH/2, -DEPTH/2), (WIDTH/2, -DEPTH/2),
               (WIDTH/2, DEPTH/2), (-WIDTH/2, DEPTH/2)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        count = int((abs(b[0]-a[0]) + abs(b[1]-a[1])) / SEGMENT)
        dx, dy = (b[0]-a[0])/count, (b[1]-a[1])/count
        ox, oy = dy/SEGMENT * HEDGE_WIDTH, -dx/SEGMENT * HEDGE_WIDTH
        for i in range(count):
            x, y = a[0]+i*dx, a[1]+i*dy
            xx, yy = x+dx, y+dy
            quad([(xx,yy,0), (x,y,0), (x,y,HEDGE_HEIGHT), (xx,yy,HEDGE_HEIGHT)], 2, flip_u=bool(i%2))
            quad([(x,y,HEDGE_HEIGHT), (x+ox,y+oy,HEDGE_HEIGHT),
                  (xx+ox,yy+oy,HEDGE_HEIGHT), (xx,yy,HEDGE_HEIGHT)], 1, flip_v=bool(i%2))

    for sx in [-1, 1]:
        for sy in [-1, 1]:
            x, y = sx*WIDTH/2, sy*DEPTH/2
            lo, hi = sorted([x, x+sx*HEDGE_WIDTH]), sorted([y, y+sy*HEDGE_WIDTH])
            quad([(lo[0],hi[0],HEDGE_HEIGHT), (lo[1],hi[0],HEDGE_HEIGHT),
                  (lo[1],hi[1],HEDGE_HEIGHT), (lo[0],hi[1],HEDGE_HEIGHT)], 1)
            cx, cy = x+sx*HEDGE_WIDTH/2, y+sy*HEDGE_WIDTH/2
            r = PILLAR_WIDTH/2
            ring = [(cx-r,cy-r),(cx+r,cy-r),(cx+r,cy+r),(cx-r,cy+r)]
            for p, q in zip(ring, ring[1:]+ring[:1]):
                quad([(*q,HEDGE_HEIGHT),(*p,HEDGE_HEIGHT),(*p,PILLAR_HEIGHT),(*q,PILLAR_HEIGHT)], 1)
            quad([(*p,PILLAR_HEIGHT) for p in ring], 1)

    return chunk(b"MODL", chunk(b"VRTX", b"".join(vertices)) + chunk(b"MATL", materials)
                 + chunk(b"FACE", b"".join(struct.pack("<hhhh", *f) for f in faces)))


def set_field(block, name, values):
    pattern = r'("' + re.escape(name) + r'"\s*\}\s*\{\s*\x27DATA\x27\s+)' + r'\s+'.join([r'-?\d+\.\d+\(1\.15\.16\)']*len(values))
    block, count = re.subn(pattern, lambda m: m[1] + " ".join(_fx(v) for v in values), block, count=1)
    if count != 1:
        raise ValueError(f"missing {name}")
    if len(values) == 1:
        label = r'("' + re.escape(name) + r'"\s*\}\s*\{\s*\x27DATA\x27[^}]*\}\s*\{\s*\x27STR\x27\s+)"[^"]*"'
        block = re.sub(label, lambda m: m[1] + f'"{values[0]:g}"', block, count=1)
    return block


def patch_level(text):
    lines = text.splitlines(keepends=True)
    seen = set()
    w, d = WIDTH/2, DEPTH/2
    boxes = {
        "statplat_15": (ORIGIN, (-w-HEDGE_WIDTH,-d-HEDGE_WIDTH,-SLAB_DEPTH,w+HEDGE_WIDTH,d+HEDGE_WIDTH,0)),
        "statplat_19": ((0,ORIGIN[1]-d-WALL_THICKNESS/2,ORIGIN[2]), (-w-HEDGE_WIDTH,-WALL_THICKNESS/2,0,w+HEDGE_WIDTH,WALL_THICKNESS/2,HEDGE_HEIGHT)),
        "statplat_20": ((w+WALL_THICKNESS/2,ORIGIN[1],ORIGIN[2]), (-WALL_THICKNESS/2,-d,0,WALL_THICKNESS/2,d,HEDGE_HEIGHT)),
        "statplat_21": ((-w-WALL_THICKNESS/2,ORIGIN[1],ORIGIN[2]), (-WALL_THICKNESS/2,-d,0,WALL_THICKNESS/2,d,HEDGE_HEIGHT)),
        "statplat_22": ((0,ORIGIN[1]+d+WALL_THICKNESS/2,ORIGIN[2]), (-w-HEDGE_WIDTH,-WALL_THICKNESS/2,0,w+HEDGE_WIDTH,WALL_THICKNESS/2,HEDGE_HEIGHT)),
    }
    # Box-body position updates use the actor origin. Centre local bounds so a
    # later update cannot lose the local box-centre offset (notably slab Z).
    boxes = {name: (tuple(position[i] + (box[i]+box[i+3])/2 for i in range(3)),
                    tuple(box[i] - (box[i%3]+box[i%3+3])/2 for i in range(6)))
             for name, (position, box) in boxes.items()}
    wanted = {"statplat_2", "player_33", "camera_8", *boxes}
    for start, end in reversed(_split_objects(text)):
        block = "".join(lines[start:end])
        name = re.search(r"'NAME'\s+\"([^\"]+)\"", block)[1]
        if name not in wanted:
            continue
        seen.add(name)
        if name == "statplat_2":
            # The slab/walls own collision. An anchored Platform renders the
            # yard without StatPlat's automatic trimesh body; overlapping that
            # double-sided, tiled floor with the slab causes contact seam hops.
            block, n = re.subn(r'("Class Name"\s*\}\s*\{\s*\x27DATA\x27\s+)"[^"]+"', lambda m: m[1]+'"platform"', block, count=1)
            assert n == 1
            block, n = re.subn(r'("MovementClass"\s*\}\s*\{\s*\x27DATA\x27\s+)\d+l', lambda m: m[1]+'7l', block, count=1)
            assert n == 1
            block = re.sub(r'("MovementClass"\s*\}.*?\x27STR\x27\s+)"\d+"', lambda m: m[1]+'"7"', block, count=1, flags=re.S)
            block = set_field(block, "Position", ORIGIN)
            block = set_euler(block, 0, 0, 0)
            block = set_field(block, "Global Bounding Box", (-w-HEDGE_WIDTH,-d-HEDGE_WIDTH,0,w+HEDGE_WIDTH,d+HEDGE_WIDTH,PILLAR_HEIGHT))
            block, n = re.subn(r'("Mesh Name"\s*\}\s*\{\s*\x27STR\x27\s+)"[^"]+"', lambda m: m[1]+'"yard01.iff"', block, count=1)
            assert n == 1
        elif name in boxes:
            position, bounds = boxes[name]
            block = set_field(block, "Position", position)
            block = set_euler(block, 0, 0, 0)
            block = set_field(block, "Global Bounding Box", bounds)
        elif name == "player_33":
            # Preserve the authored horizontal spawn.
            pattern = r'("Position"\s*\}\s*\{\s*\x27DATA\x27\s+)(-?\d+\.\d+)\(1\.15\.16\)\s+(-?\d+\.\d+)\(1\.15\.16\)'
            m = re.search(pattern, block)
            block = set_field(block, "Position", (float(m[2]), float(m[3]), ORIGIN[2]+0.02))
        else:
            block = set_field(block, "FoggingStartDistance", (FOG_START,))
            block = set_field(block, "FoggingCompleteDistance", (FOG_END,))
        replacement = block.splitlines(keepends=True)
        assert len(replacement) == end-start
        # Preserve the historical export formatting except on rewritten lines.
        replacement = [line.rstrip() + ("\n" if line.endswith("\n") else "")
                       if line != old else line
                       for line, old in zip(replacement, lines[start:end])]
        lines[start:end] = replacement
    if seen != wanted:
        raise ValueError(f"missing objects: {wanted-seen}")
    return "".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lev", action="store_true", help="also update the classic snowgoons.lev")
    args = parser.parse_args()
    target = HERE / "yard01.iff"
    target.write_bytes(mesh_bytes())
    if args.lev:
        level = HERE / "snowgoons.lev"
        level.write_text(patch_level(level.read_text()))
    print(f"{target}: {WIDTH*DEPTH} m² ({WIDTH*DEPTH/4046.8564224:.3f} acres)")


if __name__ == "__main__":
    main()
