#!/usr/bin/env python3
"""Build the lava lamp poster: one A3 portrait page (297 x 420 mm), seven panels, every claim chipped.

    python3 docs/reference/lava-lamp-poster/make_poster.py [--draft]
    python3 docs/reference/lava-lamp-poster/export_poster.py
    scripts/in-linux-container.sh python3 -m pytest tests/test_lava_lamp_poster.py -q

Plan: docs/plans/2026-11-26-lava-lamp.md (D10, Q7, Q8, Phase P). The research comes first:
docs/reference/lava-lamp-research.md gives each source's locator and what was not found. Every claim below lives in
HEADER_CLAIMS / PANELS with its status chip and its sources, and `check_claims()` refuses to build when a claim lacks
either, when a source's link is not in the research document, or (without --draft) while the research does not say
"Poster visual review: approved". A draft is marked as one on the page and exports to a review-draft PDF name.

The level's numbers are not typed here: the blob count, the model's character and the Forth words are read from
wflevels/lava_lamp (model.py, lamp.py, forth.py) when the poster builds. The hero image is hero-cycles.png
(render_hero.py, CPU Cycles in the Blender container); the QR codes are qr/*.svg (make_qr.py). Writes poster.html and
the editable SVG drawings (01-moves.svg, 02-bottle.svg).
"""
from __future__ import annotations

import argparse
import base64
import html
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LEVEL = REPO / 'wflevels' / 'lava_lamp'
RESEARCH = HERE.parent / 'lava-lamp-research.md'
sys.path.insert(0, str(LEVEL))
sys.path.insert(0, str(HERE))
import forth as FORTH  # noqa: E402
import lamp as LAMP  # noqa: E402
import model as MODEL  # noqa: E402
from patents import CHECKED, PATENTS  # noqa: E402

APPROVED_LINE = 'Poster visual review: approved'
REVIEW_PROBLEM = 'poster visual review is incomplete'

# ── Page ─────────────────────────────────────────────────────────────────────
PAGE_W_MM, PAGE_H_MM, MARGIN_MM = 297, 420, 8
WIDE = 1062                     # the page's inner width, px (281 mm at 96 px per inch)
LEFT, RIGHT = 692, 358          # row 1: the two text panels and the hero, with a 12 px gap
MIN_PX = 11.0                   # 8.25 pt: nothing on the poster is set smaller

INK, MUTED, GRID, WHITE = '#21182a', '#584e60', '#ddd5e2', '#ffffff'
NIGHT, NIGHT_TEXT, ACC = '#24102f', '#e3d3ee', '#6b2fa8'
WAX, WAX_DARK, WATER, WATER_PALE, GOLD = '#e8590c', '#b23c06', '#5b2bc4', '#e7defa', '#b88a1e'
CHIP = {   # kind: (text, fill, edge)
    'verified': ('#0f5f30', '#e3f4ea', '#1f8a4c'),
    'other-source': ('#6a2a94', '#f1e6fb', '#8a44c0'),
    'ours': ('#1b46b3', '#e4ecff', '#2b5fd9'),
    'unverified': ('#7a4500', '#fff2d9', '#b26a00'),
}
STATUS_TEXT = {'verified': 'verified', 'other-source': 'other source', 'ours': 'ours', 'unverified': 'unverified'}
LEGEND_TEXT = {
    'verified': 'a source says this of the lava lamp or its materials',
    'other-source': 'a source says it of another lamp',
    'ours': 'our level, model or design; “measured”: computed by a named script',
}
PRINTABLE = ('verified', 'other-source', 'ours')
FONT_SANS = '"Noto Sans","DejaVu Sans",sans-serif'
FONT_SERIF = '"Noto Serif","DejaVu Serif",serif'
FONT_MONO = '"Noto Sans Mono","DejaVu Sans Mono",monospace'

TEXT_PAIRS = set()              # (foreground, background) of every SVG text: the contrast test reads it
TEXT_SIZES = []                 # every SVG font size (px)


# ── The level's numbers: read, never typed ───────────────────────────────────
def level_data():
    char = MODEL.character()
    return dict(blobs=MODEL.N_BLOBS, pooled=char['pooled'] * 100, resting=char['resting'] * 100,
                moving=char['moving'] * 100, cycle=char['cycle'], climb=char['peak_climb'],
                warm=MODEL.WARM_STEPS * float(MODEL.DT), steps=MODEL.MAX_STEPS, cell0=LAMP.BLOB0,
                stride=LAMP.BLOB_STRIDE, cols=29, rows=9)


DATA = level_data()

FORTH_WORDS = ('ll-env', 'll-glow', 'll-frame', 'll-tick')


def forth_lines():
    """The printed words, copied from the director script the generator writes (the test finds each in the .lev)."""
    script = FORTH.definitions(FORTH.default_indices(), FORTH.default_fields())
    words = {}
    for ln in script.splitlines():
        m = re.match(r': (\S+) ', ln)
        if m:
            words[m.group(1)] = ln
    return [words[w] for w in FORTH_WORDS]


