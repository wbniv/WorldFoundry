#!/usr/bin/env python3
"""Generate the aquarium plan mockups (self-contained 1440x900 HTML, inline SVG).

Usage: 2026-09-30-aquarium-level-mockups.py [OUT_DIR]
       (default OUT_DIR: 2026-09-30-aquarium-level/ next to this script)

Writes tank-dimensions.html, gameplay-states.html and pane-fallbacks.html. Render the
same-name PNGs with:
  google-chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1440,900 \\
      --screenshot=<name>.png file://<abs path>/<name>.html
Plan: docs/plans/2026-09-30-aquarium-level.md (Plan B: no front pane; Plan A deferred).
"""
import math, sys, pathlib

if any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__)
    sys.exit(0)
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent / "2026-09-30-aquarium-level"
OUT.mkdir(parents=True, exist_ok=True)

IN = 0.254          # metres per inch at the plan's x10 level scale
TANK_W, TANK_D, TANK_H = 48 * IN, 13 * IN, 21 * IN     # exterior 12.192 x 3.302 x 5.334 m
WALL = 0.5 * IN
WATER_Z = 19 * IN
SAND_Z = 2.5 * IN

CSS = """
*{box-sizing:border-box}
body{margin:0;width:1440px;height:900px;overflow:hidden;background:#0e141b;color:#dce6ee;
 font:15px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;align-items:center;gap:12px;padding:14px 24px;border-bottom:1px solid #26323e;background:#141c25}
header h1{margin:0;font-size:16px;font-weight:600}
header .tag{margin-left:auto;font:600 11px ui-monospace,Menlo,monospace;letter-spacing:.04em;color:#8fa1b2;
 border:1px solid #2c3a48;border-radius:10px;padding:2px 8px}
.cap{font-size:13px;color:#9db0c0}
.cap b{color:#e8f1f8}
table{border-collapse:collapse;font-size:13px}
td,th{padding:5px 10px;border-bottom:1px solid #26323e;text-align:left;vertical-align:top}
th{color:#8fa1b2;font-weight:600}
code{font:12px ui-monospace,Menlo,monospace;color:#9fd8e8}
.k{display:inline-block;min-width:26px;text-align:center;border:1px solid #4a5b6b;border-bottom-width:3px;
 border-radius:5px;padding:1px 6px;font:600 12px ui-monospace,Menlo,monospace;background:#1a2530;color:#e8f1f8}
"""

def page(title, tag, body):
    return f"""<!DOCTYPE html>
<!-- Plan mockup: self-contained, 1440x900. Generated; edit the SVG here or regenerate. -->
<html lang="en"><head><meta charset="utf-8"><title>Mockup — {title}</title>
<style>{CSS}</style></head><body>
<header><h1>{title}</h1><span class="tag">{tag}</span></header>
{body}
</body></html>
"""

# ───────────────────────── art ─────────────────────────
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

