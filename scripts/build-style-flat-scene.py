#!/usr/bin/env python3
"""Build the untextured style scenes for the strict GL-vs-Metal check (reef plan step 14).

style_flat_realistic and style_flat_anime are copies of the geometry-only scenes
(scripts/build-style-geometry-scene.py; same Camera, fog, lights and S1/S3 fields)
whose only visible mesh is written here: a subdivided floor and back wall plus
five rotated boxes, every face a flat material colour with no texture, dynamically
lit (material flags 0). Nothing samples a texture and nothing is smaller than a few
pixels, so GL and Metal differ only where the shading math or large-polygon
rasterization does. Run in the level-build container (WF_CONTAINER_IMAGE=blender)
with --build, after build-style-geometry-scene.py.
"""
import argparse
import math
import re
import struct
import subprocess
from pathlib import Path

from level_asset_links import link_source_assets

ROOT = Path(__file__).resolve().parents[1]
SCENES = {'style_flat_realistic': 'style_geom_realistic', 'style_flat_anime': 'style_geom_anime'}
MESH = 'style_flat_shell.iff'
COLORS = [0xC8BC9A, 0x6E7F86, 0xB8553A, 0x3F7F5A, 0xD9C24A, 0x5A6FB8, 0x9A4F8E]  # floor, wall, boxes
VISIBILITY = re.compile(r"(\{ 'I32' \{ 'NAME' \"Visibility Mailbox\" \} \{ 'DATA' )\d+l( \} \{ 'STR' )\"\d+\"")
# (centre x, y, half size, height, heading in degrees, colour index)
BOXES = [(-5.0, -0.5, .8, 1.6, 20, 2), (-2.4, 1.2, .9, 2.4, 45, 3), (0.0, -1.4, .7, 1.2, 10, 4),
         (2.6, 0.8, 1.0, 2.0, 60, 5), (5.2, -0.2, .8, 2.8, 30, 6)]


def chunk(tag, payload):
    return tag.encode() + struct.pack('<I', len(payload)) + payload + b'\0' * ((4 - len(payload) % 4) % 4)


def fixed(x):
    return int(round(x * 65536))


class Builder:
    def __init__(self):
        self.vertices, self.faces = [], []

    def quad(self, a, b, c, d, material):
        """Two triangles, counter-clockwise seen from the lit side."""
        base = len(self.vertices)
        self.vertices += [(p, COLORS[material]) for p in (a, b, c, d)]
        self.faces += [(base, base + 1, base + 2, material), (base, base + 2, base + 3, material)]

    def grid(self, origin, du, dv, nu, nv, material):
        for i in range(nu):
            for j in range(nv):
                p = lambda s, t: tuple(origin[k] + du[k] * s + dv[k] * t for k in range(3))
                self.quad(p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1), material)

    def box(self, cx, cy, half, height, heading, material):
        c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))
        corner = lambda x, y, z: (cx + x * c - y * s, cy + x * s + y * c, z)
        lo = [corner(x, y, 0.0) for x, y in ((-half, -half), (half, -half), (half, half), (-half, half))]
        hi = [(x, y, height) for x, y, _ in lo]
        self.quad(*hi, material)                                   # top
        for k in range(4):
            n = (k + 1) % 4
            self.quad(lo[k], lo[n], hi[n], hi[k], material)        # sides

    def modl(self):
        vrtx = b''.join(struct.pack('<iiIiii', 0, 0, color, *(fixed(v) for v in p)) for p, color in self.vertices)
        matl = b''.join(struct.pack('<iI', 0, color) + b'\0' * 256 for color in COLORS)
        face = b''.join(struct.pack('<hhhh', *f) for f in self.faces)
        return chunk('MODL', chunk('VRTX', vrtx) + chunk('MATL', matl) + chunk('FACE', face))


def mesh_bytes():
    b = Builder()
    b.grid((-16.0, -3.1, 0.0), (1.0, 0, 0), (0, 6.3 / 6, 0), 32, 6, 0)       # floor, faces up
    b.grid((-16.0, 3.2, 0.0), (1.0, 0, 0), (0, 0, 1.0), 32, 11, 1)           # back wall, faces the camera
    for box in BOXES:
        b.box(*box)
    return b.modl()


def generate(name, source_name, build):
    source_dir = ROOT / 'wflevels' / source_name
    level = (source_dir / f'{source_name}.lev').read_text()
    head, *chunks = level.split("\t{ 'OBJ'")
    out = []
    for block in chunks:
        if '"reef_shell"' in block:
            if block.count('"reef_shell.iff"') < 1:
                raise ValueError('reef_shell has no mesh reference')
            block = block.replace('"reef_shell.iff"', f'"{MESH}"')
        elif any(f'"{rock}"' in block for rock in ('reef_left', 'reef_arch', 'reef_right')):
            block, count = VISIBILITY.subn(lambda m: f'{m[1]}0l{m[2]}"0"', block, count=1)
            if count != 1:
                raise ValueError('rock has no Visibility Mailbox')
        out.append(block)
    target = ROOT / 'wflevels' / name
    target.mkdir(exist_ok=True)
    link_source_assets(source_dir, target)
    (target / MESH).write_bytes(mesh_bytes())
    (target / f'{name}.lev').write_text(head + "\t{ 'OBJ'" + "\t{ 'OBJ'".join(out))
    wrapper = (source_dir / f'{source_name}-standalone.iff.txt').read_text()
    (target / f'{name}-standalone.iff.txt').write_text(wrapper.replace(f'../{source_name}.iff', f'../{name}.iff'))
    if build:
        subprocess.run(['bash', 'wftools/wf_blender/build_level_binary.sh', name], cwd=ROOT, check=True)
    print(name, 'written')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--build', action='store_true', help='also compile both levels with the Rust tools')
    args = ap.parse_args()
    for name, source_name in SCENES.items():
        generate(name, source_name, args.build)


if __name__ == '__main__':
    main()
