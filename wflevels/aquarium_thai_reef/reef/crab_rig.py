"""Bind the guard crab's legs and claws to independent DFRM curves."""
import struct

from .invertebrates import banded_shrimp, guard_crab, hermit_crab
from .fishes import boxfish
from .life import _clam


def bind_exported_mesh(path, Mesh, dfrm, species='crab'):
    ranges = []
    if species == 'boxfish':
        source = boxfish(Mesh, fin_ranges=ranges)
    elif species == 'clam':
        source = Mesh('clam_source')
        _clam(source, (0, 0, 0), limb_ranges=ranges)
    else:
        source = Mesh(species + '_source')
        builder = {'crab': guard_crab, 'shrimp': banded_shrimp, 'hermit': hermit_crab}[species]
        builder(source, (0, 0, 0), limb_ranges=ranges)
    owners = [None] * len(source.vertices)
    for i, (start, end, *_) in enumerate(ranges):
        owners[start:end] = [i] * (end - start)
    data = path.read_bytes()
    if data[:4] != b'MODL' or struct.unpack_from('<I', data, 4)[0] != len(data) - 8:
        raise ValueError('unexpected crab MODL header')
    cursor, vertices = 8, None
    while cursor < len(data):
        tag, size = struct.unpack_from('<4sI', data, cursor)
        end = cursor + 8 + ((size + 3) & ~3)
        if end > len(data) or tag == b'DFRM':
            raise ValueError('malformed or already bound crab mesh')
        if tag == b'VRTX':
            if vertices is not None or size % 24:
                raise ValueError('unexpected crab vertices')
            vertices = [tuple(v / 65536 for v in struct.unpack_from('<iii', data, cursor + 20 + i))
                        for i in range(0, size, 24)]
        cursor = end
    if cursor != len(data) or not vertices:
        raise ValueError('crab mesh has no vertices')
    chains = []
    for _, _, root, direction, axis in ranges:
        if species not in ('boxfish', 'clam'):
            direction, axis = (0, direction, 0), (0, 0, 1)
        chains.append([{'head': tuple(root[k] + direction[k] * .06 * i for k in range(3)),
                        'tail': tuple(root[k] + direction[k] * .06 * (i + 1) for k in range(3)),
                        'z_axis': axis, 'limits': (65, 65, 65, 65)}
                       for i in range(2)])
    bindings = []
    for p in vertices:
        i = min(range(len(source.vertices)), key=lambda j: sum((p[k] - source.vertices[j][k]) ** 2 for k in range(3)))
        if sum((p[k] - source.vertices[i][k]) ** 2 for k in range(3)) > .0002:
            raise ValueError(f'cannot map exported crab vertex {p}')
        owner = owners[i]
        if owner is None:
            bindings.append((dfrm.NONE, 0, 0))
        else:
            root = ranges[owner][2]
            distance = (sum((p[k]-root[k])**2 for k in range(3))**.5
                        if species in ('boxfish', 'clam') else abs(p[1]-root[1]))
            # The valves are rigid shells: splitting them over two hinged
            # samples tears their triangulated surfaces as they close.
            sample = 2 * owner + int(species != 'clam' and distance >= .06)
            bindings.append((dfrm.ON_SAMPLE, sample, 1.0))
    payload = dfrm.build_chunk_curves(chains, vertices, bindings, knots=(0, 1))
    chunk = b'DFRM' + struct.pack('<I', len(payload)) + payload + b'\0' * (-len(payload) % 4)
    path.write_bytes(b'MODL' + struct.pack('<I', len(data) - 8 + len(chunk)) + data[8:] + chunk)
