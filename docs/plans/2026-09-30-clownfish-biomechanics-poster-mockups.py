#!/usr/bin/env python3
"""Generate the clownfish-biomechanics-poster plan mockups (self-contained 1440x900 HTML, inline SVG).

Usage: 2026-09-30-clownfish-biomechanics-poster-mockups.py [OUT_DIR]
       (default OUT_DIR: 2026-09-30-clownfish-biomechanics-poster/ next to this script)

Writes poster-layout.html and diagram-detail.html. Render the same-name PNGs with:
  google-chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1440,900 \\
      --screenshot=<name>.png file://<abs path>/<name>.html
All curves are computed here from the formulas listed in the plan, not hand-drawn.
Plan: docs/plans/2026-09-30-clownfish-biomechanics-poster.md
"""
import math, sys, pathlib

if any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__)
    sys.exit(0)
OUT = (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1
       else pathlib.Path(__file__).resolve().parent / "2026-09-30-clownfish-biomechanics-poster")
OUT.mkdir(parents=True, exist_ok=True)

# ---- clownfish art, copied from 2026-09-30-aquarium-level-mockups.py (same approved look) ----
BODY = [(50,0),(38,-13),(22,-21),(4,-27),(-16,-25),(-34,-15),(-44,-7),(-62,-23),(-73,-15),
        (-69,0),(-73,15),(-62,23),(-44,7),(-34,13),(-12,25),(16,23),(38,14)]

def pts(p, s=1.0, ox=0.0, oy=0.0, flip=False):
    return " ".join(f"{ox + (-x if flip else x) * s:.3f},{oy + y * s:.3f}" for x, y in p)

def fish(cx, cy, s, flip=False, uid="f", tilt=0):
    """Faceted clownfish, facing +x (right) unless flip. Coordinates already in scene units."""
    P = lambda p: pts(p, 1, 0, 0, flip)
    fx = -1 if flip else 1
    facets = [
        ([(50,0),(38,-13),(22,-21),(8,0)], "#ff8a2a"),
        ([(22,-21),(4,-27),(-16,-25),(8,0)], "#ff9d47"),
        ([(-16,-25),(-34,-15),(-44,-7),(-20,0),(8,0)], "#f0731a"),
        ([(50,0),(8,0),(16,23),(38,14)], "#e8660f"),
        ([(8,0),(-20,0),(-12,25),(16,23)], "#f07a22"),
        ([(-20,0),(-44,7),(-34,13),(-12,25)], "#d95c0c"),
    ]
    g = [f'<g transform="translate({cx:.3f},{cy:.3f}) rotate({tilt}) scale({s:.5f})">']
    g.append(f'<clipPath id="{uid}c"><polygon points="{P(BODY)}"/></clipPath>')
    # tail fin + dorsal + pectoral (behind/around body)
    g.append(f'<polygon points="{P([(-44,-7),(-62,-23),(-73,-15),(-69,0),(-73,15),(-62,23),(-44,7)])}" fill="#e2620e" stroke="#111" stroke-width="2.4"/>')
    g.append(f'<polygon points="{P([(20,-21),(8,-38),(-6,-40),(-24,-30),(-16,-25),(4,-27)])}" fill="#f47c1d" stroke="#111" stroke-width="2.4"/>')
    g.append(f'<polygon points="{P(BODY)}" fill="#ff8a2a"/>')
    for poly, col in facets:
        g.append(f'<polygon points="{P(poly)}" fill="{col}" clip-path="url(#{uid}c)"/>')
    # three white bands with black edging: head, mid, tail
    for x0, x1 in ((24, 33), (-7, 6), (-40, -34)):
        a, b = sorted((fx * x0, fx * x1))
        g.append(f'<g clip-path="url(#{uid}c)"><rect x="{a-2.6:.2f}" y="-40" width="{b-a+5.2:.2f}" height="80" fill="#111"/>'
                 f'<rect x="{a:.2f}" y="-40" width="{b-a:.2f}" height="80" fill="#f6f4ee"/></g>')
    g.append(f'<polygon points="{P(BODY)}" fill="none" stroke="#111" stroke-width="2.4" stroke-linejoin="round"/>')
    ex = fx * 38
    g.append(f'<circle cx="{ex}" cy="-6" r="4.4" fill="#fff" stroke="#111" stroke-width="1.6"/><circle cx="{ex + fx*1.2}" cy="-6" r="2.2" fill="#111"/>')
    g.append(f'<polygon points="{P([(14,10),(0,17),(-8,13),(2,7)])}" fill="#ffb066" stroke="#111" stroke-width="1.6"/>')
    g.append('</g>')
    return "".join(g)


# ------------------------------------------------------------------ helpers
INK, MUTED, GRID, ACC = "#1d2733", "#5c6b7a", "#dfe5ec", "#0f7c93"
CHIP = {"verified": ("#1f8a4c", "#e3f4ea"), "unverified": ("#b26a00", "#fff2d9"), "ours": ("#2b5fd9", "#e4ecff")}
FONT = 'font-family="ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif"'

