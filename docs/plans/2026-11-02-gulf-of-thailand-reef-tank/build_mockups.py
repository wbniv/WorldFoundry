#!/usr/bin/env python3
"""Mockups for docs/plans/2026-11-02-gulf-of-thailand-reef-tank.md.

Writes five self-contained 1440x900 HTML mockups beside this script and, with
--png, a same-basename PNG for each (headless google-chrome):

  tank-wide.html   the reef from the default wide camera, every species labelled
  tank-close.html  the close camera in two states (calm / boxfish passing)
  styles.html      the two visual styles (ultra-realistic, anime/cel) on one reef
  selectors.html   the Android tank menu (9 entries) and the Dream tank list
  poster.html      the A3 poster layout, drawn with the same species art

Everything is procedural SVG from one seeded RNG, so a rerun is byte-identical.
The drawings are design intent for the plan, not game assets.
"""
from __future__ import annotations

import argparse
import math
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20261102

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
    g = []
    for k in range(30):
        a0 = -math.pi / 2 + math.radians(-80 + k * (160 / 29))
        pts, ticks = [], []
        for j in range(9):
            t = j / 8
            a = a0 + math.sin(phase + k // 3 + t * 2.4) * 0.35 * t - (0.9 * t * t if k < 15 else -0.9 * t * t) * 0.6
            px = x + r * t * math.cos(a)
            py = y + r * t * math.sin(a)
            pts.append((px, py))
            if 0 < j < 8 and k % 3 == 1:
                nx, ny = -math.sin(a), math.cos(a)
                for sg in (-1, 1):
                    ticks.append(f'<line x1="{f(px)}" y1="{f(py)}" x2="{f(px+sg*nx*9+math.cos(a)*5)}" '
                                 f'y2="{f(py+sg*ny*9+math.sin(a)*5)}" stroke="#ffd34d" stroke-width="1.6"/>')
        g.append(f'<path d="{smooth_open(pts)}" stroke="#f2a90f" stroke-width="2" fill="none" stroke-linecap="round"/>')
        g += ticks
        if k % 3 == 1:
            g.append(f'<path d="{smooth_open(pts)}" stroke="#2b1d06" stroke-width="1.2" fill="none" stroke-dasharray="3 9"/>')
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
    sx = facing
    pts = [(x - 26 * s * sx, y), (x - 10 * s * sx, y - 9 * s), (x + 12 * s * sx, y - 8 * s), (x + 24 * s * sx, y - 2 * s),
           (x + 12 * s * sx, y + 6 * s), (x - 10 * s * sx, y + 7 * s)]
    g = [f'<path d="{smooth_closed(pts)}" fill="#f5ede0"/>']
    for dx in (-15, -3, 9):
        g.append(f'<path d="M{f(x+dx*s*sx)},{f(y-7*s)} l{f(4*s*sx)},{f(13*s)}" stroke="#bd2830" stroke-width="{f(4*s)}"/>')
    for k in range(5):
        lx = x + (-8 + k * 5) * s * sx
        g.append(f'<line x1="{f(lx)}" y1="{f(y+5*s)}" x2="{f(lx+3*s*sx)}" y2="{f(y+16*s)}" stroke="#f6d38a" stroke-width="{f(1.2*s)}"/>')
    for k in (-1, 1):
        g.append(f'<path d="M{f(x+22*s*sx)},{f(y-4*s)} q{f(30*s*sx)},{f((-30+k*8)*s)} {f(70*s*sx)},{f((-10+k*14)*s)}" stroke="#fff" stroke-width="{f(1.1*s)}" fill="none"/>')
        g.append(f'<path d="M{f(x+15*s*sx)},{f(y+3*s)} l{f(25*s*sx)},{f((9+k*5)*s)} l{f(9*s*sx)},{f(-3*k*s)}" stroke="#c52c31" stroke-width="{f(2.5*s)}" fill="none"/>')
    g.append(f'<circle cx="{f(x+18*s*sx)}" cy="{f(y-5*s)}" r="{f(2*s)}" fill="#111"/>')
    return "".join(g)


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
    ("Sea fan", "gorgonian", 100, 400),
    ("Leather coral", "Sarcophyton sp.", 760, 380),
    ("Orange cup coral", "Tubastraea coccinea", 790, 540),
    ("Banded coral shrimp ×2", "Stenopus hispidus", 700, 590),
    ("Boulder coral", "Porites lutea", 680, 760),
    ("Christmas tree worms", "Spirobranchus sp.", 775, 715),
    ("Feather star", "Lamprometra palmata", 930, 380),
    ("Yellow boxfish (juvenile)", "Ostracion cubicus", 900, 290),
    ("Table coral", "Acropora sp.", 1290, 360),
    ("Fluted giant clam", "Tridacna squamosa", 1060, 805),
    ("Hermit crab", "Diogenidae", 985, 852),
    ("Barrel sponge", "Xestospongia testudinaria", 1480, 650),
]


