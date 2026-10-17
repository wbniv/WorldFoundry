#!/usr/bin/env python3
"""Longsnout seahorse biomechanics poster (portrait A3): writes poster.html and the editable SVG panels.

Every printed claim lives in PANELS / HEADER_CLAIMS below, with its status chip and its sources.
The sources, locators and access limits are documented in ../seahorse-research.md, written first;
this script may print only what that document marks verified, other species or ours.

    python3 docs/reference/seahorse-biomechanics-poster/make_poster.py      # poster.html + *.svg
    python3 docs/reference/seahorse-biomechanics-poster/export_poster.py    # PDF, 300 DPI PNG, layout review
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKED = '2026-10-16'

# ── Page and type ────────────────────────────────────────────────────────────
PAGE_W_MM, PAGE_H_MM, MARGIN_MM = 297, 420, 10
CW = 1047                       # content width in CSS px (277 mm at 96 dpi)
HALF = 517                      # one panel; two of them and a 13 px gap fill CW
SVG_H = 150                     # drawing height in every panel
MIN_PX = 11.0                   # 8.25 pt: nothing on the poster is set smaller
PX_TO_PT = 0.75

INK, MUTED, GRID, WHITE = '#1d2733', '#55636f', '#d9e0e6', '#ffffff'
NAVY, NAVY_TEXT, ACC = '#123047', '#c9dceb', '#0f6f86'
BODY, BODY_EDGE, RING, SPOT = '#e0aa45', '#6b4716', '#9a6b22', '#7a4a17'
WARN, CORAL = '#b4531a', '#c2410c'
CHIP = {   # kind: (text, fill, edge)
    'verified': ('#0f5f30', '#e3f4ea', '#1f8a4c'),
    'other-species': ('#6a2a94', '#f1e6fb', '#8a44c0'),
    'ours': ('#1b46b3', '#e4ecff', '#2b5fd9'),
    'unverified': ('#7a4500', '#fff2d9', '#b26a00'),
}
STATUS_TEXT = {'verified': 'verified', 'other-species': 'other species', 'ours': 'ours', 'unverified': 'unverified'}
LEGEND_TEXT = {
    'verified': 'source read; it says this of <i>H. reidi</i>',
    'other-species': 'source read; it is about the species named',
    'ours': 'game choices or measurements; estimates say <b>estimate (ours)</b>',
}
PRINTABLE = ('verified', 'other-species', 'ours')
FONT_SANS = '"Noto Sans","DejaVu Sans",sans-serif'
FONT_SERIF = '"Noto Serif","DejaVu Serif",serif'
_FONT_FILE = '/usr/share/fonts/truetype/noto/NotoSans-{}.ttf'
_FONT_CACHE = {}

TEXT_PAIRS = set()              # (foreground, background) of every SVG text: the contrast test reads it
TEXT_SIZES = []                 # every SVG font size (px)

# ── The game's own numbers (the plan's tail section; all ours) ───────────────
N_RINGS = 35
N_TRUNK = 11
RING_LEN = [3.75 * 0.9764 ** i for i in range(N_RINGS)]                        # mm, 3.75 → 1.67
RING_WID = [9.0 + (1.4 - 9.0) * (i / N_RINGS) ** 0.85 for i in range(N_RINGS + 1)]  # mm, 9.0 → 1.4
LIMITS = {'ventral': (12, 40), 'lateral': (8, 28), 'dorsal': (4, 12.5), 'twist': (3, 8)}  # degrees, ring 0 → 34
KNOTS = (0, 6, 12, 18, 24, 30, 34)
WRAP_VALUES = ('mode', 'start ring', 'holdfast radius', 'progress')
BLOCK_CELLS = 40
MEASURED_DATE = '2026-10-17'
MEASUREMENTS = json.loads((HERE.parents[1] / 'diagnostics/seahorse-close-cast1-20261017/comparison.json').read_text())
FRAME_MS = {view: {r['pairs']: r['median_frame_ms'] for r in rows}
            for view, rows in MEASUREMENTS['views'].items()}
FRAME_FPS = {view: {n: 1000 / ms for n, ms in rows.items()} for view, rows in FRAME_MS.items()}
INTERPOLATED_FPS = {view: {n: 1000 / (rows[2] + (n-2) * (rows[6]-rows[2])/4)
                         for n in (3, 4, 5)} for view, rows in FRAME_MS.items()}
_CPU_ROWS = MEASUREMENTS['views']['close-idle']
CPU_DELTA = {key: _CPU_ROWS[-1]['cpu']['frame_weighted_cpu_ms'][key]
                 - _CPU_ROWS[0]['cpu']['frame_weighted_cpu_ms'][key]
             for key in ('total', 'update', 'render', 'animation')}
TANK_GAL = 40
H_KUDA_TOTALS = {'ventral': 850, 'dorsal': 290, 'lateral': 570}                # Porter et al. 2015, Fig. 2A


def limit(kind, i):
    lo, hi = LIMITS[kind]
    return lo + (hi - lo) * i / (N_RINGS - 1)


def limit_total(kind):
    return sum(limit(kind, i) for i in range(N_RINGS))


# ── Sources (see ../seahorse-research.md for DOIs, locators and access) ──────
SOURCES = {
    'lourie': dict(cite='Lourie, Foster, Cooper & Vincent 2004. A Guide to the Identification of Seahorses',
                   where='pp. 2, 72–73', species='H. reidi',
                   url='https://www.traffic.org/site/assets/files/9411/a-guide-to-the-identification-of-seahorses.pdf'),
    'silveira': dict(cite='Silveira et al. 2014. Zootaxa 3861: 317–332', where='pp. 322–323', species='H. reidi',
                     url='https://doi.org/10.11646/zootaxa.3861.4.2'),
    'maia': dict(cite='Maia, Couto & Adriaens 2013. How seahorses hang on to their life. SICB abstract',
                 where='abstract', species='H. reidi, H. abdominalis',
                 url='https://sicb.org/abstracts/how-seahorses-hang-on-to-their-life'),
    'porter': dict(cite='Porter et al. 2015. Why the seahorse tail is square. Science 349: aaa6683',
                   where='Figs. 1, 2, 5', species='H. reidi, H. kuda; printed models',
                   url='https://doi.org/10.1126/science.aaa6683'),
    'zima': dict(cite='Zima-Kulisiewicz et al. 2009. Undulatory fin motion of seahorse. GALA proceedings 56',
                 where='pp. 56-4–56-5', species='H. reidi',
                 url='https://www.gala-ev.org/images/Beitraege/Beitraege%202009/PDF/56.pdf'),
    'botello': dict(cite='Botello-Payro et al. 2010. Flow induced by seahorse fins. GALA proceedings 28',
                    where='results', species='H. reidi',
                    url='https://www.gala-ev.org/images/Beitraege/Beitraege%202010/pdf/28.pdf'),
    'ashley': dict(cite='Ashley-Ross 2002. J. Exp. Zool. 293: 561–577', where='p. 566', species='H. hudsonius (= H. erectus), H. zosterae',
                   url='https://users.wfu.edu/rossma/DorsalFin.pdf'),
    'lixu': dict(cite='Li & Xu 2016. Swimming ability of the yellow seahorse. Marine Sciences 40(5): 76–81',
                 where='abstract', species='H. kuda',
                 url='https://opaj.napstic.cn/periodicalArticle/0120160900195857'),
    'roos': dict(cite='Roos et al. 2009. Suction feeding in H. reidi. J. Exp. Biol. 212: 3490–3498',
                 where='p. 3493, Table 1', species='H. reidi',
                 url='https://medialibrary.uantwerpen.be/oldcontent/container20052/files/Roos_et_al_2009_J_Exp_Biol.pdf'),
    'vw': dict(cite='Van Wassenbergh et al. 2009. Suction is kid’s play. Biol. Lett. 5: 200–203',
               where='p. 201, Fig. 2', species='H. reidi newborns',
               url='https://medialibrary.uantwerpen.be/oldcontent/container20052/files/Van_Wassenbergh_et_al_2009_Biology_Letters.pdf'),
    'mosk': dict(cite='Mosk et al. 2007. Visual Neuroscience 24: 345–354', where='abstract', species='Syngnathidae',
                 url='https://doi.org/10.1017/S0952523807070320'),
    'hett': dict(cite='Hettiarachchi & Edirisinghe 2017. Trop. Agric. Res. 29: 77–89', where='abstract', species='H. reidi',
                 url='https://doi.org/10.4038/tar.v29i1.8299'),
    'oceanrider': dict(cite='Ocean Rider (breeder). Stocking Density forum thread, 2006', where='reply #2823',
                       species='H. erectus', url='https://seahorse.com/topic/stocking-density/'),
}

# Each claim: (status, text, sources). `chip` overrides the printed chip label (same colours as the status).
HEADER_CLAIMS = [
    dict(status='verified', src=['hett', 'lourie'],
         text='Captive broodstock averages 15.6–16.6 cm tall.<br>Largest recorded adult: 17.5 cm.'),
    dict(status='verified', src=['lourie', 'silveira'],
         text='Colour: brown spots with tiny white dots, ring stripes, or uniform.'),
    dict(status='verified', src=['lourie'],
         text='Western Atlantic; on seagrass, mangrove roots, macroalgae and gorgonians.'),
]

PANELS = [
    dict(key='rings', title='Thirty-five rings', claims=[
        dict(status='verified', src=['lourie'],
             text='11 trunk rings, and most often 35 tail rings (range 31–39).'),
        dict(status='verified', src=['silveira', 'maia'],
             text='Other counts: 30–39 tail rings in 104 Brazilian specimens; 33–37 in another study.'),
        dict(status='verified', src=['porter'],
             text='Each tail ring is four L-shaped bony plates around one vertebra.'),
        dict(status='ours', src=[], game=True,
             text='Our tail: 35 rings, 90 mm. Rings shrink from 3.75 to 1.67 mm long and 9.0 to 1.4 mm wide.'),
    ]),
    dict(key='square', title='Square bends without crushing', claims=[
        dict(status='verified', src=['porter'],
             text='Joints: ball-and-socket between vertebrae, peg-and-socket between plates, gliding where plates overlap.'),
        dict(status='verified', src=['porter'],
             text='In 3D-printed models, the square tail resists crushing better than a round one, and it twists about 15° per segment (round: about 30°).'),
        dict(status='ours', src=[], game=True,
             text='Our twist limit rises from 3° at the base to 8° at the tip.'),
    ]),
    dict(key='grip', title='Grip, hold, release', claims=[
        dict(status='verified', src=['maia'],
             text='<i>H. reidi</i>: whole-tail grip on a 1 cm perch; more motion toward the tip, with sideways bend as it curls.'),
        dict(status='other-species', src=['maia'],
             text='<i>H. abdominalis</i> chose vertical, round, smooth holdfasts.'),
        dict(status='ours', src=[], game=True,
             text='Our wrap closes from the tip, tracks the post during sway, and unwinds before swimming.'),
    ]),
    dict(key='fin', title='A fin too fast to draw', claims=[
        dict(status='verified', src=['zima', 'botello'],
             text='<i>H. reidi</i> fins: 20–60 Hz, slowest when hovering; most often about 50 Hz.'),
        dict(status='other-species', src=['ashley'],
             text='<i>H. erectus</i> (as <i>H. hudsonius</i>) dorsal fin: 30–42 Hz; dwarf seahorse: 42–54 Hz.'),
        dict(status='other-species', src=['lixu'],
             text='<i>H. kuda</i> holds at most 3–4 cm/s against a current.'),
        dict(status='ours', src=[], game=True,
             text='A 60 Hz screen shows at most 30 Hz, so we draw a slowed, blurred wave. Swim speed is ours.'),
    ]),
    dict(key='strike', title='A six-millisecond strike', claims=[
        dict(status='verified', src=['roos'],
             text='Adult <i>H. reidi</i> pivot feeding: the head starts to rise 0.4 ms after the hyoid moves; the prey crosses the mouth at 5.7 ± 0.8 ms.'),
        dict(status='verified', src=['vw'],
             text='Newborns turn the head more than 40° in under 2.5 ms.'),
        dict(status='ours', src=[], game=True,
             text='The strike ends inside one 16.7 ms frame at 60 Hz, so the game cuts from aim to strike.'),
    ]),
    dict(key='pairs', title='Six pairs share six holdfasts', claims=[
        dict(status='verified', src=['lourie'],
             text='<i>H. reidi</i> is found in pairs in the wild.'),
        dict(status='other-species', src=['mosk'],
             text='Seahorses and pipefishes move each eye on its own to find, track and strike single prey.'),
        dict(status='ours', src=[], game=True,
             text='12 residents, 6 posts. Greetings rotate through visible pairs and check other residents’ spot reservations. Partners share a post at different coil heights; this and independent eye targets are ours.'),
    ]),
    dict(key='joints', title='The model we built', claims=[
        dict(status='ours', src=[], game=True,
             text='Per seahorse: body/tail 1,027 triangles + fins 74. Residents share meshes and atlas; males have a brood pouch. Yellow/orange sex colours are authored.'),
        dict(status='ours', src=[], game=True,
             text='7 three-angle knots + 4 wrap values drive 35 joints; clips blend and joint limits apply. The deformer block has 40 cells; behavior uses more.'),
        dict(status='ours', src=[], game=True,
             chip='reference check (ours)',
             text='7 exported-rig poses: no frame flips, ≤ 95.91% joint-limit use, ≤ 0.258 mm wrap-centre error. Python reference, not a device measurement.'),
    ]),
    dict(key='cost', title='Six pairs: measured on cast1', claims=[
        dict(status='ours', chip='measured (ours)', src=[], game=True,
             text=f"Close idle: None → 6 pairs, {FRAME_FPS['close-idle'][0]:.2f} → {FRAME_FPS['close-idle'][6]:.2f} FPS. Crawl: {FRAME_FPS['close-crawl'][0]:.2f} → {FRAME_FPS['close-crawl'][6]:.2f} FPS. 3 × 60 s/count/view, {MEASURED_DATE}."),
        dict(status='ours', chip='estimate (ours)', src=[], game=True,
             text='3–5 pairs: frame-time interpolation between measured 2 and 6.'),
        dict(status='other-species', src=['oceanrider'],
             text='<i>H. erectus</i> breeder guideline: one adult pair per 10 gal.'),
        dict(status='ours', src=[], game=True,
             text='Our 40 gal game defaults to 6 pairs. None retains 12 residents and hides 6 posts.'),
    ]),
]


def source_order():
    """Sources numbered in order of first use on the poster."""
    order = []
    for c in HEADER_CLAIMS + [c for p in PANELS for c in p['claims']]:
        for s in c['src']:
            if s not in order:
                order.append(s)
    return order


def all_claims():
    return [('header', c) for c in HEADER_CLAIMS] + [(p['key'], c) for p in PANELS for c in p['claims']]


def used_statuses():
    return [s for s in PRINTABLE if any(c['status'] == s for _k, c in all_claims())]


# ── Small helpers ────────────────────────────────────────────────────────────
def contrast(fg, bg):
    """WCAG 2.x contrast ratio between two #rrggbb colours."""
    def lum(c):
        ch = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        ch = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


