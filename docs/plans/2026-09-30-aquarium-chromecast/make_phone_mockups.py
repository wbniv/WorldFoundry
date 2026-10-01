#!/usr/bin/env python3
"""make_phone_mockups.py: build the three self-contained 1440x900 mockups for the "phone as a gamepad" phase of the
aquarium-on-Chromecast plan, and their PNGs.

Inline CSS/JS only; the QR code is a real QR (segno) of the example URL, inlined as SVG; the TV picture is the real Chromecast
screenshot from docs/porting-status/, embedded as a data URI so each .html stays under 512 KB.
Usage: python3 make_phone_mockups.py   (needs segno, Pillow and google-chrome)
"""
import base64, io, subprocess
from pathlib import Path
from PIL import Image
import segno

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
URL = "http://192.168.4.37:8765/?k=482913"          # the Chromecast's address from this setup; the PIN is an example


def data_uri(path, size, q=74):
    im = Image.open(path).convert("RGB").resize(size, Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=q)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


TV = data_uri(REPO / "docs/porting-status/chromecast-hd-aquarium.png", (960, 540))
CONDO = data_uri(REPO / "docs/porting-status/chromecast-hd-condo.png", (960, 540))
QR = segno.make(URL, error="m").svg_inline(scale=6, border=2, dark="#0d1117", light="#ffffff")

CSS = """
*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;background:#0d1117;color:#e6edf3;font:16px/1.4 system-ui,'Noto Sans',sans-serif;overflow:hidden}
h1{margin:0;font-size:22px;font-weight:650}.top{padding:22px 34px 10px;border-bottom:1px solid #263041;display:flex;justify-content:space-between;align-items:baseline}
.sub{color:#8b98a9;font-size:14px}.note{color:#ffb454;font-size:13px}.ok{color:#56d364}.bad{color:#ff7b72}.warn{color:#ffb454}
.pill{display:inline-block;border:1px solid #3a4a63;border-radius:999px;padding:2px 12px;font-size:13px;color:#9fb3cc}
"""


def page(title, sub, body, extra_css=""):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>{CSS}{extra_css}</style></head><body>
<div class="top"><h1>{title}</h1><div class="sub">{sub}</div></div>{body}</body></html>"""


# 1. the TV side: pairing overlay, then connected --------------------------------------------------------------
tv = page("Mockup 3: the TV, pairing the phone", "Chromecast HD, 1920×1080 shown at 640×360. The overlay is drawn by the engine, like the touch HUD.", f"""
<div style="display:flex;gap:34px;padding:22px 34px">
 <div><div class="sub" style="margin-bottom:6px">A. First launch: waiting for a phone</div>
  <div class="tv"><img src="{TV}"><div class="dim"></div>
   <div class="panel"><div class="ph">Use your phone as the controller</div>
    <div class="row"><div class="qr">{QR}</div>
     <div class="steps"><div>1. Join the <b>same Wi-Fi</b> as this TV</div><div>2. Scan the code, or open<br><code>192.168.4.37:8765</code></div><div>3. Enter PIN <b class="pin">482 913</b> if asked</div>
     <div class="wait"><span class="dot"></span> Waiting for a phone…</div></div></div>
    <div class="foot">The remote still works. Press <b>Back</b> to hide this.</div></div></div></div>
 <div><div class="sub" style="margin-bottom:6px">B. Phone connected, then the game</div>
  <div class="tv"><img src="{CONDO}"><div class="toast"><span class="dot g"></span> Phone connected</div></div>
  <div class="note" style="margin-top:8px;max-width:640px">The toast fades after 3 s. If the phone drops, the panel in A returns after 5 s and every button is released at once, so nothing sticks.</div>
  <table style="margin-top:14px"><tr><th>Shown on the TV</th><th>When</th></tr>
   <tr><td>URL, QR, PIN, "Waiting"</td><td>no phone connected</td></tr><tr><td>"Phone connected" toast</td><td>a phone joins (the newest wins)</td></tr>
   <tr><td>"Phone lost" + panel</td><td>no heartbeat for 1 s</td></tr><tr><td>nothing</td><td>a phone is connected</td></tr></table></div>
