#!/usr/bin/env python3
"""make_idle_mockup.py — draw the clownfish idle-cycle mockup from the canonical fish.

Renders the same part meshes, pivots and tunables the aquarium and this spike are
built from (wflevels/aquarium/clownfish.py) with a tiny side-on software projection: painter-sorted,
back-face culled, flat Lambert shading. Output is one self-contained 1440×900
HTML page (inline SVG + CSS, no scripts, no external assets).

    python3 wflevels/aquarium_idle/make_idle_mockup.py [out.html]

Default output: docs/plans/2026-09-30-clownfish-idle-animation/idle-cycle.html
Render the PNG beside it with headless Chrome (see the plan).
"""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'wflevels', 'aquarium'))
import clownfish as rig  # noqa: E402

FISH = rig.Clownfish()                 # ×10: the aquarium plan's world scale

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    REPO, 'docs', 'plans', '2026-09-30-clownfish-idle-animation', 'idle-cycle.html')

DT = 0.05                              # the engine's -rate20 tick
LIGHT = (0.35, -0.60, 0.72)            # toward the light: from the camera side, above
L = math.sqrt(sum(c * c for c in LIGHT))
LIGHT = tuple(c / L for c in LIGHT)
AMBIENT, KEY = 0.42, 0.68
MESHES = {name: mesh for name, mesh, _ in FISH.parts()}


def hexcol(rgb, k):
    return '#' + ''.join(f'{max(0, min(255, round(c * k * 255))):02x}' for c in rgb)


def fish_polys(poses, ox, oy, px_per_m):
    """SVG polygons (depth-sorted) of every part for one set of poses."""
    polys = []
    for name, (pos, rot, zs) in poses.items():
        mesh = MESHES[name]
        rows = rig.rot_matrix(*rot)
        world = []
        for v in mesh.verts:
            lv = (v[0], v[1], v[2] * zs)
            w = rig.apply(rows, lv)
            world.append((pos[0] + w[0], pos[1] + w[1], pos[2] + w[2]))
        for face, mat in zip(mesh.faces, mesh.mats):
            pts = [world[i] for i in face]
            n = rig._cross(rig._sub(pts[1], pts[0]), rig._sub(pts[2], pts[0]))
            ln = math.sqrt(rig._dot(n, n)) or 1.0
            n = tuple(c / ln for c in n)
            if n[1] >= 0.0:                      # camera looks along +Y: keep faces pointing -Y
                continue
            depth = sum(p[1] for p in pts) / len(pts)
            shade = AMBIENT + KEY * max(0.0, rig._dot(n, LIGHT))
            colour = hexcol(rig.COLOURS[mat], shade)
            sp = ' '.join(f'{ox + p[0] * px_per_m:.1f},{oy - p[2] * px_per_m:.1f}' for p in pts)
            polys.append((depth, f'<polygon points="{sp}" fill="{colour}" stroke="{colour}" stroke-width="0.6"/>'))
    polys.sort(key=lambda t: -t[0])              # far first
    return ''.join(p for _, p in polys)


def rest_outline(ox, oy, px_per_m):
    pts = rig.BODY_TOP + list(reversed(rig.BODY_BOTTOM[1:]))
    return ' '.join(f'{ox + x * FISH.s * px_per_m:.1f},{oy + y * FISH.s * px_per_m:.1f}' for x, y in pts)


def warm_idle():
    st = rig.RigState(FISH)
    for _ in range(int(6.0 / DT)):
        st.step(DT)
    return st


def frame_panel(x, y, w, h, st, label, sub):
    ch = st.channels()
    poses = rig.part_poses(FISH, ch, (0.0, 0.0, 0.0))
    ppm = 255.0
    ox, oy = x + w * 0.56, y + h * 0.56
    return (f'<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#0d2a4a"/>'
            f'<line x1="{x + 8}" x2="{x + w - 8}" y1="{oy:.1f}" y2="{oy:.1f}" stroke="#5f86b0" stroke-width="1" stroke-dasharray="4 5"/>'
            f'<polygon points="{rest_outline(ox, oy, ppm)}" fill="none" stroke="#9fc3e8" stroke-opacity=".35" stroke-width="1" stroke-dasharray="3 3"/>'
            + fish_polys(poses, ox, oy, ppm) +
            f'<text x="{x + 10}" y="{y + 20}" class="fl">{label}</text>'
            f'<text x="{x + 10}" y="{y + h - 10}" class="fs">{sub}</text></g>')