def T(x, y, s, size=13, anchor="start", fill=INK, weight="400", extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}" {extra}>{s}</text>'

def chip(x, y, kind, label=None):
    fg, bg = CHIP[kind]
    label = label or kind
    w = 12 + 6.4 * len(label)
    return (f'<g><rect x="{x:.1f}" y="{y-13:.1f}" width="{w:.1f}" height="18" rx="9" fill="{bg}" stroke="{fg}" stroke-width="1"/>'
            f'{T(x + w/2, y, label, 11, "middle", fg, "700")}</g>')

def arrow(x1, y1, x2, y2, col=INK, w=1.6):
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = 8 * math.cos(a), 8 * math.sin(a)
    px, py = -4 * math.sin(a), 4 * math.cos(a)
    return (f'<g stroke="{col}" stroke-width="{w}" fill="{col}"><line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2 - hx*0.6:.1f}" y2="{y2 - hy*0.6:.1f}"/>'
            f'<polygon stroke="none" points="{x2:.1f},{y2:.1f} {x2-hx+px:.1f},{y2-hy+py:.1f} {x2-hx-px:.1f},{y2-hy-py:.1f}"/></g>')

def dim(x1, y1, x2, y2, col=MUTED):
    return arrow(x1, y1, x2, y2, col, 1.2) + arrow(x2, y2, x1, y1, col, 1.2)

def panel_title(letter, title, w):
    return (f'<rect x="0" y="0" width="{w}" height="28" fill="{ACC}"/>'
            + T(12, 19, f"{letter} · {title}", 15, "start", "#fff", "700"))

def axes(x0, y0, w, h, xmax, ymax, xt, yt, xlabel, ylabel, fmtx=lambda v: f"{v:g}", fmty=lambda v: f"{v:g}"):
    s = []
    for v in xt:
        X = x0 + v / xmax * w
        s.append(f'<line x1="{X:.1f}" y1="{y0}" x2="{X:.1f}" y2="{y0-h}" stroke="{GRID}"/>' + T(X, y0 + 15, fmtx(v), 11, "middle", MUTED))
    for v in yt:
        Y = y0 - v / ymax * h
        s.append(f'<line x1="{x0}" y1="{Y:.1f}" x2="{x0+w}" y2="{Y:.1f}" stroke="{GRID}"/>' + T(x0 - 6, Y + 4, fmty(v), 11, "end", MUTED))
    s.append(f'<line x1="{x0}" y1="{y0}" x2="{x0+w}" y2="{y0}" stroke="{INK}"/><line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0-h}" stroke="{INK}"/>')
    s.append(T(x0 + w / 2, y0 + 30, xlabel, 12, "middle", INK, "600"))
    s.append(f'<text x="{x0-40}" y="{y0-h/2}" font-size="12" text-anchor="middle" fill="{INK}" font-weight="600" transform="rotate(-90 {x0-40} {y0-h/2})">{ylabel}</text>')
    return "".join(s)

