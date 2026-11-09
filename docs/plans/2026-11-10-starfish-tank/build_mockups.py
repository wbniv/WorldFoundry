#!/usr/bin/env python3
"""Mockups for docs/plans/2026-11-10-starfish-tank.md.

Writes six self-contained 1440x900 HTML mockups beside this script and, with
--png, a same-basename PNG for each (headless google-chrome):

  tank-wide.html   the tank from the default wide camera, every species numbered
  player.html      the player sea star: on the sand, on the front glass, at a corner
  residents.html   the residents' two states each (hidden / out, calm / fleeing)
  settings.html    the SeaStarsSettings phone form: defaults, maximum, only the player
  screensaver.html the Dream variant: autopilot frames and one autopilot cycle
  selectors.html   the TV tank menu at 11 / 11 and 1 / 11, and the phone's Dream list

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
SEED = 20261110


def f(v: float) -> str:
    return str(round(v)) if abs(v) >= 20 else f"{v:.1f}".rstrip("0").rstrip(".")


def smooth_closed(pts) -> str:
    """Closed Catmull-Rom spline through pts as an SVG path."""
    n = len(pts)
    d = [f"M{f(pts[0][0])},{f(pts[0][1])}"]
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}")
    return "".join(d) + "Z"


# ─────────────────────────────── species art ────────────────────────────────

SPECIES = {
    # key: (label, latin, colour, edge, arm length R, disc r, arm half-width at base, pattern)
    "linckia": ("Blue sea star (player)", "Linckia laevigata", "#2f6fd6", "#173f86", 60, 9, 7.5, "plain"),
    "protoreaster": ("Chocolate-chip star", "Protoreaster nodosus", "#dcbc8c", "#7a5630", 52, 16, 13, "knobs"),
    "fromia": ("Red Fromia", "Fromia milleporella", "#d4382a", "#7d1a12", 22, 5, 4.5, "dots"),
    "archaster": ("Sand-sifting star", "Archaster typicus", "#bfae92", "#6e6250", 38, 8, 8, "plates"),
    "ophiarachna": ("Green brittle star", "Ophiarachna incrassata", "#5f8f3a", "#2c4a18", 70, 10, 2.6, "bands"),
    "culcita": ("Cushion star", "Culcita novaeguineae", "#c8742e", "#6f3a12", 34, 30, 30, "cushion"),
}

_ids = [0]


def _id(prefix: str) -> str:
    _ids[0] += 1
    return f"{prefix}{_ids[0]}"


def arm_centre(cx, cy, ang, R, r, bend, lift=0.0, steps=7):
    """Points along one arm's centre line: start at the disc edge, curl by `bend` radians."""
    pts = []
    for k in range(steps + 1):
        t = k / steps
        a = ang + bend * t * t
        dist = r + (R - r) * t
        pts.append((cx + math.cos(a) * dist, cy + math.sin(a) * dist - lift * t * t, a))
    return pts