# ── Sources (numbered by first use) ──────────────────────────────────────────
SOURCES = {
    'lava': dict(cite='Wikipedia, “Lava lamp”', url='https://en.wikipedia.org/wiki/Lava_lamp',
                 where='“Operation” and “History”', scope='the lava lamp'),
    'us396': dict(cite='US 3,387,396, Display devices (1968)', url='https://patents.google.com/patent/US3387396A/en',
                  where='description and claim 1', scope='the lava lamp patent'),
    'hpm': dict(cite='How Products Are Made, “Lava Lamp”, Encyclopedia.com',
                url='https://www.encyclopedia.com/manufacturing/news-wires-white-papers-and-books/lava-lamp',
                where='the Century; first use', scope='the US Lava Lite'),
    'paraffin': dict(cite='Wikipedia, “Paraffin wax”', url='https://en.wikipedia.org/wiki/Paraffin_wax',
                     where='“Properties”', scope='paraffin wax'),
    'schim': dict(cite='Schimmelpfennig et al., Volume expansion of paraffins',
                  url='https://ic.unicamp.br/~stolfi/EXPORT/projects/wikipedia/00-DOCS/Volume_expansion_of_paraffins_from_dip_tube_measur.pdf',
                  where='Introduction', scope='paraffin wax'),
    'ccl4': dict(cite='Wikipedia, “Carbon tetrachloride”', url='https://en.wikipedia.org/wiki/Carbon_tetrachloride',
                 where='infobox: density', scope='carbon tetrachloride'),
    'mathmos': dict(cite='Wikipedia, “Mathmos”', url='https://en.wikipedia.org/wiki/Mathmos',
                    where='“Company history”', scope='Mathmos, Poole'),
    'gp': dict(cite='Google Patents, the six numbers in panel 04', url='https://patents.google.com/',
               where='titles, names, dates', scope='patents'),
    'ecw': dict(cite='Wikipedia, “Edward Craven Walker”', url='https://en.wikipedia.org/wiki/Edward_Craven_Walker',
                where='“Film work”, “Later years”', scope='the inventor'),
    'lavarand': dict(cite='Wikipedia, “Lavarand”', url='https://en.wikipedia.org/wiki/Lavarand',
                     where='lead and “History”', scope='Lavarand, Cloudflare'),
    'cf': dict(cite='Cloudflare blog, “LavaRand in Production” (2017)',
               url='https://blog.cloudflare.com/lavarand-in-production-the-nitty-gritty-technical-details/',
               where='introduction', scope='Cloudflare’s lobby wall'),
}

D = DATA
# ── Claims. status: verified | other-source | ours. A verified or other-source claim needs sources; an ours claim names
#    what computes or decides it in `by`. Unconfirmed claims stay in the research document and never reach this list.
HEADER_CLAIMS = [
    dict(status='verified', src=['lava'],
         text='Invented in 1963 by Edward Craven Walker, whose company became Mathmos; Mathmos lamps have been made in Poole, Dorset, ever since.'),
    dict(status='ours', src=[], by='wflevels/lava_lamp', chip='design (ours)',
         text='This one is a World Foundry clock: a 1963-style Astro whose wax moves by a small physical model written in Forth, '
              'with the time in the holes of its base.'),
]

