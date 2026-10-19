#!/usr/bin/env python3
"""make_mockups.py: the mockup for the dart-startle plan, drawn from a REAL run of school.fth (the engine's zForth in the standalone host), not from a drawing.

startle.html (+ .png): the tank seen from the front, eleven fish: a resting leader and ten followers swarming round it; a dart at t = 0 kicks the followers within 5 body lengths
(the startle of school.fth: the heading flips away from the leader at once, 2.5 times the speed for 0.6 s), then the zones pull them back. Panels at t = 0, 0.3, 0.6, 1.5 and 4 s after the dart.
Usage: python3 make_mockups.py [-h]
"""
import math, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REF = HERE.parents[1] / "reference" / "swarming-poster"
sys.path.insert(0, str(REF))
import couzin, forth_check as fc                       # noqa: E402

if len(sys.argv) > 1:
    print(__doc__); sys.exit(0)

BOX = (6.7, 1.7, 2.35)
h = fc.make_host(); fc.load_school(h, 11)
p = dict(couzin.PAPER, sigma=0.0, s=2.0, theta=120.0)
fc.set_params(h, p, 0.0, 10.0, 3.0, wall=0.6)             # the swarm setting: the leader is resting
for k, b in enumerate(BOX):
    h.write(fc.PAR + 11 + k, -b); h.write(fc.PAR + 14 + k, b)
rng = np.random.default_rng(4)
pos = (rng.random((11, 3)) * 2 - 1) * np.array([4.0, 1.2, 1.8]); vel, _ = couzin.unit(rng.normal(size=(11, 3)))
pos[0] = [0, 0, 0]; vel[0] = [1, 0, 0]
for i in range(11):
    fc.put(h, i, pos[i], vel[i])
for _ in range(150):                                         # settle into a swarm round the resting leader
    assert h.eval("sch-tick") == "ok"
dt = 0.1                                                     # the tick the parameters were set for
snaps = {}
want = {0.0: 0, 0.3: 3, 0.6: 6, 1.5: 15, 4.0: 40}
assert h.eval("5 sch-startle-all") == "ok"
for tick in range(0, 41):
    if tick in want.values():
        snaps[[k for k, v in want.items() if v == tick][0]] = fc.get(h, 11)[0].copy()
    assert h.eval("sch-tick") == "ok"
h.close()

W, H = 1440, 900
cw, ch = 255, 270 * (2 * BOX[2]) / (2 * BOX[0])
s = []
sc = cw / (2 * BOX[0])
for k, (t, P) in enumerate(snaps.items()):
    x0, y0 = 20 + k * (cw + 20), 150
    s.append(f'<rect x="{x0}" y="{y0}" width="{cw}" height="{ch * 1.0:.0f}" fill="#eaf3f8" stroke="#1d2733" stroke-width="2"/>')
    s.append(f'<circle cx="{x0 + cw / 2 + 0:.1f}" cy="{y0 + ch / 2:.1f}" r="{5 * sc:.1f}" fill="#c0392b" fill-opacity=".10" stroke="#c0392b" stroke-dasharray="5 4"/>')
    for i in range(11):
        x = x0 + (P[i, 0] + BOX[0]) * sc; y = y0 + (BOX[2] - P[i, 2]) * sc
        col = "#c05800" if i == 0 else "#1d4660"
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{5 if i == 0 else 4}" fill="{col}"/>')
    d = np.linalg.norm(P[1:] - P[0], axis=1)
    s.append(f'<text x="{x0}" y="{y0 - 12}" font-size="20" font-weight="700" fill="#1d2733">{"at the dart" if t == 0 else f"+{t:g} s"}</text>')
    s.append(f'<text x="{x0}" y="{y0 + ch / 2 + 5 * sc + 22}" font-size="15" fill="#5c6b7a">median distance to the leader {np.median(d):.1f} BL</text>')
    s.append(f'<text x="{x0}" y="{y0 + ch / 2 + 5 * sc + 42}" font-size="15" fill="#5c6b7a">{int((d < 5).sum())} of 10 within 5 BL</text>')
s.append('<text x="20" y="420" font-size="17" fill="#1d2733">The dashed circle is the startle radius, 5 body lengths. Orange: the player’s fish, resting; dark: the ten followers. Front view of the tank (x right, z up), one real run of school.fth.</text>')
svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{"".join(s)}</svg>'
html = (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Dart startle mockup</title><style>*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#fff;'
        f'font:14px/1.4 "Noto Sans","DejaVu Sans",Arial,sans-serif;color:#1d2733}}h1{{position:absolute;left:20px;top:14px;margin:0;font-size:26px}}svg{{position:absolute;left:0;top:0}}</style></head>'
        f'<body>{svg}<h1>The dart startles the followers: before, during, after (a real run)</h1></body></html>')
out = HERE / "startle.html"; out.write_text(html, encoding="utf-8")
chrome = shutil.which("google-chrome") or shutil.which("chromium")
with tempfile.TemporaryDirectory() as prof:
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--user-data-dir={prof}", "--hide-scrollbars", f"--window-size={W},{H}", f"--screenshot={out.with_suffix('.png')}", out.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
print("wrote", out, out.with_suffix(".png"))
