#!/usr/bin/env python3
"""Export poster.html to a one-page A3 PDF and a PNG with headless Chrome, and check the layout.

Playwright is not installed on every host, so this drives `google-chrome --headless` directly.
It fails if the PDF is not exactly one A3 page (297 x 420 mm), which is how overflow shows up:
the page is a fixed-height box, so too much content runs onto a second page.
"""
from pathlib import Path
import json
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PDF = HERE/'sea-stars-biomechanics-a3.pdf'
PNG = HERE/'poster'


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


chrome = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
if not chrome:
    sys.exit('no Chrome or Chromium on PATH')
with tempfile.TemporaryDirectory(dir=HERE) as profile:        # a profile inside $HOME: snap browsers cannot read /tmp
    subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', f'--user-data-dir={profile}',
                    '--no-pdf-header-footer', f'--print-to-pdf={PDF}', (HERE/'poster.html').as_uri()],
                   check=True, capture_output=True, timeout=120)
info = run('pdfinfo', str(PDF))
pages = int(re.search(r'^Pages:\s+(\d+)', info, re.M).group(1))
size = re.search(r'^Page size:\s+([\d.]+) x ([\d.]+) pts', info, re.M)
mm = [round(float(v)/72*25.4, 1) for v in size.groups()]
review = {'pages': pages, 'page_mm': mm}
(HERE/'layout-review.json').write_text(json.dumps(review, indent=2)+'\n')
assert pages == 1, f'the poster runs onto {pages} pages: {review}'
assert abs(mm[0]-297) < 1.5 and abs(mm[1]-420) < 1.5, review
run('pdftoppm', '-png', '-r', '90', '-singlefile', str(PDF), str(PNG))
# The last inked row must leave a bottom margin: the page clips, so overflow can hide inside the padding.
from PIL import Image
im = Image.open(str(PNG)+'.png').convert('RGB')
w, h = im.size
paper = im.getpixel((2, 2))
def inked(p):      # not the paper colour and not the white sliver the PDF's extra 0.2 mm leaves
    return all(max(abs(a-b) for a, b in zip(p, ref)) > 14 for ref in (paper, (255, 255, 255)))
last = max(y for y in range(h) if any(inked(im.getpixel((x, y))) for x in range(0, w, 3)))
review['bottom_margin_mm'] = round((h-last)/h*420, 1)
(HERE/'layout-review.json').write_text(json.dumps(review, indent=2)+'\n')
assert review['bottom_margin_mm'] >= 6, f'content too close to the bottom edge: {review}'
print(review)
