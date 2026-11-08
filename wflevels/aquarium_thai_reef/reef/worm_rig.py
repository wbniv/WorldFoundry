"""Bind the exported textured worm mesh to fifteen independent DFRM curves.

Each curve is rooted at its worm's tube mouth and runs along the crown axis
in two samples of half the crown height, so the per-curve scale (retract)
collapses the crown into the mouth and the crown can also sway.
"""
import itertools
import struct

from .life import worm_crowns, worm_frame
from .scene import worm_origin


def bind_exported_mesh(path, Mesh, dfrm):
    source = Mesh('worm_source')
    ranges = []
    worm_crowns(source, worm_origin(), ranges=ranges)
    buckets = {}
    for curve, r in enumerate(ranges):
        for p in source.vertices[r['start']:r['end']]:
            key = tuple(round(v * 1000) for v in p)
            buckets.setdefault(key, []).append((p, curve))

    data = path.read_bytes()
    if data[:4] != b'MODL' or struct.unpack_from('<I', data, 4)[0] != len(data) - 8:
        raise ValueError('unexpected worm MODL header')
    cursor, vertices = 8, None
    while cursor < len(data):
        tag, size = struct.unpack_from('<4sI', data, cursor)
        end = cursor + 8 + ((size + 3) & ~3)
        if end > len(data) or tag == b'DFRM':
            raise ValueError('malformed or already bound worm mesh')
        if tag == b'VRTX':
            if vertices is not None or size % 24:
                raise ValueError('unexpected worm vertex data')
            vertices = [tuple(v / 65536 for v in struct.unpack_from('<iii', data, cursor + 8 + i + 12))
                        for i in range(0, size, 24)]
        cursor = end
    if cursor != len(data) or not vertices:
        raise ValueError('worm mesh has no vertices')

    bindings = []
    for p in vertices:
        key = tuple(round(v * 1000) for v in p)
        candidates = (item for delta in itertools.product((-1, 0, 1), repeat=3)
                      for item in buckets.get(tuple(key[i] + delta[i] for i in range(3)), ()))
        best = min(candidates, key=lambda item: sum((p[i] - item[0][i]) ** 2 for i in range(3)), default=None)
        if best is None or sum((p[i] - best[0][i]) ** 2 for i in range(3)) > .000001:
            raise ValueError(f'cannot map exported worm vertex {p}')
        curve = best[1]
        r = ranges[curve]
        along = sum((p[i] - r['mouth'][i]) * r['axis'][i] for i in range(3))
        sample = 2 * curve + int(along >= r['height'] / 2)
        bindings.append((dfrm.ON_SAMPLE, sample, 1.0))

    chains = []
    for r in ranges:
        mouth, axis, half = r['mouth'], r['axis'], r['height'] / 2
        _, e2 = worm_frame(axis)
        chains.append([{'head': tuple(mouth[k] + axis[k] * half * i for k in range(3)),
                        'tail': tuple(mouth[k] + axis[k] * half * (i + 1) for k in range(3)),
                        'z_axis': e2, 'limits': (45, 45, 45, 45)}
                       for i in range(2)])
    payload = dfrm.build_chunk_curves(chains, vertices, bindings, knots=(0, 1))
    chunk = b'DFRM' + struct.pack('<I', len(payload)) + payload + b'\0' * (-len(payload) % 4)
    path.write_bytes(b'MODL' + struct.pack('<I', len(data) - 8 + len(chunk)) + data[8:] + chunk)
    return len(vertices)
