#!/usr/bin/env python3
"""Build this plan's three self-contained mockups (HTML + PNG) from make_art.py's previews.

Usage: python3 make_mockups.py            # writes beside this file
Each page is inline CSS/JS with data-URI images (under 512 KB), designed to a 1440 x 900 canvas.
"""
from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent

STYLE = """
:root{--bg:#0b1220;--panel:#111a2c;--line:#25324b;--fg:#e6edf3;--muted:#93a1b8;--accent:#4fb3d9;--ok:#5fcf8a;--warn:#f0b34a;--bad:#ff7b72}
@media (prefers-color-scheme: light){:root{--bg:#f4f7fb;--panel:#fff;--line:#d1d9e0;--fg:#1f2328;--muted:#5b6675;--accent:#0b6e99;--ok:#1a7f4b;--warn:#9a6700;--bad:#cf222e}}
*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;overflow:hidden;background:var(--bg);color:var(--fg);font:15px/1.5 ui-sans-serif,system-ui,"Segoe UI",sans-serif}
header{display:flex;align-items:center;gap:12px;padding:14px 28px;border-bottom:1px solid var(--line);background:var(--panel)}
header h1{margin:0;font-size:17px;font-weight:600}header .tag{margin-left:auto;font:600 11px ui-monospace,monospace;letter-spacing:.05em;color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:2px 9px}
main{padding:24px 28px}h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 10px;font-weight:600}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
code,pre{font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
.muted{color:var(--muted)}.nb{white-space:nowrap}
"""


def uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def page(title: str, body: str, script: str = "", extra_style: str = "") -> str:
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><title>Mockup — {title}</title>'
            f'<style>{STYLE}{extra_style}</style></head><body><header><h1>{title}</h1>'
            f'<span class="tag">MOCKUP — NOT SHIPPED</span></header>{body}<script>{script}</script></body></html>\n')


def lifecycle(art: Path) -> str:
    img = {n: uri(art / f"strip-{n}.jpg", "image/jpeg") for n in
           ("initial-seedlings", "freshwater-spreading", "freshwater-mature", "saltwater-mature")}
    body = f"""<main>
<div class="card" style="display:flex;gap:28px;align-items:center;margin-bottom:18px">
 <label>Growth speed <select id="speed"><option>0.25</option><option>0.5</option><option selected>1</option><option>2</option><option>4</option><option>8</option></select> ×</label>
 <label>Hold <input id="hold" type="number" value="120" min="0" max="86400" style="width:80px"> s</label>
 <label>Time into this tank <input id="t" type="range" min="0" max="100" value="0" style="width:420px"></label>
 <span id="now" style="margin-left:auto;font-weight:600"></span></div>
<h2>One tank, start to finish (the same loop repeats until the TV wakes)</h2>
<div id="film" style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px">
 <figure class="f"><img src="{img['initial-seedlings']}"><figcaption><b>Founders</b><span id="c0"></span><small>Seed and water drawn on entry. Plants are seedlings.</small></figcaption></figure>
 <figure class="f"><img src="{img['freshwater-spreading']}"><figcaption><b>Spreading</b><span id="c1"></span><small>Runners, daughter shoots, leaves unfurl.</small></figcaption></figure>
 <figure class="f"><img src="{img['freshwater-mature']}"><figcaption><b>Fully grown</b><span id="c2"></span><small>Growth clock reaches the maturity bound; hold starts.</small></figcaption></figure>
 <figure class="f"><img src="{img['saltwater-mature']}"><figcaption><b>Still on screen</b><span id="c3"></span><small>The plants keep swaying. Then the level ends and reloads: a new tank.</small></figcaption></figure>
</div>
<h2>Timeline (not to scale between speeds)</h2>
<div class="card"><div id="bar" style="display:flex;height:38px;border-radius:6px;overflow:hidden;border:1px solid var(--line);position:relative">
 <div id="g" style="background:linear-gradient(90deg,#2f6b3a,#5fcf8a);display:flex;align-items:center;padding-left:10px;color:#04210f;font-weight:600">Grow</div>
 <div id="h" style="background:#33507a;display:flex;align-items:center;padding-left:10px;font-weight:600">Hold</div>
 <div id="head" style="position:absolute;top:-4px;bottom:-4px;width:3px;background:var(--warn)"></div></div>
 <p id="sum" class="muted" style="margin:10px 0 0"></p></div>
<p class="muted" style="margin-top:14px">Growth time ≈ the slowest seed's finish time ÷ speed (measured worst case 195 s here; Phase 0 measures the real per-seed bound). Hold is wall-clock level time and does not scale with speed.</p>
</main>"""
    css = ".f{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}.f img{display:block;width:100%}.f figcaption{padding:10px 12px;display:grid;gap:2px}.f figcaption span{color:var(--accent);font:600 13px ui-monospace,monospace}.f small{color:var(--muted)}.f.on{outline:3px solid var(--warn)}select,input{font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:3px 6px}"
    js = """
const G=195,$=id=>document.getElementById(id),mmss=s=>Math.floor(s/60)+':'+String(Math.round(s%60)).padStart(2,'0');
function draw(){const sp=+$('speed').value,h=+$('hold').value||0,grow=G/sp,total=grow+h,p=+$('t').value/100,t=p*total;
 $('g').style.flex=grow;$('h').style.flex=Math.max(h,1);$('head').style.left=(p*100)+'%';
 const marks=[0,grow*.3,grow,grow+h];for(let i=0;i<4;i++)$('c'+i).textContent=mmss(marks[i]);
 const idx=t>=grow?(t>=total-1?3:2):(t>grow*.3?1:0);document.querySelectorAll('.f').forEach((f,i)=>f.classList.toggle('on',i===(t>=grow?(h>0?3:2):idx)));
 $('now').textContent=(t<grow?'Growing':'Holding')+' · '+mmss(t)+' of '+mmss(total);
 $('sum').textContent='Cycle: '+mmss(grow)+' grow + '+mmss(h)+' hold = '+mmss(total)+' per tank at '+sp+'×.';}
['speed','hold','t'].forEach(i=>$(i).addEventListener('input',draw));draw();"""
    return page("Planted Tank screensaver — one tank's life", body, js, css)


