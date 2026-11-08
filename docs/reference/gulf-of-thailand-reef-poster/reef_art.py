"""Original species drawings for the Gulf of Thailand reef poster.

Adapted from the plan's mockup art (docs/plans/2026-11-02-gulf-of-thailand-reef-tank/build_mockups.py,
drawn for this project). Each function draws one organism as SVG in scene units around (x, y);
s scales it. All randomness comes from the rng passed in, so a rebuild is byte-identical.
These are explanatory drawings, not game assets or engine captures.
"""
from __future__ import annotations

import math

# ─────────────────────────────── geometry helpers ───────────────────────────


def f(v: float) -> str:
    """Compact number: whole units for scene-sized values, one decimal below 20."""
    if abs(v) >= 20:
        return str(round(v))
    return f"{v:.1f}".rstrip("0").rstrip(".")


def smooth_closed(pts) -> str:
    """Closed Catmull-Rom spline through pts as an SVG path."""
    n = len(pts)
    d = [f"M{f(pts[0][0])},{f(pts[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}")
    return " ".join(d) + "Z"


def smooth_open(pts) -> str:
    d = [f"M{f(pts[0][0])},{f(pts[0][1])}"]
    for i in range(len(pts) - 1):
        p0 = pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}")
    return " ".join(d)


def blob(rng, cx, cy, rx, ry, n=22, jit=0.16):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1 + rng.uniform(-jit, jit)
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    return smooth_closed(pts)


_ids = [0]


def uid(prefix: str) -> str:
    _ids[0] += 1
    return f"{prefix}{_ids[0]}"


# ─────────────────────────────── species art ────────────────────────────────
# Each function draws one organism in scene units around (x, y); s scales it.

WORM_COLOURS = ["#e63946", "#f4a261", "#2ec4b6", "#ffd166", "#4361ee",
                "#ffffff", "#f72585", "#80ed99"]


def christmas_tree_worm(rng, x, y, s=1.0, out=True):
    if not out:
        return (f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(3.2*s)}" ry="{f(2*s)}" fill="#3a2b1c"/>'
                f'<ellipse cx="{f(x)}" cy="{f(y-0.6*s)}" rx="{f(2*s)}" ry="{f(1*s)}" fill="#8a7a5c"/>')
    c1, c2 = rng.sample(WORM_COLOURS, 2)
    g = []
    for dx, col in ((-5.5 * s, c1), (5.5 * s, c2)):
        for k in range(5):
            w = (8 - k * 1.3) * s
            yy = y - k * 4.2 * s
            g.append(f'<path d="M{f(x+dx-w/2)},{f(yy)} Q{f(x+dx)},{f(yy-6*s)} {f(x+dx+w/2)},{f(yy)}" '
                     f'fill="{col}" stroke="#00000033" stroke-width="{f(0.5*s)}"/>')
    return "".join(g)


def porites(rng, x, y, rx, ry, worms_out=True):
    gid = uid("por")
    pts = []
    for i in range(18):
        a = math.pi + math.pi * i / 17
        r = 1 + rng.uniform(-0.07, 0.07)
        pts.append((x + rx * r * math.cos(a), y + ry * r * math.sin(a)))
    pts += [(x + rx, y + 6), (x - rx, y + 6)]
    d = smooth_closed(pts)
    g = [f'<defs><radialGradient id="{gid}" cx="40%" cy="30%" r="80%">'
         f'<stop offset="0" stop-color="#f0dc98"/><stop offset="1" stop-color="#9c7c3e"/></radialGradient></defs>',
         f'<path d="{d}" fill="url(#{gid})" stroke="#6b5226" stroke-width="1.5"/>']
    for _ in range(90):  # polyp texture
        a = rng.uniform(math.pi * 1.05, math.pi * 1.95)
        r = math.sqrt(rng.random()) * 0.92
        g.append(f'<circle cx="{f(x+rx*r*math.cos(a))}" cy="{f(y+ry*r*math.sin(a))}" r="1.3" fill="#7a5f2a" opacity=".35"/>')
    spots = [(-0.55, -0.45), (-0.2, -0.8), (0.25, -0.7), (0.6, -0.4), (-0.75, -0.15),
             (0.05, -0.35), (0.4, -0.1), (-0.35, -0.15), (0.8, -0.12), (-0.05, -0.92)]
    for u, v in spots:
        g.append(christmas_tree_worm(rng, x + u * rx, y + v * ry, 1.25, worms_out))
    return "".join(g)


