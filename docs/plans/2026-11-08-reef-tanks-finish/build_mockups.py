#!/usr/bin/env python3
"""Mockups for docs/plans/2026-11-08-reef-tanks-finish.md.

Writes three self-contained 1440x900 HTML mockups beside this script and,
with --png, a same-basename PNG for each (headless google-chrome):

  worms.html      Christmas tree worms: today's cast1 capture against the
                  rebuilt twin-spiral crowns, set into the Porites boulder
                  along its surface normals, with open/retracting/hidden states
  placement.html  front and side elevations, in world units, of where the
                  worms, clam, nudibranch and crusts sit today and after the fix
  skins.html      per-actor texture audit (today vs proposed skin) and the
                  repacked 16-cell atlas

"Today" panels embed crops of the committed cast1 captures
(docs/diagnostics/reef-cast1-performance-2026-11-08). The proposed worm
positions are computed here from the boulder ellipsoids in
wflevels/aquarium_thai_reef/reef/corals.py, so the drawing is the design.
Everything else is deterministic SVG (seed 20261108).
"""
from __future__ import annotations

import argparse
import base64
import io
import math
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CAPTURES = REPO / "docs/diagnostics/reef-cast1-performance-2026-11-08"
sys.path.insert(0, str(REPO / "wflevels/aquarium_thai_reef"))
from reef.life import worm_centers  # noqa: E402  (today's worm grid)

SEED = 20261108
WORM_ORIGIN_TODAY = (-2.75, -1.35, 2.0)   # generate.py worm_crown_origin
# Porites lobes, reef/corals.py hard_corals(): centre, radii
LOBES = (((-2.75, -.78, 1.75), (.72, .48, .43)),
         ((-2.25, -.72, 1.88), (.42, .40, .34)))
MORPHS = (  # realistic base, realistic tip, anime base, anime tip
    ("blue", "#2f63c9", "#9fc4ff", "#2a6cff", "#bfe0ff"),
    ("red", "#b8282e", "#ff9d7a", "#e8303a", "#ffc0a0"),
    ("orange", "#d9701f", "#ffd08a", "#ff8a1c", "#ffe0a0"),
    ("yellow", "#d8b62a", "#fff2a6", "#ffd52a", "#fff8c8"),
    ("white", "#d9dcd6", "#ffffff", "#f2f4f0", "#ffffff"),
    ("purple", "#7a3fa8", "#d4a8ff", "#9b4ee0", "#e6c8ff"),
    ("blue / white", "#2f63c9", "#ffffff", "#2a6cff", "#ffffff"),
    ("red / white", "#b8282e", "#ffffff", "#e8303a", "#ffffff"),
)

CSS = """
*{box-sizing:border-box}html,body{margin:0;width:1440px;height:900px;overflow:hidden}
body{background:#0d1620;color:#e7eef5;font:14px/1.35 'DejaVu Sans',system-ui,sans-serif}
h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:0 0 6px;color:#9fd3ff}
.sub{color:#9fb2c4;font-size:13px}.wrap{padding:18px 22px}
.panel{background:#132332;border:1px solid #23394d;border-radius:10px;padding:12px}
.bad{color:#ff8f8f}.good{color:#8fe3a2}.tag{display:inline-block;padding:1px 7px;border-radius:9px;font-size:12px;margin-right:4px}
.tag.bad{background:#3a1a1e}.tag.good{background:#173524}
img{display:block;border-radius:6px}
ul{margin:4px 0 0 18px;padding:0}li{margin:2px 0}
"""


def page(title: str, body: str) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
            f"<meta name='viewport' content='width=1440'><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")


def crop_b64(src: str, box, size, quality=82) -> str:
    from PIL import Image
    im = Image.open(CAPTURES / src / "input-frame-001.png").convert("RGB")
    im = im.crop(box).resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


# ───────────────────────────── worm placement (the design) ─────────────────

def normal_on(lobe, p):
    (c, r) = lobe
    n = [(p[i] - c[i]) / (r[i] * r[i]) for i in range(3)]
    m = math.sqrt(sum(v * v for v in n))
    return [v / m for v in n]