# ------------------------------------------------------------------ A: travelling body wave (1300 x 380)
def diag_a():
    L_PX, XH, CY = 700.0, 1110.0, 200.0
    U = L_PX / 123.0
    lam = 1.0
    amp = lambda s: 0.1 * (0.1 + 0.9 * s * s)          # half-amplitude in body lengths; 0.1 at the tail (A = 0.2 L peak-to-peak)
    def deform(phase):
        out = []
        for (x, y) in BODY:
            s = min(max((50 - x) / 123.0, 0), 1)
            X = XH - s * L_PX
            Y = CY + y * U + amp(s) * L_PX * math.sin(2 * math.pi * (s / lam - phase))
            out.append((X, Y))
        return " ".join(f"{a:.1f},{b:.1f}" for a, b in out)
    pal = ["#2b5fd9", "#1e88c8", "#0f9c8f", "#3aa657", "#98a81f", "#d29a12", "#d5651a", "#c23a3a"]
    s = [f'<rect width="1300" height="425" fill="#fff"/>', panel_title("A", "Body wave: amplitude grows from head to tail; wavelength ≈ one body length", 1300)]
    s.append(f'<polygon points="{deform(0.0)}" fill="#ffb066" fill-opacity=".55" stroke="{INK}" stroke-width="1.6" stroke-linejoin="round"/>')
    s.append(f'<polygon points="{deform(0.25)}" fill="none" stroke="{INK}" stroke-width="1" stroke-dasharray="5 4" stroke-linejoin="round"/>')
    for k in range(8):
        d = " ".join(f"{XH - t/60*L_PX:.1f},{CY + amp(t/60)*L_PX*math.sin(2*math.pi*(t/60/lam - k/8)):.1f}" for t in range(61))
        s.append(f'<polyline points="{d}" fill="none" stroke="{pal[k]}" stroke-width="2.4"/>')
    for sign in (1, -1):
        d = " ".join(f"{XH - t/60*L_PX:.1f},{CY + sign*amp(t/60)*L_PX:.1f}" for t in range(61))
        s.append(f'<polyline points="{d}" fill="none" stroke="{MUTED}" stroke-width="1.2" stroke-dasharray="6 5"/>')
    # dimensions
    s.append(dim(XH - L_PX, 400, XH, 400)); s.append(T(XH - L_PX / 2, 392, "L = body length: 3.5 in (8.9 cm) real · 0.889 m at ×10", 13, "middle", MUTED, "600"))
    s.append(dim(XH - L_PX - 24, CY - 0.1 * L_PX, XH - L_PX - 24, CY + 0.1 * L_PX))
    s.append(T(XH - L_PX - 34, CY - 6, "A ≈ 0.2 L", 14, "end", INK, "700")); s.append(T(XH - L_PX - 34, CY + 12, "peak-to-peak", 12, "end", MUTED))
    s.append(arrow(XH + 20, 56, XH + 90, 56, ACC, 2.4)); s.append(T(XH + 20, 74, "swimming direction", 12, "start", ACC, "600"))
    s.append(arrow(XH - 240, 70, XH - 60, 70, MUTED, 1.4)); s.append(T(XH - 150, 62, "wave travels head → tail", 12, "middle", MUTED))
    # legend
    for k in range(8):
        s.append(f'<rect x="{40 + k*30}" y="60" width="26" height="8" fill="{pal[k]}"/>')
    s.append(T(40, 84, "snapshots at 0, ⅛, … ⅞ of a beat cycle", 11, "start", MUTED))
    s.append(T(40, 104, "solid fill: phase 0 · dashed outline: phase ¼", 11, "start", MUTED))
    s.append(T(40, 128, "y(s, t) = A(s) · L · sin[ 2π ( s/λ − f·t ) ]", 12.5, "start", INK, "600", 'font-family="ui-monospace,Menlo,monospace"'))
    s.append(T(40, 148, "A(s) = 0.1 · (0.1 + 0.9 s²),  λ = L", 13, "start", MUTED, "400", 'font-family="ui-monospace,Menlo,monospace"'))
    s.append(chip(40, 172, "ours", "envelope shape: illustrative")); s.append(chip(40, 196, "unverified", "A ≈ 0.2 L, λ ≈ L: widely cited"))
    return "".join(s)

# ------------------------------------------------------------------ B: Strouhal (620 x 300)
def diag_b():
    x0, y0, w, h = 70, 262, 500, 170
    X = lambda u: x0 + u / 6 * w
    Y = lambda f: y0 - f / 12 * h
    s = [f'<rect width="620" height="300" fill="#fff"/>', panel_title("B", "Tail-beat frequency follows speed (Strouhal number)", 620)]
    s.append(axes(x0, y0, w, h, 6, 12, range(0, 7), range(0, 13, 2), "swimming speed U  (body lengths / s)", "tail-beat f (Hz)"))
    lo = f'{X(0)},{Y(0)} {X(6)},{Y(6)} {X(6)},{Y(12)}'
    s.append(f'<polygon points="{lo}" fill="#0f7c93" fill-opacity=".14"/>')
    for st, col in ((0.2, "#3aa657"), (0.3, "#0f7c93"), (0.4, "#c23a3a")):
        s.append(f'<line x1="{X(0)}" y1="{Y(0)}" x2="{X(6)}" y2="{Y(5*st*6)}" stroke="{col}" stroke-width="2.2"/>')
        s.append(T(X(6) + 6, Y(5 * st * 6) + 4, f"St {st}", 12, "start", col, "700"))
    s.append(f'<line x1="{x0}" y1="{Y(10)}" x2="{x0+w}" y2="{Y(10)}" stroke="#7a2bd9" stroke-dasharray="6 4"/>')
    s.append(T(x0 + 6, Y(10) + 14, "20 fps ticks: Nyquist 10 Hz (5 Hz = 4 ticks/beat)", 11, "start", "#7a2bd9"))
    s.append(f'<circle cx="{X(3.43)}" cy="{Y(5.14)}" r="6" fill="#ff8a2a" stroke="{INK}" stroke-width="1.5"/>')
    s.append(T(X(3.43) + 10, Y(5.14) + 18, "game cruise: 3.4 BL/s ≈ 5 Hz", 12, "start", INK, "700"))
    s.append(T(x0, 50, "f = St · U / A ,  A = 0.2 L   ⇒   f ≈ 1.5 · U/L  (St 0.3)", 12, "start", INK, "600", 'font-family="ui-monospace,Menlo,monospace"'))
    s.append(chip(x0, 72, "verified", "St 0.2–0.4 (fish; trout 0.19–0.22)")); s.append(chip(x0 + 262, 72, "ours", "A = 0.2 L, St = 0.3"))
    return "".join(s)

