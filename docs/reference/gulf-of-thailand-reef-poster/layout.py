"""Page layout, type and text rules for the Gulf of Thailand reef poster.

make_poster.py holds the claims and sources; this module turns them into HTML. It is kept apart so the
claim tables in make_poster.py stay readable.
"""
from __future__ import annotations

import html
import re

# ── Page and type ────────────────────────────────────────────────────────────
PAGE_W_MM, PAGE_H_MM, MARGIN_MM = 297, 420, 7
CW = 1047                       # content width in CSS px (277 mm at 96 dpi)
MIN_PX = 11.0                   # 8.25 pt: nothing on the poster is set smaller
PX_TO_PT = 0.75

INK, MUTED, GRID, WHITE = '#1d2733', '#55636f', '#d9e0e6', '#ffffff'
NAVY, NAVY_TEXT, ACC, GOLD = '#153547', '#f0ddad', '#315865', '#e7b964'
CARD_BG = '#f8f1df'
CHIP = {   # kind: (text, fill, edge)
    'verified': ('#0f5f30', '#e3f4ea', '#1f8a4c'),
    'other-region': ('#7a4500', '#fff2d9', '#b26a00'),
    'ours': ('#1b46b3', '#e4ecff', '#2b5fd9'),
    'unverified': ('#7f1d1d', '#fde8e8', '#b91c1c'),
}
STATUS_TEXT = {'verified': 'verified', 'other-region': 'other region', 'ours': 'ours', 'unverified': 'unverified'}
LEGEND_TEXT = {
    'verified': 'source read; it says this of the species named, in the Gulf of Thailand or of the species as a whole',
    'other-region': 'source read; other region, related species or broader taxon (scope in text and sources)',
    'ours': 'a game choice: what the animal does in our tank',
}
PRINTABLE = ('verified', 'other-region', 'ours')
FONT_SANS = '"Noto Sans","Noto Sans Thai","DejaVu Sans",sans-serif'
FONT_SERIF = '"Noto Serif","Noto Sans Thai","DejaVu Serif",serif'
_FONT_FILE = '/usr/share/fonts/truetype/noto/NotoSans-{}.ttf'
_FONT_CACHE: dict = {}

TEXT_PAIRS: set = set()         # (foreground, background) of every SVG text: the contrast test reads it
TEXT_SIZES: list = []           # every SVG font size (px)


def contrast(fg, bg):
    """WCAG 2.x contrast ratio between two #rrggbb colours."""
    def lum(c):
        ch = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        ch = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


HTML_TEXT_PAIRS = {(INK, WHITE), (MUTED, WHITE), (INK, CARD_BG), (MUTED, CARD_BG), (WHITE, ACC), (WHITE, NAVY),
                   (NAVY_TEXT, NAVY), (GOLD, NAVY), (ACC, WHITE), (NAVY, CARD_BG), (NAVY, WHITE)} | \
                  {(v[0], v[1]) for v in CHIP.values()}


def esc(s):
    return html.escape(str(s), quote=False)


def T(x, y, s, size=12, anchor='start', fill=INK, weight=400, bg=WHITE, italic=False):
    """SVG text, never under the type floor; records its colours for the contrast test."""
    assert size >= MIN_PX, f'{size}px text is under the {MIN_PX}px floor: {s!r}'
    TEXT_PAIRS.add((fill, bg))
    TEXT_SIZES.append(size)
    st = ' font-style="italic"' if italic else ''
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:g}" text-anchor="{anchor}" fill="{fill}" '
            f'font-weight="{weight}"{st}>{esc(s)}</text>')


def svg_open(w, h, title, view=None):
    vb = view or f'0 0 {w} {h}'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="{vb}" '
            f'font-family=\'{FONT_SANS}\' role="img"><title>{esc(title)}</title>')


