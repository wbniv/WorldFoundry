#!/usr/bin/env python3
"""Draw the Cuckoo Village candle-flicker mockups (plan docs/plans/2026-11-22-cuckoo-village-candle-flicker.md).

    python3 scripts/mockup-candle-flicker.py [OUTDIR] [-h]

Writes flame-shapes.html and flicker-schedule.html (self-contained, 1440 x 900, live) into OUTDIR, default
docs/plans/2026-11-22-cuckoo-village-candle-flicker/, then a same-name .png of each from headless Chrome (the page renders its
fixed first frame when the URL ends in #still, so the picture is the same every run). The candle positions are the level's
(wflevels/cuckoo_village/candles.py, a pine at scale 1 at the origin); the flicker rule is the one the plan proposes. Prints the
numbers the plan quotes: changes a second per group, pixel sizes.
"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "wflevels", "cuckoo_village"))
import candles as cd  # noqa: E402

F1, F2 = 2.3, 3.7          # revolutions a second: whole cycles a minute (138 and 222), so the pattern repeats at every minute
PHI = 0.618034


def phase(tree, group):
    return ((2 * tree + group) * PHI) % 1.0


def shape(t, tree, group):
    """1 = tall and leaning one way, 2 = short and leaning the other."""
    p = phase(tree, group)
    return 1 if math.sin(math.tau * (F1 * t + p)) + math.sin(math.tau * (F2 * t + 2 * p)) > 0 else 2


def stats():
    dt = 1 / 600.0
    flips = 0
    n = 0
    for tree in range(12):
        for g in (0, 1):
            prev = shape(0, tree, g)
            for k in range(1, 60 * 600):
                s = shape(k * dt, tree, g)
                flips += s != prev
                prev = s
                n += 1
    per_group_per_s = flips / 24 / 60.0
    return dict(changes_per_second_per_group=round(per_group_per_s, 2), mean_ms_between=round(1000 / per_group_per_s))


def pine_candles():
    bases = cd.candle_bases(0, (0.0, 0.0, 0.0), 0.0, 1.0)
    return [dict(x=b[0], y=b[1], z=b[2], group=i % cd.PER_TIER) for i, b in enumerate(bases)]


CSS = """
:root{--bg:#0e1218;--panel:#161c25;--line:#2c3644;--fg:#e8ecf2;--mut:#9aa6b6;--a:#ffb454;--b:#5cc8ff;--ok:#8cdc96;--cream:#efe3c0;--pine:#1f4a35}
*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;overflow:hidden;background:var(--bg);color:var(--fg);font:15px/1.45 ui-sans-serif,system-ui,sans-serif}
h1{font-size:24px;margin:0}h2{font-size:15px;margin:0 0 8px;color:var(--mut);font-weight:600;letter-spacing:.02em}.wrap{padding:22px 30px}
.sub{color:var(--mut);margin:2px 0 14px}.grid{display:grid;gap:16px}.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
table{border-collapse:collapse;width:100%}td,th{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}th{color:var(--mut);font-weight:600}
.a{color:var(--a)}.b{color:var(--b)}code{font:13px ui-monospace,monospace;color:var(--cream)}label{color:var(--mut);font-size:14px}
input[type=range]{width:200px;vertical-align:middle}button{background:var(--line);color:var(--fg);border:0;border-radius:6px;padding:5px 12px;font:inherit;cursor:pointer}
.k{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
"""

SHAPES_HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=1440"><title>Mockup: flame shapes</title><style>__CSS__</style></head><body><div class="wrap">
<h1>Four flame meshes per tree, two shapes for each of two groups</h1>
<p class="sub">Drawn from the level's real candle positions (a pine at scale 1). Each group is the five candles on one side of the tree; the director shows one of its two shapes at a time.</p>
<div class="grid" style="grid-template-columns:430px 1fr">
<div class="card"><h2>One flame, three poses (side view, millimetres)</h2><svg id="poses" width="398" height="330" viewBox="0 0 398 330"></svg>
<table style="margin-top:6px"><tr><th>Pose</th><th>Height</th><th>Ring radius</th><th>Tip leans</th></tr>
<tr><td>Today (static)</td><td>75</td><td>22</td><td>0</td></tr><tr><td class="a">Shape 1: tall</td><td>90</td><td>20</td><td>+14 toward the draught</td></tr><tr><td class="b">Shape 2: short</td><td>60</td><td>24</td><td>&minus;10 away from it</td></tr></table></div>
<div class="card"><h2>The ten candles of one pine, side view (metres)</h2><svg id="tree" width="860" height="360" viewBox="0 0 860 360"></svg>
<div style="margin-top:4px"><span class="k" style="background:var(--a)"></span>group A (5 candles, one side)&nbsp;&nbsp;<span class="k" style="background:var(--b)"></span>group B (the other 5, opposite side)&nbsp;&nbsp;<span class="mut" style="color:var(--mut)">a flame is 8 triangles in every pose, so 80 triangles show per tree at any moment</span></div></div></div>
<div class="card" style="margin-top:16px"><h2>The four actors of each tree, and what shows when</h2><table>
<tr><th>Actor</th><th>Candles</th><th>Visibility cell (tree <code>i</code>)</th><th>Shows when</th></tr>
<tr><td><code>candle_flames_a1_NN</code></td><td class="a">group A, shape 1</td><td><code>232 + 4i</code></td><td>lit and the group's rule says shape 1</td></tr>
<tr><td><code>candle_flames_a2_NN</code></td><td class="a">group A, shape 2</td><td><code>233 + 4i</code></td><td>lit and the rule says shape 2</td></tr>
<tr><td><code>candle_flames_b1_NN</code></td><td class="b">group B, shape 1</td><td><code>234 + 4i</code></td><td>lit and group B's rule says shape 1</td></tr>
<tr><td><code>candle_flames_b2_NN</code></td><td class="b">group B, shape 2</td><td><code>235 + 4i</code></td><td>lit and group B's rule says shape 2</td></tr></table>
<p class="sub" style="margin:8px 0 0">&ldquo;Lit&rdquo; is today's rule: the candles show (1 December to 6 January, or Candles all year) and the window glow of house <code>i mod 13</code> is on, so Window lights Off puts every flame out.</p></div>
</div><script>
const T=__TREE__,GOLD='#ffb454',BLUE='#5cc8ff';
function pose(svg,ox,h,r,lean,col,label){const s=1.3,y0=300,x=ox;const p=(dx,dy)=>[x+dx*s,y0-dy*s];
 const ring=h/3,pts=[p(0,0),p(r,ring),p(lean,h),p(-r,ring)];svg.insertAdjacentHTML('beforeend','<rect x="'+(x-30*s)+'" y="'+y0+'" width="'+(60*s)+'" height="'+(120*s*0.45)+'" fill="#efe3c0"/><polygon points="'+pts.map(q=>q.join(',')).join(' ')+'" fill="'+col+'" fill-opacity=".9" stroke="'+col+'"/>'
 +'<text x="'+x+'" y="'+(y0+120*s*0.45+22)+'" fill="#9aa6b6" font-size="13" text-anchor="middle">'+label+'</text>')}
(function(){const s=document.getElementById('poses');pose(s,75,75,22,0,'#ffcf6e','today');pose(s,200,90,20,14,GOLD,'shape 1');pose(s,325,60,24,-10,BLUE,'shape 2');
 s.insertAdjacentHTML('beforeend','<line x1="20" y1="300" x2="378" y2="300" stroke="#2c3644"/><text x="20" y="22" fill="#9aa6b6" font-size="13">flame and stick to one scale (a stick is 120 mm; its top is drawn)</text>')})();
(function(){const s=document.getElementById('tree'),sc=84,ox=430,oy=345;const X=x=>ox+x*sc,Y=z=>oy-z*sc;
 let d='<polygon points="'+[[0,0]].concat(Array.from({length:21},(_,i)=>{const f=i/20;return [cd(f),f*3.755]})).map(q=>X(q[0])+','+Y(q[1])).join(' ')+' '+Array.from({length:21},(_,i)=>{const f=1-i/20;return X(-cd(f))+','+Y(f*3.755)}).join(' ')+'" fill="#1f4a35" stroke="#2f6a4d"/>';
 s.insertAdjacentHTML('beforeend',d);
 T.forEach(c=>{const col=c.group?BLUE:GOLD;s.insertAdjacentHTML('beforeend','<rect x="'+(X(c.x)-4)+'" y="'+Y(c.z+.12*2.5)+'" width="8" height="'+(.12*2.5*sc)+'" fill="#efe3c0"/><polygon points="'+[X(c.x),Y(c.z+.3),X(c.x)+5,Y(c.z+.3+.075*2.5/3),X(c.x),Y(c.z+.3+.075*2.5),X(c.x)-5,Y(c.z+.3+.075*2.5/3)].join(' ')+'" fill="'+col+'"/>')});
 function cd(f){const R=[1.02,.979,.87,.835,.72,.55,.528,.421,.297,.02];const x=Math.min(Math.max(f,0),1)*10,lo=Math.min(Math.floor(x),9),hi=Math.min(lo+1,9);return R[lo]+(R[hi]-R[lo])*(x-lo)}
 s.insertAdjacentHTML('beforeend','<text x="20" y="28" fill="#9aa6b6" font-size="13">sticks and flames drawn 2.5 times their size; the groups sit on opposite sides</text>')})();
</script></body></html>"""

SCHED_HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=1440"><title>Mockup: flicker schedule</title><style>__CSS__</style></head><body><div class="wrap">
<h1>The flicker rule, run live</h1>
<p class="sub">Each of the 24 groups (12 trees x 2) flips between shape 1 and shape 2 when <code>sin(2&pi;(2.3 t + p)) + sin(2&pi;(3.7 t + 2p)) &gt; 0</code>, with its own phase <code>p</code>. Gold = shape 1, blue = shape 2. The ruler is the 30 fps frame the Chromecast shows.</p>
<div class="card"><canvas id="c" width="1370" height="372" style="width:100%"></canvas>
<div style="margin-top:8px"><button id="pp">Pause</button>&nbsp; <label>speed <input id="sp" type="range" min="0" max="2" step="0.05" value="1"></label>&nbsp;&nbsp;<label>frame rate <select id="fr"><option>30</option><option>60</option><option>15</option></select> fps</label>
&nbsp;&nbsp;<span id="info" style="color:var(--mut)"></span></div></div>
<div class="grid" style="grid-template-columns:1fr 1fr 1fr;margin-top:16px">
<div class="card"><h2>One tree, three frames 100 ms apart</h2><canvas id="f" width="400" height="200" style="width:100%"></canvas><p class="sub" style="margin:4px 0 0">the same ten candles, flames drawn 3 times their size; the two sides do not move together</p></div>
<div class="card"><h2>How big a flame is on the screen (1080p, 60&deg; view)</h2><canvas id="px" width="400" height="200" style="width:100%"></canvas><p class="sub" style="margin:4px 0 0" id="pxn"></p></div>
<div class="card"><h2>What the numbers say</h2><table id="st"></table></div></div></div>
<script>
const F1=2.3,F2=3.7,PHI=0.618034,N=12,STILL=location.hash==='#still';
const ph=(i,g)=>((2*i+g)*PHI)%1,shp=(t,i,g)=>{const p=ph(i,g);return Math.sin(6.283185*(F1*t+p))+Math.sin(6.283185*(F2*t+2*p))>0?1:2};
const c=document.getElementById('c'),x=c.getContext('2d'),W=c.width,H=c.height,SPAN=4,L=60,GOLD='#ffb454',BLUE='#5cc8ff';
let t0=STILL?0:null,t=STILL?0.0:0,run=!STILL,speed=1,fps=30;
function draw(now){x.clearRect(0,0,W,H);x.font='12px ui-sans-serif';x.fillStyle='#9aa6b6';const rows=24,rh=(H-26)/rows;
 for(let r=0;r<rows;r++){const i=r>>1,g=r&1,y=r*rh+4;x.fillStyle='#9aa6b6';if(!g)x.fillText('tree '+(i+1),4,y+rh*1.1);
  for(let px=0;px<W-L;px++){const tt=t+px/(W-L)*SPAN-SPAN;const q=Math.floor(tt*fps)/fps;x.fillStyle=shp(q,i,g)==1?GOLD:BLUE;x.globalAlpha=g?.78:1;x.fillRect(L+px,y,1,rh-1.5)}}
 x.globalAlpha=1;x.fillStyle='#e8ecf2';x.fillRect(W-1,0,1,H-22);for(let k=0;k<=SPAN*4;k++){const px=L+(W-L)*k/(SPAN*4);x.fillStyle='#2c3644';x.fillRect(px,H-22,1,6);}
 x.fillStyle='#9aa6b6';x.fillText('now',W-26,H-4);x.fillText('-'+SPAN+' s',L,H-4);
 // frames
 const f=document.getElementById('f').getContext('2d');f.clearRect(0,0,400,200);[0,1,2].forEach(k=>{drawTree(f,20+k*128,t-0.2+k*0.1)});
 const p=document.getElementById('px').getContext('2d');p.clearRect(0,0,400,200);
 [[6.3,'6.3 m'],[16,'16 m']].forEach((d,k)=>{const ppm=1080/(2*d[0]*Math.tan(Math.PI/6)),Z=3,hh=.075*ppm*Z,ww=.044*ppm*Z,x0=110+k*190;p.fillStyle='#ffcf6e';p.beginPath();p.moveTo(x0,118);p.lineTo(x0+ww/2,118-hh/3);p.lineTo(x0,118-hh);p.lineTo(x0-ww/2,118-hh/3);p.fill();
  p.fillStyle='#efe3c0';p.fillRect(x0-.03*ppm*Z,118,.06*ppm*Z,.12*ppm*Z);p.fillStyle='#9aa6b6';p.fillText('at '+d[1]+': '+(hh/Z).toFixed(0)+' x '+(ww/Z).toFixed(0)+' px on screen',x0-62,196);});
 document.getElementById('pxn').textContent='drawn at 3x: a flame is 11 px tall at the nearest orbit (6.3 m) and 4 px at the farthest (16 m).';
 let fl=0,tt=t-1;for(let q=0;q<1*fps;q++){}
 document.getElementById('info').textContent='t = '+t.toFixed(2)+' s';}
function drawTree(f,ox,tt){const T=__TREE__;const sc=46,oy=198,q=Math.floor(tt*fps)/fps,E=3;
 const R=[1.02,.979,.87,.835,.72,.55,.528,.421,.297,.02],rad=fr=>{const x=Math.min(Math.max(fr,0),1)*10,lo=Math.min(Math.floor(x),9),hi=Math.min(lo+1,9);return R[lo]+(R[hi]-R[lo])*(x-lo)};
 f.fillStyle='#1f4a35';f.beginPath();f.moveTo(ox+60,oy);for(let k=0;k<=20;k++){const fr=k/20;f.lineTo(ox+60+rad(fr)*sc*.55,oy-fr*3.755*sc*.5)}for(let k=20;k>=0;k--){const fr=k/20;f.lineTo(ox+60-rad(fr)*sc*.55,oy-fr*3.755*sc*.5)}f.fill();
 T.forEach(cn=>{const s=shp(q,0,cn.group),col=s==1?GOLD:BLUE,cx=ox+60+cn.x*sc*.55,cy=oy-cn.z*sc*.5,h=(s==1?.09:.06)*sc*E,lean=(s==1?.014:-.010)*sc*E;
  f.fillStyle='#efe3c0';f.fillRect(cx-1.5,cy-.12*sc*E*.7,3,.12*sc*E*.7);f.fillStyle=col;f.beginPath();f.moveTo(cx,cy-.12*sc*E*.7);f.lineTo(cx+3,cy-.12*sc*E*.7-h/3);f.lineTo(cx+lean,cy-.12*sc*E*.7-h);f.lineTo(cx-3,cy-.12*sc*E*.7-h/3);f.fill()})}
// the table
(function(){const tb=document.getElementById('st');tb.innerHTML='<tr><th>Per group</th><th></th></tr><tr><td>changes a second</td><td>__CPS__</td></tr><tr><td>mean time between changes</td><td>__MS__ ms</td></tr><tr><td>frames between changes at 30 fps</td><td>about __FR__</td></tr><tr><td>groups in step with another</td><td>none: 24 different phases</td></tr><tr><td>pattern repeats every</td><td>60 s (whole cycles)</td></tr>'})();
let last=null;function loop(now){if(last===null)last=now;const dt=(now-last)/1000;last=now;if(run)t+=dt*speed;draw();if(!STILL)requestAnimationFrame(loop)}
document.getElementById('pp').onclick=e=>{run=!run;e.target.textContent=run?'Pause':'Play'};document.getElementById('sp').oninput=e=>speed=+e.target.value;document.getElementById('fr').onchange=e=>{fps=+e.target.value};
if(STILL){t=3.1;draw()}else requestAnimationFrame(loop);
</script></body></html>"""


def main(argv):
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__)
        return 0
    out = argv[0] if argv else os.path.join(HERE, "..", "docs/plans/2026-11-22-cuckoo-village-candle-flicker")
    os.makedirs(out, exist_ok=True)
    st = stats()
    tree = json.dumps(pine_candles())
    fr = round(1000 / st["mean_ms_between"] * 0 + st["mean_ms_between"] / (1000 / 30), 1)
    shapes = SHAPES_HTML.replace("__CSS__", CSS).replace("__TREE__", tree)
    sched = (SCHED_HTML.replace("__CSS__", CSS).replace("__TREE__", tree).replace("__CPS__", str(st["changes_per_second_per_group"]))
             .replace("__MS__", str(st["mean_ms_between"])).replace("__FR__", str(fr)))
    for name, html in (("flame-shapes", shapes), ("flicker-schedule", sched)):
        path = os.path.abspath(os.path.join(out, name + ".html"))
        open(path, "w").write(html)
        subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--window-size=1440,900",
                        f"--screenshot={os.path.splitext(path)[0]}.png", f"file://{path}#still"], check=True, capture_output=True)
    print(json.dumps(dict(stats=st, frames_between_changes_at_30fps=fr, px_tall_6m3=round(1080 / (2 * 6.3 * math.tan(math.pi / 6)) * .075, 1),
                          px_tall_16m=round(1080 / (2 * 16 * math.tan(math.pi / 6)) * .075, 1))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