HTML_TEXT_PAIRS = {(INK, WHITE), (MUTED, WHITE), (WHITE, ACC), (WHITE, NAVY), (NAVY_TEXT, NAVY),
                   (ACC, WHITE)} | {(v[0], v[1]) for v in CHIP.values()}


def text_width(s, size, bold=False):
    try:
        from PIL import ImageFont
        if bold not in _FONT_CACHE:
            _FONT_CACHE[bold] = ImageFont.truetype(_FONT_FILE.format('Bold' if bold else 'Regular'), 100)
        return _FONT_CACHE[bold].getlength(s) * size / 100.0
    except Exception:  # noqa: BLE001 — a missing font falls back to an estimate
        return len(s) * size * (0.6 if bold else 0.55)


def esc(s):
    return html.escape(str(s), quote=False)


def T(x, y, s, size=12, anchor='start', fill=INK, weight=400, bg=WHITE, italic=False):
    assert size >= MIN_PX, f'{size}px text is under the {MIN_PX}px floor: {s!r}'
    TEXT_PAIRS.add((fill, bg))
    TEXT_SIZES.append(size)
    st = ' font-style="italic"' if italic else ''
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:g}" text-anchor="{anchor}" fill="{fill}" '
            f'font-weight="{weight}"{st}>{esc(s)}</text>')


