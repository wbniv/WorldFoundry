#!/usr/bin/env python3
"""Build the browser gallery from recorded runtime images, clips and check results."""
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/plans/2026-10-02-aquarium-three-more-tanks/engine'
sections=[]
rows=[]
for kind,title,description in [
    ('betta','Calm Betta','Broad leaves and a Thai temple-style pavilion with red roofs, gold trim and an empty open hall. No Buddha figure or statues.'),
    ('jellyfish','Jellyfish','Six opaque pale jellies with independent drift, bell contraction and lagging oral-arm motion.'),
    ('lionfish','Lionfish','Two striped lionfish, long dorsal spines, moving fin fans and a sparse rocky reef.'),
    ('plants','Planted Tank','Three grouped foliage meshes and one sea urchin crawling at 0.0125 world units/second. No fish, rocks or decorations.')]:
    r=json.loads((OUT/kind/'checks.json').read_text())
    rows.append(f'<tr><td>{title}</td><td>{r["animals"]}</td><td>{r["actors"]}</td><td>{r["status"]}</td><td>{r.get("desktop_debug_ms_per_frame_estimate",0):.1f}</td></tr>')
    sections.append(f'<section id="{kind}"><h2>{title}</h2><p>{description}</p><video controls loop muted playsinline src="{kind}/motion.mp4" poster="{kind}/close-up.png"></video><p>Five seconds of fixed 20 Hz simulation, encoded at 20 fps. Playback does not measure rendering speed.</p><h3>Whole tank</h3><img src="{kind}/whole-tank.png" alt="{title} whole tank engine capture"><h3>Close-up</h3><img src="{kind}/close-up.png" alt="{title} engine close-up"><details><summary>Engine check results</summary><pre>{html.escape(json.dumps(r,indent=2))}</pre></details></section>')
menu=''
if (OUT/'menu/checks.json').exists():
    menu='<h2>Six-tank selector · actual engine</h2><img src="menu/selector.png" alt="Actual six-entry Aquarium selector"><p>Verified selection/return sequence: 5 → 2 → 3 → 4 → 0 → 1 → 5. This isolated desktop preview leaves the current app bundle and device alone. <a href="menu/checks.json">Menu results and source hashes</a>.</p>'
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Four Aquarium tanks · actual engine evidence</title><style>body{background:#0b1622;color:#e6edf1;font:18px/1.6 system-ui;margin:0}main{max-width:1050px;margin:auto;padding:32px}h1{line-height:1.2}p{color:#b1c5d0}a{color:#93dce6}img,video{display:block;width:100%;height:auto;border-radius:12px;margin:18px 0 30px}table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #3a5365;padding:12px}pre{font-size:14px;overflow:auto;background:#152a3c;padding:20px}section{margin-top:55px}nav{display:flex;gap:26px;flex-wrap:wrap}</style><main><h1>Betta, Jellyfish, Lionfish and Planted Tank</h1><p>Actual World Foundry engine screenshots and animation clips. The separate concept mockups remain labelled as concepts.</p><nav><a href="#betta">Thai pavilion / Betta</a><a href="#jellyfish">Jellyfish</a><a href="#lionfish">Lionfish</a><a href="#plants">Planted Tank</a><a href="../index.html">Design mockups</a></nav><h2>Desktop checks</h2><table><tr><th>Tank</th><th>Animals</th><th>Actors</th><th>Checks</th><th>Debug estimate ms/frame</th></tr>'''+''.join(rows)+'''</table><p>Timing is a local debug two-point wall-time estimate without vsync, not release/device frame pacing. Jellyfish exceeds the 16.67 ms budget in this estimate. Desktop timing is distinct from the recorded Chromecast deployment checks. Physical touch and held Back remain pending.</p>'''+menu+''.join(sections)+'''<p><a href="../index.html">Earlier design concepts</a> · <a href="../../2026-10-02-aquarium-three-more-tanks.md">Plan</a></p></main></html>''')
print(OUT/'index.html')