def proposed_worms(count=15):
    """Poisson-disk sample of tube mouths on the camera-facing upper surface.

    Rules (see plan W1): normal faces the camera (n.y <= -0.35) and is not
    downward (n.z >= -0.1); mouths >= 0.14 apart; 11 on the main lobe and 4
    on the small lobe; mouths inside the other lobe are rejected.
    Crown axis = normalize(n + 0.35 * up): tilted toward the light.
    """
    rng = random.Random(SEED)
    out = []
    quota = (11, 4)
    for li, lobe in enumerate(LOBES):
        c, r = lobe
        tries = 0
        placed = 0
        while placed < quota[li] and tries < 20000:
            tries += 1
            th = rng.uniform(0, math.tau)
            ph = math.acos(rng.uniform(-1, 1))
            u = (math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph))
            p = tuple(c[i] + r[i] * u[i] for i in range(3))
            n = normal_on(lobe, p)
            if n[1] > -.35 or n[2] < 0:
                continue
            other = LOBES[1 - li]
            if sum(((p[i] - other[0][i]) / other[1][i]) ** 2 for i in range(3)) < 1:
                continue
            if any(math.dist(p, q["p"]) < .14 for q in out):
                continue
            axis = [n[0], n[1], n[2] + .35]
            m = math.sqrt(sum(v * v for v in axis))
            axis = [v / m for v in axis]
            out.append({"p": p, "n": n, "axis": axis, "lobe": li,
                        "morph": len(out) % len(MORPHS),
                        "size": rng.uniform(.85, 1.2)})
            placed += 1
    return out


# ───────────────────────────── SVG drawing helpers ────────────────────────

