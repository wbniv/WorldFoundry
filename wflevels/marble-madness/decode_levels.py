#!/usr/bin/env python3
"""
Marble Madness arcade ROM level data decoder.
Extracts path-segment geometry for all 6 levels from the 68000 program ROM.

Usage:
    python3 decode_levels.py [path/to/marble_fullrom.bin]

Produces JSON + ASCII height profiles for each level.

ROM format discovered 2026-05-01 via MAME Lua runtime analysis.
See docs/investigations/2026-05-01-marble-madness-rom-level-data.md
"""

import sys, json, zipfile, struct, tempfile, os

# --------------------------------------------------------------------------
# ROM constants (confirmed via MAME atarisy1.cpp + runtime RAM pointer scan)
# --------------------------------------------------------------------------

LEVEL_TABLE  = 0x01DEC0   # 6×4-byte pointers to level descriptor arrays
SENTINEL     = 0xFFFF     # descriptor array end marker

LEVEL_NAMES = ['Practice', 'Beginner', 'Intermediate', 'Aerial', 'Silly', 'Ultimate']


def u16(d, o): return struct.unpack_from('>H', d, o)[0]
def u32(d, o): return struct.unpack_from('>I', d, o)[0]


def load_fullrom(path: str) -> bytes:
    """Load full 68000 ROM image from a pre-dumped binary or reconstruct from zip."""
    if path.endswith('.bin'):
        return open(path, 'rb').read()

    # Reconstruct from MAME ROM zip: interleave paired chips into 68000 address space
    rom = bytearray(0x30000)

    # ROM_LOAD16_BYTE pairs: (odd_file, even_file, base_addr, size)
    pairs = [
        ('136033.623', '136033.624', 0x10000),
        ('136033.625', '136033.626', 0x18000),
        ('136033.627', '136033.628', 0x20000),
        ('136033.229', '136033.630', 0x28000),
    ]
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        for odd_f, even_f, base in pairs:
            odd  = zf.read(odd_f)
            even = zf.read(even_f)
            for i in range(len(odd)):
                rom[base + i*2]     = odd[i]
                rom[base + i*2 + 1] = even[i]

    # NOTE: addresses 0x000000-0x00FFFF are the motherboard BIOS (not in game zip)
    # Level data lives in 0x010000-0x02FFFF which IS in our pairs above.
    # For full-ROM analysis (e.g. finding LEVEL_TABLE at 0x01DEC0) this is sufficient.
    return bytes(rom)


def decode_segment(rom: bytes, addr: int) -> dict:
    """
    Decode a 24-byte path segment record.

    Confirmed fields:
      +02  h_left   — left edge wall height (game units)
      +04  h_right  — right edge wall height
      +0A  h_center — path spine height (h_center=5 → goal zone)

    Unknown / constant fields:
      +00  flags   (0x0000 typical)
      +06  0x0000
      +08  0x0001  (type sub-flag)
      +0C  0x0000
      +0E  0x0000
      +10  0x0002
      +12  0x0C14  (possible ref → 0x020C14; may encode path width L=12 R=20)
      +14  0x0003
      +16  0x0000
    """
    if addr == 0 or addr + 24 > len(rom):
        return {'addr': addr, 'error': 'out of range'}
    return {
        'addr':     addr,
        'h_left':   u16(rom, addr + 2),
        'h_right':  u16(rom, addr + 4),
        'h_center': u16(rom, addr + 10),
        'flags':    u16(rom, addr + 0),
        'raw':      rom[addr:addr+24].hex(),
    }


def decode_level(rom: bytes, desc_addr: int) -> list[dict]:
    """Parse a descriptor array and decode each referenced segment."""
    segments = []
    off = desc_addr
    while True:
        typ  = u16(rom, off)
        addr = u32(rom, off + 2)
        off += 6
        if typ == SENTINEL:
            break
        seg = decode_segment(rom, addr)
        seg['type'] = typ
        segments.append(seg)
    return segments


def ascii_profile(segments: list[dict], field: str = 'h_center', width: int = 60) -> str:
    """Render an ASCII bar chart of a height field across segments."""
    vals = [s.get(field, 0) for s in segments if 'error' not in s]
    if not vals:
        return '(no data)'
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1
    rows = 8
    lines = []
    for row in range(rows, -1, -1):
        threshold = lo + (hi - lo) * row / rows
        line = f'{threshold:4.0f} │'
        for v in vals:
            line += '▓' if v >= threshold else ' '
        lines.append(line)
    lines.append('     └' + '─' * len(vals))
    lines.append('      ' + ''.join(str(i % 10) for i in range(len(vals))))
    return '\n'.join(lines)


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else 'assets/arcade-roms/marble.zip'
    if not os.path.exists(rom_path):
        # Try pre-dumped full ROM
        rom_path = '/tmp/marble_fullrom.bin'

    print(f'Loading ROM from {rom_path}...', file=sys.stderr)
    rom = load_fullrom(rom_path)
    print(f'ROM size: {len(rom)} bytes', file=sys.stderr)

    result = {}
    for lv in range(6):
        desc_addr = u32(rom, LEVEL_TABLE + lv * 4)
        name = LEVEL_NAMES[lv]
        segments = decode_level(rom, desc_addr)
        result[name] = {
            'desc_addr': hex(desc_addr),
            'segment_count': len(segments),
            'segments': segments,
        }

        print(f'\n{"="*60}')
        print(f'{name}  ({len(segments)} segments, desc @ 0x{desc_addr:06X})')
        print(f'{"="*60}')
        print(f'{"Seg":>4}  {"Type":>6}  {"Addr":>8}  {"h_left":>7}  {"h_right":>8}  {"h_center":>9}')
        for i, s in enumerate(segments):
            print(f'{i:4d}  0x{s["type"]:04X}  0x{s["addr"]:06X}  '
                  f'{s.get("h_left",0):7d}  {s.get("h_right",0):8d}  {s.get("h_center",0):9d}')

        print(f'\nh_center profile:')
        print(ascii_profile(segments, 'h_center'))
        print(f'\nh_left / h_right wall heights:')
        print(ascii_profile(segments, 'h_left'))

    # Write JSON
    out_path = os.path.join(os.path.dirname(__file__), 'levels.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'\nJSON written to {out_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