def branches(rng, x, y, ang, length, depth, width, spread=(14, 34)):
    out = []
    x2 = x + length * math.cos(ang)
    y2 = y + length * math.sin(ang)
    out.append((x, y, x2, y2, width, depth))
    if depth > 0:
        for sgn in (-1, 1):
            a = ang + sgn * math.radians(rng.uniform(*spread))
            out += branches(rng, x2, y2, a, length * rng.uniform(0.66, 0.8), depth - 1, width * 0.72, spread)
    return out


def branching_coral(rng, x, y, h, col="#86b9e8", tip="#e6f6ff"):
    g = []
    for k in range(5):
        a = -math.pi / 2 + math.radians(-40 + 20 * k + rng.uniform(-6, 6))
        for x1, y1, x2, y2, w, dep in branches(rng, x + (k - 2) * 8, y, a, h * 0.32, 3, 9, (12, 28)):
            g.append(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{col}" '
                     f'stroke-width="{f(w)}" stroke-linecap="round"/>')
            if dep == 0:
                g.append(f'<circle cx="{f(x2)}" cy="{f(y2)}" r="{f(w*0.75)}" fill="{tip}"/>')
    return "".join(g)


def table_acropora(rng, x, y, w):
    g = [f'<path d="M{f(x-14)},{f(y+70)} L{f(x-8)},{f(y+8)} L{f(x+8)},{f(y+8)} L{f(x+14)},{f(y+70)}Z" fill="#7d6a9e"/>']
    g.append(f'<path d="{blob(rng, x, y+10, w/2, 13, 26, 0.05)}" fill="#3d2f57" opacity=".55"/>')
    g.append(f'<path d="{blob(rng, x, y, w/2, 16, 30, 0.06)}" fill="#b9a4e0" stroke="#8a74b8" stroke-width="1.5"/>')
    for row in range(3):
        n = 22 - row * 5
        for i in range(n):
            u = (i + 0.5) / n * 2 - 1
            yy = y - 6 - row * 5
            g.append(f'<circle cx="{f(x+u*(w/2-12-row*18))}" cy="{f(yy+abs(u)*4)}" r="2.6" fill="#ece2ff"/>')
    return "".join(g)


def turbinaria(rng, x, y, s=1.0):
    g = []
    for k in range(5):
        cx = x + (k - 2) * 20 * s + rng.uniform(-4, 4)
        cy = y - k % 2 * 14 * s - abs(k - 2) * -6 * s
        rw, rh = (26 - abs(k - 2) * 3) * s, 11 * s
        g.append(f'<path d="M{f(cx-rw)},{f(cy)} Q{f(cx)},{f(cy+28*s)} {f(cx+rw)},{f(cy)}" fill="#c99a1c"/>')
        g.append(f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(rw)}" ry="{f(rh)}" fill="#f0cf45" stroke="#b8891a" stroke-width="1.2"/>')
        g.append(f'<ellipse cx="{f(cx)}" cy="{f(cy+2*s)}" rx="{f(rw*0.62)}" ry="{f(rh*0.5)}" fill="#d9ac24"/>')
    return "".join(g)


def goniopora(rng, x, y, r, sway=0.0):
    g = [f'<path d="{blob(rng, x, y+r*0.35, r, r*0.55, 18, 0.06)}" fill="#5e7d32"/>']
    for i in range(70):
        a = math.pi + math.pi * rng.random()
        bx, by = x + r * 0.9 * math.cos(a), y + r * 0.5 * math.sin(a) + r * 0.35
        L = rng.uniform(22, 38)
        ang = a * 0.35 - math.pi * 0.83 + sway
        ex, ey = bx + L * math.cos(ang) * 0.6, by - L
        g.append(f'<path d="M{f(bx)},{f(by)} Q{f(bx+(ex-bx)*0.2+6)},{f((by+ey)/2)} {f(ex)},{f(ey)}" '
                 f'stroke="#8fcf4a" stroke-width="2.2" fill="none" opacity=".9"/>')
        g.append(f'<circle cx="{f(ex)}" cy="{f(ey)}" r="3.4" fill="#c8f27a"/>'
                 f'<circle cx="{f(ex)}" cy="{f(ey)}" r="1.3" fill="#5e7d32"/>')
    return "".join(g)


