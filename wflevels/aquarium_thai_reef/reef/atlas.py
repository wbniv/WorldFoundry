"""Deterministic procedural 1024-square reef material atlas.

Layout: 16 cells of 256 x 256, cell i at x = (i % 4) * 256, y = (i // 4) * 256
(top-left origin; UV v = y / 1024 in this pipeline).
  0-7   surface tiles, TILES order (world-projected UVs)
  8     Christmas tree worm morphs: 8 rows of 32 px, root -> tip along v
  9     feather-duster radioles (light, dark) and tube
  10    guard crab: shell, legs, claw fingers
  11    banded shrimp: red and white bands
  12    nudibranch: body, ridges, tubercle gradient
  13    hermit crab: borrowed shell, legs, shell lip
  14    encrusting sponge and coralline crusts
  15    utility: flat fish swatches, water bands, clam shell, humbug sheen,
        sea-fan and feather-star base-to-tip gradients
Colour references: docs/reference/thai-reef-skin-colours.md
"""
from pathlib import Path
import math
import struct

SIZE = 1024
CELL = 256
WORM_CELL = 8
UTILITY_CELL = 15
TILES = ('coralline','polyp','sponge','sand','rock','zoanthid','clam','fish')
BASE = ((171,105,148),(202,145,128),(182,112,68),(213,197,158),
        (115,111,91),(151,115,164),(61,153,155),(222,183,72))
ANIME = ((224,102,179),(255,155,108),(248,111,64),(244,219,157),
         (111,96,82),(205,109,225),(49,194,207),(255,213,52))