def line(x1, y1, x2, y2, col=INK, w=1.2, extra=''):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{w}" {extra}/>'


def arrow(x1, y1, x2, y2, col=INK, w=1.4):
    a = math.atan2(y2 - y1, x2 - x1)
    h = 6
    p1 = (x2 - h * math.cos(a - 0.45), y2 - h * math.sin(a - 0.45))
    p2 = (x2 - h * math.cos(a + 0.45), y2 - h * math.sin(a + 0.45))
    return (line(x1, y1, x2, y2, col, w) +
            f'<path d="M{x2:.1f} {y2:.1f} L{p1[0]:.1f} {p1[1]:.1f} L{p2[0]:.1f} {p2[1]:.1f}Z" fill="{col}"/>')


def svg_open(w=HALF, h=SVG_H, title=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family=\'{FONT_SANS}\' role="img"><title>{esc(title)}</title>')


# ── Seahorse geometry (mm, facing +x, y down) ────────────────────────────────
def chain(p0, a0, lengths, turns, wv, wd):
    """Ring boundaries of a chain of rings. turns[i] is the heading change (deg) at the start of ring i
    (negative = ventral flex toward +x). Returns [(x, y, heading_deg, ventral_halfwidth, dorsal_halfwidth)]."""
    pts, (x, y), a = [], p0, a0
    for i, L in enumerate(lengths):
        a += turns[i]
        pts.append((x, y, a, wv[i], wd[i]))
        x += L * math.cos(math.radians(a))
        y += L * math.sin(math.radians(a))
    pts.append((x, y, a, wv[len(lengths)], wd[len(lengths)]))
    return pts


def edges(pts):
    ven, dor = [], []
    for x, y, a, v, d in pts:
        nx, ny = math.sin(math.radians(a)), -math.cos(math.radians(a))     # ventral normal
        ven.append((x + nx * v, y + ny * v))
        dor.append((x - nx * d, y - ny * d))
    return ven, dor


def body_geometry(flex_u=0.4, tail_rings=N_RINGS):
    trunk_len = [4.0] * N_TRUNK
    trunk_turn = [0.0] + [3.2] * (N_TRUNK - 1)
    depth = [12, 15, 18, 20, 21, 21, 20, 18, 15.5, 12.5, 10.5, 9.0]
    trunk = chain((0.0, 0.0), 70.0, trunk_len, trunk_turn, [d * 0.6 for d in depth], [d * 0.4 for d in depth])
    tx, ty, ta = trunk[-1][0], trunk[-1][1], trunk[-1][2]
    n = tail_rings
    turns = [-flex_u * limit('ventral', i) for i in range(n)]
    half = [w / 2 for w in RING_WID[:n + 1]]
    tail = chain((tx, ty), ta, RING_LEN[:n], turns, half, half)
    return trunk, tail


def poly(pts):
    return 'M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in pts) + 'Z'


