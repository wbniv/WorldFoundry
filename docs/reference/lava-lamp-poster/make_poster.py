#!/usr/bin/env python3
"""Build the lava lamp poster: one A3 portrait page (297 x 420 mm), seven panels, every claim chipped.

    python3 docs/reference/lava-lamp-poster/make_poster.py [--draft]
    python3 docs/reference/lava-lamp-poster/export_poster.py
    scripts/in-linux-container.sh python3 -m pytest tests/test_lava_lamp_poster.py -q

Plan: docs/plans/2026-11-26-lava-lamp.md (D10, Q7, Q8, Phase P). The research comes first:
docs/reference/lava-lamp-research.md gives each source's locator and what was not found. Every claim below lives in
HEADER_CLAIMS / PANELS with its status and its sources, and `check_claims()` refuses to build when a claim lacks
either, when a source's link is not in the research document, or (without --draft) while the research does not say
"Poster visual review: approved". A draft is marked as one on the page and exports to a review-draft PDF name.

The statuses are the build gate only: the page prints no status tag (Will, 2026-11-27: "remove (verify) and (ours)
tags"). A sourced sentence ends in its superscript source numbers, and the footer says an unnumbered one is ours.
The Forth column prints shipped definitions pretty-printed by `pretty()`: whitespace is the only change.

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
GAP = 10                        # between panels
HERO_COL, MID, SIDE = 352, 398, 292   # three columns: the hero, the text, the Forth (352 + 398 + 292 + 2 gaps = 1062)
HERO_W = 344                    # the render's printed width, px (2:3)
BODY_H = 1304                   # the three columns, below the header and above the sources
ROW1_H = 712                    # the hero beside panels 01 and 02
MOVES_PANEL_H = 366
HIST_H = 250
WAYS_H = 218
CODE_COLS = 39                  # characters in a line of the pretty-printed Forth
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

FORTH_WORDS = ('ll-env', 'll-heat0', 'll-tick')
FORTH_NOTES = {   # word: (stack effect, what it does); printed beside the code, never inside it
    'll-env': ('( y -- T )', 'the liquid’s temperature at height y'),
    'll-heat0': ('( -- )', 'blob 0, one step: heat, pool, buoy, drift'),
    'll-tick': ('( -- )', 'the director, every frame'),
}


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
    'gp': dict(cite='Google Patents, the six numbers in panel 05', url='https://patents.google.com/',
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
             text=f'Copied from the level’s director, which a generator writes from the Python model in 32-bit floats; a test runs '
                  f'both step for step in the real zForth VM. Blob <i>i</i> lives in mailboxes {D["cell0"]}&nbsp;+&nbsp;{D["stride"]}<i>i</i>; '
                  f'a frame runs whole 1/30 s steps, at most {D["steps"]}. Only the line breaks are ours.'),
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
                   text='The idea, not data: the wax’s density falls faster with heat than the water’s.')

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
MOVES_W, MOVES_H = MID - 2, 174


def drawing_moves():
    """A cross-section of the globe on the model's own profile (lamp.globe_r), with the four steps beside it."""
    out = [svg_open(MOVES_W, MOVES_H, 'A lava lamp in cross-section: wax heats on the coil, rises up the middle, rests under the cap, sinks by the glass')]
    cx, top, bot = 66, 14, 142
    H = bot - top
    sc = H / 1.0

    def gx(y, side):
        return cx + side * LAMP.globe_r(y) * sc

    ys = [k / 40 for k in range(41)]
    left = [(gx(y, -1), bot - y * H) for y in ys]
    right = [(gx(y, 1), bot - y * H) for y in reversed(ys)]
    pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in left + right)
    out.append(f'<polygon points="{pts}" fill="{WATER_PALE}" stroke="{WATER}" stroke-width="1.6"/>')
    out.append(f'<polygon points="{gx(1, -1):.1f},{top} {gx(1, 1):.1f},{top} {cx + 4},{top - 10} {cx - 4},{top - 10}" fill="{GOLD}"/>')
    out.append(f'<polygon points="{gx(0, -1) - 2:.1f},{bot} {gx(0, 1) + 2:.1f},{bot} {cx + 52},{MOVES_H - 6} {cx - 52},{MOVES_H - 6}" fill="{GOLD}"/>')
    out.append(f'<circle cx="{cx}" cy="{bot + 15}" r="6" fill="#ffd35a" stroke="#fff" stroke-width="1"/>')
    out.append(f'<ellipse cx="{cx}" cy="{bot - 5}" rx="{LAMP.globe_r(0.02) * sc - 3:.1f}" ry="6" fill="{WAX}"/>')
    out.append(line(cx - 28, bot - 2, cx + 28, bot - 2, '#7a6a55', 1.2, 'stroke-dasharray="3 2"'))
    for (bx, by, r) in ((cx - 5, bot - 52, 11), (cx + 7, bot - 102, 9)):
        out.append(f'<ellipse cx="{bx}" cy="{by}" rx="{r}" ry="{r * 1.3:.1f}" fill="{WAX}"/>')
    out.append(f'<ellipse cx="{cx + 2}" cy="{top + 9}" rx="18" ry="5.5" fill="{WAX_DARK}"/>')
    out.append(f'<ellipse cx="{gx(0.55, -1) + 9:.1f}" cy="{bot - 0.55 * H:.1f}" rx="6" ry="9" fill="{WAX_DARK}"/>')
    out.append(arrow(cx - 5, bot - 30, cx - 5, bot - 122, WAX_DARK, 1.6))
    out.append(arrow(gx(0.7, -1) + 6, bot - 0.82 * H, gx(0.3, -1) + 6, bot - 0.25 * H, WATER, 1.6))
    out.append(arrow(gx(0.7, 1) - 6, bot - 0.82 * H, gx(0.3, 1) - 6, bot - 0.25 * H, WATER, 1.6))
    out.append(T(cx + 18, bot + 19, 'bulb', 11, 'start', MUTED))
    steps = [('1 · Heat', 'the pool on the coil warms;', 'a tower forms and pinches off'),
             ('2 · Rise', 'lighter than the liquid, it', 'stretches into a teardrop'),
             ('3 · Rest and cool', 'it flattens under the cap', 'and gives up its heat'),
             ('4 · Sink and merge', 'denser again, it slides down', 'the glass and rejoins the pool')]
    x0 = 150
    for i, (h, a, b) in enumerate(steps):
        y = 17 + i * 42
        out.append(T(x0, y, h, 12, 'start', ACC, 700))
        out.append(T(x0, y + 14, a, 11, 'start', INK))
        out.append(T(x0, y + 28, b, 11, 'start', INK))
    out.append('</svg>')
    return ''.join(out)