def anemone(cx, cy, s, sway=0.0, layer="all", uid="a"):
    """Bubble-tip anemone: base disc, column, tentacles. sway in radians phase offset."""
    out = [f'<g transform="translate({cx:.3f},{cy:.3f}) scale({s:.5f})">']
    n = 17
    tents = []
    for i in range(n):
        t = i / (n - 1)
        ang = math.radians(-78 + 156 * t) + 0.10 * math.sin(sway + i * 1.3)
        ln = 78 + 26 * math.sin(i * 2.1 + 0.7) + (14 if 4 < i < 12 else 0)
        tents.append((i, ang, ln))
    def tentacle(i, ang, ln):
        bx = (i - (n - 1) / 2) * 5.0
        by = -46
        w0, w1 = 8.5, 4.2
        dx, dy = math.sin(ang), -math.cos(ang)
        px, py = -dy, dx
        tx, ty = bx + dx * ln, by + dy * ln
        mx, my = bx + dx * ln * .55 + 5 * math.sin(sway + i), by + dy * ln * .55
        left = f"{bx - px*w0:.1f},{by - py*w0:.1f} {mx - px*w1:.1f},{my - py*w1:.1f} {tx - px*w1:.1f},{ty - py*w1:.1f}"
        right = f"{tx + px*w1:.1f},{ty + py*w1:.1f} {mx + px*w1:.1f},{my + py*w1:.1f} {bx + px*w0:.1f},{by + py*w0:.1f}"
        shade = ("#b5558a", "#9a4573") if i % 2 == 0 else ("#c2699b", "#a95582")
        s_ = (f'<polygon points="{left} {tx:.1f},{ty:.1f}" fill="{shade[0]}"/>'
              f'<polygon points="{tx:.1f},{ty:.1f} {right}" fill="{shade[1]}"/>'
              f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="7.4" fill="#f3b2d2" stroke="#8b3a68" stroke-width="1.4"/>'
              f'<circle cx="{tx-2:.1f}" cy="{ty-2.2:.1f}" r="2.4" fill="#fde0ee"/>')
        return s_
    if layer in ("all", "back"):
        out.append('<polygon points="-46,0 -38,-24 -22,-46 22,-46 38,-24 46,0" fill="#8d6a48" stroke="#4d3822" stroke-width="2"/>')
        out.append('<polygon points="-38,-24 -22,-46 0,-46 0,0 -46,0" fill="#a17a54"/>')
        out.append('<polygon points="-30,-6 -20,-30 20,-30 30,-6" fill="#c29a6c" opacity=".55"/>')
        for i, a, l in tents:
            if i % 2 == 0:
                out.append(tentacle(i, a, l))
    if layer in ("all", "front"):
        for i, a, l in tents:
            if i % 2 == 1:
                out.append(tentacle(i, a, l))
        out.append('<ellipse cx="0" cy="-46" rx="26" ry="8" fill="#7c3a5f" opacity=".85"/>')
    out.append('</g>')
    return "".join(out)

def rock(cx, cy, s):
    p = [(-70,0),(-62,-26),(-38,-44),(-6,-52),(28,-46),(58,-28),(72,0)]
    fac = [([(-70,0),(-62,-26),(-30,-14),(-24,0)],"#6f6a63"),([(-62,-26),(-38,-44),(-6,-52),(-30,-14)],"#8a847b"),
           ([(-6,-52),(28,-46),(20,-14),(-30,-14)],"#7a746b"),([(28,-46),(58,-28),(72,0),(20,-14)],"#5f5a54"),
           ([(-30,-14),(20,-14),(72,0),(-24,0)],"#67625b")]
    o = [f'<g transform="translate({cx:.3f},{cy:.3f}) scale({s:.5f})"><polygon points="{pts(p)}" fill="#7a746b"/>']
    for poly, col in fac:
        o.append(f'<polygon points="{pts(poly)}" fill="{col}"/>')
    o.append(f'<polygon points="{pts(p)}" fill="none" stroke="#2c2a27" stroke-width="2"/></g>')
    return "".join(o)