def seahorse(ox, oy, s, flex_u=0.4, facing=1, tail_rings=N_RINGS, rings=True, spots=True, eye_dir=None, uid='a'):
    """A seahorse drawn from the game's ring table. (ox, oy) is the neck in px; s is px per mm."""
    trunk, tail = body_geometry(flex_u, tail_rings)
    tv, td = edges(trunk)
    lv, ld = edges(tail)
    outline = tv + lv[1:] + list(reversed(ld[1:])) + list(reversed(td))
    g = [f'<g transform="translate({ox:.1f} {oy:.1f}) scale({facing * s:.4f} {s:.4f})">']
    # dorsal fin (trunk rings 8–10), drawn behind the body
    b0, b1 = td[8], td[11]
    fx, fy = (b0[0] + b1[0]) / 2 - 7.5, (b0[1] + b1[1]) / 2
    g.append(f'<path d="M{b0[0]:.1f} {b0[1]:.1f} Q{fx:.1f} {fy - 6:.1f} {fx - 1:.1f} {fy + 2:.1f} '
             f'Q{fx + 1:.1f} {fy + 8:.1f} {b1[0]:.1f} {b1[1]:.1f}Z" fill="#f3d9a0" stroke="{BODY_EDGE}" stroke-width="0.35" opacity=".9"/>')
    for k in range(1, 8):
        t = k / 8
        bx, by = b0[0] + (b1[0] - b0[0]) * t, b0[1] + (b1[1] - b0[1]) * t
        g.append(f'<path d="M{bx:.1f} {by:.1f} L{fx - 0.5 + (t - .5) * 3:.1f} {fy - 3 + t * 8:.1f}" stroke="#b98a3c" stroke-width="0.3"/>')
    g.append(f'<path d="{poly(outline)}" fill="{BODY}" stroke="{BODY_EDGE}" stroke-width="0.5" stroke-linejoin="round"/>')
    if rings:
        for (a, b) in list(zip(tv, td))[1:] + list(zip(lv, ld))[1:-1]:
            g.append(f'<path d="M{a[0]:.2f} {a[1]:.2f} L{b[0]:.2f} {b[1]:.2f}" stroke="{RING}" stroke-width="0.32"/>')
    if spots:
        for i in range(2, N_TRUNK - 1):
            x, y, a, v, d = trunk[i]
            for f in (-0.45, 0.1):
                nx, ny = math.sin(math.radians(a)), -math.cos(math.radians(a))
                g.append(f'<circle cx="{x + nx * v * f:.2f}" cy="{y + ny * v * f + 1.6:.2f}" r="0.7" fill="{SPOT}" opacity=".7"/>')
        for i in range(1, tail_rings - 2, 2):
            x, y = tail[i][0], tail[i][1]
            g.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{max(0.25, RING_WID[i] * 0.07):.2f}" fill="#fff8e6"/>')
    # head: skull, snout, coronet, eye, gill cover, pectoral fin (local mm, neck at the origin)
    g.append(f'<path d="M-4 -3 Q-8 -14 0 -19 Q8 -22 13 -14 L29 -9.5 Q31 -8.5 30.6 -6.6 L29.5 -4.6 L13.5 -3.6 '
             f'Q9 1 3 2 Q-2 1.5 -4 -3Z" fill="{BODY}" stroke="{BODY_EDGE}" stroke-width="0.5" stroke-linejoin="round"/>')
    g.append(f'<path d="M-2 -17.5 L-1 -22.5 L1.5 -19.5 L3.6 -23.4 L5 -19.6 L7 -21.6 L7.6 -18.4" fill="{BODY}" stroke="{BODY_EDGE}" stroke-width="0.45" stroke-linejoin="round"/>')
    g.append(f'<path d="M2.5 -2.5 Q-1 -8 2.5 -14" fill="none" stroke="{RING}" stroke-width="0.45"/>')
    g.append(f'<path d="M-1.5 -4 Q-7.5 -4.5 -6.5 1.5 Q-3.5 0.2 -1.5 -4Z" fill="#f3d9a0" stroke="{BODY_EDGE}" stroke-width="0.3" opacity=".9"/>')
    g.append(f'<circle cx="7.2" cy="-12" r="2.7" fill="#fff7e2" stroke="{BODY_EDGE}" stroke-width="0.4"/>')
    ex, ey = (0.0, 0.0) if eye_dir is None else eye_dir
    g.append(f'<circle cx="{7.2 + ex:.2f}" cy="{-12 + ey:.2f}" r="1.45" fill="#1b2430"/>')
    g.append('</g>')
    tip = tail[-1]
    return ''.join(g), (ox + facing * s * tip[0], oy + s * tip[1]), (ox + facing * s * 7.2, oy - s * 12)


# ── The eight panels ─────────────────────────────────────────────────────────
def panel_rings():
    out = [svg_open(title='Seahorse drawn from the game’s 35-ring tail table; published ring-count ranges')]
    art, _tip, _eye = seahorse(58, 30, 1.38, flex_u=0.42, uid='r')
    out.append(art)
    out.append(T(116, 24, '11 trunk rings', 12, fill=INK))
    out.append(T(116, 118, '35 tail rings', 12, fill=INK))
    # ring-count ranges on a number line 29–49
    x0, x1, lo, hi = 214, 504, 29, 49
    X = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)          # noqa: E731
    out.append(T(x0, 16, 'Tail rings: published ranges', 12, weight=700))
    rows = [('H. reidi, guide', 31, 39, CHIP['verified'][2]), ('H. reidi, 104 fish', 30, 39, CHIP['verified'][2]),
            ('H. reidi, one study', 33, 37, CHIP['verified'][2]), ('H. abdominalis', 45, 48, CHIP['other-species'][2])]
    for k, (lab, a, b, col) in enumerate(rows):
        y = 34 + k * 15
        out.append(f'<rect x="{X(a):.1f}" y="{y - 4:.1f}" width="{X(b) - X(a):.1f}" height="8" rx="4" fill="{col}" opacity=".85"/>')
        tx, anc = (X(b) + 6, 'start') if b < 40 else (X(a) - 6, 'end')
        out.append(T(tx, y + 4, lab, 11, anc, MUTED, italic=True))
    out.append(line(X(35), 26, X(35), 92, CHIP['ours'][2], 1.4, 'stroke-dasharray="3 2"'))
    out.append(f'<circle cx="{X(35):.1f}" cy="34" r="3.4" fill="#fff" stroke="{INK}" stroke-width="1.2"/>')
    out.append(T(X(35) - 5, 88, 'mode 35 = ours', 11, 'end', CHIP['ours'][0], 700))
    out.append(line(x0, 94, x1, 94, MUTED, 1))
    for v in (30, 35, 40, 45):
        out.append(line(X(v), 94, X(v), 98, MUTED, 1))
        out.append(T(X(v), 110, str(v), 11, 'middle', MUTED))
    # ring-length bars (ours)
    bx0, base = x0, 147
    sc = 6.0
    for i, L in enumerate(RING_LEN):
        out.append(f'<rect x="{bx0 + i * 3.6:.1f}" y="{base - L * sc:.1f}" width="2.6" height="{L * sc:.1f}" fill="{CHIP["ours"][2]}" opacity=".6"/>')
    out.append(T(bx0 + 35 * 3.6 + 8, 132, 'ours: ring length, base → tip', 11, 'start', CHIP['ours'][0]))
    out.append(T(bx0 + 35 * 3.6 + 8, 146, '3.75 → 1.67 mm; 90 mm in all', 11, 'start', CHIP['ours'][0]))
    out.append('</svg>')
    return ''.join(out)


