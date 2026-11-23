"""Render the actual camera spline as a self-contained plan diagram."""
from pathlib import Path
import math
import model

out = Path(__file__).resolve().parents[2]/'docs/plans/2026-11-24-lighthouse/camera-path.svg'
colors = ('#ffd47a','#f1a77e','#d193d0','#90b6e7','#7ed8ce','#a7d88d')
parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="610" viewBox="0 0 1100 610" role="img" aria-labelledby="title desc">
<title id="title">Lighthouse camera path over a minute</title><desc id="desc">An overhead plot and an elevation plot of the same six-point smooth looping camera path. The camera stays on the front side of the sea, moving right then left while looking at the lighthouse.</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L7,3 z" fill="#e8f3f8"/></marker></defs>
<rect width="1100" height="610" rx="18" fill="#0c1725"/>
<g fill="#eaf4fa" font-family="sans-serif"><text x="35" y="44" font-size="26" font-weight="bold">The camera's complete 60-second path</text><text x="52" y="88" font-size="20">Overhead</text><text x="620" y="88" font-size="20">Elevation</text></g>
<circle cx="260" cy="208" r="98" fill="#153852" stroke="#538098" stroke-width="2"/>
<circle cx="260" cy="208" r="13" fill="#d15d42"/><circle cx="260" cy="208" r="5" fill="#ffcf77"/>
<text x="280" y="213" font-family="sans-serif" font-size="14" fill="#d4e5ef">lighthouse / look target</text>
<text x="260" y="95" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#aac4d5">12</text>
<line x1="600" y1="479" x2="1060" y2="479" stroke="#4a6171" stroke-width="2"/>
<circle cx="810" cy="454" r="6" fill="#ffcf77"/><text x="826" y="459" font-family="sans-serif" font-size="14" fill="#d4e5ef">look target</text>
<text x="604" y="503" font-family="sans-serif" font-size="14" fill="#a8bfcd">sea level</text>
''']

def top(p): return 260+14*p[0], 208-14*p[1]
def side(p): return 810+30*p[0], 479-14*p[2]

for transform in (top,side):
    for segment in range(6):
        pts = [transform(model.camera_pose(segment*10 + step/10)) for step in range(101)]
        path = 'M '+' L '.join(f'{x:.1f} {y:.1f}' for x,y in pts)
        parts.append(f'<path d="{path}" fill="none" stroke="{colors[segment]}" stroke-width="4"/>')
        x,y=pts[50]; px,py=pts[45]
        angle=math.atan2(y-py,x-px)
        points=[(x+7*math.cos(angle),y+7*math.sin(angle)),
                (x+6*math.cos(angle+2.4),y+6*math.sin(angle+2.4)),
                (x+6*math.cos(angle-2.4),y+6*math.sin(angle-2.4))]
        parts.append('<polygon points="'+' '.join(f'{a:.1f},{b:.1f}' for a,b in points)+f'" fill="{colors[segment]}"/>')
    for i,key in enumerate(model.CAMERA_KEYS):
        x,y=transform(key)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{colors[i]}" stroke="#08111a" stroke-width="2"/>')
        dx,dy = ((-20,25),(8,26),(10,-10),(8,-13),(-50,-10),(-60,25))[i]
        parts.append(f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" font-family="sans-serif" font-size="15" fill="#eef7fc">:{i*10:02d}</text>')
parts.append('''<g font-family="sans-serif" fill="#bdced9" font-size="15"><text x="52" y="548">The path stays in front of the clock; it does not circle the island.</text><text x="52" y="575">It follows the smooth curve through :00 → :10 → :20 → :30 → :40 → :50 → :00.</text><text x="620" y="548">The camera continuously looks toward the tower base.</text><text x="620" y="575">Camera drift Off holds the :00 view.</text></g></svg>''')
out.write_text('\n'.join(parts)+'\n')
print(out)