def reef_scene(state: str = "wide") -> str:
    """The whole tank in a 1600x900 box. state: wide | calm | alert."""
    rng = random.Random(SEED)
    alert = state == "alert"
    g = ['<defs>'
         '<linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c86b8"/>'
         '<stop offset=".55" stop-color="#0d4f86"/><stop offset="1" stop-color="#07284a"/></linearGradient>'
         '<linearGradient id="sand" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eadcb0"/>'
         '<stop offset="1" stop-color="#bda06a"/></linearGradient>'
         '<radialGradient id="rock" cx="40%" cy="30%" r="75%"><stop offset="0" stop-color="#7d6a61"/>'
         '<stop offset="1" stop-color="#3a2d2b"/></radialGradient>'
         '<filter id="soft"><feGaussianBlur stdDeviation="3"/></filter>'
         '</defs>',
         '<rect width="1600" height="900" fill="url(#water)"/>']
    for k in range(7):  # light shafts
        x0 = 120 + k * 230 + rng.uniform(-40, 40)
        g.append(f'<polygon points="{f(x0)},0 {f(x0+70)},0 {f(x0+210)},760 {f(x0+90)},760" fill="#ffffff" opacity="{f(rng.uniform(.035,.07))}"/>')
    for k in range(3):  # surface ripples
        pts = [(x, 18 + k * 12 + 5 * math.sin(x / 70 + k)) for x in range(0, 1601, 40)]
        g.append(f'<path d="{smooth_open(pts)}" stroke="#bfe9ff" stroke-width="1.5" fill="none" opacity=".25"/>')
    g.append('<g filter="url(#soft)" opacity=".75">')  # far rock and fans
    for cx in range(80, 1600, 170):
        g.append(f'<path d="{blob(rng, cx, 660, 130, 110)}" fill="#163a5c"/>')
    g.append('</g>')
    g.append(f'<g opacity=".85">{gorgonian(rng, 100, 640, 330, "#c9403a")}{gorgonian(rng, 1500, 600, 360, "#9b3fbf")}</g>')
    # sand
    sand = [(x, 770 + 10 * math.sin(x / 140)) for x in range(0, 1601, 80)]
    g.append(f'<path d="M0,900 L{smooth_open(sand)[1:]} L1600,900Z" fill="url(#sand)"/>')
    for k in range(12):
        y0 = 790 + k * 9
        pts = [(x, y0 + 3 * math.sin(x / 35 + k)) for x in range(0, 1601, 50)]
        g.append(f'<path d="{smooth_open(pts)}" stroke="#a88c58" stroke-width=".8" fill="none" opacity=".35"/>')
    for _ in range(80):
        g.append(f'<ellipse cx="{f(rng.uniform(0,1600))}" cy="{f(rng.uniform(800,895))}" rx="{f(rng.uniform(1.5,5))}" '
                 f'ry="{f(rng.uniform(1,2.5))}" fill="{rng.choice(["#f4ead2","#d9b9c4","#a8936a","#fff"])}" opacity=".8"/>')
    # cave behind the arch
    g.append(f'<path d="{blob(rng, 812, 610, 165, 120)}" fill="#0b0a12"/>')
    # rock masses with coralline + sponge patches, clipped to the rock
    for name, blobs in ROCK_MASSES.items():
        cid = uid("rk")
        paths = [blob(rng, *b, n=24, jit=0.14) for b in blobs]
        g.append(f'<defs><clipPath id="{cid}">' + "".join(f'<path d="{p}"/>' for p in paths) + '</clipPath></defs>')
        g += [f'<path d="{p}" fill="url(#rock)" stroke="#241b1a" stroke-width="2"/>' for p in paths]
        xs = [b[0] for b in blobs]
        ys = [b[1] for b in blobs]
        g.append(f'<g clip-path="url(#{cid})">')
        for _ in range(30):
            bx = rng.uniform(min(xs) - 120, max(xs) + 120)
            by = rng.uniform(min(ys) - 120, max(ys) + 120)
            col = rng.choice(["#c55a9a", "#9b4dab", "#e07ab0", "#b0487f", "#d9829f"])
            g.append(f'<path d="{blob(rng, bx, by, rng.uniform(10,34), rng.uniform(6,20), 12, .3)}" fill="{col}" opacity=".72"/>')
        for _ in range(9):
            bx = rng.uniform(min(xs) - 100, max(xs) + 100)
            by = rng.uniform(min(ys) - 60, max(ys) + 120)
            col = rng.choice(["#f08a24", "#3a7bd5", "#e9493a", "#f5c542"])
            g.append(f'<path d="{blob(rng, bx, by, rng.uniform(12,26), rng.uniform(7,14), 10, .35)}" fill="{col}" opacity=".9"/>')
        for _ in range(45):
            g.append(f'<circle cx="{f(rng.uniform(min(xs)-200,max(xs)+200))}" cy="{f(rng.uniform(min(ys)-180,max(ys)+180))}" '
                     f'r="{f(rng.uniform(1,3.2))}" fill="#150f0f" opacity=".4"/>')
        g.append('</g>')
    # sessile life on the rock
    g.append(zoanthids(rng, 330, 612, 70))
    g.append(zoanthids(rng, 1290, 712, 55, col="#f28c28", mouth="#3ad1c4"))
    g.append(goniopora(rng, 170, 528, 62, sway=0.25 if alert else 0.0))
    g.append(turbinaria(rng, 470, 478))
    g.append(turbinaria(rng, 1160, 482, 0.9))
    g.append(sarcophyton(rng, 760, 436, 0.95))
    g.append(tubastraea(rng, 718, 528, 8, down=True))
    g.append(crinoid(rng, 935, 408, 120, phase=1.2 if alert else 0.0))
    g.append(table_acropora(rng, 1290, 372, 300))
    g.append(feather_duster(rng, 520, 600, -100, out=not alert))
    g.append(feather_duster(rng, 1100, 610, -70, out=True))
    g.append(feather_duster(rng, 1372, 438, -60, out=True, s=0.8))
    g.append(phyllidia(rng, 262, 692, 1.0, rot=-12))
    g.append(cleaner_shrimp(rng, 700, 598, 1.0, facing=1 if not alert else -1))
    g.append(cleaner_shrimp(rng, 930, 606, 0.9, facing=-1))
    g.append(porites(rng, 760, 772, 125, 78, worms_out=not alert))
    g.append(barrel_sponge(rng, 1478, 845, 230, 130))
    g.append(giant_clam(rng, 1060, 815, 140, open_=0.35 if alert else 1.0))
    g.append(fungia(rng, 520, 838))
    g.append(fungia(rng, 600, 866, 0.8, "#9cbf7a"))
    g.append(fungia(rng, 1185, 852, 0.9, "#d7a3b8"))
    # extra density: a pink Pocillopora on the right mass, more polyp carpets and worms on the rock
    g.append(branching_coral(rng, 1185, 560, 95, col="#e58fb5", tip="#ffe1ee"))
    g.append(zoanthids(rng, 860, 452, 40, n=22, col="#7b5cd6", mouth="#9ff27a"))
    g.append(zoanthids(rng, 1010, 690, 35, n=18, col="#2fbf71", mouth="#ff5c8a"))
    for wx, wy in ((430, 600), (455, 585), (1150, 650), (1395, 560), (240, 610)):
        g.append(christmas_tree_worm(rng, wx, wy, 1.0, not alert))
    g.append(feather_duster(rng, 1015, 560, -60, out=True, s=0.7))
    g.append(hermit_crab(rng, 985, 860))
    # humbugs live in the branching head: hover above it, or hide inside it
    if alert:
        g.append(humbug(rng, 285, 380, 0.85, 1))
        g.append(humbug(rng, 325, 398, 0.8, -1))
        g.append(branching_coral(rng, 300, 470, 190))
        g.append(guard_crab(rng, 318, 398, 1.4, threat=True))
    else:
        g.append(branching_coral(rng, 300, 470, 190))
        g.append(guard_crab(rng, 318, 398, 1.4))
        g.append(humbug(rng, 300, 262, 1.0, 1))
        g.append(humbug(rng, 372, 240, 0.95, -1))
    # the boxfish: mid-water in calm views, passing the boulder when alert
    g.append(boxfish(rng, 640, 655, 1.15, 1) if alert else boxfish(rng, 905, 288, 1.2, -1))
    return "".join(g)


