#!/usr/bin/env python3
"""Render the Chromecast capture report with embedded screenshot evidence."""
import base64
import re
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/diagnostics/cast2-black-capture-investigation.md'
body = markdown.markdown(REPORT.read_text(), extensions=['fenced_code', 'tables'])

def embed(match):
    image = REPORT.parent / match.group(1)
    return 'src="data:image/png;base64,' + base64.b64encode(image.read_bytes()).decode() + '"'

body = re.sub(r'src="([^\"]+\.png)"', embed, body)
css = '''body{font:17px/1.55 system-ui,sans-serif;color:#20252a;background:#f3f5f7;margin:0}
main{max-width:1100px;margin:30px auto;padding:30px;background:white}
img{display:block;width:100%;height:auto;background:#222;border:1px solid #555}
img.blank-capture{width:160px;max-width:100%;margin:12px 0}
h1,h2,h3{line-height:1.2}h2{margin-top:2em}a{color:#125a9c}
pre{padding:16px;background:#eef2f6;overflow:auto}code{font-size:.9em}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd3db;padding:12px;text-align:left;vertical-align:top}'''
REPORT.with_suffix('.html').write_text(
    '<!doctype html><html lang="en"><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>Chromecast screenshot investigation</title><style>' + css + '</style><main>' + body + '</main></html>')
print(REPORT.with_suffix('.html'))
