"""Drawings and HTML for the Gulf of Thailand reef poster. make_poster.py supplies the claims."""
from __future__ import annotations

import math
import random
import json
from pathlib import Path

import reef_art as A
from layout import (ACC, CARD_BG, CW, GRID, INK, MUTED, NAVY, STATUS_TEXT, LEGEND_TEXT, PRINTABLE, WHITE,
                    T, esc, svg_open)

SEED = 20261102
BANGKOK = json.loads((Path(__file__).resolve().parent / 'bangkok-adm1.geojson').read_text(encoding='utf-8'))['geometry']['coordinates'][0]


# ── Header: a strip of the tank ─────────────────────────────────────────────
def tank_strip(w=400, h=100):
    """A wide strip of the reef, no text: rock, boulder coral with worms, table coral, the fishes."""
    rng = random.Random(SEED)
    vw, vh = 800, 200
    g = [svg_open(w, h, 'A strip of the reef tank: boulder coral, table coral, humbugs and the boxfish',
                  view=f'0 0 {vw} {vh}')]
    g.append('<defs><linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a8fb8"/>'
             '<stop offset="1" stop-color="#0c4a6e"/></linearGradient></defs>')
    g.append(f'<rect width="{vw}" height="{vh}" fill="url(#water)"/>')
    for k in range(5):
        x = 60 + k * 170
        g.append(f'<path d="M{x},0 L{x + 40},0 L{x + 140},{vh} L{x + 70},{vh}Z" fill="#ffffff" opacity=".06"/>')
    g.append(f'<rect y="{vh - 22}" width="{vw}" height="22" fill="#d9c393"/>')
    g.append(f'<path d="{A.blob(rng, 120, 170, 140, 60)}" fill="#7a5a63"/>')
    g.append(f'<path d="{A.blob(rng, 690, 168, 150, 58)}" fill="#6f5560"/>')
    g.append(A.zoanthids(rng, 90, 140, 40, n=14))
    g.append(A.porites(rng, 160, 150, 70, 46))
    g.append(A.table_acropora(rng, 640, 92, 160))
    g.append(A.branching_coral(rng, 395, 182, 120, '#f0a6b8', '#ffe3ea'))
    g.append(A.giant_clam(rng, 520, 168, 60))
    g.append(A.gorgonian(rng, 760, 180, 140, '#c2410c'))
    g.append(A.humbug(rng, 380, 70, 0.9, 1))
    g.append(A.humbug(rng, 425, 58, 0.8, -1))
    g.append(A.boxfish(rng, 250, 62, 0.95, 1))
    g.append('</svg>')
    return ''.join(g)


# ── Panel 1: the habitat map ────────────────────────────────────────────────
COAST = [(102.2, 5.8), (102.2, 6.1), (101.3, 6.9), (100.6, 7.2), (100.3, 7.6), (100.1, 8.3), (99.9, 8.7),
         (99.5, 9.2), (99.2, 9.8), (99.2, 10.4), (99.5, 11.0), (99.7, 11.6), (99.95, 12.4), (100.0, 13.2),
         (100.5, 13.5), (100.9, 13.4), (100.95, 13.0), (100.9, 12.65), (101.3, 12.65), (101.8, 12.5),
         (102.3, 12.2), (102.6, 11.9), (102.9, 11.6), (103.1, 11.1), (103.5, 10.6), (104.0, 10.5),
         (104.5, 10.4), (104.8, 10.1), (104.9, 9.6), (104.8, 8.6), (105.2, 8.55), (105.9, 8.75),
         (106.5, 9.05), (107.2, 9.45), (107.2, 14.2), (98.5, 14.2),
         (98.5, 5.8)]
ISLANDS = ((99.95, 9.5, 5), (100.03, 9.75, 4), (99.84, 10.1, 2.5), (99.67, 9.68, 2), (102.35, 12.05, 4.5),
           (102.55, 11.65, 3), (103.95, 10.2, 6), (100.78, 12.92, 2), (100.85, 12.62, 1.6))