def f(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def crown_svg(x, y, ang_deg, h, base, tip, anime=False, state="open"):
    """Twin spiral crowns drawn at (x, y), axis rotated ang_deg from up.

    h: crown height in px. state: open | half | hidden.
    """
    if state == "hidden":
        # Operculum (spined cap) closing the tube mouth.
        return (f"<g transform='translate({f(x)} {f(y)}) rotate({f(ang_deg)})'>"
                f"<ellipse cx='0' cy='0' rx='{f(h*.16)}' ry='{f(h*.06)}' fill='#e8e0cc' stroke='#7b6f5a' stroke-width='1'/>"
                f"<path d='M{f(-h*.10)} 0 l{f(h*.03)} {f(-h*.07)} M0 0 l0 {f(-h*.09)} M{f(h*.10)} 0 l{f(-h*.03)} {f(-h*.07)}' stroke='#7b6f5a' stroke-width='1.2'/></g>")
    k = .45 if state == "half" else 1.0
    hh = h * k
    parts = [f"<g transform='translate({f(x)} {f(y)}) rotate({f(ang_deg)})'>"]
    # Calcareous collar at the tube mouth.
    parts.append(f"<ellipse cx='0' cy='0' rx='{f(h*.20)}' ry='{f(h*.07)}' fill='#efe6d2' stroke='#9d8f72' stroke-width='1'/>")
    outline = "#101820" if anime else "none"
    for side in (-1, 1):
        cx = side * h * .12
        w0 = h * .15 * (1.15 if k < 1 else 1)
        # Cone body: the whorled radioles read as a feathery spiral cone.
        parts.append(f"<path d='M{f(cx-w0)} {f(-hh*.06)} L{f(cx)} {f(-hh)} L{f(cx+w0)} {f(-hh*.06)} "
                     f"Q{f(cx)} {f(hh*.03)} {f(cx-w0)} {f(-hh*.06)}Z' fill='{base}' stroke='{outline}' stroke-width='1.4'/>")
        # Fringe: radiole tips along both flanks (one path).
        d = []
        for t in range(9):
            fr = (t + .5) / 9
            yy = -hh * (.06 + .94 * fr)
            wv = w0 * (1 - fr)
            for sgn in (-1, 1):
                d.append(f"M{f(cx+sgn*wv*.85)} {f(yy)}L{f(cx+sgn*(wv+h*.035))} {f(yy+h*.03)}")
        parts.append(f"<path d='{''.join(d)}' stroke='{tip}' stroke-width='1' fill='none' opacity='.9'/>")
        # Helix: 5 turns from base to tip; front half bright, back half dim.
        front_d, back_d = [], []
        steps = 60
        prev_front = None
        for i in range(steps + 1):
            fr = i / steps
            ph = fr * 5 * math.tau + (0 if side < 0 else math.pi)
            yy = -hh * (.06 + .94 * fr)
            wv = w0 * (1 - fr) * .95
            x_, y_ = cx + wv * math.sin(ph), yy + wv * .28 * math.cos(ph)
            front = math.cos(ph) > 0
            target = front_d if front else back_d
            cmd = "L" if prev_front == front else "M"
            if cmd == "M" and target is not None and prev_front is not None:
                # continue the stroke across the boundary into the new half
                pass
            target.append(f"{cmd}{f(x_)} {f(y_)}")
            prev_front = front
        if back_d:
            back_d[0] = "M" + back_d[0][1:]
            parts.append(f"<path d='{''.join(back_d)}' stroke='{tip}' stroke-width='1' fill='none' opacity='.35'/>")
        if front_d:
            front_d[0] = "M" + front_d[0][1:]
            parts.append(f"<path d='{''.join(front_d)}' stroke='{tip}' stroke-width='{2.2 if h > 50 else 1.5}' fill='none' stroke-linecap='round'/>")
    parts.append("</g>")
    return "".join(parts)


# ───────────────────────────── 1 · worms.html ──────────────────────────────

def worms_html() -> str:
    today_r = crop_b64("realistic-2", (380, 540, 860, 760), (560, 257), 70)
    today_a = crop_b64("anime-1", (380, 540, 860, 760), (560, 257), 70)
    worms = proposed_worms()
    # Front elevation of the boulder: x -3.6..-1.7 -> px; z 1.2..2.4 -> px
    W, H = 760, 470
    x0, x1, z0, z1 = -3.62, -1.72, 1.22, 2.40
    sx = W / (x1 - x0)

    def P(x, z):
        return (x - x0) * sx, H - (z - z0) * sx

    svg = [f"<svg width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
           "<defs><radialGradient id='por' cx='.4' cy='.3' r='.8'><stop offset='0' stop-color='#d9a58f'/>"
           "<stop offset='1' stop-color='#9a6a5a'/></radialGradient>"
           "<pattern id='cal' width='9' height='9' patternUnits='userSpaceOnUse'><circle cx='4.5' cy='4.5' r='1.6' fill='#7d5446' opacity='.5'/></pattern></defs>",
           f"<rect width='{W}' height='{H}' fill='#3d4a3c'/>",
           f"<rect width='{W}' height='{H}' fill='url(#cal)' opacity='.15'/>"]
    for (c, r) in LOBES:
        cx, cy = P(c[0], c[2])
        svg.append(f"<ellipse cx='{f(cx)}' cy='{f(cy)}' rx='{f(r[0]*sx)}' ry='{f(r[2]*sx)}' fill='url(#por)'/>")
        svg.append(f"<ellipse cx='{f(cx)}' cy='{f(cy)}' rx='{f(r[0]*sx)}' ry='{f(r[2]*sx)}' fill='url(#cal)'/>")
    # back-to-front by y so nearer crowns overlap farther ones
    for w in sorted(worms, key=lambda w: -w["p"][1]):
        px, py = P(w["p"][0], w["p"][2])
        ang = math.degrees(math.atan2(w["axis"][0], w["axis"][2]))
        m = MORPHS[w["morph"]]
        svg.append(crown_svg(px, py, ang, 64 * w["size"], m[1], m[2]))
    svg.append(f"<text x='10' y='{H-10}' fill='#cfe' font-size='12'>front elevation, orthographic · 15 crowns, Poisson spacing ≥ 0.14 · axis = surface normal tilted toward the light</text></svg>")

    # States strip: section through the tube
    st = ["<svg width='375' height='200' viewBox='0 0 375 200'>",
          "<rect width='375' height='200' fill='#132332'/>"]
    for i, (state, label) in enumerate((("open", "Open"), ("half", "Snapping 0.15 s"), ("hidden", "Hidden · operculum"))):
        ox = 64 + i * 124
        st.append(f"<path d='M{ox-58} 150 Q{ox} 140 {ox+58} 150 L{ox+58} 200 L{ox-58} 200Z' fill='#b98270'/>")
        st.append(f"<rect x='{ox-6}' y='145' width='12' height='55' fill='#efe6d2' stroke='#9d8f72'/>")
        st.append(crown_svg(ox, 145, 0, 96, "#2f63c9", "#9fc4ff", state=state))
        st.append(f"<text x='{ox}' y='16' fill='#cfe' font-size='12' text-anchor='middle'>{label}</text>")
    st.append("<text x='6' y='34' fill='#9fb2c4' font-size='10.5'>section: tube buried in the coral; crown scales toward the mouth</text></svg>")

    # Morph palette, realistic vs anime
    pal = ["<svg width='375' height='200' viewBox='0 0 375 200'><rect width='375' height='200' fill='#132332'/>"]
    for i, m in enumerate(MORPHS):
        ox = 26 + i * 46
        pal.append(crown_svg(ox, 82, 0, 50, m[1], m[2]))
        pal.append(crown_svg(ox, 176, 0, 50, m[3], m[4], anime=True))
        pal.append(f"<text x='{ox}' y='98' fill='#9fb2c4' font-size='8.5' text-anchor='middle'>{m[0].replace(' / ', '/').replace('white', 'wht') if '/' in m[0] else m[0]}</text>")
    pal.append("<text x='4' y='14' fill='#9fb2c4' font-size='11'>8 colour morphs · realistic</text><text x='4' y='114' fill='#9fb2c4' font-size='11'>anime: 3 tones + outline</text></svg>")

    body = f"""
<div class='wrap'>
<h1>Christmas tree worms — today vs rebuilt</h1>
<div class='sub'>Spirobranchus sp. · 15 crowns on the Porites boulder · one DFRM v2 actor, 15 curves</div>
<div style='display:grid;grid-template-columns:584px 1fr;gap:16px;margin-top:12px'>
 <div style='display:flex;flex-direction:column;gap:10px'>
  <div class='panel'><h2>Today · cast1 realistic</h2><img src='{today_r}' width='560'></div>
  <div class='panel'><h2>Today · cast1 anime</h2><img src='{today_a}' width='560'>
   <ul style='margin-top:8px'>
    <li class='bad'>flat "pine-tree" cut-outs on white pegs, one plane facing the camera</li>
    <li class='bad'>rigid 5 × 3 grid floating 9–14 cm in front of the boulder; top row over bare rock</li>
    <li class='bad'>tan / pink / lilac borrowed from polyp, coralline and sponge tiles</li>
   </ul></div>
 </div>
 <div style='display:flex;flex-direction:column;gap:10px'>
  <div class='panel' style='padding:8px'><h2>Proposed · set into the coral, facing out along the surface</h2>{''.join(svg)}</div>
  <div style='display:grid;grid-template-columns:1fr 1fr;gap:10px'>
   <div class='panel' style='padding:6px'>{''.join(st)}</div>
   <div class='panel' style='padding:6px'>{''.join(pal)}</div>
  </div>
 </div>
</div></div>"""
    return page("Reef worms mockup", body)


# ───────────────────────────── 2 · placement.html ──────────────────────────

def placement_html() -> str:
    today = worm_centers(WORM_ORIGIN_TODAY)
    worms = proposed_worms()
    # Front elevation x -6..6, z 0..4  (1 unit = 100 px) ; side elevation y -2..1.5, z 0.4..3
    FW, FH = 860, 380
    fx0, fz0, fs = -4.9, .4, 860 / 5.0   # shows x -4.9..0.1

    def F(x, z):
        return (x - fx0) * fs, FH - (z - fz0) * fs

    fr = [f"<svg width='{FW}' height='{FH}'><rect width='{FW}' height='{FH}' fill='#0f2234'/>"]
    sx, sy = F(-6, .72)
    fr.append(f"<rect x='0' y='{f(sy)}' width='{FW}' height='{FH}' fill='#bdb79c'/>")
    for lo, hi in (((-5.0, .72), (-1.65, 2.5)),):
        a, b = F(*lo), F(*hi)
        fr.append(f"<rect x='{f(a[0])}' y='{f(b[1])}' width='{f(b[0]-a[0])}' height='{f(a[1]-b[1])}' fill='#4d5a49' rx='40'/>")
    for (c, r) in LOBES:
        cx, cy = F(c[0], c[2])
        fr.append(f"<ellipse cx='{f(cx)}' cy='{f(cy)}' rx='{f(r[0]*fs)}' ry='{f(r[2]*fs)}' fill='#c48f7c' stroke='#f2c3b0'/>")
    for (x, y, z) in today:
        a = F(x, z)
        fr.append(f"<rect x='{f(a[0]-4)}' y='{f(a[1]-4)}' width='8' height='8' fill='none' stroke='#ff6b6b' stroke-width='2'/>")
    for w in worms:
        a = F(w["p"][0], w["p"][2])
        b = F(w["p"][0] + w["axis"][0] * .16, w["p"][2] + w["axis"][2] * .16)
        fr.append(f"<line x1='{f(a[0])}' y1='{f(a[1])}' x2='{f(b[0])}' y2='{f(b[1])}' stroke='#6dff9a' stroke-width='2'/>"
                  f"<circle cx='{f(a[0])}' cy='{f(a[1])}' r='3.5' fill='#6dff9a'/>")
    # nudibranch today (sand) vs proposed (rock path)
    a = F(-4.0, 1.05); fr.append(f"<circle cx='{f(a[0])}' cy='{f(a[1])}' r='9' fill='none' stroke='#ff6b6b' stroke-width='2'/><text x='{f(a[0]+12)}' y='{f(a[1]+16)}' fill='#ffb3b3' font-size='12'>nudibranch today: on the sand</text>")
    path = [F(-4.55, 1.30), F(-4.25, 1.55), F(-3.95, 1.62), F(-3.62, 1.48)]
    fr.append("<polyline points='" + " ".join(f"{f(p[0])},{f(p[1])}" for p in path) + "' fill='none' stroke='#6dff9a' stroke-width='2' stroke-dasharray='6 4'/>")
    fr.append(f"<text x='{f(path[1][0]-60)}' y='{f(path[1][1]-14)}' fill='#a9ffc4' font-size='12'>nudibranch: crawl path on rock</text>")
    fr.append(f"<text x='10' y='20' fill='#cfe' font-size='13'>FRONT ELEVATION (x → , z ↑), left rock mass, world units ×10 scale</text>")
    fr.append(f"<text x='10' y='{FH-10}' fill='#333' font-size='12'>sand z = 0.72</text></svg>")

    # Side elevation y–z at x ≈ -2.75 (camera at y = -7.5, off the left)
    SW, SH = 470, 380
    sy0, sz0, ss = -1.9, .4, 470 / 2.6

    def Sd(y, z):
        return (y - sy0) * ss, SH - (z - sz0) * ss

    sd = [f"<svg width='{SW}' height='{SH}'><rect width='{SW}' height='{SH}' fill='#0f2234'/>"]
    a = Sd(-1.9, .72); sd.append(f"<rect x='0' y='{f(a[1])}' width='{SW}' height='{SH}' fill='#bdb79c'/>")
    a, b = Sd(-.25, .72), Sd(1.25, 2.5)
    sd.append(f"<rect x='{f(a[0])}' y='{f(b[1])}' width='{f(b[0]-a[0])}' height='{f(a[1]-b[1])}' fill='#4d5a49' rx='30'/>")
    c, r = LOBES[0]
    cx, cy = Sd(c[1], c[2])
    sd.append(f"<ellipse cx='{f(cx)}' cy='{f(cy)}' rx='{f(r[1]*ss)}' ry='{f(r[2]*ss)}' fill='#c48f7c' stroke='#f2c3b0'/>")
    for (x, y, z) in today:
        p = Sd(y, z)
        sd.append(f"<rect x='{f(p[0]-4)}' y='{f(p[1]-4)}' width='8' height='8' fill='none' stroke='#ff6b6b' stroke-width='2'/>")
    for w in worms:
        if w["lobe"]:
            continue
        p = Sd(w["p"][1], w["p"][2]); q = Sd(w["p"][1] + w["axis"][1] * .16, w["p"][2] + w["axis"][2] * .16)
        sd.append(f"<line x1='{f(p[0])}' y1='{f(p[1])}' x2='{f(q[0])}' y2='{f(q[1])}' stroke='#6dff9a' stroke-width='2'/><circle cx='{f(p[0])}' cy='{f(p[1])}' r='3.5' fill='#6dff9a'/>")
    gap_a, gap_b = Sd(-1.26, 1.4), Sd(-1.375, 1.4)
    sd.append(f"<line x1='{f(gap_a[0])}' y1='{f(gap_a[1])}' x2='{f(gap_b[0])}' y2='{f(gap_b[1])}' stroke='#ffd166' stroke-width='2'/>"
              f"<text x='{f(gap_b[0]-6)}' y='{f(gap_b[1]+18)}' fill='#ffd166' font-size='12'>9–14 cm of open water</text>")
    sd.append("<text x='10' y='20' fill='#cfe' font-size='13'>SIDE ELEVATION at x = −2.75 (y → , z ↑)</text>"
              f"<text x='10' y='{SH-60}' fill='#9fb2c4' font-size='12'>← camera at y = −7.5</text></svg>")

    rows = [
        ("Christmas tree worms", "grid at y −1.35…−1.40, in front of the boulder (front face y −1.26)", "on the two Porites lobes, axis along the surface normal"),
        ("Worm anchor", "actor-map <code>tree_worms</code> (−0.18, −0.15, 1.20) ≠ placed origin (−2.75, −1.35, 2.0)", "one table in <code>scene.py</code>; generator and director read it"),
        ("Giant clam", "mantle on grey stilts above the sand", "valves sunk 40 % into the sand, mantle at the gape"),
        ("Nudibranch", "black disc on the sand (−4.0, −1.65, 1.05)", "on rock, crawling an authored path"),
        ("Encrusting crusts", "flat ellipses offset from the rock", "projected onto the rock surface, ≤ 1 cm proud"),
    ]
    tr = "".join(f"<tr><td>{a}</td><td class='bad'>{b}</td><td class='good'>{c}</td></tr>" for a, b, c in rows)
    body = f"""
<div class='wrap'>
<h1>Placement — what floats today and where it goes</h1>
<div class='sub'>Red squares: today's worm positions (generate.py). Green: proposed tube mouths with crown axes. Coordinates from the generator, not hand-drawn.</div>
<div style='display:grid;grid-template-columns:884px 1fr;gap:14px;margin-top:12px'>
 <div class='panel' style='padding:8px'>{''.join(fr)}</div>
 <div class='panel' style='padding:8px'>{''.join(sd)}</div>
</div>
<div class='panel' style='margin-top:12px'>
<table style='width:100%;border-collapse:collapse;font-size:13px'>
<tr style='color:#9fd3ff;text-align:left'><th style='width:190px'>Actor</th><th>Today</th><th>After W3</th></tr>{tr}</table>
<div class='sub' style='margin-top:6px'>Regression guard: <code>tests/test_thai_reef_placement.py</code> fails if a sessile actor's attachment point is more than 2 cm off its host surface, or a worm axis is more than 37° from the surface normal.</div>
</div></div>"""
    body = body.replace("<td>", "<td style='padding:4px 6px;border-top:1px solid #23394d'>").replace("<td class=", "<td style='padding:4px 6px;border-top:1px solid #23394d' class=")
    return page("Reef placement mockup", body)


# ───────────────────────────── 3 · skins.html ──────────────────────────────

def swatch(kind: str, w=120, h=64) -> str:
    """Small SVG skin swatch. kind is a key below."""
    s = [f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"]
    if kind == "flat-orange":
        s.append(f"<rect width='{w}' height='{h}' fill='#b6703f'/>")
    elif kind == "flat-black":
        s.append(f"<rect width='{w}' height='{h}' fill='#141518'/><rect y='{h*.6}' width='{w}' height='{h*.4}' fill='#3d9a9b'/>")
    elif kind == "flat-tan":
        s.append(f"<rect width='{w}' height='{h}' fill='#d0c09a'/><rect x='{w/2}' width='{w/2}' height='{h}' fill='#b6703f'/>")
    elif kind == "flat-white":
        for i in range(8):
            s.append(f"<rect x='{i*w/8}' width='{w/8}' height='{h}' fill='{'#f5f5ed' if i%2 else '#b6703f'}'/>")
    elif kind == "flat-purple":
        s.append(f"<rect width='{w}' height='{h}' fill='#8a62a4'/>")
    elif kind == "flat-magenta":
        s.append(f"<rect width='{w}' height='{h}' fill='#a8698f'/>")
    elif kind == "flat-humbug":
        for i in range(6):
            s.append(f"<rect x='{i*w/6}' width='{w/6}' height='{h}' fill='{'#121316' if i%2 else '#f5f5ed'}'/>")
    elif kind == "flat-lilac":
        s.append(f"<rect width='{w}' height='{h}' fill='#b77fc0'/>")
    elif kind == "crab":
        s.append(f"<rect width='{w}' height='{h}' fill='#d0542a'/>")
        rng = random.Random(3)
        for _ in range(70):
            s.append(f"<circle cx='{rng.uniform(0,w):.0f}' cy='{rng.uniform(0,h):.0f}' r='{rng.uniform(.8,1.8):.1f}' fill='#8a2a16' opacity='.7'/>")
        s.append(f"<rect y='{h*.75}' width='{w}' height='{h*.25}' fill='#f0b48a' opacity='.6'/>")
    elif kind == "shrimp":
        for i in range(10):
            s.append(f"<rect x='{i*w/10}' width='{w/10}' height='{h}' fill='{'#c9202a' if i%2 else '#f6f2ea'}'/>")
        s.append(f"<rect y='{h*.42}' width='{w}' height='{h*.16}' fill='#ffffff' opacity='.35'/>")
    elif kind == "nudi":
        s.append(f"<rect width='{w}' height='{h}' fill='#121316'/>")
        for i in range(3):
            y = h * (.25 + .25 * i)
            s.append(f"<rect y='{y-4}' width='{w}' height='8' rx='4' fill='#7f9fb8'/>")
            for j in range(9):
                s.append(f"<circle cx='{8+j*13}' cy='{y}' r='3.2' fill='#f2c81e'/>")
    elif kind == "hermit":
        s.append(f"<rect width='{w}' height='{h}' fill='#8b6d4f'/>")
        for i in range(7):
            s.append(f"<path d='M{i*20-10} {h} Q{i*20+6} {h/2} {i*20-4} 0' stroke='#5a422c' stroke-width='4' fill='none'/>")
        for j in range(18):
            s.append(f"<circle cx='{(j*37)%w}' cy='{(j*23)%h}' r='2.5' fill='#d8c3a0'/>")
    elif kind == "duster":
        for i in range(12):
            s.append(f"<rect x='{i*w/12}' width='{w/12}' height='{h}' fill='{['#7a4a2a','#d9c7a6','#a0643a'][i%3]}'/>")
    elif kind == "zoanthid":
        s.append(f"<rect width='{w}' height='{h}' fill='#5a3a6a'/>")
        for cx in range(14, w, 30):
            for cy in range(16, h, 30):
                s.append(f"<circle cx='{cx}' cy='{cy}' r='12' fill='#a978c4'/><circle cx='{cx}' cy='{cy}' r='6' fill='#5ad08a'/><circle cx='{cx}' cy='{cy}' r='2.2' fill='#f4e36a'/>")
    elif kind == "crust":
        rng = random.Random(9)
        s.append(f"<rect width='{w}' height='{h}' fill='#b9668f'/>")
        for _ in range(60):
            s.append(f"<circle cx='{rng.uniform(0,w):.0f}' cy='{rng.uniform(0,h):.0f}' r='{rng.uniform(1,4):.1f}' fill='#e7a0c4' opacity='.55'/>")
    elif kind == "fan":
        s.append(f"<defs><linearGradient id='g{kind}' x1='0' x2='0' y1='1' y2='0'><stop offset='0' stop-color='#6a2f7a'/><stop offset='1' stop-color='#e3a2ef'/></linearGradient></defs><rect width='{w}' height='{h}' fill='url(#g{kind})'/>")
    elif kind == "humbug":
        s.append(f"<defs><linearGradient id='gh' x1='0' x2='0' y1='0' y2='1'><stop offset='0' stop-color='#ffffff'/><stop offset='1' stop-color='#c9d3dc'/></linearGradient></defs>")
        for i in range(6):
            s.append(f"<rect x='{i*w/6}' width='{w/6}' height='{h}' fill='{'#121316' if i%2 else 'url(#gh)'}'/>")
    elif kind == "worm":
        for i, m in enumerate(MORPHS[:6]):
            s.append(f"<defs><linearGradient id='wm{i}'><stop offset='0' stop-color='{m[1]}'/><stop offset='1' stop-color='{m[2]}'/></linearGradient></defs>"
                     f"<rect y='{i*h/6}' width='{w}' height='{h/6+.5}' fill='url(#wm{i})'/>")
        for x in range(0, w, 10):
            s.append(f"<line x1='{x}' x2='{x}' y1='0' y2='{h}' stroke='#ffffff' stroke-width='1' opacity='.35'/>")
    elif kind == "clam":
        s.append(f"<rect width='{w}' height='{h}' fill='#2f8f9a'/>")
        for i in range(12):
            s.append(f"<path d='M{i*11} 0 Q{i*11+8} {h/2} {i*11} {h}' stroke='#7fe0e8' stroke-width='2' fill='none' opacity='.7'/>")
    s.append("</svg>")
    return "".join(s)


def skins_html() -> str:
    cards = [  # actor, today's keys, today swatch, proposed swatch, verdict
        ("Christmas tree worms", "sand stalk + polyp/coralline/sponge", "flat-lilac", "worm", "new <b>worm</b> cell: 8 morph rows, radiole banding"),
        ("Guard crab", "97 % sponge (barrel-sponge pores)", "flat-orange", "crab", "new <b>crab</b> cell; per-part cylindrical UV"),
        ("Banded coral shrimp ×2", "65 % sand, 33 % sponge", "flat-tan", "shrimp", "new <b>shrimp</b> cell: red/white bands along the body axis"),
        ("Nudibranch", "62 % flat black, 22 % clam", "flat-black", "nudi", "new <b>nudibranch</b> cell: ridges + yellow tubercles"),
        ("Hermit crab", "50 % sponge, 47 % rock", "flat-orange", "hermit", "new <b>gastropod shell</b> cell, banded legs"),
        ("Feather dusters", "42 % flat white, 42 % sponge", "flat-white", "duster", "new <b>radiole band</b> cell (shared with worm tips)"),
        ("Zoanthid carpets", "zoanthid tile, 66 % of area below 3 texels", "flat-purple", "zoanthid", "object-local UV: one flower head per polyp disc"),
        ("Encrusting crusts", "sponge/coralline tile, flat ellipses", "flat-magenta", "crust", "conform to rock (W3) + finer crust tile"),
        ("Humbug ×2", "100 % flat black/white swatches", "flat-humbug", "humbug", "keep bars; add belly-to-back sheen (realistic only)"),
        ("Sea fan · feather star", "coralline / polyp tiles on 1–2 cm tubes", "flat-lilac", "fan", "<b>accept untextured</b> (D3); base-to-tip gradient only"),
        ("Giant clam", "clam mantle + clam_shell strip", "clam", "clam", "OK; placement only (W3)"),
    ]
    cells = []
    for name, keys, t, p, verdict in cards:
        cells.append(f"<div class='panel' style='padding:9px'><div style='font-weight:bold;margin-bottom:2px'>{name}</div>"
                     f"<div class='sub' style='font-size:11.5px;height:30px'>{keys}</div>"
                     f"<div style='display:flex;gap:8px;align-items:center;margin:4px 0'><div><div class='sub' style='font-size:11px'>today</div>{swatch(t,96,52)}</div>"
                     f"<div style='font-size:20px;color:#6a8'>→</div><div><div class='sub' style='font-size:11px'>proposed</div>{swatch(p,96,52)}</div></div>"
                     f"<div style='font-size:12px'>{verdict}</div></div>")
    atlas = [("coralline", "#ab6994"), ("polyp", "#ca9180"), ("sponge", "#b67044"), ("sand", "#d5c59e"),
             ("rock", "#736f5b"), ("zoanthid", "#9773a4"), ("clam mantle", "#3d999b"), ("boxfish", "#deb748"),
             ("worm morphs", "#2f63c9"), ("radiole bands", "#a0643a"), ("crab", "#d0542a"), ("shrimp", "#c9202a"),
             ("nudibranch", "#141518"), ("hermit shell", "#8b6d4f"), ("crust fine", "#b9668f"), ("utility", "#40566a")]
    grid = "".join(
        f"<div style='background:{c};height:66px;border:1px solid #0d1620;display:flex;align-items:flex-end;padding:3px;font-size:11px;"
        f"color:#fff;text-shadow:0 0 3px #000;{'outline:2px solid #6dff9a;outline-offset:-3px;' if i >= 8 and i < 15 else ''}'>{i} · {n}</div>"
        for i, (n, c) in enumerate(atlas))
    body = f"""
<div class='wrap'>
<h1>Skins — which actors read as untextured, and what replaces it</h1>
<div class='sub'>Measured from the generator meshes: share of face area that samples a single flat texel, or whose face spans fewer than 3 texels of a world-projected tile. Small creatures borrow sponge, sand and rock tiles, so at TV distance they read as flat colour.</div>
<div style='display:grid;grid-template-columns:1fr 330px;gap:14px;margin-top:12px'>
 <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:9px'>{''.join(cells)}</div>
 <div class='panel'><h2>Atlas repack · same 1024² page</h2>
  <div class='sub' style='font-size:12px;margin-bottom:6px'>8 tiles of 256 × 512 → 16 cells of 256 × 256. No new texture memory, no engine change. Green = new creature cells.</div>
  <div style='display:grid;grid-template-columns:repeat(4,1fr)'>{grid}</div>
  <ul style='font-size:12px;margin-top:8px'>
   <li>static reef keeps world-projected UVs (tile v range halves)</li>
   <li>creatures switch to <b>object-local</b> UVs: cylindrical per limb/body, along the helix for worms</li>
   <li>anime atlas is the same layout, posterised to 3 tones</li>
  </ul></div>
</div></div>"""
    return page("Reef skins mockup", body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true", help="also render PNGs with headless google-chrome")
    args = ap.parse_args()
    for name, fn in (("worms", worms_html), ("placement", placement_html), ("skins", skins_html)):
        html = HERE / f"{name}.html"
        html.write_text(fn())
        print(f"wrote {html.relative_to(REPO)} ({html.stat().st_size // 1024} KB)")
        if args.png:
            subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--window-size=1440,900", f"--screenshot={HERE / (name + '.png')}",
                            html.as_uri()], check=True, capture_output=True)


if __name__ == "__main__":
    main()