# ------------------------------------------------------------------ C: burst and coast (620 x 300)
def burst_coast(v_mean=3.43, cycle=0.6, burst=0.3, tau=0.08, k=2.0, tmax=2.4, dt=0.005):
    def sim(vp):
        v, out = vp * 0.5, []
        t = 0.0
        while t <= tmax + 1e-9:
            ph = t % cycle
            inb = ph < burst
            out.append((t, v, inb))
            v += ((vp - v) / tau if inb else -k * v) * dt
            t += dt
        return out
    lo, hi = 1.0, 20.0
    for _ in range(50):
        mid = (lo + hi) / 2
        tr = sim(mid)
        m = sum(v for (t, v, _b) in tr if t >= cycle) / max(1, sum(1 for (t, _v, _b) in tr if t >= cycle))
        lo, hi = (mid, hi) if m < v_mean else (lo, mid)
    return sim((lo + hi) / 2), (lo + hi) / 2

def diag_c():
    tr, vp = burst_coast()
    x0, y0, w, h = 70, 200, 500, 105
    X = lambda t: x0 + t / 2.4 * w
    Y = lambda v: y0 - v / 8 * h
    s = [f'<rect width="620" height="300" fill="#fff"/>', panel_title("C", "Burst-and-coast: the natural small-fish gait", 620)]
    s.append(axes(x0, y0, w, h, 2.4, 8, [0, .6, 1.2, 1.8, 2.4], [0, 2, 4, 6, 8], "time (s)", "speed (BL/s)"))
    for c in range(4):
        s.append(f'<rect x="{X(c*0.6):.1f}" y="{y0-h}" width="{X(0.3)-x0:.1f}" height="{h}" fill="#ff8a2a" fill-opacity=".13"/>')
    s.append(f'<polyline points="{" ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v, _b in tr)}" fill="none" stroke="{ACC}" stroke-width="2.4"/>')
    s.append(f'<line x1="{x0}" y1="{Y(3.43)}" x2="{x0+w}" y2="{Y(3.43)}" stroke="{INK}" stroke-dasharray="5 4"/>')
    s.append(T(x0 + w - 4, Y(3.43) + 14, "mean 3.4 BL/s", 11, "end", INK))
    s.append(T(X(0.15), y0 - h - 4, "burst", 11, "middle", "#c25b00", "700")); s.append(T(X(0.45), y0 - h - 4, "coast", 11, "middle", MUTED, "700"))
    # tail-beat trace
    ty = 250
    pts_ = " ".join(f"{X(t):.1f},{ty - (14*math.sin(2*math.pi*5.14*t) if (t % 0.6) < 0.3 else 0):.1f}" for t in [i * 0.005 for i in range(481)])
    s.append(f'<polyline points="{pts_}" fill="none" stroke="#c25b00" stroke-width="1.6"/>')
    s.append(T(x0 - 6, ty + 4, "tail", 11, "end", MUTED))
    s.append(T(x0 + 6, 62 + 8, "cycle 0.6 s: burst 0.3 s (tail beats) · coast 0.3 s (body straight)", 12, "start", INK, "600"))
    s.append(chip(x0 - 30, 282, "verified", "Cd ratio ≈ 4 : 1 · ≈45 % saved (koi)"))
    s.append(chip(x0 + 300, 282, "ours", "cycle, burst share, drag 2.0/s"))
    return "".join(s)