# ─────────────────── scene in metres (y down = -z), camera as transform ───────────────────
def scene(uid, pane="haze", anemone_x=2.5, fish_pos=(-1.6, -2.4), fish_flip=False, fish_tilt=0,
          host=False, sway=0.0):
    """Tank in metres, origin = centre of tank floor footprint, y = -z."""
    hw = TANK_W / 2
    g = []
    # room + stand
    g.append(f'<rect x="{-hw-6}" y="{-TANK_H-4}" width="{TANK_W+12}" height="{TANK_H+4}" fill="url(#{uid}wall)"/>')
    g.append(f'<rect x="{-hw-6}" y="0.0" width="{TANK_W+12}" height="4" fill="#120d09"/>')
    g.append(f'<rect x="{-hw-0.25}" y="0.0" width="{TANK_W+0.5}" height="4" fill="#20160f"/>')
    g.append(f'<rect x="{-hw-0.25}" y="0.0" width="{TANK_W+0.5}" height="0.16" fill="#3a2a1c"/>')
    # back film + water
    g.append(f'<rect x="{-hw}" y="{-TANK_H}" width="{TANK_W}" height="{TANK_H}" fill="#08283d"/>')
    g.append(f'<rect x="{-hw+WALL}" y="{-WATER_Z}" width="{TANK_W-2*WALL}" height="{WATER_Z-WALL}" fill="url(#{uid}water)"/>')
    # light shafts (flat facets, cheap)
    for k, x in enumerate((-4.2, -0.4, 3.6)):
        g.append(f'<polygon points="{x},{-WATER_Z} {x+0.9},{-WATER_Z} {x+2.2},{-SAND_Z} {x+0.6},{-SAND_Z}" fill="#bff3ff" opacity=".07"/>')
    # sand
    g.append(f'<polygon points="{-hw+WALL},{-SAND_Z} {-3},{-SAND_Z-0.06} {0.5},{-SAND_Z+0.02} {4},{-SAND_Z-0.08} {hw-WALL},{-SAND_Z} '
             f'{hw-WALL},{-WALL} {-hw+WALL},{-WALL}" fill="#cdbb8b"/>')
    g.append(f'<polygon points="{-hw+WALL},{-SAND_Z} {-3},{-SAND_Z-0.06} {-2},{-WALL} {-hw+WALL},{-WALL}" fill="#c0ae7e"/>')
    g.append(f'<polygon points="{0.5},{-SAND_Z+0.02} {4},{-SAND_Z-0.08} {5},{-WALL} {1.2},{-WALL}" fill="#d8c79a"/>')
    # rock + anemone (+ fish)
    rk_s = 0.0175
    g.append(rock(anemone_x, -SAND_Z + 0.05, rk_s))
    ax, ay = anemone_x, -SAND_Z - 0.85
    if host:
        g.append(anemone(ax, ay, 0.0165, sway, "back", uid + "a"))
        g.append(fish(fish_pos[0], fish_pos[1], 0.0078, fish_flip, uid + "f", fish_tilt))
        g.append(anemone(ax, ay, 0.0165, sway, "front", uid + "b"))
    else:
        g.append(anemone(ax, ay, 0.0165, sway, "all", uid + "a"))
        g.append(fish(fish_pos[0], fish_pos[1], 0.0078, fish_flip, uid + "f", fish_tilt))
    # surface
    g.append(f'<polygon points="{-hw+WALL},{-WATER_Z} {-3.4},{-WATER_Z-0.04} {-1},{-WATER_Z} {1.6},{-WATER_Z-0.05} {4},{-WATER_Z} {hw-WALL},{-WATER_Z-0.03} '
             f'{hw-WALL},{-WATER_Z+0.12} {-hw+WALL},{-WATER_Z+0.12}" fill="#9fe6f2" opacity=".55"/>')
    # acrylic: walls seen through the front pane -> bands of thickness WALL
    ac = "#cfeff6"
    g.append(f'<rect x="{-hw}" y="{-TANK_H}" width="{WALL}" height="{TANK_H}" fill="{ac}" opacity=".75"/>')
    g.append(f'<rect x="{hw-WALL}" y="{-TANK_H}" width="{WALL}" height="{TANK_H}" fill="{ac}" opacity=".75"/>')
    g.append(f'<rect x="{-hw}" y="{-WALL}" width="{TANK_W}" height="{WALL}" fill="{ac}" opacity=".8"/>')
    g.append(f'<rect x="{-hw}" y="{-TANK_H}" width="{TANK_W}" height="{WALL*0.8}" fill="{ac}" opacity=".55"/>')
    # front pane
    if pane == "haze":
        g.append(f'<rect x="{-hw}" y="{-TANK_H}" width="{TANK_W}" height="{TANK_H}" fill="#bfeaf3" opacity=".10"/>')
        g.append(f'<polygon points="{-hw+1.2},{-TANK_H} {-hw+2.6},{-TANK_H} {-hw+0.9},{0} {-hw-0.5},{0}" fill="#fff" opacity=".10"/>')
        g.append(f'<polygon points="{-hw+3.0},{-TANK_H} {-hw+3.4},{-TANK_H} {-hw+1.7},{0} {-hw+1.3},{0}" fill="#fff" opacity=".08"/>')
    elif pane == "opaque":
        g.append(f'<rect x="{-hw}" y="{-TANK_H}" width="{TANK_W}" height="{TANK_H}" fill="#3aa6c0" opacity=".88"/>')
    return "".join(g)

def defs(uid):
    return (f'<defs><linearGradient id="{uid}wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c2c3c"/><stop offset="1" stop-color="#101a25"/></linearGradient>'
            f'<linearGradient id="{uid}water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2fb0c4"/><stop offset=".55" stop-color="#136a88"/><stop offset="1" stop-color="#0a405c"/></linearGradient></defs>')

