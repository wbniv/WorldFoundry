#!/usr/bin/env python3
"""Original vector diagrams and a printable portrait A3 research poster."""
from pathlib import Path
from html import escape
import math

HERE = Path(__file__).resolve().parent
HERE.mkdir(parents=True, exist_ok=True)
INK = '#183f48'
TEAL = '#168c99'
ORANGE = '#d98336'

def text(x, y, s, size=22, color=INK):
    return f'<text x="{x}" y="{y}" font-family="DejaVu Sans,sans-serif" font-size="{size}" fill="{color}">{escape(s)}</text>'

def svg(body, height=300, title='Rainbow goby schematic'):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {height}" role="img"><title>{escape(title)}</title>{body}</svg>'

def fish(x, y, scale=1, dorsal=True):
    out = [f'<g transform="translate({x} {y}) scale({scale})">']
    # Original stylized male: silhouette and markings, not a diagnostic painting.
    out += ['<path d="M130 -24 Q182 -57 207 -48 L211 44 Q181 54 130 22Z" fill="#87c4c8" stroke="#285860" stroke-width="2"/>']
    for k in range(9):
        yy=-44+k*10
        out.append(f'<path d="M131 0 L206 {yy}" stroke="#285860" stroke-width="2" opacity=".7"/>')
        for j in range(3):
            out.append(f'<circle cx="{159+j*16}" cy="{yy*(.35+j*.2)}" r="2.4" fill="#364f50"/>')
    if dorsal:
        out += ['<path d="M-83 -22 Q-59 -101 -30 -104 L-11 -27Z" fill="#e69a43" stroke="#31565c" stroke-width="2"/>', '<path d="M-1 -28 Q46 -72 119 -47 L132 -22Z" fill="#9dcace" stroke="#31565c" stroke-width="2"/>']
        for k in range(6):
            out.append(f'<path d="M{-77+k*11} -24 L{-56+k*8} {-80+k*7}" stroke="#495c56" stroke-width="2"/>')
        for k in range(10):
            out.append(f'<path d="M{6+k*12} -25 L{10+k*11} {-51+abs(4-k)*2}" stroke="#2b7580" stroke-width="2"/>')
    out += ['<path d="M-164 0 Q-171 -35 -123 -39 Q-77 -39 -21 -28 Q60 -26 137 -15 L138 15 Q66 26 -19 29 Q-95 40 -150 25 Q-166 20 -164 0Z" fill="#b0b9a2" stroke="#30595c" stroke-width="2"/>']
    for row in range(5):
        for k in range(17):
            xx=-92+k*13+(row%2)*6
            yy=-20+row*10
            if xx<127:
                out.append(f'<path d="M{xx} {yy} q5 5 10 0" fill="none" stroke="#78877b" stroke-width="1.1"/>')
    for k in range(8):
        xx=14+k*15
        out.append(f'<path d="M{xx} -20 q-5 17 0 40" stroke="#687970" stroke-width="4" opacity=".45" fill="none"/>')
    out += ['<path d="M-150 -11 Q-118 -24 -93 -7 L-89 26 Q-125 34 -152 15Z" fill="#26a6b2" opacity=".88"/>','<path d="M-102 6 Q-50 -17 -34 14 L-81 33Z" fill="#accac4" stroke="#42757a" stroke-width="2"/>']
    for k in range(7):
        out.append(f'<path d="M-99 8 L{-66+k*5} {-7+k*5}" stroke="#467176" stroke-width="1.5"/>')
    out += ['<ellipse cx="-105" cy="33" rx="24" ry="7" fill="#c5cfa7" stroke="#57776d" stroke-width="2"/>','<circle cx="-140" cy="-23" r="10" fill="#dcc36c"/><circle cx="-140" cy="-23" r="6" fill="#183b42"/><circle cx="-142" cy="-25" r="2" fill="#fff"/>','<path d="M-164 11 l14 1" stroke="#234d54" stroke-width="3"/>','</g>']
    return ''.join(out)

anatomy = svg(fish(452,205,1.45)+text(30,35,'ADULT MALE · STYLIZED COLOUR STUDY',24)+text(35,103,'High-set eyes')+'<path d="M190 107 L220 151" stroke="#168c99"/>'+text(395,83,'First dorsal')+text(680,122,'Second dorsal')+'<path d="M740 126 L610 155" stroke="#168c99"/>'+text(55,325,'Down-facing mouth')+text(400,330,'Pelvic attachment disc')+'<path d="M490 301 L279 251" stroke="#168c99"/>'+text(748,301,'Broad tail')+text(35,375,'Silver–olive scales · local turquoise cheek · orange dorsal · patterned rays',22),395,'Male anatomy and chosen live-colour interpretation')

