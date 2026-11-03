"""Deterministic procedural 1024-square reef material atlas."""
from pathlib import Path
import math
import struct

SIZE = 1024
TILES = ('coralline','polyp','sponge','sand','rock','zoanthid','clam','fish')
BASE = ((171,105,148),(202,145,128),(182,112,68),(213,197,158),
        (115,111,91),(151,115,164),(61,153,155),(222,183,72))
ANIME = ((224,102,179),(255,155,108),(248,111,64),(244,219,157),
         (111,96,82),(205,109,225),(49,194,207),(255,213,52))


def _noise(x,y,seed):
    v = (x*374761393 + y*668265263 + seed*1442695041) & 0xffffffff
    v = ((v ^ (v >> 13))*1274126177) & 0xffffffff
    return ((v ^ (v >> 16)) & 255) / 255.0


def _value(ix, iy, seed):
    return _noise(ix * 1543, iy * 2917, seed)


def _smooth_noise(x, y, scale, seed):
    gx, gy = x / scale, y / scale
    ix, iy = int(gx), int(gy)
    fx, fy = gx - ix, gy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _value(ix, iy, seed)
    b = _value(ix + 1, iy, seed)
    c = _value(ix, iy + 1, seed)
    d = _value(ix + 1, iy + 1, seed)
    return (a * (1-fx) + b * fx) * (1-fy) + (c * (1-fx) + d * fx) * fy


def _detail(tile, x, y, seed):
    """Return a repeating, species-appropriate luminance variation."""
    if tile == 1:  # small coral polyps
        cell_x, cell_y = x // 24, y // 24
        dx = x % 24 - 12 + 5 * (_noise(cell_x, cell_y, seed + 101) - .5)
        dy = y % 24 - 12 + 5 * (_noise(cell_x, cell_y, seed + 102) - .5)
        r = math.hypot(dx, dy)
        # Contrasting calices and surrounding tissue remain visible at tank
        # distance, including on the broad Porites and Acropora surfaces.
        return (-24 * math.exp(-(r * r) / 11)
                + 14 * math.exp(-((r - 6) ** 2) / 7)
                + 8 * (_smooth_noise(x, y, 12, seed + 104) - .5)
                + 5 * (_noise(x, y, seed + 103) - .5))
    if tile == 2:  # barrel-sponge pores
        dx, dy = (x + 11) % 22 - 11, (y + 11) % 22 - 11
        r = math.hypot(dx, dy)
        return -23 * math.exp(-(r * r) / 12) + 6 * math.sin(r * 1.8)
    if tile == 3:  # sand grains
        return 7 * (_noise(x, y, seed + 77) - .5)
    if tile == 4:  # rough live-rock pits and mineral flecks
        coarse = _smooth_noise(x, y, 25, seed + 19)
        pits = _smooth_noise(x, y, 7, seed + 33)
        return (coarse - .5) * 34 + (pits - .5) * 19
    if tile == 5:  # zoanthid flower heads
        dx, dy = (x + 21) % 42 - 21, (y + 21) % 42 - 21
        angle = math.atan2(dy, dx)
        r = math.hypot(dx, dy)
        return 14 * math.cos(angle * 8) * math.exp(-((r - 11) ** 2) / 28) - 15 * (r < 4)
    if tile == 6:  # radial giant-clam mantle
        dx, dy = x - 128, y - 512
        angle = math.atan2(dx, max(1, abs(dy)))
        return 18 * math.sin(angle * 34 + math.hypot(dx, dy) * .012)
    if tile == 7:  # yellow juvenile boxfish spots and bars
        bars = 18 if ((x + 2 * y) // 46) % 5 == 0 else 0
        spot = -36 if ((x // 37 + 2 * y // 53) % 7 == 0 and (x % 37 - 18) ** 2 + (y % 53 - 26) ** 2 < 28) else 0
        return bars + spot
    return (_smooth_noise(x, y, 15, seed + 7) - .5) * 22


def write_atlas(path, seed=20261102, style='realistic'):
    """Write deterministic BGR pixels in top-left TGA order."""
    if style not in ('realistic', 'anime'):
        raise ValueError(f'unknown reef style: {style}')
    palette = BASE if style == 'realistic' else ANIME
    out=bytearray(struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,SIZE,SIZE,24,0x20))
    for y in range(SIZE):
        for x in range(SIZE):
            i=(y//512)*4+(x//256)
            base=palette[i]
            local_x, local_y = x % 256, y % 512
            detail = _detail(i, local_x, local_y, seed)
            noise = (_noise(x, y, seed) - .5) * (5 if style == 'realistic' else 2)
            wave = 3 * math.sin(x * .025) * math.sin(y * .02)
            shade = detail + noise + wave
            if style == 'anime':
                shade = round(shade / 22) * 22
            rgb=[max(0,min(255,round(c+shade))) for c in base]
            # Small flat swatches for fish markings, sampled at their centres.
            if 768 <= x < 800 and 512 <= y < 528:
                rgb = [18, 19, 22] if x < 784 else [245, 245, 237]
            if 800 <= x < 896 and 512 <= y < 528:
                band = (x - 800) // 16
                if style == 'anime':
                    rgb = [8 + 4 * band, 65 + 17 * band, 128 + 17 * band]
                else:
                    rgb = [8 + 3 * band, 44 + 8 * band, 64 + 10 * band]
            out.extend((rgb[2],rgb[1],rgb[0]))
    Path(path).write_bytes(out)

