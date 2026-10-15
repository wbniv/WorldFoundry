#!/usr/bin/env python3
"""Export the seahorse poster with Playwright Chromium: one A3 PDF page, a 300 DPI PNG and a layout review.

    python3 docs/reference/seahorse-biomechanics-poster/make_poster.py
    python3 docs/reference/seahorse-biomechanics-poster/export_poster.py [--out-dir DIR]

Reads DIR/poster.html (default: this directory) and writes seahorse-biomechanics-a3.pdf, poster.png and
layout-review.json beside it. Fails if any panel or the footer overflows the page.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDF_NAME = 'seahorse-biomechanics-a3.pdf'
DPI = 300

REVIEW_JS = '''() => {
  const sheet = document.querySelector('.page'), box = sheet.getBoundingClientRect();
  const pad = parseFloat(getComputedStyle(sheet).paddingBottom);
  const foot = document.getElementById('panel-src'), last = foot.lastElementChild.getBoundingClientRect();
  const panels = [...document.querySelectorAll('.panel')].map(e => ({id: e.id,
      clientHeight: e.clientHeight, scrollHeight: e.scrollHeight, overflowing: e.scrollHeight > e.clientHeight + 1}));
  const sizes = [];
  for (const el of document.querySelectorAll('.page *')) {
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (own) sizes.push(parseFloat(getComputedStyle(el).fontSize));
  }
  const pxPerMm = 96 / 25.4;
  return {
    page_mm: {width: +(box.width / pxPerMm).toFixed(2), height: +(box.height / pxPerMm).toFixed(2)},
    page_px: {width: box.width, height: box.height},
    content_bottom_limit_px: box.bottom - pad - box.top,
    footer_last_bottom_px: last.bottom - box.top,
    footer_overflowing: last.bottom > box.bottom - pad + 1,
    document_overflowing: sheet.scrollHeight > sheet.clientHeight + 1,
    panels,
    min_font_px: Math.min(...sizes),
    min_font_pt: +(Math.min(...sizes) * 0.75).toFixed(2),
    fit: document.body.getAttribute('data-fit'),
  };
}'''


def export(out_dir: Path = HERE) -> dict:
    from playwright.sync_api import sync_playwright
    out_dir = Path(out_dir)
    html = out_dir / 'poster.html'
    pdf = out_dir / PDF_NAME
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 1700})
        page.goto(html.as_uri())
        page.evaluate('document.fonts.ready')
        page.wait_for_function("document.body.getAttribute('data-fit') !== null")
        review = page.evaluate(REVIEW_JS)
        review['overflowing'] = bool(review['document_overflowing'] or review['footer_overflowing']
                                     or any(x['overflowing'] for x in review['panels']))
        (out_dir / 'layout-review.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')
        if review['overflowing'] or review['fit'] != 'ok':
            browser.close()
            raise SystemExit(f'export_poster: layout overflows, see {out_dir / "layout-review.json"}')
        page.pdf(path=str(pdf), prefer_css_page_size=True, print_background=True, display_header_footer=False)
        browser.close()
    render_png(pdf, out_dir / 'poster.png')
    return review


def render_png(pdf: Path, png: Path, dpi: int = DPI):
    """The preview is the PDF itself, rasterised at 300 DPI, so it shows exactly what prints."""
    if not shutil.which('pdftoppm'):
        raise SystemExit('export_poster: pdftoppm not found (poppler-utils)')
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / 'page'
        subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-singlefile', str(pdf), str(stem)], check=True)
        Image.open(stem.with_suffix('.png')).convert('RGB').save(png, dpi=(dpi, dpi), optimize=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out-dir', type=Path, default=HERE)
    args = ap.parse_args(argv)
    review = export(args.out_dir)
    print(json.dumps({k: review[k] for k in ('page_mm', 'min_font_pt', 'overflowing', 'fit')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