def sarcophyton(rng, x, y, s=1.0):
    g = [f'<path d="M{f(x-16*s)},{f(y)} Q{f(x-10*s)},{f(y-40*s)} {f(x-22*s)},{f(y-62*s)} '
         f'L{f(x+22*s)},{f(y-62*s)} Q{f(x+10*s)},{f(y-40*s)} {f(x+16*s)},{f(y)}Z" fill="#cdbb8e"/>']
    pts = []
    for i in range(26):
        a = math.pi + math.pi * i / 25
        r = 1 + 0.08 * math.sin(i * 1.9)
        pts.append((x + 70 * s * r * math.cos(a), y - 62 * s + 30 * s * r * math.sin(a)))
    pts += [(x + 66 * s, y - 52 * s), (x - 66 * s, y - 52 * s)]
    g.append(f'<path d="{smooth_closed(pts)}" fill="#e9dfc2" stroke="#b8a473" stroke-width="1.2"/>')
    for _ in range(120):
        a = math.pi + math.pi * rng.random()
        r = math.sqrt(rng.random()) * 0.95
        px, py = x + 66 * s * r * math.cos(a), y - 60 * s + 28 * s * r * math.sin(a)
        g.append(f'<line x1="{f(px)}" y1="{f(py)}" x2="{f(px+rng.uniform(-2,2))}" y2="{f(py-5*s)}" stroke="#fffaf0" stroke-width="1.1"/>')
    return "".join(g)


def gorgonian(rng, x, y, h, col):
    g = []
    for k in range(3):
        a = -math.pi / 2 + math.radians((k - 1) * 22)
        for x1, y1, x2, y2, w, _ in branches(rng, x, y, a, h * 0.36, 4, 6, (16, 40)):
            g.append(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" stroke="{col}" '
                     f'stroke-width="{f(max(w,1.1))}" stroke-linecap="round"/>')
    return "".join(g)


def tubastraea(rng, x, y, n=7, down=True):
    g = []
    sgn = 1 if down else -1
    for i in range(n):
        cx = x + i * 22 + rng.uniform(-4, 4)
        L = rng.uniform(10, 22)
        cy = y + sgn * L
        g.append(f'<rect x="{f(cx-7)}" y="{f(min(y,cy))}" width="14" height="{f(abs(cy-y))}" fill="#e2601a"/>')
        g.append(f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="11" ry="5" fill="#ff8a1f"/>')
        for k in range(10):
            a = 2 * math.pi * k / 10
            g.append(f'<circle cx="{f(cx+11*math.cos(a))}" cy="{f(cy+5*math.sin(a)+sgn*3)}" r="2" fill="#ffd23f"/>')
    return "".join(g)


def fungia(rng, x, y, s=1.0, col="#c7a56a"):
    g = [f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(30*s)}" ry="{f(11*s)}" fill="{col}" stroke="#8a6c3a" stroke-width="1"/>']
    for k in range(18):
        a = 2 * math.pi * k / 18
        g.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x+27*s*math.cos(a))}" y2="{f(y+9*s*math.sin(a))}" stroke="#8a6c3a" stroke-width=".9" opacity=".7"/>')
    g.append(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(6*s)}" ry="{f(2*s)}" fill="#5b4422"/>')
    return "".join(g)


def barrel_sponge(rng, x, y, h, w):
    top = y - h
    g = [f'<path d="M{f(x-w*0.42)},{f(y)} L{f(x-w*0.5)},{f(top)} L{f(x+w*0.5)},{f(top)} L{f(x+w*0.42)},{f(y)}Z" fill="#8c4a3a"/>']
    for k in range(1, 9):
        yy = y - h * k / 9
        ww = w * (0.42 + 0.08 * k / 9)
        g.append(f'<path d="M{f(x-ww)},{f(yy)} Q{f(x)},{f(yy+9)} {f(x+ww)},{f(yy)}" stroke="#6a3226" stroke-width="3" fill="none"/>')
    g.append(f'<ellipse cx="{f(x)}" cy="{f(top)}" rx="{f(w*0.5)}" ry="{f(w*0.13)}" fill="#a65c48"/>')
    g.append(f'<ellipse cx="{f(x)}" cy="{f(top+2)}" rx="{f(w*0.38)}" ry="{f(w*0.08)}" fill="#2a1410"/>')
    return "".join(g)


