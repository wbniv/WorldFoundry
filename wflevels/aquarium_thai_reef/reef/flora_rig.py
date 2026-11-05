"""Independent deformers for the fan worms and living soft corals."""
import itertools
import struct
from . import corals, life


def bind_exported_mesh(path, Mesh, dfrm, kind):
    source, ranges = Mesh(kind + '_source'), []
    {'dusters': life.feather_dusters, 'flowerpot': corals.flowerpot,
     'leather': corals.leather_coral}[kind](source, (0, 0, 0), ranges=ranges)
    group_count = {'dusters': 4, 'flowerpot': 12, 'leather': 2}[kind]
    owners = [None] * len(source.vertices)
    roots = [[] for _ in range(group_count)]
    for i, (start, end, root) in enumerate(ranges):
        group = i * group_count // len(ranges) if kind == 'flowerpot' else i
        roots[group].append(root)
        owners[start:end] = [group] * (end-start)
    for group in range(group_count):
        if not roots[group]:
            roots[group].append((0, 0, 0))
    roots = [tuple(sum(p[k] for p in group)/len(group) for k in range(3)) for group in roots]
    buckets = {}
    for p, owner in zip(source.vertices, owners):
        key = tuple(round(v*1000) for v in p)
        buckets.setdefault(key, []).append((p, owner))
    data = path.read_bytes()
    if data[:4] != b'MODL' or struct.unpack_from('<I', data, 4)[0] != len(data)-8:
        raise ValueError('unexpected animated colony mesh')
    cursor, vertices = 8, None
    while cursor < len(data):
        tag, size = struct.unpack_from('<4sI', data, cursor)
        end = cursor + 8 + ((size+3) & ~3)
        if end > len(data) or tag == b'DFRM':
            raise ValueError('malformed animated colony mesh')
        if tag == b'VRTX':
            if vertices is not None or size % 24:
                raise ValueError('unexpected colony vertices')
            vertices = [tuple(v/65536 for v in struct.unpack_from('<iii', data, cursor+20+i))
                        for i in range(0, size, 24)]
        cursor = end
    if cursor != len(data) or not vertices:
        raise ValueError('empty colony mesh')
    chains = [[{'head': (x,y,z+i*.3), 'tail': (x,y,z+(i+1)*.3),
                'z_axis': (1,0,0), 'limits': (35,35,35,35)} for i in range(2)]
              for x,y,z in roots]
    bindings = []
    for p in vertices:
        key = tuple(round(v*1000) for v in p)
        candidates = (item for delta in itertools.product((-1,0,1), repeat=3)
                      for item in buckets.get(tuple(key[i]+delta[i] for i in range(3)), ()))
        best = min(candidates, key=lambda item: sum((p[i]-item[0][i])**2 for i in range(3)), default=None)
        if best is None or sum((p[i]-best[0][i])**2 for i in range(3)) > .000001:
            raise ValueError(f'cannot map {kind} vertex {p}')
        owner = best[1]
        if owner is None:
            bindings.append((dfrm.NONE, 0, 0))
        else:
            sample = owner*2 + int(kind != 'leather' and p[2]-roots[owner][2] >= .3)
            bindings.append((dfrm.ON_SAMPLE, sample, 1))
    payload = dfrm.build_chunk_curves(chains, vertices, bindings, knots=(0,1))
    chunk = b'DFRM' + struct.pack('<I', len(payload)) + payload + b'\0'*(-len(payload)%4)
    path.write_bytes(b'MODL' + struct.pack('<I', len(data)-8+len(chunk)) + data[8:] + chunk)