# ------------------------------------------------------------------ D: pectoral fins (620 x 260)
def diag_d():
    s = [f'<rect width="620" height="260" fill="#fff"/>', panel_title("D", "Pectoral fins: clownfish swim with fins and tail together", 620)]
    x0, y0, w, h = 60, 200, 210, 130
    s.append(axes(x0, y0, w, h, 1, 6, [0, 1], [0, 2, 4, 6], "swimming intensity", "pectoral beat (Hz)", lambda v: "low" if v == 0 else "high"))
    s.append(f'<line x1="{x0}" y1="{y0 - 2.4/6*h}" x2="{x0+w}" y2="{y0 - 4.6/6*h}" stroke="{ACC}" stroke-width="2.6"/>')
    s.append(f'<circle cx="{x0}" cy="{y0 - 2.4/6*h}" r="5" fill="#ff8a2a" stroke="{INK}"/><circle cx="{x0+w}" cy="{y0 - 4.6/6*h}" r="5" fill="#ff8a2a" stroke="{INK}"/>')
    s.append(T(x0 + 8, y0 - 2.4/6*h + 18, "2.4", 12, "start", INK, "700")); s.append(T(x0 + w - 8, y0 - 4.6/6*h - 8, "4.6", 12, "end", INK, "700"))
    s.append(chip(x0 - 20, 60 + 6, "verified", "A. ocellaris, wave-surge trials"))
    # traces
    tx0, tw = 330, 260
    for row, (lab, ph, f) in enumerate((("low speed: alternating (left ↔ right)", math.pi, 2.4), ("higher speed: synchronous (in phase)", 0.0, 4.6))):
        cy = 96 + row * 78
        s.append(T(tx0, cy - 38, lab, 12, "start", INK, "600"))
        for side, col, p in (("L", "#c23a3a", 0.0), ("R", "#2b5fd9", ph)):
            d = " ".join(f"{tx0 + i/100*tw:.1f},{cy + (12 if side=='L' else 12)*-math.sin(2*math.pi*f*i/100 + p) + (0 if side=='L' else 0):.1f}" for i in range(101))
            s.append(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="2" {"stroke-dasharray=\"5 3\"" if side == "R" else ""}/>')
        s.append(T(tx0 + tw + 4, cy - 4, "L", 11, "start", "#c23a3a", "700")); s.append(T(tx0 + tw + 4, cy + 10, "R", 11, "start", "#2b5fd9", "700"))
    s.append(chip(tx0, 178, "unverified", "switch at ≈3–4 BL/s: another damselfish")); s.append(T(tx0, 200, "(Pomacentrus pavo beats 10.9–25 Hz: not the clownfish)", 11, "start", MUTED))
    s.append(T(tx0, 222, "game: fins scull alternately at rest, flare to brake, fold in a coast", 11, "start", INK))
    return "".join(s)

# ------------------------------------------------------------------ E: turning (620 x 260)
def arc_pts(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]

def diag_e():
    s = [f'<rect width="620" height="260" fill="#fff"/>', panel_title("E", "Turning: the head leads, the body bends (C-start / cruising turn)", 620)]
    cx, cy, R, Lb = 170, 150, 62, 96
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{MUTED}" stroke-dasharray="5 4"/>')
    s.append(f'<line x1="20" y1="{cy+R}" x2="{cx}" y2="{cy+R}" stroke="{MUTED}" stroke-dasharray="5 4"/><line x1="20" y1="{cy-R}" x2="{cx}" y2="{cy-R}" stroke="{MUTED}" stroke-dasharray="5 4"/>')
    for i, ang in enumerate((math.pi / 2, math.pi / 2 + 0.75, math.pi / 2 + 1.5, math.pi / 2 + 2.25, math.pi / 2 + 3.0)):
        ang_head = ang; span = Lb / R
        p = arc_pts(cx, cy, R, ang_head - span, ang_head, 16)
        s.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in p)}" fill="none" stroke="#ff8a2a" stroke-width="7" stroke-linecap="round" opacity="{0.35 + 0.13*i:.2f}"/>')
        hx, hy = p[-1]; s.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="4.5" fill="{INK}" opacity="{0.35 + 0.13*i:.2f}"/>')
    s.append(arrow(cx + R + 14, cy + 6, cx + R + 14, cy - 34, ACC, 2)); s.append(T(cx + R + 22, cy - 40, "head leads", 11, "start", ACC, "600"))
    s.append(dim(cx, cy, cx + R * math.cos(-0.7), cy + R * math.sin(-0.7), "#7a2bd9")); s.append(T(cx + 14, cy - 10, "R", 13, "start", "#7a2bd9", "700"))
    s.append(T(24, 236, "turning angle and radius R: definitions (Domenici & Blake 1997)", 11, "start", MUTED))
    # C-start inset
    base = 360
    labs = ("1 · straight", "2 · C-bend", "3 · counter-bend", "4 · glide, new heading")
    for i, lab in enumerate(labs):
        x = base + i * 65
        curv = (0.0, 2.4, -1.6, 0.0)[i]
        pts_ = []
        for j in range(11):
            u = j / 10
            pts_.append((x, 60 + u * 60))
        if curv:
            p2 = arc_pts(x + 30 * (-1 if curv > 0 else 1) * 0 , 90, 40 / abs(curv) * 1.0, 0, 0, 1)
        # body as quadratic curve
        ctrl = x + 22 * curv
        s.append(f'<path d="M {x} 48 Q {ctrl:.1f} 90 {x} 132" fill="none" stroke="#ff8a2a" stroke-width="8" stroke-linecap="round"/>')
        s.append(f'<circle cx="{x}" cy="48" r="4.5" fill="{INK}"/>')
        s.append(T(x, 152 + (i % 2) * 14, lab, 10, "middle", INK, "600"))
    s.append(T(base - 20, 200, "escape C-start: stage 1 bends the body into a C; larger fish need longer", 11, "start", INK))
    s.append(T(base - 20, 214, "for the C-bend but cover more distance", 11, "start", INK))
    s.append(chip(base - 20, 236, "verified", "definitions & stages")); s.append(chip(base + 130, 236, "ours", "radius: tuned"))
    return "".join(s)