def star(cx, cy, key, rot=0.0, bends=None, lifts=None, scale=1.0, squash=1.0, opacity=1.0,
         underside=False, buried=0.0) -> str:
    """One sea star as an SVG group. squash < 1 foreshortens it onto the sand plane."""
    label, latin, col, edge, R, r, w, pat = SPECIES[key]
    R, r, w = R * scale, r * scale, w * scale
    n = 5
    bends = bends or [0.0] * n
    lifts = lifts or [0.0] * n
    g = []
    if pat == "cushion":
        pts = []
        for k in range(n * 2):
            a = rot + k * math.pi / n
            rad = R if k % 2 == 0 else R * 0.84
            pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad * squash))
        gid = _id("cu")
        g.append(f'<defs><radialGradient id="{gid}" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#e9a25a"/>'
                 f'<stop offset="1" stop-color="{col}"/></radialGradient></defs>')
        g.append(f'<path d="{smooth_closed(pts)}" fill="url(#{gid})" stroke="{edge}" stroke-width="1.5"/>')
        rng = random.Random(int(cx * 7 + cy))
        for _ in range(int(40 * scale)):
            a, d = rng.uniform(0, 2 * math.pi), R * 0.8 * math.sqrt(rng.random())
            g.append(f'<circle cx="{f(cx + math.cos(a) * d)}" cy="{f(cy + math.sin(a) * d * squash)}" r="{f(1.2 * scale)}" fill="{edge}" opacity=".55"/>')
        return f'<g opacity="{opacity}">' + "".join(g) + "</g>"
    outline = []
    centres = []
    for i in range(n):
        ang = rot + i * 2 * math.pi / n - math.pi / 2
        c = arm_centre(cx, cy, ang, R, r, bends[i], lifts[i])
        centres.append(c)
        left, right = [], []
        for k, (x, y, a) in enumerate(c):
            t = k / (len(c) - 1)
            hw = w * (1 - 0.82 * t) + 0.6 * scale
            nx, ny = -math.sin(a), math.cos(a)
            left.append((x + nx * hw, cy + (y - cy + ny * hw) * squash))
            right.append((x - nx * hw, cy + (y - cy - ny * hw) * squash))
        tip = c[-1]
        outline += right + [(tip[0] + math.cos(tip[2]) * w * 0.25, cy + (tip[1] - cy + math.sin(tip[2]) * w * 0.25) * squash)] + left[::-1]
    fill = col
    if underside:
        fill = "#9fb9e6"
    clip = ""
    if buried > 0:
        cid = _id("bur")
        g.append(f'<defs><clipPath id="{cid}"><rect x="{f(cx - R - 5)}" y="{f(cy - R - 5)}" width="{f(2 * R + 10)}" height="{f(2 * R + 10)}"/></clipPath></defs>')
        clip = f' clip-path="url(#{cid})"'
    g.append(f'<path d="{smooth_closed(outline)}" fill="{fill}" stroke="{edge}" stroke-width="{f(1.3 * max(scale, .6))}"{clip}/>')
    if underside:
        # ambulacral grooves with tube feet, mouth in the middle
        for c in centres:
            g.append('<polyline points="' + " ".join(f"{f(x)},{f(cy + (y - cy) * squash)}" for x, y, _ in c) +
                     f'" fill="none" stroke="#e9d39a" stroke-width="{f(3.2 * scale)}" stroke-dasharray="1.2 1.6" stroke-linecap="round"/>')
        g.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * .45)}" fill="#3b2a4a"/>')
    elif pat == "knobs":
        g.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * .5)}" fill="#3e2414"/>')
        for c in centres:
            for x, y, _ in c[1:-1:2]:
                g.append(f'<circle cx="{f(x)}" cy="{f(cy + (y - cy) * squash)}" r="{f(2.7 * scale)}" fill="#3e2414"/>')
    elif pat == "dots":
        for c in centres:
            for x, y, _ in c[1:-1]:
                g.append(f'<circle cx="{f(x)}" cy="{f(cy + (y - cy) * squash)}" r="{f(.9 * scale)}" fill="{edge}"/>')
    elif pat == "plates":
        g.append(f'<path d="{smooth_closed(outline)}" fill="none" stroke="#f1e7d2" stroke-width="{f(1.4 * scale)}" stroke-dasharray="2 2"/>')
    elif pat == "bands":
        g.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * 1.05)}" fill="#4c7a2a" stroke="{edge}" stroke-width="1"/>')
        for c in centres:
            for x, y, _ in c[1::1]:
                g.append(f'<circle cx="{f(x)}" cy="{f(cy + (y - cy) * squash)}" r="{f(2.4 * scale)}" fill="#c9d65a" opacity=".85"/>')
    else:
        g.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * .7)}" fill="#3f86ec" opacity=".6"/>')
        for c in centres:   # eyespot at each arm tip
            x, y, _ = c[-1]
            g.append(f'<circle cx="{f(x)}" cy="{f(cy + (y - cy) * squash)}" r="{f(1.6 * scale)}" fill="#e2483a"/>')
    if buried > 0:
        bid = _id("sb")
        g.append(f'<defs><radialGradient id="{bid}"><stop offset=".55" stop-color="#e6d3a8" stop-opacity="{f(buried)}"/>'
                 f'<stop offset="1" stop-color="#e6d3a8" stop-opacity="0"/></radialGradient></defs>'
                 f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(R * 1.25)}" ry="{f(R * 1.25 * squash)}" fill="url(#{bid})"/>')
    return f'<g opacity="{opacity}">' + "".join(g) + "</g>"


# ─────────────────────────────── scene pieces ───────────────────────────────

CSS = """
:root{--bg:#0f1720;--ink:#e8eef5;--mute:#93a4b8;--line:#2b3a4c;--accent:#7fc4ff}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#f4f6f9;--ink:#13202e;--mute:#566577;--line:#c9d3de;--accent:#1f6fd1}}
:root[data-theme="dark"]{--bg:#0f1720;--ink:#e8eef5;--mute:#93a4b8;--line:#2b3a4c;--accent:#7fc4ff}
*{box-sizing:border-box}html,body{margin:0}
body{width:1440px;height:900px;overflow:hidden;background:var(--bg);color:var(--ink);font:15px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:0 0 6px;color:var(--accent);font-weight:600}
.sub{color:var(--mute);margin:0 0 14px}
.tv{border:10px solid #050709;border-radius:6px;box-shadow:0 8px 30px #0008;background:#000;line-height:0}
.cap{color:var(--mute);font-size:13px;margin-top:6px}
.lab{font-size:14px;line-height:1.35}.lab b{display:inline-block;width:24px;height:24px;border-radius:50%;background:var(--accent);color:var(--bg);text-align:center;line-height:24px;margin-right:8px;font-size:13px}
.lab i{color:var(--mute)}
.legend{display:grid;grid-template-columns:repeat(3,1fr);gap:8px 24px;font-size:13px;color:var(--mute)}
.legend kbd{display:inline-block;min-width:22px;padding:1px 6px;border:1px solid var(--line);border-radius:4px;color:var(--ink);font:12px ui-monospace,monospace;text-align:center;margin-right:6px}
"""


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=1440">'
            f'<title>{title}</title><style>{CSS}</style></head><body style="padding:26px 32px">{body}</body></html>')