def panel_square():
    out = [svg_open(title='Tail ring cross-sections: four L-shaped plates around a vertebra; twist per segment')]

    def sq_ring(cx, cy, r):
        g = []
        cols = ['#d39a32', '#c98a2a', '#e0aa45', '#bf8226']
        for k in range(4):
            g.append(f'<g transform="translate({cx} {cy}) rotate({k * 90})"><path d="M{-r + 2} {-r} L{-4} {-r} L{-4} {-r + 7} '
                     f'L{-r + 7} {-r + 7} L{-r + 7} {-4} L{-r} {-4} L{-r} {-r + 2}Z" fill="{cols[k]}" stroke="{BODY_EDGE}" stroke-width="1"/></g>')
        g.append(f'<circle cx="{cx}" cy="{cy}" r="9" fill="#f6ead2" stroke="{BODY_EDGE}" stroke-width="1"/>')
        for k in range(4):
            a = math.radians(45 + 90 * k)
            g.append(line(cx + 9 * math.cos(a), cy + 9 * math.sin(a), cx + (r - 9) * math.cos(a), cy + (r - 9) * math.sin(a), BODY_EDGE, 1.4))
        return ''.join(g)

    out.append(sq_ring(62, 78, 44))
    out.append(T(62, 142, 'square ring', 11, 'middle', MUTED))
    out.append(f'<circle cx="178" cy="78" r="41" fill="none" stroke="#c98a2a" stroke-width="7" stroke-dasharray="55 9.4"/>')
    out.append(f'<circle cx="178" cy="78" r="9" fill="#f6ead2" stroke="{BODY_EDGE}" stroke-width="1"/>')
    out.append(T(178, 142, 'round (model only)', 11, 'middle', MUTED))
    out.append(arrow(80, 15, 64, 32, ACC))
    out.append(T(84, 16, 'plates meet at joints', 11, fill=ACC))
    # twist per segment
    x0, y0 = 262, 30
    out.append(T(x0, 16, 'Twist between neighbouring rings', 12, weight=700))
    scale = 6.0
    bars = [('square model', 15, 15, CHIP['verified'][2]), ('round model', 30, 30, CHIP['verified'][2]),
            ('ours, base → tip', 3, 8, CHIP['ours'][2])]
    for k, (lab, a, b, col) in enumerate(bars):
        y = y0 + 14 + k * 34
        out.append(T(x0, y - 4, lab, 11, fill=MUTED))
        if a == b:
            out.append(f'<rect x="{x0}" y="{y}" width="{b * scale:.1f}" height="10" fill="{col}" opacity=".8"/>')
            out.append(T(x0 + b * scale + 5, y + 9, f'≈ {b}°', 11))
        else:
            out.append(f'<rect x="{x0}" y="{y}" width="{a * scale:.1f}" height="10" fill="{col}" opacity=".9"/>')
            out.append(f'<rect x="{x0 + a * scale:.1f}" y="{y}" width="{(b - a) * scale:.1f}" height="10" fill="{col}" opacity=".45"/>')
            out.append(T(x0 + b * scale + 5, y + 9, f'{a}–{b}°', 11))
    out.append('</svg>')
    return ''.join(out)


def panel_grip():
    out = [svg_open(title='Authored joint limits and runtime grasp, hold and release; schematic top views')]
    x0, y0, w, h = 40, 126, 205, 98
    X = lambda i: x0 + i / (N_RINGS - 1) * w                     # noqa: E731
    Y = lambda d: y0 - d / 42 * h                                 # noqa: E731
    out.append(T(10, 16, 'Our limit per joint (°)', 12, weight=700))
    for d in (0, 10, 20, 30, 40):
        out.append(line(x0, Y(d), x0 + w, Y(d), GRID, 1))
        out.append(T(x0 - 6, Y(d) + 4, str(d), 11, 'end', MUTED))
    cols = {'ventral': CORAL, 'lateral': ACC, 'twist': '#5d6f1f', 'dorsal': '#7a4a9a'}
    for kind in ('ventral', 'lateral', 'twist', 'dorsal'):
        a, b = LIMITS[kind]
        out.append(line(X(0), Y(a), X(N_RINGS - 1), Y(b), cols[kind], 2.2))
        dy = {'twist': 10, 'dorsal': -3}.get(kind, 4)
        out.append(T(X(N_RINGS - 1) + 4, Y(b) + dy, kind, 11, fill=cols[kind], weight=700))
    out.append(T(x0, y0 + 16, 'ring 0', 11, fill=MUTED))
    out.append(T(x0 + w, y0 + 16, 'ring 34 (tip)', 11, 'end', MUTED))
    out.append(T(315, 16, 'Runtime grip (ours)', 12, weight=700))
    out.append(T(315, 31, 'Top views · dot = vertical post', 11, fill=MUTED))
    for cx, label, sweep in ((337, 'Grasp', 1.0), (410, 'Hold', 1.6), (483, 'Release', .55)):
        out.append(f'<circle cx="{cx}" cy="59" r="5" fill="#8b6a4a"/>')
        pts = []
        for i in range(46):
            t = i / 45
            angle = -math.pi / 2 + t * sweep * math.pi
            radius = 22 - 10 * t
            pts.append((cx + radius * math.cos(angle), 59 + radius * math.sin(angle)))
        out.append('<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
                   + f'" fill="none" stroke="{BODY_EDGE}" stroke-width="5" stroke-linecap="round"/>')
        out.append('<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
                   + f'" fill="none" stroke="{BODY}" stroke-width="3" stroke-linecap="round"/>')
        # The arrow follows closing for grasp and reverses for release.
        a, b = (pts[22], pts[32]) if label != 'Release' else (pts[32], pts[22])
        out.append(arrow(*a, *b, CORAL))
        out.append(T(cx, 96, label, 11, 'middle', INK, 700))
    out.append(arrow(363, 59, 382, 59, MUTED))
    out.append(arrow(437, 59, 455, 59, MUTED))
    out.append(T(315, 118, 'Tip closes first; release unwinds.', 11, fill=MUTED))
    out.append(T(315, 140, 'Release → swim → probe → grasp', 11, fill=ACC))
    out.append('</svg>')
    return ''.join(out)


def panel_fin():
    out = [svg_open(title='A 50 Hz fin beat sampled at 60 Hz looks like a slow 10 Hz wave')]
    f_fin, f_screen, t_end = 50.0, 60.0, 100.0           # Hz, Hz, ms
    x0, yc, w, amp = 26, 76, 450, 30
    X = lambda t: x0 + t / t_end * w                       # noqa: E731
    pts = ' '.join(f'{X(t):.1f},{yc - amp * math.sin(2 * math.pi * f_fin * t / 1000):.1f}' for t in [k * 0.25 for k in range(401)])
    out.append(T(10, 16, f'A {f_fin:g} Hz fin beat, seen by a {f_screen:g} Hz screen', 12, weight=700))
    out.append(T(10, 32, f'Red dots: one per 16.7 ms frame. Joined up, they look like a {abs(f_fin - f_screen):g} Hz wave.', 11, fill=CORAL))
    out.append(f'<polyline id="fin-true" points="{pts}" fill="none" stroke="#8fa5b2" stroke-width="1.3"/>')
    alias = abs(f_fin - f_screen)
    apts = ' '.join(f'{X(t):.1f},{yc - amp * math.sin(-2 * math.pi * alias * t / 1000):.1f}' for t in [k * 0.5 for k in range(201)])
    out.append(f'<polyline points="{apts}" fill="none" stroke="{CORAL}" stroke-width="2" stroke-dasharray="5 3"/>')
    for k in range(int(t_end / (1000 / f_screen)) + 1):
        t = k * 1000 / f_screen
        out.append(f'<circle cx="{X(t):.1f}" cy="{yc - amp * math.sin(2 * math.pi * f_fin * t / 1000):.1f}" r="3.6" fill="{CORAL}"/>')
    out.append(line(x0, yc + amp + 8, x0 + w, yc + amp + 8, MUTED, 1))
    for t in range(0, 101, 20):
        out.append(line(X(t), yc + amp + 8, X(t), yc + amp + 12, MUTED, 1))
        out.append(T(X(t), yc + amp + 25, f'{t} ms', 11, 'middle', MUTED))
    out.append(T(10, 147, f"Six pairs, close idle: {FRAME_FPS['close-idle'][6]:.1f} FPS, one frame every {FRAME_MS['close-idle'][6]:.1f} ms.", 11, fill=MUTED))
    out.append('</svg>')
    return ''.join(out)


