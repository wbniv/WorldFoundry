#!/usr/bin/env python3
"""Build the settings-editor font mockups (tv-form, states) and their PNG thumbnails.

Renders the TV settings dialog at its 1920x1080 logical size in Atkinson
Hyperlegible Next, the font ../finding-your-way uses, with the layout measured
from the Cast1 device captures in docs/diagnostics/picker-3d/. The "before"
panels are those real captures. A prototype WFGA-style atlas is baked with the
same variant list the plan proposes, to measure its size and coverage.

    python3 docs/plans/2026-10-17-settings-editor-font/build_mockups.py [-h]

Needs Pillow, node and ~/python-tui-lib/scripts/preview-shot.mjs (system Chrome).
WF_UI_FONT_DIR overrides where the two TTFs are read from.
"""
import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FONTS = Path(os.environ.get('WF_UI_FONT_DIR', Path.home() / 'finding-your-way/game/parmenides-slice/fonts'))
SHOT = Path.home() / 'python-tui-lib' / 'scripts' / 'preview-shot.mjs'
CAPS = ROOT / 'docs/diagnostics/picker-3d'

# Colours from runtime_property_ui.cc / runtime_settings_ui.cc (0xRRGGBB).
BG, BOX, ROW, FOCUS = (6, 16, 20), (20, 45, 37), (35, 62, 49), (73, 123, 81)
INK, CAT, HINT, DIM = (241, 242, 228), (203, 212, 186), (217, 195, 106), (150, 165, 150)
LIGHT, DARK, TAG, GREEN, ERR = (228, 239, 217), (20, 38, 27), (13, 31, 23), (143, 224, 138), (255, 123, 114)
# Proposed variants: (name, style file, pixel size) at the 1920x1080 logical canvas.
VARIANTS = [('small', 'Regular', 28), ('body', 'Regular', 36), ('body-bold', 'SemiBold', 36), ('title', 'SemiBold', 46)]


def font(style, size):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / f'AtkinsonHyperlegibleNext-{style}.ttf'), size)