def screen(x, y, w, h, uid, cam, label=None, **kw):
    """4:3 game screen. cam=(cx, cz, ppm): scene point (metres, z up) at screen centre and px per metre."""
    cx, cz, ppm = cam
    sc = scene(uid, **kw)
    o = [f'<g transform="translate({x},{y})">', defs(uid), f'<clipPath id="{uid}clip"><rect width="{w}" height="{h}" rx="6"/></clipPath>',
         f'<rect width="{w}" height="{h}" rx="6" fill="#000"/>',
         f'<g clip-path="url(#{uid}clip)"><g transform="translate({w/2 - cx*ppm:.2f},{h/2 + cz*ppm:.2f}) scale({ppm})">{sc}</g></g>',
         f'<rect width="{w}" height="{h}" rx="6" fill="none" stroke="#3a4a5a" stroke-width="2"/>']
    if label:
        o.append(f'<rect x="{w-8-len(label)*6.6-8:.0f}" y="{h-26}" width="{len(label)*6.6+16:.0f}" height="20" rx="4" fill="#0a1016" fill-opacity=".85"/>'
                 f'<text x="{w-8}" y="{h-12}" text-anchor="end" font-size="11" fill="#b7c7d4" font-family="ui-monospace,monospace">{label}</text>')
    o.append('</g>')
    return "".join(o)

def dimline_h(x1, x2, y, text, col="#7fd3e6"):
    return (f'<g stroke="{col}" stroke-width="1.2" fill="{col}"><line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}"/>'
            f'<line x1="{x1}" y1="{y-6}" x2="{x1}" y2="{y+6}"/><line x1="{x2}" y1="{y-6}" x2="{x2}" y2="{y+6}"/>'
            f'<text x="{(x1+x2)/2}" y="{y-8}" text-anchor="middle" stroke="none" font-size="13">{text}</text></g>')

def dimline_v(x, y1, y2, text, col="#7fd3e6", side="left"):
    tx = x - 8 if side == "left" else x + 8
    anchor = "end" if side == "left" else "start"
    return (f'<g stroke="{col}" stroke-width="1.2" fill="{col}"><line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}"/>'
            f'<line x1="{x-6}" y1="{y1}" x2="{x+6}" y2="{y1}"/><line x1="{x-6}" y1="{y2}" x2="{x+6}" y2="{y2}"/>'
            f'<text x="{tx}" y="{(y1+y2)/2}" text-anchor="{anchor}" stroke="none" font-size="13" dominant-baseline="middle">{text}</text></g>')

