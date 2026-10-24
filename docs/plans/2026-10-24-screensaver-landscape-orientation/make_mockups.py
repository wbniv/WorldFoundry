#!/usr/bin/env python3
"""Build this plan's two self-contained mockups (HTML + PNG).

Usage: python3 make_mockups.py            # writes beside this file
Each page is inline CSS/JS with inline SVG only (under 512 KB), designed to a 1440 x 900 canvas.
  tray-orientation   the coordinator tray's Settings pane, Orientation choice in four states
  dream-orientation  the Dream on a portrait-held phone: follow-device, landscape, sensor-landscape
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent

STYLE = """
:root{--bg:#ffffff;--fg:#1f2328;--muted:#656d76;--line:#d1d9e0;--panel:#f6f8fa;--accent:#0969da;--ok:#1a7f4b;--warn:#9a6700;--bad:#cf222e;--field:#ffffff;--okbg:#dafbe1;--warnbg:#fff8c5;--badbg:#ffebe9}
@media (prefers-color-scheme: dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--line:#30363d;--panel:#161b22;--accent:#4493f8;--ok:#5fcf8a;--warn:#f0b34a;--bad:#ff7b72;--field:#0d1117;--okbg:#12261a;--warnbg:#2b2210;--badbg:#2d1517}}
*{box-sizing:border-box}
body{margin:0;width:1440px;height:900px;overflow:hidden;background:var(--bg);color:var(--fg);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
header{display:flex;align-items:center;gap:12px;padding:14px 24px;border-bottom:1px solid var(--line);background:var(--panel)}
header h1{margin:0;font-size:16px;font-weight:600}
header .tag{margin-left:auto;font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em;color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:2px 8px}
code{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
.muted{color:var(--muted)}.nb{white-space:nowrap}
"""


def page(title: str, body: str, css: str = "", js: str = "") -> str:
    script = f"<script>{js}</script>" if js else ""
    return ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<title>Mockup — {title}</title><style>{STYLE}{css}</style></head><body>'
            f'<header><h1>{title}</h1><span class="tag">MOCKUP — NOT SHIPPED</span></header>'
            f'{body}{script}</body></html>\n')


# --------------------------------------------------------------------------- tray

TRAY_CSS = """
.bar{display:flex;align-items:center;gap:8px;padding:10px 24px}
.bar b{font-size:13px;color:var(--muted);margin-right:4px}
.bar button{font:inherit;font-size:13px;background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:3px 12px;cursor:pointer}
.bar button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.bar .hint{margin-left:auto;font-size:12px;color:var(--muted)}
.win{margin:0 24px;border:1px solid var(--line);border-radius:8px;background:var(--panel);overflow:hidden;height:660px;display:flex;flex-direction:column}
.title{display:flex;align-items:center;gap:10px;padding:7px 12px;background:var(--bg);border-bottom:1px solid var(--line);font-size:13px;font-weight:600}
.title .ctl{margin-left:auto;letter-spacing:10px;color:var(--muted);font-weight:400}
.tabs{display:flex;gap:2px;padding:8px 12px 0;border-bottom:1px solid var(--line)}
.tabs span{padding:5px 16px;font-size:13px;border:1px solid transparent;border-bottom:0;border-radius:6px 6px 0 0;color:var(--muted)}
.tabs span.on{background:var(--bg);border-color:var(--line);color:var(--fg);margin-bottom:-1px;padding-bottom:6px}
.tabs .dev{margin-left:auto;font-size:12px;color:var(--muted);padding-top:7px}
.cols{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:16px;flex:1;min-height:0}
.pane{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:14px 16px;display:flex;flex-direction:column;min-height:0}
.pane h2{margin:0;font-size:16px;font-weight:600}
.pane .pkg{margin:0 0 8px;font:11px ui-monospace,monospace;color:var(--muted)}
fieldset{border:1px solid var(--line);border-radius:6px;margin:6px 0 4px;padding:8px 12px 10px;min-width:0}
legend{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);padding:0 6px}
legend em{font-style:normal;text-transform:none;letter-spacing:0;font-weight:400}
.row{display:grid;grid-template-columns:104px 1fr;gap:8px;align-items:center;margin:6px 0}
.row label{font-size:13px}
.fld{border:1px solid var(--line);background:var(--field);border-radius:4px;padding:3px 8px;font-size:13px;min-height:26px;display:flex;justify-content:space-between;align-items:center}
.fld .ph{color:var(--muted)}
.seg{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--line);border-radius:6px;overflow:hidden;margin-top:2px}
.seg button{all:unset;cursor:pointer;text-align:center;padding:5px 4px 6px;font-size:13px;line-height:1.25;background:var(--field);border-left:1px solid var(--line)}
.seg button:first-child{border-left:0}
.seg button small{display:block;font-size:11px;color:var(--muted)}
.seg button[aria-checked="true"]{background:var(--accent);color:#fff}
.seg button[aria-checked="true"] small{color:#e6f0ff}
.seg button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.map{margin:6px 0 0;color:var(--muted)}
.status{margin-top:8px;border-radius:6px;padding:6px 10px;font-size:13px;min-height:58px;border:1px solid transparent}
.status.none{border-color:var(--line);color:var(--muted)}
.status.unsaved{background:var(--warnbg);color:var(--warn);border-color:var(--warn)}
.status.saved{background:var(--okbg);color:var(--ok);border-color:var(--ok)}
.status.error{background:var(--badbg);color:var(--bad);border-color:var(--bad)}
.btns{display:flex;gap:8px;margin-top:8px}
.btns button{font:inherit;font-size:13px;background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:3px 16px;cursor:pointer}
.btns button.pri{background:var(--accent);border-color:var(--accent);color:#fff}
.btns button:disabled{opacity:.45;cursor:default}
.none-lv{font-size:13px;color:var(--muted);margin:6px 0}
"""

# Everything below the markup is data-driven: three panes, each {saved, sel, status, attempted}.
TRAY_JS = r"""
const OPTS=[
 {v:'landscape',name:'Landscape',sub:'default',c:'SCREEN_ORIENTATION_LANDSCAPE'},
 {v:'sensor-landscape',name:'Sensor landscape',sub:'flips at 180°',c:'SCREEN_ORIENTATION_SENSOR_LANDSCAPE'},
 {v:'follow-device',name:'Follow device',sub:'today’s behaviour',c:'SCREEN_ORIENTATION_UNSPECIFIED'}];
const NAMES={landscape:'Landscape','sensor-landscape':'Sensor landscape','follow-device':'Follow device'};
const APPS=[
 {id:'seahorse',name:'Seahorse Grid',pkg:'org.worldfoundry.seahorsegrid',level:'<p class="none-lv">No level properties.</p>'},
 {id:'aquarium',name:'Aquarium',pkg:'org.worldfoundry.screensaver',
  level:'<div class="row"><label>Tank</label><div class="fld">Default tank <span class="muted">▾</span></div></div>'},
 {id:'planted',name:'Planted Tank',pkg:'org.worldfoundry.plantedtank',
  level:'<div class="row"><label>Water type</label><div class="fld">Random <span class="muted">▾</span></div></div>'+
        '<div class="row"><label>Seed</label><div class="fld"><span class="ph">blank = random each tank</span></div></div>'+
        '<div class="row"><label>Growth speed</label><div class="fld">1× <span class="muted">▾</span></div></div>'+
        '<div class="row"><label>Hold seconds</label><div class="fld">120</div></div>'}];
const CHANGED={seahorse:'sensor-landscape',aquarium:'follow-device',planted:'sensor-landscape'};
const mk=(saved,sel,status,attempted)=>({saved,sel,status,attempted});
const PRESETS={
 'default':()=>({seahorse:mk('landscape','landscape','none'),aquarium:mk('landscape','landscape','none'),planted:mk('landscape','landscape','none')}),
 'changed':()=>({seahorse:mk('landscape',CHANGED.seahorse,'unsaved'),aquarium:mk('landscape',CHANGED.aquarium,'unsaved'),planted:mk('landscape',CHANGED.planted,'unsaved')}),
 'saved':()=>({seahorse:mk(CHANGED.seahorse,CHANGED.seahorse,'saved'),aquarium:mk(CHANGED.aquarium,CHANGED.aquarium,'saved'),planted:mk(CHANGED.planted,CHANGED.planted,'saved')}),
 'error':()=>({seahorse:mk('landscape','landscape','none'),aquarium:mk('landscape','landscape','none'),planted:mk('landscape','landscape','error','sensor-landscape')})};
let S=PRESETS['default']();
const $=i=>document.getElementById(i);
function msg(st){
 if(st.status==='unsaved')return '● Unsaved change: '+NAMES[st.sel]+'. Apply sends it to the device.';
 if(st.status==='saved')return '✓ Saved — takes effect the next time the screensaver starts';
 if(st.status==='error')return '✗ The provider rejected “'+st.attempted+'” (this build has no orientation setting). Value unchanged: '+NAMES[st.saved]+'.';
 return 'Saved value: '+NAMES[st.saved]+'. Pick another to change it.';}
function draw(){
 APPS.forEach(a=>{const st=S[a.id],o=OPTS.find(x=>x.v===st.sel);
  $(a.id+'-seg').innerHTML=OPTS.map(x=>'<button type="button" role="radio" aria-checked="'+(x.v===st.sel)+'" data-app="'+a.id+'" data-v="'+x.v+'">'+x.name+'<small>'+x.sub+'</small></button>').join('');
  $(a.id+'-map').textContent='orientation:'+st.sel+' → '+o.c;
  const s=$(a.id+'-st');s.className='status '+st.status;s.textContent=msg(st);
  $(a.id+'-apply').disabled=st.sel===st.saved;$(a.id+'-revert').disabled=st.sel===st.saved;});
 document.querySelectorAll('.bar button[data-state]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.state===cur));}
let cur='default';
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.state){cur=b.dataset.state;S=PRESETS[cur]();draw();return}
 if(b.dataset.v){const st=S[b.dataset.app];st.sel=b.dataset.v;st.status=st.sel===st.saved?'none':'unsaved';draw();return}
 if(b.dataset.act){const st=S[b.dataset.app];
  if(b.dataset.act==='apply'){st.saved=st.sel;st.status='saved'}else{st.sel=st.saved;st.status='none'}draw()}});
draw();
"""


def tray() -> str:
    apps = [("seahorse", "Seahorse Grid", "org.worldfoundry.seahorsegrid", "No level properties."),
            ("aquarium", "Aquarium", "org.worldfoundry.screensaver", ""),
            ("planted", "Planted Tank", "org.worldfoundry.plantedtank", "")]
    panes = ""
    for aid, name, pkg, _ in apps:
        panes += f"""<section class="pane">
 <h2>{name}</h2><p class="pkg">{pkg}</p>
 <fieldset><legend>App <em>&mdash; whole screensaver</em></legend>
  <div class="row" style="grid-template-columns:1fr"><label id="{aid}-lbl"><b>Orientation</b></label>
   <div class="seg" id="{aid}-seg" role="radiogroup" aria-labelledby="{aid}-lbl"></div></div>
  <div class="map"><code id="{aid}-map"></code></div>
 </fieldset>
 <fieldset><legend>Level <em>&mdash; existing fields</em></legend><div id="{aid}-lv"></div></fieldset>
 <div class="status none" id="{aid}-st"></div>
 <div class="btns"><button type="button" class="pri" id="{aid}-apply" data-app="{aid}" data-act="apply">Apply</button>
  <button type="button" id="{aid}-revert" data-app="{aid}" data-act="revert">Revert</button></div>
</section>"""
    body = f"""<div class="bar"><b>State</b>
 <button type="button" data-state="default" aria-pressed="true">Default</button>
 <button type="button" data-state="changed" aria-pressed="false">Changed, unsaved</button>
 <button type="button" data-state="saved" aria-pressed="false">Saved</button>
 <button type="button" data-state="error" aria-pressed="false">Error</button>
 <span class="hint">Click an orientation to change it; Apply and Revert work too.</span></div>
<div class="win">
 <div class="title">World Foundry Coordinator &mdash; Settings<span class="ctl">&minus;&#9633;&times;</span></div>
 <div class="tabs"><span>Devices</span><span class="on">Screensavers</span><span>Jobs</span><span class="dev">Target: Pixel&nbsp;8&nbsp;Pro</span></div>
 <div class="cols">{panes}</div>
</div>"""
    js = TRAY_JS + "\n" + """
document.getElementById('seahorse-lv').innerHTML=APPS[0].level;
document.getElementById('aquarium-lv').innerHTML=APPS[1].level;
document.getElementById('planted-lv').innerHTML=APPS[2].level;
"""
    return page("Coordinator tray — screensaver Orientation setting", body, TRAY_CSS, js)


# --------------------------------------------------------------------------- dream

DREAM_CSS = """
.stage{display:grid;grid-template-columns:240px 520px 520px;gap:50px;justify-content:center;padding:18px 24px 0}
.col{display:flex;flex-direction:column;align-items:center}
.well{height:540px;width:100%;display:flex;align-items:center;justify-content:center;position:relative}
.phone{background:#111;border-radius:30px;padding:8px;box-shadow:0 6px 18px rgba(0,0,0,.35);position:relative;border:2px solid #2b2f36}
.phone .scr{width:100%;height:100%;border-radius:23px;overflow:hidden;background:#000;position:relative}
.phone.p{width:240px;height:520px}.phone.l{width:520px;height:240px}
.cam{position:absolute;width:9px;height:9px;border-radius:50%;background:#000;border:1px solid #333;z-index:2}
.p .cam{top:9px;left:50%;margin-left:-5px}.l .cam{left:9px;top:50%;margin-top:-5px}
.strip{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);aspect-ratio:16/9}
.strip svg,.fill svg{display:block;width:100%;height:100%}
.fill{position:absolute;inset:0}
.edge{position:absolute;left:0;right:0;text-align:center;font:600 10px ui-monospace,monospace;color:#8b949e;z-index:2}
.cap{margin-top:12px;text-align:center;max-width:520px}
.cap h3{margin:0;font-size:16px}
.cap p{margin:2px 0 0;font-size:13px;color:var(--muted)}
.cap code{color:var(--fg)}
.arrow{position:absolute;left:0;top:0;width:100%;height:150px;pointer-events:none}
.arrow text{fill:var(--accent);font:600 12px ui-sans-serif,system-ui,sans-serif}
.note{margin:14px auto 0;width:1392px;border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:6px;background:var(--panel);padding:10px 16px;font-size:14px}
.note b{display:block;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:2px}
.legend{margin:4px auto 0;width:1392px;font-size:12px;color:var(--muted);text-align:center}
"""


def scene(p: str) -> str:
    """The wide aquarium scene as inline SVG, 16:9 viewBox. `p` keeps gradient ids unique per copy."""
    return f"""<svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
<defs>
 <linearGradient id="{p}w" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2fa3c7"/><stop offset=".55" stop-color="#16688f"/><stop offset="1" stop-color="#0a3555"/></linearGradient>
 <linearGradient id="{p}r" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
 <linearGradient id="{p}s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d8c58e"/><stop offset="1" stop-color="#9b8554"/></linearGradient>
</defs>
<rect width="160" height="90" fill="url(#{p}w)"/>
<polygon points="30,0 44,0 70,90 40,90" fill="url(#{p}r)"/><polygon points="92,0 102,0 128,90 108,90" fill="url(#{p}r)"/>
<path d="M0 78 Q30 72 60 77 T120 76 T160 74 V90 H0Z" fill="url(#{p}s)"/>
<g fill="none" stroke-linecap="round">
 <path d="M18 80 C14 66 24 58 18 44" stroke="#2f8f4a" stroke-width="3"/><path d="M24 80 C28 68 20 60 27 50" stroke="#3aa75a" stroke-width="2.4"/>
 <path d="M70 79 C66 68 74 62 69 52" stroke="#2f8f4a" stroke-width="2.6"/>
 <path d="M126 78 C122 62 132 56 126 40" stroke="#3aa75a" stroke-width="3"/><path d="M134 78 C138 66 130 60 136 52" stroke="#2f8f4a" stroke-width="2.4"/>
 <path d="M146 77 C143 68 150 64 146 56" stroke="#3aa75a" stroke-width="2.2"/></g>
<g fill="#0b2233"><ellipse cx="92" cy="38" rx="11" ry="5"/><polygon points="102,38 111,31 111,45"/><polygon points="88,33 94,28 96,34"/><circle cx="85" cy="36.5" r="1" fill="#cfe9f5"/></g>
<g fill="#0b2233" opacity=".75"><ellipse cx="46" cy="24" rx="6" ry="2.8"/><polygon points="52,24 57,20 57,28"/></g>
<g fill="none" stroke="#cfe9f5" stroke-opacity=".55" stroke-width=".7"><circle cx="40" cy="60" r="1.4"/><circle cx="42" cy="52" r="1"/><circle cx="39" cy="45" r="1.7"/><circle cx="108" cy="58" r="1.2"/><circle cx="110" cy="50" r="1"/></g>
</svg>"""


def phone_portrait(p: str) -> str:
    return (f'<div class="phone p"><span class="cam"></span><div class="scr">'
            f'<div class="edge" style="top:60px">black</div><div class="strip">{scene(p)}</div>'
            f'<div class="edge" style="bottom:60px">black</div></div></div>')


def phone_landscape(p: str) -> str:
    return (f'<div class="phone l"><span class="cam"></span><div class="scr"><div class="fill">{scene(p)}</div></div></div>')


def dream() -> str:
    flip = """<svg class="arrow" viewBox="0 0 520 150" aria-hidden="true">
 <defs><marker id="ah" markerWidth="8" markerHeight="8" refX="5" refY="4" orient="auto-start-reverse"><path d="M0 0L8 4L0 8Z" fill="var(--accent)"/></marker></defs>
 <path d="M150 108 C190 22 330 22 370 108" fill="none" stroke="var(--accent)" stroke-width="3" marker-start="url(#ah)" marker-end="url(#ah)"/>
 <text x="260" y="26" text-anchor="middle">turn the device 180°: the picture flips with it</text></svg>"""
    body = f"""<div class="stage">
 <div class="col"><div class="well">{phone_portrait('a')}</div>
  <div class="cap"><h3>A &mdash; Follow device (today)</h3><p>Portrait-held phone: the 16:9 scene is a strip in the middle of a black screen. Stays available as <code>follow-device</code>.</p></div></div>
 <div class="col"><div class="well">{phone_landscape('b')}</div>
  <div class="cap"><h3>B &mdash; Landscape (new default)</h3><p>The Dream asks for landscape; the phone shows the scene full screen, even though it is held upright. <code>landscape</code>.</p></div></div>
 <div class="col"><div class="well">{flip}{phone_landscape('c')}</div>
  <div class="cap"><h3>C &mdash; Sensor landscape</h3><p>Like B, but follows the sensor between the two landscape directions, so the scene is never upside down. <code>sensor-landscape</code>.</p></div></div>
</div>
<div class="note"><b>How the request is made</b>Android&nbsp;11 and later: DreamActivity.setRequestedOrientation. Android&nbsp;10 and earlier: TYPE_DREAM window attribute (source-checked only).</div>
<div class="legend">Pixel-class phones, drawn to the same scale. The Chromecast TVs are always landscape and look the same in A, B and C.</div>"""
    return page("Dream on a portrait-held phone — orientation choices", body, DREAM_CSS)


def main() -> None:
    pages = {"tray-orientation": tray(), "dream-orientation": dream()}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        for name, html in pages.items():
            (HERE / f"{name}.html").write_text(html, encoding="utf-8")
            tab = browser.new_page(viewport={"width": 1440, "height": 900})
            tab.goto((HERE / f"{name}.html").as_uri())
            tab.screenshot(path=str(HERE / f"{name}.png"))
            tab.close()
            print(f"{name}: {len(html) / 1024:.1f} KiB html")
        browser.close()


if __name__ == "__main__":
    main()
