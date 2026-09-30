#!/usr/bin/env python3
"""make_poster.py — build the clownfish biomechanics poster (A3 portrait) from the data sheet.

    python3 make_poster.py [--out-dir DIR] [--html-only]

Writes, into DIR (default: next to this script):
  data.json    the resolved data sheet (values read from the game's code)
  poster.html  self-contained: inline CSS and inline SVG, no external reference
  poster.pdf   one A3 page, live links, fonts embedded (headless Chrome from poster.html)
  poster.png   150 dpi preview of the PDF (pdftoppm)

Every curve is computed here from the formulas in the plan and from the constants in
wflevels/aquarium/aquarium_constants.py and clownfish.py (via data.py), so a changed constant
redraws the picture. The build fails if a chip in the data sheet disagrees with the label in
the code's comment.

Plan: docs/plans/2026-09-30-clownfish-biomechanics-poster.md
Needs: google-chrome, pdftoppm (poppler-utils). `--html-only` needs neither.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data as D  # noqa: E402

# ── Page and type ────────────────────────────────────────────────────────────
PAGE_W_MM, PAGE_H_MM, MARGIN_MM = 297, 420, 10
CW = 1047                       # content width in CSS px (277 mm at 96 dpi)
HALF = 517                      # half panel; two of them and a 13 px gap fill CW
MIN_PX = 11.0                   # 8.25 pt: nothing on the poster is set smaller (8 pt = 10.67 px)
PX_TO_PT = 0.75

INK, MUTED, GRID, ACC, WHITE = '#1d2733', '#5c6b7a', '#dfe5ec', '#0f7c93', '#ffffff'
NAVY, NAVY_TEXT = '#0f2a3a', '#c4dbe8'
CHIP = {   # kind: (text, fill, edge)
    'verified': ('#0f5f30', '#e3f4ea', '#1f8a4c'),
    'unverified': ('#7a4500', '#fff2d9', '#b26a00'),
    'ours': ('#1b46b3', '#e4ecff', '#2b5fd9'),
    'other-species': ('#6a2a94', '#f1e6fb', '#8a44c0'),
}
PURPLE, ORANGE_TXT, GREEN_TXT, RED_TXT = '#6a2ec0', '#a84e00', '#1c7a3c', '#b02a2a'
FONT_SANS = '"Noto Sans","DejaVu Sans","Liberation Sans",Arial,sans-serif'
FONT_MONO = '"Noto Sans Mono","DejaVu Sans Mono","Liberation Mono",monospace'
_FONT_FILES = {False: '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
               True: '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf'}
_FONT_CACHE = {}

TEXT_PAIRS = set()              # (foreground, background) of every text the SVGs draw: the contrast test reads it
TEXT_SIZES = []                 # every font size (px) the SVGs draw


def contrast(fg, bg):
    """WCAG 2.x contrast ratio between two #rrggbb colours."""
    def lum(c):
        ch = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        ch = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


# The HTML's own text colours on their backgrounds (the SVG text is recorded by T()).
HTML_TEXT_PAIRS = {(INK, WHITE), (MUTED, WHITE), (WHITE, ACC), (WHITE, NAVY), (NAVY_TEXT, NAVY),
                   ('#1a5f74', WHITE)} | {(v[0], v[1]) for v in CHIP.values()}


def text_width(s, size, bold=False):
    """Rendered width of `s` in Noto Sans (PIL); a per-character estimate if the font is missing."""
    try:
        from PIL import ImageFont
        if bold not in _FONT_CACHE:
            _FONT_CACHE[bold] = ImageFont.truetype(_FONT_FILES[bold], 100)
        return _FONT_CACHE[bold].getlength(s) * size / 100.0
    except Exception:  # noqa: BLE001 — any font problem falls back to an estimate
        return len(s) * size * (0.62 if bold else 0.56)


def esc(s):
    return html.escape(str(s), quote=False)


# ── SVG helpers ──────────────────────────────────────────────────────────────
def T(x, y, s, size=12, anchor='start', fill=INK, weight=400, mono=False, bg=WHITE, extra=''):
    assert size >= MIN_PX, f'{size}px text is under the {MIN_PX}px floor: {s!r}'
    TEXT_PAIRS.add((fill, bg))
    TEXT_SIZES.append(size)
    fam = f' font-family=\'{FONT_MONO}\'' if mono else ''
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:g}" text-anchor="{anchor}" fill="{fill}" '
            f'font-weight="{weight}"{fam} {extra}>{esc(s)}</text>')


def chip(x, y, kind, detail=None, size=11):
    """SVG chip: 'kind · detail'. Returns (svg, width) so callers can lay chips out in a row."""
    fg, bg, edge = CHIP[kind]
    label = D.STATUS_TEXT[kind] + (f' · {detail}' if detail else '')
    w = text_width(label, size, True) + 14
    svg = (f'<g class="chip"><rect x="{x:.1f}" y="{y - 12:.1f}" width="{w:.1f}" height="17" rx="8.5" '
           f'fill="{bg}" stroke="{edge}" stroke-width="1"/>' + T(x + w / 2, y, label, size, 'middle', fg, 700, bg=bg) + '</g>')
    return svg, w


def arrow(x1, y1, x2, y2, col=INK, w=1.6):
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = 8 * math.cos(a), 8 * math.sin(a)
    px, py = -4 * math.sin(a), 4 * math.cos(a)
    return (f'<g stroke="{col}" stroke-width="{w}" fill="{col}"><line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2 - hx * .6:.1f}" y2="{y2 - hy * .6:.1f}"/>'
            f'<polygon stroke="none" points="{x2:.1f},{y2:.1f} {x2 - hx + px:.1f},{y2 - hy + py:.1f} {x2 - hx - px:.1f},{y2 - hy - py:.1f}"/></g>')


def dim(x1, y1, x2, y2, col=MUTED):
    return arrow(x1, y1, x2, y2, col, 1.2) + arrow(x2, y2, x1, y1, col, 1.2)


def plot_open(pid, x0, y0, w, h, xmax, ymax):
    """Opens a group carrying its axis mapping, so the tests can invert what is drawn."""
    return (f'<g id="{pid}" data-x0="{x0}" data-y0="{y0}" data-w="{w}" data-h="{h}" '
            f'data-xmax="{xmax}" data-ymax="{ymax}">')