def sea_squirt(rng, x, y, s=1.0):
    return (f'<path d="M{f(x-9*s)},{f(y)} Q{f(x-14*s)},{f(y-30*s)} {f(x-6*s)},{f(y-40*s)} L{f(x+6*s)},{f(y-40*s)} '
            f'Q{f(x+14*s)},{f(y-30*s)} {f(x+9*s)},{f(y)}Z" fill="#f2e6f7" stroke="#b07bc6" stroke-width="1.2"/>'
            f'<ellipse cx="{f(x-2*s)}" cy="{f(y-40*s)}" rx="{f(5*s)}" ry="{f(2.5*s)}" fill="#ff9f1c"/>'
            f'<ellipse cx="{f(x+7*s)}" cy="{f(y-26*s)}" rx="{f(3.5*s)}" ry="{f(2*s)}" fill="#ff9f1c"/>'
            f'<path d="M{f(x-6*s)},{f(y-10*s)} q{f(4*s)},{f(-8*s)} {f(10*s)},{f(-14*s)}" stroke="#9b59b6" stroke-width="1.4" fill="none"/>')


def giant_clam(rng, x, y, w, open_=1.0):
    g = []
    n = 7
    zig = []
    for i in range(n * 2 + 1):
        u = i / (n * 2)
        zig.append((x - w / 2 + u * w, y + (0 if i % 2 else 9)))
    shell = f"M{f(x-w/2)},{f(y+34)} " + " ".join(f"L{f(px)},{f(py)}" for px, py in zig) + f" L{f(x+w/2)},{f(y+34)}Z"
    g.append(f'<path d="{shell}" fill="#e8e1cf" stroke="#9c927a" stroke-width="1.4"/>')
    for i in range(1, n * 2, 2):
        px = x - w / 2 + i / (n * 2) * w
        g.append(f'<line x1="{f(px)}" y1="{f(y+2)}" x2="{f(px*0.9+x*0.1)}" y2="{f(y+34)}" stroke="#b5ab92" stroke-width="1.3"/>')
    gid = uid("mantle")
    mh = 16 * open_
    g.append(f'<defs><linearGradient id="{gid}" x1="0" x2="1"><stop offset="0" stop-color="#1557c0"/>'
             f'<stop offset=".5" stop-color="#36c6d3"/><stop offset="1" stop-color="#1b6fd1"/></linearGradient></defs>')
    wave = [(x - w * 0.46 + w * 0.92 * i / 12, y - mh * (0.6 + 0.4 * math.sin(i * 1.3))) for i in range(13)]
    path = "M" + f"{f(x-w*0.46)},{f(y+4)} L" + smooth_open(wave)[1:] + f" L{f(x+w*0.46)},{f(y+4)}Z"
    g.append(f'<path d="{path}" fill="url(#{gid})" stroke="#0c3d86" stroke-width="1"/>')
    for _ in range(int(26 * open_)):
        g.append(f'<circle cx="{f(x+rng.uniform(-w*0.42,w*0.42))}" cy="{f(y-rng.uniform(1,mh*0.7))}" r="1.4" fill="#bff6ff"/>')
    g.append(f'<ellipse cx="{f(x+w*0.1)}" cy="{f(y-mh*0.55)}" rx="5" ry="3" fill="#06244d"/>')
    return "".join(g)