PANELS = [
    dict(key='moves', title='How it moves', claims=[
        dict(status='verified', src=['lava'],
             text='A bulb heats the bottle. Common wax floats on water at any temperature, so it was weighted to nearly the water’s density. '
                  'Heated, the wax expands, grows less dense and rises; near the cooler top it gives up heat, grows denser and sinks.'),
        dict(status='verified', src=['us396'],
             text='The lamp’s patent puts the heater beneath the bottle and, at its base, “a surface tension breaker comprising a spiral wire ring”, '
                  'so blobs coming down merge again.'),
        dict(status='verified', src=['lava'],
             text='Fluid dynamicists file the motion as a form of Rayleigh–Taylor instability. Shake a warm lamp and the two liquids emulsify into a cloudy mess.'),
        dict(status='verified', src=['hpm'],
             text='The first time, the wax may need four hours or more to melt through.'),
    ]),
    dict(key='bottle', title='What is in the bottle', claims=[]),     # a table: BOTTLE_ROWS
    dict(key='hero', title='The lamp in this clock', claims=[
        dict(status='ours', src=[], by='render_hero.py', chip='ours',
             text=f'The shipped scene in Cycles: {D["blobs"]} blobs posed as on the engine’s first frame, Orange in Violet, 21:47 in the base.'),
        dict(status='other-source', src=['hpm'],
             text='The US Lava Lite Century’s gold base “is perforated with tiny holes which simulate starlight”.'),
        dict(status='ours', src=[], by='generate.py', chip='design (ours)',
             text=f'Ours spell the time, 24-hour, on a {D["cols"]} × {D["rows"]} grid; the other holes glow faintly. '
                  'They change once a minute. The wax never knows the time.'),
    ]),
    dict(key='patents', title='Patents', claims=[
        dict(status='verified', src=['gp'],
             text='Numbers, names and dates as Google Patents gives them; scan a code to open the patent. Dunnet’s page lists the next four as citing it.'),
    ]),
    dict(key='history', title='A short history', claims=[]),          # the timeline: HISTORY
    dict(key='forth', title='Forth that moves the wax', claims=[
        dict(status='ours', src=[], by='forth.py',
             text=f'Copied from the level’s director. A generator writes it from the Python model, word for word in 32-bit floats; '
                  f'a test runs it in the real zForth VM against the model step for step. Blob <i>i</i> keeps its state in mailboxes '
                  f'{D["cell0"]}&nbsp;+&nbsp;{D["stride"]}<i>i</i>; each frame runs whole 1/30 s steps, at most {D["steps"]}.'),
        dict(status='ours', src=[], by='model.character()', chip='ours (measured)',
             text=f'Over 20 simulated minutes the {D["blobs"]} blobs spend {D["pooled"]:.0f} % of their time pooled on the coil, '
                  f'{D["resting"]:.0f} % resting under the cap and {D["moving"]:.0f} % moving; a cycle takes about {D["cycle"]:.0f} s. Game tuning, not a measured lamp.'),
    ]),
    dict(key='ways', title='Four ways to move it', claims=[
        dict(status='ours', src=[], by='plan D6; build record', chip='design (ours)',
             text='Shapes are morph targets (rise, fall, squash, neck, two wobbles) that the engine’s Morph deformer blends each frame.'),
    ]),
]

BOTTLE_ROWS = [   # (ingredient, claim)
    ('Paraffin wax', dict(status='verified', src=['paraffin'], text='about 0.9 g/cm³; melts at 46–68 °C, by grade')),
    ('On melting', dict(status='verified', src=['schim'], text='its volume grows by up to 10 %')),
    ('Carbon tetrachloride', dict(status='verified', src=['ccl4', 'lava'],
                                  text='1.59 g/cm³, about 60 % denser than water; nonflammable, mixes with wax')),
    ('The 1968 recipe', dict(status='verified', src=['us396'],
                             text='mineral oil, light paraffin, carbon tetrachloride and dye, fluent at “45 50 C.”')),
    ('Since 1970', dict(status='verified', src=['lava'], text='no carbon tetrachloride in US lamps (banned for toxicity)')),
    ('Today', dict(status='verified', src=['lava', 'mathmos'],
                   text='the US formula is a trade secret; Mathmos still uses Craven Walker’s, improved with him in the 1990s')),
]
BOTTLE_NOTE = dict(status='ours', src=[], by='design', chip='schematic (ours)',
                   text='The drawing shows the idea, not data: the wax’s density falls faster with heat than the water’s, so the lines cross.')

HISTORY = [   # (year, claim)
    ('1950', dict(status='verified', src=['gp', 'lava'],
                  text='Donald Dunnet files GB 703,924. Craven Walker later sees such an egg timer bubbling on a pub stove.')),
    ('1959', dict(status='verified', src=['ecw'],
                  text='As “Michael Keatering” he directs <i>Travelling Light</i>, the UK’s first naturist film on public release.')),
    ('1963', dict(status='verified', src=['lava'], text='His company, Crestworth, launches the first Astro lava lamp.')),
    ('1965', dict(status='verified', src=['lava'],
                  text='Wertheimer and Spector see it at a German trade show and buy the US rights: the Lava Lite.')),
    ('1968', dict(status='verified', src=['gp'], text='US 3,387,396 is granted to Crestworth.')),
    ('1970', dict(status='verified', src=['lava'], text='Carbon tetrachloride, banned for toxicity, leaves US lamps.')),
    ('late 1970s', dict(status='verified', src=['lava'],
                        text='Larry Haggerty buys the US rights and makes the lamps for over 30 years.')),
    ('1992', dict(status='verified', src=['mathmos'],
                  text='Crestworth, run by Granger and Mulley since 1989, becomes Mathmos, after the lake in <i>Barbarella</i>.')),
    ('1999', dict(status='verified', src=['mathmos'], text='Mathmos sells 800,000 lamps a year, up from 10,000 in 1989.')),
    ('1996', dict(status='verified', src=['lavarand', 'gp'],
                  text='Silicon Graphics files Lavarand: random numbers from pictures of lava lamps.')),
    ('2000', dict(status='verified', src=['ecw'], text='Craven Walker dies, aged 82, still a consultant to Mathmos.')),
    ('2017', dict(status='verified', src=['lavarand', 'cf'],
                  text='Cloudflare’s San Francisco lobby: a wall of about 100 lamps, a source of randomness.')),
]
HISTORY.sort(key=lambda h: (int(re.sub(r'\D', '', h[0])[:4] or 0), h[0]))