def plot(x, y, w, h, t0, t1, series, title, markers=(), shade=None, yfmt='{:+.0f}'):
    """Line plot; series = [(label, colour, [(t, v)], vmin, vmax)] each on its own band."""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#111a24" stroke="#24364a"/>',
           f'<text x="{x + 12}" y="{y + 20}" class="pt">{title}</text>']
    top, bottom = y + 32, y + h - 22
    band = (bottom - top) / len(series)
    sx = lambda t: x + 110 + (t - t0) / (t1 - t0) * (w - 124)
    if shade:
        for a, b, col, lab in shade:
            out.append(f'<rect x="{sx(a):.1f}" y="{top}" width="{sx(b) - sx(a):.1f}" height="{bottom - top}" fill="{col}"/>'
                       f'<text x="{sx(a) + 6:.1f}" y="{top + 14}" class="fs">{lab}</text>')
    for i, (lab, col, pts, vmin, vmax) in enumerate(series):
        by0, by1 = top + i * band + 6, top + (i + 1) * band - 6
        sy = lambda v: by1 - (v - vmin) / (vmax - vmin) * (by1 - by0)
        out.append(f'<text x="{x + 12}" y="{(by0 + by1) / 2 + 4:.1f}" class="fs" fill="{col}">{lab}</text>')
        out.append(f'<line x1="{sx(t0):.1f}" x2="{sx(t1):.1f}" y1="{sy((vmin + vmax) / 2):.1f}" y2="{sy((vmin + vmax) / 2):.1f}" stroke="#24364a"/>')
        d = ' '.join(f'{sx(t):.1f},{sy(v):.1f}' for t, v in pts)
        out.append(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="1.8"/>')
    for t, lab in markers:
        out.append(f'<line x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="{top}" y2="{bottom}" stroke="#e6edf3" stroke-opacity=".28"/>'
                   f'<text x="{sx(t) - 4:.1f}" y="{bottom + 14}" class="fs">{lab}</text>')
    return ''.join(out)


def main():
    st = warm_idle()
    period = 1.0 / FISH.T['fish-bob-hz']
    nframes = 8
    step_ticks = max(1, round(period / nframes / DT))
    frames, trace = [], []
    t = 0.0
    for i in range(nframes * step_ticks + 1):
        ch = st.channels()
        trace.append((t, ch))
        if i % step_ticks == 0 and len(frames) < nframes:
            frames.append((t, st.copy()))
        st.step(DT)
        t += DT

    svg = []
    fw, fh, gap = 326, 186, 16
    x0, y0 = 40, 92
    for i, (tf, snap) in enumerate(frames):
        ch = snap.channels()
        r, c = divmod(i, 4)
        x, y = x0 + c * (fw + gap), y0 + r * (fh + 34)
        sub = (f'bob {ch["bob"] * 1000:+.1f} mm · tail {ch["tail"] * 360:+.0f}° · '
               f'pec {ch["pec"] * 360:+.0f}° · dorsal {ch["dorsal"] * 100:.0f}%')
        svg.append(frame_panel(x, y, fw, fh, snap, f'F{i + 1} · t = {tf:.2f} s', sub))

    # Channel traces over the filmstrip's bob period.
    ts = [(tt, c) for tt, c in trace]
    series = [
        ('bob mm', '#7fd1ff', [(tt, c['bob'] * 1000) for tt, c in ts], -15, 15),
        ('tail °', '#ff9f43', [(tt, c['tail'] * 360) for tt, c in ts], -25, 25),
        ('pectoral °', '#ffd166', [(tt, c['pec'] * 360) for tt, c in ts], -35, 35),
        ('dorsal %', '#c3a6ff', [(tt, c['dorsal'] * 100) for tt, c in ts], 80, 102),
        ('pitch °', '#8be28b', [(tt, c['body_b'] * 360) for tt, c in ts], -3, 3),
    ]
    marks = [(tf, f'F{i + 1}') for i, (tf, _) in enumerate(frames)]
    svg.append(plot(40, 548, 676, 318, 0.0, trace[-1][0], series,
                    'Channels across one bob period (idle weight = 1)', marks))

    # Blend timeline: idle, input RIGHT at 3.0 s for 1.5 s, release.
    bl = rig.RigState(FISH)
    bt, tl = 0.0, []
    for _ in range(int(3.0 / DT)):
        bl.step(DT)
    x_pos = 0.0
    for i in range(int(4.0 / DT)):
        held = 1.0 <= bt < 2.5
        bl.step(DT, dx=1 if held else 0)
        x_pos += bl.vx * DT
        c = bl.channels()
        tl.append((bt, bl.w, c['tail'] * 360, x_pos, bl.idle_t))
        bt += DT
    shade = [(1.0, 2.5, '#1f3b2a', 'RIGHT held')]
    series2 = [
        ('idle w', '#7fd1ff', [(a, w) for a, w, _, _, _ in tl], -0.05, 1.05),
        ('tail °', '#ff9f43', [(a, tv) for a, _, tv, _, _ in tl], -30, 30),
        ('player x m', '#8be28b', [(a, xv) for a, _, _, xv, _ in tl], -0.2, max(xv for *_, xv, _ in tl) * 1.1),
    ]
    marks2 = [(1.0, 'input'), (1.0 + FISH.T['fish-idle-out'], ''),
              (2.5 + FISH.T['fish-idle-delay'], 'idle ramps in')]
    svg.append(plot(732, 548, 668, 318, 0.0, tl[-1][0], series2,
                    'Blend: idle → input → swim → release → idle  (t from input − 1 s)', marks2, shade))

    html = f'''<!DOCTYPE html>
<!-- Generated by wflevels/aquarium_idle/make_idle_mockup.py from wflevels/aquarium/clownfish.py — do not hand-edit. -->
<html lang="en"><head><meta charset="utf-8"><title>Clownfish idle cycle</title>
<style>
:root {{ --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#30363d; --panel:#161b22; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; width:1440px; height:900px; overflow:hidden; background:var(--bg); color:var(--fg);
  font:14px/1.45 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
header {{ display:flex; align-items:center; gap:14px; height:56px; padding:0 24px;
  border-bottom:1px solid var(--line); background:var(--panel); }}
header h1 {{ margin:0; font-size:17px; font-weight:650; white-space:nowrap; }}
header p {{ margin:0; color:var(--muted); font-size:13px; }}
header .tag {{ margin-left:auto; font:600 11px ui-monospace, Menlo, monospace; letter-spacing:.04em;
  color:var(--muted); border:1px solid var(--line); border-radius:10px; padding:2px 8px; }}
svg text.fl {{ fill:#e6edf3; font:600 13px ui-sans-serif, system-ui, sans-serif; }}
svg text.fs {{ fill:#9fb3c8; font:11px ui-monospace, Menlo, monospace; }}
svg text.pt {{ fill:#e6edf3; font:600 13px ui-sans-serif, system-ui, sans-serif; }}
svg text.hd {{ fill:#c9d1d9; font:600 13px ui-sans-serif, system-ui, sans-serif; }}
</style></head><body>
<header><h1>Clownfish idle — five-part rig, one bob period</h1>
<p>the aquarium's canonical fish, <code>wflevels/aquarium/clownfish.py</code> · 5 parts posed by the Director · Player never moves</p>
<span class="tag">MOCKUP — NOT AN ENGINE FRAME</span></header>
<svg width="1440" height="844" viewBox="0 56 1440 844" xmlns="http://www.w3.org/2000/svg">
<text x="40" y="82" class="hd">Idle filmstrip — {nframes} frames, {period / nframes:.2f} s apart (dashed line = the Player's z, dashed outline = rest pose)</text>
{''.join(svg)}
</svg></body></html>
'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        f.write(html)
    print(f'wrote {OUT} ({len(html) / 1024:.0f} KB)')


if __name__ == '__main__':
    main()
