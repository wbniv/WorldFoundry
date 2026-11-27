#!/usr/bin/env python3
"""Candle flicker A/B: the near-study strip, animated crops and the look page for Will (plan "Judging them by eye").

    python3 make_look.py A_FRAMES_DIR B_FRAMES_DIR OUT_DIR

A_FRAMES_DIR / B_FRAMES_DIR hold frame-0000.png ... from scripts/capture-candle-study.py (desktop engine, 1920 x 1080, the near
study 1.5 m from candle 9 of pine 1, frames 1/30 s apart on the level clock, so A and B show the same instants). Writes to OUT_DIR:
  near-study-strip.png   8 consecutive frames of each, cropped round the flame, 3x nearest-neighbour: A above, B below
  near-study-a.png/-b.png  every captured frame of the crop as an animated PNG (30 fps, loops), 3x
  look-real.html/.png    the page: the two animations side by side, the strip, and the cast1 tree clips (cast1-trees-a/b.mp4
                         beside it; the cast1 stills cast1-trees-a/b.png in the .png)
Run it in the Linux container (Pillow); it reads nothing else.
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw

CENTRE = (960, 530)      # the study camera looks at the flame's ring: the image centre (verified: the aimed candle lands there)
HALF = 70                # crop 140 x 140 px round it
ZOOM = 3


def crops(folder: Path):
    frames = sorted(folder.glob("frame-*.png"))
    if not frames:
        raise SystemExit(f"{folder}: no frames")
    box = (CENTRE[0] - HALF, CENTRE[1] - HALF, CENTRE[0] + HALF, CENTRE[1] + HALF)
    return [Image.open(f).convert("RGB").crop(box).resize((2 * HALF * ZOOM,) * 2, Image.NEAREST) for f in frames]


def apng(images, path: Path) -> bytes:
    buf = io.BytesIO()
    images[0].save(buf, format="PNG", save_all=True, append_images=images[1:], duration=33, loop=0, optimize=True)
    path.write_bytes(buf.getvalue())
    return buf.getvalue()


def strip(a, b, path: Path):
    n, t, gap, label = 8, a[0].width, 6, 34
    out = Image.new("RGB", (n * t + (n - 1) * gap + label, 2 * t + gap), (12, 16, 22))
    d = ImageDraw.Draw(out)
    for row, (name, seq) in enumerate((("A", a), ("B", b))):
        y = row * (t + gap)
        d.text((10, y + t // 2 - 6), name, fill=(230, 230, 230))
        for k in range(n):
            out.paste(seq[k], (label + k * (t + gap), y))
    out.save(path, optimize=True)
    return out


def main(argv):
    if len(argv) != 3 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    a, b = crops(Path(argv[0])), crops(Path(argv[1]))
    out = Path(argv[2])
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    pa, pb = apng(a, out / "near-study-a.png"), apng(b, out / "near-study-b.png")
    s = strip(a, b, out / "near-study-strip.png")
    def small(seq):        # the page embeds the crops at native size (under the bundle's 512 KB a file) and scales them up with CSS
        buf = io.BytesIO()
        seq = [im.resize((2 * HALF,) * 2, Image.NEAREST) for im in seq]
        seq[0].save(buf, format="PNG", save_all=True, append_images=seq[1:], duration=33, loop=0, optimize=True)
        return buf.getvalue()
    pa, pb = small(a), small(b)
    uri = lambda data: "data:image/png;base64," + base64.b64encode(data).decode()
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Candle flicker A/B</title>
<style>
:root {{ --bg:#f6f5f2; --fg:#1d1d1f; --muted:#5f6368; --card:#fff; --line:#d9d7d2; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111317; --fg:#ececec; --muted:#a0a4ab; --card:#1a1d22; --line:#2c3038; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui,sans-serif; }}
main {{ max-width:1400px; margin:0 auto; padding:20px 16px 40px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} h2 {{ font-size:17px; margin:26px 0 8px; }}
p {{ color:var(--muted); margin:4px 0 10px; max-width:80ch; }}
.row {{ display:flex; gap:16px; flex-wrap:wrap; }}
figure {{ margin:0; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px; }}
figcaption {{ font-weight:600; margin-bottom:6px; }}
img, video {{ display:block; max-width:100%; image-rendering:pixelated; border-radius:4px; }}
</style></head><body><main>
<h1>Candle flicker: Option A (two shapes) against Option B (deformed flame)</h1>
<p>Same level, same instants, night held at 22:00, Candles all year on. Desktop engine for the near study (1.5 m from one candle,
1920&nbsp;&times;&nbsp;1080, a 140&nbsp;px crop at 3&times;, {n} frames 33&nbsp;ms apart); cast1 for the trees (its own pixels, the village's still front view).</p>
<h2>Near study, looping</h2>
<div class="row">
<figure><figcaption>A: swap between two shapes</figcaption><img src="{uri(pa)}" width="420" height="420" alt="Option A flame, animated"></figure>
<figure><figcaption>B: one DFRM mesh, bent and stretched</figcaption><img src="{uri(pb)}" width="420" height="420" alt="Option B flame, animated"></figure>
</div>
<h2>Eight consecutive frames (33&nbsp;ms apart)</h2>
<figure><img src="near-study-strip.png" alt="eight frames of A above eight of B"></figure>
<h2>On cast1: two pines from the village's front view (crop of 1920&nbsp;&times;&nbsp;1080, native pixels)</h2>
<p>cast1's screen recorder keeps only about 6 frames a second here, so these show the twinkle, not every frame.</p>
<div class="row">
<figure><figcaption>A</figcaption><video src="cast1-trees-a.mp4" poster="cast1-trees-a.png" autoplay loop muted playsinline width="720"></video></figure>
<figure><figcaption>B</figcaption><video src="cast1-trees-b.mp4" poster="cast1-trees-b.png" autoplay loop muted playsinline width="720"></video></figure>
</div>
</main></body></html>
"""
    (out / "look-real.html").write_text(html)
    # the page's still (the bundle wants a same-name .png): first frames side by side, the strip, the cast1 stills
    stills = [Image.open(out / f"cast1-trees-{v}.png").convert("RGB") for v in "ab"]
    w = 1440
    page = Image.new("RGB", (w, 900), (17, 19, 23))
    d = ImageDraw.Draw(page)
    d.text((16, 10), "Candle flicker A (left / top) against B (right / bottom): near study, 8-frame strip, cast1 trees", fill=(236, 236, 236))
    t = 300
    page.paste(a[0].resize((t, t), Image.NEAREST), (16, 34))
    page.paste(b[0].resize((t, t), Image.NEAREST), (16 + t + 12, 34))
    sh = s.resize((w - 32 - 2 * t - 40, int(s.height * (w - 32 - 2 * t - 40) / s.width)), Image.NEAREST)
    page.paste(sh, (2 * t + 56, 34))
    cw = (w - 48) // 2
    for k, im in enumerate(stills):
        page.paste(im.resize((cw, int(im.height * cw / im.width))), (16 + k * (cw + 16), 360))
    page.quantize(256).save(out / "look-real.png", optimize=True)     # palette PNG: under the bundle's 512 KB a file
    for f in ("near-study-a.png", "near-study-b.png", "near-study-strip.png", "look-real.html", "look-real.png"):
        print(f"{f}: {(out / f).stat().st_size} B")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