# ─────────────────────────────── page chrome ────────────────────────────────

CSS = """
*{box-sizing:border-box}
body{margin:0;width:1440px;height:900px;overflow:hidden;background:#0d1117;color:#e6edf3;
font:14px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;align-items:baseline;gap:14px;padding:14px 24px;border-bottom:1px solid #30363d}
header h1{margin:0;font-size:19px;font-weight:650}
header .sub{color:#9198a1;font-size:13px}
header .tag{margin-left:auto;font:600 11px ui-monospace,monospace;letter-spacing:.06em;color:#9198a1;
border:1px solid #30363d;border-radius:10px;padding:2px 9px}
h2{font-size:15px;margin:0 0 4px}
.cap{color:#9198a1;font-size:12.5px;margin:0 0 8px}
.note{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px;font-size:12.5px;color:#c9d1d9}
.note b{color:#e6edf3}
code{font:12px ui-monospace,monospace;color:#ffa657}
"""


def page(title: str, sub: str, body: str) -> str:
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><title>{title}</title>'
            f'<style>{CSS}</style></head><body><header><h1>{title}</h1><span class="sub">{sub}</span>'
            f'<span class="tag">MOCKUP — NOT SHIPPED</span></header>{body}</body></html>\n')


def tv(scene: str, vb: str, w: int, h: int) -> str:
    return (f'<svg width="{w}" height="{h}" viewBox="{vb}" preserveAspectRatio="xMidYMid slice" '
            f'style="display:block;border:6px solid #1a1a1a;border-radius:6px;box-shadow:0 0 0 1px #30363d">{scene}</svg>')


