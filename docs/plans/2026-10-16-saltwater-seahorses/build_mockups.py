#!/usr/bin/env python3
"""Build the seahorse plan's mockups and their PNG thumbnails.

Inlines the real Chromecast captures into tank-scene.html (the bundle must be
self-contained), then renders every mockup at 1440 x 900 with Playwright's
Chromium. Run from anywhere:

    python3 docs/plans/2026-10-16-saltwater-seahorses/build_mockups.py [-h]
"""
import base64
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CAPS = REPO / 'docs/diagnostics/baseline/generic-settings/plant-cast1-final'
# (html, hash shown in the PNG, settle time ms)
SHOTS = [('tail-rig.html', 'stem', 3500), ('tank-scene.html', 'two', 1500),
         ('settings.html', '', 600), ('poster.html', '', 600)]
BUDGET = 512 * 1024


def jpeg_uri(path, size=(1040, 585), quality=72):
    from PIL import Image
    buf = io.BytesIO()
    Image.open(path).convert('RGB').resize(size, Image.LANCZOS).save(buf, 'JPEG', quality=quality, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def build_scene():
    html = (HERE / 'tank-scene.tmpl').read_text()
    html = html.replace('{{SALT_JPG}}', jpeg_uri(CAPS / 'saltwater-urchin-screenshot.png'))
    html = html.replace('{{FRESH_JPG}}', jpeg_uri(CAPS / 'goby-rock-close-view-screenshot.png'))
    (HERE / 'tank-scene.html').write_text(html)


def shoot():
    from playwright.sync_api import sync_playwright
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, frag, wait in SHOTS:
            src = HERE / name
            if not src.exists():
                failures.append(f'{name}: missing')
                continue
            if src.stat().st_size > BUDGET:
                failures.append(f'{name}: {src.stat().st_size} bytes > 512 KB budget')
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme='dark')
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(src.as_uri() + (f'#{frag}' if frag else ''))
            page.wait_for_timeout(wait)
            page.screenshot(path=str(src.with_suffix('.png')))
            page.close()
            print(f'{name}: {src.stat().st_size // 1024} KB -> {src.with_suffix(".png").name}', 'errors: ' + '; '.join(errors) if errors else '')
            failures += [f'{name}: {e}' for e in errors]
        browser.close()
    return failures


if __name__ == '__main__':
    if {'-h', '--help'} & set(sys.argv[1:]):
        print(__doc__.strip())
        sys.exit(0)
    build_scene()
    bad = shoot()
    total = sum(f.stat().st_size for f in HERE.iterdir() if f.is_file())
    print(f'bundle: {total // 1024} KB of 8192 KB')
    if bad:
        print('FAIL:', *bad, sep='\n  ')
        sys.exit(1)