# ------------------------------------------------------------------ F: frames and control (620 x 260)
def diag_f():
    s = [f'<rect width="620" height="260" fill="#fff"/>', panel_title("F", "Facing, motion and control", 620)]
    cx, cy = 110, 150
    s.append(f'<g transform="translate({cx},{cy}) rotate(-12)">' + fish(0, 0, 0.62, False, "dfF") + '</g>')
    s.append(arrow(cx + 24, cy - 8, cx + 130, cy - 40, ACC, 2.6)); s.append(T(cx + 120, cy - 50, "v ∥ nose", 13, "end", ACC, "700"))
    s.append(f'<line x1="{cx-70}" y1="{cy+8}" x2="{cx+90}" y2="{cy+8}" stroke="{MUTED}" stroke-dasharray="4 3"/>')
    s.append(T(cx + 92, cy + 12, "level", 10, "start", MUTED))
    s.append(f'<path d="M {cx+70} {cy+8} A 60 60 0 0 0 {cx+62} {cy-22}" fill="none" stroke="#7a2bd9" stroke-width="1.6"/>')
    s.append(T(cx + 78, cy - 6, "θ pitch", 11, "start", "#7a2bd9", "700"))
    s.append(T(24, 230, "ROTATION_C = yaw ψ · ROTATION_B = pitch θ (+ = nose DOWN) · ROTATION_A = roll φ (bank)", 10.5, "start", INK))
    s.append(T(24, 246, "the physics hull never turns; only the visible parts do", 10.5, "start", MUTED))
    labels = [("buttons → desired direction d", "ours"), ("target facing ψ*, θ* (pitch clamp ±35–45°)", "ours"),
              ("2nd-order filters: yaw, pitch, bank, speed", "ours"), ("burst / coast speed law", "verified"),
              ("v = V · (cosθ cosψ, cosθ sinψ, sinθ)", "ours"), ("XSPEED · YSPEED · ZSPEED", "ours")]
    bx = 260
    for i, (lab, kind) in enumerate(labels):
        y = 42 + i * 34
        fg, bg = CHIP[kind]
        s.append(f'<rect x="{bx}" y="{y}" width="230" height="26" rx="5" fill="{bg}" stroke="{fg}"/>' + T(bx + 8, y + 17, lab, 11.5, "start", INK, "600"))
        if i < len(labels) - 1:
            s.append(arrow(bx + 115, y + 26, bx + 115, y + 34, MUTED, 1.4))
    s.append(f'<rect x="510" y="76" width="96" height="40" rx="5" fill="{CHIP["verified"][1]}" stroke="{CHIP["verified"][0]}"/>' + T(514, 92, "tail: f = St·U/A", 11, "start", INK, "600") + T(514, 106, "A = 0.2 L", 11, "start", MUTED))
    s.append(f'<rect x="510" y="126" width="96" height="40" rx="5" fill="{CHIP["verified"][1]}" stroke="{CHIP["verified"][0]}"/>' + T(514, 142, "pectorals", 11, "start", INK, "600") + T(514, 156, "2.4 → 4.6 Hz", 11, "start", MUTED))
    s.append(arrow(490, 96, 510, 96, MUTED, 1.2)); s.append(arrow(490, 146, 510, 146, MUTED, 1.2))
    return "".join(s)

# ------------------------------------------------------------------ G: second-order responses (620 x 260)
def step_resp(z, tmax=10.0, dt=0.01):
    x, v, out = 0.0, 0.0, []
    t = 0.0
    while t <= tmax:
        out.append((t, x)); a = 1 - 2 * z * v - x; v += a * dt; x += v * dt; t += dt
    return out

def diag_g():
    x0, y0, w, h = 70, 205, 300, 140
    s = [f'<rect width="620" height="260" fill="#fff"/>', panel_title("G", "Smooth steering: second-order (spring-damper) filters", 620)]
    X = lambda t: x0 + t / 10 * w
    Y = lambda v: y0 - v / 1.5 * h
    s.append(axes(x0, y0, w, h, 10, 1.5, [0, 2, 4, 6, 8, 10], [0, 0.5, 1.0, 1.5], "time (× 1/ωₙ)", "response"))
    s.append(f'<rect x="{x0}" y="{Y(1.0)}" width="{w}" height="0" stroke="{INK}"/><line x1="{x0}" y1="{Y(1)}" x2="{x0+w}" y2="{Y(1)}" stroke="{INK}" stroke-dasharray="4 3"/>')
    cols = {0.3: "#c23a3a", 0.6: "#d29a12", 1.0: "#0f7c93", 1.5: "#7a2bd9"}
    for z, col in cols.items():
        tr = step_resp(z)
        s.append(f'<polyline points="{" ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in tr[::5])}" fill="none" stroke="{col}" stroke-width="2.2"/>')
    ys = 100
    for z, col in cols.items():
        os_ = math.exp(-math.pi * z / math.sqrt(1 - z * z)) * 100 if z < 1 else 0
        lab = f"ζ = {z:g}: " + (f"{os_:.0f} % overshoot" if z < 1 else ("critically damped" if z == 1.0 else "over-damped"))
        s.append(f'<rect x="405" y="{ys - 10}" width="12" height="4" fill="{col}"/>' + T(422, ys - 4, lab, 12, "start", INK, "600")); ys += 22
    s.append(T(405, ys + 6, "overshoot = exp(−πζ / √(1−ζ²))", 11.5, "start", MUTED, "400", 'font-family="ui-monospace,Menlo,monospace"'))
    s.append(T(405, ys + 32, "start: yaw ζ ≈ 0.7 · pitch ζ = 1", 12, "start", INK, "600")); s.append(T(405, ys + 48, "bank ζ ≈ 0.6 · speed ζ = 1", 12, "start", INK, "600"))
    s.append(chip(405, ys + 74, "ours", "tunable; judged by the video"))
    return "".join(s)

