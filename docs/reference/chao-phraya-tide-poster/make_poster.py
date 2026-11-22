#!/usr/bin/env python3
"""Build the Bangkok tide poster: one A3 portrait page (297 x 420 mm), eight panels, every claim chipped.

    bash wflevels/tide_harbour/tide_fit/fetch_sources.sh        # once: the Navy's tables, in ~/tmp/chao-phraya-tide
    python3 docs/reference/chao-phraya-tide-poster/make_poster.py
    python3 docs/reference/chao-phraya-tide-poster/export_poster.py
    python3 -m pytest -q tests/test_poster_chao_phraya_tide.py

Plan: docs/plans/2026-11-21-tide-harbour-clock.md (D11). The research comes first: docs/reference/chao-phraya-tide-research.md
gives each source's locator and what was not found. Every claim below lives in HEADER_CLAIMS / PANELS with its status chip
and its sources, and `check_claims()` refuses to build when a claim lacks either. The numbers are not typed here: they are
read from wflevels/tide_harbour/tide_constants.json and time_zone_check.json (written by the fit scripts) and from the Navy's
printed table. Writes poster.html and the eight editable SVG panels (01-days.svg ... 08-harbour.svg).
"""
from __future__ import annotations

import base64
import cmath
import datetime as dt
import html
import json
import math
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIT = REPO / 'wflevels' / 'tide_harbour'
sys.path.insert(0, str(FIT / 'tide_fit'))

CACHE = Path(os.environ.get('CHAO_PHRAYA_TIDE_CACHE', Path.home() / 'tmp' / 'chao-phraya-tide'))
CHECKED = '2026-11-21'

# ── Page ─────────────────────────────────────────────────────────────────────
PAGE_W_MM, PAGE_H_MM, MARGIN_MM = 297, 420, 8
HALF = 524                      # panel width, px (two panels and a 13 px gap fill the page)
SVG_H = 150                     # drawing height in every panel
MIN_PX = 11.0                   # 8.25 pt: nothing on the poster is set smaller

INK, MUTED, GRID, WHITE = '#1d2733', '#55636f', '#d9e0e6', '#ffffff'
NAVY, NAVY_TEXT, ACC = '#0b2a43', '#c9dceb', '#0f6f86'
SEA, SEA_PALE, CORAL = '#2c5d8a', '#bcd3e6', '#c2410c'
CHIP = {   # kind: (text, fill, edge)
    'verified': ('#0f5f30', '#e3f4ea', '#1f8a4c'),
    'other-source': ('#6a2a94', '#f1e6fb', '#8a44c0'),
    'ours': ('#1b46b3', '#e4ecff', '#2b5fd9'),
    'unverified': ('#7a4500', '#fff2d9', '#b26a00'),
}
STATUS_TEXT = {'verified': 'verified', 'other-source': 'other source', 'ours': 'ours (measured)', 'unverified': 'unverified'}
LEGEND_TEXT = {
    'verified': 'a source was read and says this of this station or river',
    'other-source': 'a source was read; it is about a model or another place',
    'ours': 'computed by us from the sources (“design” and “limit”: our own statements)',
}
PRINTABLE = ('verified', 'other-source', 'ours')
FONT_SANS = '"Noto Sans","DejaVu Sans",sans-serif'
FONT_SERIF = '"Noto Serif","DejaVu Serif",serif'

TEXT_PAIRS = set()              # (foreground, background) of every SVG text: the contrast test reads it
TEXT_SIZES = []                 # every SVG font size (px)


# ── The data: read, never typed ──────────────────────────────────────────────
def load_data():
    try:
        const = json.loads((FIT / 'tide_constants.json').read_text())
        tz = json.loads((FIT / 'time_zone_check.json').read_text())
        turns = json.loads((FIT / 'turning_points.json').read_text())
    except FileNotFoundError as e:
        raise SystemExit(f'make_poster: {e.filename} is missing: run wflevels/tide_harbour/tide_fit/make_constants.py, check_time_zone.py and count_turns.py')
    if not (CACHE / 'HD2026.pdf').exists():
        raise SystemExit(f'make_poster: {CACHE / "HD2026.pdf"} is missing: run wflevels/tide_harbour/tide_fit/fetch_sources.sh')
    from parse_hd import parse
    return const, tz, turns, parse(str(CACHE / 'HD2026.pdf'), 2026)


CONST, TZ, TURNS, EVENTS = load_data()
TURNS_2026 = TURNS['years']['2026']
EPOCH = dt.datetime(2026, 1, 1)
WAVE = {c['name']: c for c in CONST['constituents']}
VAL = CONST['validation_height_error_at_listed_events']
STATS = CONST['table_stats']['2026']
BY_N = CONST['error_vs_constituents_fitted_2026_scored_2027']
Z0 = CONST['z0_m']


def hours_since_epoch(when):
    return (when - EPOCH).total_seconds() / 3600.0


def wave_at(name, t):
    c = WAVE[name]
    return c['amp_m'] * math.cos(2 * math.pi * (c['cycles_per_hour'] * t + c['phase_rev']))


def tide(when):
    t = hours_since_epoch(when)
    return Z0 + sum(wave_at(n, t) for n in WAVE)


def amp_cm(name):
    return WAVE[name]['amp_m'] * 100


def period_h(name):
    return 360.0 / WAVE[name]['speed_deg_per_h']


