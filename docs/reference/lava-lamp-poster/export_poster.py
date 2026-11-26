#!/usr/bin/env python3
"""Export the lava lamp poster with Playwright Chromium: one A3 PDF page, a 300 DPI PNG and a layout review.

    python3 docs/reference/lava-lamp-poster/make_poster.py [--draft]
    python3 docs/reference/lava-lamp-poster/export_poster.py [--out-dir DIR]

Reads DIR/poster.html (default: this directory) and writes the PDF, poster.png and layout-review.json beside it. A review
draft (make_poster.py --draft, <body data-draft="1">) exports to lava-lamp-review-draft-a3.pdf, which is not committed;
the approved poster exports to lava-lamp-a3.pdf. Fails if any panel, the header or the footer overflows the page. It reuses
the seahorse poster's exporter (same page structure), changing only the PDF name, so one fix there is one fix here.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEAHORSE = HERE.parent / 'seahorse-biomechanics-poster' / 'export_poster.py'
PDF_NAME = 'lava-lamp-a3.pdf'
DRAFT_PDF_NAME = 'lava-lamp-review-draft-a3.pdf'


def pdf_name(html: Path) -> str:
    return DRAFT_PDF_NAME if 'data-draft="1"' in html.read_text(encoding='utf-8') else PDF_NAME


def load_exporter(name):
    spec = importlib.util.spec_from_file_location('seahorse_export_poster', SEAHORSE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.PDF_NAME = name
    return mod


def export(out_dir: Path = HERE) -> dict:
    out_dir = Path(out_dir)
    return load_exporter(pdf_name(out_dir / 'poster.html')).export(out_dir)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out-dir', type=Path, default=HERE)
    args = ap.parse_args(argv)
    review = export(args.out_dir)
    print(json.dumps({k: review[k] for k in ('page_mm', 'min_font_pt', 'overflowing', 'fit')}), pdf_name(args.out_dir / 'poster.html'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