def crinoid(rng, x, y, r, phase=0.0):
    # Thirty schematic arms sit inside the published 27–41 range for the
    # selected Lamprometra; their small branches are pinnules, not arms.
    g = []
    for k in range(30):
        a0 = -math.pi / 2 + math.radians(-80 + k * 160 / 29)
        pts, ticks = [], []
        for j in range(9):
            t = j / 8
            a = a0 + math.sin(phase + k // 3 + t * 2.4) * 0.12 * t - (0.9 * t * t if k < 15 else -0.9 * t * t) * 0.25
            px = x + r * t * math.cos(a)
            py = y + r * t * math.sin(a)
            pts.append((px, py))
            if 0 < j < 8:
                nx, ny = -math.sin(a), math.cos(a)
                for sg in (-1, 1):
                    ticks.append(f'<line x1="{f(px)}" y1="{f(py)}" x2="{f(px+sg*nx*9+math.cos(a)*5)}" '
                                 f'y2="{f(py+sg*ny*5+math.sin(a)*3)}" stroke="#ffd34d" stroke-width=".7"/>')
        g.append(f'<path d="{smooth_open(pts)}" stroke="#f2a90f" stroke-width="1.6" fill="none" stroke-linecap="round"/>')
        g += ticks
        g.append(f'<path d="{smooth_open(pts)}" stroke="#2b1d06" stroke-width=".6" fill="none" stroke-dasharray="3 9"/>')
    g.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="9" fill="#c47f08"/>')
    return "".join(g)


def feather_duster(rng, x, y, ang=-90, out=True, s=1.0):
    a = math.radians(ang)
    tx, ty = x + 38 * s * math.cos(a), y + 38 * s * math.sin(a)
    g = [f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(tx)}" y2="{f(ty)}" stroke="#7d6e5a" stroke-width="{f(6*s)}" stroke-linecap="round"/>']
    if not out:
        g.append(f'<circle cx="{f(tx)}" cy="{f(ty)}" r="{f(3.5*s)}" fill="#3a2b1c"/>')
        return "".join(g)
    for k in range(17):
        b = a + math.radians(-80 + k * 10)
        L = 34 * s
        ex, ey = tx + L * math.cos(b), ty + L * math.sin(b)
        g.append(f'<line x1="{f(tx)}" y1="{f(ty)}" x2="{f(ex)}" y2="{f(ey)}" stroke="#7a1f3d" stroke-width="{f(2.4*s)}"/>')
        for q in (0.35, 0.6, 0.85):
            g.append(f'<circle cx="{f(tx+(ex-tx)*q)}" cy="{f(ty+(ey-ty)*q)}" r="{f(1.5*s)}" fill="#fff4e6"/>')
    return "".join(g)


def cleaner_shrimp(rng, x, y, s=1.0, facing=1):
    """Banded coral shrimp: red/white bands, enlarged chelipeds and white antennae.

    Schematic drawing informed by Western Australian Museum's Stenopus
    hispidus account; it is not a taxonomic illustration.
    """
    sx = facing
    g = [f'<g transform="translate({f(x)} {f(y)}) scale({f(s*sx)} {f(s)})">',
         '<path d="M-24,-3 Q-8,-12 13,-7 L25,-2 L14,6 Q-5,9 -24,3 Z" fill="#faf7ee" stroke="#9d2020" stroke-width="1.3"/>',
         '<path d="M-18,-7 L-16,6 M-8,-9 L-6,7 M2,-9 L4,7 M13,-7 L15,5" stroke="#d3312d" stroke-width="3.4"/>',
         '<path d="M-24,-2 l-8,-7 l4,8 l-4,7 l9,-4" fill="#f1e8df" stroke="#d3312d" stroke-width="2"/>']
    for k in range(4):
        lx = -9 + k * 6
        g.append(f'<path d="M{lx},5 l4,9 l5,1" fill="none" stroke="#ddd3ca" stroke-width="1.4"/>')
    # The enlarged third legs end in clearly separated, banded pincers.
    g += ['<path d="M10,4 Q20,11 30,5 L35,-4" fill="none" stroke="#f9f5ed" stroke-width="4"/>',
          '<path d="M22,9 l7,-3 M32,2 l2,-4" fill="none" stroke="#d3312d" stroke-width="3"/>',
          '<path d="M35,-4 Q43,-11 47,-8 L40,-2 Q46,-1 48,3 Q42,5 35,-4" fill="#f9f5ed" stroke="#b52126" stroke-width="1.5"/>',
          '<path d="M18,-5 Q34,-20 52,-27 M19,-6 Q33,-28 48,-35" fill="none" stroke="#fafafa" stroke-width="1.2"/>',
          '<circle cx="20" cy="-6" r="1.8" fill="#111"/></g>']
    return ''.join(g)


def phyllidia(rng, x, y, s=1.0, rot=0):
    g = [f'<g transform="rotate({rot} {f(x)} {f(y)})">',
         f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(30*s)}" ry="{f(11*s)}" fill="#141414"/>',
         f'<line x1="{f(x-26*s)}" y1="{f(y-4*s)}" x2="{f(x+26*s)}" y2="{f(y-4*s)}" stroke="#4aa3ff" stroke-width="{f(2*s)}"/>',
         f'<line x1="{f(x-26*s)}" y1="{f(y+4*s)}" x2="{f(x+26*s)}" y2="{f(y+4*s)}" stroke="#4aa3ff" stroke-width="{f(2*s)}"/>']
    for k in range(7):
        for yy in (-7, 0, 7):
            g.append(f'<circle cx="{f(x+(-21+k*7)*s)}" cy="{f(y+yy*s*0.9)}" r="{f(2.2*s)}" fill="#ffd400"/>')
    g.append(f'<rect x="{f(x+28*s)}" y="{f(y-5*s)}" width="{f(5*s)}" height="{f(3*s)}" fill="#ffd400"/>'
             f'<rect x="{f(x+28*s)}" y="{f(y+2*s)}" width="{f(5*s)}" height="{f(3*s)}" fill="#ffd400"/></g>')
    return "".join(g)