FORM_FACTOR = (WAVE['K1']['amp_m'] + WAVE['O1']['amp_m']) / (WAVE['M2']['amp_m'] + WAVE['S2']['amp_m'])
SPRING_NEAP_DAYS = 1.0 / abs(WAVE['M2']['cycles_per_hour'] - WAVE['S2']['cycles_per_hour']) / 24.0
TZ_BEST = TZ['mismatch_at_best_min']
TZ_ZERO = TZ['mismatch_at_zero_min']
D2026, D2027 = VAL['fitted_2026_scored_on_2027'], VAL['fitted_2027_scored_on_2026']
IN_SAMPLE = CONST['shipped_fit_in_sample']
TIME_ERR = VAL['fitted_2026_time_error_on_2027']
DAYS = STATS['days_by_event_count']
OTHER_DAYS = STATS['days'] - DAYS['2'] - DAYS['4']

# ── Sources (numbered by first use) ──────────────────────────────────────────
SOURCES = {
    'navy': dict(cite='Royal Thai Navy Hydrographic Department, predicted tides for 2026 and 2027, station HD (Royal Thai Navy Headquarters)',
                 url='https://hydro.navy.mi.th/sevicetide', where='one PDF per station per year; heights above the lowest low water; the header gives the position',
                 scope='Bangkok, on the Chao Phraya'),
    'iho': dict(cite='IHO North Indian Ocean Hydrographic Commission, 23rd meeting: Thailand national report (2024)',
                url='https://iho.int/uploads/user/Inter-Regional%20Coordination/RHC/NIOHC/NIOHC23/NIOHC23-8.1I_2024_National%20Report%20Thailand.pdf',
                where='the paragraph on tide tables', scope='Thailand, 29 sites'),
    'gloss': dict(cite='GLOSS, Tidal work in Thailand, Hydrographic Department (2001)',
                  url='https://gloss-sealevel.org/sites/gloss/files/publications/documents/thailand_2001.pdf',
                  where='sections 2 and 3', scope='Thailand'),
    'noaa': dict(cite='NOAA Tides and Currents, About Harmonic Constituents',
                 url='https://tidesandcurrents.noaa.gov/about_harmonic_constituents.html',
                 where='the prediction formula; the M2 and S2 examples', scope='general theory'),
    'coops3': dict(cite='NOAA, NOS CO-OPS 3: Tidal Analysis and Predictions',
                   url='https://tidesandcurrents.noaa.gov/publications/Tidal_Analysis_and_Predictions.pdf',
                   where='Tables 3.2 and A.2: constituent speeds', scope='general theory'),
    'aung': dict(cite='Aungsakul, Jaroensutasinee and Jaroensutasinee 2011, Walailak J. Sci. Tech. 4(1) 95-109',
                 url='https://wjst.wu.ac.th/index.php/wjst/article/view/128', where='Table 3 and the form-factor rule',
                 scope='a numerical model of 21 stations'),
    'glosshb': dict(cite='GLOSS Station Handbook, station 39 Ko Lak',
                    url='https://www.bodc.ac.uk/resources/inventories/gloss_handbook/stations/39/',
                    where='station information sheet: time zone', scope='Ko Lak, Thailand'),
    'psmsl': dict(cite='PSMSL station 287, Bangkok Bar',
                  url='https://psmsl.org/data/obtaining/stations/287.php', where='station page: time span, data authority, warning',
                  scope='Bangkok Bar, at the river mouth'),
}

# ── Claims. status: verified | other-source | ours. A verified or other-source claim needs sources; an ours claim names
#    the script that computes it in `by`. Unconfirmed claims stay in the research document and never reach this list.
HEADER_CLAIMS = [
    dict(status='verified', src=['navy'],
         text='Station HD, Royal Thai Navy Headquarters, 13° 44′ 36″ N 100° 29′ 25″ E, on the river inside Bangkok. Heights: metres above the lowest low water.'),
    dict(status='verified', src=['navy', 'iho'],
         text='The Navy posts every day’s predicted highs and lows. It says its constants come from one year of gauge readings.'),
    dict(status='ours', src=[], by='make_constants.py',
         text=f'2026 lists {STATS["events"]} highs and lows between {STATS["min_m"]:.2f} m and {STATS["max_m"]:.2f} m. '
              f'A typical day swings {STATS["daily_range_median_m"]:.2f} m; the largest swing is {STATS["daily_range_max_m"]:.2f} m.'),
]