# ───────────────────────── 1. tank dimensions ─────────────────────────
def mock_dims():
    PX = 15.0                            # px per inch
    fx, fy = 110, 150                    # front view origin (top-left of exterior)
    W, H = 48 * PX, 21 * PX
    t = 0.5 * PX
    water_y = fy + H - 19 * PX
    sand_y = fy + H - 2.5 * PX
    s = []
    def acrylic_rect(x, y, w, h):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#bfe9f2" fill-opacity=".18" stroke="#cfeff6" stroke-width="2"/>')
    # FRONT
    s.append(f'<text x="{fx}" y="{fy-38}" font-size="14" fill="#e8f1f8" font-weight="600">FRONT (looking +Y)</text>')
    s.append(acrylic_rect(fx, fy, W, H))
    s.append(f'<rect x="{fx+t}" y="{water_y}" width="{W-2*t}" height="{fy+H-t-water_y}" fill="#1a7f9a" fill-opacity=".55"/>')
    s.append(f'<rect x="{fx+t}" y="{sand_y}" width="{W-2*t}" height="{fy+H-t-sand_y}" fill="#cdbb8b"/>')
    s.append(f'<rect x="{fx+t}" y="{fy+t}" width="{W-2*t}" height="{H-2*t}" fill="none" stroke="#5fb4c8" stroke-dasharray="4 4"/>')
    s.append(f'<line x1="{fx-20}" y1="{water_y}" x2="{fx+W+20}" y2="{water_y}" stroke="#7fe0f2" stroke-dasharray="7 4"/>')
    s.append(f'<text x="{fx+W+26}" y="{water_y+4}" font-size="12" fill="#7fe0f2">water line</text>')
    s.append(rock(fx + 0.71 * W, sand_y + 4, 0.75) if False else "")
    # anemone + fish scaled from the 10x level to px: 1 m = PX/0.254 px
    ppm = PX / IN
    ax = fx + W / 2 + 2.5 * ppm
    s.append(rock(ax, sand_y + 3, 0.0175 * ppm))
    s.append(anemone(ax, sand_y - 0.8 * ppm, 0.0165 * ppm, 0.5))
    s.append(fish(fx + W / 2 - 1.6 * ppm, sand_y - 1.9 * ppm, 0.0078 * ppm))
    s.append(dimline_h(fx, fx + W, fy - 14, "48 in · 121.9 cm"))
    s.append(dimline_v(fx - 26, fy, fy + H, "21 in<tspan x=\"%d\" dy=\"16\">53.3 cm</tspan>" % (fx - 34)))
    s.append(dimline_v(fx + W + 16, water_y, fy + H, "", side="right"))
    s.append(f'<text x="{fx+W+26}" y="{(water_y+fy+H)/2}" font-size="12" fill="#7fd3e6">19 in (48.3 cm)</text>')
    s.append(f'<text x="{fx+W+26}" y="{(water_y+fy+H)/2+15}" font-size="12" fill="#7fd3e6">to water line</text>')
    s.append(f'<text x="{fx+W+26}" y="{water_y-20}" font-size="12" fill="#9db0c0">2 in freeboard</text>')
    # wall callout
    s.append(f'<line x1="{fx+t/2}" y1="{fy+H*0.3}" x2="{fx+60}" y2="{fy+H*0.3}" stroke="#f0b35c"/>')
    s.append(f'<text x="{fx+64}" y="{fy+H*0.3+4}" font-size="12" fill="#f0b35c">½ in (12.7 mm) acrylic, every face</text>')
    s.append(f'<line x1="{fx+t}" y1="{sand_y+5}" x2="{fx+40}" y2="{sand_y+5}" stroke="#5a4a20"/>')
    s.append(f'<text x="{fx+44}" y="{sand_y+9}" font-size="12" fill="#5a4a20">sand, 2 in deep</text>')
    # SIDE
    sx, sy = 960, 150
    SW = 13 * PX
    s.append(f'<text x="{sx}" y="{sy-38}" font-size="14" fill="#e8f1f8" font-weight="600">SIDE (looking +X)</text>')
    s.append(acrylic_rect(sx, sy, SW, H))
    s.append(f'<rect x="{sx+t}" y="{water_y}" width="{SW-2*t}" height="{fy+H-t-water_y}" fill="#1a7f9a" fill-opacity=".55"/>')
    s.append(f'<rect x="{sx+t}" y="{sand_y}" width="{SW-2*t}" height="{fy+H-t-sand_y}" fill="#cdbb8b"/>')
    s.append(dimline_h(sx, sx + SW, sy - 14, "13 in · 33.0 cm"))
    s.append(f'<text x="{sx+SW/2}" y="{sy+H+22}" text-anchor="middle" font-size="12" fill="#9db0c0">interior 12 in (30.5 cm)</text>')
    # swim corridor
    s.append(f'<rect x="{sx+t+8}" y="{water_y+10}" width="{SW-2*t-16}" height="{sand_y-water_y-30}" fill="none" stroke="#f0b35c" stroke-dasharray="3 3"/>')
    s.append(f'<text x="{sx+SW/2}" y="{water_y+52}" text-anchor="middle" font-size="12" fill="#f0b35c">fish swim</text><text x="{sx+SW/2}" y="{water_y+67}" text-anchor="middle" font-size="12" fill="#f0b35c">volume</text>')
    # TOP
    tx, ty = 110, 560
    s.append(f'<text x="{tx}" y="{ty-38}" font-size="14" fill="#e8f1f8" font-weight="600">TOP (looking −Z) — camera side is the bottom edge</text>')
    s.append(acrylic_rect(tx, ty, W, 13 * PX))
    s.append(f'<rect x="{tx+t}" y="{ty+t}" width="{W-2*t}" height="{13*PX-2*t}" fill="#1a7f9a" fill-opacity=".35"/>')
    s.append(f'<ellipse cx="{ax}" cy="{ty+6.5*PX}" rx="{0.9*ppm}" ry="{0.9*ppm}" fill="#b5558a" fill-opacity=".8" stroke="#f3b2d2"/>')
    s.append(f'<text x="{ax}" y="{ty+6.5*PX+4}" text-anchor="middle" font-size="11" fill="#fff">anemone</text>')
    s.append(dimline_h(tx, tx + W, ty + 13 * PX + 62, "48 in · 121.9 cm"))
    s.append(dimline_v(tx - 22, ty, ty + 13 * PX, "13 in"))
    s.append(f'<g fill="#f0b35c"><polygon points="{tx+W/2-10},{ty+13*PX+8} {tx+W/2+10},{ty+13*PX+8} {tx+W/2},{ty+13*PX-4}"/></g>')
    s.append(f'<text x="{tx+W/2+16}" y="{ty+13*PX+18}" font-size="12" fill="#f0b35c">front-glass camera (y = −11 m at ×10)</text>')
    svg = f'<svg width="1440" height="843" viewBox="0 0 1440 843" style="position:absolute;top:57px;left:0" font-family="ui-sans-serif,system-ui,sans-serif">{"".join(s)}</svg>'
    table = """
<div style="position:absolute;left:900px;top:562px;width:500px">
<table><tr><th colspan="2">55 US gal acrylic — real vs level (×10)</th></tr>
<tr><td>Exterior</td><td>48 × 13 × 21 in<br><code>121.9 × 33.0 × 53.3 cm</code></td></tr>
<tr><td>Wall / base</td><td>½ in = 12.7 mm</td></tr>
<tr><td>Interior</td><td>47 × 12 × 20.5 in</td></tr>
<tr><td>Nominal</td><td>55 gal (exterior 56.7 gal)</td></tr>
<tr><td>Interior, to brim</td><td>50.1 gal</td></tr>
<tr><td>Operating fill</td><td>19 in → <b>45.2 gal · 171 L</b></td></tr>
<tr><td>Level scale</td><td>1 in = 0.254 m<br><code>12.19 × 3.30 × 5.33 m</code></td></tr>
<tr><td>Clownfish</td><td>3.5 in → 0.89 m</td></tr>
<tr><td>Anemone</td><td>7 in wide → 1.8 m</td></tr>
</table></div>
<div class="cap" style="position:absolute;left:1200px;top:150px;width:210px">
<b>Why ×10.</b> The engine's camera, capsule, fog and speeds are tuned for a 1.7 m walker. A 9 cm fish at 1:1 would sit under
the physics and camera minimums. ×10 keeps every number in the range the condo already proves; Phase 1 tests ×1 against ×10 before we commit.
</div>"""
    return page("Aquarium — 55 gal acrylic tank, dimensions", "MOCKUP — NOT SHIPPED", svg + table)

