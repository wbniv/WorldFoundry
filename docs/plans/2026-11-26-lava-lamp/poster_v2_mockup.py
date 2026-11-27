#!/usr/bin/env python3
"""Build poster-v2.html, the plan's mockup of the poster's second layout, from the real review draft.

    python3 docs/reference/lava-lamp-poster/make_poster.py --draft && python3 docs/reference/lava-lamp-poster/export_poster.py
    python3 docs/plans/2026-11-26-lava-lamp/poster_v2_mockup.py
    bash docs/plans/2026-11-26-lava-lamp/shoot.sh poster-v2.html

The mockup is the draft itself (docs/reference/lava-lamp-poster/poster.png, scaled to the 1440 x 900 canvas and
quantised to stay under the bundle's 512 KB) beside notes on what changed after Will's review of 2026-11-27.
poster.html beside it is the first layout, kept as the record.
"""
import base64
import io
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[2] / 'docs' / 'reference' / 'lava-lamp-poster' / 'poster.png'
OUT = HERE / 'poster-v2.html'

im = Image.open(SRC).convert('RGB')
h = 840
im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
buf = io.BytesIO()
im.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(buf, 'PNG', optimize=True)
img = base64.b64encode(buf.getvalue()).decode('ascii')

OUT.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>A3 poster, second layout</title>
<meta name="viewport" content="width=1440">
<style>
:root{{ --bg:#15101a; --ink:#efe7f4; --muted:#b8a9c4; --acc:#ffb070 }}
body{{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 "Noto Sans","DejaVu Sans",sans-serif }}
.wrap{{ display:flex; gap:28px; padding:30px }}
img{{ display:block; height:840px; box-shadow:0 0 0 1px #3a2c46 }}
h1{{ font-size:22px; margin:0 0 10px }}
li{{ margin:0 0 8px }}
b{{ color:var(--acc) }}
code{{ font-family:"Noto Sans Mono","DejaVu Sans Mono",monospace; font-size:13px }}
</style></head><body><div class="wrap"><img src="data:image/png;base64,{img}" width="{im.width}" height="{h}"
alt="The lava lamp A3 poster, second layout: the render and two text panels on top, history and patents below, a tall Forth column on the right">
<div><h1>A3 poster, second layout (review draft)</h1>
<p>Will, 2026‑11‑27: “remove (verify) and (ours) tags… pretty-print the forth and put in a narrower, longer column; consider how to relayout”.</p>
<ul>
<li><b>No status tags.</b> The verified / other source / ours statuses stay in <code>make_poster.py</code> as the build gate. On the page a sourced sentence ends in its superscript source number; the footer is the numbered source list with links, nothing else.</li>
<li><b>Forth in a tall side column</b>, the full height of the body: <code>ll-env</code>, <code>ll-heat0</code> (one blob’s step: heat, pooling, buoyancy, drift) and <code>ll-tick</code>, one definition per block, <code>if</code>/<code>else</code>/<code>then</code> indented, a break after each store. Each level mailbox number is shown by its name from <code>lamp.py</code> (<code>BLOB0_STUCK</code>, <code>STARTED</code>, <code>P1</code>); mapping the names back gives the shipped script, whitespace aside. Each block’s stack effect sits above it, outside the code.</li>
<li><b>The base shows 16:40</b> in the Cycles render.</li>
<li><b>Three columns:</b> the render leads at the top left (01), then how it moves (02) and what is in the bottle (03); the history (04) and the six patents with QR codes (05) span the two left columns; the Forth (06) and the four ways to move the wax (07) fill the right.</li>
<li>One A3 page, nothing under 8.25&nbsp;pt, no panel overflowing (<code>layout-review.json</code>).</li>
</ul></div></div>
<script>window.__ready = true;</script></body></html>
''', encoding='utf-8')
print(OUT, OUT.stat().st_size)