def habitat_map(sites, w=210, h=205):
    """Schematic map of the Gulf with the reef sites named in the research document. sites: (label, lon, lat, side)."""
    # Locally equirectangular at Bangkok latitude, then uniformly fit the map.
    # Preserve the surveyed boundary shape while retaining its map position.
    lon_factor = 0.9713  # cos(13.75 degrees)
    scale = min(w / (8.7 * lon_factor), h / 8.4)
    x_pad = (w - 8.7 * lon_factor * scale) / 2
    y_pad = (h - 8.4 * scale) / 2
    def P(lon, lat):
        return x_pad + (lon - 98.5) * lon_factor * scale, y_pad + (14.2 - lat) * scale
    sea = '#cde9f5'
    g = [svg_open(w, h, 'Schematic map of the Gulf of Thailand with the reef sites in the research document')]
    g.append(f'<rect width="{w}" height="{h}" fill="{sea}"/>')
    pts = [P(lo, la) for lo, la in COAST]
    g.append('<path d="M' + ' L'.join(f'{a:.1f},{b:.1f}' for a, b in pts) + 'Z" fill="#efe6d2" stroke="#8a7e66" stroke-width="1"/>')
    for lo, la, r in ISLANDS:
        x, y = P(lo, la)
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#efe6d2" stroke="#8a7e66" stroke-width=".8"/>')
    for label, lo, la, side in sites:
        x, y = P(lo, la)
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#b4235a" stroke="#fff" stroke-width="1"/>')
        dx = 7 if side == 'r' else -7
        g.append(T(x + dx, y + 4, label, 11, 'start' if side == 'r' else 'end', INK, 700, bg=sea))
    # WGS84 provincial boundary, highlighted as a city area, not a reef site.
    boundary = [P(lon, lat) for lon, lat in BANGKOK]
    g.append('<path d="M' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in boundary) +
             'Z" fill="#ad4a2e" fill-opacity=".55" stroke="#7a2518" stroke-width="1"/>')
    bx, by = P(100.50144, 13.75398)
    edge = max(x for x, _ in boundary)
    g.append(T(edge + 5, by + 4, 'Bangkok', 11, 'start', '#6f271b', 700, bg='#efe6d2'))
    x, y = P(102.0, 8.2)
    g.append(T(x, y, 'Gulf of Thailand', 13, 'middle', '#0b4f78', 700, bg=sea, italic=True))
    g.append(T(x, y + 17, 'อ่าวไทย', 13, 'middle', '#0b4f78', 400, bg=sea))
    for name, lo, la in (('THAILAND', 102.0, 13.1), ('CAMBODIA', 104.3, 12.2), ('MALAYSIA', 100.0, 6.8),
                         ('VIETNAM', 105.8, 10.0)):
        x, y = P(lo, la)
        g.append(T(x, y, name, 11, 'middle', '#5f5444', 400, bg='#efe6d2'))
    g.append(T(6, h - 7, 'Schematic, not to scale', 11, 'start', MUTED, bg=sea))
    g.append('</svg>')
    return ''.join(g)


