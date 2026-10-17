#!/usr/bin/env python3
"""Embed the UI font in the phone controller page as inline WOFF2 subsets (F4).

    scripts/in-linux-container.sh python3 scripts/subset-phone-font.py [--check] [--page PATH]

Subsets Atkinson Hyperlegible Next Regular and SemiBold (wfsource/fonts/atkinson-hyperlegible-next/)
to the same code points as the engine's atlas (scripts/bake-ui-font.py: printable ASCII,
U+00A0-00FF and – — ‘ ’ “ ” • … −) with fontTools' subsetter (pyftsubset; pinned in
docker/Dockerfile.linux-test), as WOFF2 without hinting and without kerning (with GPOS kerning the
page grows past tests/test_phone_controller_page.py's 64 KiB cap), and writes them into
wfsource/source/hal/phonepad/controller.html as base64 @font-face rules between the
"ui-font:begin" and "ui-font:end" markers. The page then has no external font request.
--check exits 1 if the page is not what this script would write. Plan:
docs/plans/2026-10-17-settings-editor-font.md, Phase 4.
"""
import argparse
import base64
import importlib.util
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'wfsource' / 'source' / 'hal' / 'phonepad' / 'controller.html'
BEGIN, END = '/* ui-font:begin', '/* ui-font:end */'
FAMILY = 'Atkinson Hyperlegible Next'


def bake_module():
    spec = importlib.util.spec_from_file_location('bake_ui_font', ROOT / 'scripts' / 'bake-ui-font.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def subset(path, codepoints):
    from fontTools import subset as ftsubset
    from fontTools.ttLib import TTFont
    options = ftsubset.Options()
    options.flavor = 'woff2'
    options.layout_features = []    # no GPOS: kerning costs 5.6 KB the 64 KiB page cannot spare
    options.hinting = False
    options.desubroutinize = True
    options.name_IDs = [1, 2]          # family and style only
    options.notdef_outline = True
    font = TTFont(str(path), recalcTimestamp=False)
    subsetter = ftsubset.Subsetter(options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    out = io.BytesIO()
    ftsubset.save_font(font, out, options)
    return out.getvalue()


def block(fonts_dir):
    bake = bake_module()
    codepoints = bake.coverage(fonts_dir)
    rules = []
    for weight, name in ((400, bake.FILES[0]), (600, bake.FILES[1])):
        data = base64.b64encode(subset(fonts_dir / name, codepoints)).decode()
        rules.append(f"@font-face{{font-family:'{FAMILY}';font-weight:{weight};font-style:normal;font-display:block;"
                     f"src:url(data:font/woff2;base64,{data}) format('woff2')}}")
    head = (f'{BEGIN}: {len(codepoints)} code points of {bake.FILES[0]} and {bake.FILES[1]}, WOFF2, '
            'written by scripts/subset-phone-font.py; SIL OFL 1.1 */')
    return head + '\n' + '\n'.join(rules) + '\n' + END


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--page', type=Path, default=PAGE)
    ap.add_argument('--fonts', type=Path, default=ROOT / 'wfsource' / 'fonts' / 'atkinson-hyperlegible-next')
    ap.add_argument('--check', action='store_true', help='exit 1 if the page is stale')
    args = ap.parse_args()
    html = args.page.read_text(encoding='utf-8')
    new_block = block(args.fonts)
    if BEGIN in html:
        start = html.index(BEGIN)
        end = html.index(END, start) + len(END)
        updated = html[:start] + new_block + html[end:]
    else:
        at = html.index('<style>') + len('<style>')
        updated = html[:at] + '\n' + new_block + html[at:]
    if args.check:
        if updated != html:
            print(f'{args.page}: stale; run scripts/subset-phone-font.py', file=sys.stderr)
            sys.exit(1)
        print(f'{args.page}: current ({len(html.encode())} bytes)')
        return
    args.page.write_text(updated, encoding='utf-8')
    print(f'{args.page}: {len(updated.encode())} bytes (font block {len(new_block)} bytes)')


if __name__ == '__main__':
    if {'-h', '--help'} & set(sys.argv[1:]):
        print(__doc__.strip())
        sys.exit(0)
    main()