class TV:
    """A 1920x1080 frame drawn with the proposed variants."""
    def __init__(self):
        from PIL import Image, ImageDraw
        self.im = Image.new('RGB', (1920, 1080), BG)
        self.d = ImageDraw.Draw(self.im)
        self.f = {n: font(s, px) for n, s, px in VARIANTS}

    def rect(self, x, y, w, h, c):
        self.d.rectangle([x, y, x + w - 1, y + h - 1], fill=c)

    def text(self, x, y, s, v='body', c=INK, anchor='la'):
        self.d.text((x, y), s, font=self.f[v], fill=c, anchor=anchor)

    def left_arrow(self, x, cy, c):
        self.rect(x + 3, cy - 2, 26, 4, c)
        for i in range(10):
            self.rect(x + i, cy - i - 2, 4, 4, c)
            self.rect(x + i, cy + i - 2, 4, 4, c)

    def crosshair(self, cx, cy, c):
        self.d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], outline=c, width=3)
        for a, b, w, h in ((-1.5, -20, 3, 10), (-1.5, 10, 3, 10), (-20, -1.5, 10, 3), (10, -1.5, 10, 3)):
            self.rect(cx + a, cy + b, w, h, c)

    def padlock(self, x, y, c):
        self.d.arc([x + 4, y, x + 22, y + 20], 180, 360, fill=c, width=4)
        self.rect(x + 4, y + 9, 4, 6, c); self.rect(x + 18, y + 9, 4, 6, c)
        self.d.rounded_rectangle([x, y + 13, x + 26, y + 32], radius=3, fill=c)

    def png(self, size=None):
        from PIL import Image
        im = self.im if size is None else self.im.resize(size, Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
        return buf.getvalue()


def form(error=False):
    """Baseline settings 2, the Cast1 tv-form capture's content and geometry."""
    t = TV()
    t.rect(180, 110, 1560, 820, BOX)
    t.text(222, 140, 'Planted Tank Settings' if error else 'Baseline settings 2', 'title')
    for i, label in enumerate(['Sample Settings', 'Runtime Options'] if not error else ['Plant growth', 'Seahorses']):
        t.rect(225, 240 + i * 85, 330, 66, FOCUS if (error and i == 0) else ROW)
        t.text(245, 273 + i * 85, label, 'body', INK, 'lm')
    t.text(603, 232, 'Values' if not error else 'Plant growth', 'small', CAT)
    if not error:
        t.rect(600, 270, 1080, 72, FOCUS); t.text(618, 306, 'Signed_INT32_NUMBER_40: −3', 'body', INK, 'lm')
        t.rect(600, 355, 1080, 116, ROW); t.text(618, 384, 'Fraction_FIXED32_SLIDER_64: 0.25', 'body', INK, 'lm')
        t.rect(630, 414, 1000, 4, (138, 171, 138)); t.rect(630, 414, 562, 4, LIGHT); t.rect(1185, 404, 14, 24, (240, 196, 112))
        t.text(630, 448, '−2.000000', 'small', INK, 'lm'); t.text(1630, 448, '2.000000', 'small', INK, 'rm')
        t.rect(600, 483, 1080, 98, ROW); t.text(618, 510, 'Enum_INT32_RADIOBUTTONS_48', 'body', INK, 'lm')
        for k, (o, on) in enumerate((('Low', 0), ('Medium', 1), ('High', 0))):
            x = 616 + k * 344
            t.rect(x, 532, 336, 38, LIGHT if on else (28, 48, 40)); t.text(x + 14, 551, o, 'small', DARK if on else INK, 'lm')
        t.rect(600, 592, 1080, 74, ROW); t.text(618, 629, 'Boolean_INT32_CHECKBOX_51: On', 'body', INK, 'lm')
        t.rect(600, 678, 1080, 74, ROW); t.text(618, 715, 'Text_STRING_N_A_70: Baseline', 'body', INK, 'lm')
        t.text(598, 788, 'Baseline Signed', 'small', DIM)
    else:
        t.rect(600, 270, 1080, 112, FOCUS); t.text(618, 302, 'Seed: 4294967296', 'body', INK, 'lm')
        t.text(618, 350, 'Seed must be 0 to 2 147 483 647', 'small', ERR, 'lm')
        t.rect(600, 395, 1080, 74, ROW); t.text(618, 432, 'Water type: Saltwater', 'body', INK, 'lm')
        t.rect(600, 481, 1080, 74, ROW); t.text(618, 518, 'Growth speed: 1×', 'body', INK, 'lm')
        t.rect(600, 567, 1080, 74, ROW); t.text(618, 604, 'Initial age: 150 s', 'body', DIM, 'lm'); t.padlock(1630, 588, DIM)
        t.text(598, 788, 'Random number seed from 0 to 4 294 967 295', 'small', DIM)
    t.text(222, 845, 'Arrows: select     A: edit', 'small', HINT, 'lm')
    t.left_arrow(1260, 845, INK); t.text(1302, 845, 'Apply / close', 'small', INK, 'lm')
    return t


def chooser():
    t = TV()
    t.rect(180, 110, 1560, 820, BOX)
    t.text(222, 140, 'Choose an object', 'title')
    for i, label in enumerate(['Pick in 3D', 'Baseline settings [19]', 'Baseline settings 2 [20]', 'Baseline settings 3 [21]']):
        y = 240 + i * 85
        t.rect(225, y, 1455, 66, FOCUS if i == 0 else ROW)
        if i == 0:
            t.crosshair(262, y + 33, INK); t.text(292, y + 33, label, 'body-bold', INK, 'lm')
        else:
            t.text(245, y + 33, label, 'body', INK, 'lm')
    t.text(222, 860, 'Up / down: select     OK: open     Back: cancel', 'small', HINT, 'lm')
    return t


def tags():
    t = TV()
    for i, (label, x, y) in enumerate((('Baseline settings 2', 380, 400), ('2 objects here', 1160, 400))):
        w = t.d.textlength(label, font=t.f['body-bold']) + 32
        t.rect(x, y, w, 52, TAG)
        t.d.rectangle([x, y, x + w - 1, y + 51], outline=GREEN, width=2)
        t.text(x + 16, y + 26, label, 'body-bold', GREEN, 'lm')
        cx = x + w / 2; by = y + 90
        for dx, dy in ((-60, 0), (60, 0)):
            pass
        t.d.line([cx - 60, by, cx - 30, by], fill=GREEN, width=6); t.d.line([cx - 60, by, cx - 60, by + 30], fill=GREEN, width=6)
        t.d.line([cx + 30, by, cx + 60, by], fill=GREEN, width=6); t.d.line([cx + 60, by, cx + 60, by + 30], fill=GREEN, width=6)
    t.rect(0, 1020, 1920, 60, (8, 16, 9))
    t.text(30, 1050, 'Arrows: move     OK: edit', 'small', HINT, 'lm'); t.text(1890, 1050, '← list', 'small', HINT, 'rm')
    return t


def cast1(name, sub='cast1-baseline-settings'):
    from PIL import Image
    p = CAPS / sub / name
    return Image.open(p).convert('RGB') if p.exists() else None


def png_of(im, size):
    from PIL import Image
    buf = io.BytesIO(); im.resize(size, Image.LANCZOS).save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def bake_atlas():
    """Prototype atlas: the plan's coverage set and variants, shelf-packed 1024 wide."""
    from PIL import Image
    sys.path.insert(0, str(FONTS.parent))
    import glyph_atlas  # finding-your-way's cmap reader (build-time only)
    cmap = glyph_atlas.cmap(FONTS / 'AtkinsonHyperlegibleNext-Regular.ttf')
    want = [c for c in list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x2212] if c in cmap]
    W, pad, x, y, row, glyphs = 1024, 2, 0, 0, 0, []
    for name, style, px in VARIANTS:
        f = font(style, px)
        for c in want:
            box = f.getbbox(chr(c))
            w, h = max(1, box[2] - box[0]), max(1, box[3] - box[1])
            if x + w + pad > W:
                x, y, row = 0, y + row + pad, 0
            glyphs.append((name, c, x, y, w, h, f, box)); x += w + pad; row = max(row, h)
    H = 1 << (y + row).bit_length()
    atlas = Image.new('L', (W, H), 0)
    for name, c, gx, gy, w, h, f, box in glyphs:
        m = f.getmask(chr(c))
        g = Image.frombytes('L', m.size, bytes(m)) if m.size[0] and m.size[1] else None
        if g:
            atlas.paste(g, (gx, gy))
    return atlas, len(want), len(glyphs), (W, H)


