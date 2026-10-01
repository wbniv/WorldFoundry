#!/usr/bin/env python3
"""make_mockups.py: render the mockups for the Android icons plan from the REAL generated resources (not drawings).

Reads android/app/src/<flavor>/res/ (the output of scripts/gen-android-icons.py) and the previous icons from git (HEAD~ of the
generation commit is approximated by `git show <rev>:<path>`; pass --before REV, default the parent of the first icons commit
is not needed: the old files are read from the working tree's git history via `git show HEAD:`). Each page is one self-contained
1440x900 HTML (inline CSS, images as data URIs) plus a same-name PNG made with headless Chrome.
Usage: python3 make_mockups.py [--before REV]
"""
import argparse, base64, io, subprocess
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
ap = argparse.ArgumentParser(); ap.add_argument("--before", default="HEAD"); a = ap.parse_args()
GAMES = [("snowgoons", "Snow Goons"), ("aquarium", "Aquarium"), ("condo", "Condo")]


def uri(img, fmt="PNG", q=88):
    b = io.BytesIO()
    (img.convert("RGB") if fmt == "JPEG" else img).save(b, fmt, **({"quality": q} if fmt == "JPEG" else {}))
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()


def now(game, rel, fmt="PNG"):
    return uri(Image.open(REPO / "android/app/src" / game / "res" / rel), fmt)


def before(game, rel, fmt="PNG"):
    """The icon the flavor had before this change: its own override at REV, else main's (the snowgoons flavor used main)."""
    for path in (f"android/app/src/{game}/res/{rel}", f"android/app/src/main/res/{rel}"):
        r = subprocess.run(["git", "show", f"{a.before}:{path}"], cwd=REPO, capture_output=True)
        if r.returncode == 0 and r.stdout:
            return uri(Image.open(io.BytesIO(r.stdout)), fmt)
    return None


CSS = """*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;background:#0d1117;color:#e6edf3;font:16px/1.4 system-ui,'Noto Sans',sans-serif;overflow:hidden}
h1{margin:0;font-size:22px;font-weight:650}.top{padding:20px 34px 10px;border-bottom:1px solid #263041;display:flex;justify-content:space-between;align-items:baseline}
.sub{color:#8b98a9;font-size:14px}.note{color:#ffb454;font-size:13px}h3{margin:0 0 8px;font-size:17px}.row{display:flex;gap:26px;align-items:flex-end;flex-wrap:wrap}
.cap{font-size:12px;color:#8b98a9;text-align:center;margin-top:6px}"""


def page(title, sub, body, css=""):
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>{CSS}{css}</style></head><body><div class="top"><h1>{title}</h1><div class="sub">{sub}</div></div>{body}</body></html>'


# 1. icons: before, the new legacy square, round, adaptive on three masks, and the phone-launcher size ----------------------------
cols = []
for g, label in GAMES:
    old = before(g, "mipmap-xxxhdpi/ic_launcher.png")
    sq, rd, fg = now(g, "mipmap-xxxhdpi/ic_launcher.png"), now(g, "mipmap-xxxhdpi/ic_launcher_round.png"), now(g, "mipmap-xhdpi/ic_launcher_foreground.png", "JPEG")
    small = now(g, "mipmap-xhdpi/ic_launcher_round.png")
    cols.append(f"""<div class="col" style="--fg:url({fg})"><h3>{label}</h3>
 <div class="row"><div><img class="old" src="{old or sq}"><div class="cap">before</div></div><div><img class="sqr" src="{sq}"><div class="cap">new, square (legacy)</div></div><div><img class="rnd" src="{rd}"><div class="cap">new, round</div></div></div>
 <div class="row" style="margin-top:12px"><div><div class="mask circ"></div><div class="cap">adaptive, circle mask</div></div><div><div class="mask squi"></div><div class="cap">adaptive, squircle</div></div>
  <div><div class="mask safe"></div><div class="cap">safe zone (inner 72 of 108 dp)</div></div></div>
 <div class="row" style="margin-top:12px;align-items:center"><img src="{small}" style="width:48px;height:48px"><img src="{small}" style="width:96px;height:96px"><span class="sub">launcher sizes: 48 px and 96 px</span></div></div>""")
icons = page("Mockup 1: the three new launcher icons, rendered from the real resources", "Same layout for every game: the game's art, plus the World Foundry logo bottom-right. Left of each set: the icon it replaces.", f'<div style="display:flex;gap:30px;padding:24px 34px">{"".join(cols)}</div>',
""".col{width:430px}img.old,img.sqr,img.rnd{width:112px;height:112px;display:block;border-radius:14px}img.rnd{border-radius:0}img.old{opacity:.8;outline:1px dashed #3a4a63}
.mask{width:104px;height:104px;overflow:hidden;background:#1a1a2e var(--fg) center/cover;position:relative}.circ{border-radius:50%}.squi{border-radius:30%}
.safe{border-radius:0;outline:2px solid #56d364}.safe:after{content:'';position:absolute;inset:16.66%;outline:2px dashed #ffb454}""")

