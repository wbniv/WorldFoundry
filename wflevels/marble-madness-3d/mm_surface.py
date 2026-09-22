#!/usr/bin/env python3
"""Marble Madness (arcade, Atari System 1) course-surface decoder.

Re-implements the game's own ground-height code (68000 routines at ROM
0x1CABA "load 4 cells" and 0x1CC62 "interpolate under the ball"), driven by
MAME memory dumps taken while the level is live:

  * game ROM image      0x010000-0x02FFFF  (reconstructed from marble.zip)
  * slapstic bank       0x080000-0x081FFF  (tile -> surface-code table lives here)
  * work RAM            0x400000-0x401FFF  (row-base heights at 0x400478, dynamic
                                            surface table at 0x40076E)
  * playfield VRAM      0xA00000-0xA01FFF  (64 x 64 tile words, the course art)

The arcade stores NO explicit height map: the isometric tile art *is* the map.
Each 8x8-unit world cell (cx, cy) sits on isometric row r = cx+cy-20 and
column c = 21-cx+(r>>1) (+22 on odd rows); the tile word(s) there index a
surface code, which yields 4 height words for the cell.  See
docs/investigations/2026-09-22-marble-madness-surface-algorithm.md.

Height/world units: 1 XY unit = 1 arcade unit (8 per cell); 1 height unit =
1 screen pixel; "sea level" is 0x4000 (the row base).  Void cells decode to
all-zero heights (the marble falls).

Usage:
    mm_surface.py --rom marble_game.bin --bank bank.bin --ram ram.bin --vram vram.bin \
                  [--cell CX CY] [--json out.json] [--ascii]
"""
import argparse
import json
import struct
import sys

ROW_VRAM_TBL = 0x1EB3A     # iso row-pair -> VRAM byte offset (words)
COL_OFF_TBL = 0x1ED0A      # iso col -> byte offset (44 bytes), +0x2C -> shift count
SLOPE_TBL = 0x1ED62        # 32 words
NEIGHBOR_TBL = 0x24B3A     # 2 x 3 x (dcol, drow, dA5) words; +0x12 for odd rows
LEVEL_PTR_TBL = 0x2BE00    # 6 longs -> per-level struct
ROWBASE_RAM = 0x400478     # word per iso row
DYN_TBL_RAM = 0x40076E     # dynamic surface codes (0x800..0xFFF indirect)

SEA = 0x4000


class Mem:
    """Sparse 68000 address space assembled from dump files."""

    def __init__(self):
        self.regions = []

    def add(self, base, data):
        self.regions.append((base, bytes(data)))

    def _get(self, addr, n):
        for base, data in self.regions:
            if base <= addr and addr + n <= base + len(data):
                o = addr - base
                return data[o:o + n]
        raise KeyError(f"unmapped read {addr:06X}+{n}")

    def u8(self, a):
        return self._get(a, 1)[0]

    def s8(self, a):
        v = self.u8(a)
        return v - 256 if v >= 128 else v

    def u16(self, a):
        return struct.unpack('>H', self._get(a, 2))[0]

    def s16(self, a):
        v = self.u16(a)
        return v - 65536 if v >= 32768 else v

    def u32(self, a):
        return struct.unpack('>I', self._get(a, 4))[0]


def s16(v):
    v &= 0xFFFF
    return v - 65536 if v >= 32768 else v