def page(name, title, sub, body):
    return f'''<!DOCTYPE html>
<!-- Plan mockup: settings editor font. GENERATED by build_mockups.py; 1440x900. -->
<html lang="en"><head><meta charset="utf-8"><title>Mockup: {title}</title><style>
 :root{{--bg:#fff;--fg:#1f2328;--muted:#656d76;--line:#d1d9e0;--panel:#f6f8fa}}
 @media (prefers-color-scheme: dark){{:root{{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--line:#30363d;--panel:#161b22}}}}
 *{{box-sizing:border-box}} body{{margin:0;width:1440px;height:900px;overflow:hidden;background:var(--bg);color:var(--fg);font:13.5px/1.4 system-ui,sans-serif}}
 header{{display:flex;gap:14px;align-items:baseline;height:52px;padding:13px 22px;border-bottom:1px solid var(--line);background:var(--panel)}}
 header h1{{margin:0;font-size:16px}} header .sub{{color:var(--muted)}} header .tag{{margin-left:auto;font:600 11px ui-monospace,monospace;color:var(--muted);border:1px solid var(--line);border-radius:10px;padding:2px 8px}}
 main{{display:grid;gap:14px 20px;padding:12px 22px}} h2{{margin:0 0 4px;font-size:13.5px}} .cap{{margin:0 0 6px;color:var(--muted);font-size:12px}}
 img{{display:block;border-radius:6px}} code{{font:12px ui-monospace,monospace}}
</style></head><body><header><h1>{title}</h1><span class="sub">{sub}</span><span class="tag">MOCKUP: NOT SHIPPED</span></header>
{body}</body></html>'''


def uri(b):
    return 'data:image/png;base64,' + base64.b64encode(b).decode()