WAYS = [   # (mark, name, how, status in the level)
    ('✓', 'Forth model', 'buoyancy, heat and pooling in the level’s script', 'ships'),
    ('✓', 'Native word', 'the pair loop only, <code>lava-pairs</code> in C++', 'ships: cast1 missed frames with it in Forth'),
    ('½', 'Baked tape', f'only the {DATA["warm"]:.0f} s warm-up, run at build time', 'so the level opens mid-flow'),
    ('–', 'Jolt', 'rigid spheres pushed by buoyancy', 'not used: rigid bodies do not change shape'),
]


# ── Checks ───────────────────────────────────────────────────────────────────
def all_claims():
    for c in HEADER_CLAIMS:
        yield 'header', c
    for p in PANELS:
        for c in p['claims']:
            yield p['key'], c
    for name, c in BOTTLE_ROWS:
        yield f'bottle: {name}', c
    yield 'bottle: note', BOTTLE_NOTE
    for year, c in HISTORY:
        yield f'history: {year}', c


def source_order():
    seen = []
    for _, c in all_claims():
        for s in c['src']:
            if s not in seen:
                seen.append(s)
    return seen


def used_statuses():
    return [s for s in PRINTABLE if any(c['status'] == s for _, c in all_claims())]


def research_text():
    return RESEARCH.read_text(encoding='utf-8') if RESEARCH.exists() else ''


def check_claims():
    problems = []
    research = research_text()
    if APPROVED_LINE not in research:
        problems.append(REVIEW_PROBLEM)
    for area, c in all_claims():
        if c['status'] not in PRINTABLE:
            problems.append(f'{area}: status {c["status"]!r} cannot be printed; keep it in the research document')
        if c['status'] in ('verified', 'other-source') and not c['src']:
            problems.append(f'{area}: a {c["status"]} claim needs a source: {c["text"][:50]}')
        if c['status'] == 'ours' and not c.get('by'):
            problems.append(f'{area}: an ours claim must name what computes it: {c["text"][:50]}')
        for s in c['src']:
            if s not in SOURCES:
                problems.append(f'{area}: unknown source {s!r}')
            elif SOURCES[s]['url'] not in research:
                problems.append(f'{area}: source {s} is not in the research document')
        if not c['text'].strip():
            problems.append(f'{area}: empty claim')
    for p in PATENTS:
        if p['url'] not in research:
            problems.append(f'patent {p["number"]}: its link is not in the research document')
        if not (HERE / 'qr' / f'{p["key"]}.svg').exists():
            problems.append(f'patent {p["number"]}: qr/{p["key"]}.svg is missing (run make_qr.py)')
    return problems


# ── SVG helpers ──────────────────────────────────────────────────────────────
def esc(s):
    return html.escape(str(s), quote=True)


def T(x, y, s, size=11, anchor='start', fill=INK, weight=400, bg=WHITE, italic=False):
    TEXT_PAIRS.add((fill, bg))
    TEXT_SIZES.append(size)
    st = ' font-style="italic"' if italic else ''
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}"'
            f' font-family=\'{FONT_SANS}\'{st}>{esc(s)}</text>')


def line(x1, y1, x2, y2, col=INK, w=1.0, extra=''):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{w}" {extra}/>'


def arrow(x1, y1, x2, y2, col=INK, w=1.6):
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 7 * math.cos(a), y2 - 7 * math.sin(a)
    px, py = -math.sin(a) * 3.5, math.cos(a) * 3.5
    return (line(x1, y1, hx, hy, col, w) +
            f'<polygon points="{x2:.1f},{y2:.1f} {hx + px:.1f},{hy + py:.1f} {hx - px:.1f},{hy - py:.1f}" fill="{col}"/>')