class Level:
    def __init__(self, mem: Mem, level_index: int, tile_tbl: int):
        self.mem = mem
        self.struct = mem.u32(LEVEL_PTR_TBL + 4 * level_index)   # == *(0x400474)
        self.tile_tbl = tile_tbl                      # == *(0x40065A) at runtime (in bank)
        self.corner_base = mem.u32(self.struct)       # (A1) : base for 4-byte corner records
        self.nrows = mem.u16(self.struct + 0x18)

    # --- 0x1CABA core: one cell -> 4 height words -----------------------------
    def cell_heights(self, row, col):
        m = self.mem
        if row < 0 or row >= self.nrows:
            return None                                   # outside the course
        d0 = col
        d1 = row & 0xFE
        if row & 1:
            d0 += 0x16
        if not (0 <= d0 < 44):
            return None
        vram = 0xA00000 + m.u16(ROW_VRAM_TBL + d1)
        vram += m.u8(COL_OFF_TBL + d0) - 2
        try:
            field = m.u32(vram)
        except KeyError:
            return None
        shift = m.u8(COL_OFF_TBL + 0x2C + d0)
        field = (field >> shift) & 0x7FE
        code = m.u16(self.tile_tbl + field)
        rowbase = s16(m.u16(ROWBASE_RAM + 2 * row))
        return self.decode_code(code, rowbase)

    def decode_code(self, code, rowbase):
        m = self.mem
        for _ in range(8):                                # 0x800..0xFFF indirection loop
            if code >= 0x1000:
                break
            if code >= 0x800:
                code = m.u16(DYN_TBL_RAM + (code & 0x7FE))
                continue
            if code == 0:
                return [0, 0, 0, 0]
            p = self.corner_base + code
            d1 = rowbase - 0x80
            out = []
            for i in range(4):
                b = m.u8(p + i)
                out.append(0 if b == 0 else s16(b + d1))
            return out
        if code >= 0xF000:
            h = s16((code & 0x7F) - 0x40 + rowbase)
            return [h, h, h, h]
        d5 = code
        d0 = s16((code & 0x7F) - 0x40 + rowbase)
        slope = m.u16(SLOPE_TBL + ((code >> 6) & 0x3E))
        d1 = 0 if slope == 0x1000 else s16(d0 - slope)
        return [d0 if d5 & (1 << (12 + i)) else d1 for i in range(4)]

    # --- 0x1CABA outer loop: the 4 cells the interpolator needs ----------------
    @staticmethod
    def iso(cx, cy):
        row = cx + cy + 1 - 0x15
        col = 0x15 - cx + (row >> 1)
        return row, col

    def four_cells(self, cx, cy):
        """Returns the 16 words at 0x401C28 in memory order (cell0..cell3 x 4)."""
        m = self.mem
        row, col = self.iso(cx, cy)
        tbl = NEIGHBOR_TBL + (0x12 if row & 1 else 0)
        slots = [None] * 4
        a5 = 0
        for i in range(4):
            h = self.cell_heights(row, col)
            slots[a5 // 8] = h if h is not None else [0, 0, 0, 0]
            if i == 3:
                break
            dcol = s16(m.u16(tbl + 6 * i))
            drow = s16(m.u16(tbl + 6 * i + 2))
            da5 = s16(m.u16(tbl + 6 * i + 4))
            col += dcol
            row += drow
            a5 += 8 + da5
        return slots

    # --- 0x1CC62: ground height under (cx,cy) + (sx,sy) in 1/8 cell ------------
    def ground(self, cx, cy, sx, sy):
        c0, c1, c2, c3 = self.four_cells(cx, cy)
        if sy < sx:                                   # 0x4006A2 == 1
            gx = c1[3] - c0[2]
            gy = c0[2] - c3[1]
        else:
            gx = c2[0] - c3[1]
            gy = c1[3] - c2[0]
        base = c3[1]
        return base + (gx * sx + gy * sy) / 8.0, (c0, c1, c2, c3)

    def is_void(self, cx, cy):
        row, col = self.iso(cx, cy)
        h = self.cell_heights(row, col)
        return h is None or h == [0, 0, 0, 0]


def load(args):
    mem = Mem()
    mem.add(0x000000, open(args.rom, 'rb').read())
    mem.add(0x080000, open(args.bank, 'rb').read())
    mem.add(0x400000, open(args.ram, 'rb').read())
    mem.add(0xA00000, open(args.vram, 'rb').read())
    return mem


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rom', required=True)
    ap.add_argument('--bank', required=True)
    ap.add_argument('--ram', required=True)
    ap.add_argument('--vram', required=True)
    ap.add_argument('--level', type=int, default=0)
    ap.add_argument('--tile-tbl', type=lambda x: int(x, 0), required=True, help='runtime value of 0x40065A, e.g. 0x81874 for Practice')
    ap.add_argument('--cell', nargs=2, type=int, metavar=('CX', 'CY'))
    ap.add_argument('--json', help='write full course heightfield JSON')
    ap.add_argument('--ascii', action='store_true', help='print an ASCII map of cell centre heights')
    ap.add_argument('--range', nargs=4, type=int, metavar=('CX0', 'CY0', 'CX1', 'CY1'), default=[0, 0, 96, 96])
    a = ap.parse_args(argv)
    mem = load(a)
    lv = Level(mem, a.level, a.tile_tbl)
    print(f"level {a.level}: struct={lv.struct:06X} tile_tbl={lv.tile_tbl:06X} nrows={lv.nrows}", file=sys.stderr)
    if a.cell:
        cx, cy = a.cell
        cells = lv.four_cells(cx, cy)
        print(f"cell ({cx},{cy}) iso={lv.iso(cx, cy)} -> " + " | ".join(" ".join(f"{s16(v):5d}" for v in c) for c in cells))
        for sx, sy in ((0, 0), (7, 0), (0, 7), (7, 7), (4, 4)):
            print(f"  ground sub({sx},{sy}) = {lv.ground(cx, cy, sx, sy)[0]:.2f}")
    if a.json or a.ascii:
        cx0, cy0, cx1, cy1 = a.range
        cells = {}
        for cy in range(cy0, cy1):
            for cx in range(cx0, cx1):
                if lv.is_void(cx, cy):
                    continue
                cells[(cx, cy)] = [lv.ground(cx, cy, sx, sy)[0] for (sx, sy) in ((0, 0), (8, 0), (8, 8), (0, 8))]
        if a.ascii:
            for cy in range(cy1 - 1, cy0 - 1, -1):
                line = ''
                for cx in range(cx0, cx1):
                    h = cells.get((cx, cy))
                    if h is None:
                        line += ' .'
                    else:
                        line += f"{int(round(sum(h) / 4)) - SEA:+3d}"[-2:]
                print(f"{cy:3d} {line}")
        if a.json:
            out = {'level': a.level, 'unit_cells': 8, 'sea': SEA,
                   'cells': [{'i': cx, 'j': cy, 'h': [h - SEA for h in hs]} for (cx, cy), hs in sorted(cells.items())]}
            with open(a.json, 'w') as f:
                json.dump(out, f)
            print(f"wrote {len(cells)} cells to {a.json}", file=sys.stderr)


if __name__ == '__main__':
    main()