# ───────────────────────── 2. gameplay states ─────────────────────────
def keycap(x, y, t, w=34):
    return (f'<g><rect x="{x}" y="{y}" width="{w}" height="30" rx="5" fill="#1a2530" stroke="#4a5b6b" stroke-width="1.5"/>'
            f'<rect x="{x}" y="{y+24}" width="{w}" height="6" rx="3" fill="#2c3a48"/>'
            f'<text x="{x+w/2}" y="{y+18}" text-anchor="middle" font-size="12" font-weight="700" fill="#e8f1f8" font-family="ui-monospace,monospace">{t}</text></g>')

def mock_states():
    s = []
    # A default
    s.append(screen(60, 100, 640, 480, "A", (0, 2.7, 46), label="640×480 · fixed front camshot", pane="none",
                    fish_pos=(-1.6, -2.4)))
    s.append('<text x="303" y="395" text-anchor="middle" font-size="12" fill="#f0b35c">◀ ▶ ▲ ▼  swim</text>')
    # B host
    s.append(screen(740, 100, 640, 480, "B", (2.5, 2.45, 118), label="close-up camshot (zone: 2.2 m of anemone)", pane="none",
                    host=True, fish_pos=(2.6, -SAND_Z - 0.85 - 1.3), fish_tilt=-10, sway=0.6))
    s.append('<rect x="880" y="112" width="180" height="24" rx="12" fill="#0a1016" fill-opacity=".8"/><text x="970" y="129" text-anchor="middle" font-size="13" fill="#f7d9e8" font-weight="600">nestled · tentacles sway</text>')
    s.append('<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#f0b35c"/></marker></defs>')
    body = (f'<svg width="1440" height="843" viewBox="0 0 1440 843" style="position:absolute;top:57px;left:0" font-family="ui-sans-serif,system-ui,sans-serif">'
            f'<g transform="translate(0,-57)">{"".join(s)}'
            '<g fill="#e8f1f8" font-size="14" font-weight="600">'
            '<text x="60" y="88">A · Swimming — the whole tank in frame (Plan B: no front pane)</text>'
            '<text x="740" y="88">B · Hosting — camera closes in at the anemone</text></g></g>'
            '</svg>')
    caps = """
<div class="cap" style="position:absolute;left:60px;top:598px;width:640px">
<b>A.</b> The default view is the aquarium experience: a locked, straight-on shot through the front glass, whole tank visible.
The fish swims in X and Z with a shallow Y range (3.0 m interior depth at ×10). Its heading flips to face the direction of travel.
</div>
<div class="cap" style="position:absolute;left:740px;top:598px;width:640px">
<b>B.</b> A <code>target</code> zone around the anemone selects a second camshot. The fish stays a controllable actor; the anemone tentacles that
overlap it draw in front (front/back tentacle split is <em>mesh authoring</em>, not layering logic — see plan §7).
</div>
<div style="position:absolute;left:60px;top:690px;width:640px">
<table><tr><th colspan="3">Controls (existing logical buttons)</th></tr>
<tr><td>Swim</td><td><span class="k">←</span><span class="k">→</span><span class="k">↑</span><span class="k">↓</span> or D-pad / stick</td><td class="cap">↑↓ = swim up/down; ←→ = swim + turn</td></tr>
<tr><td>Y-depth</td><td><span class="k">2</span> in / <span class="k">3</span> out</td><td class="cap">buttons B / C, held</td></tr>
<tr><td>Dart</td><td><span class="k">1</span> (A)</td><td class="cap">short burst, then glide</td></tr>
</table></div>
<div style="position:absolute;left:740px;top:690px;width:640px">
<table><tr><th colspan="2">Camera zones (top view, ×10 metres)</th></tr>
<tr><td colspan="2" style="padding:0;border:0">
<svg width="640" height="120" viewBox="-6.6 -2.2 13.2 4.4" style="display:block">
<rect x="-6.096" y="-1.651" width="12.192" height="3.302" fill="#0b3550" stroke="#cfeff6" stroke-width=".06"/>
<circle cx="2.5" cy="0" r="2.2" fill="#b5558a" fill-opacity=".25" stroke="#f3b2d2" stroke-width=".05" stroke-dasharray=".2 .12"/>
<circle cx="2.5" cy="0" r=".9" fill="#b5558a"/>
<text x="2.5" y="1.05" text-anchor="middle" font-size=".42" fill="#fff">anemone zone → B</text>
<text x="-3.2" y="-.3" text-anchor="middle" font-size=".42" fill="#9fd8e8">everywhere else → A</text>
<circle cx="-1.6" cy=".2" r=".25" fill="#ff8a2a"/>
</svg></td></tr></table></div>"""
    return page("Aquarium — swimming and hosting", "MOCKUP — NOT SHIPPED", body + caps)

