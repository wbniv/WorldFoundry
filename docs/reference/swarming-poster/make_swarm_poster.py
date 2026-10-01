#!/usr/bin/env python3
"""make_poster.py: build the swarming poster (A3 portrait): how a school or a swarm of fish moves, the model behind it, and the Forth that runs it.

    python3 make_swarm_poster.py [--out-dir DIR] [--html-only] [--resim]

Writes, into DIR (default: next to this script):
  data.json    the resolved data sheet
  poster.html  self-contained: inline CSS and inline SVG, no external reference
  poster.pdf   one A3 page, live links (headless Chrome from poster.html)
  poster.png   150 dpi preview of the PDF (pdftoppm)

Every figure is computed here: the four snapshots by couzin.py (cached in snapshots.json; --resim recomputes), the phase diagram from sweep.json,
the tank panel from tank.json (the Forth core, run), the Forth listing and its size from wflevels/aquarium/school.fth and measured.json.
Helpers (text, chips, arrows, the PDF step) are the clownfish poster's own, imported, so the two posters look and behave alike.

Plan: docs/plans/2026-10-01-swarming-poster.md.   Needs: google-chrome, pdftoppm (poppler-utils); `--html-only` needs neither.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import textwrap
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import swarm_data as D  # noqa: E402
import couzin  # noqa: E402

_spec = importlib.util.spec_from_file_location("fishposter", HERE.parent / "clownfish-biomechanics-poster" / "make_poster.py")
FP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FP)
FP.D = D                                    # chip() reads STATUS_TEXT from the data module; ours has the same four statuses

T, chip, arrow, esc, contrast, text_width = FP.T, FP.chip, FP.arrow, FP.esc, FP.contrast, FP.text_width
INK, MUTED, GRID, ACC, WHITE, NAVY, NAVY_TEXT = FP.INK, FP.MUTED, FP.GRID, FP.ACC, FP.WHITE, FP.NAVY, FP.NAVY_TEXT
CW, HALF, FONT_SANS, FONT_MONO = FP.CW, FP.HALF, FP.FONT_SANS, FP.FONT_MONO
ORANGE, BLUE, GREEN, RED, PURPLE = '#b25a00', '#2b5fd9', '#1f8a4c', '#c0392b', '#6a2ec0'

SCHOOL_FTH = HERE.parents[2] / "wflevels" / "aquarium" / "school.fth"
STATES = [   # name, (dro, dra), seed, chip text
    ("swarm", (0, 15), 1), ("torus", (1, 12), 1), ("dynamic parallel", (3, 10), 1), ("highly parallel", (10, 10), 1)]


def loadj(name):
    p = HERE / name
    return json.loads(p.read_text()) if p.exists() else None


# ── Snapshots (the paper's four states, simulated here) ──────────────────────
def snapshots(resim=False):
    cache = HERE / "snapshots.json"
    if cache.exists() and not resim:
        return json.loads(cache.read_text())
    out = []
    for name, (dro, dra), seed in STATES:
        pos, vel, p, m, frag = couzin.run(float(dro), float(dra), steps=700, seed=seed, tail=100)
        out.append(dict(name=name, dro=dro, dra=dra, seed=seed, p=p, m=m, frag=bool(frag), pos=pos.tolist(), vel=vel.tolist()))
    cache.write_text(json.dumps(out))
    return out


def view_basis(pos, vel, name):
    """Two orthonormal axes to draw a 3D group on: look down the rotation axis for a torus, from the side of the motion for a parallel group."""
    pos, vel = np.array(pos), np.array(vel)
    c = pos.mean(0)
    if name == "torus":
        L = np.cross(pos - c, vel).sum(0)
        n = L / np.linalg.norm(L)
    elif "parallel" in name:
        d = vel.mean(0)
        d = d / np.linalg.norm(d)
        n = np.cross(d, [0, 0, 1.0]); n = n / np.linalg.norm(n) if np.linalg.norm(n) > 1e-6 else np.array([1.0, 0, 0])
    else:
        n = np.array([0.0, 0.0, 1.0])
    a = np.cross(n, [0.3, 0.5, 0.8]); a /= np.linalg.norm(a)
    if "parallel" in name:                                     # put the direction of travel along the first axis
        d = vel.mean(0); a = d - (d @ n) * n; a /= np.linalg.norm(a)
    b = np.cross(n, a)
    return a, b, n


def panel_a():
    snaps = snapshots()
    W, H = CW, 150
    s = []
    cw = (W - 5 * 8) / 4
    for k, sn in enumerate(snaps):
        x0 = 8 + k * (cw + 8)
        pos, vel = np.array(sn["pos"]), np.array(sn["vel"])
        a, b, n = view_basis(pos, vel, sn["name"])
        c = pos.mean(0)
        P = np.stack([(pos - c) @ a, (pos - c) @ b], 1)
        V = np.stack([vel @ a, vel @ b], 1)
        ext = max(np.abs(P).max(), 4.0)
        sc = min(cw, 82) / 2 / ext * 0.98
        cx, cy = x0 + cw / 2, 54
        s.append(f'<rect x="{x0:.1f}" y="8" width="{cw:.1f}" height="88" fill="#f6f9fb" stroke="{GRID}"/>')
        depth = (pos - c) @ n
        order = np.argsort(depth)
        for i in order:                                         # far fish first, paler; near fish darker
            t = (depth[i] - depth.min()) / max(np.ptp(depth), 1e-9)
            col = '#5c7f95' if t < 0.5 else '#1d4660'
            x, y = cx + P[i, 0] * sc, cy - P[i, 1] * sc
            L = 4.2
            vx, vy = V[i, 0], -V[i, 1]
            s.append(f'<line x1="{x - vx * L / 2:.1f}" y1="{y - vy * L / 2:.1f}" x2="{x + vx * L / 2:.1f}" y2="{y + vy * L / 2:.1f}" stroke="{col}" stroke-width="1.5" stroke-linecap="round"/>'
                     f'<circle cx="{x + vx * L / 2:.1f}" cy="{y + vy * L / 2:.1f}" r="1.7" fill="{col}"/>')
        s.append(f'<text></text>')
        s.append(T(x0 + 6, 24, f'{"ABCD"[k]} · {sn["name"]}', 12, 'start', INK, 700, bg='#f6f9fb'))
        s.append(T(x0 + cw - 6, 24, f'{"spin-axis view" if sn["name"] == "torus" else ("side view" if "parallel" in sn["name"] else "top view")}', 11, 'end', MUTED, 400, bg='#f6f9fb'))
        s.append(T(x0 + 6, 110, f'Δr_o = {sn["dro"]}, Δr_a = {sn["dra"]}', 12, 'start', INK, 700))
        s.append(T(x0 + 6, 124, f'p_group {sn["p"]:.2f} · m_group {sn["m"]:.2f}', 12, 'start', INK, 400))
    c1, w1 = chip(8, 142, 'ours', f'N = 100 simulated here; the zone widths are ours, the paper prints none')
    s.append(c1)
    return ''.join(s), W, H


# ── B: the zones ─────────────────────────────────────────────────────────────
def panel_b():
    W, H = HALF, 190
    cx, cy = 100, 88
    ro = [1, 6, 12]                                              # r_r, r_r + Δr_o, r_r + Δr_o + Δr_a for the school setting (1, 5, 6)
    sc = 6.4
    s = []
    # attraction ring, orientation ring, repulsion ring, blind wedge
    cols = [('#e8f0f6', '#7d9fb5'), ('#d3e4ef', '#5c86a0'), ('#b9d3e4', '#2e6285')]
    for r, (fill, edge) in zip(reversed(ro), reversed(cols)):
        s.append(f'<circle cx="{cx}" cy="{cy}" r="{r * sc:.1f}" fill="{fill}" stroke="{edge}" stroke-width="1.2"/>')
    # blind volume: 90 degrees behind (left), drawn as a wedge across all zones
    R = 12 * sc
    a0, a1 = math.radians(135), math.radians(225)
    s.append(f'<path d="M{cx},{cy} L{cx + R * math.cos(a0):.1f},{cy - R * math.sin(a0):.1f} A{R},{R} 0 0 0 {cx + R * math.cos(a1):.1f},{cy - R * math.sin(a1):.1f} Z" fill="#ffffff" fill-opacity=".85" stroke="{MUTED}" stroke-dasharray="4 3"/>')
    s.append(T(cx - R * 0.62, cy + 4, 'blind', 11, 'middle', MUTED, 700))
    # the focal fish
    s.append(f'<polygon points="{cx + 9},{cy} {cx - 7},{cy - 4.5} {cx - 7},{cy + 4.5}" fill="{INK}"/>')
    # neighbours: repulsion (inside r_r), orientation, attraction
    nb = [((cx + 0.55 * sc, cy - 0.5 * sc), 'rep'), ((cx + 3.8 * sc, cy - 3.0 * sc), 'ori'), ((cx + 3.0 * sc, cy + 4.5 * sc), 'ori'), ((cx + 9.5 * sc, cy - 5 * sc), 'att')]
    for (x, y), kind in nb:
        col = {'rep': RED, 'ori': GREEN, 'att': BLUE}[kind]
        s.append(f'<polygon points="{x + 6:.1f},{y:.1f} {x - 5:.1f},{y - 3.2:.1f} {x - 5:.1f},{y + 3.2:.1f}" fill="{col}"/>')
    s.append(arrow(cx + 0.55 * sc - 3, cy - 0.5 * sc + 3, cx - 14, cy + 14, RED, 1.8))                        # repulsion: away
    s.append(arrow(cx + 3.8 * sc - 6, cy - 3.0 * sc - 8, cx + 3.8 * sc + 20, cy - 3.0 * sc - 8, GREEN, 1.8))      # orientation: match heading
    s.append(arrow(cx + 3.0 * sc - 6, cy + 4.5 * sc + 8, cx + 3.0 * sc + 20, cy + 4.5 * sc + 8, GREEN, 1.8))
    s.append(arrow(cx + 9.5 * sc - 8, cy - 5 * sc + 6, cx + 6.5 * sc, cy - 3.1 * sc, BLUE, 1.8))              # attraction: toward
    # legend (right)
    lx = 214
    items = [(RED, 'repulsion zone, r_r = 1', 'anyone here:', 'turn away, nothing else counts'),
             (GREEN, 'orientation zone, width Δr_o', 'those here:', 'match their heading'),
             (BLUE, 'attraction zone, width Δr_a', 'those here:', 'turn toward them'),
             (MUTED, 'blind volume, 90° behind', 'α = 270°:', 'cannot see here')]
    y = 26
    for col, name, val, what in items:
        s.append(f'<rect x="{lx}" y="{y - 10}" width="12" height="12" rx="2" fill="{col}"/>')
        s.append(T(lx + 18, y, name, 12, 'start', INK, 700))
        s.append(T(lx + 18, y + 14, f'{val} {what}', 11, 'start', MUTED, 400))
        y += 32
    s.append(T(lx, y + 2, 'Drawn at the school setting: Δr_o = 5, Δr_a = 6', 11, 'start', INK, 400))
    c1, w1 = chip(10, 184, 'verified', 'zones, α, r_r: Couzin 2002')
    c2, w2 = chip(10 + w1 + 8, 184, 'ours', 'widths drawn')
    s += [c1, c2]
    return ''.join(s), W, H


# ── C: the phase diagram ─────────────────────────────────────────────────────
def classify(c):
    if c['frag'] > 0.5:
        return 'F'
    p, m = c['p'], c['m']
    if p > 0.95:
        return 'P'
    if m > 0.7 and p < 0.4:
        return 'T'
    if p > 0.6:
        return 'D'
    if p < 0.3 and m < 0.4:
        return 'S'
    return '?'


LEVELS = ['#eaf2f7', '#9fc3d9', '#2e6285', '#0e3652']          # four steps: every one keeps a letter readable (INK on the two light, white on the two dark)


def ramp(v):
    """p_group 0..1 -> one of four steps (< 0.25, < 0.6, < 0.9, above)."""
    return LEVELS[0 if v < 0.25 else 1 if v < 0.6 else 2 if v < 0.9 else 3]


def panel_c():
    sw = loadj('sweep.json')
    W, H = HALF, 190
    G = sw['grid']
    cells = {(c['dro'], c['dra']): c for c in sw['cells']}
    x0, y0, cs = 40, 4, 13.8
    s = []
    for j, dra in enumerate(G):
        for i, dro in enumerate(G):
            c = cells[(dro, dra)]
            col = ramp(c['p'])
            X, Y = x0 + i * cs, y0 + (len(G) - 1 - j) * cs
            s.append(f'<rect x="{X:.1f}" y="{Y:.1f}" width="{cs:.1f}" height="{cs:.1f}" fill="{col}" stroke="#ffffff" stroke-width=".6"/>')
            ch = classify(c)
            fg = '#ffffff' if col in LEVELS[2:] else INK
            s.append(T(X + cs / 2, Y + cs / 2 + 4, ch, 11, 'middle', fg, 700, bg=col))
    for i, dro in enumerate(G):
        s.append(T(x0 + i * cs + cs / 2, y0 + len(G) * cs + 13, f'{dro}', 11, 'middle', MUTED))
    for j, dra in enumerate(G):
        s.append(T(x0 - 6, y0 + (len(G) - 1 - j) * cs + cs / 2 + 4, f'{dra}', 11, 'end', MUTED))
    s.append(T(x0 + len(G) * cs / 2, y0 + len(G) * cs + 28, 'orientation width Δr_o (BL)', 12, 'middle', INK))
    s.append(f'<text transform="translate(12,{y0 + len(G) * cs / 2:.1f}) rotate(-90)" font-size="12" text-anchor="middle" fill="{INK}">attraction width Δr_a</text>')
    TEXT = FP.TEXT_PAIRS; TEXT.add((INK, WHITE)); FP.TEXT_SIZES.append(12)
    # our three settings
    for (dro, dra), lab in (((0, 10), 'swarm'), ((1, 10), 'torus'), ((5, 6), 'school')):
        i, j = G.index(dro) if dro in G else None, G.index(dra) if dra in G else None
        if i is None or j is None:
            continue
        X, Y = x0 + i * cs + cs / 2, y0 + (len(G) - 1 - j) * cs + cs / 2
        s.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="{cs * 0.46:.1f}" fill="none" stroke="#ffb000" stroke-width="2.4"/>')
    # legend
    lx = x0 + len(G) * cs + 18
    s.append(T(lx, 22, 'p_group (alignment)', 12, 'start', INK, 700))
    for k, (lab, col) in enumerate(zip(['< 0.25', '< 0.6', '< 0.9', '≥ 0.9'], LEVELS)):
        s.append(f'<rect x="{lx + k * 38}" y="30" width="38" height="12" fill="{col}"/>')
        s.append(T(lx + k * 38 + 19, 54, lab, 11, 'middle', MUTED))
    names = [('S', 'swarm: low p, low m'), ('T', 'torus: low p, high m'), ('D', 'dynamic parallel: high p'), ('P', 'highly parallel: p ≈ 1'), ('F', 'fragments (more than half)'), ('?', 'seeds disagree: no one state')]
    for k, (ch, what) in enumerate(names):
        s.append(T(lx, 74 + k * 15, ch, 11, 'start', INK, 700)); s.append(T(lx + 16, 74 + k * 15, what, 11, 'start', INK))
    s.append(f'<circle cx="{lx + 5}" cy="{74 + 6 * 15 + 1}" r="6" fill="none" stroke="#ffb000" stroke-width="2.4"/>')
    s.append(T(lx + 16, 74 + 6 * 15 + 4, 'our swarm, torus, school', 11, 'start', INK))
    c1, w1 = chip(10, 184, 'ours', f'N = 100, {sw["reps"]} replicates, {sw["steps"]} steps (paper: 30)')
    s.append(c1)
    return ''.join(s), W, H


# ── D: the rule, mapped to the Forth ─────────────────────────────────────────
RULE = [
    ('1', 'See the others, except behind', 'u_ij · v_i ≥ cos(α/2)', 'sch-pair', 'verified'),
    ('2', 'Repulsion if anyone is within r_r', 'd = −Σ u_ij  (nothing else counts)', 'sch-pair', 'verified'),
    ('3', 'Else orientation and attraction', 'd_o = Σ v_j,  d_a = Σ u_ij;  d = (d̂_o + d̂_a)/2', 'sch-pair, sch-want', 'verified'),
    ('4', 'Nobody in any zone: keep the heading', 'd = v_i', 'sch-want', 'verified'),
    ('5', 'Turn toward d by at most θτ, move s τ', 'v ← rotate(v, d, θτ);  c ← c + s τ v', 'sch-turn, sch-follow', 'verified'),
    ('6', 'The leader counts w times in sums 3', 'Σ w_j v_j,  Σ w_j u_ij', 'sch-pair (weight)', 'ours'),
    ('7', 'Walls repel like a neighbour', 'wall within 0.6 BL: one more repulsion', 'sch-wall', 'ours'),
    ('8', 'A dart startles the followers nearby', 'swim away from the leader for 0.5 s', 'sch-startle-all', 'ours'),
]


def panel_d():
    W = CW
    pd, pr = D.paper_turn(); gd, gr = D.game_turn()
    K = D.constants()
    by = K.INT_Y / K.FISH_LEN
    s = []
    y = 16
    for num, what, maths, word, kind in RULE:
        fg, bg, edge = FP.CHIP[kind]
        s.append(f'<circle cx="16" cy="{y - 4}" r="7.5" fill="{bg}" stroke="{edge}"/>')
        s.append(T(16, y, num, 11, 'middle', fg, 700, bg=bg))
        s.append(T(32, y, what, 12, 'start', INK, 700))
        s.append(T(330, y, maths, 11, 'start', MUTED, 400, mono=True))
        s.append(T(W - 10, y, word, 11, 'end', FP.CHIP['ours'][0] if kind == 'ours' else '#1a5f74', 700))
        y += 14.5
    y += 6
    note = (f'The paper’s random error (σ = 0.05 rad) is left out of the Forth: the caller adds it. Our units differ from the paper’s, on purpose: at its s = 3 BL/s and θ = 40°/s a 90° turn takes {pd:.2f} BL of swimming (radius {pr:.1f} BL), '
            f'wider than the tank is deep ({by:.1f} BL), and the tank runs below could not keep the fish in. Ours: s = 2 BL/s, θ = 120°/s, {gd:.2f} BL, radius {gr:.2f} BL.')
    for wl in textwrap.wrap(note, 190):
        s.append(T(10, y, wl, 11, 'start', INK)); y += 13
    H = int(y + 12)
    c1, w1 = chip(10, H - 3, 'verified', 'rules 1–5 and the paper’s s, θ: Couzin 2002, eqns 1–3 and Fig. 3')
    c2, w2 = chip(10 + w1 + 8, H - 3, 'ours', 'rules 6–8, our s, θ, the 0.6 BL wall, the 0.5 s startle')
    s += [c1, c2]
    return ''.join(s), W, H + 4


# ── F: the Forth core ────────────────────────────────────────────────────────
CORE = ['sch-pair', 'sch-want', 'sch-turn', 'sch-follow']


def forth_blocks():
    """(name, [lines]) for every definition in school.fth, comments dropped except the one-line ones directly above a word."""
    out, cur, comment = {}, None, None
    for line in SCHOOL_FTH.read_text().splitlines():
        if line.startswith(': '):
            cur = [line.split()[1], [line]]
            out[cur[0]] = cur
            if line.rstrip().endswith(';'):
                cur = None
        elif cur is not None and line.strip():
            cur[1].append(line)
            if line.rstrip().endswith(';'):
                cur = None
    return {k: v[1] for k, v in out.items()}


def wrap_code(lines, width=52):
    res = []
    for ln in lines:
        body = ln.split('\\')[0].rstrip() if '\\ ' in ln else ln.rstrip()
        indent = len(body) - len(body.lstrip())
        parts = textwrap.wrap(body.strip(), width - indent - 0, subsequent_indent='    ', break_long_words=False)
        res += [' ' * indent + p for p in parts]
    return res


WORD_NOTE = {
    'sch-pair': 'one neighbour: blind volume, then repulsion, orientation or attraction',
    'sch-want': 'the wanted direction from the three sums, or the old heading',
    'sch-turn': 'turn toward it by at most θτ, keep the heading unit length',
    'sch-follow': 'one follower, start to finish: scan, walls, startle, turn, move',
}


def panel_f():
    m = loadj('measured.json')
    blocks = forth_blocks()
    bytes_of = {w['name']: (w['bytes'], w['lines']) for w in m['words']}
    W = CW
    pad, gap = 8, 8
    COL_WEIGHT = {n: max(len(l.split('\\ ')[0].rstrip()) for l in blocks[n]) for n in CORE}      # width in proportion to the longest line, so little needs wrapping
    tot = sum(COL_WEIGHT.values())
    avail = W - 2 * pad - gap * (len(CORE) - 1)
    cols, x = [], pad
    for n in CORE:
        cwid = avail * COL_WEIGHT[n] / tot
        chars = int((cwid - 10) / 6.62)
        cols.append((n, x, cwid, wrap_code(blocks[n], chars)))
        x += cwid + gap
    lh = 12.2
    head = 52
    nlines = max(len(c[3]) for c in cols)
    H_list = head + nlines * lh + 10
    top = 6
    s = []
    for n, x, cwid, code in cols:
        s.append(f'<rect x="{x:.1f}" y="2" width="{cwid:.1f}" height="{H_list:.1f}" fill="#f6f9fb" stroke="{GRID}"/>')
        s.append(f'<rect x="{x:.1f}" y="2" width="{cwid:.1f}" height="21" fill="{ACC}"/>')
        s.append(T(x + 7, 17, n, 13, 'start', WHITE, 700, mono=True, bg=ACC))
        b_, l_ = bytes_of[n]
        s.append(T(x + cwid - 7, 17, f'{b_} B · {l_} lines', 11, 'end', WHITE, 700, bg=ACC))
        for k, wl in enumerate(textwrap.wrap(WORD_NOTE[n], int((cwid - 14) / 5.9))[:2]):
            s.append(T(x + 7, 37 + k * 12, wl, 11, 'start', MUTED, 400, bg='#f6f9fb'))
        for i, ln in enumerate(code):
            if ln.strip():
                s.append(T(x + 7, head + 8 + i * lh, ln, 11, 'start', INK, 400, mono=True, bg='#f6f9fb', extra='xml:space="preserve"'))
    y0 = H_list + 10
    dev = m.get('device') or {}
    ms = dev.get('ms', float('nan'))
    eng = m.get('engine') or {}
    ea, eb = eng.get('after', {}), eng.get('before', {})
    big = [(f'{m["dictionary_bytes"]} B', f'of the {m["dictionary_size"] // 1024} KB dictionary ({100 * m["dictionary_bytes"] / m["dictionary_size"]:.1f} %): all {len(m["words"])} words, {m["code_lines"]} code lines'),
           (f'{ms:.1f} → {ea.get("director_ms", [0])[0]:.1f} ms', f'one tick, 11 fish, Chromecast HD: the bare interpreter, then in the engine (with the camera and sway); {ea.get("fps", 0):.0f} fps'),
           (f'{eb.get("mailbox_us", 0):g} → {ea.get("mailbox_us", 0):g} µs', f'per mailbox call: three debug streams the engine ran on every call, found by this timing; {eb.get("fps", 0):.0f} fps before'),
           (f'{m["error"]["head_max"]:.0e}', 'largest heading error against couzin.py in one tick (the engine’s sine is 0.2 % off); position 3e‑04')]
    bw = (W - 2 * pad - 3 * gap) / 4
    for i, (a_, b_) in enumerate(big):
        x = pad + i * (bw + gap)
        s.append(T(x, y0 + 20, a_, 22, 'start', ACC, 800))
        for k, wl in enumerate(textwrap.wrap(b_, int(bw / 5.9))[:3]):
            s.append(T(x, y0 + 36 + k * 12.5, wl, 11, 'start', INK))
    H = int(y0 + 36 + 3 * 12.5 + 22)
    c1, w1 = chip(12, H - 6, 'ours', 'our measurements: the bare interpreter, and a bench level (the Director runs school.fth every tick) on the real Chromecast, release build')
    s.append(c1)
    return ''.join(s), W, H


# ── G: the tank, with the Forth running ──────────────────────────────────────
def panel_g():
    t = loadj('tank.json')
    K = D.constants()
    W = CW
    bx, bz = K.INT_X / K.FISH_LEN, (K.WATER_Z - K.SAND_TOP) / K.FISH_LEN
    cw = (W - 5 * 8) / 4
    sc = (cw - 4) / bx
    s = []
    names = {'swarm': 'swarm setting (0, 10)', 'torus': 'torus setting (1, 10)', 'school': 'school setting (5, 6)'}
    for k, mode in enumerate(('swarm', 'torus', 'school')):
        x0 = 8 + k * (cw + 8)
        y0 = 20
        sn = t['snaps'][mode]
        pos, vel = np.array(sn['pos']), np.array(sn['vel'])
        s.append(f'<rect x="{x0:.1f}" y="{y0}" width="{bx * sc:.1f}" height="{bz * sc:.1f}" fill="#eaf3f8" stroke="{INK}" stroke-width="1.6"/>')
        for i in range(len(pos)):
            x = x0 + (pos[i, 0] + bx / 2) * sc
            y = y0 + (bz / 2 - pos[i, 2]) * sc
            vx, vz = vel[i, 0], -vel[i, 2]
            col = '#c05800' if i == 0 else '#1d4660'
            L = 6.0 if i else 7.5
            s.append(f'<line x1="{x - vx * L / 2:.1f}" y1="{y - vz * L / 2:.1f}" x2="{x + vx * L / 2:.1f}" y2="{y + vz * L / 2:.1f}" stroke="{col}" stroke-width="{2.6 if i == 0 else 1.8}" stroke-linecap="round"/>'
                     f'<circle cx="{x + vx * L / 2:.1f}" cy="{y + vz * L / 2:.1f}" r="{2.6 if i == 0 else 2}" fill="{col}"/>')
        s.append(T(x0 + 2, y0 - 5, names[mode], 12, 'start', INK, 700))
        yy = y0 + bz * sc + 14
        s.append(T(x0, yy, 'leader weight w', 11, 'start', MUTED)); s.append(T(x0 + cw - 4, yy, 'dist · align · p · in box', 11, 'end', MUTED))
        for r in [r for r in t['rows'] if r['mode'] == mode]:
            yy += 13
            s.append(T(x0, yy, f'w = {r["w"]}', 11, 'start', INK, 400, mono=True))
            s.append(T(x0 + cw - 4, yy, f'{r["dist"]:.1f} BL · {r["align"]:+.2f} · {r["p"]:.2f} · {"yes" if r["inside"] else "no"}', 11, 'end', INK, 400, mono=True))
    # the startle trace: median distance to the leader, 5-tick moving average, 6 s before to 12 s after the dart (tick 500)
    x0 = 8 + 3 * (cw + 8)
    cy0, ch = 28, bz * sc - 12
    cwid = cw - 4
    s.append(T(x0, 22, 'Startle: distance to the leader', 12, 'start', INK, 700))
    s.append(f'<rect x="{x0}" y="{cy0}" width="{cwid:.1f}" height="{ch:.1f}" fill="#ffffff" stroke="{GRID}"/>')
    lo, hi = 440, 620
    sm = {}
    for mode in ('swarm', 'torus', 'school'):
        tr = np.array(t['snaps'][mode]['trace'])
        sm[mode] = np.convolve(tr, np.ones(5) / 5, mode='same')
    tmax = max(v[lo:hi].max() for v in sm.values())
    for mode, col in (('swarm', ORANGE), ('torus', PURPLE), ('school', ACC)):
        pts = ' '.join(f'{x0 + (i - lo) / (hi - lo) * cwid:.1f},{cy0 + ch - sm[mode][i] / tmax * ch:.1f}' for i in range(lo, hi, 2))
        s.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2"/>')
    sx = x0 + (500 - lo) / (hi - lo) * cwid
    s.append(f'<line x1="{sx:.1f}" y1="{cy0}" x2="{sx:.1f}" y2="{cy0 + ch:.1f}" stroke="{RED}" stroke-width="1.4" stroke-dasharray="4 3"/>')
    s.append(T(sx - 4, cy0 + 12, 'dart', 11, 'end', RED, 700))
    ly = cy0 + ch + 13
    for i, (mode, col) in enumerate((('swarm', ORANGE), ('torus', PURPLE), ('school', ACC))):
        s.append(f'<rect x="{x0 + i * 62}" y="{ly - 9}" width="10" height="10" fill="{col}"/>'); s.append(T(x0 + i * 62 + 14, ly, mode, 11, 'start', INK))
    s.append(T(x0, ly + 13, f'−6 s to +12 s; top = {tmax:.0f} BL; one seed', 11, 'start', MUTED))
    H = int(bz * sc + 20 + 4 * 13 + 22)
    c1, w1 = chip(8, H - 6, 'ours', 'the Forth core in the tank’s real box (w = 3, seed 1 drawn; the table is the mean of 3 seeds; “no” = a fish strayed more than 0.5 BL out)')
    s.append(c1)
    return ''.join(s), W, H


# ── Sources ──────────────────────────────────────────────────────────────────
def footer_html():
    def item(k):
        v = D.SOURCES[k]
        head = f'<a href="{FP.html.escape(v["url"])}">{esc(v["short"])}</a>' if v['url'] else esc(v['short'])
        tag = FP.chip_html('verified' if v['opened'] else 'unverified') if k != 'S5' else FP.chip_html('ours')
        return f'<li><b>{k}</b> {head}<br>{tag} <span class="sub">{esc(v["backs"])}</span></li>'
    keys = list(D.SOURCES)
    cols = [''.join(item(k) for k in keys[i:i + 2]) for i in (0, 2, 4)]
    how = ('<p><b>How to read the chips</b></p>'
           f'<p>{FP.chip_html("verified")} the source was opened; the number is on its page<br>'
           f'{FP.chip_html("unverified")} from a summary, or not opened<br>'
           f'{FP.chip_html("ours")} our own choice, maths or measurement</p>'
           f'<p class="sub">Not claimed: that real clownfish school (they do not), that our sweep shows the paper’s hysteresis (it is too coarse), or that the school is in the game: it is not wired in yet, only timed there. Data dated {D.DATA_DATE}.</p>')
    return ('<section class="panel foot" id="panel-src"><div class="bar"><b>Sources</b> · live links in the PDF; what could not be verified is marked</div>'
            f'<div class="cols">{"".join(f"<ul class=srcl>{c}</ul>" for c in cols)}<div class="how">{how}</div></div></section>')


PANELS = {
    'A': ('Four collective states from one rule, simulated here (N = 100, the paper’s r_r, α, θ, s, σ)', panel_a),
    'B': ('The model: three zones and a blind volume', panel_b),
    'C': ('The map: p_group over the two zone widths', panel_c),
    'D': ('The rule in eight lines, and the Forth word that does each', panel_d),
    'F': ('The Forth core, school.fth: the four rule words, and what they cost', panel_f),
    'G': ('The Forth, running in the tank: swarm, torus, school, and a startle', panel_g),
}


def panel_html(letter):
    title, fn = PANELS[letter]
    svg, w, h = fn()
    return (f'<section class="panel" id="panel-{letter.lower()}" style="width:{w}px"><div class="bar"><b>{letter}</b> · {esc(title)}</div>'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family=\'{FONT_SANS}\'>{svg}</svg></section>')


def header_html():
    return ('<header><div><h1>How a school swarms</h1><div class="sub">collective motion for the aquarium level’s ten followers · the Couzin zone model, '
            'measured against our own Forth implementation</div></div><div class="scale">Lengths are in <b>body lengths</b> (BL; a fish is 3.5 in). '
            'The tank is 13.4 × 3.4 × 4.7 BL inside. A <b>school</b> is polarised (p_group near 1); a <b>swarm</b> is not (p near 0.1): '
            'moving one zone width, Δr_o, switches between them.</div></header>')


def build_html():
    FP.TEXT_PAIRS.clear(); FP.TEXT_SIZES.clear()
    body = [header_html(), f'<div class="row">{panel_html("A")}</div>']
    body.append(f'<div class="row">{panel_html("B")}{panel_html("C")}</div>')
    body += [f'<div class="row">{panel_html("D")}</div>', f'<div class="row">{panel_html("F")}</div>', f'<div class="row">{panel_html("G")}</div>', footer_html()]
    doc = ('<!DOCTYPE html>\n<!-- Generated by make_swarm_poster.py from swarm_data.py, sweep.json, tank.json, measured.json and school.fth: edit those, not this file. -->\n'
           '<html lang="en"><head><meta charset="utf-8"><title>How a school swarms: collective-motion poster (A3)</title>'
           f'<style>{FP.CSS.replace('height:76px','height:68px').replace('padding:10mm;','padding:7mm 10mm;') + 'ul.srcl{width:218px} .foot .cols{gap:10px} .how{min-width:330px}'}</style></head><body><div class="page">{"".join(body)}</div>{FP.FIT_SCRIPT}</body></html>\n')
    return FP.polish(doc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split('\n\n', 1)[1])
    ap.add_argument('--out-dir', type=Path, default=HERE)
    ap.add_argument('--html-only', action='store_true', help='write data.json and poster.html, skip Chrome and pdftoppm')
    ap.add_argument('--resim', action='store_true', help='recompute the four snapshots (about 20 s) instead of reading snapshots.json')
    args = ap.parse_args(argv)
    if args.resim:
        snapshots(True)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    rows = D.rows()
    (out / 'data.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
    html_path = out / 'poster.html'
    html_path.write_text(build_html(), encoding='utf-8')
    print(f'wrote {html_path} ({html_path.stat().st_size // 1024} KB), {len(rows)} rows')
    if args.html_only:
        return 0
    FP.render_pdf(html_path, out / 'poster.pdf')
    FP.render_png(out / 'poster.pdf', out / 'poster.png')
    print(f'wrote {out / "poster.pdf"}, {out / "poster.png"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