PANELS = [
    dict(key='days', title='Two highs a day, or only one', claims=[
        dict(status='ours', src=[], by='make_constants.py',
             text=f'Of {STATS["days"]} days in 2026, {DAYS["4"]} list two highs and two lows, {DAYS["2"]} list one of each, and {OTHER_DAYS} list one or three events.'),
        dict(status='ours', src=[], by='make_constants.py',
             text=f'Where a day lists one high there is a flat shoulder where a second would be. The table lists only true tops and bottoms, so events can be '
                  f'{STATS["max_gap_between_events_h"]:.0f} hours apart.'),
        dict(status='other-source', src=['aung'],
             text='A form factor (K1 + O1) ÷ (M2 + S2) from 0.25 to 1.5 makes a tide “mixed, mainly semidiurnal”. That paper’s model gives this station 1.06.'),
        dict(status='ours', src=[], by='make_constants.py',
             text=f'Our fit gives {FORM_FACTOR:.2f}: the same class.'),
    ]),
    dict(key='waves', title='A tide is a sum of waves', claims=[
        dict(status='verified', src=['noaa'],
             text='A prediction adds cosine curves, <i>h = Ho + Σ f·H·cos[a·t + (V0+u) − K]</i>, one for each cause. <i>a</i> is the cause’s speed.'),
        dict(status='verified', src=['noaa'],
             text='M2, the Moon’s main effect, makes two peaks every 24 hours 50 minutes. S2, the Sun’s, makes two every 24 hours.'),
        dict(status='ours', src=['coops3'], by='make_constants.py',
             text=f'K1 {amp_cm("K1"):.1f} cm ({period_h("K1"):.2f} h), M2 {amp_cm("M2"):.1f} cm ({period_h("M2"):.2f} h), O1 {amp_cm("O1"):.1f} cm '
                  f'({period_h("O1"):.2f} h), S2 {amp_cm("S2"):.1f} cm ({period_h("S2"):.2f} h): the four largest of 64. Periods come from NOAA’s speeds.'),
    ]),
    dict(key='springneap', title='Spring and neap tides', claims=[
        dict(status='ours', src=['coops3'], by='make_constants.py',
             text=f'M2 and S2 drift in and out of step every {SPRING_NEAP_DAYS:.2f} days, the gap between their speeds.'),
        dict(status='ours', src=[], by='make_constants.py',
             text=f'Added, they swing in amplitude from {amp_cm("M2") + amp_cm("S2"):.0f} cm (spring) to {abs(amp_cm("M2") - amp_cm("S2")):.0f} cm (neap).'),
    ]),
    dict(key='year', title='A year of high and low water', claims=[
        dict(status='ours', src=[], by='make_constants.py',
             text=f'The highest high and lowest low of each day of 2026, {STATS["min_m"]:.2f} m to {STATS["max_m"]:.2f} m. The middle of our fit is {Z0:.2f} m.'),
        dict(status='ours', src=[], by='make_constants.py',
             text=f'A yearly wave of {amp_cm("Sa"):.0f} cm lifts and lowers the mean level. In a river it mixes the sea’s season with the river’s flow; two years cannot separate them.'),
        dict(status='verified', src=['psmsl'],
             text='At the river mouth, Bangkok Bar has monthly means from 1926. PSMSL flags them “not research quality data”.'),
    ]),
    dict(key='method', title='From a table to constants', claims=[
        dict(status='verified', src=['iho', 'gloss'],
             text='The Navy’s own constants are not published. It describes constants from one year of observations, and 112 constituents.'),
        dict(status='ours', src=[], by='make_constants.py',
             text='We fit its published highs and lows. At each event the height equals the listed height and the slope is zero, which is linear in the unknowns: '
                  f'one least squares finds all {CONST["n_constituents"]} waves from 171 candidates.'),
        dict(status='ours', src=['coops3'], by='constituents.py',
             text='The 55 standard candidates use astronomical speeds that match NOAA’s table to 1e-7 degrees an hour; the rest are sums and differences a river makes.'),
    ]),
    dict(key='accuracy', title='How good is it?', claims=[
        dict(status='ours', src=[], by='make_constants.py',
             text=f'Fitted to 2026, scored on 2027, which it never saw: median error {D2026["median_cm"]:.1f} cm, 90th percentile {D2026["p90_cm"]:.1f} cm, '
                  f'largest {D2026["max_cm"]:.1f} cm. The reverse: {D2027["median_cm"]:.1f}, {D2027["p90_cm"]:.1f}, {D2027["max_cm"]:.1f} cm.'),
        dict(status='ours', src=[], by='make_constants.py',
             text=f'Waves kept: 12 leave {BY_N["12"]["median_cm"]:.0f} cm, 24 leave {BY_N["24"]["median_cm"]:.0f} cm, 48 leave {BY_N["48"]["median_cm"]:.1f} cm, '
                  f'64 leave {BY_N["64"]["median_cm"]:.1f} cm.'),
        dict(status='ours', src=[], by='make_constants.py',
             text=f'Times are looser: at a flat top a few centimetres move the peak by an hour or two. The median error in the time of a high or low is {TIME_ERR["median_min"]:.0f} min.'),
        dict(status='ours', src=[], by='count_turns.py',
             text=f'The curve also wiggles at flat tops: it turns {TURNS_2026["model_turns"]} times in 2026 where the table lists {TURNS_2026["table_events"]} highs and lows. '
                  f'Ignoring turns under {TURNS["min_swing_m"] * 100:.0f} cm leaves {TURNS_2026["turns_kept"]}.'),
    ]),
    dict(key='clock', title='Which clock does the table use?', claims=[
        dict(status='ours', src=[], by='check_time_zone.py',
             text=f'Ko Lak’s observed 2025 hourly sea level, run forward, matches the Navy’s 2026 table to {TZ_BEST:.0f} min when the table is read 7 hours ahead of the record. '
                  f'With no shift the mismatch is {TZ_ZERO:.0f} min.'),
        dict(status='verified', src=['glosshb'],
             text='The GLOSS handbook gives Ko Lak’s time zone as “105E, GMT + 7hrs”.'),
        dict(status='ours', src=[], by='check_time_zone.py',
             text='The record’s own clock is not stated on the pages read. If it is GMT, as such archives usually are, the table is in Thai local time, UTC+7.'),
    ]),
    dict(key='harbour', title='In the harbour, and what we do not know', claims=[
        dict(status='ours', src=[], by='design; turns.py', chip='design (ours)',
             text='One number moves the river, the boats and the raft; the tower’s dial tells the time. A side panel shows the next high and low water '
                  '(17:51: 20:40, 2.7 m; 04:50, 1.3 m, as <code>turns.py</code> finds them), the level and a river map (© OpenStreetMap contributors), and swaps sides every ten minutes.'),
        dict(status='ours', src=['noaa'], by='make_constants.py',
             text=f'NOAA’s formula has a yearly amplitude factor <i>f</i>; ours sets it to 1 and loses almost nothing: '
                  f'{VAL["fitted_2026_scored_on_2026"]["median_cm"]:.1f} cm on the fitted year, {VAL["fitted_2026_scored_on_2027"]["median_cm"]:.1f} cm on the next.'),
        dict(status='ours', src=[], by='design', chip='limit (ours)',
             text='River flow is folded into the yearly wave. Nothing here concerns the Sun or Moon.'),
    ]),
]