def icons(art: Path) -> str:
    b = {n: uri(art / f"banner{n}.jpg", "image/jpeg") for n in ("-aquarium", "-seahorse", "")}
    fg = {n: uri(art / f"icon-foreground{n}.png", "image/png") for n in ("-aquarium", "-seahorse", "")}
    leg = uri(art / "icon-legacy.png", "image/png")
    tiles = "".join(
        f'<button class="tile{" new" if key == "" else ""}" data-n="{name}"><img src="{b[key]}"><span>{name}</span>{"<em>NEW</em>" if key == "" else ""}</button>'
        for key, name in (("-aquarium", "Aquarium"), ("-seahorse", "Seahorse Grid"), ("", "Planted Tank")))
    masks = "".join(
        f'<div class="ic"><div class="mask {m}" style="background:#073C58"><img src="{fg[key]}"></div><small>{name}</small></div>'
        for key, name in (("-aquarium", "Aquarium"), ("-seahorse", "Seahorse"), ("", "Planted Tank")) for m in ("circle",))
    squares = "".join(
        f'<div class="ic"><div class="mask squircle" style="background:#073C58"><img src="{fg[key]}"></div><small>{name}</small></div>'
        for key, name in (("-aquarium", "Aquarium"), ("-seahorse", "Seahorse"), ("", "Planted Tank")))
    body = f"""<main style="display:grid;grid-template-columns:1060px 300px;gap:24px">
<div>
 <h2>Google TV “Apps” row — focus with ← →</h2>
 <div class="card" style="background:#0a0f19;border-color:#25324b"><div id="row" style="display:flex;gap:14px;padding:18px 6px 26px">{tiles}</div>
  <p class="muted" style="margin:0">Banners are 320 × 180 dp on screen. The World Foundry badge sits lower-right; the title lower-left.</p></div>
 <h2 style="margin-top:22px">Launcher icons — adaptive, circle and rounded-square masks</h2>
 <div class="card" style="display:flex;gap:30px;flex-wrap:wrap;align-items:flex-end">{masks}<div style="width:1px;background:var(--line);align-self:stretch"></div>{squares}
  <div class="ic"><img src="{leg}" style="width:96px;height:96px;border-radius:6px"><small>Legacy square (API&nbsp;20)</small></div></div>
</div>
<div class="card"><h2>What changes</h2>
 <ul style="padding-left:18px;margin:0 0 12px"><li>Third flavor <code>planted</code>, own app id and label.</li><li>Art: a real capture of the plants-only level (this mockup uses retained 2026‑10 device frames, which still show the urchin).</li><li>Badge: <code>add_logo(scale=.17, safe_circle=72/108)</code> on the foreground; <code>.26</code> legacy; same as the other two.</li><li>Banner: <code>gen-android-icons.banner()</code> with the name “Planted Tank”.</li></ul>
 <h2>States</h2><p class="muted" style="margin:0">Unfocused tile at 100 %; focused tile scales to 110 % with an outline. Dark and light launcher backgrounds both keep the badge on its white tile, so it never disappears.</p></div>
</main>"""
    css = """.tile{all:unset;cursor:pointer;position:relative;display:grid;gap:6px;width:320px;text-align:center;color:var(--fg);transition:transform .12s}.tile img{width:320px;height:180px;border-radius:8px;display:block;border:2px solid transparent}
.tile span{font-size:14px;color:#cbd5e1}.tile em{position:absolute;top:8px;left:8px;background:var(--warn);color:#111;font:700 11px ui-monospace,monospace;padding:1px 7px;border-radius:9px;font-style:normal}
.tile:focus img,.tile.f img{outline:4px solid #fff;transform:scale(1.0)}.tile.f{transform:scale(1.08)}
.ic{display:grid;gap:6px;justify-items:center}.ic small{color:var(--muted);font-size:12px}.mask{width:96px;height:96px;overflow:hidden;position:relative}.mask img{width:96px;height:96px;display:block}
.mask.circle{border-radius:50%}.mask.squircle{border-radius:28%}"""
    js = """const t=[...document.querySelectorAll('.tile')];let i=2;const f=()=>t.forEach((e,j)=>e.classList.toggle('f',j===i));f();
t.forEach((e,j)=>e.addEventListener('click',()=>{i=j;f()}));document.addEventListener('keydown',e=>{if(e.key==='ArrowRight')i=Math.min(2,i+1);if(e.key==='ArrowLeft')i=Math.max(0,i-1);f()});"""
    return page("Planted Tank screensaver — icon and TV banner", body, js, css)


