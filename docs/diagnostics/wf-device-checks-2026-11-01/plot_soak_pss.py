#!/usr/bin/env python3
"""Render the cast1 Planted Tank PSS soak charts from coordinator evidence."""
import json
import sys
from datetime import datetime
from pathlib import Path


source, destination = map(Path, sys.argv[1:3])
timeline = json.loads(source.read_text())
samples = [item["result"] for item in timeline
           if item.get("kind") == "sample" and item.get("state") == "applied"]
if not samples:
    raise SystemExit("no successful process samples in timeline")

start = samples[0]["captured"]
end = samples[-1]["captured"]
points = [(item["captured"], item["total_pss_kb"] / 1024) for item in samples]
last_ten = [(t, pss) for t, pss in points if end - t <= 600]
low, high = min(pss for _, pss in last_ten), max(pss for _, pss in last_ten)
spread = high - low
limit = 4.0

W, H = 1040, 800
L, R = 90, 990
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         '<rect width="100%" height="100%" fill="#fff"/>',
         '<style>text{font-family:system-ui,sans-serif;fill:#18212b}.title{font-size:22px;font-weight:650}.axis{font-size:13px}.grid{stroke:#d9e0e7;stroke-width:1}.line{fill:none;stroke:#1677a8;stroke-width:2}.point{fill:#1677a8;opacity:.58}</style>',
         '<text x="90" y="38" class="title">Planted Tank soak — process PSS</text>',
         '<text x="90" y="61" class="axis">cast1 · PID 1324 · 235 successful samples · 51 tank starts / 50 reloads</text>']

def panel(y0, y1, values, xvalues, xmin, xmax, ymin, ymax, xticks, yticks, xlabel):
    for value, label in yticks:
        y = y1 - (value - ymin) * (y1 - y0) / (ymax - ymin)
        parts.append(f'<line x1="{L}" y1="{y:.1f}" x2="{R}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{L-12}" y="{y+4:.1f}" text-anchor="end" class="axis">{label}</text>')
    for value, label in xticks:
        x = L + (value - xmin) * (R - L) / (xmax - xmin)
        parts.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y1}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{y1+22}" text-anchor="middle" class="axis">{label}</text>')
    coords = []
    for xv, yv in zip(xvalues, values):
        x = L + (xv - xmin) * (R - L) / (xmax - xmin)
        y = y1 - (yv - ymin) * (y1 - y0) / (ymax - ymin)
        coords.append(f'{x:.1f},{y:.1f}')
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" class="point"/>')
    parts.append(f'<polyline points="{" ".join(coords)}" class="line"/>')
    parts.append(f'<text x="{(L+R)/2}" y="{y1+48}" text-anchor="middle" class="axis">{xlabel}</text>')
    parts.append(f'<text x="24" y="{(y0+y1)/2}" transform="rotate(-90 24 {(y0+y1)/2})" text-anchor="middle" class="axis">PSS (MiB)</text>')

minutes = [(t - start) / 60 for t, _ in points]
pss_values = [pss for _, pss in points]
duration = minutes[-1]
panel(102, 310, pss_values, minutes, 0, duration, 70, 130,
      [(v, str(v)) for v in range(0, int(duration // 10 * 10) + 1, 10)],
      [(v, v) for v in range(70, 131, 10)], "Minutes since first tank marker")
parts.append('<text x="90" y="365" class="title" style="font-size:18px">Final ten minutes</text>')
last_minutes = [(t - (end - 600)) / 60 for t, _ in last_ten]
last_values = [pss for _, pss in last_ten]
ymin, ymax = 78, 92
panel(395, 570, last_values, last_minutes, 0, 10, ymin, ymax,
      [(v, str(v)) for v in range(0, 11, 2)],
      [(v, v) for v in range(78, 93, 2)], "Minutes within final ten-minute window")

parts.append('<text x="90" y="645" class="title" style="font-size:18px">Final-window spread versus criterion</text>')
bar_left, bar_right = 250, 900
bar_width = bar_right - bar_left
scale = bar_width / 8
for value in range(0, 9, 2):
    x = bar_left + value * scale
    parts.append(f'<line x1="{x}" y1="675" x2="{x}" y2="755" class="grid"/>')
    parts.append(f'<text x="{x}" y="774" text-anchor="middle" class="axis">{value} MiB</text>')
parts.append('<text x="90" y="700" class="axis">Measured spread</text>')
parts.append(f'<rect x="{bar_left}" y="682" width="{spread*scale:.1f}" height="24" rx="3" fill="#c45a22"/>')
parts.append(f'<text x="{bar_left + spread*scale + 10:.1f}" y="700" class="axis">{spread:.2f} MiB</text>')
parts.append('<text x="90" y="740" class="axis">4 MiB limit</text>')
parts.append(f'<rect x="{bar_left}" y="722" width="{limit*scale:.1f}" height="24" rx="3" fill="#34875b"/>')
parts.append(f'<text x="{bar_left + limit*scale + 10:.1f}" y="740" class="axis">{limit:.2f} MiB</text>')
parts.append('<text x="90" y="795" class="axis">PSS fell over the full run; the threshold is a spread check, and the final-window spread exceeds it.</text>')
parts.append('</svg>')
destination.write_text("\n".join(parts) + "\n")