# ── Panel 2: card drawings (no text, scaled to fit) ─────────────────────────
DRAW = {
    'xmas': (lambda r: A.christmas_tree_worm(r, 0, 12, 3.2), '-40 -40 80 62'),
    'duster': (lambda r: A.feather_duster(r, 0, 40, -90, True, 0.8), '-40 -38 80 82'),
    'clam': (lambda r: A.giant_clam(r, 0, 6, 110), '-60 -24 120 64'),
    'crinoid': (lambda r: A.crinoid(r, 0, 26, 52), '-64 -36 128 84'),
    'shrimp': (lambda r: A.cleaner_shrimp(r, -24, 10, 1.15), '-60 -40 120 64'),
    'nudi': (lambda r: A.phyllidia(r, 0, 4, 1.5), '-56 -26 112 60'),
    'star': (lambda r: A.linckia(r, 0, 2, 0.6), '-40 -36 80 76'),
    'hermit': (lambda r: A.hermit_crab(r, 0, 12, 1.4), '-40 -30 86 58'),
    'porites': (lambda r: A.porites(r, 0, 26, 52, 34), '-58 -26 116 60'),
    'table': (lambda r: A.table_acropora(r, 0, -4, 120), '-64 -30 128 108'),
    'pocillopora': (lambda r: A.branching_coral(r, 0, 56, 120, '#f0a6b8', '#ffe3ea'), '-70 -50 140 110'),
    'gonio': (lambda r: A.goniopora(r, 0, 16, 34), '-56 -40 112 80'),
    'sarco': (lambda r: A.sarcophyton(r, 0, 30, 0.62), '-50 -22 100 56'),
    'tuba': (lambda r: A.tubastraea(r, -66, 18, 6, down=False), '-80 -18 132 44'),
    'turbi': (lambda r: A.turbinaria(r, 0, 10, 0.9), '-66 -24 132 56'),
    'sponge': (lambda r: A.barrel_sponge(r, 0, 38, 70, 50), '-40 -40 80 82'),
    'squirt': (lambda r: A.sea_squirt(r, 0, 30, 1.4), '-36 -36 72 70'),
    'fungia': (lambda r: A.fungia(r, 0, 10, 1.6), '-54 -14 108 46'),
    'fan': (lambda r: A.gorgonian(r, 0, 60, 120, '#c2410c'), '-70 -64 140 128'),
    'zoanth': (lambda r: A.zoanthids(r, 0, 0, 34, n=26), '-46 -26 92 52'),
    'crab': (lambda r: A.guard_crab(r, 0, 10, 2.0), '-48 -30 96 60'),
}


def card_drawing(key, w=72, h=50):
    rng = random.Random(f'{SEED}-{key}')
    fn, view = DRAW[key]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{view}" '
            f'preserveAspectRatio="xMidYMid meet" role="img"><title>{esc(key)}</title>{fn(rng)}</svg>')


