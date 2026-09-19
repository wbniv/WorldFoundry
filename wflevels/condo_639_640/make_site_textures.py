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
FAR_R    = 8000     # farther out only the towers: height ≥ 40 m or ≥ 15 levels (the Bangkok skyline —
                    # MahaNakhon, ICONSIAM/Magnolias, the Sathorn cluster — sits 3–7 km away)
WATER_R  = 3000
ROADS_R  = 400
GREEN_R  = 700
GEOM_R   = 150      # buildings this close become level geometry (site-buildings.json → a merged mesh
                    # in blender_create_condo.py) and are left out of the sky raster
FAR_GROUND_HALF = 3000.0   # the far ground raster behind the dome's lower half: reaches the Chao Phraya (≈1.6 km)
BUILDINGS_JSON = os.path.join(SCRIPT_DIR, 'site-buildings.json')
CATALOG_MD     = os.path.join(SCRIPT_DIR, 'site-catalog.md')
BRIDGE_R = 8000
# OSM carries no pylon heights; published figures (pylon top, deck) in metres for the
# cable-stayed bridges in view. Anything else cable-stayed gets the default.
BRIDGES = {'Rama IX Bridge': (87.0, 41.0), 'Bhumibol Bridge 1': (173.0, 50.0), 'Bhumibol Bridge 2': (164.0, 50.0),
           'Kanchanaphisek Bridge': (187.0, 50.0)}
BRIDGE_DEFAULT = (100.0, 40.0)          # a cable-stayed expressway span with no entry above (the 2024 Rama III–Dao Khanong twin)
# What each POV camera can sweep (compass bearings, pan start→end ± half the 60° FOV) — for the catalog.
VIEWS = {'balcony (639 patio, west)': (206, 330), 'master window (640, south)': (118, 242)}

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


# Untagged footprints (all of them near the pin) get a height by building type: Bang Phong
# Phang is shophouse country — 3–4 storeys.
TYPE_HEIGHT = {'house': 7.0, 'detached': 7.0, 'residential': 12.0, 'apartments': 24.0, 'commercial': 12.0,
               'retail': 8.0, 'industrial': 9.0, 'warehouse': 9.0, 'school': 12.0, 'hotel': 30.0,
               'office': 30.0, 'church': 12.0, 'temple': 14.0, 'garage': 4.0, 'shed': 3.5, 'roof': 4.0}


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
            return float(lv) * 3.2
        except ValueError:
            pass
    return TYPE_HEIGHT.get(str(tags.get('building', 'yes')).lower(), 11.0)


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
  way["building"]["height"~"^([4-9][0-9]|[1-9][0-9][0-9])"](around:{FAR_R},{LAT0},{LON0});
  way["building"]["building:levels"~"^(1[5-9]|[2-9][0-9])$"](around:{FAR_R},{LAT0},{LON0});
  relation["building"]["height"~"^([4-9][0-9]|[1-9][0-9][0-9])"](around:{FAR_R},{LAT0},{LON0});
  relation["building"]["building:levels"~"^(1[5-9]|[2-9][0-9])$"](around:{FAR_R},{LAT0},{LON0});
  way["highway"](around:{ROADS_R},{LAT0},{LON0});
  way["natural"="water"](around:{WATER_R},{LAT0},{LON0});
  relation["natural"="water"](around:{WATER_R},{LAT0},{LON0});
  way["waterway"](around:{WATER_R},{LAT0},{LON0});
  way["landuse"~"grass|recreation_ground|cemetery|forest|orchard|farmland|meadow"](around:{GREEN_R},{LAT0},{LON0});
  way["leisure"~"park|garden|pitch|playground"](around:{GREEN_R},{LAT0},{LON0});
  way["bridge"]["bridge:structure"="cable-stayed"](around:{BRIDGE_R},{LAT0},{LON0});
  way["man_made"="bridge"]["name"](around:{BRIDGE_R},{LAT0},{LON0});
  relation["man_made"="bridge"]["name"](around:{BRIDGE_R},{LAT0},{LON0});
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
                                     'water', 'waterway', 'landuse', 'leisure', 'name', 'name:en', 'type',
                                     'bridge', 'bridge:structure', 'layer', 'man_made')
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
    buildings, roads, water_polys, water_lines, greens, bridges = [], [], [], [], [], []
    for el in data['elements']:
        t = el['tags']
        if el['type'] == 'way':
            pts = [en_to_level(*to_en(la, lo)) for la, lo in el['geom']]
            closed = len(pts) > 3 and el['geom'][0] == el['geom'][-1]
            if 'building' in t and closed:
                buildings.append((pts[:-1], building_height(t), t))
            elif t.get('man_made') == 'bridge' or (t.get('bridge') and t.get('bridge:structure') == 'cable-stayed'):
                bridges.append((pts, t))
                if 'highway' in t:
                    roads.append((pts, t['highway']))
            elif 'highway' in t:
                roads.append((pts, t['highway']))
            elif (t.get('natural') == 'water' or t.get('waterway') in ('riverbank',)) and closed:
                water_polys.append(pts[:-1])
            elif 'waterway' in t:
                water_lines.append((pts, t['waterway']))
            elif ('landuse' in t or 'leisure' in t) and closed:
                greens.append(pts[:-1])
        else:   # relation (multipolygon water or building): stitch outer members into rings
            rings = stitch_rings([m['geom'] for m in el['members'] if m['role'] in ('outer', '')])
            for ring in rings:
                pts = [en_to_level(*to_en(la, lo)) for la, lo in ring]
                if 'building' in t:
                    buildings.append((pts[:-1] if ring[0] == ring[-1] else pts, building_height(t), t))
                elif t.get('man_made') == 'bridge':
                    bridges.append((pts, t))
                else:
                    water_polys.append(pts)
    return buildings, roads, water_polys, water_lines, greens, merge_bridges(bridges)


