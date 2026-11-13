#!/usr/bin/env python3
"""Top-down plan view, to scale, of the Snowgoons yard before and after the one-acre change.

Writes plan-view.html (self-contained inline SVG, 1440x900) beside this script. The "before"
geometry is read from the shipped meshes (quadpatch01.iff, house.iff) and placed at the actor
positions in snowgoons.lev; the "after" geometry is the plan's recommended layout (option B)
plus the square alternative (option A).

  python3 docs/plans/2026-11-13-snowgoons-one-acre-arena/plan_view.py
  google-chrome --headless=new --hide-scrollbars --window-size=1440,900 \
      --screenshot=docs/plans/2026-11-13-snowgoons-one-acre-arena/plan-view.png \
      file://$PWD/docs/plans/2026-11-13-snowgoons-one-acre-arena/plan-view.html
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts"))
from audit_face_hand import chunks, find_models  # noqa: E402

LEVEL = REPO / "wflevels" / "snowgoons-blender"
ACRE = 4046.8564224


def load(name):
    data = (LEVEL / name).read_bytes()
    _, model = next(iter(find_models(data)))
    size = struct.unpack_from("<I", model, 4)[0]
    parts = {tag: model[a:b] for tag, _, a, b in chunks(model, 8, size + 8)}
    verts = [tuple(c / 65536 for c in struct.unpack_from("<iii", parts[b"VRTX"], o + 12))
             for o in range(0, len(parts[b"VRTX"]), 24)]
    faces = [struct.unpack_from("<hhhh", parts[b"FACE"], o) for o in range(0, len(parts[b"FACE"]), 8)]
    return verts, faces


def tri_area(p, q, r):
    return abs((q[0] - p[0]) * (r[1] - p[1]) - (r[0] - p[0]) * (q[1] - p[1])) / 2


# Actor positions from snowgoons.lev (statplat_2 arena, statplat_1 house, statplat_3/4 trees, player_33).
ARENA_POS = (-0.036, 6.835)
HOUSE_POS = (-0.036, 12.054)
TREES = [((7.87, -10.57), 3.4, "tree02"), ((-8.12, 1.83), 4.4, "tree03")]   # radius = mean half-extent
PLAYER = (-1.0, -0.08)
CAMERA = (10.10, -40.40)       # camera_8, the bungee camera's authored start
ROOM_SPLIT_Y = -2.98           # room_6 (Room0) / room_16 (Room1) boundary

av, af = load("quadpatch01.iff")
hv, hf = load("house.iff")
lawn_area = sum(tri_area(av[a], av[b], av[c]) for a, b, c, m in af if m == 5)

# ── Proposed layouts (WF world metres) ─────────────────────────────────────────
B = dict(x=(-30.0, 30.0), y=(-46.0, 22.0), label="B · backyard rectangle (recommended)")
A = dict(x=(-32.0, 32.0), y=(-42.0, 22.0), label="A · square")
HEDGE_T, TILE, PILLAR = 2.0, 4.0, 0.8


def area(o):
    return (o["x"][1] - o["x"][0]) * (o["y"][1] - o["y"][0])


class View:
    """World metres → SVG pixels, north (+Y) up."""

    def __init__(self, x0, y1, scale, ox, oy):
        self.x0, self.y1, self.s, self.ox, self.oy = x0, y1, scale, ox, oy

    def p(self, x, y):
        return self.ox + (x - self.x0) * self.s, self.oy + (self.y1 - y) * self.s

    def pts(self, seq):
        return " ".join(f"{a:.1f},{b:.1f}" for a, b in (self.p(x, y) for x, y in seq))

    def rect(self, x0, y0, x1, y1, cls, extra=""):
        a, b = self.p(x0, y1)
        return (f'<rect class="{cls}" x="{a:.1f}" y="{b:.1f}" width="{(x1 - x0) * self.s:.1f}" '
                f'height="{(y1 - y0) * self.s:.1f}" {extra}/>')


def common(v, out, house=True):
    if house:
        for a, b, c, _ in hf:
            pa, pb, pc = [(hv[i][0] + HOUSE_POS[0], hv[i][1] + HOUSE_POS[1]) for i in (a, b, c)]
            out.append(f'<polygon class="house" points="{v.pts([pa, pb, pc])}"/>')
        hx, hy = v.p(HOUSE_POS[0] + 0.2, HOUSE_POS[1] + 0.6)
        out.append(f'<text class="lbl dark" x="{hx:.1f}" y="{hy:.1f}" text-anchor="middle">house</text>')
    for (x, y), r, name in TREES:
        cx, cy = v.p(x, y)
        out.append(f'<circle class="tree" cx="{cx:.1f}" cy="{cy:.1f}" r="{r * v.s:.1f}"/>')
        out.append(f'<circle class="trunk" cx="{cx:.1f}" cy="{cy:.1f}" r="{max(2.0, 0.35 * v.s):.1f}"/>')
    px, py = v.p(*PLAYER)
    out.append(f'<circle class="player" cx="{px:.1f}" cy="{py:.1f}" r="5"/>')
    out.append(f'<text class="lbl" x="{px + 8:.1f}" y="{py + 4:.1f}">player start</text>')


def dim_h(v, x0, x1, y, text, out, below=True):
    a, b = v.p(x0, y)
    c, _ = v.p(x1, y)
    off = 18 if below else -10
    out.append(f'<line class="dim" x1="{a:.1f}" y1="{b + off:.1f}" x2="{c:.1f}" y2="{b + off:.1f}" '
               f'marker-start="url(#arr)" marker-end="url(#arr)"/>')
    out.append(f'<text class="dimt" x="{(a + c) / 2:.1f}" y="{b + off + (14 if below else -5):.1f}" '
               f'text-anchor="middle">{text}</text>')


def dim_v(v, y0, y1, x, text, out):
    a, b = v.p(x, y1)
    _, d = v.p(x, y0)
    out.append(f'<line class="dim" x1="{a - 16:.1f}" y1="{b:.1f}" x2="{a - 16:.1f}" y2="{d:.1f}" '
               f'marker-start="url(#arr)" marker-end="url(#arr)"/>')
    out.append(f'<text class="dimt" transform="translate({a - 22:.1f},{(b + d) / 2:.1f}) rotate(-90)" '
               f'text-anchor="middle">{text}</text>')


def grid(v, x0, y0, x1, y1, step, out):
    gx = (int(x0 // step) + 1) * step
    while gx < x1:
        a, b = v.p(gx, y0)
        _, d = v.p(gx, y1)
        out.append(f'<line class="grid" x1="{a:.1f}" y1="{b:.1f}" x2="{a:.1f}" y2="{d:.1f}"/>')
        gx += step
    gy = (int(y0 // step) + 1) * step
    while gy < y1:
        a, b = v.p(x0, gy)
        c, _ = v.p(x1, gy)
        out.append(f'<line class="grid" x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{b:.1f}"/>')
        gy += step


def room_split(v, x0, x1, out):
    a, b = v.p(x0, ROOM_SPLIT_Y)
    c, _ = v.p(x1, ROOM_SPLIT_Y)
    out.append(f'<line class="room" x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{b:.1f}"/>')
    out.append(f'<text class="lbl room-t" x="{c - 4:.1f}" y="{b - 4:.1f}" text-anchor="end">Room1 ↑ · Room0 ↓</text>')


def proposed(v, o, out, details=True):
    (x0, x1), (y0, y1) = o["x"], o["y"]
    t = HEDGE_T
    out.append(v.rect(x0 - t, y0 - t, x1 + t, y1 + t, "hedge"))
    out.append(v.rect(x0, y0, x1, y1, "lawn"))
    if details:
        gx = x0 + TILE
        while gx < x1 - 1e-6:
            a, b = v.p(gx, y0)
            _, d = v.p(gx, y1)
            out.append(f'<line class="tile" x1="{a:.1f}" y1="{b:.1f}" x2="{a:.1f}" y2="{d:.1f}"/>')
            gx += TILE
        gy = y0 + TILE
        while gy < y1 - 1e-6:
            a, b = v.p(x0, gy)
            c, _ = v.p(x1, gy)
            out.append(f'<line class="tile" x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{b:.1f}"/>')
            gy += TILE
    for cx, cy in ((x0 - t / 2, y0 - t / 2), (x1 + t / 2, y0 - t / 2), (x1 + t / 2, y1 + t / 2), (x0 - t / 2, y1 + t / 2)):
        out.append(v.rect(cx - PILLAR / 2, cy - PILLAR / 2, cx + PILLAR / 2, cy + PILLAR / 2, "pillar"))


svg = []
# Shared scale: 9.5 px per metre for both before and after.
S = 9.5
before = View(-16.0, 23.5, S, 30, 120)
after = View(-34.0, 25.5, S, 395, 120)

# ── Before ─────────────────────────────────────────────────────────────────────
out = []
grid(before, -16, -15, 17, 23.5, 10, out)
for a, b, c, m in af:
    if m not in (1, 5):
        continue
    tri = [(av[i][0] + ARENA_POS[0], av[i][1] + ARENA_POS[1]) for i in (a, b, c)]
    out.append(f'<polygon class="{"lawn" if m == 5 else "hedge"}" points="{before.pts(tri)}"/>')
room_split(before, -15.5, 16.5, out)
# Collision walls with zero orientation: statplat_19 (south) and statplat_22 (behind the house).
for (x0, x1, y0, y1, name) in ((-14.30, 14.72, -16.85, -16.60, "statplat_19"), (-12.12, 12.80, 13.73, 13.98, "statplat_22")):
    out.append(before.rect(x0, y0, x1, y1, "wall"))
    lx, ly = before.p(x1, y1)
    out.append(f'<text class="lbl wall-t" x="{lx - 2:.1f}" y="{ly - 4:.1f}" text-anchor="end">{name}</text>')
common(before, out)
dim_h(before, -12.54, 12.96, -12.9, "lawn 25.5 m", out)
dim_v(before, -10.80, 19.86, -14.6, "lawn 30.7 m", out)
svg.append("\n".join(out))

# ── After (B) ──────────────────────────────────────────────────────────────────
out = []
grid(after, -34, -50, 34, 25.5, 10, out)
proposed(after, B, out)
room_split(after, -33, 33, out)
(bx0, bx1), (by0, by1) = B["x"], B["y"]
# New colliders: statplat_19-22 become zero-orientation walls on the inner hedge lines; statplat_15 the
# ground slab under the whole yard (dashed). Nothing blocks the path behind the house any more.
out.append(after.rect(bx0 - HEDGE_T, by0 - HEDGE_T, bx1 + HEDGE_T, by1 + HEDGE_T, "slab"))
for (x0, x1, y0, y1, name) in ((bx0, bx1, by0 - 0.25, by0, "statplat_19"), (bx1, bx1 + 0.25, by0, by1, "statplat_20"),
                               (bx0 - 0.25, bx0, by0, by1, "statplat_21"), (bx0, bx1, by1, by1 + 0.25, "statplat_22")):
    out.append(after.rect(x0, y0, x1, y1, "wall"))
lx, ly = after.p(bx1 - 1, by1 - 1.6)
out.append(f'<text class="lbl wall-t" x="{lx:.1f}" y="{ly:.1f}" text-anchor="end">walls statplat_19–22 on the hedge lines</text>')
lx, ly = after.p(bx1 - 1, by0 + 1.2)
out.append(f'<text class="lbl wall-t" x="{lx:.1f}" y="{ly:.1f}" text-anchor="end">statplat_15 = ground slab, top at the lawn (z −0.62)</text>')
# The old yard's outline, for scale.
out.append(f'<polygon class="ghost" points="{after.pts([(-12.54, -10.80), (12.96, -10.80), (12.96, 19.86), (-12.54, 19.86)])}"/>')
gx, gy = after.p(-12.3, -10.2)
out.append(f'<text class="lbl ghost-t" x="{gx:.1f}" y="{gy:.1f}">today’s lawn</text>')
common(after, out)
cx, cy = after.p(*CAMERA)
out.append(f'<path class="cam" d="M{cx - 7:.1f},{cy + 6:.1f} L{cx + 7:.1f},{cy + 6:.1f} L{cx:.1f},{cy - 8:.1f} Z"/>')
out.append(f'<text class="lbl" x="{cx + 10:.1f}" y="{cy + 4:.1f}">camera_8 start</text>')
dim_h(after, bx0, bx1, by1 + HEDGE_T, "lawn 60 m", out, below=False)
dim_v(after, by0, by1, bx0 - HEDGE_T, "lawn 68 m", out)
svg.append("\n".join(out))

# ── Option A thumbnail ─────────────────────────────────────────────────────────
out = []
sa = 2.6
thumb = View(-35.0, 25.0, sa, 1125, 610)
proposed(thumb, A, out, details=False)
common(thumb, out, house=True)
svg.append("\n".join(out))

# Scale bar (20 m at S).
bar_x, bar_y = 40, 650
scale_bar = (f'<line class="bar" x1="{bar_x}" y1="{bar_y}" x2="{bar_x + 20 * S}" y2="{bar_y}"/>'
             f'<line class="bar" x1="{bar_x}" y1="{bar_y - 5}" x2="{bar_x}" y2="{bar_y + 5}"/>'
             f'<line class="bar" x1="{bar_x + 10 * S}" y1="{bar_y - 4}" x2="{bar_x + 10 * S}" y2="{bar_y + 4}"/>'
             f'<line class="bar" x1="{bar_x + 20 * S}" y1="{bar_y - 5}" x2="{bar_x + 20 * S}" y2="{bar_y + 5}"/>'
             f'<text class="lbl" x="{bar_x}" y="{bar_y + 20}">0</text>'
             f'<text class="lbl" x="{bar_x + 10 * S}" y="{bar_y + 20}" text-anchor="middle">10 m</text>'
             f'<text class="lbl" x="{bar_x + 20 * S}" y="{bar_y + 20}" text-anchor="middle">20 m</text>'
             f'<text class="lbl" x="{bar_x}" y="{bar_y + 42}">both plans at 9.5 px/m · grid 10 m · lawn tiles 4 m</text>'
             f'<text class="lbl" x="{bar_x}" y="{bar_y + 60}">statplat_15/20/21 today are rotated boxes (not drawn);</text>'
             f'<text class="lbl" x="{bar_x}" y="{bar_y + 76}">19 and 22 have zero orientation.</text>')

hedge_len_b = 2 * ((bx1 - bx0) + (by1 - by0))
html = f"""<!DOCTYPE html>
<!-- Generated by plan_view.py; geometry read from wflevels/snowgoons-blender/{{quadpatch01,house}}.iff. -->
<html lang="en"><head><meta charset="utf-8"><title>Snowgoons yard plan view</title>
<style>
  :root {{ --bg:#ffffff; --fg:#1f2328; --muted:#656d76; --line:#d1d9e0; --panel:#f6f8fa; --accent:#0969da;
          --lawn:#eef2f7; --hedge:#2f6b3a; --house:#8a5a3c; --wall:#d1242f; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; width:1440px; height:900px; overflow:hidden; background:var(--bg); color:var(--fg);
         font:14px/1.45 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
  header {{ display:flex; align-items:center; gap:12px; padding:12px 24px; border-bottom:1px solid var(--line); background:var(--panel); height:52px; }}
  header h1 {{ margin:0; font-size:16px; font-weight:600; }}
  header .tag {{ margin-left:auto; font:600 11px ui-monospace, Menlo, monospace; letter-spacing:.04em; color:var(--muted);
                border:1px solid var(--line); border-radius:10px; padding:2px 8px; }}
  svg {{ position:absolute; left:0; top:52px; }}
  .lawn {{ fill:var(--lawn); stroke:#c9d3df; stroke-width:.4; }}
  .hedge {{ fill:var(--hedge); stroke:var(--hedge); stroke-width:.4; }}
  .pillar {{ fill:#1d4426; }}
  .tile {{ stroke:#c4cfdc; stroke-width:.6; }}
  .grid {{ stroke:#e6e9ee; stroke-width:1; }}
  .house {{ fill:var(--house); stroke:var(--house); stroke-width:.3; }}
  .tree {{ fill:#7a8f74; fill-opacity:.45; stroke:#55634f; stroke-width:1; }}
  .trunk {{ fill:#4b3727; }}
  .player {{ fill:#e0447a; stroke:#fff; stroke-width:1.5; }}
  .cam {{ fill:#0969da; }}
  .wall {{ fill:var(--wall); fill-opacity:.85; }}
  .slab {{ fill:none; stroke:var(--wall); stroke-width:1.2; stroke-dasharray:3 3; }}
  .room {{ stroke:#8250df; stroke-width:1.2; stroke-dasharray:6 4; }}
  .ghost {{ fill:none; stroke:#0969da; stroke-width:1.5; stroke-dasharray:5 4; }}
  .dim {{ stroke:#57606a; stroke-width:1; }}
  .bar {{ stroke:var(--fg); stroke-width:2; }}
  .lbl {{ font-size:12px; fill:var(--fg); }}
  .dark {{ fill:#fff; font-weight:600; font-size:11px; }}
  .dimt {{ font-size:12.5px; font-weight:600; fill:#24292f; }}
  .room-t {{ fill:#8250df; font-size:11px; }}
  .wall-t {{ fill:var(--wall); font-size:11px; }}
  .ghost-t {{ fill:#0969da; font-size:11px; }}
  .ttl {{ font-size:15px; font-weight:650; fill:var(--fg); }}
  .sub {{ font-size:12.5px; fill:var(--muted); }}
  aside {{ position:absolute; left:1075px; top:66px; width:355px; font-size:13px; }}
  aside h2 {{ font-size:14px; margin:0 0 6px; }}
  table {{ border-collapse:collapse; width:100%; margin-bottom:12px; }}
  table {{ font-size:12px; }}
  td, th {{ border-bottom:1px solid var(--line); padding:3px 4px; text-align:left; }}
  td.n, th {{ white-space:nowrap; }}
  td.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
  .key {{ display:grid; grid-template-columns:18px 1fr; gap:3px 8px; align-items:center; margin-bottom:12px; }}
  .sw {{ width:16px; height:12px; border-radius:2px; }}
</style></head><body>
<header><h1>Snowgoons yard: today vs one acre, top-down, to scale (north = +Y, up)</h1><span class="tag">MOCKUP · PLAN 2026‑11‑13</span></header>
<svg width="1080" height="848" viewBox="0 0 1080 848">
  <defs><marker id="arr" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="#57606a"/></marker></defs>
  <text class="ttl" x="30" y="28">Today</text>
  <text class="sub" x="30" y="46">lawn {lawn_area:,.0f} m² = {lawn_area / ACRE:.2f} acre (3ds Max arena, quadpatch01.iff)</text>
  <text class="ttl" x="395" y="28">After · {B['label']}</text>
  <text class="sub" x="395" y="46">lawn {B['x'][1] - B['x'][0]:.0f} × {B['y'][1] - B['y'][0]:.0f} m = {area(B):,.0f} m² = {area(B) / ACRE:.3f} acre · hedge {hedge_len_b:.0f} m · house and trees stay put</text>
  {svg[0]}
  {svg[1]}
  {scale_bar}
</svg>
<aside>
  <h2>Numbers</h2>
  <table>
    <tr><th></th><th>today</th><th>B (rec.)</th><th>A</th></tr>
    <tr><td>lawn (m)</td><td class="n">25.5 × 30.7*</td><td class="n">60 × 68</td><td class="n">64 × 64</td></tr>
    <tr><td>lawn area (m²)</td><td class="n">{lawn_area:,.0f}</td><td class="n">{area(B):,.0f}</td><td class="n">{area(A):,.0f}</td></tr>
    <tr><td>acres</td><td class="n">{lawn_area / ACRE:.2f}</td><td class="n">{area(B) / ACRE:.3f}</td><td class="n">{area(A) / ACRE:.3f}</td></tr>
    <tr><td>outside hedges (m)</td><td class="n">29.5 × 34.7</td><td class="n">64 × 72</td><td class="n">68 × 68</td></tr>
    <tr><td>lawn faces</td><td class="n">176</td><td class="n">510</td><td class="n">512</td></tr>
    <tr><td>arena faces total</td><td class="n">445</td><td class="n">≈ 1,060</td><td class="n">≈ 1,060</td></tr>
    <tr><td>north path behind house</td><td class="n">blocked</td><td class="n">6 m, open</td><td class="n">6 m, open</td></tr>
    <tr><td>lawn tilt</td><td class="n">4.5° (render)</td><td class="n">level</td><td class="n">level</td></tr>
  </table>
  <div class="sub" style="margin:-6px 0 10px">* bounding box; the lawn itself is {lawn_area:,.0f} m² (corners and the hedge lip are cut out).</div>
  <h2>Key</h2>
  <div class="key">
    <span class="sw" style="background:#eef2f7;border:1px solid #c9d3df"></span><span>lawn, G_SnowyGrass11 (one tile per 4 m cell)</span>
    <span class="sw" style="background:#2f6b3a"></span><span>hedge band 2 m, ~2.1 m tall; corner pillars 4.2 m</span>
    <span class="sw" style="background:#8a5a3c"></span><span>house (house.iff, stays put)</span>
    <span class="sw" style="background:#d1242f"></span><span>invisible collision walls (statplat)</span>
    <span class="sw" style="border-top:2px dashed #8250df;height:0"></span><span>Room0 / Room1 boundary, y = −2.98</span>
    <span class="sw" style="border-top:2px dashed #0969da;height:0"></span><span>today’s lawn outline, for scale</span>
  </div>
  <h2>Option A · square 64 × 64 m</h2>
  <div class="sub">same north edge and house; {area(A) / ACRE:.3f} acre; 4 m less depth in front of the house, 4 m more width</div>
</aside>
<svg width="1440" height="848" viewBox="0 0 1440 848" style="pointer-events:none">{svg[2]}</svg>
</body></html>
"""
(HERE / "plan-view.html").write_text(html)
print(f"lawn today {lawn_area:.1f} m2; B {area(B):.0f}; A {area(A):.0f}; plan-view.html {len(html)} bytes")