def svg_open(w, h, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title><rect width="{w}" height="{h}" fill="{WHITE}"/>')


# ── Drawings ─────────────────────────────────────────────────────────────────
MOVES_W, MOVES_H = LEFT - 2, 142


def drawing_moves():
    """A cross-section of the globe on the model's own profile (lamp.globe_r), with the four steps beside it."""
    out = [svg_open(MOVES_W, MOVES_H, 'A lava lamp in cross-section: wax heats on the coil, rises up the middle, rests under the cap, sinks by the glass')]
    cx, top, bot = 92, 8, 116
    H = bot - top
    sc = H / 1.0

    def gx(y, side):
        return cx + side * LAMP.globe_r(y) * sc

    ys = [k / 40 for k in range(41)]
    left = [(gx(y, -1), bot - y * H) for y in ys]
    right = [(gx(y, 1), bot - y * H) for y in reversed(ys)]
    pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in left + right)
    out.append(f'<polygon points="{pts}" fill="{WATER_PALE}" stroke="{WATER}" stroke-width="1.6"/>')
    # cap and base
    out.append(f'<polygon points="{gx(1, -1):.1f},{top} {gx(1, 1):.1f},{top} {cx + 4},{top - 6} {cx - 4},{top - 6}" fill="{GOLD}"/>')
    out.append(f'<polygon points="{gx(0, -1) - 2:.1f},{bot} {gx(0, 1) + 2:.1f},{bot} {cx + 46},{MOVES_H - 4} {cx - 46},{MOVES_H - 4}" fill="{GOLD}"/>')
    out.append(f'<circle cx="{cx}" cy="{bot + 13}" r="6" fill="#ffd35a" stroke="#fff" stroke-width="1"/>')
    # pool, coil, blobs
    out.append(f'<ellipse cx="{cx}" cy="{bot - 4}" rx="{LAMP.globe_r(0.02) * sc - 2:.1f}" ry="5" fill="{WAX}"/>')
    out.append(line(cx - 22, bot - 2, cx + 22, bot - 2, '#7a6a55', 1.2, 'stroke-dasharray="3 2"'))
    for (bx, by, r) in ((cx - 4, bot - 40, 9), (cx + 6, bot - 78, 7)):
        out.append(f'<ellipse cx="{bx}" cy="{by}" rx="{r}" ry="{r * 1.3:.1f}" fill="{WAX}"/>')
    out.append(f'<ellipse cx="{cx + 2}" cy="{top + 7}" rx="14" ry="4.5" fill="{WAX_DARK}"/>')
    out.append(f'<ellipse cx="{gx(0.55, -1) + 8:.1f}" cy="{bot - 0.55 * H:.1f}" rx="5" ry="7" fill="{WAX_DARK}"/>')
    out.append(arrow(cx - 4, bot - 24, cx - 4, bot - 92, WAX_DARK, 1.6))
    out.append(arrow(gx(0.7, -1) + 5, bot - 0.82 * H, gx(0.3, -1) + 5, bot - 0.25 * H, WATER, 1.6))
    out.append(arrow(gx(0.7, 1) - 5, bot - 0.82 * H, gx(0.3, 1) - 5, bot - 0.25 * H, WATER, 1.6))
    out.append(T(cx + 16, bot + 17, 'bulb', 11, 'start', MUTED))
    # the four steps
    steps = [('1 · Heat', 'the pool on the coil warms; a tower forms and pinches off'),
             ('2 · Rise', 'warm wax is lighter than the liquid; it stretches into a teardrop'),
             ('3 · Rest and cool', 'it flattens under the cap and gives up its heat'),
             ('4 · Sink and merge', 'denser again, it slides down by the glass; the coil lets it rejoin')]
    x0 = 200
    for i, (h, s) in enumerate(steps):
        y = 22 + i * 32
        out.append(T(x0, y, h, 12, 'start', ACC, 700))
        out.append(T(x0, y + 14, s, 11, 'start', INK))
    out.append('</svg>')
    return ''.join(out)


BOTTLE_W, BOTTLE_H = 232, 150


def drawing_bottle():
    """Schematic: density against temperature for the wax and the water, crossing (no numbers: see BOTTLE_NOTE)."""
    out = [svg_open(BOTTLE_W, BOTTLE_H, 'Schematic: the wax mix is denser than the water when cold and lighter when hot')]
    X0, X1, Y0, Y1 = 30, BOTTLE_W - 8, 14, 112
    out.append(line(X0, Y0 - 4, X0, Y1, INK, 1.2) + line(X0, Y1, X1, Y1, INK, 1.2))
    out.append(T(X0 - 6, Y0 + 4, 'ρ', 13, 'end', INK, 700))
    out.append(T(X1, Y1 + 15, 'temperature →', 11, 'end', MUTED))
    out.append(line(X0, Y0 + 30, X1, Y0 + 52, WATER, 2.4))
    out.append(line(X0, Y0 + 8, X1, Y0 + 82, WAX, 2.4))
    xc = X0 + (X1 - X0) * (22 / (74 - 22))
    yc = Y0 + 30 + 22 * (xc - X0) / (X1 - X0)
    out.append(f'<circle cx="{xc:.1f}" cy="{yc:.1f}" r="4" fill="{INK}"/>')
    out.append(T(xc + 6, yc - 7, 'crossing', 11, 'start', INK, 700))
    out.append(T(X0 + 6, Y0 + 2, 'wax mix', 11, 'start', WAX_DARK, 700))
    out.append(T(X1, Y0 + 66, 'water', 11, 'end', WATER, 700))
    out.append(T(X0 + 4, Y1 + 15, 'cold: sinks', 11, 'start', INK))
    out.append(T(X0 + 4, Y1 + 30, 'hot: rises', 11, 'start', INK))
    out.append('</svg>')
    return ''.join(out)


# ── HTML ─────────────────────────────────────────────────────────────────────
def chip_html(c):
    kind = c['status']
    return f'<span class="chip {kind}">{esc(c.get("chip", STATUS_TEXT[kind]))}</span>'