def head_outline(cx, cy, s, rot):
    return (f'<g transform="translate({cx} {cy}) rotate({rot}) scale({s})">'
            f'<path d="M-4 -3 Q-8 -14 0 -19 Q8 -22 13 -14 L29 -9.5 Q31 -8.5 30.6 -6.6 L29.5 -4.6 L13.5 -3.6 Q9 1 3 2 Q-2 1.5 -4 -3Z" '
            f'fill="{BODY}" stroke="{BODY_EDGE}" stroke-width="0.6" opacity="{1 if rot else .45}"/>'
            f'<circle cx="7.2" cy="-12" r="2.2" fill="#1b2430" opacity="{1 if rot else .45}"/></g>')


def panel_strike():
    out = [svg_open(title='Adult H. reidi strike timeline against one 60 Hz frame')]
    out.append(head_outline(34, 90, 2.2, 0))
    out.append(head_outline(34, 90, 2.2, -27))
    ref = source_order().index('roos') + 1
    out.append(T(10, 128, 'peak head rotation', 11, fill=MUTED))
    out.append(T(10, 142, f'26.7 ± 8° [{ref}]', 11, fill=MUTED))
    x0, x1, y = 132, 500, 104
    t_end = 18.0
    X = lambda t: x0 + t / t_end * (x1 - x0)               # noqa: E731
    out.append(T(10, 16, 'Adult strike, timed from the first hyoid movement (ms)', 12, weight=700))
    out.append(f'<rect x="{X(4.9):.1f}" y="{y - 8}" width="{X(6.5) - X(4.9):.1f}" height="16" fill="{CORAL}" opacity=".18"/>')
    out.append(line(x0, y, x1, y, INK, 1.4))
    for t in range(0, 19, 2):
        out.append(line(X(t), y, X(t), y + 5, INK, 1))
        out.append(T(X(t), y + 19, str(t), 11, 'middle', MUTED))
    events = [(0.4, 'head starts to rise'), (2.6, 'widest gape'), (3.6, 'head at its highest'), (5.7, 'prey in the mouth')]
    tx = X(7.0)
    for k, (t, lab) in enumerate(events):
        ly = 34 + k * 15
        col = CORAL if t == 5.7 else INK
        out.append(f'<path d="M{X(t):.1f} {y - 3} L{X(t):.1f} {ly - 4} L{tx - 4:.1f} {ly - 4}" fill="none" stroke="{col}" stroke-width="0.9" stroke-dasharray="2 2"/>')
        out.append(f'<circle cx="{X(t):.1f}" cy="{y}" r="3.5" fill="{col}"/>')
        out.append(T(tx, ly, f'{t:g} ms  {lab}', 11, 'start', col, 700 if t == 5.7 else 400))
    fr = 1000 / 60
    out.append(line(X(fr), 26, X(fr), y + 6, ACC, 2))
    out.append(T(X(fr) - 4, 142, 'one frame at 60 Hz = 16.7 ms', 11, 'end', ACC, 700))
    out.append('</svg>')
    return ''.join(out)


def panel_pairs():
    out = [svg_open(title='Authored greeting: opposite sides and offset coils; six pairs and six holdfasts, schematic not tank layout')]
    px = 152
    out.append(T(10, 16, 'Greeting (ours)', 12, weight=700))
    out.append(f'<rect x="{px - 5}" y="29" width="10" height="111" rx="4" fill="#8b6a4a" stroke="#5c432c" stroke-width="1"/>')
    colours = (BODY, '#d58f3a')
    for k, (ox, facing, eye) in enumerate(((90, 1, (1.0, -0.7)), (214, -1, (0.7, 0.8)))):
        art, tip, ep = seahorse(ox, 49, 1.0, flex_u=0.12, facing=facing, tail_rings=11, spots=False, eye_dir=eye, uid=f'p{k}')
        col = colours[k]
        if k == 1:
            art = art.replace(f'fill="{BODY}"', f'fill="{col}"')
        out.append(art)
        y_on = 104 + k * 13
        out.append(f'<path d="M{tip[0]:.1f} {tip[1]:.1f} Q{tip[0] + facing * 2:.1f} {y_on + 2:.1f} {px - facing * 10:.1f} {y_on:.1f}" '
                   f'fill="none" stroke="{col}" stroke-width="5" stroke-linecap="round"/>')
        for j in range(3):
            yb = y_on + j * 5
            out.append(f'<path d="M{px - 11} {yb:.1f} Q{px} {yb - 5:.1f} {px + 11} {yb + 2:.1f}" fill="none" '
                       f'stroke="{col}" stroke-width="{7 - j * 1.1:.1f}" stroke-linecap="round"/>')
        ex, ey = ep
        tx_, ty_ = (ex + facing * 22, ey - 14) if k == 0 else (ex + facing * 30, ey + 22)
        out.append(arrow(ex + facing * 3, ey, tx_, ty_, ACC))
    out.append(T(10, 146, 'Opposite sides; coils at different heights', 11, fill=MUTED))
    out.append(line(270, 8, 270, 145, GRID))
    out.append(T(283, 16, '12 residents · 6 holdfasts (ours)', 12, weight=700))
    for i in range(6):
        cx, cy = 313 + i % 3 * 77, 48 + i // 3 * 43
        out.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="#8b6a4a"/>')
        for dx, col in ((-17, BODY), (17, '#d58f3a')):
            out.append(f'<circle cx="{cx + dx}" cy="{cy}" r="5" fill="{col}" stroke="{BODY_EDGE}"/>')
        out.append(T(cx, cy + 22, str(i + 1), 11, 'middle', MUTED))
    out.append(T(283, 130, 'Greeting rotates through visible pairs.', 11, fill=ACC))
    out.append(T(283, 146, 'Check occupied spots before moving.', 11, fill=MUTED))
    out.append('</svg>')
    return ''.join(out)


def panel_joints():
    out = [svg_open(title='As-built asset: 1101 triangles, 2 actors, 693 clip frames; 25 controls drive 105 joint angles')]
    for cx, number, label in ((88, '1,101', 'triangles / seahorse'),
                              (258, '2', 'actors: body + fins'),
                              (430, '693', 'authored clip frames')):
        out.append(T(cx, 31, number, 27, 'middle', ACC, 700))
        out.append(T(cx, 49, label, 11, 'middle', MUTED))
    out.append(line(10, 59, 507, 59, GRID))
    out.append(T(10, 76, '35 rings · flex + sideways bend + twist · 7 control knots', 11, weight=700))
    x0, y, step = 20, 81, 13.8
    for i in range(N_RINGS):
        cx = x0 + 6 + i * step
        knot = i in KNOTS
        out.append(f'<circle cx="{cx:.1f}" cy="{y + 10}" r="{6 if knot else 3.2}" fill="{CORAL if knot else BODY}" stroke="{BODY_EDGE}" stroke-width="1"/>')
        if knot:
            out.append(T(cx, y + 28, str(i), 11, 'middle', MUTED))
    out.append(T(10, 139, '21 knot angles + 4 wrap values', 12, fill=CHIP['ours'][0], weight=700))
    out.append(arrow(226, 135, 260, 135, ACC))
    out.append(T(277, 139, '105 joint angles + clip blending', 12, fill=ACC, weight=700))
    out.append('</svg>')
    return ''.join(out)


