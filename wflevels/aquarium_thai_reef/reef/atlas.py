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
        sea-fan and feather-star base-to-tip gradients, humbug body scales
        (the humbug is Dascyllus reticulatus since D10, 2026-11-09)
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
# Dascyllus reticulatus (the 'humbug' pair, D10): a mid-grey swatch for the faint
# rear bar and anal fin, after the water bands (which end at UTIL_X + 136).
FISH_GREY = (UTIL_X + 152, UTIL_Y + 8)
# Its pale grey body with dark scale margins (the 'reticulated' net): a 64 x 64
# square at cell rows 192-255, so the projected UVs stay isotropic. Realistic only
# paints the net; anime keeps the body one flat tone.
HUMBUG_SCALES = (UTIL_X, UTIL_Y + 192, 64, 64)   # x, y, width, height
# Goniopora flowerpot skins (2026-11-10), each a 64-px region of cell 15:
# skeleton, polyp column, tentacles, mouth.
GONIOPORA = {'body': (UTIL_X + 64, UTIL_Y + 192, 64, 64), 'polyp': (UTIL_X + 128, UTIL_Y + 192, 64, 64),
             'tentacle': (UTIL_X + 192, UTIL_Y + 192, 64, 64), 'mouth': (UTIL_X, UTIL_Y + 64, 64, 32)}


NUDI_RIDGE_V = (.267, .5, .733)      # ridge centres across the mantle (v)
NUDI_SEED = 20261102
NUDI_CELL_W, NUDI_CELL_H = 255, 191  # painted mantle: u along x 0-255, v along y 0-191


def nudi_ridge_centre(k, x):
    """Ridge k's centre (v, 0-1) at mantle column x (0-255)."""
    return NUDI_RIDGE_V[k] + .012 * math.sin(x * .07 + k * 2.1)


def nudi_ridge_width(k, x):
    """Ridge k's half-width (v units) at column x."""
    return .040 + .022 * _smooth_noise(x, k * 50, 16, NUDI_SEED + 611)


