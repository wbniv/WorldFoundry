#!/usr/bin/env python3
"""make_mockups.py: the mockups for docs/plans/2026-10-01-split-cd-iff-one-app-per-game.md, from the REAL resources.

Reads android/app/src/<flavor>/res/ (scripts/gen-android-icons.py writes the art; values/strings.xml the labels, falling back
to src/main/res for snowgoons) and writes two self-contained 1440x900 pages (inline CSS, images as data URIs) beside this
file, each with a same-name PNG made by headless Chrome:

  launcher.html   the launcher tiles of all five apps: a phone grid, the legacy square and round icons, a narrow phone
  banners.html    the TV banners in a Google TV apps row (the new SMB tile focused) and the two new banners at 420 px
  adaptive-<app>.png   each app's adaptive icon as a launcher draws it, for the plan's Icons table

Usage: python3 make_mockups.py [-h]
"""
import argparse
import functools
import base64
import io
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
SRC = REPO / "android" / "app" / "src"
APPS = ["smb", "snowgoons", "qbert", "aquarium", "condo"]       # the two new apps first
NEW = {"smb", "qbert"}


def uri(img, fmt="PNG"):
    b = io.BytesIO()
    (img.convert("RGB") if fmt == "JPEG" else img).save(b, fmt, **({"quality": 88} if fmt == "JPEG" else {}))
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()


def res(app, rel):
    p = SRC / app / "res" / rel
    return p if p.exists() else SRC / "main" / "res" / rel


def label(app):
    return re.search(r'name="app_name">([^<]*)<', res(app, "values/strings.xml").read_text()).group(1)


def background(app):
    m = re.search(r'name="ic_launcher_background">(#[0-9A-Fa-f]{6})<', res(app, "values/colors.xml").read_text())
    return m.group(1) if m else "#1A1A2E"


@functools.lru_cache(None)
def adaptive(app, size=162):
    return uri(adaptive_img(app, size))


def adaptive_img(app, size):
    """The adaptive icon as a launcher draws it: background colour + foreground, under a circle mask (the visible 72 of 108 dp)."""
    fg = Image.open(res(app, "mipmap-xhdpi/ic_launcher_foreground.png")).convert("RGBA").resize((size, size), Image.LANCZOS)
    im = Image.new("RGBA", (size, size), background(app))
    im.alpha_composite(fg)
    inset = size // 6
    im = im.crop((inset, inset, size - inset, size - inset))
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, im.size[0] - 1, im.size[1] - 1), fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


CSS = """*{box-sizing:border-box}body{margin:0;width:1440px;height:900px;background:#0d1117;color:#e6edf3;font:16px/1.4 system-ui,'Noto Sans',sans-serif;overflow:hidden}
h1{margin:0;font-size:22px;font-weight:650}.top{padding:20px 34px 10px;border-bottom:1px solid #263041;display:flex;justify-content:space-between;align-items:baseline;gap:20px}
.sub{color:#8b98a9;font-size:14px}h3{margin:0 0 10px;font-size:17px}.cap{font-size:12px;color:#8b98a9;text-align:center;margin-top:6px}
.new{color:#56d364;font-size:11px;font-weight:700;letter-spacing:.04em}"""


def page(title, sub, body, css=""):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>{CSS}{css}</style></head>'
            f'<body><div class="top"><h1>{title}</h1><div class="sub">{sub}</div></div>{body}</body></html>')


def grid(cols, icon_px):
    cells = "".join(f'<div class="app"><img src="{adaptive(a)}" style="width:{icon_px}px;height:{icon_px}px">'
                    f'<div class="lbl">{label(a)}</div>{"<div class=new>NEW</div>" if a in NEW else ""}</div>' for a in APPS)
    return f'<div class="grid" style="grid-template-columns:repeat({cols},1fr)">{cells}</div>'