# ───────────────────────── 3. pane options, test card, narrow ─────────────────────────
def mock_pane():
    s = []
    W, H = 420, 315
    ys = 105
    xs = (40, 510, 980)
    s.append(screen(xs[0], ys, W, H, "P", (0, 2.7, 30), label="PLAN A · deferred (needs engine shader change)", pane="haze", fish_pos=(-1.6, -2.4)))
    s.append(screen(xs[1], ys, W, H, "Q", (0, 2.7, 30), label="PLAN B · CHOSEN · no front pane drawn", pane="none", fish_pos=(-1.6, -2.4)))
    s.append(screen(xs[2], ys, W, H, "R", (0, 2.7, 30), label="PLAN C · opaque tinted pane (fish hidden!)", pane="opaque", fish_pos=(-1.6, -2.4)))
    # Test card: pass / fail
    def card(x, y, ok):
        g = [f'<g transform="translate({x},{y})">',
             '<rect width="420" height="240" rx="6" fill="#000" stroke="#3a4a5a" stroke-width="2"/>']
        for i in range(0, 420, 30):
            for j in range(0, 240, 30):
                if ((i // 30) + (j // 30)) % 2 == 0:
                    g.append(f'<rect x="{i}" y="{j}" width="30" height="30" fill="#23303c"/>')
        # fish behind pane
        g.append(f'<g transform="translate(0,0)">{fish(120, 120, 1.35, uid="tc"+("1" if ok else "2"))}</g>')
        g.append(f'<rect x="60" y="30" width="180" height="170" fill="#bfeaf3" fill-opacity=".22" stroke="#cfeff6"/>' if ok else
                 f'<rect x="60" y="30" width="180" height="170" fill="#7db9c8"/>')
        g.append(f'<g transform="translate(320,120)">{fish(0, 0, 1.0, uid="tc"+("3" if ok else "4"))}</g>')
        lab = "needed — far fish visible, near fish not clipped" if ok else "stock engine: pane drawn opaque, far fish hidden"
        g.append(f'<text x="8" y="232" font-size="11" fill="{"#8be3a2" if ok else "#ff8f8f"}">{"✓" if ok else "✗"} {lab}</text></g>')
        return "".join(g)
    s.append(card(40, 490, True))
    s.append(card(510, 490, False))
    # narrow / phone landscape with touch controls
    s.append(f'<g transform="translate(980,470)"><rect width="420" height="200" rx="18" fill="#05080c" stroke="#3a4a5a" stroke-width="3"/>'
             + screen(50, 12, 320, 176, "N", (0, 2.7, 24), pane="none", fish_pos=(-1.6, -2.4)).replace('rx="6"', 'rx="4"') +
             '<g opacity=".8"><circle cx="34" cy="150" r="20" fill="#fff" fill-opacity=".14" stroke="#fff" stroke-opacity=".4"/>'
             '<text x="34" y="154" text-anchor="middle" font-size="11" fill="#fff">◀▶▲▼</text>'
             '<circle cx="384" cy="132" r="14" fill="#fff" fill-opacity=".14" stroke="#fff" stroke-opacity=".4"/><text x="384" y="136" text-anchor="middle" font-size="11" fill="#fff">A</text>'
             '<circle cx="384" cy="166" r="14" fill="#fff" fill-opacity=".14" stroke="#fff" stroke-opacity=".4"/><text x="384" y="170" text-anchor="middle" font-size="11" fill="#fff">B</text></g></g>')
    body = (f'<svg width="1440" height="843" viewBox="0 0 1440 843" style="position:absolute;top:57px;left:0" font-family="ui-sans-serif,system-ui,sans-serif">'
            f'<g transform="translate(0,-57)">{"".join(s)}'
            '<g fill="#e8f1f8" font-size="14" font-weight="600">'
            '<text x="40" y="76">Acrylic front pane — Plan B chosen; Plan A needs an engine change</text>'
            '<text x="40" y="472">Phase 0 test card — left: what Plan A needs; right: what the stock engine did</text>'
            '<text x="980" y="452">Narrow: phone landscape, touch profile</text></g></g></svg>')
    caps = """
<div class="cap" style="position:absolute;left:40px;top:440px;width:440px;display:none"></div>
<div class="cap" style="position:absolute;left:40px;top:748px;width:900px">
<b>Plan B (chosen):</b> leave the front face out; the four acrylic edges, rim, bevel highlights and back film still read as a tank, and the fish is never occluded. Works with the engine as it is. <b>Plan A (deferred):</b> a textured pane with bit-15 texels would draw at 50 %, but the fragment shader discards texture alpha, so today it is opaque; fixing it is an engine change (one line per backend, plus a capture sweep across all levels) and the pane must be created after every opaque actor. Tracked as its own TODO item. <b>Plan C</b> is what Plan A produces on the stock engine: an opaque pane hides the fish.<br>Phase 0 verdict: see the plan. Screenshots: <code>phase0-*.png</code>.</div>
<div class="cap" style="position:absolute;left:980px;top:690px;width:420px">
The touch profile reuses the condo's proven A/B + D-pad mapping — no new host UI. A cycles Swim → Depth; B darts.
</div>"""
    return page("Aquarium — acrylic pane, fallbacks, narrow", "MOCKUP — NOT SHIPPED", body + caps)

(OUT / "tank-dimensions.html").write_text(mock_dims())
(OUT / "gameplay-states.html").write_text(mock_states())
(OUT / "pane-fallbacks.html").write_text(mock_pane())
print("ok")
