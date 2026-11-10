#!/usr/bin/env python3
"""Tile sheet for the reef surface-tile repaint: atlas tiles 0-7, before and after.

Usage (from the repo root):
  python3 docs/diagnostics/reef-tiles-2026-11-10/tile-sheet.py BEFORE_TREE OUTDIR

BEFORE_TREE holds a reef/ package at the earlier commit, e.g.
  git archive <rev> wflevels/aquarium_thai_reef/reef | tar -x -C build-docker/reef-tiles-before
and is used as BEFORE_TREE/wflevels/aquarium_thai_reef. The after atlas comes from the
current wflevels/aquarium_thai_reef. Writes tile-sheet-{realistic,anime}.png (each row:
before, after; each tile labelled with its luminance std dev and mean RGB) and
tile-stats.json.
"""
import importlib.util
import json
import statistics
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

if any(a in ('-h', '--help') for a in sys.argv[1:]) or len(sys.argv) != 3:
    print(__doc__)
    sys.exit(0 if any(a in ('-h', '--help') for a in sys.argv[1:]) else 2)
ROOT = Path(__file__).resolve().parents[3]
BEFORE = Path(sys.argv[1]).resolve() / 'wflevels/aquarium_thai_reef/reef/atlas.py'
AFTER = ROOT / 'wflevels/aquarium_thai_reef/reef/atlas.py'
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
NAMES = ('coralline', 'coral surface', 'sponge', 'sand', 'rock', 'flower heads', 'clam mantle', 'boxfish')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tiles(module, style):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'atlas.tga'
        module.write_atlas(path, style=style)
        image = Image.open(path).convert('RGB')
        image.load()
    crops, stats = [], []
    for t in range(8):
        x0, y0 = (t % 4) * 256, (t // 4) * 256
        crop = image.crop((x0, y0, x0 + 256, y0 + 256))
        px = list(crop.getdata())
        lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]
        mean = [round(sum(c) / len(px)) for c in zip(*px)]
        crops.append(crop)
        stats.append({'tile': t, 'name': NAMES[t], 'std': round(statistics.pstdev(lum), 1), 'mean_rgb': mean})
    return crops, stats


before, after = load(BEFORE, 'atlas_before'), load(AFTER, 'atlas_after')
summary = {}
for style in ('realistic', 'anime'):
    rows = [('before', *tiles(before, style)), ('after', *tiles(after, style))]
    sheet = Image.new('RGB', (8 * 260 + 80, 2 * 300 + 10), (24, 26, 30))
    draw = ImageDraw.Draw(sheet)
    for r, (label, crops, stats) in enumerate(rows):
        y = 10 + r * 300
        draw.text((8, y + 120), label, fill=(230, 230, 230))
        for t, (crop, st) in enumerate(zip(crops, stats)):
            x = 80 + t * 260
            sheet.paste(crop, (x, y))
            draw.text((x, y + 260), f"{t} {st['name']}", fill=(230, 230, 230))
            draw.text((x, y + 274), f"std {st['std']}  mean {tuple(st['mean_rgb'])}", fill=(200, 200, 200))
        summary.setdefault(style, {})[label] = stats
    sheet.save(OUT / f'tile-sheet-{style}.png')
    print('wrote', OUT / f'tile-sheet-{style}.png')
(OUT / 'tile-stats.json').write_text(json.dumps(summary, indent=1) + '\n')
