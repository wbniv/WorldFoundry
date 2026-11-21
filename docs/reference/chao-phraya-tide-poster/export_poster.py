#!/usr/bin/env python3
"""Export the tide poster with Playwright Chromium: one A3 PDF page, a 300 DPI PNG and a layout review.

    python3 docs/reference/chao-phraya-tide-poster/make_poster.py
    python3 docs/reference/chao-phraya-tide-poster/export_poster.py [--out-dir DIR]

Reads DIR/poster.html (default: this directory) and writes chao-phraya-tide-a3.pdf, poster.png and layout-review.json
beside it. Fails if any panel, the header or the footer overflows the page. It reuses the seahorse poster's exporter
(same page structure), changing only the PDF name, so one fix there is one fix here.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEAHORSE = HERE.parent / 'seahorse-biomechanics-poster' / 'export_poster.py'
PDF_NAME = 'chao-phraya-tide-a3.pdf'


def load_exporter():
    spec = importlib.util.spec_from_file_location('seahorse_export_poster', SEAHORSE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.PDF_NAME = PDF_NAME
    return mod


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out-dir', type=Path, default=HERE)
    args = ap.parse_args(argv)
    review = load_exporter().export(args.out_dir)
    print(json.dumps({k: review[k] for k in ('page_mm', 'min_font_pt', 'overflowing', 'fit')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
