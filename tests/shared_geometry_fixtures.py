#!/usr/bin/env python3
"""Write plain and shared-geometry model fixtures from one cube.

The shared-geometry format (GEOM + GREF/UVCL appearances) is specified in
finding-your-way docs/plans/2026-10-17-texture-variant-mesh-sharing.md,
section "Exporter finding and the v1 format". This generator writes, from the
same cube positions and face list:

  cube_a.iff, cube_b.iff        plain MODL (VRTX + MATL + FACE), two UV maps
  shared/cube_geo.iff           GEOM (POSN + FACE)
  shared/cube_a.iff, cube_b.iff appearance MODL (MATL + GREF + UVCL), chunk order
                                as the chapter pass writes it (MATL first)
  bad/<case>/...                one defect per directory, for rejection tests

So shared/cube_X.iff must decode to exactly the vertices and faces of
cube_X.iff. Faces alternate between two materials so the runtime's
material sort reorders them. Usage:

  python3 tests/shared_geometry_fixtures.py OUT_DIR
"""
import argparse
from pathlib import Path
import struct
import sys
import zlib

GREF_FORMAT = '<IIIII32s'          # version, vertexCount, faceCount, posCrc32, faceCrc32, name
MATERIAL_NAME_LEN = 256            # _MaterialOnDisk = flags, colour, name[256] (264 bytes)


def chunk(tag, payload):
    return tag + struct.pack('<I', len(payload)) + payload


def material(flags, colour, texture=b''):
    return struct.pack('<iI', flags, colour) + texture.ljust(MATERIAL_NAME_LEN, b'\0')


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def cube():
    """(positions, faces): 24 vertices (4 per side, split at UV seams), 12 triangles."""
    corner = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    positions, faces = [], []
    for side, quad in enumerate(quads):
        base = len(positions)
        positions += [tuple(c * 65536 - 32768 for c in corner[i]) for i in quad]
        material_index = side % 2
        faces.append((base, base + 1, base + 2, material_index))
        faces.append((base, base + 2, base + 3, material_index))
    return positions, faces


def uv_a(i):
    return (i % 4 // 2) * 65536, (i % 2) * 65536, 0xFFFFFF


def uv_b(i):
    return 65536 - i * 1024, 4096 + i * 2048, 0x80FF80 + i


MATL = material(6, 0x00FFFFFF, b'cube.tga') + material(1, 0x0000FF00)   # Color::Validate: top byte 0


def posn_payload(positions):
    return b''.join(struct.pack('<iii', *p) for p in positions)


def face_payload(faces):
    return b''.join(struct.pack('<hhhh', *f) for f in faces)


def plain(positions, faces, uv):
    vrtx = b''.join(struct.pack('<iiI', *uv(i)) + struct.pack('<iii', *p) for i, p in enumerate(positions))
    return chunk(b'MODL', chunk(b'VRTX', vrtx) + chunk(b'MATL', MATL) + chunk(b'FACE', face_payload(faces)))


def gref(name, vertex_count, face_count, pos_crc, face_crc, version=1):
    return struct.pack(GREF_FORMAT, version, vertex_count, face_count, pos_crc, face_crc,
                       name.ljust(32, b'\0')[:32])


def appearance(gref_payload, uvcl, matl=MATL, extra=b''):
    return chunk(b'MODL', chunk(b'MATL', matl) + extra + chunk(b'GREF', gref_payload) + chunk(b'UVCL', uvcl))


def write(out):
    positions, faces = cube()
    posn, face = posn_payload(positions), face_payload(faces)
    n, m = len(positions), len(faces)
    good = gref(b'cube_geo.iff', n, m, crc32(posn), crc32(face))
    uvcl = {k: b''.join(struct.pack('<iiI', *uv(i)) for i in range(n)) for k, uv in (('a', uv_a), ('b', uv_b))}
    geometry = chunk(b'GEOM', chunk(b'POSN', posn) + chunk(b'FACE', face))
    files = {
        'cube_a.iff': plain(positions, faces, uv_a),
        'cube_b.iff': plain(positions, faces, uv_b),
        'shared/cube_geo.iff': geometry,
        'shared/cube_a.iff': appearance(good, uvcl['a']),
        'shared/cube_b.iff': appearance(good, uvcl['b']),
    }
    # One defect each; every directory keeps a valid name so only the defect fails.
    bad_face = face_payload([faces[0][:2] + (n,) + faces[0][3:]] + faces[1:])
    bad = {
        'pos-crc': (gref(b'cube_geo.iff', n, m, crc32(posn) ^ 1, crc32(face)), uvcl['a'], geometry),
        'face-crc': (gref(b'cube_geo.iff', n, m, crc32(posn), crc32(face) ^ 1), uvcl['a'], geometry),
        'vertex-count': (gref(b'cube_geo.iff', n + 1, m, crc32(posn), crc32(face)),
                         uvcl['a'] + struct.pack('<iiI', 0, 0, 0), geometry),   # UVCL agrees with GREF
        'uvcl-count': (good, uvcl['a'][:-12], geometry),
        'face-index': (gref(b'cube_geo.iff', n, m, crc32(posn), crc32(bad_face)), uvcl['a'],
                       chunk(b'GEOM', chunk(b'POSN', posn) + chunk(b'FACE', bad_face))),
        'version': (gref(b'cube_geo.iff', n, m, crc32(posn), crc32(face), version=2), uvcl['a'], geometry),
        'missing': (gref(b'cube_gone.iff', n, m, crc32(posn), crc32(face)), uvcl['a'], geometry),
    }
    for case, (g, u, geo) in bad.items():
        files[f'bad/{case}/cube_geo.iff'] = geo
        files[f'bad/{case}/cube_a.iff'] = appearance(g, u)
    one_material = material(1, 0x0000FF00)
    files['bad/material-index/cube_geo.iff'] = geometry
    files['bad/material-index/cube_a.iff'] = appearance(good, uvcl['a'], matl=one_material)
    files['bad/lrig/cube_geo.iff'] = geometry
    files['bad/lrig/cube_a.iff'] = appearance(good, uvcl['a'], extra=chunk(b'LRIG', struct.pack('<II', 1, 0)))
    for name, data in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('out', type=Path)
    args = parser.parse_args(argv)
    files = write(args.out)
    for name, data in sorted(files.items()):
        print(f'{len(data):6d} {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