# ── Checks ───────────────────────────────────────────────────────────────────
def all_claims():
    for c in HEADER_CLAIMS:
        yield 'header', c
    for p in PANELS:
        for c in p['claims']:
            yield p['key'], c


def source_order():
    seen = []
    for _, c in all_claims():
        for s in c['src']:
            if s not in seen:
                seen.append(s)
    return seen


def used_statuses():
    return [s for s in PRINTABLE if any(c['status'] == s for _, c in all_claims())]


def check_claims():
    problems = []
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
        if not c['text'].strip():
            problems.append(f'{area}: empty claim')
    return problems


# ── SVG helpers ──────────────────────────────────────────────────────────────
def esc(s):
    return html.escape(str(s), quote=True)


def T(x, y, s, size=11, anchor='start', fill=INK, weight=400, bg=WHITE, italic=False, halo=False):
    TEXT_PAIRS.add((fill, bg))
    TEXT_SIZES.append(size)
    st = (' font-style="italic"' if italic else '') + (f' stroke="{bg}" stroke-width="3.5" paint-order="stroke" stroke-linejoin="round"' if halo else '')
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}"'
            f' font-family=\'{FONT_SANS}\'{st}>{esc(s)}</text>')


def line(x1, y1, x2, y2, col=INK, w=1.0, extra=''):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{w}" {extra}/>'


def arrow(x1, y1, x2, y2, col=INK, w=1.4):
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 7 * math.cos(a), y2 - 7 * math.sin(a)
    px, py = -math.sin(a) * 3.5, math.cos(a) * 3.5
    return (line(x1, y1, hx, hy, col, w) +
            f'<polygon points="{x2:.1f},{y2:.1f} {hx + px:.1f},{hy + py:.1f} {hx - px:.1f},{hy - py:.1f}" fill="{col}"/>')


def poly(pts, col, w=1.4, extra=''):
    return f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linejoin="round" {extra}/>'