# ── Text polish: units, dates ───────────────────────────────────────────────
UNITS = r'(?:cm/s|ms|cm|mm|km|m|kg|g|s|min|h|°C|%|°|psu|years?)'
_NUM_UNIT = re.compile(rf'(\d)[ \u00a0]+({UNITS})(?![\w/])')
_TIMES = re.compile(r'(\d) × (\d)')
_PM = re.compile(r'(\d) ± (\d)')
_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')


def polish_text(s):
    s = _PM.sub('\\1\u00a0±\u00a0\\2', s)
    s = _TIMES.sub('\\1\u00a0×\u00a0\\2', s)
    s = _NUM_UNIT.sub('\\1\u00a0\\2', s)
    return _ISO.sub('\\1\u2011\\2\u2011\\3', s)


def polish(doc):
    """Unit binding and non-breaking hyphens in text nodes only (never in tags, <style> or <script>)."""
    out, skip = [], False
    for part in re.split(r'(<[^>]*>)', doc):
        if part.startswith('<'):
            low = part.lower()
            if low.startswith(('<style', '<script')):
                skip = True
            elif low.startswith(('</style', '</script')):
                skip = False
            out.append(part)
        else:
            out.append(part if skip else polish_text(part))
    return ''.join(out)


# ── CSS and the fit check ───────────────────────────────────────────────────
def css():
    chips = ''.join(f'.chip.{k}{{ color:{v[0]}; background:{v[1]}; border-color:{v[2]} }}' for k, v in CHIP.items())
    return f"""
@page {{ size: A3 portrait; margin: 0 }}
*{{ box-sizing: border-box }}
html,body{{ margin:0; background:#fff; color:{INK}; -webkit-print-color-adjust:exact; print-color-adjust:exact }}
body{{ font: 11.5px/1.3 {FONT_SANS} }}
.page{{ width:{PAGE_W_MM}mm; height:{PAGE_H_MM}mm; padding:{MARGIN_MM}mm; overflow:hidden; display:flex; flex-direction:column; gap:6px; background:#fffaf0 }}
header{{ position:relative; isolation:isolate; overflow:hidden; background:{NAVY}; color:#fff; display:flex; gap:14px; padding:12px 18px; height:205px; flex:none; align-items:center; border-top:7px solid {GOLD}; box-shadow:inset 0 -4px #9b533a }}
header .ttl{{ flex:1; position:relative; z-index:2; max-width:55% }}
header .hero{{ position:absolute; z-index:-2; inset:0; width:100%; height:100%; object-fit:cover; object-position:center 68% }}
header.has-hero:after{{ content:''; position:absolute; z-index:-1; inset:0; background:linear-gradient(90deg,rgba(10,38,52,.96),rgba(10,38,52,.72) 40%,rgba(10,38,52,.05) 75%) }}
header h1{{ font-family:{FONT_SERIF}; margin:0; font-size:31pt; line-height:1.05; font-weight:700; letter-spacing:-.01em }}
header .thai{{ color:{GOLD}; font-size:17px; margin-top:3px }}
header .sub{{ color:{NAVY_TEXT}; font-size:12.5px; line-height:1.3; margin-top:4px }}
header svg{{ flex:none; display:block; border-radius:3px; width:430px; height:108px }}
.sec{{ flex:none; border:0; background:#fffaf0 }}
.bar{{ color:{NAVY}; background:transparent; font-family:{FONT_SERIF}; font-size:16pt; font-weight:700; height:28px; line-height:27px; padding:0 0 0 10px; white-space:nowrap; border-left:7px solid {GOLD}; border-bottom:1px solid #bd9b6b; letter-spacing:.01em }}
.bar .k{{ font-family:{FONT_SANS}; font-weight:400; font-size:11.5px; margin-left:10px; color:#fff }}
#panel-habitat .body{{ display:flex; gap:12px; padding:6px 8px }}
#panel-habitat svg{{ flex:none; display:block }}
.facts{{ flex:1; display:flex; flex-direction:column; gap:5px }}
.depth{{ display:flex; gap:13px; align-items:center; border-bottom:1px solid #d8c8a7; color:{NAVY}; padding:0 0 4px }}
.depth strong{{ color:#a15a38; font-family:{FONT_SERIF}; font-size:32px; line-height:35px }}
.depth strong span{{ font-size:15px }}
.depth div{{ font-family:{FONT_SERIF}; font-size:15px; line-height:18px; max-width:250px }}
.fact-columns{{ display:grid; grid-template-columns:1fr 1fr; column-gap:20px }}
.cl{{ margin:0 0 3px; font-size:11.5px; line-height:15px }}
.facts .cl{{ margin:0 0 7px; font-size:12px; line-height:16px }}
.ref{{ color:{MUTED}; white-space:nowrap }}
.chip{{ display:inline-block; min-width:14px; text-align:center; padding:0 2px; font-size:11px; line-height:13px; font-weight:800; border:0; white-space:nowrap; vertical-align:baseline }}
{chips}
.group-title{{ color:#87552e; font-family:{FONT_SERIF}; font-size:13pt; font-weight:700; line-height:22px; padding:2px 0 0 3px }}
.group-title span{{ color:#b67341; font-family:{FONT_SANS}; font-size:11px; letter-spacing:.08em; margin-right:8px }}
.cards{{ display:grid; grid-template-columns:repeat(2, 1fr); gap:1px 20px; padding:2px 3px 4px }}
.card{{ background:transparent; display:grid; grid-template-columns:170px minmax(0,1fr); gap:8px; align-items:center; padding:3px 0; overflow:hidden; border-bottom:1px solid #d8c8a7 }}
.card .top{{ display:flex; gap:6px; align-items:center; min-height:56px }}
.card .top svg{{ flex:none; display:block }}
.card .nm{{ font-family:{FONT_SERIF}; font-weight:700; font-size:14px; line-height:15px; color:{NAVY} }}
.card .lt{{ font-style:italic; font-size:11px; line-height:13px; color:{MUTED} }}
.card .kd{{ font-size:11px; line-height:13px; color:{MUTED} }}
.card .occur{{ font-size:11px; line-height:13px; color:{MUTED} }}
.card .cl{{ font-size:11px; line-height:12.8px; margin:0 0 1px }}
.card .cl b{{ color:{NAVY} }}
.fishes{{ display:flex; gap:8px; padding:6px }}
.fish{{ flex:1; display:flex; gap:8px }}
.fish svg{{ flex:none; display:block }}
.fish .nm{{ font-weight:700; font-size:13px; color:{NAVY} }}
.fish .lt{{ font-style:italic; font-size:11.5px; color:{MUTED}; margin-bottom:3px }}
footer{{ flex:1; border-top:2px solid {ACC}; padding-top:5px; display:flex; flex-direction:column; gap:4px; min-height:0 }}
.legend{{ display:flex; gap:12px; font-size:11px; line-height:14px; color:{INK} }}
.srcs{{ display:block; font-size:11.5px; line-height:17px }}
.srcs a{{ display:inline-block; margin-right:5px }}
.srcs ol{{ list-style:none; margin:0; padding:0; flex:1 }}
.srcs li{{ font-size:11px; line-height:13.5px; margin:0 0 2px; color:{MUTED} }}
.note{{ font-size:11px; line-height:14px; color:{MUTED} }}
a{{ color:{ACC}; text-decoration:underline }}
"""


FIT_SCRIPT = ("<script>window.addEventListener('load',function(){var p=document.querySelector('.page'),"
              "lim=p.getBoundingClientRect().bottom-parseFloat(getComputedStyle(p).paddingBottom),"
              "f=document.getElementById('panel-src'),k=f.lastElementChild,over=k.getBoundingClientRect().bottom-lim,bad=[];"
              "document.querySelectorAll('.sec,.card,.fish').forEach(function(e){if(e.scrollHeight>e.clientHeight+1)bad.push(e.id);});"
              "document.body.setAttribute('data-fit',(over<=1&&!bad.length)?'ok':'overflow');"
              "document.body.setAttribute('data-over',over.toFixed(1));"
              "document.body.setAttribute('data-panels-over',bad.join(' '));});</script>")