</div>""", """
.tv{position:relative;width:640px;height:360px;background:#000;border:1px solid #2b3a52;overflow:hidden}.tv img{width:100%;display:block}.dim{position:absolute;inset:0;background:#000a}
.panel{position:absolute;left:28px;top:30px;right:28px;bottom:30px;background:#111826ee;border:1px solid #3a4a63;border-radius:10px;padding:12px 16px}
.ph{font-size:22px;font-weight:650;margin-bottom:14px}.row{display:flex;gap:22px;align-items:center}.qr{width:168px;height:168px;background:#fff;padding:4px;border-radius:4px}.qr svg{width:100%;height:100%;display:block}
.steps{font-size:17px;color:#c9d4e3;line-height:1.55}code{background:#05080d;padding:1px 6px;border-radius:4px;color:#9fb3cc}.pin{color:#56d364;letter-spacing:.06em}
.wait{margin-top:6px;color:#ffb454}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#ffb454;margin-right:4px;animation:p 1.2s infinite}.dot.g{background:#56d364;animation:none}
@keyframes p{50%{opacity:.25}}.foot{position:absolute;left:20px;bottom:12px;font-size:13px;color:#8b98a9}
.toast{position:absolute;right:12px;top:12px;background:#000b;border:1px solid #56d364;color:#56d364;border-radius:999px;padding:4px 14px;font-size:15px}
table{border-collapse:collapse;font-size:14px;width:640px}th{text-align:left;color:#8b98a9;font-weight:500;padding:4px 10px 6px 0}td{padding:6px 10px 6px 0;border-bottom:1px solid #1d2635}""")

# 2. the phone controller (interactive) ----------------------------------------------------------------------------
JS = """
const state={};const out=document.getElementById('mask');
const bits={LEFT:1,RIGHT:2,UP:4,DOWN:8,A:16,B:32,C:64,D:128,E:256,F:512};
function render(){let m=0;for(const k in state)if(state[k])m|=bits[k];out.textContent='0x'+m.toString(16).padStart(4,'0')+'   '+(Object.keys(state).filter(k=>state[k]).join(' + ')||'(nothing held)');}
document.querySelectorAll('[data-b]').forEach(el=>{
  const k=el.dataset.b;
  el.addEventListener('pointerdown',e=>{state[k]=true;el.classList.add('on');el.setPointerCapture(e.pointerId);render();});
  const up=()=>{state[k]=false;el.classList.remove('on');render();};
  el.addEventListener('pointerup',up);el.addEventListener('pointercancel',up);
});
document.querySelectorAll('.stick').forEach(st=>{
  const knob=st.querySelector('.knob');
  function set(dx,dy){const r=70,d=Math.hypot(dx,dy)||1,s=Math.min(1,r/d);knob.style.transform=`translate(${dx*s}px,${dy*s}px)`;
    const t=28;state.LEFT=dx<-t;state.RIGHT=dx>t;state.UP=dy<-t;state.DOWN=dy>t;render();}
  st.addEventListener('pointerdown',e=>{st.setPointerCapture(e.pointerId);const b=st.getBoundingClientRect();st._c=[b.left+b.width/2,b.top+b.height/2];set(e.clientX-st._c[0],e.clientY-st._c[1]);});
  st.addEventListener('pointermove',e=>{if(st._c&&e.buttons)set(e.clientX-st._c[0],e.clientY-st._c[1]);});
  const end=()=>{st._c=null;knob.style.transform='translate(0,0)';state.LEFT=state.RIGHT=state.UP=state.DOWN=false;render();};
  st.addEventListener('pointerup',end);st.addEventListener('pointercancel',end);
});render();
"""


def phone(name, buttons, note):
    btns = "".join(f'<div class="btn {c}" data-b="{k}" style="left:{x}px;top:{y}px">{lab}</div>' for k, lab, x, y, c in buttons)
    return f"""<div><div class="sub" style="margin-bottom:6px">{name}</div>
 <div class="phone"><div class="screen"><div class="status"><span class="dot g"></span> Connected to the TV</div>
  <div class="stick" style="left:34px;top:92px"><div class="ring"></div><div class="knob"></div></div>{btns}</div></div>
 <div class="note" style="margin-top:8px;max-width:600px">{note}</div></div>"""


aq = phone("A. Aquarium: stick plus two buttons", [("A", "A", 500, 120, ""), ("B", "B", 420, 160, "")], "Steers the clownfish (A and B are free for later). The stick maps to the same four directions the D-pad does (threshold 28 px of 70), so it behaves exactly like the remote.")
condo = phone("B. Condo: stick plus the buttons the remote cannot reach",
              [("A", "hop", 520, 150, ""), ("B", "doors", 440, 98, ""), ("C", "teleport", 520, 46, ""), ("D", "orbit (hold)", 350, 150, "hold"), ("E", "zoom −", 262, 46, "small"), ("F", "zoom +", 262, 106, "small")],
              "Doors (B), the 639⇄640 teleport (C), orbit (hold D with the stick) and zoom (E/F) are exactly what a TV remote cannot do. This closes the condo plan's gamepad question without buying a gamepad.")
pad = page("Mockup 2: the phone as the controller (live: click and drag)", "Landscape phone page served by the Chromecast. Layout per app. Try the controls: the line below shows the button mask that would be sent.", f"""
<div style="padding:18px 34px"><div style="display:flex;gap:34px">{aq}{condo}</div>
<div class="mask"><span class="sub">sent to the TV on every change (and every 250 ms as a heartbeat):</span><br><code id="mask"></code></div></div>
<script>{JS}</script>""", """
.phone{width:640px;height:296px;background:#05080d;border:6px solid #2b3a52;border-radius:34px;position:relative;padding:8px}.screen{position:absolute;inset:8px;background:#111826;border-radius:26px;overflow:hidden;touch-action:none}
.status{position:absolute;left:20px;top:10px;font-size:12px;color:#8b98a9}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#56d364;margin-right:4px}
.stick{position:absolute;width:150px;height:150px;touch-action:none}.ring{position:absolute;inset:0;border-radius:50%;border:2px solid #3a4a63;background:#0d1320}.knob{position:absolute;left:45px;top:45px;width:60px;height:60px;border-radius:50%;background:#2f6fb3;box-shadow:0 0 0 2px #56a0e8 inset;transition:transform .04s}
.btn{position:absolute;width:62px;height:62px;border-radius:50%;background:#1d2a3f;border:2px solid #3a4a63;display:flex;align-items:center;justify-content:center;font-size:12px;text-align:center;user-select:none;touch-action:none;color:#c9d4e3}
.btn.small{width:52px;height:52px}.btn.on{background:#56d364;color:#0d1117;border-color:#56d364}
.mask{margin-top:16px}code{background:#05080d;padding:3px 10px;border-radius:4px;color:#56d364;font-size:15px;display:inline-block;margin-top:4px}""")

# 3. states -----------------------------------------------------------------------------------------------------------
def card(title, cls, body, shot):
    return f'<div class="c"><div class="s">{shot}</div><h3 class="{cls}">{title}</h3><p>{body}</p></div>'


states = page("Mockup 4: the states, including the failures a living room produces", "Phone screens and the TV panel, each with what the user sees and what the code does.", f"""
<div class="grid">
 {card("1 Connecting", "", "The page loaded; the WebSocket is opening. Buttons are shown but disabled.", '<div class="ph2"><span class="dot2"></span> Connecting…</div>')}
 {card("2 Connected", "ok", "Buttons live. The mask is sent on every change and as a heartbeat every 250 ms.", '<div class="ph2 g">● Connected to the TV</div>')}
 {card("3 Signal lost", "warn", "No reply for 1 s: buttons grey out and the phone retries every second. <b>The TV releases every button at once</b> (no stuck RIGHT).", '<div class="ph2 w">Reconnecting… <small>buttons off</small></div>')}
 {card("4 Wrong PIN", "bad", "The PIN in the URL does not match this launch's: HTTP 403 and a plain message. No game input accepted.", '<div class="ph2 r">Wrong code. Scan the TV again.</div>')}
 {card("5 Not on the same Wi-Fi", "bad", "Nothing answers within 5 s. The page says why: join the TV's network; a guest network or <i>AP isolation</i> blocks it.", '<div class="ph2 r">Can’t reach the TV.<br><small>Same Wi-Fi? Guest network?</small></div>')}
 {card("6 Phone locks or sleeps", "warn", "A screen Wake Lock is requested while connected. If the phone sleeps anyway, it is state 3 and the TV releases the buttons.", '<div class="ph2 w">Screen kept awake</div>')}
 {card("7 A second phone joins", "warn", "The newest connection wins; the first sees “Another phone took over”. Two players is a later feature.", '<div class="ph2 w">Another phone took over</div>')}
 {card("8 The remote at the same time", "ok", "Remote, a gamepad and the phone are OR-ed together, like the touch HUD and a gamepad already are. Any of them works.", '<div class="ph2 g">Remote + phone + gamepad</div>')}
</div>""", """
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:20px 34px}.c{background:#111826;border:1px solid #233048;border-radius:10px;padding:12px}
.s{height:112px;background:#05080d;border:1px solid #2b3a52;border-radius:8px;display:flex;align-items:center;justify-content:center}h3{margin:10px 0 4px;font-size:16px}p{margin:0;font-size:13.5px;color:#b7c3d4}
.ph2{font-size:15px;color:#c9d4e3;text-align:center;padding:0 10px}.ph2.g{color:#56d364}.ph2.w{color:#ffb454}.ph2.r{color:#ff7b72}small{color:#8b98a9;font-size:12px}.dot2{display:inline-block;width:9px;height:9px;border-radius:50%;background:#ffb454;margin-right:6px}""")

for name, html in (("phone-controller", pad), ("phone-pairing-tv", tv), ("phone-states", states)):
    f = HERE / f"{name}.html"
    f.write_text(html, encoding="utf-8")
    kb = f.stat().st_size // 1024
    assert kb < 512, (name, kb)
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1440,900",
                    f"--screenshot={HERE / (name + '.png')}", f"file://{f}"], capture_output=True, text=True)
    print(f"{name}: {kb} KB html, png {'ok' if (HERE / (name + '.png')).exists() else 'MISSING'}")
