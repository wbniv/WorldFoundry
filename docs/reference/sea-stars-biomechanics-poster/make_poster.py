#!/usr/bin/env python3
"""Original vector diagrams and the portrait A3 Sea Stars research poster.

Every biology claim comes from ../sea-stars-research.md (checked 2026-11-20) or the one extra
source it was extended with here; whatever is game design says so on the poster. The engine
numbers are measured on cast1 (docs/diagnostics/sea-stars-cast1-acceptance-2026-11-20/).
"""
from pathlib import Path
from html import escape
import math

HERE = Path(__file__).resolve().parent
INK = '#263c48'
TEAL = '#167e83'
BLUE = '#3f6fb5'
ORANGE = '#db9a54'
ARM = '#6f9ad6'
SAND = '#e5cf9e'


def text(x, y, value, size=22, color=INK, anchor='start', weight='normal'):
    return (f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{escape(value)}</text>')


def svg(body, height=300, title='Sea star schematic', background='#edf3f1'):
    rect = f'<rect width="1000" height="{height}" rx="18" fill="{background}"/>' if background else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {height}" role="img">'
            f'<title>{escape(title)}</title>{rect}{body}</svg>')


def line(x1, y1, x2, y2, color=TEAL, width=3, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" stroke-width="{width}" fill="none"{d}/>'


# ---------------------------------------------------------------------------------------------
# 01 Tube-foot cycle: side view of an arm on its tube feet, four beats.
def gait():
    out = []
    labels = ['1 Reach', '2 Attach', '3 Pull', '4 Release']
    for k, label in enumerate(labels):
        cx = 125 + k*250
        shift = 26 if k >= 2 else 0
        out.append(text(cx-108, 34, label, 22))
        out.append(f'<path d="M{cx-112} 196 H{cx+112}" stroke="#879b98" stroke-width="10"/>')
        # footprints left on the ground by earlier contacts
        if k >= 2:
            out.append(f'<ellipse cx="{cx-55}" cy="196" rx="11" ry="3.5" fill="{ORANGE}"/>')
        if k == 3:
            out.append(f'<ellipse cx="{cx-29}" cy="196" rx="11" ry="3.5" fill="{ORANGE}"/>')
        out.append(f'<rect x="{cx-92+shift}" y="86" width="184" height="46" rx="22" fill="{ARM}" stroke="#4a73ad" stroke-width="3"/>')
        # three tube feet: rear, middle, leading
        for j, fx in enumerate((-52, 0, 52)):
            x0 = cx + fx + shift
            reach = k == 0 and j == 2
            release = k == 3 and j == 0
            if k == 2:
                x1, y1 = x0 - 26, 186      # planted feet stretch backwards as the body moves on
            elif reach:
                x1, y1 = x0 + 34, 170      # leading foot extended, not yet touching
            elif release:
                x1, y1 = x0 - 20, 168      # rear foot lifts off
            else:
                x1, y1 = x0, 186
            out.append(f'<path d="M{x0} 132 Q{(x0+x1)/2+6} 160 {x1} {y1}" fill="none" stroke="{TEAL}" stroke-width="7" stroke-linecap="round"/>')
            out.append(f'<ellipse cx="{x1}" cy="{y1}" rx="12" ry="4.5" fill="#cfe3d6" stroke="{TEAL}" stroke-width="2"/>')
            if k == 1 and j == 2:
                out.append(f'<circle cx="{x1}" cy="{y1}" r="19" fill="none" stroke="{ORANGE}" stroke-width="3"/>')
        if k == 2:
            out.append(f'<path d="M{cx-40} 62 H{cx+48} l-13 -9 m13 9 l-13 9" stroke="{TEAL}" stroke-width="4" fill="none"/>')
    out.append(text(30, 244, 'Sticky footprints stay on the ground (orange). Four beats are an animation abstraction.', 20))
    return svg(''.join(out), 262, 'Schematic tube-foot attach, pull and release cycle')


# ---------------------------------------------------------------------------------------------
# 02 Eye at the arm tip: side view of a raised leading arm looking at the reef.
def eye():
    out = [f'<path d="M30 226 H970" stroke="#879b98" stroke-width="10"/>']
    out.append('<path d="M760 226 L770 120 Q800 78 850 96 Q905 84 935 130 L945 226Z" fill="#8f8aa8" stroke="#6b6585" stroke-width="3"/>')
    out.append(text(850, 262, 'Reef', 22, anchor='middle'))
    out.append(f'<path d="M80 196 L400 196 Q500 196 548 150 L575 118" stroke="#4a73ad" stroke-width="52" stroke-linecap="round" fill="none"/>')
    out.append(f'<path d="M80 196 L400 196 Q500 196 548 150 L575 118" stroke="{ARM}" stroke-width="46" stroke-linecap="round" fill="none"/>')
    for x in range(110, 440, 46):
        out.append(f'<path d="M{x} 219 q4 8 -6 9" stroke="{TEAL}" stroke-width="5" fill="none" stroke-linecap="round"/>')
    out.append('<circle cx="580" cy="110" r="10" fill="#d9453b" stroke="#fff" stroke-width="3"/>')
    out.append(line(595, 106, 765, 118, '#d9453b', 3, '9 8'))
    out.append(text(40, 52, 'Eyespot at the arm tip: compound eyes', 24))
    out.append(line(420, 58, 566, 98, TEAL, 2))
    out.append(text(612, 62, 'Sight line to the reef', 22, '#b6362d'))
    out.append(text(40, 262, 'The raised tip is this drawing, not a measurement.', 21, '#4a5d68'))
    return svg(''.join(out), 280, 'Blue sea star with an eyespot at the raised arm tip looking at a reef')

# ---------------------------------------------------------------------------------------------
# 03 Burying in sand: three beats in side view.
def bury():
    out = []
    for k, label in enumerate(['Crawling', 'Digging in', 'Buried']):
        cx = 167 + k*333
        out.append(text(cx, 34, label, 22, anchor='middle'))
        y = [136, 160, 190][k]
        out.append(f'<ellipse cx="{cx}" cy="{y}" rx="104" ry="19" fill="#ebe7da" stroke="#9a9684" stroke-width="3"/>')
        top = 172
        out.append(f'<path d="M{cx-150} {top} Q{cx-60} {top-8} {cx} {top-2} T{cx+150} {top} V232 H{cx-150}Z" fill="{SAND}"/>')
        for g in range(9):
            out.append(f'<circle cx="{cx-130+g*32}" cy="{196+(g*13)%28}" r="3" fill="#c9b27a"/>')
        if k == 2:
            out.append(f'<path d="M{cx-80} {top-3} Q{cx} {top-13} {cx+80} {top-3}" stroke="#a89363" stroke-width="3" fill="none" stroke-dasharray="6 6"/>')
    out.append(text(30, 258, 'Burying is real. The dive trigger and its timing are authored for play.', 20))
    return svg(''.join(out), 276, 'Sand-sifting star crawling, digging in and buried')

# ---------------------------------------------------------------------------------------------
# 04 Brittle star: top view, rowing arms; side view of a raised distal segment.
def brittle():
    out = []
    cx, cy = 235, 150
    out.append(text(30, 38, 'TOP VIEW · ROWING', 22))
    paths = [
        f'M{cx} {cy} C{cx+70} {cy-50} {cx+140} {cy-10} {cx+200} {cy-60}',
        f'M{cx} {cy} C{cx+60} {cy+35} {cx+140} {cy+55} {cx+205} {cy+95}',
        f'M{cx} {cy} C{cx-30} {cy+70} {cx-70} {cy+90} {cx-105} {cy+125}',
        f'M{cx} {cy} C{cx-75} {cy+25} {cx-140} {cy+10} {cx-205} {cy+45}',
        f'M{cx} {cy} C{cx-55} {cy-55} {cx-110} {cy-55} {cx-170} {cy-100}',
    ]
    for d in paths:
        out.append(f'<path d="{d}" stroke="#4d7d57" stroke-width="12" fill="none" stroke-linecap="round"/>')
        out.append(f'<path d="{d}" stroke="#9cc7a4" stroke-width="7" fill="none" stroke-linecap="round" stroke-dasharray="9 4"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="34" fill="#9cc7a4" stroke="#4d7d57" stroke-width="4"/>')
    for i in range(5):
        a = i*2*math.pi/5-math.pi/2
        out.append(f'<circle cx="{cx+16*math.cos(a):.1f}" cy="{cy+16*math.sin(a):.1f}" r="4" fill="#6a9e74"/>')
    out.append(f'<path d="M{cx+222} {cy-68} H{cx+285} l-12 -9 m12 9 l-12 9" stroke="{ORANGE}" stroke-width="5" fill="none"/>')
    out.append(f'<path d="M{cx+228} {cy+98} H{cx+285} l-12 -9 m12 9 l-12 9" stroke="{ORANGE}" stroke-width="5" fill="none"/>')
    out.append(text(cx+222, cy-84, 'leading arms', 20, '#a56a22'))
    out.append(text(30, 302, 'Arms coordinate; which arm leads can change.', 20))
    out.append(text(640, 38, 'SIDE VIEW · TIP LIFTED', 22))
    out.append('<path d="M620 232 H970" stroke="#879b98" stroke-width="10"/>')
    d = 'M640 214 C700 214 740 214 790 212 C845 208 880 180 905 150 C925 126 945 126 952 144'
    out.append(f'<path d="{d}" stroke="#4d7d57" stroke-width="16" fill="none" stroke-linecap="round"/>')
    out.append(f'<path d="{d}" stroke="#9cc7a4" stroke-width="10" fill="none" stroke-linecap="round" stroke-dasharray="11 4"/>')
    out.append(text(640, 272, 'Distal segments bend upward', 20))
    return svg(''.join(out), 316, 'Brittle star with S-bent arms rowing and a lifted arm tip')

# ---------------------------------------------------------------------------------------------
# 05 The tank's five planes and the lap the autopilot walks (surface ids 0 sand, 1 front, 2 right, 3 back, 4 left).
def planes():
    out = []
    F = (80, 150, 500, 370)                 # front glass
    dx, dy = 110, -90                       # depth
    fx0, fy0, fx1, fy1 = F
    bx0, by0, bx1, by1 = fx0+dx, fy0+dy, fx1+dx, fy1+dy
    poly = lambda pts, fill, op=1: f'<polygon points="{" ".join(f"{x},{y}" for x, y in pts)}" fill="{fill}" fill-opacity="{op}" stroke="#7fa3a8" stroke-width="2.5"/>'
    out.append(poly([(fx0, fy1), (fx1, fy1), (bx1, by1), (bx0, by1)], '#d9c28a', .55))                # floor
    out.append(poly([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)], '#7fa3a8', .18))                # back
    out.append(poly([(fx1, fy0), (bx1, by0), (bx1, by1), (fx1, fy1)], '#7fa3a8', .28))                # right
    out.append(poly([(fx0, fy0), (bx0, by0), (bx0, by1), (fx0, fy1)], '#7fa3a8', .28))                # left
    out.append(poly([(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)], '#9fd0d6', .16))                # front
    lab = lambda x, y, t: text(x, y, t, 31, '#e8f1ef', 'middle', 'bold')
    out += [lab(290, 320, '0 sand'), lab(290, 200, '1 front'), lab(560, 190, '2 right'), lab(400, 130, '3 back'), lab(150, 205, '4 left')]
    # the lap: sand -> front glass -> up -> across -> right wall -> back -> down
    route = 'M300 345 L300 232 L430 232 L540 214 L520 120 L420 150'
    out.append(f'<path d="{route}" stroke="{ORANGE}" stroke-width="6" fill="none" stroke-dasharray="11 9" stroke-linecap="round"/>')
    out.append(f'<path d="M420 150 l-3 -22 m3 22 l22 -4" stroke="{ORANGE}" stroke-width="6" fill="none" stroke-linecap="round"/>')
    out.append(f'<circle cx="300" cy="345" r="13" fill="{ARM}" stroke="#faf7ee" stroke-width="3"/>')
    out.append(text(40, 40, 'ONE LAP OF THE TANK', 30, '#b8dbca'))
    return svg(''.join(out), 400, 'The five planes of the tank and the lap the autopilot walks', background=None)