BOTTLE_W, BOTTLE_H = MID - 2, 92


def drawing_bottle():
    """Schematic: density against temperature for the wax and the water, crossing (no numbers: see BOTTLE_NOTE)."""
    out = [svg_open(BOTTLE_W, BOTTLE_H, 'Schematic: the wax mix is denser than the water when cold and lighter when hot')]
    X0, X1, Y0, Y1 = 26, 236, 10, 74
    out.append(line(X0, Y0 - 4, X0, Y1, INK, 1.2) + line(X0, Y1, X1, Y1, INK, 1.2))
    out.append(T(X0 - 6, Y0 + 6, 'ρ', 13, 'end', INK, 700))
    out.append(T(X1, Y1 + 15, 'temperature →', 11, 'end', MUTED))
    out.append(line(X0, Y0 + 20, X1, Y0 + 36, WATER, 2.4))
    out.append(line(X0, Y0 + 4, X1, Y0 + 56, WAX, 2.4))
    t = 16 / (52 - 16)
    xc, yc = X0 + (X1 - X0) * t, Y0 + 20 + 16 * t
    out.append(f'<circle cx="{xc:.1f}" cy="{yc:.1f}" r="4" fill="{INK}"/>')
    out.append(T(xc + 6, yc - 7, 'crossing', 11, 'start', INK, 700))
    out.append(T(X0 + 6, Y0 + 2, 'wax mix', 11, 'start', WAX_DARK, 700))
    out.append(T(X1, Y0 + 32, 'water', 11, 'end', WATER, 700))
    out.append(T(250, 30, 'cold: the wax', 11, 'start', INK))
    out.append(T(250, 44, 'is denser, sinks', 11, 'start', INK))
    out.append(T(250, 62, 'hot: lighter,', 11, 'start', INK))
    out.append(T(250, 76, 'it rises', 11, 'start', INK))
    out.append('</svg>')
    return ''.join(out)


# ── The Forth, pretty-printed: whitespace is the only change ─────────────────
BREAK_AFTER = ('write-mailbox', 'write-actor-mailbox')


