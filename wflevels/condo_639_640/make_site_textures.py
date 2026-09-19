#!/usr/bin/env python3
"""make_site_textures.py — the condo level's sky dome and ground map from OpenStreetMap.

    make_site_textures.py fetch            # Overpass → site-osm.json (network; run once / to refresh)
    make_site_textures.py render [--preview DIR]
                                           # site-osm.json → condo_ground.tga + condo_sky.tga (offline,
                                           # byte-stable); --preview also writes PNGs + the plan mockup

Outputs (beside the .lev, where textile-rs picks textures up):
  condo_ground.tga  512×512  north-up flat map ±GROUND_HALF m around the pin — the `site-map`
                    quad's texture. Image top = north = level +X, image right = east = level −Y.
  condo_sky.tga     1024×512 equirectangular panorama from the 6th-floor viewpoint (UNIT_Z):
                    u = θ/360 (0 N, 0.25 E, 0.5 S, 0.75 W), v = 1 zenith. Sky gradient + haze +
                    sun glow above the horizon; every OSM building as a wall/roof band at its true
                    azimuth span and elevation; below the horizon the flat ground palette projected
                    from the viewpoint, so the dome continues the ground quad beyond ±80 m.

Both are 24-bit RGB TGA (a 32-bit RGBA TGA packs to an all-zero atlas — troubleshooting
§ "Room0.tga is 146 bytes") with an ordered dither so the engine's 15-bit colour doesn't band.
Data © OpenStreetMap contributors, ODbL. Plan: docs/plans/2026-09-19-condo-site-skybox.md
"""
import argparse
import base64
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_constants import (SITE_LATLON, SITE_OFFSET_EN, UNIT_Z, GROUND_HALF, GROUND_PX, SKY_W, SKY_H,
                            sun_compass, level_to_compass)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OSM_JSON   = os.path.join(SCRIPT_DIR, 'site-osm.json')
GROUND_TGA = os.path.join(SCRIPT_DIR, 'condo_ground.tga')
SKY_TGA    = os.path.join(SCRIPT_DIR, 'condo_sky.tga')

LAT0, LON0 = SITE_LATLON
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))

NEAR_R   = 700      # every building this close (ground map + near skyline)
FAR_R    = 2500     # farther out only buildings that carry a height / levels tag
WATER_R  = 3000
ROADS_R  = 400
GREEN_R  = 700

# ── Flat palette (RGB 0–255) — the level's doll-house look, not a photo ───────
PAL = {
    'ground':   (196, 186, 168),   # bare / unmapped lot
    'road':     (110, 112, 118),
    'soi':      (150, 150, 152),
    'path':     (172, 168, 160),
    'water':    ( 92, 132, 168),
    'green':    (128, 156, 104),
    'roof':     (176, 172, 166),
    'roof_own': (150, 146, 140),   # the condo's own footprint, under the units
    'wall':     (158, 150, 140),
    'zenith':   ( 74, 122, 190),
    'horizon':  (206, 214, 222),
    'haze':     (214, 216, 218),
    'sun':      (255, 246, 214),
}


# ── Geometry helpers ──────────────────────────────────────────────────────────
def to_en(lat, lon):
    """(lat, lon) → (east, north) metres from the level origin (pin + SITE_OFFSET_EN)."""
    return ((lon - LON0) * M_PER_DEG_LON - SITE_OFFSET_EN[0],
            (lat - LAT0) * M_PER_DEG_LAT - SITE_OFFSET_EN[1])


def en_to_level(e, n):
    """(east, north) → level (x, y): +X north, +Y west."""
    return n, -e


def building_height(tags):
    h = tags.get('height')
    if h:
        try:
            return float(str(h).replace('m', '').strip())
        except ValueError:
            pass
    lv = tags.get('building:levels')
    if lv:
        try:
            return float(lv) * 3.0
        except ValueError:
            pass
    return 10.0


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                inside = not inside
    return inside


# ── fetch ─────────────────────────────────────────────────────────────────────
OVERPASS = 'https://overpass-api.de/api/interpreter'

QUERY = f"""
[out:json][timeout:120];
(
  way["building"](around:{NEAR_R},{LAT0},{LON0});
  way["building"]["height"](around:{FAR_R},{LAT0},{LON0});
  way["building"]["building:levels"](around:{FAR_R},{LAT0},{LON0});
  way["highway"](around:{ROADS_R},{LAT0},{LON0});
  way["natural"="water"](around:{WATER_R},{LAT0},{LON0});
  relation["natural"="water"](around:{WATER_R},{LAT0},{LON0});
  way["waterway"](around:{WATER_R},{LAT0},{LON0});
  way["landuse"~"grass|recreation_ground|cemetery|forest|orchard|farmland|meadow"](around:{GREEN_R},{LAT0},{LON0});
  way["leisure"~"park|garden|pitch|playground"](around:{GREEN_R},{LAT0},{LON0});
);
out geom;
"""


