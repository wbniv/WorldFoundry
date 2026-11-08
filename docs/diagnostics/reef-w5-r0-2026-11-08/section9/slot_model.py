#!/usr/bin/env python3
"""Reef W5 R0, section 9: Room #0 asset-slot usage of a built reef level, fitted to cast1.

Usage: python3 slot_model.py LEVEL_DIR [LEVEL_DIR ...]   (a wflevels/<level>/ or build-docker/r0/<probe>/<level>/ dir)

The Room #0 slot is one LMalloc of cbRoom bytes (the standalone wrapper's RAM 'ROOM' field; 32,000,000 for
both reef levels), carved from the 64,000,000-byte HAL arena (hal/hal.cc:36, asset/assets.cc:48,220).
It holds:
  * the room's mesh asset files (the RM0 .iff entries; the room's .tga/.ruv/.cyc are not charged), and
  * each mesh actor's own RenderObject3D copy, built by the on-disk constructor (gfx/rendobj3.cc:164-370) out
    of the slot memory that ActiveRooms passes to Actor::BindAssets (room/actrooms.cc:95):
      Vertex3D[V] 24 B + TriFace[F+1] 20 B + Primitive[2 x F] 44 B (ORDER_TABLES=2, gfx/otable.hp:52)
      + about 380 B per actor (RenderActor3D, materials, alignment; fitted, see README section 9).
Fit: the realistic P3 abort is reproduced exactly (fails on clump 34's 106,656-byte Primitive array with
~67 KB modelled vs 40,672 B reported remaining, i.e. ~380 B/actor unmodelled), and the anime P3 / realistic
P1 levels, which load, model below the limit.
"""
import re
import struct
import sys
from pathlib import Path

SLOT = 32_000_000
PER_ACTOR = 380


def chunks(data, off, end):
    while off + 8 <= end:
        tag = data[off:off + 4]
        size = struct.unpack_from('<I', data, off + 4)[0]
        yield tag, off + 8, size
        off += 8 + size + ((4 - (size & 3)) & 3)


def mesh_stats(path):
    d = path.read_bytes()
    tag, start, size = next(chunks(d, 0, len(d)))
    assert tag == b'MODL', (path, tag)
    v = f = 0
    for t, o, s in chunks(d, start, start + size):
        if t == b'VRTX':
            v = s // 24          # Vertex3DOnDisk: u, v, colour, x, y, z (gfx/rendobj3.hp:165)
        elif t == b'FACE':
            f = s // 8           # _TriFaceOnDisk: 4 x int16 (gfx/face.hp:34)
    return v, f


def copy_bytes(v, f):
    return 24 * v + 20 * (f + 1) + 88 * f + PER_ACTOR


def level(dirpath):
    dirpath = Path(dirpath)
    name = dirpath.name
    blocks = (dirpath / f'{name}.lev').read_text().split("\t{ 'OBJ'")[1:]
    txt = (dirpath / f'{name}.iff.txt').read_text()
    rm0 = re.search(r"\{ 'RM0'(.*?)\n\t\}", txt, re.S).group(1)
    meshes = [f for f in re.findall(r'\[ "([^"]+)" \]', rm0) if f.endswith('.iff')]
    files = sum((dirpath / f).stat().st_size for f in meshes)
    actors = []
    for b in blocks:
        m = re.search(r'"Mesh Name" \} \{ \'STR\' "([^"]+)"', b)
        if m and m.group(1) in meshes:
            v, f = mesh_stats(dirpath / m.group(1))
            actors.append((re.search(r"'NAME' \"([^\"]+)\"", b).group(1), v, f, copy_bytes(v, f)))
    return files, actors


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        raise SystemExit(0)
    for d in sys.argv[1:]:
        files, actors = level(d)
        copies = sum(a[3] for a in actors)
        used = files + copies
        print(f'{d}: mesh files {files:,} B + {len(actors)} actor copies {copies:,} B = {used:,} B '
              f'({used / SLOT * 100:.1f}% of {SLOT:,}; free {SLOT - used:,} B)')
