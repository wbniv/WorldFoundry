"""Make a test MODL from a real reef export's vertex and material format."""
import struct
import sys
from pathlib import Path

source = Path('wflevels/aquarium_thai_reef/reef_left.iff').read_bytes()
chunks = {}
offset = 8
while offset < len(source):
    tag, size = struct.unpack_from('<4sI', source, offset)
    chunks[tag] = source[offset + 8:offset + 8 + size]
    offset += 8 + ((size + 3) & ~3)

vertices = bytearray(chunks[b'VRTX'][:12 * 24])
# 66 fixed 16.16 units = 0.001007..., hence representable on disk.
for i, xyz in enumerate([(0, 0, 0), (65536, 0, 0), (0, 65536, 0),
                         (0, 0, 0), (66, 0, 0), (0, 66, 0),
                         (0, 0, 0), (0, 0, 0), (0, 0, 0),
                         (0, 0, 0), (0, 66, 0), (66, 0, 0)]):
    struct.pack_into('<iii', vertices, i * 24 + 12, *xyz)
faces = b''.join(struct.pack('<hhhh', i, i+1, i+2, 0) for i in (0, 3, 6, 9))
def chunk(tag, data):
    return tag + struct.pack('<I', len(data)) + data + bytes((-len(data)) % 4)
body = chunk(b'VRTX', vertices) + chunk(b'MATL', chunks[b'MATL']) + chunk(b'FACE', faces)
Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/reef-loader-fixture.iff').write_bytes(
    b'MODL' + struct.pack('<I', len(body)) + body)