def water_and_sand(W, H, horizon, rng, caustics=True) -> str:
    gid, sid = _id("w"), _id("s")
    s = [f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3fa8c9"/>'
         f'<stop offset="1" stop-color="#1b6f93"/></linearGradient>'
         f'<linearGradient id="{sid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#cdb98f"/>'
         f'<stop offset="1" stop-color="#ead8ad"/></linearGradient></defs>',
         f'<rect width="{W}" height="{H}" fill="url(#{gid})"/>',
         f'<path d="M0,{horizon} Q{W * .3},{horizon - 8} {W * .55},{horizon + 4} T{W},{horizon - 2} V{H} H0Z" fill="url(#{sid})"/>']
    for _ in range(26):   # sand ripples
        y = rng.uniform(horizon + 12, H - 6)
        x = rng.uniform(-40, W)
        L = rng.uniform(80, 220) * (0.5 + (y - horizon) / (H - horizon))
        s.append(f'<path d="M{f(x)},{f(y)} q{f(L / 2)},-4 {f(L)},0" fill="none" stroke="#b9a274" stroke-width="1.4" opacity=".5"/>')
    if caustics:
        for _ in range(70):
            y = rng.uniform(horizon + 8, H)
            x = rng.uniform(0, W)
            k = 0.4 + (y - horizon) / (H - horizon)
            pts = [(x + math.cos(a) * rng.uniform(9, 17) * k, y + math.sin(a) * rng.uniform(3, 7) * k)
                   for a in [i * 2 * math.pi / 6 for i in range(6)]]
            s.append(f'<path d="{smooth_closed(pts)}" fill="none" stroke="#fff6d8" stroke-width="1.2" opacity=".45"/>')
        for i in range(7):   # light shafts
            x = W * (0.08 + i * 0.14) + rng.uniform(-20, 20)
            s.append(f'<path d="M{f(x)},0 l70,0 l{f(rng.uniform(-30, 60))},{horizon} l-110,0Z" fill="#ffffff" opacity=".05"/>')
    return "".join(s)


def rock(cx, cy, w, h, rng, shade="#7d7466") -> str:
    pts = []
    for k in range(10):
        a = math.pi + k * math.pi / 9
        rx = w / 2 * rng.uniform(.85, 1.05)
        ry = h * rng.uniform(.8, 1.05)
        pts.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry))
    pts += [(cx + w / 2, cy + 6), (cx - w / 2, cy + 6)]
    gid = _id("rk")
    out = [f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a69a86"/>'
           f'<stop offset="1" stop-color="{shade}"/></linearGradient></defs>',
           f'<path d="{smooth_closed(pts)}" fill="url(#{gid})" stroke="#4d463c" stroke-width="1.3"/>']
    for _ in range(int(w / 9)):   # pits and coralline crust
        x, y = cx + rng.uniform(-w / 2.6, w / 2.6), cy - rng.uniform(4, h * .85)
        col = rng.choice(["#5c554a", "#b66b8c", "#5c554a", "#8a9a5a"])
        out.append(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(rng.uniform(2, 5))}" ry="{f(rng.uniform(1.5, 3))}" fill="{col}" opacity=".6"/>')
    out.append(f'<ellipse cx="{f(cx)}" cy="{f(cy + 5)}" rx="{f(w * .55)}" ry="7" fill="#000" opacity=".18"/>')
    return "".join(out)


def seagrass(x, y, rng, n=6, hgt=70) -> str:
    out = []
    for _ in range(n):
        dx = rng.uniform(-10, 10)
        h = rng.uniform(.6, 1) * hgt
        b = rng.uniform(-22, 22)
        out.append(f'<path d="M{f(x + dx)},{f(y)} q{f(b / 2)},{f(-h / 2)} {f(b)},{f(-h)}" stroke="#4f8a3c" stroke-width="3.2" fill="none" stroke-linecap="round"/>')
    return "".join(out)


def rubble(W, horizon, H, rng, n=40) -> str:
    out = []
    for _ in range(n):
        x, y = rng.uniform(0, W), rng.uniform(horizon + 20, H - 4)
        k = .4 + (y - horizon) / (H - horizon)
        out.append(f'<ellipse cx="{f(x)}" cy="{f(y)}" rx="{f(rng.uniform(2, 6) * k)}" ry="{f(rng.uniform(1, 3) * k)}" '
                   f'fill="{rng.choice(["#f2ead6", "#a99c84", "#d9c9a6"])}"/>')
    return "".join(out)


def tag(x, y, n) -> str:
    return (f'<g><circle cx="{f(x)}" cy="{f(y)}" r="11" fill="#0d1622" stroke="#7fc4ff" stroke-width="1.5"/>'
            f'<text x="{f(x)}" y="{f(y + 4.5)}" font-size="12" font-weight="700" fill="#7fc4ff" text-anchor="middle" '
            f'font-family="system-ui">{n}</text></g>')


# ─────────────────────────────── mockups ────────────────────────────────────