def fetch():
    import requests
    print(f"[site] Overpass query around {LAT0}, {LON0} …")
    # Overpass answers 406 to python-requests' default User-Agent; identify the project.
    r = requests.post(OVERPASS, data={'data': QUERY}, timeout=180,
                      headers={'User-Agent': 'worldfoundry-condo-level/1.0 (+https://worldfoundry.org)'})
    r.raise_for_status()
    raw = r.json()
    elems = []
    for el in raw.get('elements', []):
        tags = el.get('tags', {}) or {}
        keep = {k: tags[k] for k in ('building', 'height', 'building:levels', 'highway', 'natural',
                                     'water', 'waterway', 'landuse', 'leisure', 'name', 'name:en', 'type')
                if k in tags}
        if el['type'] == 'way':
            geom = [(g['lat'], g['lon']) for g in el.get('geometry', [])]
            if len(geom) < 2:
                continue
            elems.append({'type': 'way', 'id': el['id'], 'tags': keep, 'geom': geom})
        elif el['type'] == 'relation':
            members = []
            for m in el.get('members', []):
                g = m.get('geometry')
                if g and m.get('type') == 'way':
                    members.append({'role': m.get('role', ''), 'geom': [(p['lat'], p['lon']) for p in g]})
            if members:
                elems.append({'type': 'relation', 'id': el['id'], 'tags': keep, 'members': members})
    out = {'_source': 'OpenStreetMap contributors, ODbL — https://www.openstreetmap.org/copyright',
           'pin': [LAT0, LON0], 'elements': elems}
    with open(OSM_JSON, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    kinds = {}
    for e in elems:
        k = next((t for t in ('building', 'highway', 'natural', 'waterway', 'landuse', 'leisure') if t in e['tags']), '?')
        kinds[k] = kinds.get(k, 0) + 1
    print(f"[site] wrote {OSM_JSON}: {len(elems)} elements {kinds}, {os.path.getsize(OSM_JSON)//1024} KB")


# ── classify ──────────────────────────────────────────────────────────────────
def load_osm():
    with open(OSM_JSON) as f:
        data = json.load(f)
    buildings, roads, water_polys, water_lines, greens = [], [], [], [], []
    for el in data['elements']:
        t = el['tags']
        if el['type'] == 'way':
            pts = [en_to_level(*to_en(la, lo)) for la, lo in el['geom']]
            closed = len(pts) > 3 and el['geom'][0] == el['geom'][-1]
            if 'building' in t and closed:
                buildings.append((pts[:-1], building_height(t), t))
            elif 'highway' in t:
                roads.append((pts, t['highway']))
            elif (t.get('natural') == 'water' or t.get('waterway') in ('riverbank',)) and closed:
                water_polys.append(pts[:-1])
            elif 'waterway' in t:
                water_lines.append((pts, t['waterway']))
            elif ('landuse' in t or 'leisure' in t) and closed:
                greens.append(pts[:-1])
        else:   # relation (multipolygon water): stitch outer members into rings
            rings = stitch_rings([m['geom'] for m in el['members'] if m['role'] in ('outer', '')])
            for ring in rings:
                water_polys.append([en_to_level(*to_en(la, lo)) for la, lo in ring])
    return buildings, roads, water_polys, water_lines, greens


def stitch_rings(ways):
    """Join way fragments end-to-end into closed rings (OSM multipolygon outers)."""
    ways = [list(w) for w in ways if len(w) > 1]
    rings = []
    while ways:
        ring = ways.pop(0)
        changed = True
        while changed and ring[0] != ring[-1]:
            changed = False
            for i, w in enumerate(ways):
                if w[0] == ring[-1]:
                    ring += w[1:]; ways.pop(i); changed = True; break
                if w[-1] == ring[-1]:
                    ring += list(reversed(w))[1:]; ways.pop(i); changed = True; break
                if w[-1] == ring[0]:
                    ring = w[:-1] + ring; ways.pop(i); changed = True; break
                if w[0] == ring[0]:
                    ring = list(reversed(w))[:-1] + ring; ways.pop(i); changed = True; break
        if len(ring) > 3:
            rings.append(ring)
    return rings


def own_building(buildings):
    """Index of the footprint containing the pin, or None — never a neighbour by proximity
    (the pin resolves to the Soi Sathu Pradit 34 / Sathu Pradit Road corner, which OSM has
    as road, not building; a wrong 'own' footprint would be painted darker under the units)."""
    for i, (pts, h, t) in enumerate(buildings):
        if point_in_poly(0.0, 0.0, pts):
            return i
    return None


# ── ground raster (level metres → pixels) ─────────────────────────────────────
def draw_ground(size_px, half_m, buildings, roads, water_polys, water_lines, greens, own_idx):
    """North-up flat map. Level x (north) → image up, level y (west) → image left."""
    img = Image.new('RGB', (size_px, size_px), PAL['ground'])
    d = ImageDraw.Draw(img)
    s = size_px / (2.0 * half_m)

    def P(pt):
        x, y = pt                     # x north, y west
        return (size_px / 2.0 - y * s, size_px / 2.0 - x * s)

    for poly in greens:
        d.polygon([P(p) for p in poly], fill=PAL['green'])
    for poly in water_polys:
        d.polygon([P(p) for p in poly], fill=PAL['water'])
    for pts, kind in water_lines:
        w = {'river': 40, 'canal': 10, 'stream': 4}.get(kind, 4)
        d.line([P(p) for p in pts], fill=PAL['water'], width=max(1, int(w * s)))
    for pts, kind in roads:
        if kind in ('primary', 'secondary', 'tertiary', 'trunk', 'primary_link', 'secondary_link'):
            col, w = PAL['road'], 12
        elif kind in ('residential', 'unclassified', 'living_street', 'service'):
            col, w = PAL['soi'], 6
        else:
            col, w = PAL['path'], 2
        d.line([P(p) for p in pts], fill=col, width=max(1, int(w * s)), joint='curve')
    for i, (pts, h, t) in enumerate(buildings):
        d.polygon([P(p) for p in pts], fill=PAL['roof_own'] if i == own_idx else PAL['roof'])
    return img


# ── sky panorama ──────────────────────────────────────────────────────────────
def draw_sky(buildings, ground_far, far_half_m, own_idx):
    W, H = SKY_W, SKY_H
    cols = (np.arange(W) + 0.5) / W
    rows = (np.arange(H) + 0.5) / H
    theta = cols * 360.0                          # compass azimuth per column
    phi = 90.0 - rows * 180.0                     # elevation per row (+ up)
    img = np.zeros((H, W, 3), np.float32)

    # sky gradient (rows above horizon) — zenith → horizon with a haze band
    up = phi > 0
    t = np.clip(phi[up] / 90.0, 0, 1)[:, None]
    zen, hor, haze = (np.array(PAL[k], np.float32) for k in ('zenith', 'horizon', 'haze'))
    grad = hor + (zen - hor) * (t ** 0.65)
    band = np.exp(-(phi[up] / 6.0) ** 2)[:, None]          # haze thickens at the horizon
    img[up] = (grad * (1 - band * 0.5) + haze * band * 0.5)[:, None, :]

    # sun glow + disc
    sth, salt = sun_compass()
    dth = np.deg2rad(theta[None, :] - sth)
    ang = np.arccos(np.clip(np.sin(np.deg2rad(phi))[:, None] * math.sin(math.radians(salt))
                            + np.cos(np.deg2rad(phi))[:, None] * math.cos(math.radians(salt)) * np.cos(dth), -1, 1))
    glow = np.exp(-(np.rad2deg(ang) / 10.0) ** 2) * 0.55 + (np.rad2deg(ang) < 1.2) * 1.0
    glow = np.clip(glow, 0, 1)[:, :, None] * up[:, None, None]
    img = img * (1 - glow) + np.array(PAL['sun'], np.float32) * glow

    # below the horizon: ground plane seen from UNIT_Z, sampled from the far ground raster
    dn = phi < 0
    dist = UNIT_Z / np.tan(np.deg2rad(-phi[dn]))                 # (rows,)
    e = dist[:, None] * np.sin(np.deg2rad(theta))[None, :]       # east
    n = dist[:, None] * np.cos(np.deg2rad(theta))[None, :]       # north
    gf = np.asarray(ground_far, np.float32)
    gs = gf.shape[0] / (2.0 * far_half_m)
    px = np.clip((gf.shape[1] / 2.0 + e * gs).astype(int), 0, gf.shape[1] - 1)
    py = np.clip((gf.shape[0] / 2.0 - n * gs).astype(int), 0, gf.shape[0] - 1)
    samp = gf[py, px]
    beyond = (np.abs(e) > far_half_m) | (np.abs(n) > far_half_m)
    fog = np.clip(dist / (far_half_m * 1.2), 0, 1)[:, None, None]   # aerial perspective toward the haze
    samp = samp * (1 - fog) + haze * fog
    samp[beyond] = haze
    img[dn] = samp

    # buildings: per column a [base, roof] elevation band, far → near so near overwrites
    wall, roof, roof_own = (np.array(PAL[k], np.float32) for k in ('wall', 'roof', 'roof_own'))
    order = sorted(range(len(buildings)),
                   key=lambda i: -min(math.hypot(x, y) for x, y in buildings[i][0]))
    col_of = lambda th: int((th / 360.0) * W) % W
    row_of = lambda el: int((90.0 - el) / 180.0 * H)
    for i in order:
        pts, h, tags = buildings[i]
        n_pts = len(pts)
        base_el = np.full(W, np.nan); roof_el = np.full(W, np.nan); near_d = np.full(W, np.inf)
        for k in range(n_pts):
            x0, y0 = pts[k]; x1, y1 = pts[(k + 1) % n_pts]
            seg = math.hypot(x1 - x0, y1 - y0)
            steps = max(2, int(seg / 0.5) + 1)
            for s in np.linspace(0, 1, steps):
                x, y = x0 + (x1 - x0) * s, y0 + (y1 - y0) * s
                dd = math.hypot(x, y)
                if dd < 0.5:
                    continue
                c = col_of(level_to_compass(x, y))
                b = math.degrees(math.atan2(-UNIT_Z, dd))
                r = math.degrees(math.atan2(h - UNIT_Z, dd))
                base_el[c] = b if np.isnan(base_el[c]) else min(base_el[c], b)
                roof_el[c] = r if np.isnan(roof_el[c]) else max(roof_el[c], r)
                near_d[c] = min(near_d[c], dd)
        cols_hit = np.where(~np.isnan(roof_el))[0]
        if len(cols_hit) == 0:
            continue
        # fill gaps between hit columns when the footprint spans them (small polygons at distance)
        lo, hi = cols_hit.min(), cols_hit.max()
        span = np.arange(lo, hi + 1) if hi - lo < W / 2 else np.r_[np.arange(hi, W), np.arange(0, lo + 1)]
        # interpolate over the span so a 4-vertex box gives a solid band
        rf = np.interp(span, cols_hit, roof_el[cols_hit], period=W)
        bf = np.interp(span, cols_hit, base_el[cols_hit], period=W)
        df = np.interp(span, cols_hit, near_d[cols_hit], period=W)
        rc = roof_own if i == own_idx else roof
        for c, r_el, b_el, dd in zip(span, rf, bf, df):
            r0, r1 = row_of(r_el), row_of(b_el)
            if r1 <= r0:
                continue
            fog = 1 - math.exp(-dd / 1400.0)
            wcol = wall * (1 - fog) + haze * fog
            rcol = rc * (1 - fog) + haze * fog
            img[r0:r1, c % W] = wcol
            # a thin roof line at the top edge so near blocks read as blocks, not slabs
            img[r0:min(r0 + 2, r1), c % W] = rcol
    return img


# ── output ────────────────────────────────────────────────────────────────────
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16.0 - 0.5


def dither8(arr):
    """Ordered dither (±4 of 255) so 5-bit-per-channel quantisation doesn't band."""
    h, w = arr.shape[:2]
    tile = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w, None]
    return np.clip(np.round(arr + tile * 8.0), 0, 255).astype(np.uint8)