def main():
    from PIL import Image
    S = (640, 360)
    before_form, before_choose = cast1('tv-form-screenshot.png'), cast1('picker-chooser-screenshot.png', 'cast1-baseline-picker')
    blank = Image.new('RGB', (1920, 1080), (40, 40, 40))
    f_after, c_after = form(), chooser()
    body = f'''<main style="grid-template-columns:640px 640px">
 <div><h2>1. Before: the form on Chromecast 1 today</h2><p class="cap"><code>stb_easy_font</code> strokes, scaled ×2.5 (<code>tv-form-screenshot.png</code>, J‑28f5619ea275).</p><img src="{uri(png_of(before_form or blank, S))}" width="640" height="360"></div>
 <div><h2>2. After: Atkinson Hyperlegible Next, same layout</h2><p class="cap">Title SemiBold 46 px · rows Regular 36 px · help and hints Regular 28 px (1080p logical).</p><img src="{uri(f_after.png(S))}" width="640" height="360"></div>
 <div><h2>3. Before: the chooser</h2><p class="cap">The Pick in 3D row as Cast1 drew it (J‑6922370e7eb5).</p><img src="{uri(png_of(before_choose or blank, S))}" width="640" height="360"></div>
 <div><h2>4. After: the chooser</h2><p class="cap">Selected row SemiBold; crosshair, gear, arrow and padlock stay drawn shapes.</p><img src="{uri(c_after.png(S))}" width="640" height="360"></div>
</main>'''
    out = {}
    out['tv-form'] = page('tv-form', 'Settings editor font: before and after', 'Chromecast 1 captures vs the same layout in Atkinson Hyperlegible Next', body)

    atlas, cps, n, (W, H) = bake_atlas()
    small = f_after.im.resize((1280, 720), Image.BILINEAR).crop((0, 40, 640, 400))
    abuf = io.BytesIO(); atlas.crop((0, 0, 1024, min(H, 512))).resize((512, min(H, 512) // 2)).save(abuf, 'PNG', optimize=True)
    body2 = f'''<main style="grid-template-columns:640px 640px">
 <div><h2>5. Pick mode: highlight tags</h2><p class="cap">The single-object tag and the same-spot group, SemiBold 36 px on the picker's green.</p><img src="{uri(tags().png(S))}" width="640" height="360"></div>
 <div><h2>6. Error: a value outside its range</h2><p class="cap">The row keeps focus; the message is Regular 28 px in the error colour. Read-only rows dim with the padlock (M8).</p><img src="{uri(form(error=True).png(S))}" width="640" height="360"></div>
 <div><h2>7. Narrow: drawn at 1280×720, shown 1:1</h2><p class="cap">The 1080p atlas sampled at ⅔ scale (bilinear), as on a 720p surface; the smallest text is 19 px.</p><img src="{uri(png_of(small, (640, 360)))}" width="640" height="360"></div>
 <div><h2>8. The baked atlas (prototype)</h2><p class="cap">{cps} code points × {len(VARIANTS)} variants = {n} glyphs, shelf-packed: <b>{W}×{H}</b>, 8-bit coverage = {W*H//1024} KiB. Top {min(H,512)} rows shown at ½ scale.</p><img src="{uri(abuf.getvalue())}" width="512"></div>
</main>'''
    out['states'] = page('states', 'Settings editor font: states and the atlas', 'pick tags, error, 720p, the baked atlas', body2)

    for name, html in out.items():
        p = HERE / f'{name}.html'
        p.write_text(html)
        full = HERE / f'{name}-full.png'
        subprocess.run(['node', str(SHOT), str(p), str(full), '--width', '1440', '--height', '1000', '--full', '--wait', '800'], check=True, capture_output=True)
        Image.open(full).crop((0, 0, 1440, 900)).save(HERE / f'{name}.png'); full.unlink()
        print(f'{name}.html {p.stat().st_size // 1024} KB')
    (HERE / 'atlas.json').write_text(json.dumps({'codepoints': cps, 'variants': [list(v) for v in VARIANTS], 'glyphs': n, 'atlas': [W, H], 'bytes': W * H}, indent=1) + '\n')
    print(json.dumps({'codepoints': cps, 'glyphs': n, 'atlas': [W, H]}))


if __name__ == '__main__':
    if {'-h', '--help'} & set(sys.argv[1:]):
        print(__doc__.strip()); sys.exit(0)
    main()