# Christmas tree worm morphs (plan D1): realistic and anime root/tip colours.
WORM_MORPHS = (
    ('blue', (47, 99, 201), (159, 196, 255), (42, 108, 255), (191, 224, 255)),
    ('red', (184, 40, 46), (255, 157, 122), (232, 48, 58), (255, 192, 160)),
    ('orange', (217, 112, 31), (255, 208, 138), (255, 138, 28), (255, 224, 160)),
    ('yellow', (216, 182, 42), (255, 242, 166), (255, 213, 42), (255, 248, 200)),
    ('white', (205, 208, 202), (255, 255, 255), (242, 244, 240), (255, 255, 255)),
    ('purple', (122, 63, 168), (212, 168, 255), (155, 78, 224), (230, 200, 255)),
    ('blue-white', (47, 99, 201), (250, 250, 250), (42, 108, 255), (255, 255, 255)),
    ('red-white', (184, 40, 46), (250, 250, 250), (232, 48, 58), (255, 255, 255)),
)
# Utility cell texel centres, in atlas pixels (u = x / 1024, v = y / 1024).
UTIL_X, UTIL_Y = (UTILITY_CELL % 4) * CELL, (UTILITY_CELL // 4) * CELL
FISH_DARK = (UTIL_X + 8, UTIL_Y + 8)
FISH_WHITE = (UTIL_X + 24, UTIL_Y + 8)
WATER_X0 = UTIL_X + 40          # six 16-px bands from here, centre +8
CLAM_SHELL = (UTIL_X, UTIL_Y + 32, 128, 32)   # x, y, width, height


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _saturate(rgb, k=1.25):
    m = sum(rgb) / 3
    return tuple(m + (c - m) * k for c in rgb)


def _creature_texel(cell, x, y, seed):
    """(base rgb, shade) for creature cells 9-14 at cell-local x, y."""
    grain = (_noise(x, y, seed + 500 + cell) - .5)
    smooth = _smooth_noise(x, y, 14, seed + 520 + cell) - .5
    if cell == 9:                                  # Sabellastarte radioles and tube
        if y < 96:
            return (226, 206, 168), (-58 if (x + y) % 8 == 0 else 0) + 8 * grain
        if y < 192:
            return (96, 58, 36), (46 if (x - y) % 8 == 0 else 0) + 8 * grain
        return (128, 116, 92), 30 * grain + 10 * smooth
    if cell == 10:                                 # Trapezia cymodoce
        if y < 128:
            cx, cy = x // 32, y // 32
            spot = _noise(cx, cy, seed + 531) > .78
            dx = x % 32 - 8 - 16 * _noise(cx, cy, seed + 532)
            dy = y % 32 - 8 - 16 * _noise(cx, cy, seed + 533)
            if spot and dx * dx + dy * dy < 18:
                return (232, 96, 52), 6 * grain
            return (172, 88, 46), 22 * smooth + 6 * grain
        if y < 208:
            return ((70, 38, 26) if (x // 20) % 4 == 0 else (150, 76, 42)), 8 * grain
        return (52, 30, 24), 10 * grain
    if cell == 11:                                 # Stenopus hispidus bands
        if y < 128:
            fleck = 40 if _noise(x, y, seed + 541) > .93 else 0
            return (200, 32, 40), fleck + 14 * smooth + 6 * grain
        return (240, 236, 226), (-18 if y % 16 == 0 else 0) + 6 * grain
    if cell == 12:                                 # Phyllidia varicosa
        if y < 128:
            return (16, 17, 20), (22 if _noise(x, y, seed + 551) > .9 else 0) + 4 * grain
        if y < 192:
            return (122, 146, 170), 18 * smooth + 6 * grain
        return _mix((232, 140, 30), (242, 204, 40), (y - 192) / 63), 6 * grain
    if cell == 13:                                 # Dardanus lagopodes in a borrowed shell
        if y < 128:
            band = math.sin((x * .6 + y * .9) / 3.5) > .72     # fine spiral growth lines
            return ((120, 82, 52) if band else (214, 196, 160)), 14 * smooth + 6 * grain
        if y < 192:
            if _noise(x, y, seed + 561) > .95:
                return (235, 230, 220), 0
            return _mix((138, 58, 46), (92, 34, 40), max(0.0, min(1.0, smooth + .5))), 6 * grain
        return (236, 224, 200), 12 * smooth + 4 * grain
    # cell 14: encrusting crusts
    if y < 128:
        pore = (x % 10 - 5) ** 2 + (y % 10 - 5) ** 2 < 4
        return (190, 110, 60), (-40 if pore else 0) + 14 * smooth + 6 * grain
    bump = _smooth_noise(x, y, 5, seed + 571) - .5
    return (178, 98, 150), 26 * smooth + 22 * bump + 4 * grain


# Utility gradients: (realistic base, realistic tip, anime base, anime tip).
GRADIENTS = {
    96: ((250, 250, 246), (200, 210, 222), (245, 245, 237), (245, 245, 237)),   # humbug: belly -> back
    128: ((100, 44, 112), (222, 152, 218), (178, 60, 168), (250, 156, 236)),    # sea fan
    160: ((130, 58, 96), (232, 178, 200), (200, 70, 140), (255, 192, 222)),     # feather star
}


def _worm_texel(x, y, style):
    """Worm cell: per-row morph gradient with radiole striations along u."""
    morph = min(7, y // 32)
    t = ((y % 32) - 4) / 24
    t = max(0.0, min(1.0, t))
    _, rb, rt, ab, at = WORM_MORPHS[morph]
    base, tip = (rb, rt) if style == 'realistic' else (ab, at)
    if style == 'anime':
        t = 0.0 if t < .4 else .55 if t < .8 else 1.0
    stripe = 1.0 if style == 'anime' else (.82 if x % 4 == 0 else 1.0)
    return [max(0, min(255, round((b + (c - b) * t) * stripe))) for b, c in zip(base, tip)]


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
    if tile == 6:  # radial giant-clam mantle, centred on the cell's lower edge
        dx, dy = x - 128, y - 256
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
            i = (y // CELL) * 4 + (x // CELL)
            local_x, local_y = x % CELL, y % CELL
            if i == WORM_CELL:
                rgb = _worm_texel(local_x, local_y, style)
            elif i < len(TILES):
                base = palette[i]
                detail = _detail(i, local_x, local_y, seed)
                noise = (_noise(x, y, seed) - .5) * (5 if style == 'realistic' else 2)
                wave = 3 * math.sin(x * .025) * math.sin(y * .02)
                shade = detail + noise + wave
                if style == 'anime':
                    shade = round(shade / 22) * 22
                rgb = [max(0, min(255, round(c + shade))) for c in base]
            elif i < UTILITY_CELL:
                base, shade = _creature_texel(i, local_x, local_y, seed)
                if style == 'anime':
                    base, shade = _saturate(base), round(shade / 22) * 22
                rgb = [max(0, min(255, round(c + shade))) for c in base]
            else:
                rgb = [128, 128, 128]
            if i == UTILITY_CELL:
                # Small flat swatches for fish markings and the outline hull.
                if UTIL_Y <= y < UTIL_Y + 16 and UTIL_X <= x < UTIL_X + 32:
                    rgb = [18, 19, 22] if x < UTIL_X + 16 else [245, 245, 237]
                if UTIL_Y <= y < UTIL_Y + 16 and WATER_X0 <= x < WATER_X0 + 96:
                    band = (x - WATER_X0) // 16
                    if style == 'anime':
                        rgb = [8 + 4 * band, 65 + 17 * band, 128 + 17 * band]
                    else:
                        rgb = [8 + 3 * band, 44 + 8 * band, 64 + 10 * band]
                gy = local_y - local_y % 32
                if gy in GRADIENTS:
                    rb, rt, ab, at = GRADIENTS[gy]
                    t = 1 - (local_y - gy) / 31          # strip bottom = base, top = tip
                    if style == 'anime':
                        t = 0.0 if t < .34 else .5 if t < .67 else 1.0
                        rgb = [round(c) for c in _mix(ab, at, t)]
                    else:
                        rgb = [round(c) for c in _mix(rb, rt, t)]
                cx, cy, cw, ch = CLAM_SHELL
                if cx <= x < cx + cw and cy <= y < cy + ch:
                    grain = _smooth_noise(x, y, 5, seed + 231) - .5
                    ridge = math.cos((x - cx) * math.tau / 12)
                    value = 14 * grain + 20 * ridge
                    if style == 'anime':
                        value = round(value / 18) * 18
                    base_shell = (191, 161, 126) if style == 'realistic' else (211, 174, 125)
                    rgb = [max(0, min(255, round(c + value))) for c in base_shell]
            out.extend((rgb[2],rgb[1],rgb[0]))
    Path(path).write_bytes(out)

