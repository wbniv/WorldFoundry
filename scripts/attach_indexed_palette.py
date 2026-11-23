#!/usr/bin/env python3
"""Attach indexed palette tables to an L4 standalone level's RAM locator."""
import argparse
from pathlib import Path
import struct

SECTOR = 2048
TAG = b'IPLT'


def attach(level, palette):
    data = bytearray(level)
    if len(data) < 2 * SECTOR or data[SECTOR:SECTOR + 4] != b'RAM\0':
        raise ValueError('expected a standalone level with RAM at sector one')
    if len(palette) < 8 or palette[:4] != b'DPLT':
        raise ValueError('expected a DPLT palette table')
    version, count = struct.unpack_from('<HH', palette, 4)
    if version != 1 or not 1 <= count <= 256 or len(palette) != 8 + count * 768:
        raise ValueError('invalid DPLT palette table')
    old_size = struct.unpack_from('<I', data, SECTOR + 4)[0]
    end = SECTOR + 8 + old_size
    if end + 8 > 2 * SECTOR or data[end:end + 4] != b'ALGN':
        raise ValueError('RAM padding absent')
    pad = struct.unpack_from('<I', data, end + 4)[0]
    if end + 8 + pad != 2 * SECTOR:
        raise ValueError('invalid RAM alignment')
    if any(data[i:i + 4] == TAG for i in range(SECTOR + 44, end - 11, 4)):
        raise ValueError('palette locator already present; rebuild from the unmodified level')
    if pad < 12 or len(data) % SECTOR:
        raise ValueError('insufficient RAM padding or unaligned level')
    offset = len(data) - SECTOR
    chunk = TAG + struct.pack('<I', len(palette)) + palette
    chunk += bytes((-len(chunk)) % SECTOR)
    data.extend(chunk)
    struct.pack_into('<I', data, SECTOR + 4, old_size + 12)
    data[end:end + 20] = TAG + struct.pack('<II', offset, len(chunk)) + b'ALGN' + struct.pack('<I', pad - 12)
    struct.pack_into('<I', data, 4, len(data) - 8)
    return bytes(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('level', type=Path)
    parser.add_argument('palette', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_bytes(attach(args.level.read_bytes(), args.palette.read_bytes()))