def axes(x0, y0, w, h, xmax, ymax, xt, yt, xlabel, ylabel, fmtx=lambda v: f'{v:g}', fmty=lambda v: f'{v:g}'):
    s = []
    for v in xt:
        X = x0 + v / xmax * w
        s.append(f'<line x1="{X:.1f}" y1="{y0}" x2="{X:.1f}" y2="{y0 - h}" stroke="{GRID}"/>' + T(X, y0 + 14, fmtx(v), 11, 'middle', MUTED))
    for v in yt:
        Y = y0 - v / ymax * h
        s.append(f'<line x1="{x0}" y1="{Y:.1f}" x2="{x0 + w}" y2="{Y:.1f}" stroke="{GRID}"/>' + T(x0 - 5, Y + 4, fmty(v), 11, 'end', MUTED))
    s.append(f'<line x1="{x0}" y1="{y0}" x2="{x0 + w}" y2="{y0}" stroke="{INK}"/><line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 - h}" stroke="{INK}"/>')
    s.append(T(x0 + w / 2, y0 + 29, xlabel, 11.5, 'middle', INK, 600))
    cx = x0 - 34
    s.append(f'<text x="{cx}" y="{y0 - h / 2:.1f}" font-size="11.5" text-anchor="middle" fill="{INK}" font-weight="600" '
             f'transform="rotate(-90 {cx} {y0 - h / 2:.1f})">{esc(ylabel)}</text>')
    TEXT_PAIRS.add((INK, WHITE))
    TEXT_SIZES.append(11.5)
    return ''.join(s)


# ── The clownfish (the approved mockup look), outline from the game's own polygons ──
def outline(k):
    F = k.F
    return list(F.BODY_TOP) + list(F.TAIL[1:]) + list(reversed(F.BODY_BOTTOM))[1:-1]


