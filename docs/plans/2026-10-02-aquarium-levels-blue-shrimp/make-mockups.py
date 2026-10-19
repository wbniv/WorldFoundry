#!/usr/bin/env python3
"""Generate reviewable SVG concepts and a browser gallery. No engine captures."""
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent


def svg(body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 760" role="img">
<defs><linearGradient id="water" x2="0" y2="1"><stop stop-color="#15495c"/><stop offset="1" stop-color="#082735"/></linearGradient>
<linearGradient id="blue"><stop stop-color="#36c5ff"/><stop offset=".55" stop-color="#126bdf"/><stop offset="1" stop-color="#143688"/></linearGradient></defs>
<style>text{{font-family:Arial,sans-serif;fill:#e7f4fa}} .sub{{fill:#9ab4c2;font-size:18px}} .label{{font-size:22px;font-weight:bold}} .line{{stroke:#75a4b6;stroke-width:2;fill:none}}</style>
<rect width="1280" height="760" fill="#0e1726"/>{body}</svg>'''


def shrimp(x, y, size=1, flip=False):
    return f'''<g transform="translate({x} {y}) scale({-size if flip else size} {size})">
<ellipse cx="0" cy="12" rx="32" ry="5" fill="#00121d" opacity=".35"/>
<path d="M-29 0 Q-10 -19 12 -12 Q25 -10 28 0 L20 5 Q-4 0 -22 8 Z" fill="url(#blue)" stroke="#53c6ff" stroke-width="1"/>
<path d="M-29 0 L-42 -4 L-38 8 L-26 8" fill="#227bec"/>
<path d="M-19 -8 L-15 3 M-9 -12 L-5 1 M2 -14 L6 1" stroke="#91dfff" opacity=".55" fill="none"/>
<path d="M-9 3 L-13 13 M0 3 L-2 14 M9 3 L13 14 M18 3 L24 12" stroke="#4996de" stroke-width="2"/>
<circle cx="24" cy="-8" r="2.8" fill="#051222"/>
<path d="M27 -6 Q45 -29 63 -24 M27 -3 Q49 -15 68 -8" fill="none" stroke="#77cfff" stroke-width="1.4"/>
</g>'''


menu = '''<text x="110" y="115" font-size="42" font-weight="bold">WF Aquarium</text>
<text x="110" y="160" class="sub">Choose a tank</text>
<rect x="110" y="232" width="1060" height="100" rx="8" fill="#18283d"/>
<text x="155" y="291" font-size="30">Clownfish Reef</text><text x="1120" y="291" class="sub" text-anchor="end">01</text>
<rect x="110" y="356" width="1060" height="100" rx="8" fill="#23406b"/>
<rect x="110" y="356" width="7" height="100" fill="#56d364"/>
<text x="155" y="415" font-size="30">Blue Shrimp</text><text x="1120" y="415" class="sub" text-anchor="end">02</text>
<text x="110" y="504" class="sub">2 / 2</text>
<text x="110" y="644" class="sub">D-pad choose · OK starts · Hold Back in a tank for this menu</text>
<text x="110" y="710" font-size="15" fill="#6e8da4">LAYOUT MOCKUP · Reuses the SMB selector; no new thumbnail UI</text>'''
(HERE / "selector.svg").write_text(svg(menu))

rng = random.Random(24)
scene = '''<text x="60" y="65" font-size="34" font-weight="bold">Blue Shrimp — whole-tank view</text>
<text x="60" y="98" class="sub">Proposed planted tank · 24 residents · wide foreground for readable movement</text>
<rect x="60" y="135" width="1160" height="505" rx="12" fill="url(#water)" stroke="#789fae" stroke-width="8"/>
<rect x="67" y="165" width="1146" height="4" fill="#7edcdd" opacity=".45"/>
<path d="M67 580 Q300 560 500 580 T930 577 L1213 570 L1213 632 L67 632 Z" fill="#b2aa86"/>
<path d="M330 573 Q450 530 556 483 Q655 437 763 346 M555 483 Q553 378 481 311 M682 408 L920 408" stroke="#614c39" stroke-width="32" stroke-linecap="round" fill="none"/>
<path d="M344 565 Q484 488 570 478" stroke="#88924f" stroke-width="18" fill="none"/>
<path d="M730 573 L749 516 L789 487 L854 495 L902 549 L911 579 Z" fill="#35454c"/>
<path d="M749 516 L789 487 L854 495 L827 525 Z" fill="#52666b"/>
'''
for x in [130, 160, 195, 1020, 1060, 1100, 1140]:
    height = rng.randint(140, 280)
    scene += f'<path d="M{x} 580 Q{x-45} {580-height//2} {x+5} {580-height}" stroke="#477d58" stroke-width="12" fill="none"/>'
    for j in range(4):
        y = 550-j*height/5
        scene += f'<ellipse cx="{x+(-16 if j%2 else 16)}" cy="{y}" rx="24" ry="9" fill="#53865a" transform="rotate({-30 if j%2 else 30} {x} {y})"/>'
for i in range(24):
    if i < 15:
        x, y = 155+i*65+rng.randint(-15, 15), rng.randint(574, 610)
    elif i < 20:
        x, y = 415+(i-15)*76, 528-(i-15)*37
    else:
        x, y = rng.randint(260, 970), rng.randint(260, 400)
    scene += shrimp(x, y, rng.uniform(.55, .95), bool(i%2))
scene += '''<circle cx="805" cy="585" r="48" stroke="#d8f7ff" stroke-width="2" fill="none" stroke-dasharray="5 5"/>
<text x="60" y="694" class="sub">Warm substrate + green plants contrast with cobalt bodies. Close-up activates near the grazing patch.</text>
<text x="60" y="729" font-size="15">SCENE CONCEPT · Illustrated geometry; actual rig, lighting and visibility need engine verification</text>'''
(HERE / "tank.svg").write_text(svg(scene))

diagram = '''<text x="60" y="65" font-size="34" font-weight="bold">From selection to a living colony</text>
<text x="60" y="98" class="sub">Existing bundle menu + independent content + shared shrimp meshes</text>'''


def box(x, y, w, h, title, subtitle, color="#18334a"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{color}" stroke="#46718b"/><text x="{x+20}" y="{y+36}" class="label">{title}</text><text x="{x+20}" y="{y+67}" class="sub">{subtitle}</text>'


diagram += box(60, 145, 330, 96, "Aquarium menu", "shell-menu.fth + MENU")
diagram += box(460, 132, 355, 96, "0 · Clownfish Reef", "Existing standalone level")
diagram += box(460, 260, 355, 96, "1 · Blue Shrimp", "New standalone level", "#173e55")
diagram += '<path d="M390 182 H425 V175 H460 M425 182 V305 H460" class="line"/>'
diagram += box(880, 260, 340, 96, "Director tick", "Colony decisions + rig poses")
diagram += '<path d="M815 305 H880 M1050 356 V407" class="line"/>'
diagram += box(850, 407, 370, 110, "Graze → Crawl → Swim", "Settle to graze · dart → escape")
diagram += '<path d="M460 340 H425 V383 H70 V250" class="line"/><text x="80" y="372" class="sub">Backspace / held Back returns to menu</text>'
diagram += '<text x="60" y="457" class="label">Proposed compact rig</text>'
diagram += shrimp(285, 559, 3.1)
diagram += '<path d="M212 544 L150 490 M306 524 L430 484 M318 594 L454 640 M427 511 L584 566" class="line"/>'
diagram += '<text x="65" y="482" class="sub">Abdomen / tail</text><text x="422" y="474" class="sub">Body / head</text><text x="451" y="669" class="sub">Paired leg groups</text><text x="589" y="574" class="sub">Antennae</text>'
diagram += '<text x="850" y="568" class="sub">24 shrimp share mesh assets.</text><text x="850" y="601" class="sub">Each has its own pose and phase.</text><text x="850" y="634" class="sub">Player: one invisible collision hull.</text><text x="850" y="667" class="sub">23 residents: visual actors only.</text>'
diagram += '<text x="60" y="729" font-size="15">DESIGN DIAGRAM · Final part count and device budget are measured in the rig spike</text>'
(HERE / "flow-and-rig.svg").write_text(svg(diagram))

sections = [("selector", "1. Tank selector", "Use the SMB layout and navigation. Blue Shrimp is the first added entry."),
            ("tank", "2. Blue Shrimp scene", "A composition concept, not an engine screenshot. Foreground grazers, wood routes and short swims keep the colony visible."),
            ("flow-and-rig", "3. Level flow and shrimp rig", "The same menu loads independent levels. The colony has its own behavior; it shares meshes, not animation phases.")]
body = "".join(f'<section id="{name}"><h2>{title}</h2><p>{desc}</p>{(HERE / (name+".svg")).read_text()}</section>' for name, title, desc in sections)
(HERE / "mockups.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aquarium levels — visual plan</title><style>body{margin:0;background:#09131e;color:#e7f4fa;font:18px/1.6 system-ui}main{max-width:1280px;margin:auto;padding:30px}h1{margin-bottom:8px}p{color:#a7c2d0}nav{display:flex;gap:24px;flex-wrap:wrap}a{color:#76cfff}section{margin:50px 0}svg{display:block;width:100%;height:auto;border-radius:14px}h2{margin-bottom:4px}</style><main><h1>Aquarium levels · visual plan</h1><p>Review concepts for the existing tank + Blue Shrimp. These are proposed visuals, not implementation evidence.</p><nav><a href="#selector">Selector</a><a href="#tank">Blue Shrimp tank</a><a href="#flow-and-rig">Flow + rig</a></nav>'''+body+'</main></html>')
print(HERE / "mockups.html")