def svg_open(title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {HALF} {SVG_H}" width="{HALF}" height="{SVG_H}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title><rect width="{HALF}" height="{SVG_H}" fill="{WHITE}"/>')


def box(x, y, w, h, fill='#f4f7fa', stroke=GRID, sw=1.2):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


# ── Panels ───────────────────────────────────────────────────────────────────
def panel_days():
    X0, X1, Y0, Y1 = 46, HALF - 14, 12, 112
    X = lambda h: X0 + (X1 - X0) * h / 72.0
    Y = lambda m: Y1 - (Y1 - Y0) * (m - 0.8) / 2.6
    out = [svg_open('Three days of January 2026: the fitted tide and the Navy’s printed highs and lows')]
    for m in (1, 2, 3):
        out.append(line(X0, Y(m), X1, Y(m), GRID, 1))
        out.append(T(X0 - 6, Y(m) + 4, f'{m} m', 11, 'end', MUTED))
    for d in range(4):
        out.append(line(X(24 * d), Y0 - 4, X(24 * d), Y1 + 3, GRID, 1))
        if d < 3:
            out.append(T(X(24 * d) + 4, Y1 + 14, f'{8 + d} Jan 00:00', 11, 'start', MUTED))
    start = dt.datetime(2026, 1, 8)
    out.append(poly([(X(k / 6), Y(tide(start + dt.timedelta(minutes=10 * k)))) for k in range(72 * 6 + 1)], SEA, 1.8))
    for t, h in EVENTS:
        if t.month == 1 and 8 <= t.day <= 10:
            out.append(f'<circle cx="{X(hours_since_epoch(t) - hours_since_epoch(start)):.1f}" cy="{Y(h):.1f}" r="3.2" fill="{CORAL}" stroke="#fff" stroke-width="1"/>')
    out.append(line(X0, 142, X0 + 22, 142, SEA, 2))
    out.append(T(X0 + 27, 146, 'our 64 waves', 11, 'start', INK))
    out.append(f'<circle cx="{X0 + 142}" cy="141" r="3.2" fill="{CORAL}"/>')
    out.append(T(X0 + 150, 146, 'the Navy’s printed highs and lows', 11, 'start', INK))
    out.append('</svg>')
    return ''.join(out)


def panel_waves():
    X0, X1 = 92, HALF - 14
    X = lambda h: X0 + (X1 - X0) * h / 24.0
    out = [svg_open('The four largest waves on 8 January 2026 and their sum')]
    t0 = hours_since_epoch(dt.datetime(2026, 1, 8))
    rows = [('K1', 17), ('O1', 42), ('M2', 67), ('S2', 92)]
    for name, y in rows:
        out.append(line(X0, y, X1, y, GRID, 1))
        out.append(poly([(X(k / 6), y - wave_at(name, t0 + k / 6) * 24) for k in range(145)], SEA, 1.5))
        out.append(T(X0 - 8, y + 4, f'{name}  {amp_cm(name):.0f} cm', 11, 'end', INK))
    ys = 126
    out.append(line(X0, ys, X1, ys, GRID, 1))
    out.append(poly([(X(k / 6), ys - sum(wave_at(n, t0 + k / 6) for n, _ in rows) * 12) for k in range(145)], CORAL, 2.2))
    out.append(T(X0 - 8, ys + 4, 'sum of four', 11, 'end', CORAL, 700))
    for h in (0, 6, 12, 18, 24):
        out.append(T(X(h), 148, f'{h:02d}:00', 11, 'end' if h == 24 else 'middle', MUTED))
    out.append('</svg>')
    return ''.join(out)


def panel_springneap():
    X0, X1 = 36, HALF - 14
    n_days = 31
    X = lambda d: X0 + (X1 - X0) * d / n_days
    yc, sc = 66, 56
    out = [svg_open('The M2 and S2 waves added over January 2026, with their envelope')]
    c1, c2 = WAVE['M2'], WAVE['S2']
    def z(t):
        return (c1['amp_m'] * cmath.exp(2j * math.pi * (c1['cycles_per_hour'] * t + c1['phase_rev'])) +
                c2['amp_m'] * cmath.exp(2j * math.pi * (c2['cycles_per_hour'] * t + c2['phase_rev'])))
    out.append(line(X0, yc, X1, yc, GRID, 1))
    for m in (-0.5, 0.5):
        out.append(line(X0, yc - m * sc, X1, yc - m * sc, GRID, 1))
        out.append(T(X0 - 5, yc - m * sc + 4, f'{m:+.1f}', 11, 'end', MUTED))
    pts = [(X(k / 24), yc - z(k).real * sc) for k in range(n_days * 24 + 1)]
    env_hi = [(X(k / 24), yc - abs(z(k)) * sc) for k in range(0, n_days * 24 + 1, 3)]
    env_lo = [(x, 2 * yc - y) for x, y in env_hi]
    out.append(poly(pts, SEA, 1.1))
    out.append(poly(env_hi, CORAL, 1.8, 'stroke-dasharray="5 3"'))
    out.append(poly(env_lo, CORAL, 1.8, 'stroke-dasharray="5 3"'))
    days = [(abs(z(k * 3)), k / 8.0) for k in range(n_days * 8)]
    spring = max(days)[1]
    neap = min(d for d in days if 4 <= d[1] <= 27)[1]
    out.append(T(X(spring) + 5, yc - abs(z(spring * 24)) * sc - 4, 'spring', 11, 'start', CORAL, 700))
    out.append(T(X(neap), yc + 30, 'neap', 11, 'middle', CORAL, 700))
    for d in (0, 7, 14, 21, 28):
        out.append(T(X(d), 143, f'{d + 1} Jan', 11, 'middle', MUTED))
    out.append(T(HALF - 14, 12, 'metres, M2 + S2 only', 11, 'end', MUTED))
    out.append('</svg>')
    return ''.join(out)


def panel_year():
    X0, X1, Y0, Y1 = 40, HALF - 12, 10, 112
    X = lambda d: X0 + (X1 - X0) * d / 365.0
    Y = lambda m: Y1 - (Y1 - Y0) * (m - 0.4) / 3.2
    out = [svg_open('The highest and lowest listed water of each day of 2026, with the mean level of the fit')]
    for m in (1, 2, 3):
        out.append(line(X0, Y(m), X1, Y(m), GRID, 1))
        out.append(T(X0 - 6, Y(m) + 4, f'{m} m', 11, 'end', MUTED))
    out.append(line(X0, Y(Z0), X1, Y(Z0), INK, 1.2, 'stroke-dasharray="6 3"'))
    # The table's events strictly alternate high and low, so each one is a high when it is above its neighbour.
    kinds = []
    for i, (t, h) in enumerate(EVENTS):
        other = EVENTS[i + 1][1] if i == 0 else EVENTS[i - 1][1]
        kinds.append('H' if h > other else 'L')
    highs, lows = {}, {}
    for (t, h), k in zip(EVENTS, kinds):
        (highs if k == 'H' else lows).setdefault(t.date(), []).append(h)
    hi_pts = [(X((dt.datetime(d.year, d.month, d.day) - EPOCH).days + 0.5), Y(max(v))) for d, v in sorted(highs.items())]
    lo_pts = [(X((dt.datetime(d.year, d.month, d.day) - EPOCH).days + 0.5), Y(min(v))) for d, v in sorted(lows.items())]
    out.append(poly(hi_pts, CORAL, 1.3))
    out.append(poly(lo_pts, SEA, 1.3))
    hi = max(EVENTS, key=lambda e: e[1])
    lo = min(EVENTS, key=lambda e: e[1])
    xh, xl = X((hi[0] - EPOCH).total_seconds() / 86400), X((lo[0] - EPOCH).total_seconds() / 86400)
    out.append(f'<circle cx="{xh:.1f}" cy="{Y(hi[1]):.1f}" r="3.5" fill="{CORAL}"/>' + T(xh + 8, Y(hi[1]) + 4, f'{hi[1]:.2f} m', 11, 'start', INK, 700, halo=True))
    out.append(f'<circle cx="{xl:.1f}" cy="{Y(lo[1]):.1f}" r="3.5" fill="{SEA}"/>' + T(xl + 8, Y(lo[1]) + 4, f'{lo[1]:.2f} m', 11, 'start', INK, 700, halo=True))
    for i, name in enumerate('JFMAMJJASOND'):
        mid = (dt.datetime(2026, i + 1, 15) - EPOCH).days
        out.append(T(X(mid), 128, name, 11, 'middle', MUTED))
    out.append(line(X0, 143, X0 + 20, 143, CORAL, 2) + T(X0 + 25, 147, 'highest high of the day', 11, 'start', INK))
    out.append(line(X0 + 160, 143, X0 + 180, 143, SEA, 2) + T(X0 + 185, 147, 'lowest low of the day', 11, 'start', INK))
    out.append(line(X0 + 320, 143, X0 + 340, 143, INK, 1.2, 'stroke-dasharray="6 3"') + T(X0 + 345, 147, f'mean level, {Z0:.2f} m', 11, 'start', INK))
    out.append('</svg>')
    return ''.join(out)


def panel_method():
    out = [svg_open('From the printed table to the fitted constants')]
    out.append(box(8, 14, 118, 118))
    out.append(T(16, 31, '8 Jan, printed', 11, 'start', INK, 700))
    day = [(t, h) for t, h in EVENTS if t.month == 1 and t.day == 8]
    for i, (t, h) in enumerate(day):
        out.append(T(20, 52 + 20 * i, t.strftime('%H%M'), 12, 'start', INK))
        out.append(T(112, 52 + 20 * i, f'{h:.2f} m', 12, 'end', INK))
    out.append(arrow(128, 73, 150, 73, ACC, 2))
    out.append(box(152, 30, 112, 86, '#eef6f8', ACC))
    for i, s in enumerate(['at every event:', 'height = listed', 'slope = zero', '(a flat top)']):
        out.append(T(160, 50 + 17 * i, s, 11, 'start', INK, 700 if i == 0 else 400))
    out.append(arrow(266, 73, 288, 73, ACC, 2))
    out.append(box(290, 30, 112, 86, '#eef6f8', ACC))
    for i, s in enumerate(['one linear', 'least squares', '171 candidate', 'waves']):
        out.append(T(298, 50 + 17 * i, s, 11, 'start', INK, 700 if i == 0 else 400))
    out.append(arrow(404, 73, 426, 73, ACC, 2))
    out.append(box(428, 30, 88, 86, '#e8f1fb', SEA, 1.8))
    for i, s in enumerate([f'{CONST["n_constituents"]} waves', 'kept, with', 'their phase', 'and size']):
        out.append(T(436, 50 + 17 * i, s, 11, 'start', INK, 700 if i == 0 else 400))
    out.append(T(8, 146, 'the table lists only tops and bottoms, so nothing is drawn through them', 11, 'start', MUTED))
    out.append('</svg>')
    return ''.join(out)


def panel_accuracy():
    X0, base = 44, 112
    ns = ['6', '12', '24', '32', '48', '64', '96', '171']
    sc = 3.0
    out = [svg_open('Median height error against the number of waves kept, scored on the unseen year 2027')]
    for e in (10, 20, 30):
        out.append(line(X0 - 6, base - e * sc, HALF - 10, base - e * sc, GRID, 1))
        out.append(T(X0 - 10, base - e * sc + 4, f'{e}', 11, 'end', MUTED))
    out.append(T(10, 12, 'cm', 11, 'start', MUTED))
    for i, n in enumerate(ns):
        e = BY_N[n]['median_cm']
        x = X0 + i * 59
        keep = n == '64'
        out.append(f'<rect x="{x}" y="{base - e * sc:.1f}" width="42" height="{e * sc:.1f}" fill="{CORAL if keep else SEA}"/>')
        out.append(T(x + 21, base - e * sc - 4, f'{e:.1f}', 11, 'middle', INK, 700 if keep else 400))
        out.append(T(x + 21, base + 15, n, 11, 'middle', INK, 700 if keep else 400))
    out.append(T(X0 + 205, 146, 'waves kept (the fit uses 64)', 11, 'middle', MUTED))
    out.append('</svg>')
    return ''.join(out)


def panel_clock():
    shifts = [('+0.0', '0 h'), ('+6.5', '6.5 h'), ('+7.0', '7 h'), ('+7.5', '7.5 h')]
    mm = TZ['median_mismatch_min_by_shift_h']
    base, cap = 112, 90
    out = [svg_open('Median mismatch between Ko Lak observations and the Navy’s table, by how far ahead the table is read')]
    out.append(T(10, 12, 'minutes of mismatch', 11, 'start', MUTED))
    for i, (key, lab) in enumerate(shifts):
        x = 64 + i * 112
        v = mm[key]
        h = min(v * 0.55, cap)
        best = key == '+7.0'
        out.append(f'<rect x="{x}" y="{base - h:.1f}" width="72" height="{h:.1f}" fill="{CORAL if best else SEA}"/>')
        if v * 0.55 > cap:
            out.append(f'<polygon points="{x},{base - cap + 8} {x + 72},{base - cap + 2} {x + 72},{base - cap + 12} {x},{base - cap + 18}" fill="#fff"/>')
        if v * 0.55 > cap:
            out.append(T(x + 36, base - h + 34, f'{v:.0f} min', 11, 'middle', WHITE, 700, SEA))
        else:
            out.append(T(x + 36, base - h - 5, f'{v:.0f} min', 11, 'middle', INK, 700 if best else 400))
        out.append(T(x + 36, base + 15, lab, 11, 'middle', INK, 700 if best else 400))
    out.append(T(HALF // 2, 146, 'table read this far ahead of the record', 11, 'middle', MUTED))
    out.append('</svg>')
    return ''.join(out)


def panel_harbour():
    """The shipped level drawn by the engine (08-harbour-engine.png: scripts/check-tide-harbour.py --capture --no-fps --times
    2026-01-08T17:51:00), beside the tide curve of that same day with 'now' at the moment of the picture."""
    out = [svg_open('The Tide Harbour clock as the engine draws it, with its river panel, and that day’s tide curve')]
    img = base64.b64encode((HERE / '08-harbour-engine.png').read_bytes()).decode('ascii')
    out.append(f'<image x="0" y="0" width="232" height="130.5" href="data:image/png;base64,{img}"/>')
    out.append(f'<rect x="0" y="0" width="232" height="130.5" fill="none" stroke="{GRID}" stroke-width="1"/>')
    out.append(T(0, 146, 'engine capture, 8 Jan 17:51 Thai time', 11, 'start', MUTED))
    X0, X1, Y0, Y1 = 290, HALF - 12, 14, 112
    day = dt.datetime(2026, 1, 8)
    X = lambda h: X0 + (X1 - X0) * h / 24.0
    Y = lambda m: Y1 - (Y1 - Y0) * (m - 0.8) / 2.6
    out.append(line(X0, Y1, X1, Y1, GRID, 1))
    out.append(poly([(X(k / 6), Y(tide(day + dt.timedelta(minutes=10 * k)))) for k in range(145)], SEA, 2))
    now = 17.85
    out.append(f'<circle cx="{X(now):.1f}" cy="{Y(tide(day + dt.timedelta(hours=now))):.1f}" r="4.5" fill="{CORAL}"/>')
    out.append(T(X(now) - 6, Y(tide(day + dt.timedelta(hours=now))) - 9, 'now', 11, 'end', CORAL, 700))
    for h in (0, 6, 12, 18, 24):
        out.append(T(X(h), 130, f'{h:02d}', 11, 'middle', MUTED))
    out.append(T((X0 + X1) / 2, 146, 'one number drives it all', 11, 'middle', MUTED))
    out.append('</svg>')
    return ''.join(out)


PANEL_FN = {'days': panel_days, 'waves': panel_waves, 'springneap': panel_springneap, 'year': panel_year,
            'method': panel_method, 'accuracy': panel_accuracy, 'clock': panel_clock, 'harbour': panel_harbour}


# ── HTML ─────────────────────────────────────────────────────────────────────
def chip_html(c):
    kind = c['status']
    return f'<span class="chip {kind}">{esc(c.get("chip", STATUS_TEXT[kind]))}</span>'


def refs_html(c, num):
    return ('\u00a0<span class="ref">[' + ', '.join(str(num[s]) for s in c['src']) + ']</span>') if c['src'] else ''


def claim_html(c, num, area):
    return f'<p class="cl" data-status="{c["status"]}" data-area="{area}">{chip_html(c)} {c["text"]}{refs_html(c, num)}</p>'


def panel_html(i, p, num, svg):
    claims = ''.join(claim_html(c, num, p['key']) for c in p['claims'])
    return (f'<section class="panel" id="panel-{p["key"]}"><div class="bar">{i:02d} · {esc(p["title"])}</div>'
            f'{svg}<div class="claims">{claims}</div></section>')


def header_html(num):
    claims = ''.join(claim_html(c, num, 'header') for c in HEADER_CLAIMS)
    return ('<header><div class="ttl"><h1>The tide at Bangkok</h1>'
            '<div class="sub">How a computer adds up the river’s tide, and how far to trust the sum</div>'
            '<div class="meta">The Chao Phraya at Bangkok · World Foundry harbour clock</div></div>'
            f'<div class="facts">{claims}</div></header>')


def legend_html():
    items = ''.join(f'<span class="lg"><span class="chip {s}">{STATUS_TEXT[s]}</span> {LEGEND_TEXT[s]}</span>' for s in used_statuses())
    return f'<div class="legend">{items}</div>'


def footer_html(num):
    lis = []
    for s in source_order():
        d = SOURCES[s]
        lis.append(f'<li>[{num[s]}] <a href="{d["url"]}">{esc(d["cite"])}</a> · {esc(d["where"])} · <i>{esc(d["scope"])}</i></li>')
    per = -(-len(lis) // 3)
    cols = ''.join(f'<ol>{"".join(lis[i * per:(i + 1) * per])}</ol>' for i in range(3))
    return (f'<footer id="panel-src">{legend_html()}<div class="srcs">{cols}</div>'
            f'<div class="note">Tide predictions: Hydrographic Department, Royal Thai Navy; the constants here are our fit to them. Sources checked {CHECKED}. Numbers are computed by '
            'wflevels/tide_harbour/tide_fit; locators and what could not be found: docs/reference/chao-phraya-tide-research.md. Drawings are original. '
            'A3 portrait, 297 × 420 mm; print on matte or uncoated stock.</div></footer>')


CSS = f"""
@page {{ size: A3 portrait; margin: 0 }}
*{{ box-sizing: border-box }}
html,body{{ margin:0; background:#fff; color:{INK}; -webkit-print-color-adjust:exact; print-color-adjust:exact }}
body{{ font: 11.5px/1.3 {FONT_SANS} }}
.page{{ width:{PAGE_W_MM}mm; height:{PAGE_H_MM}mm; padding:{MARGIN_MM}mm; overflow:hidden; display:flex; flex-direction:column; gap:5px; background:#fff }}
header{{ background:{NAVY}; color:#fff; display:flex; gap:16px; padding:9px 14px 8px; height:118px; flex:none }}
header .ttl{{ width:400px; flex:none }}
header h1{{ font-family:{FONT_SERIF}; margin:0; font-size:27pt; white-space:nowrap; line-height:1.05; font-weight:700; letter-spacing:-.01em }}
header .sub{{ color:{NAVY_TEXT}; font-size:13px; line-height:1.3; margin-top:5px }}
header .meta{{ color:{NAVY_TEXT}; font-size:12px; margin-top:4px }}
header .facts{{ flex:1; background:#fff; color:{INK}; border-radius:5px; padding:4px 8px; overflow:hidden }}
header .facts .cl{{ margin:0 0 2px }}
.row{{ display:flex; gap:13px; flex:none }}
.panel{{ width:{HALF}px; height:292px; overflow:hidden; border:1px solid {GRID}; flex:none }}
.bar{{ background:{ACC}; color:#fff; font-family:{FONT_SERIF}; font-size:12.5pt; font-weight:700; height:24px; line-height:24px; padding:0 10px; white-space:nowrap }}
.panel svg{{ display:block; margin-top:2px }}
.claims{{ padding:1px 9px 0 }}
.cl{{ margin:0 0 3px; font-size:11px; line-height:14px }}
.ref{{ color:{MUTED}; white-space:nowrap }}
.chip{{ display:inline-block; border-radius:8px; padding:0 6px; font-size:11px; line-height:13px; font-weight:700; border:1px solid; white-space:nowrap; vertical-align:baseline }}
{''.join(f'.chip.{k}{{ color:{v[0]}; background:{v[1]}; border-color:{v[2]} }}' for k, v in CHIP.items())}
footer{{ flex:1; border-top:2px solid {ACC}; padding-top:4px; display:flex; flex-direction:column; gap:3px; min-height:0 }}
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

UNITS = r'(?:cm|mm|km|min|h|m|%|°)'
_NUM_UNIT = re.compile(rf'(\d)[ \u00a0]+({UNITS})(?![\w/])')
_TIMES = re.compile(r'(\d) × (\d)')
_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')


def polish_text(s):
    s = _NUM_UNIT.sub('\\1\u00a0\\2', s)
    s = _TIMES.sub('\\1\u00a0×\u00a0\\2', s)
    return _ISO.sub('\\1\u2011\\2\u2011\\3', s)


def polish(doc):
    """Keep every number with its unit and every ISO date on one line, outside tags and the style and script blocks."""
    parts = re.split(r'(<style>.*?</style>|<script>.*?</script>|<svg.*?</svg>|<[^>]+>)', doc, flags=re.S)
    return ''.join(p if p.startswith('<') else polish_text(p) for p in parts)


def build():
    problems = check_claims()
    if problems:
        raise SystemExit('make_poster: refusing to build:\n  ' + '\n  '.join(problems))
    num = {s: i + 1 for i, s in enumerate(source_order())}
    svgs = {}
    for p in PANELS:
        svgs[p['key']] = PANEL_FN[p['key']]()
    for i, p in enumerate(PANELS, 1):
        (HERE / f'{i:02d}-{p["key"]}.svg').write_text(svgs[p['key']] + '\n', encoding='utf-8')
    rows = ''.join('<div class="row">' + panel_html(2 * r + 1, PANELS[2 * r], num, svgs[PANELS[2 * r]['key']]) +
                   panel_html(2 * r + 2, PANELS[2 * r + 1], num, svgs[PANELS[2 * r + 1]['key']]) + '</div>' for r in range(4))
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>The tide at Bangkok</title>'
           f'<style>{CSS}</style></head><body><div class="page">{header_html(num)}{rows}{footer_html(num)}</div>{FIT_SCRIPT}</body></html>')
    (HERE / 'poster.html').write_text(polish(doc), encoding='utf-8')
    print(f'poster.html: {len(PANELS)} panels, {sum(1 for _ in all_claims())} claims, {len(num)} sources')


if __name__ == '__main__':
    build()
