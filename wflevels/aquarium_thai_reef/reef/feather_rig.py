"""Bind groups of three feather-star arms to ten articulated curves."""
import itertools
import math
import struct

from .life import _feather_star


def bind_exported_mesh(path, Mesh, dfrm):
    source = Mesh('feather_source')
    ranges = []
    _feather_star(source, (0, 0, 0), ranges=ranges)
    owners = [None] * len(source.vertices)
    for arm, (start, end) in enumerate(ranges):
        owners[start:end] = [arm // 3] * (end - start)
    buckets = {}
    for p, owner in zip(source.vertices, owners):
        key = tuple(round(v * 1000) for v in p)
        buckets.setdefault(key, []).append((p, owner))
    data = path.read_bytes()
    cursor, vertices = 8, None
    if data[:4] != b'MODL' or struct.unpack_from('<I', data, 4)[0] != len(data)-8:
        raise ValueError('unexpected feather star header')
    while cursor < len(data):
        tag, size = struct.unpack_from('<4sI', data, cursor)
        end = cursor + 8 + ((size + 3) & ~3)
        if end > len(data) or tag == b'DFRM':
            raise ValueError('malformed feather star mesh')
        if tag == b'VRTX':
            if vertices is not None or size % 24:
                raise ValueError('unexpected feather star vertices')
            vertices = [tuple(v/65536 for v in struct.unpack_from('<iii', data, cursor+20+i))
                        for i in range(0, size, 24)]
        cursor = end
    if cursor != len(data) or not vertices:
        raise ValueError('feather star has no vertices')
    chains = []
    for group in range(10):
        angle = math.pi * (.06 + .88 * (3*group + 1) / 29)
        dx, dz = math.cos(angle), math.sin(angle)
        chains.append([{'head': (dx*(.12+i*.3), 0, dz*(.12+i*.3)),
                        'tail': (dx*(.12+(i+1)*.3), 0, dz*(.12+(i+1)*.3)),
                        'z_axis': (0, 1, 0), 'limits': (35, 35, 35, 35)}
                       for i in range(2)])
    bindings = []
    for p in vertices:
        key = tuple(round(v*1000) for v in p)
        candidates = (item for delta in itertools.product((-1, 0, 1), repeat=3)
                      for item in buckets.get(tuple(key[i]+delta[i] for i in range(3)), ()))
        best = min(candidates, key=lambda item: sum((p[i]-item[0][i])**2 for i in range(3)), default=None)
        if best is None or sum((p[i]-best[0][i])**2 for i in range(3)) > .000001:
            raise ValueError(f'cannot map feather star vertex {p}')
        owner = best[1]
        bindings.append((dfrm.NONE, 0, 0) if owner is None else
                        (dfrm.ON_SAMPLE, 2*owner + int(math.hypot(p[0], p[2]) >= .42), 1))
    payload = dfrm.build_chunk_curves(chains, vertices, bindings, knots=(0, 1))
    chunk = b'DFRM' + struct.pack('<I', len(payload)) + payload + b'\0' * (-len(payload) % 4)
    path.write_bytes(b'MODL' + struct.pack('<I', len(data)-8+len(chunk)) + data[8:] + chunk)