DIAGS = {"A": (diag_a, 1300, 425), "B": (diag_b, 620, 300), "C": (diag_c, 620, 300), "D": (diag_d, 620, 260),
         "E": (diag_e, 620, 260), "F": (diag_f, 620, 260), "G": (diag_g, 620, 260)}

def place(letter, x, y, w):
    fn, dw, dh = DIAGS[letter]
    sc = w / dw
    return (f'<g transform="translate({x:.1f},{y:.1f}) scale({sc:.4f})"><rect width="{dw}" height="{dh}" fill="#fff"/>{fn()}'
            f'<rect width="{dw}" height="{dh}" fill="none" stroke="{GRID}" stroke-width="{1/sc:.2f}"/></g>'), dh * sc

CSS = """*{box-sizing:border-box}
body{margin:0;width:1440px;height:900px;overflow:hidden;background:#0e141b;color:#dce6ee;font:15px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;align-items:center;gap:12px;padding:14px 24px;border-bottom:1px solid #26323e;background:#141c25}
header h1{margin:0;font-size:16px;font-weight:600}
header .tag{margin-left:auto;font:600 11px ui-monospace,Menlo,monospace;letter-spacing:.04em;color:#8fa1b2;border:1px solid #2c3a48;border-radius:10px;padding:2px 8px}
.cap{font-size:13px;color:#9db0c0}.cap b{color:#e8f1f8}
table{border-collapse:collapse;font-size:13px}td,th{padding:5px 10px;border-bottom:1px solid #26323e;text-align:left;vertical-align:top}
th{color:#8fa1b2;font-weight:600}code{font:12px ui-monospace,Menlo,monospace;color:#9fd8e8}
.c{display:inline-block;border-radius:9px;padding:0 8px;font-size:11px;font-weight:700;border:1px solid}
.v{color:#1f8a4c;background:#e3f4ea;border-color:#1f8a4c}.u{color:#b26a00;background:#fff2d9;border-color:#b26a00}.o{color:#2b5fd9;background:#e4ecff;border-color:#2b5fd9}"""

def page(title, body):
    return (f'<!DOCTYPE html>\n<!-- Plan mockup: self-contained, 1440x900. Generated; edit the script, not this file. -->\n<html lang="en"><head><meta charset="utf-8">'
            f'<title>Mockup — {title}</title><style>{CSS}</style></head><body><header><h1>{title}</h1><span class="tag">MOCKUP — NOT SHIPPED</span></header>{body}</body></html>\n')