# 2. TV banners in a Google TV apps row + the focused tile ----------------------------------------------------------------------------
ban = {g: now(g, "drawable/tv_banner.png", "JPEG") for g, _ in GAMES}
tiles = "".join(f'<div class="t{" f" if g == "aquarium" else ""}"><img src="{ban[g]}"><div class="n">{l}</div></div>' for g, l in GAMES)
banners = page("Mockup 2: the TV banners in the Google TV apps row", "640×360, shown at 1/2 size in a generic row. The aquarium tile is focused.", f"""
<div style="padding:26px 34px"><div class="sub" style="margin-bottom:12px">Your apps</div><div class="row" style="align-items:flex-start">{tiles}</div>
<div style="display:flex;gap:30px;margin-top:34px;align-items:flex-start">{"".join(f'<div><img src="{ban[g]}" style="width:420px;border:1px solid #2b3a52"><div class="cap">{l} at 420 px: name bottom-left, logo bottom-right</div></div>' for g, l in GAMES)}</div></div>""",
""".t{width:320px;text-align:center;color:#9fb3cc;font-size:14px}.t img{width:320px;height:180px;display:block;border-radius:6px}.t .n{margin-top:6px}.t.f img{outline:4px solid #fff;outline-offset:3px;transform:scale(1.04)}.t.f .n{color:#fff;font-weight:600}""")

# 3. the layout rule and the logo script ---------------------------------------------------------------------------------------------
lay = page("Mockup 3: the layout rule, and the logo as a separate script", "scripts/add-wf-logo.py stamps the favicon onto any existing icon; the generator only prepares the art.", f"""
<div style="display:flex;gap:40px;padding:26px 34px">
 <div><h3>Any icon in, same icon plus logo out</h3><div class="row" style="align-items:center"><div><img src="{before('snowgoons','mipmap-xxxhdpi/ic_launcher.png') or now('snowgoons','mipmap-xxxhdpi/ic_launcher.png')}" style="width:150px;height:150px"><div class="cap">an existing icon</div></div><div style="font-size:34px;color:#8b98a9">→</div><div><img src="{now('snowgoons','mipmap-xxxhdpi/ic_launcher.png')}" style="width:150px;height:150px"><div class="cap">{"add-wf-logo.py icon.png"}</div></div></div>
 <pre>scripts/add-wf-logo.py ICON.png            # in place
scripts/add-wf-logo.py ICON.png -o OUT.png
scripts/add-wf-logo.py *.png               # many
  --scale 0.26   --margin 0.05
  --safe-inset 0.1667   # adaptive foreground
  --circle              # round icon</pre></div>
 <div><h3>The rule</h3><div class="spec"><div class="art">the game's art<br>fills the icon</div><div class="logo"></div><span class="lbl">WF logo: 26% of the short side, 5% margin, bottom-right</span></div>
  <table><tr><td>Art</td><td>one image per game, committed in <code>android/app/art-src/</code></td></tr><tr><td>Logo</td><td>the website favicon, <code>../worldfoundry.org/public/favicon.svg</code></td></tr>
  <tr><td>Adaptive foreground</td><td>logo kept inside the inner 72 of 108 dp</td></tr><tr><td>Round icon</td><td>circle-masked; logo inside the circle at 45°</td></tr><tr><td>TV banner</td><td>name bottom-left, logo bottom-right</td></tr></table></div></div>""",
""".spec{position:relative;width:300px;height:300px;background:linear-gradient(135deg,#2f6fb3,#0f3a5c);border-radius:20px;margin-bottom:14px}.art{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;color:#cfe3ff;font-size:16px}
.logo{position:absolute;right:15px;bottom:15px;width:78px;height:78px;background:#f80000;border:5px solid #fff;box-shadow:inset 0 0 0 0 #000}.logo:after{content:'';position:absolute;inset:25%;background:#1a1714}
.lbl{position:absolute;left:0;top:306px;font-size:12px;color:#8b98a9;width:330px}pre{background:#05080d;border:1px solid #233048;border-radius:8px;padding:12px;font-size:13px;margin-top:16px}
table{border-collapse:collapse;font-size:14px;margin-top:34px}td{padding:6px 14px 6px 0;border-bottom:1px solid #1d2635;vertical-align:top}code{color:#9fb3cc}""")

import shutil, os
for name, html in (("icons", icons), ("banners", banners), ("layout", lay)):
    f = HERE / f"{name}.html"; f.write_text(html, encoding="utf-8")
    kb = f.stat().st_size // 1024; assert kb < 512, (name, kb)
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1440,900", f"--screenshot={HERE / (name + '.png')}", f"file://{f}"], capture_output=True, text=True)
    print(f"{name}: {kb} KB html, png {'ok' if (HERE / (name + '.png')).exists() else 'MISSING'}")