def densify(poly, n=8):
    out = []
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        for i in range(n):
            out.append((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
    return out


def fish_icon(k, cx, cy, s, tilt=0.0, uid='f', opacity=1.0):
    """Faceted clownfish facing +x, 123 drawing units long, at scale s."""
    body = outline(k)
    P = lambda p: ' '.join(f'{x:.2f},{y:.2f}' for x, y in p)
    facets = [([(50, 0), (38, -13), (22, -21), (8, 0)], '#ff8a2a'), ([(22, -21), (4, -27), (-16, -25), (8, 0)], '#ff9d47'),
              ([(-16, -25), (-34, -15), (-44, -7), (-20, 0), (8, 0)], '#f0731a'), ([(50, 0), (8, 0), (16, 23), (38, 14)], '#e8660f'),
              ([(8, 0), (-20, 0), (-12, 25), (16, 23)], '#f07a22'), ([(-20, 0), (-44, 7), (-34, 13), (-12, 25)], '#d95c0c')]
    g = [f'<g transform="translate({cx:.2f},{cy:.2f}) rotate({tilt:.2f}) scale({s:.5f})" opacity="{opacity}">',
         f'<clipPath id="{uid}c"><polygon points="{P(body)}"/></clipPath>',
         f'<polygon points="{P([(-44, -7), (-62, -23), (-73, -15), (-69, 0), (-73, 15), (-62, 23), (-44, 7)])}" fill="#e2620e" stroke="#111" stroke-width="2.4"/>',
         f'<polygon points="{P([(20, -21), (8, -38), (-6, -40), (-24, -30), (-16, -25), (4, -27)])}" fill="#f47c1d" stroke="#111" stroke-width="2.4"/>',
         f'<polygon points="{P(body)}" fill="#ff8a2a"/>']
    for poly, col in facets:
        g.append(f'<polygon points="{P(poly)}" fill="{col}" clip-path="url(#{uid}c)"/>')
    for x0, x1 in ((24, 33), (-7, 6), (-40, -34)):
        g.append(f'<g clip-path="url(#{uid}c)"><rect x="{x0 - 2.6}" y="-40" width="{x1 - x0 + 5.2:.1f}" height="80" fill="#111"/>'
                 f'<rect x="{x0}" y="-40" width="{x1 - x0}" height="80" fill="#f6f4ee"/></g>')
    g.append(f'<polygon points="{P(body)}" fill="none" stroke="#111" stroke-width="2.4" stroke-linejoin="round"/>')
    g.append('<circle cx="38" cy="-6" r="4.4" fill="#fff" stroke="#111" stroke-width="1.6"/><circle cx="39.2" cy="-6" r="2.2" fill="#111"/>')
    g.append(f'<polygon points="{P([(14, 10), (0, 17), (-8, 13), (2, 7)])}" fill="#ffb066" stroke="#111" stroke-width="1.6"/></g>')
    return ''.join(g)


# ── Panel A: the travelling body wave (1047 × 236) ───────────────────────────
def diag_a(k):
    W, H = CW, 200
    L_PX, XH, CY = 370.0, 820.0, 98.0
    U = L_PX / 123.0
    half = k.a_over_l / 2                                       # A/2 in body lengths: the tail-tip half excursion
    amp = lambda s: half * (0.1 + 0.9 * s * s)                  # A(s) = (A/2)·(0.1 + 0.9 s²)
    poly = densify(outline(k), 10)

    def deform(phase):
        pts = []
        for x, y in poly:
            s = min(max((50 - x) / 123.0, 0.0), 1.0)
            pts.append((XH - s * L_PX, CY + y * U + amp(s) * L_PX * math.sin(2 * math.pi * (s - phase))))
        return ' '.join(f'{a:.1f},{b:.1f}' for a, b in pts)

    pal = ['#2b5fd9', '#1e88c8', '#0f9c8f', '#3aa657', '#98a81f', '#d29a12', '#d5651a', '#c23a3a']
    s = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    s.append(f'<polygon points="{deform(0.0)}" fill="#ffb066" fill-opacity=".55" stroke="{INK}" stroke-width="1.6" stroke-linejoin="round"/>')
    s.append(f'<polygon points="{deform(0.25)}" fill="none" stroke="{INK}" stroke-width="1" stroke-dasharray="5 4" stroke-linejoin="round"/>')
    for i in range(8):
        d = ' '.join(f'{XH - t / 60 * L_PX:.1f},{CY + amp(t / 60) * L_PX * math.sin(2 * math.pi * (t / 60 - i / 8)):.1f}' for t in range(61))
        s.append(f'<polyline points="{d}" fill="none" stroke="{pal[i]}" stroke-width="2.4"/>')
    for sign in (1, -1):
        d = ' '.join(f'{XH - t / 60 * L_PX:.1f},{CY + sign * amp(t / 60) * L_PX:.1f}' for t in range(61))
        s.append(f'<polyline points="{d}" fill="none" stroke="{MUTED}" stroke-width="1.2" stroke-dasharray="6 5"/>')
    # body-length dimension, broken around its label
    label = f'L = body length: {k.C.FISH_LEN:g} in ({k.C.FISH_LEN * 2.54:.1f} cm) real · {k.L:.3f} m at ×{k.C.WORLD_SCALE:g}'
    mid, dy = XH - L_PX / 2, 192
    gap = text_width(label, 12, True) / 2 + 8
    s.append(arrow(mid - gap, dy, XH - L_PX, dy, MUTED, 1.2) + arrow(mid + gap, dy, XH, dy, MUTED, 1.2))
    s.append(T(mid, dy + 4, label, 12, 'middle', MUTED, 600))
    ax = XH - L_PX - 26
    s.append(dim(ax, CY - half * L_PX, ax, CY + half * L_PX))
    s.append(T(ax - 8, CY - 2, f'A ≈ {k.a_over_l:.1f} L', 13, 'end', INK, 700))
    s.append(T(ax - 8, CY + 14, 'peak to peak', 11.5, 'end', MUTED))
    s.append(arrow(XH + 40, 40, XH + 130, 40, ACC, 2.4))
    s.append(T(XH + 40, 58, 'swimming direction', 12, 'start', ACC, 600))
    s.append(arrow(XH + 190, 100, XH + 60, 100, MUTED, 1.4))
    s.append(T(XH + 60, 118, 'wave travels head → tail', 12, 'start', MUTED))
    for i in range(8):
        s.append(f'<rect x="{16 + i * 30}" y="14" width="26" height="8" fill="{pal[i]}"/>')
    s.append(T(16, 40, 'eight phases of one beat: 0, ⅛ … ⅞', 11.5, 'start', MUTED))
    s.append(T(16, 58, 'solid fill: phase 0 · dashed outline: phase ¼', 11.5, 'start', MUTED))
    s.append(T(16, 84, 'y(s, t) = A(s)·L·sin[ 2π ( s/λ − f·t ) ]', 12, 'start', INK, 600, mono=True))
    s.append(T(16, 102, 'A(s) = (A/2)·(0.1 + 0.9 s²),   λ = L', 12, 'start', MUTED, 400, mono=True))
    s.append(T(16, 120, 's = 0 at the nose, 1 at the tail tip', 11.5, 'start', MUTED))
    c1, w1 = chip(16, 152, 'ours', 'envelope shape: drawing only')
    c2, w2 = chip(16, 176, 'unverified', 'A ≈ 0.2 L, λ ≈ L: widely cited')
    return ''.join(s) + c1 + c2, W, H


# ── Panel B: Strouhal (517 × 226) ────────────────────────────────────────────
def diag_b(k):
    W, H = HALF, 218
    x0, y0, w, h = 50, 176, 388, 122
    UMAX, FMAX = 7.0, 14.0
    X = lambda u: x0 + u / UMAX * w
    Y = lambda f: y0 - f / FMAX * h
    a = k.a_over_l
    s = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    s.append(T(10, 16, 'f = St · U / A ,  A = 0.2 L   ⇒   f = 5 · St · U/L', 12, 'start', INK, 600, mono=True))
    c1, w1 = chip(10, 38, 'verified', 'St 0.2–0.4 in fish')
    c2, w2 = chip(10 + w1 + 8, 38, 'unverified', 'A = 0.2 L')
    c3, w3 = chip(10 + w1 + w2 + 16, 38, 'ours', 'St = 0.3, cap')
    s.append(c1 + c2 + c3)
    s.append(axes(x0, y0, w, h, UMAX, FMAX, range(0, 8), range(0, 15, 2), 'swimming speed U (body lengths / s)', 'tail beat f (Hz)'))
    s.append(plot_open('plot-b', x0, y0, w, h, UMAX, FMAX))
    s.append(f'<polygon points="{X(0):.1f},{Y(0):.1f} {X(UMAX):.1f},{Y(UMAX * 0.2 / a):.1f} {X(UMAX):.1f},{Y(min(FMAX, UMAX * 0.4 / a)):.1f}" fill="{ACC}" fill-opacity=".13"/>')
    for st, col, tc in ((0.2, '#3aa657', GREEN_TXT), (0.3, ACC, ACC), (0.4, '#c23a3a', RED_TXT)):
        f_end = st / a * UMAX
        s.append(f'<line id="b-st-{st}" data-st="{st}" x1="{X(0):.2f}" y1="{Y(0):.2f}" x2="{X(UMAX):.2f}" y2="{Y(f_end):.2f}" stroke="{col}" stroke-width="2"/>')
        s.append(T(X(UMAX) + 5, Y(f_end) + 4, f'St {st}', 12, 'start', tc, 700))
    pts = []
    for i in range(0, 71):
        u = i * 0.1
        pts.append((u, min(k.st * u * k.L / k.T['fish-tail-app'], k.f_cap)))
    s.append(f'<polyline id="b-game" points="{" ".join(f"{X(u):.2f},{Y(f):.2f}" for u, f in pts)}" fill="none" stroke="#e8660f" stroke-width="3.2"/>')
    ny = k.tick_hz / 2
    s.append(f'<line x1="{x0}" y1="{Y(ny):.1f}" x2="{x0 + w}" y2="{Y(ny):.1f}" stroke="{PURPLE}" stroke-dasharray="6 4"/>')
    s.append(T(x0 + 6, Y(ny) - 4, f'Nyquist {ny:g} Hz at {k.tick_hz:g} ticks/s', 11, 'start', PURPLE))
    s.append(f'<line x1="{x0}" y1="{Y(k.f_cap):.1f}" x2="{x0 + w}" y2="{Y(k.f_cap):.1f}" stroke="{ORANGE_TXT}" stroke-dasharray="2 4"/>')
    s.append(T(x0 + 6, Y(k.f_cap) - 4, f'game cap {k.f_cap:g} Hz', 11, 'start', ORANGE_TXT, 600))
    s.append(f'<circle id="b-op" data-u="{k.V_bl:.4f}" data-f="{k.f_cruise:.4f}" cx="{X(k.V_bl):.2f}" cy="{Y(k.f_cruise):.2f}" r="5.5" fill="#ff8a2a" stroke="{INK}" stroke-width="1.5"/>')
    lx, ly = X(3.7), Y(1.6)
    s.append(f'<line x1="{X(k.V_bl):.1f}" y1="{Y(k.f_cruise) + 6:.1f}" x2="{lx + 4:.1f}" y2="{ly - 12:.1f}" stroke="{INK}" stroke-width="1"/>')
    s.append(T(lx, ly, f'cruise {k.V_bl:.2f} BL/s → {k.f_cruise:.1f} Hz', 11.5, 'start', INK, 700))
    s.append(f'<circle cx="{X(k.dart_bl):.2f}" cy="{Y(k.f_cap):.2f}" r="5" fill="#fff" stroke="{INK}" stroke-width="1.5"/>')
    s.append(T(X(k.dart_bl) - 8, Y(k.f_cap) + 18, f'dart: St {k.st_dart:.2f}', 11, 'end', INK, 600))
    s.append('</g>')
    return ''.join(s), W, H


# ── Panel C: burst-and-coast (517 × 226) ─────────────────────────────────────
def gait_trace(k, cycles=4, warm=40):
    """Mirror of aquarium_swim.fth `aq-gait` at one engine tick per step (the game's law:
    cycle counter, burst toward BURST_SPEED with tau_a for duty × cycle, else ease to 0 with tau_c),
    driving the rig's own RigState for the tail. Returns ticks [(t, v, burst, tail_rev)] and
    fine-grained tail samples [(t, tail_rev)] for the last `cycles` cycles."""
    C, F = k.C, k.F
    dt = k.dt
    rig, fine = F.RigState(k.fish), F.RigState(k.fish)
    v, cyc = 0.0, 0.0
    n_total = int(round((warm + cycles) * C.GAIT_CYCLE / dt))
    n_show = int(round(cycles * C.GAIT_CYCLE / dt))
    ticks, tail = [], []
    sub = 10
    for i in range(n_total):
        cyc += dt
        if cyc >= C.GAIT_CYCLE - 1e-9:
            cyc -= C.GAIT_CYCLE
        burst = cyc < C.GAIT_CYCLE * C.GAIT_DUTY - 1e-9
        target, tau = (C.BURST_SPEED, C.TAU_ACCEL) if burst else (0.0, C.TAU_COAST)
        v += min(1.0, dt / tau) * (target - v)
        rig.speed, rig.burst = v, 1.0 if burst else 0.0
        rig.step_rig(dt)
        fine.speed, fine.burst = v, rig.burst
        j = i - (n_total - n_show)
        for m in range(sub):
            fine.step_rig(dt / sub)
            if j >= 0:
                tail.append((j * dt + (m + 1) * dt / sub, fine.channels()['tail']))
        if j >= 0:
            ticks.append(((j + 1) * dt, v, burst, rig.channels()['tail']))
    return ticks, tail


def diag_c(k):
    W, H = HALF, 218
    x0, y0, w, h = 50, 120, 430, 72
    cycles = 4
    tmax = cycles * k.C.GAIT_CYCLE
    VMAX = 5.0
    X = lambda t: x0 + t / tmax * w
    Y = lambda bl: y0 - bl / VMAX * h
    ticks, tail = gait_trace(k, cycles)
    s = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    s.append(T(10, 16, f'cycle {k.C.GAIT_CYCLE:g} s: burst {k.C.GAIT_DUTY * 100:g} % (tail beats) · coast {100 - k.C.GAIT_DUTY * 100:g} % (body straight)', 12, 'start', INK, 600))
    s.append(axes(x0, y0, w, h, tmax, VMAX, [i * k.C.GAIT_CYCLE for i in range(cycles + 1)], range(0, 6), 'time (s)', 'speed (BL/s)'))
    s.append(plot_open('plot-c', x0, y0, w, h, tmax, VMAX))
    for t, v, b, _ in ticks:
        if b:
            s.append(f'<rect x="{X(t - k.dt):.1f}" y="{y0 - h}" width="{X(k.dt) - x0:.1f}" height="{h}" fill="#ff8a2a" fill-opacity=".16"/>')
    pts = [(0.0, ticks[-1][1])] + [(t, v) for t, v, _, _ in ticks]      # t = 0 is the end of the previous cycle
    s.append(f'<polyline id="c-speed" points="{" ".join(f"{X(t):.2f},{Y(v / k.L):.2f}" for t, v in pts)}" fill="none" stroke="{ACC}" stroke-width="2.4"/>')
    n_cyc = int(round(k.C.GAIT_CYCLE / k.dt))
    mean = sum(v for _, v, _, _ in ticks[-n_cyc:]) / n_cyc / k.L
    s.append(f'<line id="c-mean" data-bl="{mean:.4f}" x1="{x0}" y1="{Y(mean):.2f}" x2="{x0 + w}" y2="{Y(mean):.2f}" stroke="{INK}" stroke-dasharray="5 4"/>')
    s.append(T(x0 + 6, Y(0.7), f'- - -  mean {mean:.2f} BL/s = V', 11.5, 'start', INK, 700))
    s.append(T(X(0.1), y0 - h - 4, 'burst', 11, 'middle', ORANGE_TXT, 700))
    s.append(T(X(0.35), y0 - h - 4, 'coast', 11, 'middle', MUTED, 700))
    s.append('</g>')
    ty = 168
    amp_deg = k.T['fish-tail-swim-amp'] * 360
    sc = 14.0 / amp_deg
    s.append(f'<line x1="{x0}" y1="{ty}" x2="{x0 + w}" y2="{ty}" stroke="{GRID}"/>')
    s.append(f'<polyline points="{" ".join(f"{X(t):.1f},{ty - r * 360 * sc:.1f}" for t, r in tail)}" fill="none" stroke="#e8a060" stroke-width="1.2"/>')
    s.append(f'<polyline points="{" ".join(f"{X(t):.1f},{ty - r * 360 * sc:.1f}" for t, _, _, r in ticks)}" fill="none" stroke="{ORANGE_TXT}" stroke-width="1.4"/>')
    s.append(T(x0 - 6, ty + 4, 'tail', 11, 'end', MUTED))
    s.append(T(x0 + w, ty + 26, f'tail yaw ±{amp_deg:.0f}°: thin = continuous, dark = sampled at {k.tick_hz:g} ticks/s', 11, 'end', MUTED))
    c1, w1 = chip(10, 210, 'verified', 'drag ≈ 4 : 1, ≈ 45 % saved (koi)')
    c2, w2 = chip(10 + w1 + 8, 210, 'ours', 'cycle, share, τ')
    s.append(c1 + c2)
    return ''.join(s), W, H


# ── Panel D: pectoral fins (517 × 218) ───────────────────────────────────────
def diag_d(k):
    W, H = HALF, 210
    x0, y0, w, h = 50, 128, 232, 92
    XM, FM = 5.0, 6.0
    X = lambda u: x0 + u / XM * w
    Y = lambda f: y0 - f / FM * h
    T_ = k.T
    lo, hi, vhi = T_['fish-pec-idle-hz'], T_['fish-pec-hz-hi'], T_['fish-pec-v-hi'] / k.L
    a_bl, s_bl = T_['fish-pec-sync-lo'] / k.L, T_['fish-pec-sync-hi'] / k.L
    s = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    s.append(f'<rect x="{X(0):.1f}" y="{y0 - h}" width="{X(a_bl) - x0:.1f}" height="{h}" fill="#c23a3a" fill-opacity=".08"/>')
    s.append(f'<rect x="{X(s_bl):.1f}" y="{y0 - h}" width="{X(XM) - X(s_bl):.1f}" height="{h}" fill="#2b5fd9" fill-opacity=".08"/>')
    s.append(axes(x0, y0, w, h, XM, FM, range(0, 6), range(0, 7, 2), "game's swimming speed (BL/s)", 'pectoral beat (Hz)'))
    s.append(plot_open('plot-d', x0, y0, w, h, XM, FM))
    s.append(f'<polyline id="d-beat" points="{X(0):.1f},{Y(lo):.1f} {X(vhi):.1f},{Y(hi):.1f} {X(XM):.1f},{Y(hi):.1f}" fill="none" stroke="{ACC}" stroke-width="2.6"/>')
    s.append('</g>')
    for u, f in ((0, lo), (vhi, hi)):
        s.append(f'<circle cx="{X(u):.1f}" cy="{Y(f):.1f}" r="5" fill="#ff8a2a" stroke="{INK}"/>')
    s.append(T(x0 + 8, Y(lo) + 17, f'{lo:g} Hz', 12, 'start', INK, 700))
    s.append(T(X(vhi) + 2, Y(hi) + 19, f'{hi:g} Hz', 12, 'middle', INK, 700))
    s.append(T(x0 + 3, y0 - h + 13, 'alternating', 11, 'start', RED_TXT, 600))
    s.append(T(X(XM) - 3, y0 - h + 13, 'synchronous', 11, 'end', '#1b46b3', 600))
    hb = y0 + 44
    s.append(f'<rect x="{X(1.87):.1f}" y="{hb - 8}" width="{X(4.95) - X(1.87):.1f}" height="8" fill="{CHIP["other-species"][2]}" fill-opacity=".55"/>')
    s.append(T(X(1.87) - 5, hb, 'damselfish switch', 11, 'end', CHIP['other-species'][0], 600))
    s.append(T(X(4.95) + 5, hb, '1.87–4.95', 11, 'start', CHIP['other-species'][0], 600))
    tx0, tw = 318, 172
    for row, (lab, f, sync) in enumerate(((f'slow: alternating, {lo:g} Hz', lo, 0.0), (f'fast: synchronous, {hi:g} Hz', hi, 1.0))):
        cy = 66 + row * 62
        s.append(T(tx0, cy - 30, lab, 11.5, 'start', INK, 600))
        for side, col, ph in (('L', '#c23a3a', 0.0), ('R', '#2b5fd9', 0.5 * (1 - sync))):
            d = ' '.join(f'{tx0 + i / 100 * tw:.1f},{cy - 11 * math.sin(2 * math.pi * (f * (i / 100) * 0.9 + ph)):.1f}' for i in range(101))
            s.append(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="2" {"stroke-dasharray=\"5 3\"" if side == "R" else ""}/>')
        s.append(T(tx0 + tw + 5, cy - 3, 'L', 11, 'start', '#b02a2a', 700))
        s.append(T(tx0 + tw + 5, cy + 11, 'R', 11, 'start', '#1b46b3', 700))
    s.append(T(tx0 + tw, 66 + 62 + 26, '0.9 s shown', 11, 'end', MUTED))
    c1, w1 = chip(10, 201, 'verified', f'A. ocellaris {lo:g} → {hi:g} /s, surge trials')
    c2, w2 = chip(10 + w1 + 8, 201, 'other-species', 'gait switch: hint')
    s.append(c1 + c2)
    return ''.join(s), W, H


# ── Panel E: turning (517 × 218) ─────────────────────────────────────────────
def diag_e(k):
    W, H = HALF, 210
    s = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    L_PX = 96.0
    R = k.uturn_r / k.L * L_PX
    cx, cy = 110, 88
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{R:.1f}" fill="none" stroke="{GRID}" stroke-width="2"/>')
    s.append(f'<path d="M {cx} {cy + R:.1f} A {R:.1f} {R:.1f} 0 0 0 {cx} {cy - R:.1f}" fill="none" stroke="#ff8a2a" stroke-width="4"/>')
    for a in (0.0, math.pi / 2, math.pi):
        px, py = cx + R * math.sin(a), cy + R * math.cos(a)
        tx, ty = math.cos(a), -math.sin(a)                     # heading: tangent to the path
        nx, ny = -ty, tx
        s.append(f'<polygon points="{px + tx * 9:.1f},{py + ty * 9:.1f} {px - tx * 6 + nx * 6:.1f},{py - ty * 6 + ny * 6:.1f} {px - tx * 6 - nx * 6:.1f},{py - ty * 6 - ny * 6:.1f}" fill="{INK}"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="{PURPLE}"/>')
    s.append(dim(cx, cy, cx + R * math.cos(-0.9), cy + R * math.sin(-0.9), PURPLE))
    s.append(T(cx - 12, cy - 12, 'R', 13, 'middle', PURPLE, 700))
    by = cy + R + 20
    s.append(dim(cx - L_PX / 2, by, cx + L_PX / 2, by))
    s.append(T(cx, by + 15, f'L = {k.L:.3f} m, same scale', 11, 'middle', MUTED))
    s.append(T(10, 20, f'cruising U-turn: R ≈ {k.uturn_r:.1f} m = {k.uturn_r / k.L:.2f} L', 12, 'start', INK, 700))
    s.append(T(10, 36, f'R = V / (2π · ω), V = {k.V:.3f} m/s, ω = {k.C.YAW_WMAX:g} rev/s', 11, 'start', MUTED))
    s.append(T(10, 180, 'path of the body centre; arrows = heading', 11, 'start', MUTED))
    base = 296
    labs = ('1 straight', '2 C-bend', '3 counter-bend', '4 glide')
    s.append(T(base - 16, 20, 'escape C-start: four stages', 12, 'start', INK, 700))
    for i, lab in enumerate(labs):
        x = base + i * 62
        curv = (0.0, 2.6, -1.7, 0.0)[i]
        s.append(f'<path d="M {x} 38 Q {x + 22 * curv:.1f} 68 {x} 98" fill="none" stroke="#ff8a2a" stroke-width="9" stroke-linecap="round"/>')
        s.append(f'<circle cx="{x}" cy="38" r="4.5" fill="{INK}"/>')
        s.append(T(x, 118 + (i % 2) * 14, lab, 11, 'middle', INK, 600))
    s.append(T(base - 16, 154, 'stage 1 bends the body into a C; larger', 11, 'start', INK))
    s.append(T(base - 16, 168, 'fish bend slower but cover more distance.', 11, 'start', INK))
    s.append(T(base - 16, 182, 'Definitions, not a clownfish figure.', 11, 'start', INK))
    c1, w1 = chip(10, 201, 'ours', 'R: game measurement')
    c2, w2 = chip(10 + w1 + 8, 201, 'unverified', 'C-start: Domenici & Blake')
    s.append(c1 + c2)
    return ''.join(s), W, H


# ── Panel F: facing, velocity and the control chain (517 × 218) ──────────────
def diag_f(k):
    W, H = HALF, 210
    s = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    fcx, fcy = 92, 58
    tilt = -18.0
    s.append(fish_icon(k, fcx, fcy, 0.78, tilt, 'ff'))
    a = math.radians(tilt)
    nx, ny = fcx + 50 * 0.78 * math.cos(a), fcy + 50 * 0.78 * math.sin(a)
    s.append(arrow(nx + 2, ny - 1, nx + 60 * math.cos(a), ny + 60 * math.sin(a), ACC, 2.6))
    s.append(T(nx + 50, ny - 30, 'v ∥ nose', 12, 'start', ACC, 700))
    s.append(f'<line x1="{fcx - 60}" y1="{fcy + 2}" x2="{fcx + 125}" y2="{fcy + 2}" stroke="{MUTED}" stroke-dasharray="4 3"/>')
    s.append(T(fcx + 128, fcy + 6, 'level', 11, 'start', MUTED))
    r = 76
    s.append(f'<path d="M {fcx + r:.1f} {fcy + 2} A {r} {r} 0 0 0 {fcx + r * math.cos(a):.1f} {fcy + 2 + r * math.sin(a):.1f}" fill="none" stroke="{PURPLE}" stroke-width="1.6"/>')
    s.append(T(fcx + r + 6, fcy - 10, 'θ pitch', 12, 'start', PURPLE, 700))
    pmax = k.C.PITCH_MAX * 360
    s.append(T(10, 120, 'ψ yaw = ROTATION_C', 11, 'start', INK))
    s.append(T(10, 134, f'θ pitch = −ROTATION_B, limit {pmax:g}°', 11, 'start', INK))
    s.append(T(10, 148, f'φ roll = ROTATION_A, bank ≤ {k.C.BANK_MAX * 360:g}°', 11, 'start', INK))
    s.append(T(10, 166, 'the physics hull never turns;', 11, 'start', MUTED))
    s.append(T(10, 180, 'only the visible parts do', 11, 'start', MUTED))
    labels = [('buttons → wanted direction d', 'ours'),
              (f'target facing ψ*, θ* (pitch ≤ {pmax:g}°)', 'ours'),
              ('yaw, pitch springs (ω, ζ) · bank', 'ours'),
              ('burst-and-coast speed U', 'ours'),
              ('v = U·(cosθ cosψ, cosθ sinψ, sinθ)', 'ours'),
              ('XSPEED · YSPEED · ZSPEED', 'ours')]
    bx, bw = 262, 246
    for i, (lab, kind) in enumerate(labels):
        y = 8 + i * 27
        fg, bg, edge = CHIP[kind]
        s.append(f'<rect x="{bx}" y="{y}" width="{bw}" height="22" rx="5" fill="{bg}" stroke="{edge}"/>')
        s.append(T(bx + 8, y + 15.5, lab, 11.5, 'start', INK, 600, mono=(i == 4), bg=bg))
        if i < len(labels) - 1:
            s.append(arrow(bx + bw / 2, y + 22, bx + bw / 2, y + 27, MUTED, 1.4))
    c1, w1 = chip(10, 201, 'ours', 'every box: the game')
    c2, w2 = chip(10 + w1 + 8, 201, 'unverified', 'layering idea: Tu & Terzopoulos')
    s.append(c1 + c2)
    return ''.join(s), W, H


# ── Panel G: damped steering (517 × 218) ─────────────────────────────────────
def step_response(z, t):
    """Unit-step response of x'' + 2ζx' + x = 1 (ω = 1, time in 1/ω)."""
    if z < 1:
        wd = math.sqrt(1 - z * z)
        return 1 - math.exp(-z * t) * (math.cos(wd * t) + z / wd * math.sin(wd * t))
    if z == 1:
        return 1 - math.exp(-t) * (1 + t)
    w = math.sqrt(z * z - 1)
    return 1 - math.exp(-z * t) * (math.cosh(w * t) + z / w * math.sinh(w * t))


def overshoot(z):
    return math.exp(-math.pi * z / math.sqrt(1 - z * z)) if z < 1 else 0.0


def diag_g(k):
    W, H = HALF, 210
    x0, y0, w, h = 46, 152, 226, 96
    TM, YM = 10.0, 1.5
    X = lambda t: x0 + t / TM * w
    Y = lambda v: y0 - v / YM * h
    C = k.C
    s = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    s.append(axes(x0, y0, w, h, TM, YM, [0, 2, 4, 6, 8, 10], [0, 0.5, 1.0, 1.5], 'time (units of 1/ω)', 'response to a step'))
    s.append(f'<line x1="{x0}" y1="{Y(1):.1f}" x2="{x0 + w}" y2="{Y(1):.1f}" stroke="{INK}" stroke-dasharray="4 3"/>')
    curves = [(0.3, '#c23a3a', 'solid'), (0.6, '#d29a12', 'solid'), (1.0, ACC, 'solid'), (1.5, '#8a44c0', 'solid'),
              (C.YAW_ZETA, '#e8660f', 'game'), (C.PITCH_ZETA, '#2b5fd9', 'game')]
    s.append(plot_open('plot-g', x0, y0, w, h, TM, YM))
    for z, col, kind in curves:
        pts = ' '.join(f'{X(t):.2f},{Y(step_response(z, t)):.2f}' for t in [i * 0.05 for i in range(201)])
        dash = ' stroke-dasharray="7 3"' if kind == 'game' else ''
        s.append(f'<polyline data-zeta="{z}" points="{pts}" fill="none" stroke="{col}" stroke-width="{3 if kind == "game" else 2}"{dash}/>')
    s.append('</g>')
    lx, ly = 292, 16
    for i, (z, col, kind) in enumerate(curves):
        os_ = overshoot(z) * 100
        if kind == 'game':
            who = 'yaw' if z == C.YAW_ZETA else 'pitch'
            lab = f'game {who}: ζ = {z:g}, {os_:.2g} %'
        else:
            lab = f'ζ = {z:g}: ' + (f'{os_:.0f} % overshoot' if z < 1 else ('critical' if z == 1 else 'over-damped'))
        y = ly + i * 18
        dash = ' stroke-dasharray="6 2"' if kind == 'game' else ''
        s.append(f'<line x1="{lx}" y1="{y - 4}" x2="{lx + 20}" y2="{y - 4}" stroke="{col}" stroke-width="{3 if kind == "game" else 2}"{dash}/>')
        s.append(T(lx + 26, y, lab, 11.5, 'start', INK, 600))
    s.append(T(lx, ly + 6 * 18 + 6, 'overshoot = exp(−πζ / √(1−ζ²))', 11, 'start', MUTED, mono=True))
    s.append(T(lx, ly + 6 * 18 + 26, f'1 unit = 1/ω: yaw {1 / C.YAW_WN:.3g} s (ω {C.YAW_WN:g}),', 11, 'start', INK))
    s.append(T(lx, ly + 6 * 18 + 40, f'pitch {1 / C.PITCH_WN:.3g} s (ω {C.PITCH_WN:g} rad/s)', 11, 'start', INK))
    s.append(T(lx, ly + 6 * 18 + 54, 'rate caps not drawn', 11, 'start', MUTED))
    c1, w1 = chip(10, 201, 'ours', 'the game’s ζ and ω; the other four are illustrations')
    s.append(c1)
    return ''.join(s), W, H


PANELS = {
    'A': ('Body wave: amplitude grows from head to tail; wavelength ≈ one body length', diag_a),
    'B': ('Tail-beat frequency follows speed (Strouhal number)', diag_b),
    'C': ('Burst-and-coast: the gait the game gives the fish', diag_c),
    'D': ('Pectoral fins: beat rate and gait', diag_d),
    'E': ('Turning: the head leads, the body bends', diag_e),
    'F': ('Facing, velocity along the nose, and the control chain', diag_f),
    'G': ('Damped steering: why ζ decides how a turn feels', diag_g),
}


def panel_html(letter, k):
    title, fn = PANELS[letter]
    svg, w, h = fn(k)
    return (f'<section class="panel" id="panel-{letter.lower()}" style="width:{w}px"><div class="bar"><b>{letter}</b> · {esc(title)}</div>'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family=\'{FONT_SANS}\'>{svg}</svg></section>')


# ── Table H and footer ───────────────────────────────────────────────────────
def chip_html(kind, extra=''):
    return f'<span class="chip {kind}">{D.STATUS_TEXT[kind]}{extra}</span>'


def table_html(resolved):
    n = len(resolved)
    per = math.ceil(n / 3)
    cols = []
    for c in range(3):
        rows_ = []
        for r in resolved[c * per:(c + 1) * per]:
            src = '' if r['sources'] == [D.GAME] else f' <span class="src">{esc(" ".join(r["sources"]))}</span>'
            rows_.append(f'<tr data-id="{r["id"]}" data-status="{r["status"]}"><td class="q">{esc(r["quantity"])}</td>'
                         f'<td class="v">{esc(r["disp"])}</td><td class="c">{chip_html(r["status"])}{src}</td></tr>')
        cols.append('<table class="h"><colgroup><col style="width:112px"><col style="width:112px"><col></colgroup>'
                    '<thead><tr><th>Quantity</th><th>Value</th><th>Chip · source</th></tr></thead><tbody>'
                    + ''.join(rows_) + '</tbody></table>')
    return ('<section class="panel" id="panel-h"><div class="bar"><b>H</b> · Parameter table: every number, its unit, its source and how far to trust it</div>'
            f'<div class="tables">{"".join(cols)}</div></section>')


SHORT = {
    'S1': 'Knight 2014, JEB 217:2224',
    'S2': 'Nudds et al. 2014, JEB 217:2244',
    'S3': 'Wu, Yang & Zeng 2007, JEB 210:2181',
    'S4': 'Marcoux & Korsmeyer 2019, JEB 222(4)',
    'S5': 'Hale et al. 2006, JEB 209:3708',
    'S6': 'Li et al. 2021, Commun. Biol. 4:40',
    'S7': 'Domenici & Blake 1997, fast-starts',
    'S8': 'Tu & Terzopoulos 1994',
    'S9': 'A ≈ 0.2 L, λ ≈ L: no primary source',
}
BACKS = {
    'S1': 'St 0.2–0.4 in fish; trout 0.19–0.22',
    'S2': 'via S1 only',
    'S3': 'koi: drag ≈ 4 : 1; ≈ 45 % saved',
    'S4': 'A. ocellaris pectoral 2.4 → 4.6 /s, surge',
    'S5': 'damselfish, not clownfish: gait switch',
    'S6': 'constant cycle idea: not opened',
    'S7': 'C-start definitions: not opened',
    'S8': 'layering idea only: not opened',
    'S9': 'widely cited; no source opened',
}


def footer_html():
    def item(key):
        src = D.SOURCES[key]
        if src['url']:
            head = f'<a href="{html.escape(src["url"])}">{esc(SHORT[key])}</a>'
            sub = esc(BACKS[key])
        else:
            head = esc(SHORT[key])
            sub = f'<span class="missing">link missing</span> {esc(BACKS[key])}'
        return f'<li><b>{key}</b> {head}<br><span class="sub">{sub}</span></li>'
    keys = list(D.SOURCES)
    cols = [''.join(item(k) for k in keys[i:i + 3]) for i in (0, 3, 6)]
    how = ('<p><b>How to read the chips</b></p>'
           f'<p>{chip_html("verified")} opened; the number is on the page<br>'
           f'{chip_html("unverified")} widely cited, or not opened<br>'
           f'{chip_html("ours")} a game tunable or our own maths<br>'
           f'{chip_html("other-species")} another species: a hint only</p>'
           '<p class="sub">“ours” values come from the game’s code at build time. '
           f'Not used: Rohr &amp; Fish 2004 (cetaceans). Data dated {D.DATA_DATE}.</p>')
    return ('<section class="panel foot" id="panel-src"><div class="bar"><b>Sources</b> · live links in the PDF; what could not be verified is marked</div>'
            f'<div class="cols">{"".join(f"<ul class=srcl>{c}</ul>" for c in cols)}<div class="how">{how}</div></div></section>')


CSS = f"""
@page {{ size: A3 portrait; margin: 0 }}
*{{ box-sizing: border-box }}
html,body{{ margin:0; background:#fff; color:{INK}; -webkit-print-color-adjust:exact; print-color-adjust:exact }}
body{{ font: 12px/1.3 {FONT_SANS} }}
.page{{ width:{PAGE_W_MM}mm; height:{PAGE_H_MM}mm; padding:{MARGIN_MM}mm; overflow:hidden; display:flex; flex-direction:column; gap:5px }}
header{{ background:{NAVY}; color:#fff; display:flex; align-items:center; gap:18px; padding:6px 16px; height:76px; flex:none }}
header h1{{ margin:0; font-size:36pt; line-height:1; font-weight:800; letter-spacing:-.01em; white-space:nowrap }}
header .sub{{ color:{NAVY_TEXT}; font-size:12px; line-height:1.3; margin-top:4px; white-space:nowrap }}
header .scale{{ margin-left:auto; color:{NAVY_TEXT}; font-size:11px; line-height:1.3; width:290px; flex:none }}
header svg{{ flex:none }}
.row{{ display:flex; gap:13px; flex:none }}
.panel{{ border:1px solid {GRID}; background:#fff; flex:none }}
.bar{{ background:{ACC}; color:#fff; font-size:12pt; font-weight:700; height:22px; line-height:22px; padding:0 10px; white-space:nowrap; overflow:hidden }}
.panel svg{{ display:block }}
.tables{{ display:flex; gap:12px; padding:3px 6px 3px }}
table.h{{ border-collapse:collapse; width:335px; font-size:11px; line-height:14px; table-layout:fixed }}
table.h th{{ text-align:left; font-weight:700; color:{MUTED}; border-bottom:1px solid {GRID}; padding:0 2px }}
table.h td{{ padding:0 2px; border-bottom:1px solid {GRID}; height:15px; white-space:nowrap; overflow:hidden }}
.src{{ color:{MUTED}; font-weight:600 }}
.chip{{ display:inline-block; border-radius:9px; padding:0 6px; font-size:11px; line-height:12px; font-weight:700; border:1px solid; white-space:nowrap; vertical-align:middle }}
.chip.verified{{ color:{CHIP['verified'][0]}; background:{CHIP['verified'][1]}; border-color:{CHIP['verified'][2]} }}
.chip.unverified{{ color:{CHIP['unverified'][0]}; background:{CHIP['unverified'][1]}; border-color:{CHIP['unverified'][2]} }}
.chip.ours{{ color:{CHIP['ours'][0]}; background:{CHIP['ours'][1]}; border-color:{CHIP['ours'][2]} }}
.chip.other-species{{ color:{CHIP['other-species'][0]}; background:{CHIP['other-species'][1]}; border-color:{CHIP['other-species'][2]} }}
.foot .cols{{ display:flex; gap:14px; padding:5px 10px 4px }}
ul.srcl{{ list-style:none; margin:0; padding:0; width:240px; font-size:11px; line-height:13px }}
ul.srcl li{{ margin:0 0 4px }}
.sub{{ color:{MUTED}; font-size:11px; line-height:13px }}
.how{{ flex:1; font-size:11px; line-height:15px }} .how p{{ margin:0 0 3px }}
a{{ color:#1a5f74; text-decoration:underline }}
.missing{{ display:inline-block; line-height:12px; margin:1px 0; color:{CHIP['unverified'][0]}; font-weight:700; border:1px dashed {CHIP['unverified'][2]}; border-radius:3px; padding:0 3px; white-space:nowrap }}
"""

FIT_SCRIPT = ("<script>window.addEventListener('load',function(){var p=document.querySelector('.page'),"
              "f=document.getElementById('panel-src'),lim=p.getBoundingClientRect().bottom-parseFloat(getComputedStyle(p).paddingBottom),"
              "over=f.getBoundingClientRect().bottom-lim;"
              "document.body.setAttribute('data-fit',over<=1?'ok':'overflow');"
              "document.body.setAttribute('data-over',over.toFixed(1));});</script>")

UNITS = r'(?:BL/s|m/s|rad/s|rev/s|ticks/s|ms|Hz|cm|mm|kg|in|s|m|%|°|L|V)'
_NUM_UNIT = re.compile(rf'(\d)[ \u00a0]+({UNITS})(?![\w/])')
_RATIO = re.compile(r'(\d) : (\d)')
_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_ID = re.compile(r'\b([CS])-(start|bend)\b')


def polish_text(s):
    s = _NUM_UNIT.sub('\\1\u00a0\\2', s)
    s = _RATIO.sub('\\1\u00a0:\u00a0\\2', s)
    s = _ISO.sub('\\1\u2011\\2\u2011\\3', s)
    return _ID.sub('\\1\u2011\\2', s)


def polish(doc):
    """Non-breaking spaces between numbers and units, non-breaking hyphens in ISO dates and C-start
    style ids — in text nodes only (never in tags, attributes, <style> or <script>)."""
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


def header_html(k):
    icon = (f'<svg width="120" height="66" viewBox="-70 -38 140 76">{fish_icon(k, 0, 0, 0.5, 0, "hd")}</svg>')
    return (f'<header><div><h1>How a clownfish swims</h1><div class="sub">the biomechanics behind the aquarium level’s fish rig · Amphiprion ocellaris · '
            f'numbers, formulas and how far to trust each one</div></div><div class="scale">The level is ×{k.C.WORLD_SCALE:g} in <b>space</b> and real in <b>time</b>: '
            f'speeds are in body lengths per second, frequencies in hertz. The fish is {k.C.FISH_LEN:g} in ({k.C.FISH_LEN * 2.54:.1f} cm) real, '
            f'{k.L:.3f} m in the level; cruise {k.V:.3f} m/s ({k.V_bl:.2f} BL/s).</div>{icon}</header>')


def build_html(k, resolved):
    TEXT_PAIRS.clear()
    TEXT_SIZES.clear()
    body = [header_html(k), f'<div class="row">{panel_html("A", k)}</div>']
    for a, b in (('B', 'C'), ('D', 'E'), ('F', 'G')):
        body.append(f'<div class="row">{panel_html(a, k)}{panel_html(b, k)}</div>')
    body += [table_html(resolved), footer_html()]
    doc = ('<!DOCTYPE html>\n<!-- Generated by make_poster.py from data.py and the aquarium constants: edit those, not this file. -->\n'
           '<html lang="en"><head><meta charset="utf-8"><title>How a clownfish swims: biomechanics poster (A3)</title>'
           f'<style>{CSS}</style></head><body><div class="page">{"".join(body)}</div>{FIT_SCRIPT}</body></html>\n')
    return polish(doc)


# ── PDF and PNG ──────────────────────────────────────────────────────────────
def render_pdf(html_path, pdf_path):
    chrome = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
    if not chrome:
        raise SystemExit('make_poster: google-chrome not found (needed for the PDF)')
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', f'--user-data-dir={prof}',
                        '--no-pdf-header-footer', f'--print-to-pdf={pdf_path}', html_path.as_uri()],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


def render_png(pdf_path, png_path, dpi=150):
    if not shutil.which('pdftoppm'):
        raise SystemExit('make_poster: pdftoppm not found (poppler-utils)')
    stem = png_path.with_suffix('')
    subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile', str(pdf_path), str(stem)], check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__.split('\n\n', 1)[1])
    ap.add_argument('--out-dir', type=Path, default=HERE)
    ap.add_argument('--html-only', action='store_true', help='write data.json and poster.html, skip Chrome and pdftoppm')
    args = ap.parse_args(argv)
    k = D.constants()
    resolved = D.resolve(k)
    problems = D.label_problems(resolved)
    if problems:
        raise SystemExit('make_poster: the data sheet disagrees with the code:\n  ' + '\n  '.join(problems))
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / 'data.json').write_text(D.to_json(resolved), encoding='utf-8')
    html_path = out / 'poster.html'
    html_path.write_text(build_html(k, resolved), encoding='utf-8')
    print(f'wrote {html_path} ({html_path.stat().st_size // 1024} KB), {len(resolved)} rows')
    if args.html_only:
        return 0
    render_pdf(html_path, out / 'poster.pdf')
    render_png(out / 'poster.pdf', out / 'poster.png')
    print(f'wrote {out / "poster.pdf"}, {out / "poster.png"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