# ------------------------------------------------------------------ mockup 1: the whole A3 poster
def mock_poster():
    PW, PH = 560, 792          # A3 portrait 297 x 420 mm at 1.885 px/mm
    px, py = 40, 62
    s = [f'<rect x="{px+6}" y="{py+8}" width="{PW}" height="{PH}" fill="#000" opacity=".45"/><rect x="{px}" y="{py}" width="{PW}" height="{PH}" fill="#fff"/>']
    m = 12
    s.append(f'<rect x="{px}" y="{py}" width="{PW}" height="46" fill="#0f2a3a"/>')
    s.append(T(px + m, py + 22, "How a clownfish swims", 19, "start", "#fff", "800"))
    s.append(T(px + m, py + 38, "the biomechanics behind the aquarium level's fish rig · Amphiprion ocellaris · A3", 10, "start", "#b9d3e0"))
    s.append(f'<g transform="translate({px+PW-80},{py+24}) scale(.55)">{fish(0, 0, 1.0, False, "hd")}</g>')
    y = py + 46 + 8
    g, hh = place("A", px + m, y, PW - 2 * m); s.append(g); y += hh + 8
    colw = (PW - 2 * m - 8) / 2
    for a, b in (("B", "C"), ("D", "E"), ("F", "G")):
        g1, h1 = place(a, px + m, y, colw); g2, h2 = place(b, px + m + colw + 8, y, colw); s.append(g1 + g2); y += max(h1, h2) + 8
    # parameter table strip
    th = 128
    s.append(f'<rect x="{px+m}" y="{y}" width="{PW-2*m}" height="{th}" fill="#fff" stroke="{GRID}"/><rect x="{px+m}" y="{y}" width="{PW-2*m}" height="14" fill="{ACC}"/>')
    s.append(T(px + m + 5, y + 10.5, "H · Parameter table — every number, its unit, its source and how far it can be trusted", 8, "start", "#fff", "700"))
    rows = [("St = f·A/U", "0.2 – 0.4", "verified"), ("A / L (peak-to-peak)", "≈ 0.2", "unverified"), ("Cd burst : coast", "≈ 4 : 1", "verified"),
            ("energy saved, burst-coast", "≈ 45 %", "verified"), ("A. ocellaris pectoral beat", "2.4 → 4.6 Hz", "verified"), ("cycle 0.6 s, burst 0.3 s", "game", "ours"),
            ("pitch clamp", "±35–45°", "ours"), ("yaw ζ / pitch ζ", "0.7 / 1.0", "ours")]
    for i, (a, b, k) in enumerate(rows):
        rx = px + m + 6 + (i // 4) * ((PW - 2 * m) / 2); ry = y + 26 + (i % 4) * 25
        fg, bgc = CHIP[k]
        s.append(T(rx, ry, a, 8.5, "start", INK, "600") + T(rx + 128, ry, b, 8.5, "start", MUTED) + f'<rect x="{rx+200:.0f}" y="{ry-8}" width="52" height="11" rx="5" fill="{bgc}" stroke="{fg}"/>' + T(rx + 226, ry, k, 7.5, "middle", fg, "700"))
    y += th + 8
    s.append(f'<rect x="{px+m}" y="{y}" width="{PW-2*m}" height="{py+PH-y-m}" fill="#f4f7fa" stroke="{GRID}"/>')
    s.append(T(px + m + 5, y + 12, "Sources (clickable in the PDF) · what we could not verify · how to read the status chips", 8, "start", INK, "700"))
    for i in range(4):
        s.append(f'<rect x="{px+m+5}" y="{y+19+i*7}" width="{(PW-2*m-10)*(0.95-0.12*(i%3))}" height="2.5" fill="{GRID}"/>')
    # right column: legend
    lx = 640
    s.append(T(lx, 88, "The poster, panel by panel", 20, "start", "#e8f1f8", "700"))
    items = [("A", "Body wave: envelope and wavelength drawn from the formula, 8 phases overlaid on the fish"),
             ("B", "Strouhal chart: tail-beat frequency vs speed, our operating point, the 20 fps ceiling"),
             ("C", "Burst-and-coast speed trace with the tail-beat pulses underneath"),
             ("D", "Pectoral fins: 2.4 → 4.6 Hz and the alternating vs synchronous beat"),
             ("E", "Turning geometry and the C-start stages"),
             ("F", "Facing, velocity along the nose, and the control chain"),
             ("G", "Second-order responses: why damping ζ decides how a turn feels"),
             ("H", "Full parameter table with status chips and sources")]
    y2 = 116
    for l, t in items:
        s.append(f'<circle cx="{lx+12}" cy="{y2-5}" r="12" fill="{ACC}"/>' + T(lx + 12, y2, l, 14, "middle", "#fff", "800"))
        s.append(T(lx + 34, y2, t, 14, "start", "#dce6ee")); y2 += 34
    y2 += 6
    s.append(T(lx, y2, "Status chips — the honest part", 16, "start", "#e8f1f8", "700")); y2 += 26
    for k, txt in (("verified", "opened the paper's page; the number is on it"), ("unverified", "widely cited, or from a search summary; not confirmed"), ("ours", "a game tunable or our own maths, not biology")):
        s.append(chip(lx, y2, k) + T(lx + 96, y2, txt, 13, "start", "#dce6ee")); y2 += 26
    y2 += 12
    s.append(T(lx, y2, "Format", 16, "start", "#e8f1f8", "700")); y2 += 24
    for line in ("A3 portrait, 297 × 420 mm, one page, 10 mm margins", "self-contained HTML → PDF (vector, links live) → PNG preview",
                 "light background, prints on any office plotter; type ≥ 8 pt at A3", "generated by one script from the plan's formulas"):
        s.append(T(lx, y2, "•  " + line, 13, "start", "#9db0c0")); y2 += 21
    return page("Clownfish biomechanics poster: layout", f'<svg width="1440" height="843" viewBox="0 0 1440 843" style="position:absolute;top:57px;left:0" {FONT}><g transform="translate(0,-57)">{"".join(s)}</g></svg>')

# ------------------------------------------------------------------ mockup 2: diagrams at print scale
def mock_detail():
    s = []
    g, h = place("A", 40, 74, 1360); s.append(g)
    y = 74 + h + 14
    g, h2 = place("B", 40, y, 668); s.append(g)
    g, h3 = place("C", 732, y, 668); s.append(g)
    body = (f'<svg width="1440" height="843" viewBox="0 0 1440 843" style="position:absolute;top:57px;left:0" {FONT}><g transform="translate(0,-57)">{"".join(s)}'
            f'<text x="40" y="66" font-size="14" font-weight="600" fill="#e8f1f8">Three of the seven diagrams at print scale (an A3 panel is about 270 mm wide ≈ 1020 px)</text></g></svg>')
    return page("Clownfish biomechanics poster: diagrams A, B, C at print scale", body)

(OUT / "poster-layout.html").write_text(mock_poster(), encoding="utf-8")
(OUT / "diagram-detail.html").write_text(mock_detail(), encoding="utf-8")
print("ok")