stream = svg('<path d="M25 45 H935 l-18 -10 m18 10 l-18 10" stroke="#168c99" stroke-width="5" fill="none"/>'+text(35,30,'Clear water over a biofilm-coated bed',24)+'<path d="M20 200 Q150 158 255 202 Q360 172 465 205 Q650 166 820 195 L980 220 V265 H20Z" fill="#b0b7a0"/>'+''.join(f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r*.42}" fill="#849d87" stroke="#5d7768" stroke-width="3"/><path d="M{x-r*.75} {y-r*.22} Q{x} {y-r*.5} {x+r*.7} {y-r*.2}" stroke="#93b24b" stroke-width="6" fill="none"/>' for x,y,r in [(140,205,100),(385,205,105),(680,211,142),(910,222,60)])+fish(390,161,.68)+text(28,293,'Plant thickets are our aquarium setting; stones supply the grazing surfaces.',21),315,'Proposed aquarium hardscape informed by stream habitat')

motion=[]
for k,(label,yy) in enumerate([('PERCH',167),('SHORT SWIM',118),('SETTLE',149),('GRAZE',167)]):
    x=125+k*250
    motion += [text(x-100,32,label,23),f'<ellipse cx="{x}" cy="210" rx="110" ry="23" fill="#9da88e"/>',fish(x,yy,.47,k!=0)]
    if k==1:motion+=['<path d="M285 80 Q350 57 437 88 l-15 -13 m15 13 l-22 0" fill="none" stroke="#168c99" stroke-width="4"/>']
    if k==2:motion+=['<path d="M670 71 Q698 90 710 122 l-2 -17 m2 17 l-13 -12" stroke="#168c99" stroke-width="4" fill="none"/>']
    if k==3:motion+=['<path d="M800 182 q-10 -13 0 -26" stroke="#d98336" stroke-width="3" fill="none"/>']
motion += [text(25,276,'Proposed animation loop: attachment, brief travel, soft landing, small feeding nods.',21)]
cycle=svg(''.join(motion),300,'Animation abstraction, not measured kinematic traces')

disc=svg('<ellipse cx="210" cy="145" rx="127" ry="60" fill="#c5cfa7" stroke="#547970" stroke-width="5"/><ellipse cx="210" cy="145" rx="80" ry="36" fill="#a2bca0"/>'+''.join(f'<path d="M210 145 L{210+118*math.cos(k*math.pi/7)} {145+52*math.sin(k*math.pi/7)}" stroke="#658b77" stroke-width="3"/>' for k in range(14))+text(35,35,'JOINED PELVIC FINS · UNDERSIDE',24)+text(400,87,'Hold position on a surface')+text(400,133,'Provide leverage while grazing')+text(400,179,'Keep the body quiet at rest')+text(35,264,'Conceptual disc diagram; rock contact comes before tail or fin flutter.',21),285,'Joined pelvic fins and attachment concept')

wave=svg(''.join(f'<path d="M{35+k*230} 135 '+ ' '.join(f'L{35+k*230+j*6:.1f} {135+math.sin(j/5-k*1.2)*(j/32)**2*35:.1f}' for j in range(33))+'" stroke="#168c99" stroke-width="7" fill="none"/>'+text(35+k*230,44,f'Phase {k+1}',22) for k in range(4))+text(35,232,'Quiet head → growing tail amplitude · rays stay structured · membranes can transmit light',20),260,'Conceptual travelling body wave with amplitude rising toward the tail')

for name,art in [('anatomy.svg',anatomy),('habitat.svg',stream),('movement.svg',cycle),('pelvic-disc.svg',disc),('tail-wave.svg',wave)]:
    (HERE/name).write_text(art)

refs = [('1','Maeda & Tan (2013): taxonomy and proportions','https://www.science.nus.edu.sg/wp-content/uploads/sites/11/2024/07/61rbz749-761.pdf'),('2','Seriously Fish: habitat, feeding and trade-name ambiguity','https://www.seriouslyfish.com/species/stiphodon-ornatus/'),('3','Green Aqua: live-colour reference','https://greenaqua.hu/en/stiphodon-sp.html')]
links=' · '.join(f'<a href="{u}">[{n}] {escape(label)}</a>' for n,label,u in refs)
html=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Rainbow goby · A3 portrait poster</title><style>
@page{{size:A3 portrait;margin:0}}*{{box-sizing:border-box}}body{{margin:0;background:#c8d7d3;color:{INK};font-family:"DejaVu Sans",sans-serif}}.page{{width:297mm;height:420mm;padding:10mm 12mm;margin:auto;background:#fbf7eb;display:flex;flex-direction:column;gap:3.5mm}}header{{border-bottom:3px solid {TEAL};padding-bottom:3mm}}h1{{font-size:39pt;margin:0;letter-spacing:-1px}}h2{{font-size:14pt;margin:0 0 2mm}}p{{font-size:10.3pt;line-height:1.38;margin:1.6mm 0}}.strap{{font-size:11pt;color:#997039;letter-spacing:1px}}.hero{{display:grid;grid-template-columns:1.8fr 1fr;gap:4mm;align-items:center}}svg{{width:100%;display:block}}.row{{display:grid;grid-template-columns:1fr 1fr;gap:4mm}}.panel{{padding:3.5mm;border-radius:3mm;background:#e7efdf}}.wide{{background:#e2eeeb;padding:3mm;border-radius:3mm}}.wide svg{{height:35mm}}.code{{background:{INK};color:#f7f5e8;padding:4mm;border-radius:3mm}}.code h2{{color:#a6d6cd}}pre{{font-size:9pt;line-height:1.5;white-space:pre-wrap;margin:2mm 0}}.small{{font-size:9pt}}footer{{font-size:8pt;line-height:1.4;margin-top:auto}}a{{color:inherit}}@media screen{{.page{{margin:20px auto;box-shadow:0 5px 25px #78928c}}}}@media print{{.page{{margin:0}}body{{background:white}}}}</style>
<main class="page"><header><div class="strap">FRESHWATER STREAMS · BIOFILM GRAZING · A PELVIC DISC</div><h1>Rainbow goby</h1><p><i>Stiphodon ornatus</i> · A small fish with a very different way of staying put.</p></header>
<section class="hero">{anatomy}<div><h2>A name needs a species</h2><p>“Rainbow goby” covers several traded fish. Our reference is an adult male <i>S. ornatus</i>, documented from western Sumatra. [1,2]</p><p>Examined males were about 35–53 mm in standard length, excluding the tail. The male tail is roughly 29–35% of that length. [1]</p><p class="small">Original drawings. The chosen turquoise cheek and warm dorsal are a live-colour interpretation, not a diagnostic colour chart. [3]</p></div></section>
<div class="row"><section class="panel"><h2>01 · A rock is a feeding station</h2>{stream}<p>Clear, oxygen-rich streams support algae and associated microscopic life on submerged surfaces. The fish grazes this biofilm. [2]</p><p>For our planted aquarium, leave rounded stones visible among the colonies. This is an aquarium interpretation of its habitat.</p></section><section class="panel"><h2>02 · Attach, then graze</h2>{disc}<p>The pelvic fins form a disc. It helps the fish hold position and brace during feeding; its mouth faces the substrate. [1,2]</p><p>A convincing resting pose needs a believable contact point. Tiny feeding motions should leave the whole fish settled.</p></section></div>
<section class="wide"><h2>03 · Motion with pauses</h2>{cycle}<p>The grazing habit motivates this game loop: perch → brief swim → settle → graze. Timing, acceleration and descent rates are authored choices. Avoid perpetual cruising, instant direction flips and sliding while apparently attached.</p></section>
<div class="row"><section class="panel"><h2>04 · Structure before shimmer</h2>{wave}<p>Use two distinct dorsals, a low elongated body, broad tail and patterned fin rays. [1] Keep body scales restrained; concentrate bright colour around the cheek and dorsal.</p><p class="small">Game proposal: 256² authored textures, selective fin translucency, bounded tail deformation and modest pectoral motion.</p></section><section class="panel"><h2>05 · From biology to controls</h2><p><b>← →</b> · Short lateral swims, easing into movement.</p><p><b>↑ ↓</b> · Lift off or descend toward a perch.</p><p><b>Release</b> · Settle; a quiet graze follows contact.</p><p><b>Tap A</b> · Change view. <b>Hold A</b> · Settings.</p><p><b>↶</b> · Close settings first; otherwise return to the level selector.</p><p class="small">Proposed controls preserve the plant level’s camera/settings gestures. Forth reads the Director’s OAS/OAD Water type: freshwater chooses the goby; saltwater chooses the urchin.</p></section></div>
<section class="code"><h2>06 · Small Forth ideas: ease, settle, keep the head quiet</h2><div class="row"><pre>\\ Mailbox velocity eases toward intent
: gb-ease ( target mailbox -- )
  &gt;r r@ gb@ -
  gb-dt gb@ 7 * 1 min *
  r@ gb@ + r&gt; gb! ;</pre><div><pre>\\ Illustrative tail envelope: u in [0,1]
: tail-weight ( u -- amplitude ) dup * ;</pre><p class="small">The first fragment comes from the authored controller. The second is a simple deformation idea: little motion near the head, more toward the tail. Neither is a measured biological law.</p></div></div></section>
<footer><b>Separate research:</b> <a href="../rainbow-goby-research.md">rainbow-goby-research.md</a> · Checked 6 October 2026.<br>{links}<br>A3 portrait · 297 × 420 mm · Life-history evidence for <i>S. percnopterygionus</i> supports a marine larval phase within this genus; identical timing for <i>S. ornatus</i> is not established here. [1] No breeding or waterfall-climbing simulation is proposed.</footer></main></html>'''
(HERE/'poster.html').write_text(html)
print(HERE/'poster.html')