def refs_html(c, num):
    return ('\u00a0<span class="ref">[' + ', '.join(str(num[s]) for s in c['src']) + ']</span>') if c['src'] else ''


def claim_html(c, num, area, tag='p'):
    return f'<{tag} class="cl" data-status="{c["status"]}" data-area="{esc(area)}">{chip_html(c)} {c["text"]}{refs_html(c, num)}</{tag}>'


def bar(i, title):
    return f'<div class="bar"><span class="no">{i:02d}</span> {esc(title)}</div>'


def panel(i, p, body, extra_class=''):
    return f'<section class="panel {extra_class}" id="panel-{p["key"]}">{bar(i, p["title"])}{body}</section>'


def claims_html(p, num):
    return '<div class="claims">' + ''.join(claim_html(c, num, p['key']) for c in p['claims']) + '</div>'


def bottle_html(num, svg):
    rows = ''.join(f'<tr><th>{esc(name)}</th><td>{claim_html(c, num, "bottle: " + name, "span")}</td></tr>' for name, c in BOTTLE_ROWS)
    return (f'<div class="split">{svg}<table class="props"><tbody>{rows}</tbody></table></div>'
            f'<div class="claims">{claim_html(BOTTLE_NOTE, num, "bottle: note")}</div>')


def hero_html(p, num):
    img = base64.b64encode((HERE / 'hero-cycles.png').read_bytes()).decode('ascii')
    return (f'<img class="hero" src="data:image/png;base64,{img}" width="260" height="390" '
            f'alt="The lava lamp clock rendered in Cycles: a gold Astro, orange wax in violet liquid, 21:47 in the holes of its base">'
            + claims_html(p, num))


def qr_inline(key, size):
    svg = (HERE / 'qr' / f'{key}.svg').read_text(encoding='ascii').strip()
    m = re.match(r'<svg xmlns="http://www.w3.org/2000/svg" width="(\d+)" height="(\d+)"', svg)
    if not m:
        raise SystemExit(f'make_poster: qr/{key}.svg is not a segno SVG (run make_qr.py)')
    w = m.group(1)
    return svg.replace(m.group(0), f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {w}" width="{size}" height="{size}" '
                                   f'shape-rendering="crispEdges" role="img" aria-label="QR code: {key}"', 1)


def patents_html(p, num):
    cards = []
    for pt in PATENTS:
        cards.append(f'<div class="pat">{qr_inline(pt["key"], 78)}<div class="pt">'
                     f'<a class="pn" href="{pt["url"]}">{pt["number"].replace(" ", chr(0xa0))}</a>'
                     f'<div class="ptitle">{esc(pt["title"])}</div>'
                     f'<div class="pwho">{esc(pt["who"])}</div>'
                     f'<div class="pwhat">{esc(pt["what"])}</div>'
                     f'<div class="pdate">{esc(pt["dates"])}</div></div></div>')
    return f'<div class="pats">{"".join(cards)}</div>' + claims_html(p, num)


def history_html(num):
    n = len(HISTORY) // 2
    cells = []
    for row in (HISTORY[:n], HISTORY[n:]):
        cells.append('<div class="hrow">' + ''.join(
            f'<div class="ev"><div class="yr">{esc(y)}</div>{claim_html(c, num, "history: " + y)}</div>' for y, c in row) + '</div>')
    return ''.join(cells)


def forth_html(p, num):
    # a line may wrap only between words: a hyphenated word (ll-frame, read-mailbox) stays whole
    code = '\n'.join(' '.join(f'<span class="nw">{esc(w)}</span>' if '-' in w else esc(w) for w in ln.split(' '))
                      for ln in forth_lines())
    return f'<pre class="code">{code}</pre>' + claims_html(p, num)


def ways_html(p, num):
    rows = ''.join(f'<tr><td class="mk">{m}</td><th>{esc(n)}</th><td>{how}</td><td class="st">{esc(st)}</td></tr>' for m, n, how, st in WAYS)
    return f'<table class="ways"><tbody>{rows}</tbody></table>' + claims_html(p, num)


def header_html(num, draft):
    claims = ''.join(claim_html(c, num, 'header') for c in HEADER_CLAIMS)
    meta = ('<div class="meta draft">REVIEW DRAFT · awaiting Will’s visual review · not for print</div>' if draft else
            '<div class="meta">World Foundry · 3D Clocks · A3 poster</div>')
    return ('<header><div class="ttl"><h1>The lava lamp</h1>'
            '<div class="sub">Two liquids that will not mix, one bulb, and a density that changes with heat: a slow convection engine, and a clock built around it</div>'
            f'{meta}</div><div class="facts">{claims}</div></header>')


def legend_html():
    items = ''.join(f'<span class="lg"><span class="chip {s}">{STATUS_TEXT[s]}</span> {LEGEND_TEXT[s]}</span>' for s in used_statuses())
    return f'<div class="legend">{items}</div>'


