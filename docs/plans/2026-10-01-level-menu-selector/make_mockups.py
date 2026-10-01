#!/usr/bin/env python3
"""make_mockups.py: the mockups for docs/plans/2026-10-01-level-menu-selector.md.

Writes six self-contained 1440x900 pages (inline CSS, no external references) beside this file, each with a same-name PNG
made by headless Chrome. Each page shows a 1280x720 TV (the Chromecast HD's surface) with the menu drawn on the 1920x1080
design canvas that wfsource/source/game/level_menu.cc scales from:

  default.html      launch: the first entry chosen
  moved.html        the cursor moved down to Q*bert
  scrolling.html    a 14-entry bundle: six rows show, arrows say more are above and below
  long-name.html    a name longer than the row ends in "..."
  remote-hint.html  the TV hint (D-pad and OK only) instead of the desktop one
  one-level.html    a one-entry bundle starts at once; an empty manifest is refused by cdpack

Usage: python3 make_mockups.py [-h] [--no-png]
"""
import argparse
import html
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The colours level_menu.cc uses (0xRRGGBB).
BG, TITLE, SUB, TEXT, SEL_BAR, SEL_EDGE, SEL_TEXT = "#0E1726", "#FFB454", "#8FA3BF", "#C9D4E3", "#23406B", "#56D364", "#FFFFFF"

SEVEN = ["SMB World 1-1", "SMB World 1-2", "SMB World 1-3", "SMB World 1-4", "Snowgoons", "Q*bert", "Astra Marble Madness"]
DESKTOP_HINT = "Up/Down choose - Space starts - Backspace in a game comes back here"
TV_HINT = "D-pad choose - OK starts"
ROWS, ROW_H, ROW_GAP, LIST_X0, LIST_X1, LIST_Y = 6, 92, 8, 360, 1560, 300
MAX_CHARS = 34   # what fits the row at this font; the engine measures the real width


def clip(name):
    return name if len(name) <= MAX_CHARS else name[:MAX_CHARS - 3] + "..."


def menu(names, cursor, hint, title="World Foundry"):
    """The menu on the 1920x1080 design canvas, as absolutely positioned boxes."""
    first = min(max(0, cursor - ROWS + 1), max(0, len(names) - ROWS))
    first = min(first, cursor)
    out = [f'<div class="t" style="top:66px;font-size:84px;color:{TITLE}">{html.escape(title)}</div>',
           f'<div class="t" style="top:176px;font-size:40px;color:{SUB}">Choose a game</div>']
    for row, i in enumerate(range(first, min(len(names), first + ROWS))):
        y = LIST_Y + row * (ROW_H + ROW_GAP)
        if i == cursor:
            out.append(f'<div class="r" style="left:{LIST_X0}px;top:{y}px;width:{LIST_X1 - LIST_X0}px;height:{ROW_H}px;background:{SEL_BAR}"></div>')
            out.append(f'<div class="r" style="left:{LIST_X0}px;top:{y}px;width:14px;height:{ROW_H}px;background:{SEL_EDGE}"></div>')
        colour = SEL_TEXT if i == cursor else TEXT
        out.append(f'<div class="n" style="left:{LIST_X0 + 48}px;top:{y + 20}px;color:{colour}">{html.escape(clip(names[i]))}</div>')
    if first > 0:
        out.append(f'<div class="t" style="top:246px;font-size:36px;color:{SUB}">&#9650;</div>')
    if first + ROWS < len(names):
        out.append(f'<div class="t" style="top:{LIST_Y + ROWS * (ROW_H + ROW_GAP) + 4}px;font-size:36px;color:{SUB}">&#9660;</div>')
    out.append(f'<div class="n" style="right:{1920 - LIST_X1}px;top:{LIST_Y + ROWS * (ROW_H + ROW_GAP) + 6}px;font-size:34px;color:{SUB}">'
               f'{cursor + 1} / {len(names)}</div>')
    out.append(f'<div class="t" style="top:996px;font-size:34px;color:{SUB}">{html.escape(hint)}</div>')
    return "\n".join(out)