def merge_bridges(ways):
    """Named `man_made=bridge` outlines carry the names (Rama IX, Bhumibol 1/2 …) but no
    heights; the cable-stayed `bridge=yes` motorway ways carry the structure but split per
    carriageway. A named outline with a BRIDGES entry becomes a deck line along the outline's
    long axis; a cable-stayed way group not within 500 m of one of those becomes a default-
    height bridge named after its expressway; carriageway twins collapse to the longest."""
    named, stayed = [], {}
    for pts, t in ways:
        name = t.get('name:en') or t.get('name') or ''
        if t.get('man_made') == 'bridge':
            if name in BRIDGES:
                a, b = max(((p, q) for p in pts for q in pts), key=lambda pq: math.hypot(pq[0][0] - pq[1][0], pq[0][1] - pq[1][1]))
                named.append({'name': name, 'pts': [a, b], 'pylon_h': BRIDGES[name][0], 'deck_h': BRIDGES[name][1],
                              'length': math.hypot(a[0] - b[0], a[1] - b[1])})
        else:
            length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
            if name not in stayed or length > stayed[name][1]:
                stayed[name] = (pts, length)
    out = list(named)
    for name, (pts, length) in stayed.items():
        mid = pts[len(pts) // 2]
        if any(math.hypot(mid[0] - (n['pts'][0][0] + n['pts'][1][0]) / 2, mid[1] - (n['pts'][0][1] + n['pts'][1][1]) / 2) < 500 for n in named):
            continue
        out.append({'name': name, 'pts': pts, 'pylon_h': BRIDGE_DEFAULT[0], 'deck_h': BRIDGE_DEFAULT[1], 'length': length})
    return out


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
def draw_bridges(img, bridges):
    """Deck band + two pylons + stay cables per bridge, as silhouettes on the equirect array."""
    W, H = SKY_W, SKY_H
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), 'RGB')
    d = ImageDraw.Draw(pil)
    haze = np.array(PAL['haze'], np.float32)
    def col_row(x, y, z):
        dd = math.hypot(x, y)
        th = level_to_compass(x, y)
        el = math.degrees(math.atan2(z - UNIT_Z, dd))
        return th / 360.0 * W, (90.0 - el) / 180.0 * H, dd
    for b in bridges:
        pts = b['pts']
        d0 = min(math.hypot(x, y) for x, y in pts)
        fog = 1 - math.exp(-d0 / 1400.0)
        steel = tuple(int(v) for v in (np.array((96, 100, 108), np.float32) * (1 - fog) + haze * fog))
        # deck: polyline at deck height, 2 px thick; the road bed sits a little below the rail
        deck = [col_row(x, y, b['deck_h']) for x, y in pts]
        # split at the u seam
        segs, cur = [], [deck[0]]
        for a, c in zip(deck, deck[1:]):
            if abs(c[0] - a[0]) > W / 2:
                segs.append(cur); cur = [c]
            else:
                cur.append(c)
        segs.append(cur)
        for s in segs:
            if len(s) > 1:
                d.line([(u, v) for u, v, _ in s], fill=steel, width=3)
        # pylons at 35 % and 65 % of the deck length, cables fanning to the deck ends of the main span
        L = b['length']; cum = 0.0; marks = {}
        for a, c in zip(pts, pts[1:]):
            seg = math.hypot(c[0] - a[0], c[1] - a[1])
            for f in (0.35, 0.65):
                if cum <= f * L <= cum + seg and f not in marks:
                    k = (f * L - cum) / seg
                    marks[f] = (a[0] + (c[0] - a[0]) * k, a[1] + (c[1] - a[1]) * k)
            cum += seg
        tops = []
        for f, (x, y) in sorted(marks.items()):
            u0, v_deck, _ = col_row(x, y, b['deck_h'])
            u1, v_top, _ = col_row(x, y, b['pylon_h'])
            d.line([(u0, v_deck + 1), (u1, v_top)], fill=steel, width=2)
            tops.append((u1, v_top, u0, v_deck))
        if len(tops) == 2:
            (ua, va, _, vda), (ub, vb, _, vdb) = tops
            mid = ((ua + ub) / 2, (vda + vdb) / 2)
            for (u, v, ud, vd) in tops:
                for k in (0.33, 0.66, 1.0):
                    d.line([(u, v + (vd - v) * (1 - k) * 0.15), (u + (mid[0] - u) * k, mid[1])], fill=steel, width=1)
                    outer = (u - (mid[0] - u) * k, vd)
                    d.line([(u, v + (vd - v) * (1 - k) * 0.15), outer], fill=steel, width=1)
    return np.asarray(pil, np.float32)


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
    order = sorted((i for i in range(len(buildings)) if min(math.hypot(x, y) for x, y in buildings[i][0]) > GEOM_R),
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


def _bearing_dist(pts):
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    return level_to_compass(cx, cy), math.hypot(cx, cy), min(math.hypot(x, y) for x, y in pts)


def _seen_from(bearing):
    return ', '.join(name.split(' (')[0] for name, (a, b) in VIEWS.items() if a <= bearing <= b) or '—'


def write_catalog(buildings, bridges, water_polys):
    """site-catalog.md — what the skybox and the near geometry actually contain, from the data."""
    near = [(pts, h, tg) for pts, h, tg in buildings if min(math.hypot(x, y) for x, y in pts) <= GEOM_R]
    towers = []
    for pts, h, tg in buildings:
        br, dc, dmin = _bearing_dist(pts)
        if dmin > GEOM_R and h >= 100:
            towers.append((h, dc, br, tg.get('name:en') or tg.get('name') or '(unnamed)'))
    towers.sort(key=lambda r: -r[0])
    kinds = {}
    for pts, h, tg in near:
        k = str(tg.get('building', 'yes')); kinds[k] = kinds.get(k, 0) + 1
    L = []
    L.append("# Condo site catalog — what the skybox and the near geometry contain\n")
    L.append("Generated by `make_site_textures.py render` from `site-osm.json` (© OpenStreetMap contributors, ODbL); "
             "regenerate rather than edit. Bearings are compass degrees from the pin, distances from the pin; "
             f"\"seen from\" uses each POV camera's pan sweep ± half its 60° FOV ({'; '.join(f'{k}: {a}–{b}°' for k, (a, b) in VIEWS.items())}).\n")
    L.append(f"## Near buildings — level geometry (`site-buildings`, ≤ {GEOM_R:.0f} m)\n")
    L.append(f"{len(near)} footprints, heights {min(h for _, h, _ in near):.0f}–{max(h for _, h, _ in near):.0f} m "
             f"(untagged → by type: {', '.join(f'{k} {v}' for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]))}). "
             "No footprint in OSM carries a height here; `TYPE_HEIGHT` in the script assigns them.\n")
    L.append("| Name | Type | Height | Bearing | Distance |\n|---|---|---|---|---|")
    named = sorted(((tg.get('name:en') or tg.get('name')), str(tg.get('building')), h, *_bearing_dist(pts)[:2])
                   for pts, h, tg in near if tg.get('name') or tg.get('name:en'))
    for name, kind, h, br, dc in named:
        L.append(f"| {name} | {kind} | {h:.0f} m | {br:.0f}° | {dc:.0f} m |")
    if not named:
        L.append("| (none named) | | | | |")
    L.append(f"\n## Skyline towers ≥ 100 m (painted silhouettes, {GEOM_R:.0f} m – {FAR_R / 1000:.0f} km)\n")
    L.append(f"{len(towers)} towers; the {min(40, len(towers))} tallest:\n")
    L.append("| Tower | Height | Bearing | Distance | Seen from |\n|---|---|---|---|---|")
    for h, dc, br, name in towers[:40]:
        L.append(f"| {name} | {h:.0f} m | {br:.0f}° | {dc / 1000:.1f} km | {_seen_from(br)} |")
    L.append("\n## Bridges (deck + pylons + stay cables)\n")
    L.append("| Bridge | Pylons | Deck | Bearing | Distance | Seen from |\n|---|---|---|---|---|---|")
    for b in sorted(bridges, key=lambda b: min(math.hypot(x, y) for x, y in b['pts'])):
        br, dc, dmin = _bearing_dist(b['pts'])
        L.append(f"| {b['name']} | {b['pylon_h']:.0f} m | {b['deck_h']:.0f} m | {br:.0f}° | {dmin / 1000:.1f} km | {_seen_from(br)} |")
    L.append("\n## Water\n")
    big = sorted(water_polys, key=lambda p: -len(p))[:3]
    for poly in big:
        br, dc, dmin = _bearing_dist(poly)
        L.append(f"- polygon of {len(poly)} vertices, nearest {dmin / 1000:.1f} km at {level_to_compass(*min(poly, key=lambda q: math.hypot(*q))):.0f}° "
                 f"(the Chao Phraya's loop round Bang Krachao lies south-west to south)")
    with open(CATALOG_MD, 'w') as f:
        f.write('\n'.join(L) + '\n')
    print(f"[site] catalog → {os.path.basename(CATALOG_MD)}: {len(near)} near, {len(towers)} towers, {len(bridges)} bridges")


def _height_colour(h):
    stops = [(4, (230, 225, 210)), (12, (200, 180, 140)), (24, (190, 130, 90)), (60, (150, 70, 80)), (150, (90, 40, 120)), (320, (30, 20, 80))]
    for (h0, c0), (h1, c1) in zip(stops, stops[1:]):
        if h <= h1:
            k = max(0.0, (h - h0) / (h1 - h0))
            return tuple(int(a + (b - a) * k) for a, b in zip(c0, c1))
    return stops[-1][1]


def write_overview(preview_dir, buildings, bridges, water_polys, roads):
    """site-overview.png/.html — near buildings coloured by height (left) and the 8 km skyline
    map with towers, bridges, the river and both POV pan sectors (right)."""
    W, H = 1440, 900
    canvas = Image.new('RGB', (W, H), (28, 30, 34)); d = ImageDraw.Draw(canvas, 'RGBA')
    # left: ±160 m, 2 px/m, north up, west left
    s = 2.0; cx, cy = 320, 320                 # panel-local: ±160 m → 640 px, pasted at (20, 60)
    panel = Image.new('RGB', (640, 640), (52, 56, 62)); pd = ImageDraw.Draw(panel, 'RGBA')
    P = lambda x, y: (cx - y * s, cy - x * s)
    for pts, kind in roads:
        pd.line([P(x, y) for x, y in pts], fill=(90, 92, 98), width=6 if kind in ('primary', 'secondary', 'tertiary') else 3)
    for pts, h, tg in sorted(buildings, key=lambda b: b[1]):
        if min(math.hypot(x, y) for x, y in pts) <= GEOM_R:
            pd.polygon([P(x, y) for x, y in pts], fill=_height_colour(h), outline=(20, 20, 24))
    pd.ellipse([cx - GEOM_R * s, cy - GEOM_R * s, cx + GEOM_R * s, cy + GEOM_R * s], outline=(255, 255, 255, 120), width=2)
    pd.rectangle([P(8.05, 0.05), P(-7.95, -15.4)], outline=(80, 140, 255), width=3)   # the units
    pd.rectangle([P(9, 0.05), P(-9, -17.55)], outline=(80, 140, 255, 120), width=1)     # podium
    canvas.paste(panel, (20, 60))
    d.text((20, 20), f"Near geometry: {sum(1 for b in buildings if min(math.hypot(x, y) for x, y in b[0]) <= GEOM_R)} footprints within {GEOM_R:.0f} m, extruded to their heights (site-buildings). Blue = units + podium. North up, west left, 2 px/m.", fill=(230, 230, 230))
    lx = 20
    for h, label in ((4, '4'), (12, '12'), (24, '24'), (60, '60'), (150, '150'), (320, '320 m')):
        d.rectangle([lx, 740, lx + 40, 760], fill=_height_colour(h)); d.text((lx, 764), label, fill=(230, 230, 230)); lx += 48
    d.text((20, 790), "height legend (metres): shophouses 11–12, apartments 24; skyline towers on the right", fill=(200, 200, 200))
    # right: 8 km, 0.0575 px/m
    S = 460 / 8000.0; RX, RY = 1080, 380
    Q = lambda x, y: (RX - y * S, RY - x * S)
    d.rectangle([RX - 460, RY - 460, RX + 460, RY + 460], fill=(40, 44, 50))
    for poly in water_polys:
        d.polygon([Q(x, y) for x, y in poly], fill=(70, 110, 150))
    for pts, h, tg in sorted(buildings, key=lambda b: b[1]):
        if h >= 40 and min(math.hypot(x, y) for x, y in pts) > GEOM_R:
            br, dc, _ = _bearing_dist(pts); qx, qy = Q(*[(sum(p[i] for p in pts) / len(pts)) for i in (0, 1)])
            r = 2 + h / 40.0
            d.ellipse([qx - r, qy - r, qx + r, qy + r], fill=_height_colour(h))
    for b in bridges:
        d.line([Q(x, y) for x, y in b['pts']], fill=(255, 200, 80), width=4)
        br, dc, dmin = _bearing_dist(b['pts']); qx, qy = Q(b['pts'][len(b['pts']) // 2][0], b['pts'][len(b['pts']) // 2][1])
        d.text((qx + 6, qy - 6), b['name'], fill=(255, 200, 80))
    for name, (a, bb) in VIEWS.items():
        pts = [Q(0, 0)] + [Q(8000 * math.cos(math.radians(th)), -8000 * math.sin(math.radians(th))) for th in range(a, bb + 1, 4)]
        d.polygon(pts, fill=(255, 255, 255, 28), outline=(255, 255, 255, 90))
        mid = math.radians((a + bb) / 2); tx, ty = Q(6500 * math.cos(mid), -6500 * math.sin(mid))
        d.text((tx - 60, ty), name.split(' (')[0] + ' pan', fill=(255, 255, 255))
    for name, h in (('MahaNakhon 314 m', 0), ('ICONSIAM / Magnolias 318 m', 0)):
        pass
    tallest = sorted(((h, tg.get('name:en') or tg.get('name') or '', pts) for pts, h, tg in buildings if h >= 150 and min(math.hypot(x, y) for x, y in pts) > GEOM_R), key=lambda r: -r[0])[:6]
    for h, name, pts in tallest:
        qx, qy = Q(*[(sum(p[i] for p in pts) / len(pts)) for i in (0, 1)])
        d.text((qx + 8, qy + 4), f"{name or 'tower'} {h:.0f} m", fill=(235, 235, 235))
    d.text((620, 20), f"Skyline: {sum(1 for b in buildings if b[1] >= 40 and min(math.hypot(x, y) for x, y in b[0]) > GEOM_R)} towers ≥ 40 m within 8 km (dot size = height), bridges in yellow, the Chao Phraya in blue, POV pan sectors in white.", fill=(230, 230, 230))
    d.ellipse([RX - 4, RY - 4, RX + 4, RY + 4], fill=(80, 140, 255))
    png = os.path.join(preview_dir, 'site-overview.png'); canvas.save(png)
    b64 = base64.b64encode(open(png, 'rb').read()).decode()
    with open(os.path.join(preview_dir, 'site-overview.html'), 'w') as f:
        f.write(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Condo site overview — buildings and heights</title>
<style>html,body{{margin:0;background:#1c1e22}} main{{width:1440px;height:900px}} img{{display:block;width:1440px;height:900px}}</style></head>
<body><main><img alt="Near buildings by height and the 8 km skyline map" src="data:image/png;base64,{b64}"></main></body></html>
""")
    print(f"[site] overview → {png}")


def render(preview_dir=None):
    buildings, roads, water_polys, water_lines, greens, bridges = load_osm()
    own_idx = own_building(buildings)
    print(f"[site] bridges: " + ', '.join(f"{b['name']} ({min(math.hypot(x, y) for x, y in b['pts']):.0f} m, pylons {b['pylon_h']:.0f} m)" for b in bridges))
    print(f"[site] {len(buildings)} buildings, {len(roads)} roads, {len(water_polys)} water polys, "
          f"{len(water_lines)} water lines, {len(greens)} green; own building idx {own_idx}"
          + (f" ({buildings[own_idx][2].get('name', buildings[own_idx][2].get('name:en', 'unnamed'))}, "
             f"h={buildings[own_idx][1]:.0f} m)" if own_idx is not None else ''))
    ground = draw_ground(GROUND_PX, GROUND_HALF, buildings, roads, water_polys, water_lines, greens, own_idx)
    far_half = FAR_GROUND_HALF
    ground_far = draw_ground(1500, far_half, buildings, roads, water_polys, water_lines, greens, own_idx)   # 4 m/px
    sky = draw_sky(buildings, ground_far, far_half, own_idx)
    sky = draw_bridges(sky, bridges)
    write_catalog(buildings, bridges, water_polys)
    near = [{'pts': [[round(x, 2), round(y, 2)] for x, y in pts], 'h': round(h, 1),
             'kind': str(tags.get('building', 'yes')), 'name': tags.get('name:en', tags.get('name', ''))}
            for pts, h, tags in buildings if min(math.hypot(x, y) for x, y in pts) <= GEOM_R]
    with open(BUILDINGS_JSON, 'w') as f:
        json.dump({'_source': 'OpenStreetMap contributors, ODbL', 'geom_r': GEOM_R, 'buildings': near}, f, separators=(',', ':'))
    print(f"[site] {len(near)} buildings within {GEOM_R} m → {os.path.basename(BUILDINGS_JSON)} "
          f"(heights {min(b['h'] for b in near):.0f}–{max(b['h'] for b in near):.0f} m); "
          f"{sum(1 for b in buildings if min(math.hypot(x, y) for x, y in b[0]) > GEOM_R and b[1] >= 40)} towers ≥ 40 m in the sky")
    ground8 = dither8(np.asarray(ground, np.float32))
    sky8 = dither8(sky)
    save_tga(ground8, GROUND_TGA)
    save_tga(sky8, SKY_TGA)
    print(f"[site] wrote {os.path.basename(GROUND_TGA)} {ground8.shape[1]}×{ground8.shape[0]}, "
          f"{os.path.basename(SKY_TGA)} {sky8.shape[1]}×{sky8.shape[0]} (24-bit RGB)")
    if preview_dir:
        write_preview(preview_dir, Image.fromarray(ground8, 'RGB'), sky8, buildings, own_idx)
        write_overview(preview_dir, buildings, bridges, water_polys, roads)


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