def pretty(definition: str, width: int = CODE_COLS) -> list:
    """Lay one shipped definition out as lines: the name on its own line, `if` opening an indented block, `else` and
    `then` at the block's own indent, a break after each store, and a wrap before `width` columns. Only whitespace
    changes: ' '.join(lines joined) == the definition (test_the_forth_on_the_poster_is_the_shipped_script)."""
    toks = definition.split()
    assert toks[0] == ':' and toks[-1] == ';', definition[:40]
    out, buf, depth = [f': {toks[1]}'], [], 1

    def flush():
        if buf:
            out.append('  ' * depth + ' '.join(buf))
            buf.clear()

    units = []                      # a cell number stays with its read-mailbox or write-mailbox
    for t in toks[2:-1]:
        if t in ('read-mailbox', 'write-mailbox') and units and re.fullmatch(r'\d+', units[-1]):
            units[-1] += ' ' + t
        else:
            units.append(t)
    for t in units:
        if t in ('else', 'then'):
            flush()
            depth -= 1
            out.append('  ' * depth + t)
            if t == 'else':
                depth += 1
            continue
        if buf and len('  ' * depth + ' '.join(buf + [t])) > width:
            flush()
        buf.append(t)
        if t == 'if':
            flush()
            depth += 1
        elif t.split()[-1] in BREAK_AFTER:
            flush()
    if buf and len('  ' * depth + ' '.join(buf + [';'])) <= width:
        buf.append(';')
        flush()
    else:
        flush()
        out.append(';')
    return out


# ── HTML ─────────────────────────────────────────────────────────────────────
def refs_html(c, num):
    """The only printed trace of a claim: its source numbers, superscript. Unnumbered statements are ours (the footer says so)."""
    return ('<sup class="ref">' + ','.join(str(num[s]) for s in c['src']) + '</sup>') if c['src'] else ''


def claim_html(c, num, area, tag='p'):
    return f'<{tag} class="cl" data-status="{c["status"]}" data-area="{esc(area)}">{c["text"]}{refs_html(c, num)}</{tag}>'


def bar(i, title):
    return f'<div class="bar"><span class="no">{i:02d}</span> {esc(title)}</div>'


def panel(i, p, body):
    return f'<section class="panel" id="panel-{p["key"]}">{bar(i, p["title"])}{body}</section>'


def claims_html(p, num):
    return '<div class="claims">' + ''.join(claim_html(c, num, p['key']) for c in p['claims']) + '</div>'


def bottle_html(num, svg):
    rows = ''.join(f'<tr><th>{esc(name)}</th><td>{claim_html(c, num, "bottle: " + name, "span")}</td></tr>' for name, c in BOTTLE_ROWS)
    return (f'{svg}<table class="props"><tbody>{rows}</tbody></table>'
            f'<div class="claims">{claim_html(BOTTLE_NOTE, num, "bottle: note")}</div>')


