"""Extract the exact triangle input for the paired fixed-point normal benchmark."""
from pathlib import Path
import hashlib
import struct

root = Path(__file__).resolve().parents[3]
out = bytearray()
for name in ('aquarium_thai_reef', 'aquarium_thai_reef_anime'):
    data = (root/'wflevels'/name/'reef_left.iff').read_bytes()
    chunks, offset = {}, 8
    while offset + 8 <= len(data):
        tag, size = struct.unpack_from('<4sI', data, offset)
        chunks[tag] = data[offset+8:offset+8+size]
        offset += 8 + ((size+3) & ~3)
    vertices = [struct.unpack_from('<iii', chunks[b'VRTX'], i+12)
                for i in range(0, len(chunks[b'VRTX']), 24)]
    for i in range(0, len(chunks[b'FACE']), 8):
        for vertex in struct.unpack_from('<hhh', chunks[b'FACE'], i):
            out.extend(struct.pack('<iii', *vertices[vertex]))
print('faces:', len(out)//36, 'sha256:', hashlib.sha256(out).hexdigest())