def params() -> str:
    body = """<main style="display:grid;grid-template-columns:520px 1fr;gap:24px">
<div class="card"><h2>Parameters</h2><div style="display:flex;gap:8px;margin:-4px 0 12px"><button id="tv" type="button">Try: valid</button><button id="ti" type="button">Try: invalid seed</button></div>
 <div class="row"><label for="water">water</label><select id="water"><option>random</option><option>freshwater</option><option>saltwater</option></select><small>default random; each tank draws its own</small></div>
 <div class="row"><label for="seed">seed</label><input id="seed" placeholder="blank = random each tank" inputmode="numeric"><small>0 – 4294967295</small></div>
 <div class="row"><label for="speed">speed</label><select id="speed"><option>0.25</option><option>0.5</option><option selected>1</option><option>2</option><option>4</option><option>8</option></select><small>growth clock; 1× is the default</small></div>
 <div class="row"><label for="hold">hold</label><input id="hold" value="120"><small>seconds on screen once grown</small></div>
 <p id="err" style="margin:12px 0 0;min-height:44px"></p></div>
<div style="display:grid;gap:16px;align-content:start">
 <div class="card"><h2>Preview launch (activity extras)</h2><pre id="am"></pre></div>
 <div class="card"><h2>Persist for the Dream (settings provider, one call per key)</h2><pre id="cc"></pre></div>
 <div class="card"><h2>Coordinator tray choices</h2><div id="tray" class="muted"></div></div>
</div></main>"""
    css = """.row{display:grid;grid-template-columns:90px 1fr;gap:4px 12px;align-items:center;margin-bottom:10px}.row small{grid-column:2;color:var(--muted);margin-top:-2px}
input:not([type=checkbox]),select{font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:5px 8px;width:100%}input.bad{border-color:var(--bad)}
pre{margin:0;white-space:pre-wrap;word-break:break-all}button{font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer}.chk{display:flex;gap:8px;align-items:center}.ok{color:var(--ok)}.bad{color:var(--bad)}
.tr{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--line)}.tr b{color:var(--fg)}"""
    js = """
const $=i=>document.getElementById(i);const PKG='org.worldfoundry.plantedtank';
function intOk(v,lo,hi){return /^\\d{1,10}$/.test(v)&&+v>=lo&&+v<=hi}
function draw(){const e=[],w=$('water').value,seed=$('seed').value.trim(),hold=$('hold').value.trim();
 ['seed','hold'].forEach(i=>$(i).classList.remove('bad'));
 if(seed&&!intOk(seed,0,4294967295)){e.push('seed must be a whole number from 0 to 4294967295');$('seed').classList.add('bad')}
 if(!intOk(hold,0,86400)){e.push('hold must be 0 to 86400 seconds');$('hold').classList.add('bad')}
 const t=[['Water',w==='random'?'Random':w[0].toUpperCase()+w.slice(1)],['Speed',$('speed').value+'×'],['Seed',seed||'Random (CLI only)']];
 $('tray').innerHTML=t.map(r=>'<div class="tr"><span>'+r[0]+'</span><b>'+r[1]+'</b></div>').join('');
 if(e.length){$('err').innerHTML='<span class="bad">✗ '+e.join('<br>✗ ')+'</span><br><span class="muted">Nothing sent. Previous settings stay in force.</span>';$('am').textContent='(no command: fix the highlighted field)';$('cc').textContent='(no command)';return}
 $('err').innerHTML='<span class="ok">✓ valid</span> <span class="muted">· same checks run on the device, which rejects the call with the same message</span>';
 const kv=[['water',w],['speed',$('speed').value],['hold',hold]];if(seed)kv.push(['seed',seed]);
 const flag=([k,v])=>k==='seed'?'--el seed '+v:k==='speed'?'--ef speed '+v:k==='water'?'--es water '+v:'--ei '+k+' '+v;
 $('am').textContent='adb shell am start -n '+PKG+'/.PlantedTankActivity \\\\\\n  '+kv.map(flag).join(' \\\\\\n  ');
 $('cc').textContent=kv.map(([k,v])=>'adb shell content call --uri content://'+PKG+'.settings \\\\\\n  --method setSetting --arg '+k+':'+v).join('\\n');}
document.querySelectorAll('input,select').forEach(e=>e.addEventListener('input',draw));
$('tv').onclick=()=>{$('water').value='saltwater';$('seed').value='713';$('speed').value='2';draw()};
$('ti').onclick=()=>{$('water').value='freshwater';$('seed').value='4294967296';$('hold').value='-5';draw()};draw();"""
    return page("Planted Tank screensaver — parameters", body, js, css)


def main() -> None:
    art = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    if not (art / "banner.jpg").exists():
        subprocess.run([sys.executable, str(HERE / "make_art.py"), "--out", str(art)], check=True)
    pages = {"dream-lifecycle": lifecycle(art), "icon-and-banner": icons(art), "parameters": params()}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        for name, html in pages.items():
            (HERE / f"{name}.html").write_text(html)
            tab = browser.new_page(viewport={"width": 1440, "height": 900})
            tab.goto((HERE / f"{name}.html").as_uri())
            if name == "parameters":
                tab.click("#ti")  # the thumbnail shows the rejected-input state; the page opens on defaults
            tab.screenshot(path=str(HERE / f"{name}.png"))
            tab.close()
            print(f"{name}: {len(html) // 1024} KiB")
        browser.close()


if __name__ == "__main__":
    main()