arts = {'gait.svg': gait(), 'eye.svg': eye(), 'bury.svg': bury(), 'brittle.svg': brittle(), 'planes.svg': planes()}
for name, data in arts.items():
    (HERE/name).write_text(data)

# ---------------------------------------------------------------------------------------------
refs = [
    ('1', 'Algrain et al. 2022', 'https://doi.org/10.1098/rsob.220103'),
    ('2', 'Mueller et al. 2011', 'https://doi.org/10.3354/ab00326'),
    ('3', 'Garm &amp; Nilsson 2014', 'https://doi.org/10.1098/rspb.2013.3011'),
    ('4', 'Bos et al. 2011', 'https://doi.org/10.1007/s00227-010-1588-0'),
    ('5', 'Kano et al. 2019', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC6923253/'),
    ('6', 'Matsuzaka et al. 2017', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC5399548/'),
    ('7', 'Western Australian Museum', 'https://museum.wa.gov.au/online-collections/names/Culcita-novaeguineae/'),
    ('8', 'Reef Life Survey', 'https://reeflife.org/species/fromia-milleporella/'),
    ('9', 'SeagrassNet guide', 'https://www.seagrassnet.org/downloads/seagrass_global_bioregion_photo_guide_2025.pdf'),
]
reference_html = ' · '.join(f'<a href="{url}">[{n}] {label}</a>' for n, label, url in refs)

species = [
    ('species-linckia', 'Blue sea star', 'Linckia laevigata', '18 cm', 'The one you steer. Eyes at the arm tips; any arm can lead. [3] Crawls 8.1 cm a minute. [2]'),
    ('species-chip', 'Chocolate-chip star', 'Protoreaster nodosus', '20 cm', 'Thick arms, dark knobs. Crawls 18.8 cm a minute. [2] <span class="game">Rests 20 to 60 s between walks.</span>'),
    ('species-fromia', 'Red Fromia', 'Fromia milleporella', '8 cm', 'Red with fine dark pores; colour varies in the wild. [8] <span class="game">Creeps along the three rocks.</span>'),
    ('species-sand', 'Sand-sifting star', 'Archaster typicus', '11.2 cm', 'Flat grey-tan star that buries in sand. [4] Fastest of the three measured crawlers: 45.8 cm a minute. [2]'),
    ('species-brittle', 'Green brittle star', 'Ophiarachna incrassata', '3.8 cm disc', 'Rows on 15 cm S-bent arms. [5,6] <span class="game">Hides under the ledges.</span>'),
    ('species-cushion', 'Cushion star', 'Culcita novaeguineae', '14.4 cm', 'A thick pentagon with short arms and patchy colours; barely moves. [7]'),
]
def crop_tile(name):
    """Recompress a 960 x 800 render to the part that holds the animal (every animal fits inside this box)."""
    from PIL import Image
    im = Image.open(HERE.parent/'sea-stars-art'/f'{name}.png').convert('RGB')
    out = HERE/'tiles'
    out.mkdir(exist_ok=True)
    im.crop((70, 76, 890, 641)).save(out/f'{name}.jpg', quality=90)       # 820 x 565
    return f'tiles/{name}.jpg'


tiles = ''.join(
    f'<figure><img src="{crop_tile(f)}" alt="{escape(n)}"><figcaption><b>{escape(n)}</b><br>'
    f'<i>{escape(l)}</i> <span class="size">· {escape(sz)}</span><p>{note}</p></figcaption></figure>' for f, n, l, sz, note in species)

forth = '''st-auto-step st@ 0 = if
  JOYSTICK_BUTTON_DOWN st-buttons st!
  st-surface st@ 1 = if 1 st-auto-step st! then
else st-auto-step st@ 1 = if
  JOYSTICK_BUTTON_UP st-buttons st!
  st-z st@ 3 >= if 2 st-auto-step st! then
else ( ... right, back, down, rest ... ) then then'''

html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Sea stars · A3 portrait research poster</title><style>
@page{{size:A3 portrait;margin:0}}*{{box-sizing:border-box}}body{{margin:0;background:#ccd7d5;color:{INK};font-family:"DejaVu Sans",sans-serif}}.page{{width:297mm;height:420mm;padding:9mm 12mm;background:#faf7ee;margin:auto;display:flex;flex-direction:column;gap:3mm;overflow:hidden}}header{{border-bottom:3px solid {TEAL};padding-bottom:3mm}}h1{{font-size:36pt;letter-spacing:-1px;margin:0}}h2{{font-size:13.5pt;margin:0 0 1.5mm}}p{{font-size:10pt;line-height:1.38;margin:1.2mm 0}}.strap{{font-size:12pt;letter-spacing:1px;color:{BLUE}}}.tiles{{display:grid;grid-template-columns:repeat(3,1fr);gap:3.5mm}}figure{{margin:0;background:#edf3f1;border-radius:3mm;overflow:hidden}}figure img{{width:100%;height:auto;aspect-ratio:1.45;object-fit:cover;display:block}}figcaption{{font-size:10.5pt;line-height:1.28;padding:1.8mm 3mm 2.2mm}}figcaption .size{{color:{BLUE};font-size:9.5pt}}figcaption p{{font-size:9.4pt;line-height:1.36;margin:1mm 0 0}}svg{{display:block;margin:0 auto;max-width:100%;height:25mm}}.row{{display:grid;grid-template-columns:1fr 1fr;gap:3mm}}.panel{{background:#edf3f1;border-radius:3mm;padding:3mm 3.5mm}}.panel p{{font-size:9.4pt;margin:1mm 0}}.bottom{{background:#263c48;color:#faf7ee;padding:3.5mm 4mm;border-radius:3mm}}.bottom h2{{color:#b8dbca}}.three{{display:grid;grid-template-columns:.9fr 1fr 1fr;gap:5mm;align-items:center}}.bottom svg{{height:auto;width:100%}}.bottom p{{font-size:9.4pt}}pre{{font-size:8pt;line-height:1.42;white-space:pre-wrap;margin:0}}footer{{margin-top:auto;font-size:8.2pt;line-height:1.42}}a{{color:inherit}}.small{{font-size:9pt}}.game{{color:#7a4f12}}.bottom .game{{color:#f0c98c}}@media screen{{.page{{margin:20px auto;box-shadow:0 5px 25px #55716e}}}}@media print{{body{{background:white}}.page{{margin:0}}}}</style>
<main class="page"><header><div class="strap">SIX ANIMALS · TUBE FEET · SAND AND GLASS</div><h1>Sea stars</h1><p>A slow crawl on adhesive feet, with no front and no back.</p></header>
<section class="tiles">{tiles}</section>
<div class="row"><section class="panel"><h2>01 · Attach, pull, let go</h2>{arts['gait.svg']}<p>Tube feet stick by secretion and let go by de-adhesion; the footprint stays. [1]</p><p class="game">The four beats are an animation. Speeds are multiplied by 30, 20 and 20 so the stars are watchable.</p></section><section class="panel"><h2>02 · Eyes at the tips of the arms</h2>{arts['eye.svg']}<p>Compound eyes at the arm tips let it steer across the reef by sight. [3]</p><p class="game">The raised tip follows that anatomy; the two-second reach on button A is an animation.</p></section></div>
<div class="row"><section class="panel"><h2>03 · Disappearing into sand</h2>{arts['bury.svg']}<p>Sand-sifting stars bury themselves in sand and move between habitats. [4]</p><p class="game">A nearby player makes one dive. When it dives and how fast are authored, not measured.</p></section><section class="panel"><h2>04 · Brittle stars row</h2>{arts['brittle.svg']}<p>Arms coordinate, the leading arm changes [5], and the tips bend upward. [6]</p><p class="game">3.8 cm disc, 15 cm arms with 16 joints each, about 34 cm across. The escape speed is a readability choice.</p></section></div>
<section class="bottom"><h2>05 · The tank, and the lap that walks it</h2><div class="three"><div>{arts['planes.svg']}</div><div><p>Reef flats and rubble are cushion-star ground. [7] Our tank borrows that: an open sand flat, three rocks and tufts of ribbon seagrass, 9 to 18 cm tall. [9]</p><p class="game">Game design: press into the glass and your underside meets it, on five planes. Let go and an autopilot walks this lap. Its Forth:</p></div><pre>{escape(forth)}</pre></div></section>
<footer><b>Research:</b> <a href="../sea-stars-research.md">sea-stars-research.md</a>, checked 20 November 2026. {reference_html}<br>A3 portrait · 297 × 420 mm · Marine animals. Original renders of the game&rsquo;s own models, not photographs; sizes are the ones chosen for the tank. Drawings are conceptual, not measured. Amber text marks game design, not research.</footer></main></html>'''
(HERE/'poster.html').write_text(html)
print(HERE/'poster.html')