def nudi_tubercles():
    """(x, y, radius) of every yellow tubercle, in mantle pixels. life.py
    raises a 3D tubercle on each, so geometry and paint coincide."""
    out = []
    for k in range(len(NUDI_RIDGE_V)):
        for cell_x in range(NUDI_CELL_W // 21 + 1):
            tx = cell_x * 21 + 10 + 6 * (_noise(cell_x, k, NUDI_SEED + 612) - .5)
            ty = (nudi_ridge_centre(k, tx) + .01 * (_noise(cell_x, k, NUDI_SEED + 613) - .5)) * NUDI_CELL_H
            out.append((tx, ty, 5.5 + 3.5 * _noise(cell_x, k, NUDI_SEED + 614)))
    return out


def _nudi_mantle(x, y, seed):
    """Phyllidia varicosa mantle, mapped top-down: u (x 0-255) runs along the
    body, v (y 0-191) across it. Black, faintly mottled; three raised,
    wavy blue-grey ridges carrying shaded yellow tubercles; small grey
    tubercles between them; short transverse ridges out to a grey rim.
    References: docs/reference/thai-reef-skin-colours.md."""
    v = y / NUDI_CELL_H
    mottle = _smooth_noise(x, y, 9, seed + 610) - .5
    base = tuple(c + 14 * mottle for c in (16, 17, 21))
    if v < .03 or v > .97:
        return (44, 50, 60)
    for tx, ty, radius in _NUDI_TUBERCLES:
        dx, dy = x - tx, y - ty
        if abs(dx) < radius and abs(dy) < radius:
            d = math.hypot(dx, dy) / radius
            if d < 1:
                colour = _mix((252, 222, 70), (232, 158, 36), d ** 1.8)
                glint = max(0.0, 1 - math.hypot(dx + radius * .35, dy + radius * .35) / (radius * .45))
                return _mix(colour, (255, 244, 190), glint * .8)
    for k in range(len(NUDI_RIDGE_V)):
        dv = abs(v - nudi_ridge_centre(k, x))
        width = nudi_ridge_width(k, x)
        if dv < width:
            profile = 1 - (dv / width) ** 2
            colour = _mix((66, 84, 104), (150, 172, 194), profile)
            return tuple(c + 10 * mottle for c in colour)
    # Short transverse ridges toward both margins.
    if v < .17 or v > .83:
        cell_x = x // 13
        rx = cell_x * 13 + 6 + 4 * (_noise(cell_x, int(v > .5), seed + 615) - .5)
        reach = .07 + .08 * _noise(cell_x, int(v > .5), seed + 616)
        edge = v if v < .5 else 1 - v
        if abs(x - rx) < 1.8 and edge < .03 + reach:
            return _mix((70, 86, 106), (126, 146, 168), 1 - abs(x - rx) / 1.8)
    # Scattered small grey tubercles on the black between ridges.
    cell_x, cell_y = x // 11, y // 11
    if _noise(cell_x, cell_y, seed + 617) > .72:
        sx = cell_x * 11 + 5 + 4 * (_noise(cell_x, cell_y, seed + 618) - .5)
        sy = cell_y * 11 + 5 + 4 * (_noise(cell_x, cell_y, seed + 619) - .5)
        if math.hypot(x - sx, y - sy) < 2.2:
            return (62, 72, 86)
    return base


def _posterise(rgb):
    """Anime: keep hue, snap brightness to one of three bands."""
    peak = max(rgb) or 1
    band = 40 if peak < 70 else 150 if peak < 175 else 245
    return tuple(c * band / peak for c in rgb)


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
        if y < 192:
            return _nudi_mantle(x, y, seed), 0
        if y < 224:                                # ridge tubes: mottled blue-grey
            return (120, 142, 166), 22 * smooth + 10 * grain - (18 if _noise(x, y, seed + 552) > .9 else 0)
        # tubercle caps: yellow mottled toward orange
        return _mix((246, 210, 52), (228, 136, 32), max(0.0, min(1.0, smooth + .45))), 6 * grain
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
    96: ((242, 244, 240), (196, 204, 206), (232, 234, 228), (232, 234, 228)),   # humbug fins/tail: pale grey
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


# Surface tiles 0-6 (reef tiles review, 2026-11-10). Each is painted from what the
# material looks like, with real contrast (luminance std dev about 25-50, against
# 5-8 before), shifted to keep its mean colour, and tileable so the world-projected
# repeat has no seams. Anime posterises the same shapes to three flat tones.
# Tile 7 is the boxfish's approved skin and keeps its own painter (_detail).
SURFACE_TILES = (0, 1, 2, 3, 4, 5, 6)


def _tvalue(ix, iy, n, seed):
    return _noise((ix % n) * 1543, (iy % n) * 2917, seed)


def _tnoise(x, y, cell, seed):
    """Tileable smooth value noise over the 256-px tile, lattice spacing `cell`."""
    n = CELL // cell
    gx, gy = x / cell, y / cell
    ix, iy = int(gx), int(gy)
    fx, fy = gx - ix, gy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _tvalue(ix, iy, n, seed), _tvalue(ix + 1, iy, n, seed)
    c, d = _tvalue(ix, iy + 1, n, seed), _tvalue(ix + 1, iy + 1, n, seed)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _fbm(x, y, seed, cells=(64, 32, 16, 8)):
    total = weight = 0.0
    w = 1.0
    for k, cell in enumerate(cells):
        total += w * _tnoise(x, y, cell, seed + 17 * k)
        weight += w
        w *= .55
    return total / weight


def _voronoi(x, y, cell, seed, jitter=.8):
    """Tileable cellular noise: (nearest distance, second distance, angle to nearest, id)."""
    n = CELL // cell
    cx, cy = x // cell, y // cell
    best = second = 1e9
    angle, ident = 0.0, 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            gx, gy = cx + dx, cy + dy
            wx, wy = gx % n, gy % n
            px = (gx + .5 + jitter * (_noise(wx, wy, seed) - .5)) * cell
            py = (gy + .5 + jitter * (_noise(wx, wy, seed + 1) - .5)) * cell
            dist = math.hypot(x - px, y - py)
            if dist < best:
                second, best = best, dist
                angle, ident = math.atan2(y - py, x - px), wx + n * wy
            elif dist < second:
                second = dist
    return best, second, angle, ident


def _surface_texel(tile, x, y, seed, fine=True):
    """Luminance offset for surface tile `tile` at (x, y) inside its 256-px cell.

    fine=False drops the per-texel grain (and the sand's specks), for anime, whose
    three posterised tones would otherwise break into speckle along each edge.
    """
    grain = _noise(x, y, seed + 900 + tile) - .5 if fine else 0.0
    if tile == 0:   # crustose coralline algae: mottled crust, pale growing margins, fine seams
        # Warp the cells so the crust patches are irregular, not paving stones.
        wx = (x + 14 * (_tnoise(x, y, 64, seed + 13) - .5)) % CELL
        wy = (y + 14 * (_tnoise(x, y, 64, seed + 14) - .5)) % CELL
        d1, d2, _, ident = _voronoi(int(wx), int(wy), 32, seed + 10)
        edge = d2 - d1
        tone = (_noise(ident, 7, seed + 11) - .5) * 30
        mottle = (_fbm(x, y, seed + 12, (32, 16, 8)) - .5) * 80
        seam = -26 * math.exp(-(edge / 1.4) ** 2)
        rim = 24 * math.exp(-((edge - 4.0) / 2.6) ** 2)
        return tone + mottle + seam + rim + 10 * grain
    if tile == 1:   # coral surface: corallite pits, septa and ridged walls
        d1, d2, angle, _ = _voronoi(x, y, 16, seed + 20, jitter=.55)
        edge = d2 - d1
        if d1 < 3.2:
            v = -42 * (1 - d1 / 3.2) - 10
        else:
            v = 8 * math.cos(angle * 12) * math.exp(-((d1 - 4.6) ** 2) / 3)
        if edge < 2.4:
            v += 30 * (1 - edge / 2.4)
        return v + (_fbm(x, y, seed + 21, (64, 32)) - .5) * 22 + 6 * grain
    if tile == 2:   # sponge: pores in a ridged, mottled surface
        d1, _, _, _ = _voronoi(x, y, 16, seed + 30, jitter=.7)
        ridge = 15 * math.sin((x + 9 * _tnoise(x, y, 32, seed + 31)) * math.tau / 32)
        if d1 < 3.0:
            return -62 + 6 * grain
        rim = 16 * math.exp(-((d1 - 3.8) ** 2) / 1.5)
        return ridge + rim + (_fbm(x, y, seed + 32, (32, 16)) - .5) * 30 + 8 * grain
    if tile == 3:   # sand: wind-ripple bands and scattered dark and pale grains
        warp = 10 * _tnoise(x, y, 64, seed + 40)
        ripple = 15 * math.sin((y + warp) * math.tau / 32)
        speck = _noise(x, y, seed + 41)
        dot = (-40 if speck < .07 else 30 if speck > .95 else 0) if fine else 0
        return ripple + dot + (_fbm(x, y, seed + 42, (32, 8)) - .5) * 16 + 12 * grain
    if tile == 4:   # live rock: crevices, pits, mineral grain and flecks
        crack = abs(_fbm(x, y, seed + 50, (64, 32, 16)) - .5)
        d1, _, _, _ = _voronoi(x, y, 32, seed + 51, jitter=.9)
        v = (_fbm(x, y, seed + 52, (64, 32, 16)) - .5) * 70
        v -= 24 * math.exp(-(crack / .016) ** 2)
        if d1 < 5.5:
            v -= 30 * (1 - d1 / 5.5) ** 1.5
        fleck = _noise(x, y, seed + 53)
        v += 22 if fleck > .988 and fine else 0
        return v + 12 * grain
    if tile == 5:   # zoanthid flower heads: dark mouths, striped discs, tentacle crowns
        d1, d2, angle, _ = _voronoi(x, y, 32, seed + 60, jitter=.3)
        if d1 < 3.5:
            return -60 + 6 * grain
        if d1 < 8.5:
            return 6 + 14 * math.cos(angle * 10) + 6 * grain
        if d1 < 13.5 and d2 - d1 > 2:
            return 34 * math.cos(angle * 8) ** 2 - 4 + 6 * grain
        return -46 + 8 * grain
    if tile == 6:   # giant clam mantle: wavy bands and iridescent spots
        band = 20 * math.sin((x + 7 * math.sin(y * math.tau / 64)) * math.tau / 32)
        d1, _, _, _ = _voronoi(x, y, 16, seed + 70, jitter=.8)
        spot = 42 * max(0.0, 1 - d1 / 2.8)
        return band + spot + (_fbm(x, y, seed + 71, (32, 16)) - .5) * 20 + 6 * grain
    raise ValueError(tile)


def _surface_shades(seed, style):
    """Per-tile 256 x 256 luminance offsets with a zero mean (the mean colour holds).

    Realistic uses the painted offsets; anime posterises them to three flat tones
    (dark, mid, light), so the same shapes read under its toon bands and outlines.
    """
    key = (seed, style)
    if key in _SURFACE_CACHE:
        return _SURFACE_CACHE[key]
    shades = {}
    for tile in SURFACE_TILES:
        values = [_surface_texel(tile, x, y, seed, fine=style == 'realistic')
                  for y in range(CELL) for x in range(CELL)]
        if style == 'anime':
            ordered = sorted(values)
            lo, hi = ordered[len(ordered) // 4], ordered[3 * len(ordered) // 4]
            dark, light = ANIME_TONES.get(tile, (-42.0, 38.0))
            values = [dark if v < lo else light if v > hi else 0.0 for v in values]
        mean = sum(values) / len(values)
        values = [v - mean for v in values]
        if style == 'realistic':
            # Scale the painted offsets to the tile's target contrast (std dev).
            std = (sum(v * v for v in values) / len(values)) ** .5 or 1.0
            gain = SURFACE_CONTRAST[tile] / std
            values = [v * gain for v in values]
        shades[tile] = values
    _SURFACE_CACHE[key] = shades
    return shades


# Target luminance std dev per surface tile, realistic style (the brief: 30-60).
# Sand and the clam mantle stay lower so the sand bed and the mantle do not get noisy.
SURFACE_CONTRAST = {0: 42, 1: 42, 2: 40, 3: 28, 4: 40, 5: 46, 6: 32}
# Anime dark and light tone offsets; the sand stays quiet so its ripples do not band the floor.
ANIME_TONES = {3: (-16.0, 12.0)}
_SURFACE_CACHE = {}


def _goniopora_texel(part, x, y, style, seed):
    """Goniopora skins: x, y inside the part's region. Anime posterises to three tones."""
    grain = _noise(x, y, seed + 801) - .5
    if part == 'body':      # tan-brown skeleton, dark corallite pits, pale walls
        base = (150, 116, 82) if style == 'realistic' else (176, 128, 84)
        n = 64
        d1, d2 = _voronoi_n(x, y, 8, n, seed + 802)
        v = -70 * max(0.0, 1 - d1 / 3.0) + 26 * max(0.0, 1 - (d2 - d1) / 1.6) + 12 * grain
    elif part == 'polyp':   # purple column with fine stripes along the polyp
        base = (142, 100, 176) if style == 'realistic' else (176, 102, 220)
        v = 20 * math.cos(x * math.tau / 8) + 10 * (_tnoise_n(x, y, 16, 64, seed + 803) - .5) + 8 * grain
    elif part == 'tentacle':  # lighter purple with pale bands
        base = (170, 132, 202) if style == 'realistic' else (204, 140, 240)
        v = 26 * math.cos(y * math.tau / 10) + 8 * grain
    else:                   # pale cream-lilac mouth disc
        base = (226, 210, 222) if style == 'realistic' else (246, 226, 244)
        v = 14 * (_tnoise_n(x, y, 8, 64, seed + 804) - .5) + 6 * grain
    if style == 'anime':
        v = -34 if v < -12 else 26 if v > 12 else 0
    return [max(0, min(255, round(c + v))) for c in base]


def _tnoise_n(x, y, cell, size, seed):
    """Tileable value noise over a `size`-px region."""
    n = size // cell
    gx, gy = x / cell, y / cell
    ix, iy = int(gx), int(gy)
    fx, fy = gx - ix, gy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _tvalue(ix, iy, n, seed), _tvalue(ix + 1, iy, n, seed)
    c, d = _tvalue(ix, iy + 1, n, seed), _tvalue(ix + 1, iy + 1, n, seed)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _voronoi_n(x, y, cell, size, seed):
    """Cellular noise tileable over a `size`-px region: (nearest, second nearest)."""
    n = size // cell
    cx, cy = x // cell, y // cell
    best = second = 1e9
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            gx, gy = cx + dx, cy + dy
            wx, wy = gx % n, gy % n
            px = (gx + .5 + .6 * (_noise(wx, wy, seed) - .5)) * cell
            py = (gy + .5 + .6 * (_noise(wx, wy, seed + 1) - .5)) * cell
            dist = math.hypot(x - px, y - py)
            if dist < best:
                second, best = best, dist
            elif dist < second:
                second = dist
    return best, second


def _humbug_scale_texel(x, y, style, seed):
    """Dascyllus reticulatus body: pale grey, blackish scale margins (FishBase).

    A diamond lattice of 8-px scales: texels on either diagonal line are the
    darker scale margins, which read as a net at close range and as a slightly
    darker grey from the wide camera. Anime is flat.
    """
    if style == 'anime':
        return [214, 218, 220]
    base = (212, 216, 216)      # uniform: the mirrored UV repeat would band a gradient
    grain = (_smooth_noise(x, y, 4, seed + 911) - .5) * 8
    edge = min((x + y) % 8, (8 - (x + y) % 8) % 8, (x - y) % 8, (8 - (x - y) % 8) % 8)
    rim = -58 if edge == 0 else -18 if edge == 1 else 0
    return [max(0, min(255, round(c + grain + rim))) for c in base]


def write_atlas(path, seed=20261102, style='realistic'):
    """Write deterministic BGR pixels in top-left TGA order."""
    if style not in ('realistic', 'anime'):
        raise ValueError(f'unknown reef style: {style}')
    palette = BASE if style == 'realistic' else ANIME
    surface = _surface_shades(seed, style)
    out=bytearray(struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,SIZE,SIZE,24,0x20))
    for y in range(SIZE):
        for x in range(SIZE):
            i = (y // CELL) * 4 + (x // CELL)
            local_x, local_y = x % CELL, y % CELL
            if i == WORM_CELL:
                rgb = _worm_texel(local_x, local_y, style)
            elif i in surface:
                rgb = [max(0, min(255, round(c + surface[i][local_y * CELL + local_x])))
                       for c in palette[i]]
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
                    if i == 12 and local_y < 192:      # painted mantle: posterise whole
                        base, shade = _posterise(_saturate(base)), 0
                    else:
                        base, shade = _saturate(base), round(shade / 22) * 22
                rgb = [max(0, min(255, round(c + shade))) for c in base]
            else:
                rgb = [128, 128, 128]
            if i == UTILITY_CELL:
                # Small flat swatches for fish markings and the outline hull.
                if UTIL_Y <= y < UTIL_Y + 16 and UTIL_X <= x < UTIL_X + 32:
                    rgb = [18, 19, 22] if x < UTIL_X + 16 else [245, 245, 237]
                if UTIL_Y <= y < UTIL_Y + 16 and FISH_GREY[0] - 8 <= x < FISH_GREY[0] + 8:
                    rgb = [112, 116, 120] if style == 'realistic' else [118, 122, 132]
                hx, hy, hw, hh = HUMBUG_SCALES
                if hx <= x < hx + hw and hy <= y < hy + hh:
                    rgb = _humbug_scale_texel(x - hx, y - hy, style, seed)
                for part, (gx0, gy0, gw, gh) in GONIOPORA.items():
                    if gx0 <= x < gx0 + gw and gy0 <= y < gy0 + gh:
                        rgb = _goniopora_texel(part, x - gx0, y - gy0, style, seed)
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


_NUDI_TUBERCLES = nudi_tubercles()