def footer_html(num):
    lis = []
    for s in source_order():
        d = SOURCES[s]
        lis.append(f'<li>[{num[s]}] <a href="{d["url"]}">{esc(d["cite"])}</a> · {esc(d["where"])}</li>')
    per = -(-len(lis) // 3)
    cols = ''.join(f'<ol>{"".join(lis[i * per:(i + 1) * per])}</ol>' for i in range(3))
    return (f'<footer id="panel-src">{legend_html()}<div class="srcs">{cols}</div>'
            f'<div class="note">Checked {CHECKED}; locators and what was not found: docs/reference/lava-lamp-research.md. '
            'Numbers and Forth read from wflevels/lava_lamp. Drawings original; lamp: our Cycles render. A3, 297 × 420 mm.</div></footer>')


CSS = f"""
@page {{ size: A3 portrait; margin: 0 }}
*{{ box-sizing: border-box }}
html,body{{ margin:0; background:#fff; color:{INK}; -webkit-print-color-adjust:exact; print-color-adjust:exact }}
body{{ font: 11.5px/1.3 {FONT_SANS} }}
.page{{ width:{PAGE_W_MM}mm; height:{PAGE_H_MM}mm; padding:{MARGIN_MM}mm; overflow:hidden; display:flex; flex-direction:column; gap:5px; background:#fff }}
header{{ background:{NIGHT}; color:#fff; display:flex; gap:16px; padding:9px 14px 8px; height:104px; flex:none }}
header .ttl{{ width:470px; flex:none }}
header h1{{ font-family:{FONT_SERIF}; margin:0; font-size:30pt; white-space:nowrap; line-height:1.0; font-weight:700; letter-spacing:-.01em }}
header .sub{{ color:{NIGHT_TEXT}; font-size:12.5px; line-height:1.3; margin-top:5px }}
header .meta{{ color:{NIGHT_TEXT}; font-size:11px; margin-top:4px; letter-spacing:.06em }}
header .meta.draft{{ color:#ffd9a8; font-weight:700 }}
header .facts{{ flex:1; background:#fff; color:{INK}; border-radius:5px; padding:5px 8px; overflow:hidden }}
header .facts .cl{{ margin:0 0 4px }}
.row{{ display:flex; gap:12px; flex:none }}
.col{{ display:flex; flex-direction:column; gap:6px; flex:none }}
.panel{{ overflow:hidden; border:1px solid {GRID}; flex:none; background:#fff }}
.bar{{ background:{ACC}; color:#fff; font-family:{FONT_SERIF}; font-size:12.5pt; font-weight:700; height:24px; line-height:24px; padding:0 10px; white-space:nowrap }}
.bar .no{{ color:#ffd9a8 }}
.panel svg{{ display:block }}
.claims{{ padding:2px 9px 0 }}
.cl{{ margin:0 0 3px; font-size:11px; line-height:14px }}
.ref{{ color:{MUTED}; white-space:nowrap }}
.chip{{ display:inline-block; border-radius:8px; padding:0 6px; font-size:11px; line-height:13px; font-weight:700; border:1px solid; white-space:nowrap; vertical-align:baseline }}
{''.join(f'.chip.{k}{{ color:{v[0]}; background:{v[1]}; border-color:{v[2]} }}' for k, v in CHIP.items())}
#panel-moves{{ width:{LEFT}px; height:290px }}
#panel-moves svg{{ margin:4px 0 2px }}
#panel-bottle{{ width:{LEFT}px; height:254px }}
.split{{ display:flex; gap:8px; padding:4px 6px 0 2px }}
.props{{ border-collapse:collapse; flex:1 }}
.props th{{ text-align:left; vertical-align:top; font-size:11px; line-height:14px; padding:2px 6px 3px 0; width:118px; color:{INK}; border-bottom:1px solid {GRID} }}
.props td{{ font-size:11px; line-height:14px; padding:2px 0 3px; border-bottom:1px solid {GRID} }}
.props .cl{{ margin:0 }}
#panel-hero{{ width:{RIGHT}px; height:550px }}
img.hero{{ display:block; margin:6px auto 4px; border:1px solid {GRID} }}
#panel-patents{{ width:{WIDE}px; height:250px }}
.pats{{ display:grid; grid-template-columns:repeat(3, 1fr); gap:6px 12px; padding:6px 9px 3px }}
.pat{{ display:flex; gap:8px; align-items:flex-start }}
.pat svg{{ flex:none }}
.pt{{ font-size:11px; line-height:13.5px }}
.pn{{ font-weight:700; font-size:12.5px }}
.ptitle{{ font-style:italic }}
.pwho, .pdate{{ color:{MUTED} }}
#panel-history{{ width:{WIDE}px; height:196px }}
.hrow{{ display:grid; grid-template-columns:repeat({len(HISTORY) // 2}, 1fr); gap:0 12px; padding:5px 9px 2px }}
.ev .yr{{ font-family:{FONT_SERIF}; font-weight:700; font-size:12.5px; color:{WAX_DARK}; line-height:15px }}
.ev .cl{{ margin:0 }}
#panel-forth{{ width:620px; height:248px }}
pre.code{{ margin:6px 9px 4px; padding:6px 8px; background:#1d1420; color:#f3e9f7; font: 11px/14px {FONT_MONO}; white-space:pre-wrap; border-radius:4px }}
.nw{{ white-space:nowrap }}
#panel-ways{{ width:430px; height:248px }}
.ways{{ border-collapse:collapse; margin:6px 9px 4px; width:calc(100% - 18px) }}
.ways th, .ways td{{ text-align:left; vertical-align:top; font-size:11px; line-height:14px; padding:3px 6px 4px 0; border-bottom:1px solid {GRID} }}
.ways .mk{{ font-weight:700; color:{ACC}; width:16px }}
.ways .st{{ color:{MUTED} }}
code{{ font-family:{FONT_MONO}; font-size:11px }}
footer{{ flex:1; border-top:2px solid {ACC}; padding-top:4px; display:flex; flex-direction:column; gap:3px; min-height:0 }}
.legend{{ display:flex; gap:18px; font-size:11px; line-height:14px; color:{INK} }}
.srcs{{ display:flex; gap:14px }}
.srcs ol{{ list-style:none; margin:0; padding:0; flex:1 }}
.srcs li{{ font-size:11px; line-height:13.5px; margin:0 0 2px; color:{MUTED} }}
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

UNITS = r'(?:g/cm³|kg/m³|cm|mm|km|min|°C|h|m|s|%|°)'
_NUM_UNIT = re.compile(rf'(\d)[ \u00a0]+({UNITS})(?![\w/])')
_TIMES = re.compile(r'(\d) × (\d)')
_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')


def polish_text(s):
    s = _NUM_UNIT.sub('\\1\u00a0\\2', s)
    s = _TIMES.sub('\\1\u00a0×\u00a0\\2', s)
    return _ISO.sub('\\1\u2011\\2\u2011\\3', s)


def polish(doc):
    """Keep every number with its unit and every ISO date on one line, outside tags, code and the style and script blocks."""
    parts = re.split(r'(<style>.*?</style>|<script>.*?</script>|<svg.*?</svg>|<pre.*?</pre>|<[^>]+>)', doc, flags=re.S)
    return ''.join(p if p.startswith('<') else polish_text(p) for p in parts)


SVG_FILES = {'moves': '01-moves.svg', 'bottle': '02-bottle.svg'}


def build(*, draft=False):
    """Return the poster HTML and the drawings {file name: svg}. Refuses on any claim problem; refuses an unapproved
    poster unless draft (a review draft for Will, marked as one)."""
    problems = check_claims()
    if draft:
        problems = [p for p in problems if p != REVIEW_PROBLEM]
    if problems:
        raise SystemExit('make_poster: refusing to build:\n  ' + '\n  '.join(problems))
    TEXT_PAIRS.clear()
    TEXT_SIZES.clear()
    num = {s: i + 1 for i, s in enumerate(source_order())}
    P = {p['key']: p for p in PANELS}
    svgs = {'moves': drawing_moves(), 'bottle': drawing_bottle()}
    row1 = ('<div class="row"><div class="col">'
            + panel(1, P['moves'], svgs['moves'] + claims_html(P['moves'], num))
            + panel(2, P['bottle'], bottle_html(num, svgs['bottle']))
            + '</div>' + panel(3, P['hero'], hero_html(P['hero'], num)) + '</div>')
    row2 = panel(4, P['patents'], patents_html(P['patents'], num))
    row3 = panel(5, P['history'], history_html(num))
    row4 = ('<div class="row">' + panel(6, P['forth'], forth_html(P['forth'], num))
            + panel(7, P['ways'], ways_html(P['ways'], num)) + '</div>')
    body_attr = ' data-draft="1"' if draft else ''
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>The lava lamp</title>'
           f'<style>{CSS}</style></head><body{body_attr}><div class="page">{header_html(num, draft)}{row1}{row2}{row3}{row4}'
           f'{footer_html(num)}</div>{FIT_SCRIPT}</body></html>')
    return polish(doc), {SVG_FILES[k]: v for k, v in svgs.items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--draft', action='store_true', help='build a marked review draft while the visual review is pending')
    ap.add_argument('--out-dir', type=Path, default=HERE)
    args = ap.parse_args(argv)
    doc, svgs = build(draft=args.draft)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, svg in svgs.items():
        (args.out_dir / name).write_text(svg + '\n', encoding='utf-8')
    (args.out_dir / 'poster.html').write_text(doc, encoding='utf-8')
    print(f'poster.html{" (review draft)" if args.draft else ""}: {len(PANELS)} panels, {sum(1 for _ in all_claims())} claims, '
          f'{len(source_order())} sources, {len(PATENTS)} patents')
    return 0


if __name__ == '__main__':
    sys.exit(main())