def tank_wide() -> str:
    # TV frame 960x540 at (240,72) in the page; scene 1600x900 → scale 0.6
    fx, fy, sc = 240, 70, 0.6
    scene = reef_scene("wide")
    # Numbered pins on the picture, names in two legend columns outside the frame:
    # pins never cross, and long names have room.
    items = sorted(CALLOUTS, key=lambda c: (c[2] // 200, c[3]))
    half = (len(items) + 1) // 2
    ov = ['<svg width="1440" height="560" style="position:absolute;left:0;top:0;pointer-events:none">']
    for i, (name, latin, ax, ay) in enumerate(items):
        px, py = fx + ax * sc, fy + ay * sc
        ov.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="9.5" fill="#ffd166" stroke="#000" stroke-width="1.2"/>'
                  f'<text x="{f(px)}" y="{f(py+4)}" text-anchor="middle" font-size="11" font-weight="700" fill="#000">{i+1}</text>')
        col, row = (0, i) if i < half else (1, i - half)
        lx = 16 if col == 0 else 1214
        ly = 22 + row * (520 / max(half - 1, 1))
        ov.append(f'<circle cx="{lx+9}" cy="{f(ly-4)}" r="9" fill="#ffd166"/>'
                  f'<text x="{lx+9}" y="{f(ly)}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#000">{i+1}</text>'
                  f'<text x="{lx+24}" y="{f(ly-2)}" font-size="12.5" fill="#e6edf3" font-weight="600">{name}</text>'
                  f'<text x="{lx+24}" y="{f(ly+12)}" font-size="11" fill="#9198a1" font-style="italic">{latin}</text>')
    ov.append('</svg>')
    body = (f'<div style="position:relative;height:843px">'
            f'<div style="position:absolute;left:{fx}px;top:{fy}px">{tv(scene, "0 0 1600 900", 960, 540)}</div>'
            + "".join(ov) +
            '<div style="position:absolute;left:240px;top:630px;width:960px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">'
            '<div class="note"><b>Wide camera, idle.</b> Two rock masses and a central arch on a sand bed; '
            'the cave under the arch is the cleaner-shrimp station. Three fish live among the reef life.</div>'
            '<div class="note"><b>Budget.</b> Static reef ≤ 48,000 triangles in ≤ 8 static groups; '
            '16 animated actors with multi-curve DFRM (33 without it); one 1024² reef atlas. Gate: ≥ 20 FPS on cast1.</div>'
            '<div class="note"><b>Labels sit outside the TV frame</b> and are not drawn in the game. '
            'Species pending a Gulf of Thailand record are swapped in Phase 0, not here.</div>'
            '</div></div>')
    return page("Gulf of Thailand Reef — wide view", "aquarium_thai_reef · default camera · 1920×1080 TV", body)


def tank_close() -> str:
    vb = "380 392 760 427.5"
    calm, alert = reef_scene("calm"), reef_scene("alert")
    body = ('<div style="display:grid;grid-template-columns:688px 688px;gap:24px;padding:18px 24px 0">'
            '<div><h2>1. Close camera — calm</h2><p class="cap">The boxfish is away. Christmas tree worms and '
            'the feather duster are open; the clam mantle is fully spread; cleaner shrimp wave their antennae at the cave mouth.</p>'
            f'{tv(calm, vb, 688, 387)}</div>'
            '<div><h2>2. Boxfish passing — the reef flinches</h2><p class="cap">Within 1.5 body lengths, worm crowns on the '
            'boulder snap shut (0.15 s) and the duster withdraws; the clam half-closes; the humbugs drop into their coral head. '
            'Each reopens after its own 3–8 s timer once the fish has gone.</p>'
            f'{tv(alert, vb, 688, 387)}</div></div>'
            '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:16px 24px">'
            '<div class="note"><b>Worms.</b> All 15 crowns in the tank are curves of <i>one</i> actor; a retract is the '
            'curve\'s scale cell going to 0.02 (multi-curve DFRM, engine proposal E1–E6).</div>'
            '<div class="note"><b>Feather dusters.</b> Four crowns, one actor, one curve each: '
            'per-curve clip "furl" 0.2 s, "unfurl" 2.5 s, started independently.</div>'
            '<div class="note"><b>Giant clam.</b> Mantle ripple is a DFRM weighted transform; '
            'a shadow (fish above, within 1 m) closes the valves to 35 %.</div>'
            '<div class="note"><b>Cleaner shrimp.</b> If the boxfish stops within reach of the cave mouth for 2 s, '
            'one shrimp walks out onto it and "cleans" for 4–6 s.</div></div>'
            '<div style="padding:0 24px"><h2>3. One pass, second by second</h2>' + timeline_svg() + '</div>')
    return page("Gulf of Thailand Reef — close camera", "two states of the same moment · labels omitted", body)


TIMELINE = [  # (row, colour, [(start s, end s, kind)]) kind: shut | open | move
    ("Boxfish within 1.5 body lengths", "#ffd400", [(0, 1.5, "move")]),
    ("Christmas tree worm clusters", "#e63946", [(0, .15, "shut"), (.15, 5.2, "hid"), (5.2, 6.7, "open")]),
    ("Feather duster", "#b0487f", [(0, .2, "shut"), (.2, 6.5, "hid"), (6.5, 9.0, "open")]),
    ("Giant clam (valves to 35 %)", "#36c6d3", [(0, .6, "shut"), (.6, 3.5, "hid"), (3.5, 5.5, "open")]),
    ("Humbugs dive into the coral head", "#e6edf3", [(0, .5, "shut"), (.5, 3.0, "hid"), (3.0, 4.0, "open")]),
    ("Guard crab: claws-up threat at the coral edge", "#f97316", [(0, .3, "shut"), (.3, 2.5, "move"), (2.5, 3.2, "open")]),
    ("Cleaner shrimp (never hide: they advertise)", "#f6b33a", [(0, 10, "move")]),
]


def timeline_svg(w=1392, h=236) -> str:
    x0, x1, top, rowh = 300, w - 20, 26, 28
    sx = (x1 - x0) / 10
    g = [f'<svg width="{w}" height="{h}" style="display:block">']
    for t in range(11):
        x = x0 + t * sx
        g.append(f'<line x1="{f(x)}" y1="{top-6}" x2="{f(x)}" y2="{top+len(TIMELINE)*rowh}" stroke="#30363d"/>'
                 f'<text x="{f(x)}" y="{top-10}" text-anchor="middle" font-size="11" fill="#9198a1">{t} s</text>')
    for i, (label, col, segs) in enumerate(TIMELINE):
        y = top + i * rowh
        g.append(f'<text x="{x0-12}" y="{y+17}" text-anchor="end" font-size="12.5" fill="#c9d1d9">{label}</text>')
        for a, b, kind in segs:
            op = {"move": .85, "shut": 1, "hid": .25, "open": .6}[kind]
            g.append(f'<rect x="{f(x0+a*sx)}" y="{y+5}" width="{f(max((b-a)*sx,3))}" height="16" rx="3" fill="{col}" opacity="{op}"/>')
    g.append(f'<text x="{x0}" y="{h-6}" font-size="11.5" fill="#9198a1">Solid = closing · faint = hidden (own 3–8 s timer after the fish leaves) · mid = re-opening. '
             f'Times are the Phase 2 starting values, tuned on the desktop.</text></svg>')
    return "".join(g)


def menu_svg(rows, cursor, first, total) -> str:
    vis = rows[first:first + 6]
    g = ['<svg viewBox="0 0 1920 1080" width="600" height="338" style="display:block;border:6px solid #1a1a1a;border-radius:6px">',
         '<rect width="1920" height="1080" fill="#0f1726"/>',
         '<text x="960" y="132" text-anchor="middle" font-size="80" font-weight="700" fill="#ffad42">WF Aquarium</text>',
         '<text x="960" y="210" text-anchor="middle" font-size="34" fill="#93a4bd">Choose a tank</text>']
    for i, label in enumerate(vis):
        idx = first + i
        y = 300 + i * 100
        if idx == cursor:
            g.append(f'<rect x="360" y="{y}" width="1200" height="92" fill="#22406b"/><rect x="360" y="{y}" width="14" height="92" fill="#4cc764"/>')
        weight = 700 if idx == cursor else 400
        col = "#ffffff" if idx == cursor else "#c9d4e3"
        g.append(f'<text x="406" y="{y+66}" font-size="56" font-weight="{weight}" fill="{col}">{label}</text>')
        if label == "Gulf of Thailand Reef":
            g.append(f'<rect x="1400" y="{y+24}" width="120" height="44" rx="22" fill="none" stroke="#ffd166" stroke-width="3"/>'
                     f'<text x="1460" y="{y+56}" text-anchor="middle" font-size="28" fill="#ffd166">new</text>')
    if first > 0:
        g.append('<polygon points="936,290 984,290 960,262" fill="#93a4bd"/>')
    if first + 6 < total:
        g.append('<polygon points="936,904 984,904 960,932" fill="#93a4bd"/>')
    g.append(f'<text x="1550" y="935" text-anchor="end" font-size="34" fill="#93a4bd">{cursor+1} / {total}</text>')
    g.append('<text x="960" y="1028" text-anchor="middle" font-size="34" fill="#93a4bd">Up/Down choose - Space starts - Backspace returns here; here exits</text>')
    g.append('</svg>')
    return "".join(g)


REAL_LABEL, CEL_LABEL = "Gulf of Thailand Reef", "Gulf of Thailand Reef — Anime"
DREAM_REAL, DREAM_CEL = "Thai Reef", "Thai Reef Anime"


def selectors() -> str:
    rows = ["Clownfish &amp; Sea Anemone", "Blue Shrimp", "Calm Betta", "Jellyfish", "Lionfish",
            "Planted Tank", "Asian Arowana", "Tiger Barbs", REAL_LABEL, CEL_LABEL]
    dream = ["Random", "Clownfish", "Blue Shrimp", "Betta", "Jellyfish", "Lionfish",
             "Planted Urchin", "Arowana", "Tiger Barbs", DREAM_REAL, DREAM_CEL]
    phone = ['<div style="width:300px;border:10px solid #2b313b;border-radius:28px;background:#111823;padding:12px 16px;font-size:12.5px;line-height:1.15">',
             '<div style="font-weight:650;font-size:15px">WF Screensaver</div><div style="color:#8b98a9;margin-bottom:4px">Bedroom TV · connected</div>',
             '<div style="color:#8b98a9;margin:2px 0">Tank</div>']
    for d in dream:
        sel = d == DREAM_CEL
        new = d in (DREAM_REAL, DREAM_CEL)
        phone.append(f'<div style="display:flex;align-items:center;gap:10px;padding:3px 10px;border-radius:7px;'
                     f'{"background:#1f3a24;border:1px solid #4cc764;" if sel else "border:1px solid transparent;"}">'
                     f'<span style="width:14px;height:14px;border-radius:50%;border:2px solid {"#4cc764" if sel else "#5b6676"};'
                     f'{"background:radial-gradient(#4cc764 45%,transparent 50%)" if sel else ""}"></span>{d}'
                     f'{"<span style=margin-left:auto;color:#ffd166;font-size:11px>new</span>" if new else ""}</div>')
    phone.append('<div style="color:#8b98a9;font-size:11.5px;margin-top:4px">Random now draws from 10 tanks.</div></div>')
    body = ('<div style="display:grid;grid-template-columns:612px 612px;gap:48px;padding:12px 60px 0 60px">'
            '<div><h2>1. TV selector — the anime reef chosen</h2><p class="cap">Row 10 of 10; the list scrolls as today (6 visible rows). '
            'The "new" pill is mockup-only.</p>' + menu_svg(rows, 9, 4, 10) + '</div>'
            '<div><h2>2. TV selector — opened (first row)</h2><p class="cap">Indices 0–7 are unchanged, so saved resume state and '
            'tests keyed on them keep working. The counter reads 1 / 10.</p>' + menu_svg(rows, 0, 0, 10) + '</div></div>'
            '<div style="display:grid;grid-template-columns:340px 1fr;gap:24px;padding:10px 60px">'
            '<div><h2>3. Phone — Dream tank list</h2>' + "".join(phone) + '</div>'
            '<div style="display:flex;flex-direction:column;gap:10px;padding-top:26px">'
            '<div class="note"><b>Menu manifest.</b> Two lines appended to <code>wflevels/aquarium-menu.manifest</code>:<br>'
            f'<code>level aquarium_thai_reef-standalone.iff | {REAL_LABEL}</code><br>'
            f'<code>level aquarium_thai_reef_anime-standalone.iff | {CEL_LABEL}</code></div>'
            '<div class="note"><b>Dream list.</b> <code>TankChoice.IDS</code> gains <code>aquarium_thai_reef</code> and '
            f'<code>aquarium_thai_reef_anime</code>; <code>LABELS</code> gains <code>{DREAM_REAL}</code> and <code>{DREAM_CEL}</code>. '
            '<code>TankSettingsProvider</code> already serialises every entry, so no phone code changes.</div>'
            '<div class="note"><b>Same-length lists, checked.</b> <code>tests/test_aquarium_menu.py</code> (TOC 11 → 13 chunks, 10 titles) '
            'and <code>tests/test_aquarium_screensaver_input.py</code> pin both lists, so a half-registered tank fails CI.</div>'
            f'<div class="note"><b>Long label.</b> "{CEL_LABEL}" measures ≈ 860 px of the 1,154 px row at SemiBold 56, '
            'so it needs no truncation.</div></div></div>')
    return page("Selectors — two reef styles", "Android aquarium menu · Dream tank setting", body)


# ─────────────────────────────── the two styles ─────────────────────────────

STYLE_DEFS = """
<svg width="0" height="0" style="position:absolute">
<defs>
  <filter id="real" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feTurbulence type="fractalNoise" baseFrequency="0.032" numOctaves="4" seed="7" result="mottle"/>
    <feColorMatrix in="mottle" type="saturate" values="0" result="mottleG"/>
    <feComposite in="SourceGraphic" in2="mottleG" operator="arithmetic" k1="1.15" k2="0.55" k3="0" k4="0" result="mottled"/>
    <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="3" result="grain"/>
    <feColorMatrix in="grain" type="saturate" values="0" result="grainG"/>
    <feComposite in="mottled" in2="grainG" operator="arithmetic" k1="0.5" k2="0.78" k3="0" k4="0" result="grained"/>
    <feGaussianBlur in="grained" stdDeviation="0.7" result="soft"/>
    <feColorMatrix in="soft" type="matrix" result="graded"
      values="0.70 0.10 0.02 0 0.01   0.04 0.95 0.12 0 0.04   0.02 0.16 1.0 0 0.07   0 0 0 1 0"/>
  </filter>
  <filter id="caustic" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feTurbulence type="turbulence" baseFrequency="0.011 0.026" numOctaves="2" seed="11" result="t"/>
    <feColorMatrix in="t" type="luminanceToAlpha" result="ta"/>
    <feComponentTransfer in="ta" result="lines"><feFuncA type="table" tableValues="1 0.55 0 0 0 0 0 0"/></feComponentTransfer>
    <feFlood flood-color="#d9fbff" result="c"/>
    <feComposite in="c" in2="lines" operator="in"/>
  </filter>
  <filter id="cel" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feColorMatrix in="SourceGraphic" type="saturate" values="1.45" result="sat"/>
    <feComponentTransfer in="sat" result="post">
      <feFuncR type="discrete" tableValues="0.04 0.30 0.58 0.84 1"/>
      <feFuncG type="discrete" tableValues="0.06 0.32 0.60 0.86 1"/>
      <feFuncB type="discrete" tableValues="0.14 0.40 0.66 0.90 1"/>
    </feComponentTransfer>
    <feColorMatrix in="SourceGraphic" type="saturate" values="0" result="grey"/>
    <feConvolveMatrix in="grey" order="3" kernelMatrix="-1 -1 -1 -1 8 -1 -1 -1 -1" divisor="1" preserveAlpha="true" result="edge"/>
    <feColorMatrix in="edge" type="luminanceToAlpha" result="edgeA"/>
    <feComponentTransfer in="edgeA" result="edgeT"><feFuncA type="discrete" tableValues="0 1 1 1 1 1"/></feComponentTransfer>
    <feMorphology in="edgeT" operator="dilate" radius="0.7" result="thick"/>
    <feFlood flood-color="#1c1236" result="ink"/>
    <feComposite in="ink" in2="thick" operator="in" result="lines"/>
    <feMerge><feMergeNode in="post"/><feMergeNode in="lines"/></feMerge>
  </filter>
  <radialGradient id="vignette" cx="50%" cy="45%" r="75%">
    <stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/>
  </radialGradient>
  <linearGradient id="causticMask" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset=".85" stop-color="#fff" stop-opacity=".12"/>
    <stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
  <mask id="cmask"><rect width="1600" height="900" fill="url(#causticMask)"/></mask>
  <linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#3fa7b8" stop-opacity=".10"/><stop offset=".6" stop-color="#0e5a6e" stop-opacity=".22"/>
    <stop offset="1" stop-color="#062a3a" stop-opacity=".30"/>
  </linearGradient>
</defs>
</svg>"""


def sparkle(x, y, r):
    return (f'<path d="M{f(x)},{f(y-r)} Q{f(x+r*.16)},{f(y-r*.16)} {f(x+r)},{f(y)} Q{f(x+r*.16)},{f(y+r*.16)} {f(x)},{f(y+r)} '
            f'Q{f(x-r*.16)},{f(y+r*.16)} {f(x-r)},{f(y)} Q{f(x-r*.16)},{f(y-r*.16)} {f(x)},{f(y-r)}Z" fill="#fff"/>')


def styled_tv(style: str, vb: str, w: int, h: int, state: str) -> str:
    """One TV frame: the shared reef (<use>) under a style filter, plus that style's overlays."""
    use = f'<use href="#reef-{state}" filter="url(#{style})"/>'
    if style == "real":
        over = ('<rect width="1600" height="900" filter="url(#caustic)" mask="url(#cmask)" style="mix-blend-mode:screen"/>'
                '<rect width="1600" height="900" fill="url(#haze)"/>'
                + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="#dff7ff" stroke-opacity=".55" stroke-width="1.2"/>'
                          for x, y, r in ((612, 520, 4), (618, 470, 3), (606, 420, 2.5), (1012, 380, 3), (1018, 330, 2)))
                + '<rect width="1600" height="900" fill="url(#vignette)"/>')
    else:
        rng = random.Random(5)
        over = "".join(sparkle(rng.uniform(60, 1540), rng.uniform(40, 360), rng.uniform(5, 13)) for _ in range(16))
        over += "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#e9fdff" stroke="#1c1236" stroke-width="2.5"/>'
                        f'<circle cx="{x-r*.35}" cy="{y-r*.35}" r="{r*.3}" fill="#fff"/>'
                        for x, y, r in ((612, 520, 7), (622, 468, 5), (606, 425, 4), (1012, 380, 6), (1020, 335, 4)))
        # anime eye highlights on the fish (wide state positions)
        if state == "calm":
            over += ('<circle cx="928" cy="272" r="5" fill="#fff"/><circle cx="314" cy="254" r="3" fill="#fff"/>'
                     '<circle cx="357" cy="232" r="3" fill="#fff"/>')
    return (f'<svg width="{w}" height="{h}" viewBox="{vb}" preserveAspectRatio="xMidYMid slice" '
            f'style="display:block;border:6px solid #1a1a1a;border-radius:6px;box-shadow:0 0 0 1px #30363d">{use}{over}</svg>')