def tank_wide() -> str:
    rng = random.Random(SEED)
    W, H, hz = 1040, 585, 250
    sv = [water_and_sand(W, H, hz, rng)]
    sv.append(rock(300, 330, 230, 120, rng))
    sv.append(rock(780, 300, 300, 150, rng))
    sv.append(rock(560, 268, 140, 60, rng, "#6e665a"))
    sv.append(seagrass(90, 300, rng, 9, 90) + seagrass(950, 290, rng, 7, 80) + seagrass(470, 280, rng, 5, 55))
    sv.append(rubble(W, hz, H, rng))
    tags = []
    # 1 player linckia, foreground centre, leading arm raised
    sv.append(star(520, 470, "linckia", rot=.15, bends=[.2, -.15, .1, .25, -.1], lifts=[14, 0, 0, 0, 0], squash=.55, scale=1.15))
    tags.append((520, 405, 1))
    # 2 protoreaster x2
    sv.append(star(200, 470, "protoreaster", rot=.5, squash=.5, scale=1.0))
    sv.append(star(860, 500, "protoreaster", rot=1.3, bends=[.1, 0, -.1, .1, 0], squash=.55, scale=1.1))
    tags += [(200, 425, 2), (860, 450, 2)]
    # 3 fromia x3 on rock faces
    sv.append(star(270, 285, "fromia", rot=.3, scale=1.0))
    sv.append(star(745, 245, "fromia", rot=1.1, scale=.9))
    sv.append(star(840, 270, "fromia", rot=.6, scale=.85))
    tags += [(270, 258, 3), (745, 222, 3), (840, 247, 3)]
    # 4 archaster x2: one out, one buried
    sv.append(star(660, 545, "archaster", rot=.9, squash=.5, scale=1.1))
    sv.append(star(380, 545, "archaster", rot=.2, squash=.45, scale=1.0, buried=.7))
    tags += [(660, 515, 4), (380, 520, 4)]
    # 5 brittle star: arms poking from under the big rock ledge
    sv.append(f'<g>{star(700, 376, "ophiarachna", rot=.4, bends=[.5, -.4, .3, -.5, .2], squash=.5, scale=.95)}</g>')
    sv.append(rock(700, 360, 120, 40, rng, "#6a6256"))
    tags.append((660, 395, 5))
    # 6 culcita
    sv.append(star(110, 545, "culcita", rot=.2, squash=.55, scale=1.0))
    tags.append((110, 510, 6))
    # glass edge highlight
    sv.append(f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" fill="none" stroke="#ffffff" stroke-opacity=".12" stroke-width="2"/>')
    sv += [tag(x, y, n) for x, y, n in tags]
    svg = f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">{"".join(sv)}</svg>'
    labels = "".join(
        f'<div class="lab" style="margin-bottom:14px"><b>{i}</b>{SPECIES[k][0]}{" ×" + str(c) if c > 1 else ""}<br>'
        f'<i style="margin-left:32px">{SPECIES[k][1]}</i><br><span style="margin-left:32px;color:var(--mute);font-size:12.5px">{note}</span></div>'
        for i, (k, c, note) in enumerate([
            ("linckia", 1, "you steer it; leading arm tip raised"),
            ("protoreaster", 2, "grazes the sand flat"),
            ("fromia", 3, "creeps on the rock faces"),
            ("archaster", 2, "buries itself, comes up, buries again"),
            ("ophiarachna", 1, "hides under the ledge; bolts when you come near"),
            ("culcita", 1, "barely moves; slow puff"),
        ], 1))
    body = (f'<h1>Sea Stars — wide camera</h1><p class="sub">Indo-Pacific sand flat with three rock outcrops. '
            f'Six species, 10 animals. Caustics (S2) on the sand. Labels sit outside the TV frame.</p>'
            f'<div style="display:flex;gap:34px;align-items:flex-start"><div><div class="tv">{svg}</div>'
            f'<div class="cap">Default wide camera, 16:9. Static: shell, sand, 3 rock outcrops, rubble, seagrass tufts.</div></div>'
            f'<div style="width:300px;padding-top:4px">{labels}</div></div>')
    return page("Sea Stars wide view", body)


def player() -> str:
    rng = random.Random(SEED + 1)
    W, H = 420, 420
    panels = []
    # (a) on the sand, top-ish view, leader arm raised, arrow shows travel; body does not turn
    s = [water_and_sand(W, H, 40, rng)]
    s.append(star(210, 240, "linckia", rot=0, bends=[.15, .2, -.1, .1, -.2], lifts=[18, 0, 0, 0, 0], squash=.75, scale=2.0))
    s.append('<path d="M210,120 L210,58" stroke="#fff" stroke-width="4" marker-end="url(#ah)"/>')
    s.append('<text x="222" y="92" fill="#fff" font-size="14" font-family="system-ui">stick ▲: this arm leads</text>')
    s.append('<path d="M330,250 L388,250" stroke="#fff" stroke-width="3" stroke-dasharray="6 5" marker-end="url(#ah)"/>')
    s.append('<text x="262" y="285" fill="#fff" font-size="13" font-family="system-ui">stick ▶: leader swaps;</text>'
             '<text x="262" y="301" fill="#fff" font-size="13" font-family="system-ui">body eases ≤ 36° to it</text>')
    panels.append(("On the sand", "Any arm can lead. The arm nearest the stick direction lifts its tip (eyespot) and the star glides that way; the body turns at most 36° to line it up.", s))
    # (b) on the front glass: the camera sees the underside
    s = [f'<rect width="{W}" height="{H}" fill="#2d8db1"/>']
    for i in range(6):
        s.append(f'<path d="M{40 + i * 70},0 l40,0 l-60,{H} l-40,0Z" fill="#fff" opacity=".05"/>')
    s.append(f'<rect x="0" y="330" width="{W}" height="90" fill="#d9c79c"/>')
    s.append(star(210, 190, "linckia", rot=.2, bends=[.05, -.05, .1, 0, -.1], scale=2.3, underside=True))
    s.append('<path d="M210,60 L210,24" stroke="#fff" stroke-width="4" marker-end="url(#ah)"/>')
    s.append('<text x="12" y="410" fill="#273" font-size="13" font-family="system-ui">sand line</text>')
    panels.append(("On the front glass", "Push into the front glass and the star climbs it: you see its underside, the five grooves of tube feet and the mouth. ▲▼ climb, ◀▶ traverse; ▼ at the sand steps down.", s))
    # (c) corner: arms drape over the edge between sand and back glass
    s = [f'<rect width="{W}" height="{H}" fill="#2a86aa"/>',
         f'<path d="M0,250 L{W},250 L{W},{H} L0,{H}Z" fill="#dcc89c"/>',
         f'<line x1="0" y1="250" x2="{W}" y2="250" stroke="#fff" stroke-opacity=".35" stroke-width="2"/>']
    s.append(star(210, 236, "linckia", rot=0, bends=[0, .25, -.2, .2, -.25], lifts=[0, 0, -10, -10, 0], scale=1.9, squash=.65))
    s.append('<text x="18" y="236" fill="#fff" font-size="13" font-family="system-ui">back glass</text>'
             '<text x="18" y="278" fill="#5b4b2a" font-size="13" font-family="system-ui">sand</text>')
    s.append('<path d="M330,180 a40,40 0 0 1 0,90" stroke="#fff" stroke-width="3" fill="none" marker-end="url(#ah)"/>'
             '<text x="290" y="150" fill="#fff" font-size="13" font-family="system-ui">1.2 s roll over</text>'
             '<text x="290" y="166" fill="#fff" font-size="13" font-family="system-ui">the edge</text>')
    panels.append(("Corner", "At a sand-to-glass edge the leading arms climb first (flex bias per arm) and the body pitches 90° over 1.2 s. No physics change: the position is held on a plane.", s))
    defs = ('<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M0,0 L10,5 L0,10z" fill="#fff"/></marker></defs>')
    cols = "".join(
        f'<div style="width:{W}px"><h2>{t}</h2><div class="tv"><svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'xmlns="http://www.w3.org/2000/svg">{defs}{"".join(sv)}</svg></div><div class="cap" style="height:58px">{c}</div></div>'
        for t, c, sv in panels)
    legend = ('<div class="legend" style="margin-top:14px">'
              '<div><kbd>◀▶▲▼</kbd>glide; the nearest arm leads</div>'
              '<div><kbd>into glass</kbd>climb onto it (front, back, sides)</div>'
              '<div><kbd>A</kbd>reach: rear up on two arms for 2 s</div>'
              '<div><kbd>touch</kbd>same mapping as the other tanks</div>'
              '<div><kbd>idle 30 s</kbd>autopilot takes over (as the Dream does)</div>'
              '<div><kbd>Back</kbd>to the tank menu</div></div>')
    body = (f'<h1>The player: a blue sea star, <i>Linckia laevigata</i></h1>'
            f'<p class="sub">Five arms are five DFRM v2 curves in one mesh. The star never swims: it holds to the sand or a glass plane.</p>'
            f'<div style="display:flex;gap:30px">{cols}</div>{legend}')
    return page("Sea Stars player", body)


def residents() -> str:
    rng = random.Random(SEED + 2)
    W, H = 300, 230
    rows = [
        ("Sand-sifting star", "archaster",
         ("Buried", lambda: star(150, 150, "archaster", rot=.4, squash=.55, scale=1.9, buried=.72), "Under the sand: only a faint five-point outline and a bump."),
         ("Out", lambda: star(150, 150, "archaster", rot=.4, bends=[.1, -.1, .1, 0, .1], squash=.55, scale=1.9), "Rises in 4 s, glides 20–40 cm, sinks again. Touching it makes it sink at once.")),
        ("Green brittle star", "ophiarachna",
         ("Hiding", lambda: star(150, 165, "ophiarachna", rot=.6, bends=[.6, -.5, .4, -.6, .3], squash=.5, scale=1.3) + rock(150, 150, 170, 55, rng, "#6a6256"),
          "Disc under the ledge; two or three arm tips out on the sand, waving."),
         ("Bolting", lambda: "".join(star(70 + i * 55, 160, "ophiarachna", rot=.2 + i * .25, bends=[.7, -.3, .6, -.7, .1], squash=.5, scale=1.1, opacity=.25 + .25 * i) for i in range(4)),
          "Player within 25 cm: it rows away on two arm pairs (fast, ×6 the stars) to another ledge.")),
        ("Cushion star", "culcita",
         ("Rest", lambda: star(150, 150, "culcita", squash=.6, scale=1.7), "A pentagonal cushion; no arms to bend."),
         ("Puff", lambda: star(150, 147, "culcita", squash=.66, scale=1.85), "Swells 8 % and settles over 10 s. Transforms only; no DFRM.")),
        ("Chocolate-chip / Fromia", "protoreaster",
         ("Graze", lambda: star(150, 150, "protoreaster", rot=.2, squash=.55, scale=1.6), "Chocolate-chip stars wander the sand between grazing spots."),
         ("Creep", lambda: rock(150, 205, 270, 170, rng) + star(110, 110, "fromia", rot=.6, scale=1.9) + star(205, 150, "fromia", rot=1.2, scale=1.6),
          "Fromia creep along authored routes on the rock faces.")),
    ]
    out = []
    for name, _k, *states in rows:
        cells = []
        for st, fn, cap in states:
            rng.seed(SEED + len(out) * 10 + len(cells))
            sv = water_and_sand(W, H, 70, rng, caustics=True) + fn()
            cells.append(f'<div style="width:{W}px"><div class="tv" style="border-width:6px"><svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
                         f'xmlns="http://www.w3.org/2000/svg">{sv}</svg></div><div class="cap"><b style="color:var(--ink)">{st}.</b> {cap}</div></div>')
        out.append(f'<div><h2>{name}</h2><div style="display:flex;gap:16px">{"".join(cells)}</div></div>')
    grid = f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px 40px">{"".join(out)}</div>'
    body = (f'<h1>Residents: the states each one shows</h1>'
            f'<p class="sub">One director (Forth) runs every resident on timers seeded per level load; two react to the player.</p>{grid}')
    return page("Sea Stars residents", body)


MENU = ["Clownfish & Sea Anemone", "Blue Shrimp", "Calm Betta", "Jellyfish", "Lionfish", "Planted Tank",
        "Asian Arowana", "Tiger Barbs", "Gulf of Thailand Reef", "Gulf of Thailand Reef - Anime", "Sea Stars"]
DREAM = ["Clownfish", "Blue Shrimp", "Betta", "Jellyfish", "Lionfish", "Planted Urchin", "Arowana", "Tiger Barbs",
         "Thai Reef", "Thai Reef Anime", "Sea Stars"]


def tv_menu(sel: int, top: int) -> str:
    W, H = 560, 315
    rows = []
    for i in range(top, min(top + 6, len(MENU))):
        y = 92 + (i - top) * 34
        on = i == sel
        new = i == len(MENU) - 1
        rows.append((f'<rect x="60" y="{y - 22}" width="440" height="30" rx="4" fill="#2f6fd6"/>' if on else "") +
                    f'<text x="76" y="{y}" fill="{"#fff" if on else "#c8d4e2"}" font-size="17" font-family="system-ui">{MENU[i]}</text>' +
                    (f'<text x="484" y="{y}" fill="#ffd36a" font-size="12" text-anchor="end" font-family="system-ui">NEW</text>' if new else ""))
    more_up = f'<text x="280" y="60" fill="#8aa" font-size="13" text-anchor="middle">▲ {top} more</text>' if top else ""
    rest = len(MENU) - top - 6
    more_dn = f'<text x="280" y="300" fill="#8aa" font-size="13" text-anchor="middle">▼ {rest} more</text>' if rest > 0 else ""
    svg = (f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
           f'<rect width="{W}" height="{H}" fill="#0a1220"/>'
           f'<text x="30" y="36" fill="#fff" font-size="20" font-weight="600" font-family="system-ui">WF Aquarium</text>'
           f'<text x="530" y="36" fill="#8aa" font-size="13" text-anchor="end" font-family="system-ui">{sel + 1} / {len(MENU)}</text>'
           f'{more_up}{"".join(rows)}{more_dn}</svg>')
    return f'<div class="tv">{svg}</div>'


def selectors() -> str:
    phone_rows = "".join(
        f'<div style="padding:11px 16px;border-bottom:1px solid #e3e7ec;display:flex;justify-content:space-between;'
        f'{"background:#e8f0fd;" if n == "Sea Stars" else ""}"><span>{n}</span>'
        f'<span style="color:#1f6fd1">{"●" if n == "Sea Stars" else "○"}</span></div>' for n in ["Random"] + DREAM)
    phone = (f'<div style="width:300px;height:640px;border:10px solid #111;border-radius:30px;background:#fff;color:#13202e;'
             f'overflow:hidden;font-size:14px"><div style="padding:16px;font-weight:600;font-size:16px;border-bottom:1px solid #ccd">'
             f'Dream tank</div>{phone_rows}</div>')
    body = (f'<h1>Selectors: the 11th tank</h1><p class="sub">One <code>level</code> line appended to '
            f'<code>aquarium-menu.manifest</code>; indices 0–9 do not move. The engine menu shows 6 rows and scrolls.</p>'
            f'<div style="display:flex;gap:40px;align-items:flex-start">'
            f'<div><h2>TV menu, Sea Stars selected (11 / 11)</h2>{tv_menu(10, 5)}'
            f'<h2 style="margin-top:22px">TV menu, at the top (1 / 11)</h2>{tv_menu(0, 0)}</div>'
            f'<div><h2>Phone: Dream tank list (narrow)</h2>{phone}'
            f'<div class="cap" style="width:300px">From <code>TankChoice.java</code> IDS / LABELS via '
            f'<code>TankSettingsProvider</code> (no change to the provider).</div></div></div>')
    return page("Sea Stars selectors", body)


SETTINGS = [  # (label, kind, lo, hi, default, choices)
    ("Chocolate-chip stars", "slider", 0, 4, 2, None),
    ("Red Fromia", "slider", 0, 5, 3, None),
    ("Sand-sifting stars", "slider", 0, 4, 2, None),
    ("Brittle stars", "slider", 0, 2, 1, None),
    ("Cushion stars", "slider", 0, 2, 1, None),
    ("Speed", "radio", 0, 2, 1, ["Slow", "Normal", "Fast"]),
    ("Glass climbing", "radio", 0, 1, 1, ["Off", "On"]),
    ("Caustics", "radio", 0, 1, 1, ["Off", "On"]),
    ("Seed", "number", 0, 16777215, 0, None),
]


def phone_form(values: dict, title: str) -> str:
    rows = ['<div style="padding:10px 16px;border-bottom:1px solid #e3e7ec;color:#9aa5b1;display:flex;justify-content:space-between">'
            '<span>Player</span><span>Blue sea star &#128274;</span></div>']
    for label, kind, lo, hi, d, ch in SETTINGS:
        v = values.get(label, d)
        if kind == "slider":
            pct = 100 * (v - lo) / (hi - lo)
            ctl = (f'<div style="display:flex;align-items:center;gap:10px;margin-top:6px"><div style="flex:1;height:4px;background:#d5dce4;border-radius:2px;position:relative">'
                   f'<div style="width:{pct:.0f}%;height:4px;background:#1f6fd1;border-radius:2px"></div>'
                   f'<div style="position:absolute;left:calc({pct:.0f}% - 8px);top:-6px;width:16px;height:16px;border-radius:50%;background:#1f6fd1"></div></div>'
                   f'<b style="width:18px;text-align:right">{v}</b></div>')
        elif kind == "radio":
            ctl = '<div style="display:flex;gap:14px;margin-top:6px">' + "".join(
                f'<span>{"&#9673;" if i == v else "&#9675;"} {c}</span>' for i, c in enumerate(ch)) + "</div>"
        else:
            ctl = (f'<div style="margin-top:6px;border:1px solid #c9d3de;border-radius:4px;padding:3px 8px;width:120px">{v}</div>')
        rows.append(f'<div style="padding:8px 16px;border-bottom:1px solid #e3e7ec"><div>{label}</div>{ctl}</div>')
    return (f'<div style="width:300px;height:690px;border:10px solid #111;border-radius:30px;background:#fff;color:#13202e;overflow:hidden;font-size:13.5px">'
            f'<div style="padding:14px 16px;font-weight:600;font-size:15.5px;border-bottom:1px solid #ccd">&#8249; {title}</div>{"".join(rows)}</div>')


def settings() -> str:
    states = [
        ("Defaults", {}, "Ships like this: 9 residents, the D7 gate is measured here."),
        ("Maximum population", {"Chocolate-chip stars": 4, "Red Fromia": 5, "Sand-sifting stars": 4, "Brittle stars": 2, "Cushion stars": 2},
         "17 residents + the player. Phase 4 measures this too; a maximum that misses the gate is lowered (D10)."),
        ("Only the player", {"Chocolate-chip stars": 0, "Red Fromia": 0, "Sand-sifting stars": 0, "Brittle stars": 0, "Cushion stars": 0, "Seed": 4242},
         "All counts 0: the empty tank. The Director parks every resident; the player and the Dream autopilot still run."),
    ]
    cols = "".join(f'<div style="width:330px"><h2>{t}</h2>{phone_form(v, "Sea Stars settings")}<div class="cap" style="width:300px">{c}</div></div>'
                   for t, v, c in states)
    notes = ('<div style="width:300px;font-size:13.5px;color:var(--mute);padding-top:30px">'
             '<h2>Notes</h2><p>Editable rows carry no marker. The read-only row is dimmed with a padlock.</p>'
             '<p>Every field takes effect within a second: the Director reads the object with <code>property@</code> once a second.</p>'
             '<p>Seed is live too: the residents glide to the spots of the new seed. 0 draws new spots on every entry.</p>'
             '<p>One <code>SeaStarsSettings</code> object sits in the level (a standard OAS type that inherits <code>Settings</code>). The TV and phone forms come from its <code>.oad</code>; no RPRP catalog.</p></div>')
    body = (f'<h1>Level settings: SeaStarsSettings</h1><p class="sub">A <code>SeaStarsSettings</code> object in the level, a standard OAS type. '
            f'The forms are generated from its <code>.oad</code>.</p><div style="display:flex;gap:26px">{cols}{notes}</div>')
    return page("Sea Stars settings", body)


def screensaver() -> str:
    rng = random.Random(SEED + 3)
    W, H, hz = 760, 428, 175
    def frame(extra, many=False):
        sv = [water_and_sand(W, H, hz, rng), rock(220, 240, 170, 90, rng), rock(570, 220, 220, 110, rng),
              seagrass(60, 220, rng, 7, 70), seagrass(700, 212, rng, 6, 60), rubble(W, hz, H, rng, 30)]
        n_cc, n_fr, n_ar = (4, 5, 4) if many else (2, 3, 2)
        for i in range(n_cc):
            sv.append(star(120 + i * 160, 360 + (i % 2) * 30, "protoreaster", rot=i * .7, squash=.5, scale=.8))
        for i in range(n_fr):
            sv.append(star(180 + i * 95 + (i > 1) * 200, 205 + (i % 2) * 22 - (i > 1) * 10, "fromia", rot=i, scale=.7))
        for i in range(n_ar):
            sv.append(star(90 + i * 190, 405, "archaster", rot=i * .4, squash=.45, scale=.75, buried=.7 if i % 2 else 0))
        sv.append(star(520, 285, "ophiarachna", rot=.4, bends=[.5, -.4, .3, -.5, .2], squash=.5, scale=.7))
        if many:
            sv.append(star(300, 300, "ophiarachna", rot=1.4, bends=[.6, -.3, .4, -.5, .2], squash=.5, scale=.7))
            sv.append(star(680, 395, "culcita", squash=.55, scale=.75))
        sv.append(star(45, 400, "culcita", squash=.55, scale=.75))
        sv.append(extra)
        return f'<div class="tv"><svg width="660" height="372" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">{"".join(sv)}</svg></div>'
    glass = star(380, 120, "linckia", rot=.25, scale=1.25, underside=True)   # autopilot up the front glass
    sand = star(400, 330, "linckia", rot=.1, lifts=[10, 0, 0, 0, 0], squash=.55, scale=1.0)
    steps = [("0:00", "enter: seeded spots"), ("0:20", "glide to sand spot"), ("1:10", "pause 10–40 s"),
             ("2:30", "up the front glass"), ("4:00", "along the back glass"), ("5:30", "rear up (reach)"),
             ("…", "repeat; no HUD, no input")]
    tl = "".join(f'<div style="flex:1;border-top:3px solid var(--accent);padding-top:6px;font-size:12.5px"><b>{t}</b><br>'
                 f'<span style="color:var(--mute)">{d}</span></div>' for t, d in steps)
    body = (f'<h1>Screensaver: <code>aquarium_sea_stars_screensaver</code></h1>'
            f'<p class="sub">The Dream variant swaps the player script for the autopilot (<code>sea_stars_screensaver.fth</code>) and carries the '
            f'<code>SeaStarsSettings</code> object. Full screen, no HUD, no input.</p>'
            f'<div style="display:flex;gap:30px"><div><h2>Defaults: autopilot climbing the front glass</h2>{frame(glass)}</div>'
            f'<div><h2>Maximum population: autopilot on the sand</h2>{frame(sand, True)}</div></div>'
            f'<h2 style="margin-top:18px">One autopilot cycle (seeded waypoints)</h2><div style="display:flex;gap:10px;width:1376px">{tl}</div>'
            f'<div class="cap" style="margin-top:12px">The Dream picks Sea Stars from the phone list; the settings form opens from that list. '
            f'Leaving the Dream restores the TV; the settings stay as set.</div>')
    return page("Sea Stars screensaver", body)


MOCKUPS = {"tank-wide": tank_wide, "player": player, "residents": residents, "settings": settings,
           "screensaver": screensaver, "selectors": selectors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--png", action="store_true", help="also render each mockup to a 1440x900 PNG with google-chrome")
    args = ap.parse_args()
    for name, fn in MOCKUPS.items():
        _ids[0] = 0
        out = HERE / f"{name}.html"
        out.write_text(fn(), encoding="utf-8")
        size = out.stat().st_size
        print(f"{out.name}: {size / 1024:.0f} KB")
        if size > 512 * 1024:
            print(f"  ERROR: {out.name} is over the 512 KB mockup limit", file=sys.stderr)
            return 1
        if args.png:
            png = HERE / (name + ".png")
            subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--window-size=1440,900", f"--screenshot={png}", out.as_uri()],
                           check=True, capture_output=True)
            if png.stat().st_size > 512 * 1024:
                from PIL import Image
                im = Image.open(png).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                                                             dither=Image.Dither.FLOYDSTEINBERG)
                im.save(png, optimize=True)
            print(f"  {png.name}: {png.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