def linckia(rng, x, y, s=1.0, rot=0):
    g = [f'<g transform="rotate({rot} {f(x)} {f(y)})">']
    for k in range(5):
        a = math.radians(k * 72 - 90)
        ex, ey = x + 52 * s * math.cos(a), y + 52 * s * math.sin(a)
        g.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(ex)}" y2="{f(ey)}" stroke="#2f6fd6" stroke-width="{f(11*s)}" stroke-linecap="round"/>')
        g.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(ex)}" y2="{f(ey)}" stroke="#5c95f0" stroke-width="{f(3*s)}" stroke-linecap="round"/>')
    g.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(9*s)}" fill="#2f6fd6"/></g>')
    return "".join(g)


def sea_cucumber(rng, x, y, s=1.0):
    g = [f'<path d="M{f(x-200*s)},{f(y+8*s)} Q{f(x-120*s)},{f(y+2*s)} {f(x-50*s)},{f(y+6*s)}" stroke="#d9c393" stroke-width="{f(5*s)}" fill="none" opacity=".8"/>',
         f'<path d="{blob(rng, x, y, 55*s, 13*s, 20, 0.05)}" fill="#1d1712"/>']
    for _ in range(26):
        g.append(f'<circle cx="{f(x+rng.uniform(-48,48)*s)}" cy="{f(y+rng.uniform(-10,4)*s)}" r="{f(2.4*s)}" fill="#3d3127"/>')
    return "".join(g)


def hermit_crab(rng, x, y, s=1.0):
    g = []
    for k in range(3):
        g.append(f'<line x1="{f(x+(6+k*6)*s)}" y1="{f(y-4*s)}" x2="{f(x+(14+k*7)*s)}" y2="{f(y+8*s)}" stroke="#d1342c" stroke-width="{f(3*s)}" stroke-linecap="round"/>')
    g.append(f'<path d="M{f(x-22*s)},{f(y+6*s)} Q{f(x-26*s)},{f(y-24*s)} {f(x)},{f(y-22*s)} Q{f(x+20*s)},{f(y-14*s)} {f(x+10*s)},{f(y+6*s)}Z" fill="#cfb998" stroke="#8a7656"/>')
    g.append(f'<path d="M{f(x-12*s)},{f(y-6*s)} q{f(6*s)},{f(-10*s)} {f(14*s)},{f(-4*s)} q{f(-4*s)},{f(8*s)} {f(-8*s)},{f(4*s)}" fill="none" stroke="#8a7656" stroke-width="{f(1.4*s)}"/>')
    g.append(f'<ellipse cx="{f(x+22*s)}" cy="{f(y-2*s)}" rx="{f(7*s)}" ry="{f(5*s)}" fill="#e3402f"/>'
             f'<circle cx="{f(x+21*s)}" cy="{f(y-10*s)}" r="{f(1.8*s)}" fill="#111"/>')
    return "".join(g)