def styles() -> str:
    defs = (f'<svg width="0" height="0" style="position:absolute"><defs><g id="reef-calm">{reef_scene("calm")}</g></defs></svg>'
            + STYLE_DEFS)
    wide, close = "0 0 1600 900", "380 392 760 427.5"
    W, H = 640, 360
    body = (defs +
            '<div style="display:grid;grid-template-columns:640px 640px;gap:12px 40px;padding:6px 60px 0">'
            f'<div><h2>1. Ultra-realistic — "{REAL_LABEL}"</h2><p class="cap">Baked light and occlusion, '
            'photographic-detail atlas, per-channel water absorption (reds fade first), caustics on lit surfaces, '
            'drifting bubbles, a soft vignette. Same reef, same behaviour.</p>' + styled_tv("real", wide, W, H, "calm") + '</div>'
            f'<div><h2>2. Cartoon / anime / cel — "{CEL_LABEL}"</h2><p class="cap">Flat posterised palette, 3-band toon light, '
            'ink outlines (inverted hull), saturated colour, sparkles and big eye highlights; cartoon bubbles.</p>'
            + styled_tv("cel", wide, W, H, "calm") + '</div>'
            + styled_tv("real", close, W, H, "calm").replace('<svg', '<div><svg', 1).replace('</svg>', '</svg></div>', 1)
            + styled_tv("cel", close, W, H, "calm").replace('<svg', '<div><svg', 1).replace('</svg>', '</svg></div>', 1)
            + '</div>'
            '<p class="cap" style="padding:6px 60px 0">Mockup approximations with SVG filters: the real looks come from the '
            'per-style assets and shaders in the plan (style table, engine proposal S1–S3), not from post-processing.</p>')
    return page("Two styles, one reef", "ultra-realistic · cartoon / anime / cel-shaded · wide and close cameras", body)