def hero_html(p, num):
    img = base64.b64encode((HERE / 'hero-cycles.png').read_bytes()).decode('ascii')
    return (f'<img class="hero" src="data:image/png;base64,{img}" width="{HERO_W}" height="{HERO_W * 3 // 2}" '
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
        cards.append(f'<div class="pat">{qr_inline(pt["key"], 76)}<div class="pt">'
                     f'<a class="pn" href="{pt["url"]}">{pt["number"].replace(" ", chr(0xa0))}</a>'
                     f'<div class="ptitle">{esc(pt["title"])}</div>'
                     f'<div class="pwho">{esc(pt["who"])}</div>'
                     f'<div class="pwhat">{esc(pt["what"])}</div>'
                     f'<div class="pdate">{esc(pt["dates"])}</div></div></div>')
    return f'<div class="pats">{"".join(cards)}</div>' + claims_html(p, num)


def history_html(num):
    return '<div class="hgrid">' + ''.join(
        f'<div class="ev"><div class="yr">{esc(y)}</div>{claim_html(c, num, "history: " + y)}</div>' for y, c in HISTORY) + '</div>'


def forth_html(p, num):
    blocks = []
    for word, ln in zip(FORTH_WORDS, forth_lines()):
        effect, what = FORTH_NOTES[word]
        body = '\n'.join(esc(x) for x in pretty(ln))
        blocks.append(f'<div class="fw"><div class="fh"><span class="fwhat">{esc(what)}</span><span class="fx">{esc(effect)}</span></div>'
                      f'<pre class="code" data-word="{word}">{body}</pre></div>')
    return ''.join(blocks) + claims_html(p, num)


def ways_html(p, num):
    rows = ''.join(f'<tr><td class="mk">{m}</td><td><b>{esc(n)}</b>: {how} <span class="st">({esc(st)})</span></td></tr>' for m, n, how, st in WAYS)
    return f'<table class="ways"><tbody>{rows}</tbody></table>' + claims_html(p, num)


def header_html(num, draft):
    claims = ''.join(claim_html(c, num, 'header') for c in HEADER_CLAIMS)
    meta = ('<div class="meta draft">REVIEW DRAFT · awaiting Will’s visual review · not for print</div>' if draft else
            '<div class="meta">World Foundry · 3D Clocks · A3 poster</div>')
    return ('<header><div class="ttl"><h1>The lava lamp</h1>'
            '<div class="sub">Two liquids that will not mix, one bulb, and a density that changes with heat: a slow convection engine, and a clock built around it</div>'
            f'{meta}</div><div class="facts">{claims}</div></header>')


def footer_html(num):
    lis = []
    for s in source_order():
        d = SOURCES[s]
        lis.append(f'<li><sup>{num[s]}</sup> <a href="{d["url"]}">{esc(d["cite"])}</a></li>')
    per = -(-len(lis) // 3)
    cols = ''.join(f'<ol>{"".join(lis[i * per:(i + 1) * per])}</ol>' for i in range(3))
    return (f'<footer id="panel-src"><div class="srcs">{cols}</div>'
            f'<div class="note">A superscript number is the source of the sentence it ends; a sentence without one is ours (the level, its model, its design). '
            f'Checked {CHECKED}; locators: docs/reference/lava-lamp-research.md. Drawings original; lamp: our Cycles render. A3, 297 × 420 mm.</div></footer>')


CSS = f"""
@page {{ size: A3 portrait; margin: 0 }}
*{{ box-sizing: border-box }}
html,body{{ margin:0; background:#fff; color:{INK}; -webkit-print-color-adjust:exact; print-color-adjust:exact }}
body{{ font: 11.5px/1.3 {FONT_SANS} }}
.page{{ width:{PAGE_W_MM}mm; height:{PAGE_H_MM}mm; padding:{MARGIN_MM}mm; overflow:hidden; display:flex; flex-direction:column; gap:6px; background:#fff }}
header{{ background:{NIGHT}; color:#fff; display:flex; gap:16px; padding:9px 14px 8px; height:104px; flex:none }}
header .ttl{{ width:470px; flex:none }}
header h1{{ font-family:{FONT_SERIF}; margin:0; font-size:30pt; white-space:nowrap; line-height:1.0; font-weight:700; letter-spacing:-.01em }}
header .sub{{ color:{NIGHT_TEXT}; font-size:12.5px; line-height:1.3; margin-top:5px }}
header .meta{{ color:{NIGHT_TEXT}; font-size:11px; margin-top:4px; letter-spacing:.06em }}
header .meta.draft{{ color:#ffd9a8; font-weight:700 }}
header .facts{{ flex:1; background:#fff; color:{INK}; border-radius:5px; padding:6px 9px; overflow:hidden }}
header .facts .cl{{ margin:0 0 4px }}
.body{{ display:flex; gap:{GAP}px; flex:none; height:{BODY_H}px }}
.main{{ width:{HERO_COL + GAP + MID}px; display:flex; flex-direction:column; gap:{GAP}px; flex:none }}
.row{{ display:flex; gap:{GAP}px; flex:none }}
.col{{ display:flex; flex-direction:column; gap:{GAP}px; flex:none }}
.side{{ width:{SIDE}px; display:flex; flex-direction:column; gap:{GAP}px; flex:none }}
.panel{{ overflow:hidden; border:1px solid {GRID}; flex:none; background:#fff }}
.bar{{ background:{ACC}; color:#fff; font-family:{FONT_SERIF}; font-size:12.5pt; font-weight:700; height:24px; line-height:24px; padding:0 10px; white-space:nowrap }}
.bar .no{{ color:#ffd9a8 }}
.panel svg{{ display:block }}
.claims{{ padding:3px 9px 0 }}
.cl{{ margin:0 0 4px; font-size:11px; line-height:14px }}
sup, .ref{{ font-size:11px; line-height:0; color:{ACC}; font-weight:700; vertical-align:super; padding-left:1px }}
#panel-hero{{ width:{HERO_COL}px; height:{ROW1_H}px }}
img.hero{{ display:block; margin:8px auto 6px; border:1px solid {GRID} }}
#panel-moves{{ width:{MID}px; height:{MOVES_PANEL_H}px }}
#panel-moves svg{{ margin:6px 0 2px }}
#panel-bottle{{ width:{MID}px; height:{ROW1_H - MOVES_PANEL_H - GAP}px }}
#panel-bottle svg{{ margin:6px 0 0 }}
.props{{ border-collapse:collapse; margin:2px 9px 0; width:calc(100% - 18px) }}
.props th{{ text-align:left; vertical-align:top; font-size:11px; line-height:14px; padding:2px 6px 3px 0; width:96px; color:{INK}; border-bottom:1px solid {GRID} }}
.props td{{ font-size:11px; line-height:14px; padding:2px 0 3px; border-bottom:1px solid {GRID} }}
.props .cl{{ margin:0 }}
#panel-history{{ width:{HERO_COL + GAP + MID}px; height:{HIST_H}px }}
.hgrid{{ display:grid; grid-template-columns:repeat(4, 1fr); gap:5px 14px; padding:6px 9px 2px }}
.ev .yr{{ font-family:{FONT_SERIF}; font-weight:700; font-size:12.5px; color:{WAX_DARK}; line-height:15px }}
.ev .cl{{ margin:0 }}
#panel-patents{{ width:{HERO_COL + GAP + MID}px; height:{BODY_H - ROW1_H - HIST_H - 2 * GAP}px }}
.pats{{ display:grid; grid-template-columns:repeat(2, 1fr); gap:7px 14px; padding:7px 9px 3px }}
.pat{{ display:flex; gap:8px; align-items:flex-start }}
.pat svg{{ flex:none }}
.pt{{ font-size:11px; line-height:13.5px }}
.pn{{ font-weight:700; font-size:12.5px }}
.ptitle{{ font-style:italic }}
.pwho, .pdate{{ color:{MUTED} }}
#panel-forth{{ width:{SIDE}px; height:{BODY_H - WAYS_H - GAP}px }}
.fw{{ margin:4px 8px 0 }}
.fh{{ display:flex; justify-content:space-between; gap:6px; font-size:11px; line-height:14px; color:{MUTED} }}
.fh .fx{{ font-family:{FONT_MONO}; color:{ACC}; white-space:nowrap }}
pre.code{{ margin:1px 0 0; padding:4px 7px; background:#1d1420; color:#f3e9f7; font: 11px/13.5px {FONT_MONO}; white-space:pre; border-radius:4px; overflow:hidden }}
#panel-forth .claims{{ padding-top:5px }}
#panel-ways{{ width:{SIDE}px; height:{WAYS_H}px }}
.ways{{ border-collapse:collapse; margin:5px 9px 2px; width:calc(100% - 18px) }}
.ways td{{ text-align:left; vertical-align:top; font-size:11px; line-height:14px; padding:2px 4px 3px 0; border-bottom:1px solid {GRID} }}
.ways .mk{{ font-weight:700; color:{ACC}; width:14px }}
.ways .st{{ color:{MUTED} }}
code{{ font-family:{FONT_MONO}; font-size:11px }}
footer{{ flex:1; border-top:2px solid {ACC}; padding-top:4px; display:flex; flex-direction:column; gap:3px; min-height:0 }}
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
    row1 = ('<div class="row">' + panel(1, P['hero'], hero_html(P['hero'], num)) + '<div class="col">'
            + panel(2, P['moves'], svgs['moves'] + claims_html(P['moves'], num))
            + panel(3, P['bottle'], bottle_html(num, svgs['bottle'])) + '</div></div>')
    main = ('<div class="main">' + row1 + panel(4, P['history'], history_html(num))
            + panel(5, P['patents'], patents_html(P['patents'], num)) + '</div>')
    side = ('<div class="side">' + panel(6, P['forth'], forth_html(P['forth'], num))
            + panel(7, P['ways'], ways_html(P['ways'], num)) + '</div>')
    rows = f'<div class="body">{main}{side}</div>'
    body_attr = ' data-draft="1"' if draft else ''
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>The lava lamp</title>'
           f'<style>{CSS}</style></head><body{body_attr}><div class="page">{header_html(num, draft)}{rows}'
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