def panel_cost():
    out = [svg_open(title='Cast1 close-idle FPS: measured populations and interpolated estimates; CPU increment')]
    x0, x1, top, bottom = 36, 298, 30, 105
    X = lambda n: x0 + n / 6 * (x1 - x0)
    Y = lambda fps: bottom - fps / 25 * (bottom-top)
    out.append(T(10, 16, 'Close idle · FPS', 12, weight=700))
    for fps in (0, 10, 20):
        out.append(line(x0, Y(fps), x1, Y(fps), GRID, 1))
        out.append(T(x0-5, Y(fps)+4, str(fps), 11, 'end', MUTED))
    for n in range(7):
        out.append(T(X(n), 122, 'None' if n == 0 else str(n), 11, 'middle', MUTED))
    measured = FRAME_FPS['close-idle']
    estimated = INTERPOLATED_FPS['close-idle']
    for a, b in ((0, 1), (1, 2)):
        out.append(line(X(a), Y(measured[a]), X(b), Y(measured[b]), CHIP['ours'][0], 1.6))
    rows = FRAME_MS['close-idle']
    curve = [(2+i/25, 1000/(rows[2]+i/100*(rows[6]-rows[2]))) for i in range(101)]
    points = ' '.join(f'{X(n):.2f},{Y(fps):.2f}' for n, fps in curve)
    out.append(f'<polyline points="{points}" fill="none" stroke="{WARN}" stroke-width="1.5" stroke-dasharray="4 3"/>')
    for n in range(7):
        known = n in measured
        fps = measured[n] if known else estimated[n]
        col = CHIP['ours'][0] if known else WARN
        out.append(f'<circle cx="{X(n):.2f}" cy="{Y(fps):.2f}" r="3.2" fill="{col if known else WHITE}" stroke="{col}" stroke-width="1.4"/>')
        out.append(T(X(n), Y(fps)-8, f'{fps:.1f}', 11, 'middle', col))
    for x, known, label in ((14, True, 'measured'), (123, False, 'estimated')):
        col = CHIP['ours'][0] if known else WARN
        out.append(f'<circle cx="{x}" cy="140" r="3.2" fill="{col if known else WHITE}" stroke="{col}" stroke-width="1.4"/>')
        out.append(T(x+8, 144, label, 11, fill=col))
    out.append(T(293, 144, 'pairs', 11, 'end', MUTED))
    bx, bw = 331, 173
    out.append(T(bx, 16, 'Main-thread CPU', 12, weight=700))
    out.append(T(bx, 35, '6 pairs − None · close idle', 11, fill=MUTED))
    out.append(T(bx, 56, f"+{CPU_DELTA['total']:.2f} ms", 17, weight=700))
    update_width = bw * CPU_DELTA['update']/CPU_DELTA['total']
    out.append(f'<rect x="{bx}" y="65" width="{update_width:.2f}" height="13" fill="{CHIP["ours"][0]}"/>')
    out.append(f'<rect x="{bx+update_width:.2f}" y="65" width="{bw-update_width:.2f}" height="13" fill="{ACC}"/>')
    out.append(T(bx, 96, f"+{CPU_DELTA['update']:.2f} update", 11, fill=CHIP['ours'][0]))
    out.append(T(bx, 112, f"+{CPU_DELTA['render']:.2f} render", 11, fill=ACC))
    out.append(T(bx, 129, f"animation +{CPU_DELTA['animation']:.2f}", 11, fill=MUTED))
    out.append(T(bx, 144, 'already inside update', 11, fill=MUTED))
    out.append('</svg>')
    return ''.join(out)


DRAW = {'rings': panel_rings, 'square': panel_square, 'grip': panel_grip, 'fin': panel_fin,
        'strike': panel_strike, 'pairs': panel_pairs, 'joints': panel_joints, 'cost': panel_cost}


# ── HTML ─────────────────────────────────────────────────────────────────────
def chip_html(c):
    kind = c['status']
    label = c.get('chip', STATUS_TEXT[kind])
    return f'<span class="chip {kind}">{esc(label)}</span>'


def refs_html(c, num):
    if not c['src']:
        return ''
    return '\u00a0<span class="ref">[' + ', '.join(str(num[s]) for s in c['src']) + ']</span>'


def claim_html(c, num, area):
    return (f'<p class="cl" data-status="{c["status"]}" data-area="{area}">{chip_html(c)} {c["text"]}{refs_html(c, num)}</p>')


def panel_html(i, p, num, svg):
    claims = ''.join(claim_html(c, num, p['key']) for c in p['claims'])
    return (f'<section class="panel" id="panel-{p["key"]}"><div class="bar">{i:02d} · {esc(p["title"])}</div>'
            f'{svg}<div class="claims">{claims}</div></section>')


def header_html(num):
    claims = ''.join(claim_html(c, num, 'header') for c in HEADER_CLAIMS)
    return ('<header><div class="ttl"><h1>Longsnout seahorse</h1>'
            '<div class="sub">A tail that holds on: the biomechanics behind the Planted Tank’s seahorses</div>'
            '<div class="meta"><i>Hippocampus reidi</i> · World Foundry aquarium series</div></div>'
            f'<div class="facts">{claims}</div></header>')


def legend_html():
    items = ''.join(f'<span class="lg"><span class="chip {s}">{STATUS_TEXT[s]}</span> {LEGEND_TEXT[s]}</span>' for s in used_statuses())
    return f'<div class="legend">{items}</div>'