def zoanthids(rng, x, y, r, n=40, col="#2fbf71", mouth="#ffd23f"):
    g = []
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        d = math.sqrt(rng.random()) * r
        px, py = x + d * math.cos(a), y + d * math.sin(a) * 0.55
        g.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="5.2" fill="{col}" stroke="#155d38" stroke-width=".8"/>'
                 f'<circle cx="{f(px)}" cy="{f(py)}" r="2" fill="{mouth}"/>')
    return "".join(g)


def guard_crab(rng, x, y, s=1.0, threat=False):
    """Trapezia cymodoce: a smooth orange-red coral crab, ~1.5 cm carapace."""
    g = []
    for sg in (-1, 1):
        for k in range(4):
            bx = x + sg * (6 + k * 3) * s
            g.append(f'<path d="M{f(bx)},{f(y+2*s)} l{f(sg*9*s)},{f(-5*s+k*3*s)} l{f(sg*5*s)},{f(9*s)}" '
                     f'stroke="#c2410c" stroke-width="{f(2.2*s)}" fill="none" stroke-linecap="round"/>')
    lift = -10 if threat else 0
    for sg in (-1, 1):
        cx, cy = x + sg * 15 * s, y - 6 * s + lift * s
        g.append(f'<line x1="{f(x+sg*7*s)}" y1="{f(y-2*s)}" x2="{f(cx)}" y2="{f(cy)}" stroke="#ea580c" stroke-width="{f(3*s)}" stroke-linecap="round"/>')
        g.append(f'<ellipse cx="{f(cx+sg*3*s)}" cy="{f(cy-2*s)}" rx="{f(6*s)}" ry="{f(4*s)}" fill="#f97316" stroke="#9a3412" stroke-width=".8"/>')
        g.append(f'<line x1="{f(cx+sg*3*s)}" y1="{f(cy-2*s)}" x2="{f(cx+sg*9*s)}" y2="{f(cy-2*s)}" stroke="#1c1917" stroke-width="{f(1.2*s)}"/>')
    g.append(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(12*s)}" ry="{f(8.5*s)}" fill="#f97316" stroke="#9a3412" stroke-width="1"/>')
    g.append(f'<ellipse cx="{f(x-3*s)}" cy="{f(y-3*s)}" rx="{f(5*s)}" ry="{f(2.5*s)}" fill="#fdba74" opacity=".8"/>')
    for sg in (-1, 1):
        g.append(f'<circle cx="{f(x+sg*4*s)}" cy="{f(y-9*s)}" r="{f(1.8*s)}" fill="#111"/>')
    return "".join(g)


def humbug(rng, x, y, s=1.0, facing=1):
    cid = uid("hb")
    g = [f'<defs><clipPath id="{cid}"><ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(22*s)}" ry="{f(17*s)}"/></clipPath></defs>',
         f'<path d="M{f(x-20*s*facing)},{f(y)} l{f(-14*s*facing)},{f(-9*s)} l0,{f(18*s)}Z" fill="#f4f4f4" stroke="#999" stroke-width=".6"/>',
         f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(22*s)}" ry="{f(17*s)}" fill="#f7f7f7"/>',
         f'<g clip-path="url(#{cid})">']
    for bx in (-12, 0, 13):
        g.append(f'<rect x="{f(x+bx*s*facing-4*s)}" y="{f(y-20*s)}" width="{f(8*s)}" height="{f(40*s)}" fill="#151515" transform="rotate({-8*facing} {f(x)} {f(y)})"/>')
    g.append('</g>')
    g.append(f'<path d="M{f(x-14*s)},{f(y-15*s)} Q{f(x)},{f(y-26*s)} {f(x+14*s)},{f(y-15*s)}" fill="#151515"/>')
    g.append(f'<circle cx="{f(x+15*s*facing)}" cy="{f(y-4*s)}" r="{f(2.6*s)}" fill="#111" stroke="#fff" stroke-width=".8"/>')
    return "".join(g)