# ─────────────────────────────── the poster ─────────────────────────────────

COAST = [(102.2, 5.8), (102.2, 6.1), (101.3, 6.9), (100.6, 7.2), (100.3, 7.6), (100.1, 8.3), (99.9, 8.7),
         (99.5, 9.2), (99.2, 9.8), (99.2, 10.4), (99.5, 11.0), (99.7, 11.6), (99.95, 12.4), (100.0, 13.2),
         (100.5, 13.5), (100.9, 13.4), (100.95, 13.0), (100.9, 12.65), (101.3, 12.65), (101.8, 12.5),
         (102.3, 12.2), (102.6, 11.9), (102.9, 11.6), (103.1, 11.1), (103.5, 10.6), (104.0, 10.5),
         (104.5, 10.4), (104.8, 10.1), (104.9, 9.6), (104.8, 8.6), (105.8, 8.6), (105.8, 14.2), (98.5, 14.2), (98.5, 5.8)]
SITES = [("Ko Tao", 99.84, 10.1), ("Ko Samui", 100.0, 9.5), ("Ang Thong", 99.67, 9.68), ("Ko Chang", 102.35, 12.05),
         ("Ko Kut", 102.55, 11.65), ("Ko Lan", 100.78, 12.92), ("Ko Kham", 100.85, 12.62)]