def ann_rows():
    rows = []
    for a in APPS:
        sq = uri(Image.open(res(a, "mipmap-xhdpi/ic_launcher.png")))
        rd = uri(Image.open(res(a, "mipmap-xhdpi/ic_launcher_round.png")))
        rows.append(f'<tr><td><b>{label(a)}</b>{" <span class=new>NEW</span>" if a in NEW else ""}<div class="sub">{a}</div></td>'
                    f'<td><img src="{sq}" class="ic"></td><td><img src="{rd}" class="ic"></td><td><img src="{adaptive(a)}" class="ic"></td></tr>')
    return "".join(rows)


launcher = page(
    "Mockup 1: the launcher tiles of all five apps",
    "Rendered from the real resources. SMB and Q*bert are new; their labels and art are placeholders until the user picks real ones.",
    f"""<div style="display:flex;gap:34px;padding:24px 34px;align-items:flex-start">
 <div><h3>Phone launcher (adaptive icons, circle mask)</h3><div class="phone wide">{grid(4, 64)}</div></div>
 <div><h3>Every icon, per app</h3><table><tr><th>App</th><th>legacy square</th><th>legacy round</th><th>adaptive</th></tr>{ann_rows()}</table></div>
 <div><h3>Narrow phone (320 px)</h3><div class="phone narrow">{grid(3, 56)}</div></div></div>""",
    """.phone{background:linear-gradient(160deg,#24384f,#121c28);border:10px solid #05080d;border-radius:34px;padding:26px 14px}.wide{width:420px;height:640px}
.narrow{width:320px;height:560px}.grid{display:grid;gap:18px 6px}.app{text-align:center}.app img{display:block;margin:0 auto;filter:drop-shadow(0 2px 3px #0008)}
.lbl{font-size:12px;margin-top:6px;color:#f0f4f8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}table{border-collapse:collapse;font-size:14px}
th{font-size:12px;color:#8b98a9;font-weight:500;text-align:left;padding:0 12px 8px 0}td{padding:6px 12px 6px 0;border-bottom:1px solid #1d2635;vertical-align:middle}
img.ic{width:72px;height:72px;display:block}""")

ban = {a: uri(Image.open(res(a, "drawable/tv_banner.png")), "JPEG") for a in APPS}
tiles = "".join(f'<div class="t{" f" if a == "smb" else ""}"><img src="{ban[a]}"><div class="n">{label(a)}</div></div>' for a in APPS)
banners = page(
    "Mockup 2: the TV banners in the Google TV apps row",
    "640×360 banners at half size; the new SMB tile is focused. Below: the two new banners at 420 px.",
    f"""<div style="padding:26px 34px"><div class="sub" style="margin-bottom:12px">Your apps</div><div class="row">{tiles}</div>
<div style="display:flex;gap:34px;margin-top:40px">{"".join(f'<div><img src="{ban[a]}" style="width:420px;border:1px solid #2b3a52;display:block"><div class="cap">{label(a)}: the name bottom-left, the logo bottom-right</div></div>' for a in ("smb", "qbert"))}
<div class="sub" style="max-width:420px">Both banners are cut from real engine frames (W1‑1 from the test harness; the Q*bert pyramid after the relight), below the score line. The frames are 640 px wide, so nothing is upscaled here; the 432 px icon foregrounds are.</div></div></div>""",
    """.row{display:flex;gap:18px;align-items:flex-start}.t{width:250px;text-align:center;color:#9fb3cc;font-size:14px}.t img{width:250px;height:141px;display:block;border-radius:6px}
.t .n{margin-top:6px}.t.f img{outline:4px solid #fff;outline-offset:3px;transform:scale(1.04)}.t.f .n{color:#fff;font-weight:600}""")


def main():
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args()
    for a in APPS:
        adaptive_img(a, 216).save(HERE / f"adaptive-{a}.png", optimize=True)
    for name, html in (("launcher", launcher), ("banners", banners)):
        f = HERE / f"{name}.html"
        f.write_text(html, encoding="utf-8")
        kb = f.stat().st_size // 1024
        assert kb < 512, (name, kb)
        subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1440,900",
                        f"--screenshot={HERE / (name + '.png')}", f"file://{f}"], capture_output=True, text=True)
        print(f"{name}: {kb} KB html, png {'ok' if (HERE / (name + '.png')).exists() else 'MISSING'}")


if __name__ == "__main__":
    main()
