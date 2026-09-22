#!/usr/bin/env python3
"""Merge a MAME sweep (RAM+VRAM dumps taken every N frames while a Marble
Madness level scrolls past) into one complete course heightfield.

The arcade keeps only a 64-row window of the course in playfield VRAM and
blanks rows once they scroll off, so no single dump holds the whole level.
For every cell we take the decode from the first dump in which the cell's tile
is present, and check that every other dump that has it agrees.

Input directory layout (as written by scripts/research/mame/mm_demo_sweep.lua):
    bank.bin             slapstic bank 0x080000-0x081FFF
    ram_<frame>.bin      0x400000-0x401FFF
    vram_<frame>.bin     0xA00000-0xA03FFF
    log.txt              "<frame> lvl=<n> scroll=<hex> X=.. Y=.. Z=.. tbl=<hex>"

Output JSON (course-<level>.json):
    {"level": n, "sea": 16384, "extent": [cx0,cy0,cx1,cy1],
     "cells": [{"i": cx, "j": cy, "h": [h00,h10,h11,h01],
                                          "code": <surface code>}...],
    }
Heights are in arcade height units relative to sea level (0x4000); 8 XY units
per cell.  Void cells (surface code 0, or never seen) are omitted.

Usage: mm_merge_course.py --rom marble_game.bin --sweep DIR --level 0 --out course-practice.json [--ascii]
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mm_surface as M  # noqa: E402


def load_sweep(rom_path, sweep, level):
    log = {}
    for line in open(os.path.join(sweep, 'log.txt')):
        m = re.match(r'(\d+) lvl=(\d+) scroll=([0-9A-F]+) X=([0-9A-F]+) Y=([0-9A-F]+) Z=([0-9A-F]+) tbl=([0-9A-F]+)', line)
        if m:
            fr = int(m.group(1))
            log[fr] = dict(lvl=int(m.group(2)), scroll=int(m.group(3), 16), X=int(m.group(4), 16),
                           Y=int(m.group(5), 16), Z=int(m.group(6), 16), tbl=int(m.group(7), 16))
    rom = open(rom_path, 'rb').read()
    bank = open(os.path.join(sweep, 'bank.bin'), 'rb').read()
    frames = []
    for vf in sorted(glob.glob(os.path.join(sweep, 'vram_*.bin')), key=lambda p: int(re.search(r'(\d+)', os.path.basename(p)).group(1))):
        fr = int(re.search(r'(\d+)', os.path.basename(vf)).group(1))
        info = log.get(fr)
        if not info or info['lvl'] != level or info['scroll'] == 0:
            continue
        mem = M.Mem()
        mem.add(0, rom)
        mem.add(0x080000, bank)
        mem.add(0x400000, open(os.path.join(sweep, f'ram_{fr}.bin'), 'rb').read())
        mem.add(0xA00000, open(vf, 'rb').read())
        frames.append((fr, info, M.Level(mem, level, info['tbl'])))
    return frames


def cell_code(lv, cx, cy):
    """Raw surface code for the cell, or None if the tile row is not in VRAM."""
    m = lv.mem
    row, col = lv.iso(cx, cy)
    if row < 0 or row >= lv.nrows:
        return None
    d0 = col + (0x16 if row & 1 else 0)
    if not (0 <= d0 < 44):
        return None
    vram = 0xA00000 + m.u16(M.ROW_VRAM_TBL + (row & 0xFE)) + m.u8(M.COL_OFF_TBL + d0) - 2
    try:
        raw = m.u32(vram)
    except KeyError:
        return None
    if raw == 0:
        return None            # blanked row (scrolled off) — treat as "not seen"
    field = (raw >> m.u8(M.COL_OFF_TBL + 0x2C + d0)) & 0x7FE
    return m.u16(lv.tile_tbl + field)


def merge(frames, extent):
    cx0, cy0, cx1, cy1 = extent
    cells = {}
    conflicts = 0
    for cy in range(cy0, cy1):
        for cx in range(cx0, cx1):
            best = None
            for fr, info, lv in frames:
                code = cell_code(lv, cx, cy)
                if code is None:
                    continue
                # The cell's four corners come from four different vertex records
                # (see mm_surface.Level.ground); a word of 0 means "void on this
                # side" and the marble falls, so the cell is solid only if all
                # four are non-zero.
                c0, c1, c2, c3 = lv.four_cells(cx, cy)
                corners = (c3[1], c2[0], c1[3], c0[2])      # (0,0) (8,0) (8,8) (0,8)
                if code == 0 or 0 in corners:
                    entry = None
                else:
                    hs = [lv.ground(cx, cy, sx, sy)[0] for (sx, sy) in ((0, 0), (8, 0), (8, 8), (0, 8))]
                    entry = {'i': cx, 'j': cy, 'h': [h - M.SEA for h in hs], 'code': code}
                if best is None:
                    best = (entry, fr)
                elif best[0] != entry and not (best[0] is None and entry is None):
                    conflicts += 1
            if best and best[0]:
                cells[(cx, cy)] = best[0]
    return cells, conflicts


def ascii_map(cells, extent):
    cx0, cy0, cx1, cy1 = extent
    lines = []
    for cy in range(cy1 - 1, cy0 - 1, -1):
        row = f'{cy:3d} '
        for cx in range(cx0, cx1):
            c = cells.get((cx, cy))
            if c is None:
                row += '   .'
            else:
                row += f'{int(round(sum(c["h"]) / 4)):4d}'
        lines.append(row)
    lines.append('    ' + ''.join(f'{cx:4d}' for cx in range(cx0, cx1)))
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rom', required=True)
    ap.add_argument('--sweep', required=True)
    ap.add_argument('--level', type=int, default=0)
    ap.add_argument('--extent', nargs=4, type=int, default=[0, 0, 100, 100], metavar=('CX0', 'CY0', 'CX1', 'CY1'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--ascii', action='store_true')
    a = ap.parse_args(argv)
    frames = load_sweep(a.rom, a.sweep, a.level)
    print(f'{len(frames)} usable dumps for level {a.level}', file=sys.stderr)
    cells, conflicts = merge(frames, a.extent)
    xs = [c for c, _ in cells]; ys = [c for _, c in cells]
    ext = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
    out = {'level': a.level, 'sea': M.SEA, 'unit_cells': 8, 'extent': ext,
           'cells': [cells[k] for k in sorted(cells)]}
    with open(a.out, 'w') as f:
        json.dump(out, f)
    print(f'wrote {len(cells)} cells, extent {ext}, {conflicts} conflicts -> {a.out}', file=sys.stderr)
    if a.ascii:
        print(ascii_map(cells, ext))


if __name__ == '__main__':
    main()