def footer_html(num):
    order = source_order()
    lis = []
    for s in order:
        d = SOURCES[s]
        lis.append(f'<li>[{num[s]}] <a href="{d["url"]}">{esc(d["cite"])}</a> · {esc(d["where"])} · <i>{esc(d["species"])}</i></li>')
    per = -(-len(lis) // 3)
    cols = [lis[i * per:(i + 1) * per] for i in range(3)]
    cols_html = ''.join(f'<ol>{"".join(c)}</ol>' for c in cols)
    return (f'<footer id="panel-src">{legend_html()}<div class="srcs">{cols_html}</div>'
            f'<div class="note">Sources checked {CHECKED}; game measured {MEASURED_DATE}. Saltwater, seed 713, age 150, growth paused. Locators, DOIs and access limits: docs/reference/seahorse-research.md. '
            'The drawings are original and use the game’s own ring table. Claims the research could not confirm stay in the research document. '
            'A3 portrait, 297 × 420 mm; print on matte or uncoated stock.</div></footer>')


CSS = f"""
@page {{ size: A3 portrait; margin: 0 }}
*{{ box-sizing: border-box }}
html,body{{ margin:0; background:#fff; color:{INK}; -webkit-print-color-adjust:exact; print-color-adjust:exact }}
body{{ font: 11.5px/1.3 {FONT_SANS} }}
.page{{ width:{PAGE_W_MM}mm; height:{PAGE_H_MM}mm; padding:{MARGIN_MM}mm; overflow:hidden; display:flex; flex-direction:column; gap:6px; background:#fff }}
header{{ background:{NAVY}; color:#fff; display:flex; gap:16px; padding:9px 14px 8px; height:104px; flex:none }}
header .ttl{{ width:470px; flex:none }}
header h1{{ font-family:{FONT_SERIF}; margin:0; font-size:33pt; line-height:1.05; font-weight:700; letter-spacing:-.01em }}
header .sub{{ color:{NAVY_TEXT}; font-size:13px; line-height:1.3; margin-top:5px }}
header .meta{{ color:{NAVY_TEXT}; font-size:12px; margin-top:4px }}
header .facts{{ flex:1; background:#fff; color:{INK}; border-radius:5px; padding:5px 8px }}
header .facts .cl{{ margin:0 0 3px }}
.row{{ display:flex; gap:13px; flex:none }}
.panel{{ width:{HALF}px; height:288px; overflow:hidden; border:1px solid {GRID}; flex:none }}
.bar{{ background:{ACC}; color:#fff; font-family:{FONT_SERIF}; font-size:12.5pt; font-weight:700; height:24px; line-height:24px; padding:0 10px; white-space:nowrap }}
.panel svg{{ display:block; margin-top:2px }}
.claims{{ padding:1px 9px 0 }}
.cl{{ margin:0 0 3px; font-size:11.5px; line-height:15px }}
.ref{{ color:{MUTED}; white-space:nowrap }}
.chip{{ display:inline-block; border-radius:8px; padding:0 6px; font-size:11px; line-height:13px; font-weight:700; border:1px solid; white-space:nowrap; vertical-align:baseline }}
{''.join(f'.chip.{k}{{ color:{v[0]}; background:{v[1]}; border-color:{v[2]} }}' for k, v in CHIP.items())}
footer{{ flex:1; border-top:2px solid {ACC}; padding-top:5px; display:flex; flex-direction:column; gap:4px; min-height:0 }}
.legend{{ display:flex; gap:18px; font-size:11px; line-height:14px; color:{INK} }}
.srcs{{ display:flex; gap:14px }}
.srcs ol{{ list-style:none; margin:0; padding:0; flex:1 }}
.srcs li{{ font-size:11px; line-height:13.5px; margin:0 0 3px; color:{MUTED} }}
.note{{ font-size:11px; line-height:14px; color:{MUTED} }}
a{{ color:{ACC}; text-decoration:underline }}
"""

FIT_SCRIPT = ("<script>window.addEventListener('load',function(){var p=document.querySelector('.page'),"
              "lim=p.getBoundingClientRect().bottom-parseFloat(getComputedStyle(p).paddingBottom),"
              "f=document.getElementById('panel-src'),k=f.lastElementChild,over=k.getBoundingClientRect().bottom-lim,bad=[];"
              "document.querySelectorAll('.panel').forEach(function(e){if(e.scrollHeight>e.clientHeight+1)bad.push(e.id);});"
              "document.body.setAttribute('data-fit',(over<=1&&!bad.length)?'ok':'overflow');"
              "document.body.setAttribute('data-over',over.toFixed(1));"
              "document.body.setAttribute('data-panels-over',bad.join(' '));});</script>")

UNITS = r'(?:cm/s|frames/s|ms|Hz|cm|mm|gal|kg|g|s|m|%|°|FPS)'
_NUM_UNIT = re.compile(rf'(\d)[ \u00a0]+({UNITS})(?![\w/])')
_PM = re.compile(r'(\d) ± (\d)')
_TIMES = re.compile(r'(\d) × (\d)')
_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_PAGEID = re.compile(r'\b(56)-(\d)\b')


def polish_text(s):
    s = _PM.sub('\\1\u00a0±\u00a0\\2', s)
    s = _TIMES.sub('\\1\u00a0×\u00a0\\2', s)
    s = _NUM_UNIT.sub('\\1\u00a0\\2', s)
    s = _ISO.sub('\\1\u2011\\2\u2011\\3', s)
    return _PAGEID.sub('\\1\u2011\\2', s)


def polish(doc):
    """Unit binding and non-breaking hyphens in text nodes only (never in tags, <style> or <script>)."""
    out, skip = [], False
    for part in re.split(r'(<[^>]*>)', doc):
        if part.startswith('<'):
            low = part.lower()
            if low.startswith(('<style', '<script')):
                skip = True
            elif low.startswith(('</style', '</script')):
                skip = False
            out.append(part)
        else:
            out.append(part if skip else polish_text(part))
    return ''.join(out)


def check_claims():
    problems = []
    for area, c in all_claims():
        if c['status'] not in PRINTABLE:
            problems.append(f'{area}: {c["status"]} claim may not print: {c["text"][:60]}')
        if c['status'] in ('verified', 'other-species') and not c['src']:
            problems.append(f'{area}: {c["status"]} claim without a source')
        if c.get('game') and c['status'] != 'ours':
            problems.append(f'{area}: a game number must be chipped ours')
        for s in c['src']:
            if s not in SOURCES:
                problems.append(f'{area}: unknown source {s}')
    return problems


def build():
    """Returns (poster html, {svg file name: svg}). Polished, ready to write."""
    problems = check_claims()
    if problems:
        raise SystemExit('make_poster: ' + '\n  '.join(problems))
    TEXT_PAIRS.clear()
    TEXT_SIZES.clear()
    num = {s: i + 1 for i, s in enumerate(source_order())}
    svgs = {p['key']: polish(DRAW[p['key']]()) for p in PANELS}
    rows = []
    for r in range(0, len(PANELS), 2):
        rows.append('<div class="row">' + ''.join(panel_html(r + j + 1, PANELS[r + j], num, svgs[PANELS[r + j]['key']])
                                                  for j in range(2)) + '</div>')
    body = header_html(num) + ''.join(rows) + footer_html(num)
    doc = ('<!DOCTYPE html>\n<!-- Generated by make_poster.py: edit that, not this file. -->\n'
           '<html lang="en"><head><meta charset="utf-8"><title>Longsnout seahorse: biomechanics poster (A3)</title>'
           f'<style>{CSS}</style></head><body><div class="page">{body}</div>{FIT_SCRIPT}</body></html>\n')
    files = {f'{i + 1:02d}-{p["key"]}.svg': '<?xml version="1.0" encoding="UTF-8"?>\n' + svgs[p['key']] + '\n'
             for i, p in enumerate(PANELS)}
    return polish(doc), files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out-dir', type=Path, default=HERE)
    args = ap.parse_args(argv)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    doc, files = build()
    (out / 'poster.html').write_text(doc, encoding='utf-8')
    for name, svg in files.items():
        (out / name).write_text(svg, encoding='utf-8')
    print(f'wrote {out / "poster.html"} and {len(files)} SVG panels')
    return 0


if __name__ == '__main__':
    sys.exit(main())