def tv(inner):
    return f'<div class="tv"><div class="canvas">{inner}</div></div>'


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mockup - {title}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; width: 1440px; height: 900px; overflow: hidden; background: #ECEFF3; color: #1F2328;
         font: 15px/1.5 ui-sans-serif, system-ui, "Segoe UI", sans-serif; }}
  header {{ display: flex; align-items: center; gap: 12px; height: 64px; padding: 0 24px; border-bottom: 1px solid #D1D9E0; background: #F6F8FA; }}
  header h1 {{ margin: 0; font-size: 18px; font-weight: 600; }}
  header p {{ margin: 0; color: #59636E; font-size: 14px; }}
  header .tag {{ margin-left: auto; font: 600 11px ui-monospace, monospace; letter-spacing: .04em; color: #59636E;
                border: 1px solid #D1D9E0; border-radius: 10px; padding: 2px 8px; white-space: nowrap; }}
  .stage {{ display: flex; gap: 24px; justify-content: center; align-items: flex-start; padding: 40px 24px 0; }}
  .tv {{ position: relative; width: 1280px; height: 720px; border: 10px solid #111; border-radius: 6px; overflow: hidden;
         box-shadow: 0 8px 30px rgba(0,0,0,.25); background: {bg}; }}
  .small .tv {{ width: 640px; height: 360px; border-width: 6px; }}
  .canvas {{ position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; transform-origin: 0 0; transform: scale(0.6563); }}
  .small .canvas {{ transform: scale(0.3271); }}
  .t {{ position: absolute; left: 0; width: 1920px; text-align: center; white-space: nowrap; }}
  .r {{ position: absolute; }}
  .n {{ position: absolute; white-space: nowrap; font-size: 52px; }}
  .t, .n {{ font-family: "Courier New", "DejaVu Sans Mono", monospace; font-weight: bold; letter-spacing: 1px; }}
  figure {{ margin: 0; }}
  figcaption {{ margin-top: 10px; color: #59636E; font-size: 14px; max-width: 640px; }}
  pre {{ margin: 0; padding: 14px 16px; background: #0D1117; color: #E6EDF3; border-radius: 6px; font: 13px/1.5 ui-monospace, monospace; white-space: pre-wrap; }}
</style>
</head>
<body>
<header><h1>{title}</h1><p>{sub}</p><span class="tag">MOCKUP - NOT SHIPPED</span></header>
{body}
</body>
</html>
"""


def page(name, title, sub, body):
    path = HERE / f"{name}.html"
    path.write_text(PAGE.format(title=html.escape(title), sub=html.escape(sub), body=body, bg=BG))
    return path


def build():
    pages = []
    pages.append(page("default", "Level menu: at launch", "Desktop, 7 levels, the first chosen.",
                      f'<div class="stage">{tv(menu(SEVEN, 0, DESKTOP_HINT))}</div>'))
    pages.append(page("moved", "Level menu: a selection moved", "Down pressed five times: Q*bert. A starts it once released.",
                      f'<div class="stage">{tv(menu(SEVEN, 5, DESKTOP_HINT))}</div>'))
    many = SEVEN + [f"Test level {n}" for n in range(8, 15)]
    pages.append(page("scrolling", "Level menu: many entries", "14 entries, cursor on 9: six rows, arrows above and below.",
                      f'<div class="stage">{tv(menu(many, 8, DESKTOP_HINT))}</div>'))
    long_names = SEVEN[:4] + ["Snowgoons: the extended director's cut with all the bonus rooms", "Q*bert", "Astra Marble Madness"]
    pages.append(page("long-name", "Level menu: a long name", "A name wider than the row is cut and ends in '...'; the row never overflows.",
                      f'<div class="stage">{tv(menu(long_names, 4, DESKTOP_HINT))}</div>'))
    pages.append(page("remote-hint", "Level menu: the TV remote", "Chromecast HD at 720p: only the D-pad and OK are named (Phase E).",
                      f'<div class="stage">{tv(menu(SEVEN, 1, TV_HINT))}</div>'))
    one = (f'<div class="stage small">'
           f'<figure>{tv(menu(["Aquarium"], 0, DESKTOP_HINT))}'
           f'<figcaption><b>One entry: no menu is shown.</b> The engine starts the only game at once; this frame is never drawn. '
           f'Single-level bundles built without a manifest have no MENU chunk and boot level 0 exactly as today.</figcaption></figure>'
           f'<figure style="width:640px"><pre>$ cdpack shell-menu.fth --manifest empty.manifest -o out.iff\n'
           f'error: empty.manifest: no "level" lines\n$ echo $?\n1\n\n'
           f'$ wf_game   # shell-menu.fth, but a bundle with no MENU chunk\n'
           f'level-menu: no MENU chunk in cd.iff: starting level 0</pre>'
           f'<figcaption><b>Empty or missing menu.</b> cdpack refuses a manifest with no levels, so an empty menu cannot be built; a menu shell '
           f'over a plain bundle falls back to level 0 with one line on stderr.</figcaption></figure></div>')
    pages.append(page("one-level", "Level menu: one level, or none", "The two cases where no menu appears.", one))
    return pages


def shoot(path):
    png = path.with_suffix(".png")
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--hide-scrollbars", "--window-size=1440,900",
                    f"--screenshot={png}", path.as_uri()], check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-png", action="store_true", help="write the HTML only")
    args = ap.parse_args()
    for p in build():
        if not args.no_png:
            shoot(p)
        print(p.name)


if __name__ == "__main__":
    main()