def boxfish(rng, x, y, s=1.0, facing=1):
    g = [f'<path d="M{f(x-26*s*facing)},{f(y)} l{f(-16*s*facing)},{f(-12*s)} q{f(-4*s*facing)},{f(12*s)} 0,{f(24*s)}Z" fill="#f5c400" stroke="#b38f00"/>',
         f'<rect x="{f(x-28*s)}" y="{f(y-17*s)}" width="{f(54*s)}" height="{f(34*s)}" rx="{f(11*s)}" fill="#ffd400" stroke="#c7a200" stroke-width="1.2"/>']
    for u, v in ((-16, -8), (-6, -10), (4, -9), (-12, 2), (0, 0), (10, 3), (-18, 9), (-4, 10), (8, 11), (16, -6)):
        g.append(f'<circle cx="{f(x+u*s*facing)}" cy="{f(y+v*s)}" r="{f(2.1*s)}" fill="#141414"/>')
    g.append(f'<ellipse cx="{f(x+4*s*facing)}" cy="{f(y+3*s)}" rx="{f(5*s)}" ry="{f(7*s)}" fill="#ffe680" opacity=".9"/>')
    g.append(f'<circle cx="{f(x+17*s*facing)}" cy="{f(y-6*s)}" r="{f(4.3*s)}" fill="#fff"/><circle cx="{f(x+18*s*facing)}" cy="{f(y-6*s)}" r="{f(2.4*s)}" fill="#111"/>')
    g.append(f'<ellipse cx="{f(x+28*s*facing)}" cy="{f(y+3*s)}" rx="{f(2.4*s)}" ry="{f(2*s)}" fill="#e07a5f"/>')
    return "".join(g)


# ─────────────────────────────── the reef scene ─────────────────────────────

ROCK_MASSES = {
    "left": [(300, 650, 230, 170), (210, 560, 130, 120), (390, 545, 140, 110), (300, 470, 120, 90), (470, 660, 120, 110)],
    "right": [(1250, 630, 230, 170), (1340, 520, 140, 130), (1170, 560, 130, 110), (1260, 445, 110, 90), (1430, 670, 120, 120)],
    "arch": [(640, 670, 90, 115), (985, 660, 95, 120), (810, 478, 250, 52), (700, 452, 70, 40), (925, 448, 85, 45)],
}

# (label, latin, anchor x, y) in scene units — the wide view's callouts.
CALLOUTS = [
    ("Live rock + coralline algae", "Corallinales", 230, 610),
    ("Flowerpot coral", "Goniopora sp.", 175, 500),
    ("Cauliflower coral head", "Pocillopora damicornis", 250, 360),
    ("Coral guard crab", "Trapezia cymodoce", 352, 420),
    ("Reticulated dascyllus ×2", "Dascyllus reticulatus", 335, 250),
    ("Yellow scroll coral", "Turbinaria sp.", 470, 455),
    ("Feather duster worm", "Sabellastarte sp.", 520, 560),
    ("Zoanthid carpet", "Palythoa / Zoanthus", 330, 610),
    ("Phyllidia nudibranch", "Phyllidia varicosa", 260, 690),
    ("Mushroom coral", "Fungiidae", 520, 835),
    ("Sea cucumber", "Holothuria sp.", 300, 860),
    ("Sea fan", "gorgonian", 100, 400),
    ("Leather coral", "Sarcophyton sp.", 760, 380),
    ("Orange cup coral", "Tubastraea coccinea", 790, 540),
    ("Cleaner shrimp ×2", "Lysmata amboinensis", 700, 590),
    ("Boulder coral", "Porites lutea", 680, 760),
    ("Christmas tree worms", "Spirobranchus sp.", 775, 715),
    ("Feather star", "Comatulida", 930, 380),
    ("Yellow boxfish (juvenile)", "Ostracion cubicus", 900, 290),
    ("Table coral", "Acropora sp.", 1290, 360),
    ("Fluted giant clam", "Tridacna squamosa", 1060, 805),
    ("Hermit crab", "Diogenidae", 985, 852),
    ("Blue sea star", "Linckia laevigata", 1220, 650),
    ("Gold-mouth sea squirts", "Polycarpa aurata", 1335, 585),
    ("Barrel sponge", "Xestospongia testudinaria", 1480, 650),
]

