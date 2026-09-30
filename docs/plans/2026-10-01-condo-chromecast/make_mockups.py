#!/usr/bin/env python3
"""make_mockups.py: build the three self-contained 1440x900 mockups for the condo-on-Chromecast plan, and their PNGs.

Inline CSS/JS only, images embedded as data URIs (so each .html stays under 512 KB). The condo picture is an EARLIER
Linux render of the level (repo: docs/plans/2026-09-19-exporter-face-hand/), not a Chromecast capture: the mockups say so.
Usage: python3 make_mockups.py   (needs google-chrome for the PNGs)
"""
import base64, io, subprocess, sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent


def data_uri(path, size=None, fmt="JPEG", q=78):
    im = Image.open(path).convert("RGB")
    if size:
        im = im.resize(size, Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, fmt, quality=q) if fmt == "JPEG" else im.save(b, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()


CONDO = data_uri(REPO / "docs/plans/screenshots/2026-09-19-condo-site-dollhouse.png", (720, 540))
AQ_BANNER = data_uri(REPO / "docs/porting-status/android-tv-banner.png", (320, 180), "PNG")

CSS = """
*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;background:#0d1117;color:#e6edf3;font:16px/1.4 system-ui,'Noto Sans',sans-serif;overflow:hidden}
h1{margin:0;font-size:22px;font-weight:650}.top{padding:22px 34px 10px;border-bottom:1px solid #263041;display:flex;justify-content:space-between;align-items:baseline}
.sub{color:#8b98a9;font-size:14px}.note{color:#ffb454;font-size:13px}.tag{display:inline-block;border:1px solid #3a4a63;border-radius:999px;padding:1px 10px;font-size:12px;color:#9fb3cc;margin-left:8px}
.ok{color:#56d364}.bad{color:#ff7b72}.warn{color:#ffb454}
"""


def page(title, sub, body, extra_css=""):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>{CSS}{extra_css}</style></head><body>
<div class="top"><h1>{title}</h1><div class="sub">{sub}</div></div>{body}</body></html>"""


# 1. launcher row ---------------------------------------------------------------------------------------------
launcher = page("Mockup 1: the launcher row", "Chromecast HD, 1920×1080 shown at 1440×900. Generic launcher, not the real Google TV UI.", f"""
<div style="padding:28px 34px">
 <div class="sub" style="margin-bottom:14px">Your apps</div>
 <div class="row">
  <div class="t"><div class="c" style="background:#2b3a55">▶</div><span>Video</span></div>
  <div class="t"><div class="c" style="background:#5a2b55">♪</div><span>Music</span></div>
  <div class="t"><div class="c" style="background:#10466b;overflow:hidden"><img src="{AQ_BANNER}" style="height:100%;margin-left:-38px"></div><span>WF Aquarium</span></div>
  <div class="t f"><div class="c" style="background:#6b5a3a;overflow:hidden"><img src="{CONDO}" style="height:100%;margin-left:-20px"></div><span style="color:#fff;font-weight:600">WF Condo</span></div>
  <div class="t"><div class="c" style="background:#26303f">＋</div><span>Add apps</span></div>
 </div>
 <div style="display:flex;gap:40px;margin-top:40px">
  <div><div class="sub">TV banner (320×180) when the tile is focused</div>
   <div style="width:480px;height:270px;border:2px solid #56d364;border-radius:8px;overflow:hidden;position:relative;margin-top:8px"><img src="{CONDO}" style="width:100%"><div style="position:absolute;left:14px;bottom:12px;font-size:30px;font-weight:700;text-shadow:0 2px 6px #000">WF CONDO</div></div>
   <div class="note" style="margin-top:8px">Art is generated from a real capture of the level; this picture is an earlier render.</div></div>
  <div style="flex:1"><div class="sub">States</div>
   <table><tr><td><b>Unfocused</b></td><td>round icon + label below, like the other apps</td></tr>
   <tr><td><b>Focused</b></td><td>tile grows, bright ring, full label (shown above)</td></tr>
   <tr><td><b>Installed next to</b></td><td>WF Aquarium and snowgoons: separate app ids, never a level menu</td></tr>
   <tr><td><b>No icon art</b></td><td class="bad">a blank or default icon fails the plan's art check</td></tr></table></div>
 </div></div>""", """
.row{display:flex;gap:34px;align-items:flex-end}.t{text-align:center;width:150px;color:#9fb3cc;font-size:14px}.c{width:132px;height:132px;border-radius:50%;margin:0 auto 10px;display:flex;align-items:center;justify-content:center;font-size:40px;color:#c9d4e3}
.t.f .c{transform:scale(1.18);box-shadow:0 0 0 4px #56d364,0 0 34px #56d36488}.t.f{transform:translateY(-4px)}.t.f span{display:block;margin-top:16px}table{border-collapse:collapse;margin-top:8px;font-size:15px}td{padding:6px 14px 6px 0;border-bottom:1px solid #1d2635;vertical-align:top}""")

# 2. running + controls -------------------------------------------------------------------------------------------
running = page("Mockup 2: the condo running, and what the remote reaches", "TV mode: the on-screen touch HUD is hidden (detected on the aquarium app).", f"""
<div style="display:flex;gap:30px;padding:24px 34px">
 <div><div style="position:relative;width:864px;height:486px;background:#000;border:1px solid #2b3a52">
   <img src="{CONDO}" style="position:absolute;left:144px;top:0;height:486px"><div class="pill" style="left:10px;top:10px">WF Condo · running · TV mode (no touch HUD)</div>
   <div class="pill" style="right:10px;bottom:10px;border-color:#ffb454;color:#ffb454">frame pace: MEASURE ON DEVICE (target 15+ fps)</div></div>
  <div class="note" style="margin-top:8px;max-width:864px">This picture is a 4:3 render (pillarboxed here). The real 16:9 framing of the condo has never been seen: camera FOV and the dollhouse shot may need a per-aspect value, as the aquarium did.</div></div>
 <div style="flex:1"><div class="sub" style="margin-bottom:6px">Controls: reachable from the TV remote vs a gamepad</div>
  <table><tr><th>Input</th><th>Effect</th><th>Remote</th><th>Gamepad</th></tr>
   <tr><td>▲ ▼</td><td>walk back / front</td><td class="ok">yes</td><td class="ok">yes</td></tr>
   <tr><td>◀ ▶</td><td>strafe</td><td class="ok">yes</td><td class="ok">yes</td></tr>
   <tr><td>A</td><td>hop</td><td class="warn">OK button (to verify)</td><td class="ok">yes</td></tr>
   <tr><td>B</td><td>glass doors, balcony zip screen</td><td class="bad">no</td><td class="ok">yes</td></tr>
   <tr><td>C</td><td>teleport 639 ⇄ 640</td><td class="bad">no</td><td class="ok">yes</td></tr>
   <tr><td>hold D + ◀▶▲▼</td><td>orbit, inspection angle</td><td class="bad">no</td><td class="ok">yes</td></tr>
   <tr><td>E / F</td><td>zoom</td><td class="bad">no</td><td class="ok">yes</td></tr></table>
  <div class="note" style="margin-top:12px">With only the remote you can walk around the units, strafe and hop. Doors, the teleport and the camera need a paired gamepad.</div></div></div>""", """
.pill{position:absolute;background:#000a;border:1px solid #56d364;color:#56d364;border-radius:999px;padding:3px 12px;font-size:13px}table{border-collapse:collapse;font-size:14.5px;width:100%}th{text-align:left;color:#8b98a9;font-weight:500;padding:4px 10px 6px 0}td{padding:6px 10px 6px 0;border-bottom:1px solid #1d2635;vertical-align:top}""")

# 3. states storyboard --------------------------------------------------------------------------------------------
states = page("Mockup 3: the states a viewer and the tester will see", "Real states from the aquarium run, applied to the condo; numbers are what the plan will measure.", f"""
<div class="grid">
 <div class="p"><div class="sh"><div class="lbl">1 Loading</div><div class="sub" style="text-align:center">black frame, 2.4 MB level<br>first frame after ~? s</div></div><h3>Loading</h3><p>The aquarium's 186 KB level launched in 1.1 s. The condo is 13× bigger: <b>time to first frame is measured</b>, target under 10 s.</p></div>
 <div class="p"><div class="sh" style="padding:0"><img src="{CONDO}" style="height:100%"></div><h3 class="ok">2 Running</h3><p>Alive after 60 s, no crash lines, walking with the D-pad moves the player (<code>ball pos</code> changes).</p></div>
 <div class="p"><div class="sh" style="padding:0;position:relative"><img src="{CONDO}" style="height:100%;filter:saturate(.6)"><div class="pill2">0.4 s / frame</div></div><h3 class="warn">3 Slow</h3><p>The aquarium's <i>debug</i> build drew 0.4 s per frame. Judge the condo on a <b>release</b> build; if it is under ~15 fps, report the number and do not change the level.</p></div>
 <div class="p"><div class="sh" style="padding:18px"><div class="sub">Home pressed</div><div class="lbl" style="font-size:20px">suspended</div><div class="sub">back to launcher, app kept</div></div><h3>4 Suspend and resume</h3><p>Home then reopen: the app resumes or restarts without a crash. <span class="warn">Not yet tested on the device.</span></p></div>
 <div class="p" style="grid-column:span 2"><div class="term"><span class="bad">FAIL</span> the APK has no native ABI this device supports (APK: arm64-v8a; device: armeabi-v7a)<br><span class="sub">what the install script said before the 32-bit build; the condo app carries both ABIs</span><br><span class="bad">FAIL</span> process not running after 25 s: <span class="warn">AssertMsg: width = 1024, map.GetXSize()+1 = 257 (gfx/texture.cc:74)</span><br><span class="sub">cause: the Android app passed no --vram-* flags, so the engine used its small default texture budget (the level is fine); the app now ships wf_args.txt</span></div><h3 class="bad">5 Errors the plan must catch</h3></div>
</div>""", """
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;padding:22px 34px}.p{background:#111826;border:1px solid #233048;border-radius:10px;padding:14px}h3{margin:10px 0 4px;font-size:16px}p{margin:0;font-size:14px;color:#b7c3d4}
.sh{height:168px;background:#000;border:1px solid #2b3a52;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden}.lbl{font-size:26px;color:#8b98a9}.pill2{position:absolute;right:6px;bottom:6px;background:#000c;border:1px solid #ffb454;color:#ffb454;padding:1px 8px;border-radius:999px;font-size:12px}
.term{font:13.5px/1.6 ui-monospace,monospace;background:#05080d;border:1px solid #233048;border-radius:6px;padding:12px}code{color:#9fb3cc}""")

for name, html in (("launcher-row", launcher), ("running-and-controls", running), ("states", states)):
    f = HERE / f"{name}.html"
    f.write_text(html, encoding="utf-8")
    kb = f.stat().st_size // 1024
    assert kb < 512, (name, kb)
    r = subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1440,900",
                        f"--screenshot={HERE / (name + '.png')}", f"file://{f}"], capture_output=True, text=True)
    print(f"{name}: {kb} KB html, png {'ok' if (HERE / (name + '.png')).exists() else 'MISSING'}")
