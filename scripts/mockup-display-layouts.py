#!/usr/bin/env python3
"""Draw where the Tide Harbour river panel sits on five screen shapes, now and with the display mailboxes.

    python3 scripts/mockup-display-layouts.py [OUTDIR] [-h]

Writes layouts.png (1440 x 900, five screens, two rows) and layouts.html (the same drawing live, with a slider for the
screen's shape) into OUTDIR, default docs/plans/2026-11-22-display-mailboxes/. Plan: docs/plans/2026-11-22-display-mailboxes.md.

The geometry is the Tide Harbour director's: the panel is a full-height strip PANEL_FRAC (0.27) of the screen's width wide,
on one side (here the right). Today (wflevels/tide_harbour/panel.py: ASPECT = 16/9) its width and its edge are computed for a
16:9 frame centred on the screen, so on any other shape they are wrong; with the runtime display aspect they come from the
screen that is really drawn. The Pixel row is the real measurement: a 1520 x 680 drawing area (aspect 2.235) on which the
panel's right edge was at about x = 1445 of 1600 (docs/plans/2026-11-22-display-mailboxes/pixel-tide-now.png).
"""
import json
import os
import sys

PANEL_FRAC = 0.27
SHAPES = [("TV 16:9", 16 / 9), ("Pixel landscape", 1520 / 680), ("Ultrawide 21:9", 21 / 9), ("Tablet 4:3", 4 / 3), ("Phone portrait", 0.45)]


def panel_now(aspect, h=1.0):
    """(left, right) of the panel in screen x from the screen's left edge, for a display h tall: today's constant 16:9 frame."""
    w = h * aspect
    frame = h * 16 / 9
    right = w / 2 + frame / 2
    return right - PANEL_FRAC * frame, right


def panel_new(aspect, h=1.0):
    w = h * aspect
    return w - PANEL_FRAC * w, w


def visible(aspect, edges, h=1.0):
    w = h * aspect
    left, right = edges
    return max(0.0, min(right, w) - max(left, 0.0)) / (right - left)


def png(out):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1440, 900
    im = Image.new("RGB", (W, H), (22, 26, 24)); d = ImageDraw.Draw(im)
    bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    reg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    d.text((30, 20), "Where the river panel sits, on five screen shapes", fill=(240, 240, 228), font=bold)
    d.text((30, 54), "Panel = a full-height strip 27 % of the screen's width, on the right. Red = off the screen.", fill=(170, 175, 165), font=reg)
    h_px = 120
    for row, (title, fn) in enumerate((("Today: placed for a centred 16:9 frame", panel_now), ("With the display mailboxes: placed for the screen that is drawn", panel_new))):
        top = 120 + row * 380
        d.text((30, top - 4), title, fill=(255, 190, 90) if row == 0 else (140, 220, 150), font=bold)
        cursor = 30
        for i, (name, aspect) in enumerate(SHAPES):
            w_px = h_px * aspect
            slot = max(w_px, 250) + 24                                  # wide enough for the label under it
            x0 = cursor
            cursor += slot
            y0 = top + 60
            d.rectangle([x0, y0, x0 + w_px, y0 + h_px], fill=(14, 20, 40), outline=(120, 130, 120))
            left, right = fn(aspect, h_px)
            pl, pr = x0 + left, x0 + right
            vis = visible(aspect, (left, right), h_px)
            if min(pr, x0 + w_px) > max(pl, x0):                            # some of it is on the screen
                d.rectangle([max(pl, x0), y0, min(pr, x0 + w_px), y0 + h_px], fill=(150, 120, 70))
            if pr > x0 + w_px + 0.5:                                   # off the right edge: show it, hatched red
                d.rectangle([x0 + w_px, y0, pr, y0 + h_px], outline=(235, 70, 60))
                for k in range(0, int(pr - x0 - w_px), 6):
                    d.line([x0 + w_px + k, y0 + h_px, min(x0 + w_px + k + 6, pr), y0], fill=(235, 70, 60))
            if pl < x0 - 0.5:
                d.rectangle([pl, y0, x0, y0 + h_px], outline=(235, 70, 60))
            d.text((x0, y0 + h_px + 12), name, fill=(235, 235, 225), font=reg)
            d.text((x0, y0 + h_px + 36), f"aspect {aspect:.3f}", fill=(170, 175, 165), font=small)
            d.text((x0, y0 + h_px + 56), f"panel {PANEL_FRAC * 100 if row else (right - left) / w_px * 100:.0f} % wide, {vis * 100:.0f} % visible",
                   fill=(255, 120, 100) if vis < 0.99 else (140, 220, 150), font=small)
            gap = (x0 + w_px) - min(pr, x0 + w_px)
            d.text((x0, y0 + h_px + 76), f"gap to the edge {gap / h_px * 680:.0f} px at 680 high" if gap > 0.5 else "at the edge", fill=(170, 175, 165), font=small)
    d.text((30, 860), "Measured on the Pixel (screenshot in this folder): the panel's right edge at x = 1445 of 1600, 155 px short of the edge.",
           fill=(170, 175, 165), font=small)
    im.save(out, optimize=True)


HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Display layouts</title><style>
:root{--bg:#161a18;--fg:#f0f0e4;--mut:#aab1a4;--warn:#ff7864;--ok:#8cdc96;--amb:#ffbe5a}
@media (prefers-color-scheme: light){:root{--bg:#f4f4ec;--fg:#1c211d;--mut:#555d54;--warn:#c0392b;--ok:#1e7a37;--amb:#a15f00}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 system-ui,sans-serif;padding:16px;max-width:1100px;margin:auto}
h1{font-size:20px;margin:0 0 4px}p{color:var(--mut);margin:4px 0 12px}.row{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}
.box{flex:1 1 360px}.box h2{font-size:15px;margin:0 0 6px}canvas{width:100%;background:#0e1428;border:1px solid var(--mut)}
label{display:block;margin:10px 0 2px}input[type=range]{width:100%}.k{display:inline-block;margin:6px 10px 0 0;padding:2px 8px;border:1px solid var(--mut);border-radius:4px;cursor:pointer;color:var(--fg);background:none;font:inherit}
.r{font-variant-numeric:tabular-nums}.w{color:var(--warn)}.o{color:var(--ok)}</style></head><body>
<h1>Where the river panel sits, for any screen shape</h1>
<p>A full-height strip, 27 % of the screen's width, on the right. Drag the slider or pick a screen. Red hatching is off the screen.</p>
<div>__BUTTONS__</div><label for="a">Screen aspect (width / height): <b id="av">1.778</b></label>
<input id="a" type="range" min="0.4" max="2.6" step="0.005" value="1.778">
<div class="row"><div class="box"><h2 style="color:var(--amb)">Today: placed for a centred 16:9 frame</h2><canvas id="c0" width="560" height="320"></canvas><div class="r" id="t0"></div></div>
<div class="box"><h2 style="color:var(--ok)">With the display mailboxes: placed for the screen that is drawn</h2><canvas id="c1" width="560" height="320"></canvas><div class="r" id="t1"></div></div></div>
<script>
const F=0.27,H=300;
function place(kind,asp){const w=H*asp;if(kind==0){const fr=H*16/9,r=w/2+fr/2;return [r-F*fr,r]}return [w-F*w,w]}
function draw(cv,kind,asp,out){const x=cv.getContext('2d');x.clearRect(0,0,cv.width,cv.height);const w=H*asp,s=Math.min(1,(cv.width-80)/(w*1.4)),W=w*s,Hh=H*s,x0=(cv.width-W)/2-(kind==0?0:0),y0=10;
x.fillStyle='#0e1428';x.fillRect(x0,y0,W,Hh);x.strokeStyle='#789';x.strokeRect(x0,y0,W,Hh);
let [l,r]=place(kind,asp);l*=s;r*=s;const vl=Math.max(l,0),vr=Math.min(r,W);x.fillStyle='#96784a';if(vr>vl)x.fillRect(x0+vl,y0,vr-vl,Hh);
x.strokeStyle='#eb463c';if(r>W){for(let k=0;k<r-W;k+=6){x.beginPath();x.moveTo(x0+W+k,y0+Hh);x.lineTo(x0+W+k+6,y0);x.stroke()}x.strokeRect(x0+W,y0,r-W,Hh)}
if(l<0)x.strokeRect(x0+l,y0,-l,Hh);const vis=Math.max(0,vr-vl)/(r-l),gap=W-Math.min(r,W);
out.innerHTML='panel '+((r-l)/W*100).toFixed(0)+' % of the screen wide, <span class="'+(vis<.99?'w':'o')+'">'+(vis*100).toFixed(0)+' % visible</span>, '+(gap>0.5?'gap to the edge '+(gap/Hh*680).toFixed(0)+' px at 680 high':'at the edge')}
const a=document.getElementById('a'),av=document.getElementById('av');
function go(){const v=+a.value;av.textContent=v.toFixed(3);draw(document.getElementById('c0'),0,v,document.getElementById('t0'));draw(document.getElementById('c1'),1,v,document.getElementById('t1'))}
a.oninput=go;document.querySelectorAll('.k').forEach(b=>b.onclick=()=>{a.value=b.dataset.a;go()});go();
</script></body></html>"""


def html(out):
    buttons = "".join(f'<button class="k" data-a="{asp:.4f}">{name} ({asp:.3f})</button>' for name, asp in SHAPES)
    open(out, "w").write(HTML.replace("__BUTTONS__", buttons))


def main(argv):
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    out = argv[0] if argv else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs/plans/2026-11-22-display-mailboxes")
    os.makedirs(out, exist_ok=True)
    png(os.path.join(out, "layouts.png"))
    html(os.path.join(out, "layouts.html"))
    print(json.dumps({n: dict(now_visible=round(visible(a, panel_now(a)), 3), new_visible=round(visible(a, panel_new(a)), 3)) for n, a in SHAPES}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
