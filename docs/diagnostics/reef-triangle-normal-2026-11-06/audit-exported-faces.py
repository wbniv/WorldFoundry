"""Count exported faces and exact 16.16 coordinate degeneracy in MODL files."""
import csv
import hashlib
import math
import struct
import sys
from pathlib import Path

root = Path(sys.argv[1])
writer = csv.writer(sys.stdout, lineterminator='\n')
writer.writerow(['file', 'sha256', 'vertices', 'faces', 'zero_after_quantization',
                 'nonzero_below_filter_area', 'nonzero_at_or_below_legacy_normal_threshold'])
for path in sorted(root.glob('*.iff')):
    data = path.read_bytes()
    if data[:4] != b'MODL':
        continue
    chunks = {}
    offset = 8
    while offset + 8 <= len(data):
        tag, size = struct.unpack_from('<4sI', data, offset)
        chunks[tag] = data[offset+8:offset+8+size]
        offset += 8 + ((size+3) & ~3)
    if b'VRTX' not in chunks or b'FACE' not in chunks:
        continue
    vertices = [struct.unpack_from('<iii', chunks[b'VRTX'], i+12)
                for i in range(0, len(chunks[b'VRTX']), 24)]
    zero = small = legacy_rejected = 0
    for offset in range(0, len(chunks[b'FACE']), 8):
        ids = struct.unpack_from('<hhh', chunks[b'FACE'], offset)
        a, b, c = (vertices[i] for i in ids)
        u, v = ([b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)])
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        n2 = sum(component*component for component in n)
        if not n2:
            zero += 1
        else:
            area = math.sqrt(n2) / (2 * 65536**2)
            small += area < .00008
            legacy_rejected += area <= 2 / 65536
    writer.writerow([path.name, hashlib.sha256(data).hexdigest(), len(vertices),
                     len(chunks[b'FACE'])//8, zero, small, legacy_rejected])