def poster_map(x, y, w, h) -> str:
    def P(lon, lat):
        return x + (lon - 98.5) / 7.3 * w, y + (14.2 - lat) / 8.4 * h
    g = [f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="#bfe3f2"/>']
    pts = [P(lo, la) for lo, la in COAST]
    g.append('<path d="M' + " L".join(f"{f(a)},{f(b)}" for a, b in pts) + 'Z" fill="#efe6d2" stroke="#8a7e66" stroke-width=".3"/>')
    for lo, la, rx in ((99.95, 9.5, .9), (100.03, 9.75, .7), (99.84, 10.1, .45), (102.35, 12.05, .8), (102.55, 11.65, .55), (103.95, 10.2, 1.0)):
        px, py = P(lo, la)
        g.append(f'<ellipse cx="{f(px)}" cy="{f(py)}" rx="{f(rx)}" ry="{f(rx*0.8)}" fill="#efe6d2" stroke="#8a7e66" stroke-width=".25"/>')
    for name, lo, la in SITES:
        px, py = P(lo, la)
        right = lo < 101
        g.append(f'<circle cx="{f(px)}" cy="{f(py)}" r="1.1" fill="#e0457b"/>'
                 f'<text x="{f(px+(2 if right else -2))}" y="{f(py+0.9)}" font-size="2.6" fill="#173b57" '
                 f'text-anchor="{"start" if right else "end"}">{name}</text>')
    tx, ty = P(102.3, 9.2)
    g.append(f'<text x="{f(tx)}" y="{f(ty)}" font-size="4.2" font-style="italic" fill="#1d5f86" text-anchor="middle">Gulf of Thailand</text>'
             f'<text x="{f(tx)}" y="{f(ty+4.6)}" font-size="3.4" fill="#1d5f86" text-anchor="middle">อ่าวไทย</text>')
    for name, lo, la in (("THAILAND", 101.6, 13.9), ("CAMBODIA", 104.2, 11.9), ("MALAYSIA", 100.0, 6.2), ("VIETNAM", 105.3, 10.1)):
        px, py = P(lo, la)
        g.append(f'<text x="{f(px)}" y="{f(py)}" font-size="2.6" letter-spacing=".4" fill="#6b604c" text-anchor="middle">{name}</text>')
    g.append(f'<text x="{f(x+1.5)}" y="{f(y+h-1.6)}" font-size="2.2" fill="#4b6a80">schematic, not to scale · reef sites to verify in Phase 0</text>')
    return "".join(g)


GALLERY = [
    ("Christmas tree worm", "Spirobranchus", lambda r: christmas_tree_worm(r, 0, 10, 2.6)),
    ("Feather duster", "Sabellastarte", lambda r: feather_duster(r, 0, 32, -90, True, 0.75)),
    ("Fluted giant clam", "Tridacna squamosa", lambda r: giant_clam(r, 0, 6, 110)),
    ("Feather star", "Lamprometra palmata", lambda r: crinoid(r, 0, 26, 52)),
    ("Banded coral shrimp", "Stenopus hispidus", lambda r: cleaner_shrimp(r, -14, 8, 1.1)),
    ("Phyllidia nudibranch", "Phyllidia varicosa", lambda r: phyllidia(r, 0, 4, 1.5)),
    ("Hermit crab", "Diogenidae", lambda r: hermit_crab(r, 0, 12, 1.4)),
    ("Boulder coral", "Porites", lambda r: porites(r, 0, 26, 52, 34)),
    ("Table coral", "Acropora", lambda r: table_acropora(r, 0, -4, 120)),
    ("Flowerpot coral", "Goniopora", lambda r: goniopora(r, 0, 16, 34)),
    ("Leather coral", "Sarcophyton", lambda r: sarcophyton(r, 0, 30, 0.62)),
    ("Orange cup coral", "Tubastraea coccinea", lambda r: tubastraea(r, -60, 18, 6, down=False)),
    ("Yellow scroll coral", "Turbinaria", lambda r: turbinaria(r, 0, 10, 0.9)),
    ("Barrel sponge", "Xestospongia testudinaria", lambda r: barrel_sponge(r, 0, 38, 70, 50)),
    ("Coral guard crab", "Trapezia cymodoce", lambda r: guard_crab(r, 0, 10, 2.0)),
]


def poster_svg() -> str:
    rng = random.Random(SEED + 1)
    g = ['<svg viewBox="0 0 297 420" width="560" height="792" style="display:block;background:#fffdf8;box-shadow:0 0 0 1px #30363d,0 8px 30px #0008" '
         'font-family="ui-sans-serif,system-ui,sans-serif">']
    # header band
    g.append('<rect width="297" height="56" fill="#0b3a5e"/>')
    g.append('<text x="12" y="22" font-size="13" font-weight="800" fill="#fff">Reef of the Gulf of Thailand</text>')
    g.append('<text x="12" y="33" font-size="5.6" fill="#ffd166">แนวปะการังอ่าวไทย · invertebrates, two fishes, one shallow sea</text>')
    g.append('<text x="12" y="46" font-size="3.6" fill="#cfe3f2">The life of the WF Aquarium\'s ninth tank, and the real reefs it is drawn from.</text>')
    g.append(f'<svg x="214" y="5" width="78" height="46" viewBox="560 160 640 340" preserveAspectRatio="xMidYMid slice">{reef_scene("wide")}</svg>')
    # 1 habitat
    g.append('<text x="12" y="68" font-size="6" font-weight="700" fill="#0b3a5e">1 · The habitat</text>')
    g.append(poster_map(12, 72, 120, 120))
    facts = ["A shallow, semi-enclosed sea: mean depth ≈ 45 m",
             "Fringing reefs around islands, not barrier reefs",
             "Monsoon-driven: turbid wet season, clear dry season",
             "Massive Porites dominate the inner, siltier reefs",
             "Recurrent bleaching years: 1998, 2010, 2016, 2024",
             "Reefs grow on granite boulders and old coral rock",
             "Water 28–31 °C; the tank runs a reef-keeper 26 °C"]
    for i, t in enumerate(facts):
        y = 80 + i * 13
        g.append(f'<circle cx="141" cy="{y-1.3}" r="1.2" fill="#e0457b"/><text x="145" y="{y}" font-size="3.8" fill="#222">{t}</text>')
        g.append(f'<rect x="145" y="{y+2}" width="16" height="3.6" rx="1.8" fill="#fde7b0"/><text x="153" y="{y+4.8}" font-size="2.4" text-anchor="middle" fill="#7a5a00">verify</text>')
    # 2 invertebrate gallery 4x4
    g.append('<text x="12" y="206" font-size="6" font-weight="700" fill="#0b3a5e">2 · Life without a backbone</text>')
    cw, ch = 66.5, 34
    for i, (name, latin, draw) in enumerate(GALLERY):
        cx, cy = 12 + (i % 4) * (cw + 3), 211 + (i // 4) * (ch + 3)
        g.append(f'<rect x="{f(cx)}" y="{f(cy)}" width="{f(cw)}" height="{f(ch)}" rx="2" fill="#eaf4f8"/>')
        g.append(f'<g transform="translate({f(cx+14)} {f(cy+18)}) scale(.18)">{draw(rng)}</g>')
        g.append(f'<text x="{f(cx+29)}" y="{f(cy+9)}" font-size="3.2" font-weight="700" fill="#0b3a5e">{name}</text>'
                 f'<text x="{f(cx+29)}" y="{f(cy+13)}" font-size="2.6" font-style="italic" fill="#555">{latin}</text>')
        for k in range(3):
            g.append(f'<rect x="{f(cx+29)}" y="{f(cy+17+k*3.8)}" width="{f(33-k*6)}" height="1.8" fill="#c5d6de"/>')
        tag = "moves" if i < 8 else "builds"
        g.append(f'<rect x="{f(cx+29)}" y="{f(cy+28.5)}" width="13" height="3.6" rx="1.8" fill="{"#d7f0dd" if i < 8 else "#e8e0f5"}"/>'
                 f'<text x="{f(cx+35.5)}" y="{f(cy+31.3)}" font-size="2.4" text-anchor="middle" fill="#333">{tag}</text>')
    # 3 the fishes
    y0 = 386
    g.append('<text x="12" y="370" font-size="6" font-weight="700" fill="#0b3a5e">3 · The two fishes</text>')
    g.append(f'<g transform="translate(26 {y0+2}) scale(.32)">{humbug(rng, 0, 0, 1, 1)}{humbug(rng, 52, -10, .9, -1)}</g>')
    g.append(f'<text x="50" y="{y0-3}" font-size="4.4" font-weight="700" fill="#0b3a5e">Reticulated dascyllus ×2</text>'
             f'<text x="50" y="{y0+2}" font-size="3" font-style="italic" fill="#555">Dascyllus reticulatus — lives in one branching coral head, dives into it</text>')
    g.append(f'<g transform="translate(166 {y0+1}) scale(.34)">{boxfish(rng, 0, 0, 1, 1)}</g>')
    g.append(f'<text x="182" y="{y0-3}" font-size="4.4" font-weight="700" fill="#0b3a5e">Yellow boxfish (juvenile)</text>'
             f'<text x="182" y="{y0+2}" font-size="3" font-style="italic" fill="#555">Ostracion cubicus — rigid box, swims with its fins</text>')
    for x0 in (50, 182):
        for k in range(2):
            g.append(f'<rect x="{x0}" y="{y0+5+k*3.4}" width="{90-k*20}" height="1.6" fill="#c5d6de"/>')
    # footer
    g.append('<rect y="402" width="297" height="18" fill="#0b3a5e"/>')
    for i, (lab, col) in enumerate((("verified", "#c8f0d0"), ("other region", "#fde7b0"), ("ours", "#d9e4ff"))):
        g.append(f'<rect x="{12+i*30}" y="408" width="26" height="5" rx="2.5" fill="{col}"/>'
                 f'<text x="{25+i*30}" y="411.8" font-size="3" text-anchor="middle" fill="#222">{lab}</text>')
    g.append('<text x="285" y="412" font-size="3" text-anchor="end" fill="#cfe3f2">Sources: docs/reference/thai-reef-research.md · World Foundry · 2026</text>')
    g.append('</svg>')
    return "".join(g)


def poster() -> str:
    body = ('<div style="display:grid;grid-template-columns:640px 1fr;gap:28px;padding:14px 24px">'
            f'<div style="display:flex;justify-content:center">{poster_svg()}</div>'
            '<div style="display:flex;flex-direction:column;gap:12px;padding-top:6px">'
            '<h2>A3 portrait, 297 × 420 mm — layout only</h2>'
            '<p class="cap">Grey bars stand for body text written in Phase 0 from the research document. The drawings are the same '
            'procedural art as the tank mockups; the printed poster gets finished panels.</p>'
            '<div class="note"><b>1 · The habitat.</b> A schematic map of the Gulf with the reef islands (Ko Tao, Ko Samui, Ang Thong, '
            'Ko Chang, Ko Kut, Ko Lan, Ko Kham), and seven facts: depth, reef type, monsoon, Porites dominance, bleaching years, '
            'substrate, temperature. Every fact prints with a chip.</div>'
            '<div class="note"><b>2 · Life without a backbone.</b> 15 cards: seven that <i>move</i> in the tank (worms, clam, feather star, '
            'shrimp, nudibranch, hermit crab), seven that <i>build</i> it (corals, sponge) and the coral guard crab that defends one. Each card: what it eats, '
            'how it defends itself, what it does in the tank.</div>'
            '<div class="note"><b>3 · The two fishes.</b> Why a pair of humbugs share one coral head, and how a boxfish swims with a rigid '
            'body (ostraciiform: fins row, the box does not bend). Includes the toxin note that matters to a real reef tank.</div>'
            '<div class="note"><b>Chips.</b> <span style="background:#c8f0d0;color:#222;border-radius:8px;padding:0 6px">verified</span> '
            'source read, says this about this species in the Gulf; '
            '<span style="background:#fde7b0;color:#222;border-radius:8px;padding:0 6px">other region</span> about this species elsewhere; '
            '<span style="background:#d9e4ff;color:#222;border-radius:8px;padding:0 6px">ours</span> a game choice. '
            'Nothing unverified prints (the 2026‑10‑06 poster audit rule).</div>'
            '<div class="note"><b>Output.</b> <code>docs/reference/gulf-of-thailand-reef-poster/</code>: <code>make_poster.py</code>, '
            '<code>export_poster.py</code>, <code>poster.html</code>, <code>gulf-of-thailand-reef-a3.pdf</code>, 300 DPI <code>poster.png</code>, '
            '<code>layout-review.json</code>; guarded by <code>tests/test_poster_gulf_of_thailand_reef.py</code>.</div>'
            '</div></div>')
    return page("A3 poster — Reef of the Gulf of Thailand", "habitat · invertebrates · the two fishes", body)


MOCKUPS = {"tank-wide": tank_wide, "tank-close": tank_close, "styles": styles, "selectors": selectors, "poster": poster}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true", help="also render each mockup to a 1440x900 PNG with google-chrome")
    args = ap.parse_args()
    for name, fn in MOCKUPS.items():
        _ids[0] = 0
        html = fn()
        out = HERE / f"{name}.html"
        out.write_text(html, encoding="utf-8")
        size = out.stat().st_size
        print(f"{out.name}: {size/1024:.0f} KB")
        if size > 512 * 1024:
            print(f"  ERROR: {out.name} is over the 512 KB mockup limit", file=sys.stderr)
            return 1
        if args.png:
            subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--window-size=1440,900", f"--screenshot={HERE / (name + '.png')}", out.as_uri()],
                           check=True, capture_output=True)
            png = HERE / (name + ".png")
            if png.stat().st_size > 512 * 1024:   # bundle rule: <= 512 KB per file
                from PIL import Image
                im = Image.open(png).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                                                             dither=Image.Dither.FLOYDSTEINBERG)
                im.save(png, optimize=True)
            print(f"  {png.name}: {png.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