def save_tga(arr8, path):
    Image.fromarray(arr8, 'RGB').save(path)                  # PIL: 24-bit uncompressed for RGB
    with open(path, 'rb') as f:
        hdr = f.read(18)
    assert hdr[16] == 24, f"{path}: expected 24-bit TGA, got {hdr[16]}-bit"


def write_preview(preview_dir, ground_img, sky8, buildings, own_idx):
    os.makedirs(preview_dir, exist_ok=True)
    ground_img.save(os.path.join(preview_dir, 'ground-ortho.png'))
    Image.fromarray(sky8, 'RGB').save(os.path.join(preview_dir, 'sky-equirect.png'))
    # doll-house composite: ±40 m of the ground map with the unit footprints + corridor, 1440×900
    W, H = 1440, 900
    half = 40.0
    big = ground_img.resize((900, 900), Image.NEAREST)        # ±80 m → 900 px; crop the centre ±40 m
    big = big.crop((225, 225, 675, 675)).resize((900, 900), Image.NEAREST)
    canvas = Image.new('RGB', (W, H), (28, 30, 34))
    canvas.paste(big, (270, 0))
    d = ImageDraw.Draw(canvas, 'RGBA')
    s = 900 / (2 * half)
    P = lambda x, y: (270 + 450 - y * s, 450 - x * s)          # level (x north, y west) → px
    for (x0, y0, x1, y1, col) in [(-0.05, -15.4, 8.05, 0.05, (72, 120, 210, 140)),      # unit 639
                                  (-7.95, -15.4, 0.05, 0.05, (96, 176, 120, 140)),      # unit 640
                                  (-9.0, -17.4, 9.0, -15.4, (200, 200, 200, 150))]:     # corridor
        d.rectangle([P(x1, y1), P(x0, y0)], fill=col, outline=(255, 255, 255, 220))
    d.line([P(-half + 2, 0), P(half - 2, 0)], fill=(255, 255, 255, 60))
    d.line([P(0, -half + 2), P(0, half - 2)], fill=(255, 255, 255, 60))
    # labels (PIL default font — no external fonts, self-contained)
    d.text((280, 8), "N ↑   W ←   unit 639 (blue) / 640 (green) at z = 15.75 m over the OSM ground map, ±40 m", fill=(255, 255, 255))
    d.text((12, 20), "condo_ground.tga  512² ±80 m", fill=(230, 230, 230))
    d.text((12, 40), "doll-house camera: 69° down from the east", fill=(230, 230, 230))
    d.text((12, 60), f"{len(buildings)} OSM buildings, own footprint darker", fill=(230, 230, 230))
    d.text((1190, 20), "condo_sky.tga (west → +Y)", fill=(230, 230, 230))
    sky_small = Image.fromarray(sky8, 'RGB').resize((240, 120), Image.BILINEAR)
    canvas.paste(sky_small, (1190, 40))
    png_path = os.path.join(preview_dir, 'dollhouse-view.png')
    canvas.save(png_path)
    with open(png_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Condo site skybox — doll-house view</title>
<style>html,body{{margin:0;background:#1c1e22;color:#ddd;font:14px system-ui,sans-serif}}
main{{width:1440px;height:900px;position:relative}} img{{display:block;width:1440px;height:900px}}
p{{position:absolute;left:12px;bottom:8px;margin:0;background:rgba(0,0,0,.55);padding:6px 10px;border-radius:4px}}</style></head>
<body><main><img alt="Unit footprints over the OSM ground map, with the sky panorama" src="data:image/png;base64,{b64}">
<p>Generated by make_site_textures.py --preview. Data © OpenStreetMap contributors (ODbL).</p></main></body></html>
"""
    with open(os.path.join(preview_dir, 'dollhouse-view.html'), 'w') as f:
        f.write(html)
    print(f"[site] preview → {preview_dir}")


def render(preview_dir=None):
    buildings, roads, water_polys, water_lines, greens = load_osm()
    own_idx = own_building(buildings)
    print(f"[site] {len(buildings)} buildings, {len(roads)} roads, {len(water_polys)} water polys, "
          f"{len(water_lines)} water lines, {len(greens)} green; own building idx {own_idx}"
          + (f" ({buildings[own_idx][2].get('name', buildings[own_idx][2].get('name:en', 'unnamed'))}, "
             f"h={buildings[own_idx][1]:.0f} m)" if own_idx is not None else ''))
    ground = draw_ground(GROUND_PX, GROUND_HALF, buildings, roads, water_polys, water_lines, greens, own_idx)
    far_half = 1200.0
    ground_far = draw_ground(1200, far_half, buildings, roads, water_polys, water_lines, greens, own_idx)
    sky = draw_sky(buildings, ground_far, far_half, own_idx)
    ground8 = dither8(np.asarray(ground, np.float32))
    sky8 = dither8(sky)
    save_tga(ground8, GROUND_TGA)
    save_tga(sky8, SKY_TGA)
    print(f"[site] wrote {os.path.basename(GROUND_TGA)} {ground8.shape[1]}×{ground8.shape[0]}, "
          f"{os.path.basename(SKY_TGA)} {sky8.shape[1]}×{sky8.shape[0]} (24-bit RGB)")
    if preview_dir:
        write_preview(preview_dir, Image.fromarray(ground8, 'RGB'), sky8, buildings, own_idx)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('fetch', help='Overpass → site-osm.json')
    r = sub.add_parser('render', help='site-osm.json → condo_ground.tga + condo_sky.tga')
    r.add_argument('--preview', metavar='DIR', help='also write PNG previews + the plan mockup here')
    a = ap.parse_args()
    if a.cmd == 'fetch':
        fetch()
    else:
        if not os.path.exists(OSM_JSON):
            raise SystemExit(f"[site] {OSM_JSON} missing — run `make_site_textures.py fetch` once")
        render(a.preview)


if __name__ == '__main__':
    main()