def cards_sheet(cards, cols=4, cw=180, ch=120):
    """Every card's drawing on one editable sheet, labelled (the 03 SVG panel)."""
    rows = -(-len(cards) // cols)
    g = [svg_open(cols * cw, rows * ch, 'The invertebrate drawings')]
    for i, c in enumerate(cards):
        x, y = (i % cols) * cw, (i // cols) * ch
        rng = random.Random(f'{SEED}-{c["draw"]}')
        fn, view = DRAW[c['draw']]
        vx, vy, vw, vh = map(float, view.split())
        s = min((cw - 20) / vw, (ch - 34) / vh)
        g.append(f'<rect x="{x + 4}" y="{y + 4}" width="{cw - 8}" height="{ch - 8}" rx="5" fill="{CARD_BG}"/>')
        g.append(f'<g transform="translate({x + cw / 2 - (vx + vw / 2) * s:.1f} {y + 10 - vy * s:.1f}) scale({s:.3f})">{fn(rng)}</g>')
        g.append(T(x + cw / 2, y + ch - 12, c['name'], 11, 'middle', NAVY, 700, bg=CARD_BG))
    g.append('</svg>')
    return ''.join(g)


# ── Panel 3: the fishes ─────────────────────────────────────────────────────
def humbug_drawing(w=170, h=150):
    """Two humbugs over their branching coral head; one dives into it."""
    rng = random.Random(f'{SEED}-humbug')
    g = [svg_open(w, h, 'Two humbug damselfish over one branching coral head; one dives into the branches')]
    g.append(A.branching_coral(rng, 85, h - 12, 140, '#e79aac', '#fde2e8'))
    g.append(A.humbug(rng, 52, 34, 0.95, 1))
    g.append(A.humbug(rng, 112, 70, 0.75, -1))
    g.append(f'<path d="M122 82 q8 18 -4 34" fill="none" stroke="{ACC}" stroke-width="2" stroke-dasharray="4 3"/>')
    g.append(f'<path d="M113 115 l5 5 l5 -6" fill="none" stroke="{ACC}" stroke-width="2"/>')
    g.append(T(6, 14, 'dives into the head', 11, 'start', ACC, 700, bg='#fffaf0'))
    g.append('</svg>')
    return ''.join(g)


def boxfish_drawing(w=230, h=150):
    """The rigid box and the fins that row it: thrust from the dorsal, anal and pectoral fins."""
    rng = random.Random(f'{SEED}-boxfish')
    bg = '#fffaf0'
    g = [svg_open(w, h, 'Juvenile yellow boxfish: a rigid box rowed by its fins; the tail mostly steers')]
    g.append(f'<g transform="translate(110 76) scale(1.6)">{A.boxfish(rng, 0, 0, 1.0, 1)}</g>')
    # fins as arrows: dorsal (top), anal (bottom), pectoral (side), caudal (tail)
    for x1, y1, x2, y2 in ((96, 40, 76, 30), (96, 112, 76, 122), (126, 92, 108, 104)):
        g.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ACC}" stroke-width="2"/>')
        a = math.atan2(y2 - y1, x2 - x1)
        p1 = (x2 - 6 * math.cos(a - .45), y2 - 6 * math.sin(a - .45))
        p2 = (x2 - 6 * math.cos(a + .45), y2 - 6 * math.sin(a + .45))
        g.append(f'<path d="M{x2} {y2} L{p1[0]:.1f} {p1[1]:.1f} L{p2[0]:.1f} {p2[1]:.1f}Z" fill="{ACC}"/>')
    g.append(T(8, 16, 'fins row', 11, 'start', ACC, 700, bg=bg))
    g.append(T(8, 144, 'box stays rigid', 11, 'start', INK, 700, bg=bg))
    g.append(T(226, 16, 'tail steers', 11, 'end', MUTED, 700, bg=bg))
    g.append('</svg>')
    return ''.join(g)


# ── HTML pieces ─────────────────────────────────────────────────────────────
def chip_html(c):
    kind = c['status']
    key = {'verified': 'V', 'other-region': 'R', 'ours': 'T', 'unverified': '?'}[kind]
    return f'<span class="chip {kind}" title="{esc(STATUS_TEXT[kind])}">{key}</span>'


def refs_html(c, num):
    if not c['src']:
        return ''
    return ' <span class="ref">[' + ', '.join(str(num[s]) for s in c['src']) + ']</span>'


ROLE_LABEL = {'gulf': 'Gulf', 'eats': 'Eats', 'defends': 'Defence', 'tank': 'In the tank'}


def claim_html(c, num, area):
    lead = f'<b>{c.get("label", ROLE_LABEL[c["role"]])}:</b> ' if c.get('role') in ROLE_LABEL else ''
    content = c['text']
    if c.get('role') == 'gulf' and content == 'Recorded in the Gulf of Thailand.':
        content = 'Recorded in the Gulf.'
    elif c.get('role') == 'tank' and content.startswith('In the planned tank, '):
        content = content[len('In the planned tank, '):]
        content = content[:1].upper() + content[1:]
    return (f'<p class="cl" data-status="{c["status"]}" data-area="{area}">{chip_html(c)} {lead}{content}'
            f'{refs_html(c, num)}</p>')


def legend_html(used):
    keys = {'verified': 'V', 'other-region': 'R', 'ours': 'T'}
    items = ''.join(f'<span class="lg"><span class="chip {s}">{keys[s]}</span> {LEGEND_TEXT[s]}</span>'
                    for s in PRINTABLE if s in used)
    return f'<div class="legend">{items}</div>'


def sources_html(order, sources, num, ncols=4):
    links = []
    for s in order:
        d = sources[s]
        label = esc(f'{d["cite"]} · {d["where"]} · {d["about"]}')
        links.append(f'<a href="{d["url"]}" title="{label}" aria-label="Source {num[s]}: {label}">[{num[s]}]</a>')
    return '<div class="srcs"><b>Sources:</b> ' + ' '.join(links) + '</div>'
