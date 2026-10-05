#!/usr/bin/env python3
"""Original vector biology diagrams, portrait A3 poster and plan illustrations."""
from pathlib import Path
from html import escape
import math

HERE = Path(__file__).resolve().parent
PLAN = HERE.parents[1] / 'plans/2026-10-05-sea-urchin-realism'
PLAN.mkdir(parents=True, exist_ok=True)
INK = '#263c48'
TEAL = '#167e83'
PURPLE = '#78509d'

def text(x, y, value, size=22, color=INK):
    return f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" fill="{color}">{escape(value)}</text>'

def svg(body, height=300, title='Sea urchin schematic'):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {height}" role="img"><title>{escape(title)}</title><rect width="1000" height="{height}" rx="18" fill="#edf3f1"/>{body}</svg>'

def urchin(cx, cy, scale=1, tilt=0, feet=True):
    out = [f'<g transform="translate({cx},{cy}) scale({scale})">']
    # Layer the rear spines, soft feet, rigid test and front spines.
    for layer in (0, 1):
        if layer == 1:
            if feet:
                for k in range(7):
                    x = -90+k*30
                    out.append(f'<path d="M{x} 20 Q{x-10} 56 {x+13} 78" stroke="#72b4b0" stroke-width="5" fill="none"/><ellipse cx="{x+13}" cy="78" rx="9" ry="4" fill="#c0d9c6" stroke="#167e83"/>')
            out.append('<ellipse cx="0" cy="0" rx="122" ry="78" fill="#6b4988" stroke="#493366" stroke-width="3"/>')
            for k in range(35):
                a = k*2.399963
                r = math.sqrt((k+.5)/35)
                x, y = math.cos(a)*110*r, math.sin(a)*67*r
                out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#9874b5"/>')
        for k in range(27):
            a = math.pi*2*(k+.3*layer)/27
            x, y = math.cos(a)*105, math.sin(a)*63
            if (y>0) != bool(layer):
                continue
            length = 43+(k*17)%34
            local_tilt = tilt if math.cos(a) > .35 and math.sin(a) < -.15 else 0
            dx = math.cos(a+local_tilt)*length
            dy = math.sin(a+local_tilt)*length
            col = ['#725095','#9470b2','#654784'][k%3]
            out.append(f'<path d="M{x-3:.1f} {y:.1f} L{x+dx:.1f} {y+dy:.1f} L{x+3:.1f} {y:.1f}Z" fill="{col}" stroke="#4e3968" stroke-width="1"/>')
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#bc9dcb"/>')
    out.append('</g>')
    return ''.join(out)

anatomy = svg(urchin(460,190,1.1)+text(30,40,'SHORT-SPINED REGULAR URCHIN',26)+text(25,110,'Rigid test')+'<path d="M157 113 L350 176" stroke="#167e83"/>'+text(740,90,'Jointed spines')+'<path d="M790 103 L620 137" stroke="#167e83"/>'+text(680,315,'Soft adhesive feet')+'<path d="M735 287 L565 300" stroke="#167e83"/>'+text(25,346,'Mouth underneath · spines and tube feet are different organs',22),370,'Test, articulated spines and soft tube feet')

joint = svg('''<path d="M60 238 H940" stroke="#6b4988" stroke-width="26"/><circle cx="450" cy="220" r="35" fill="#b799c6" stroke="#6b4988" stroke-width="4"/><path d="M417 197 L439 42 L463 197Z" fill="#78509d"/><path d="M455 190 L555 65 L488 212Z" fill="#a080bb"/><path d="M398 208 Q450 165 508 216" fill="none" stroke="#d09c65" stroke-width="12"/><path d="M381 208 Q450 145 526 215" fill="none" stroke="#167e83" stroke-width="7"/>'''+text(35,42,'PIVOT → HOLD → RECOVER',25)+text(35,104,'Muscle moves')+text(35,146,'Catch tissue holds')+text(653,110,'Rigid shaft')+text(653,153,'Basal ball-and-socket')+text(653,196,'No flexible tip wave')+text(320,287,'Same pivot, different orientations',22),310,'Spine rotation about a basal joint')

gait = []
for k,label in enumerate(['1 Reach','2 Attach','3 Pull / support','4 Release / recover']):
    x = k*250+125
    gait += [text(x-108,33,label,21),f'<path d="M{x-105} 190 H{x+105}" stroke="#879b98" stroke-width="10"/>',f'<ellipse cx="{x+(20 if k==2 else 0)}" cy="105" rx="60" ry="37" fill="#78509d"/>']
    px = x+43 if k<2 else x+20
    py = 164 if k in (0,3) else 185
    gait += [f'<path d="M{x+15+(20 if k==2 else 0)} 123 Q{x+25} 162 {px} {py}" fill="none" stroke="#167e83" stroke-width="8"/>',f'<ellipse cx="{px}" cy="{py}" rx="13" ry="5" fill="#bdcfb6" stroke="#167e83"/>']
    if k in (1,2):
        gait.append(f'<circle cx="{px}" cy="185" r="19" fill="none" stroke="#db9a54" stroke-width="3"/>')
    if k==2:
        gait.append(f'<path d="M{x-50} 61 H{x+35} l-13 -8 m13 8 l-13 8" stroke="#167e83" stroke-width="4" fill="none"/>')
gait += [text(30,236,'Disc stays planted while the body advances; other feet overlap the contact.',21)]
locomotion = svg(''.join(gait),260,'Schematic overlapping attachment and traction cycle')

local = svg(urchin(240,185,.85)+urchin(745,185,.85,.28)+text(35,34,'REST: MOST SPINES HOLD',23)+text(550,34,'LOCAL STIMULUS: NEARBY TILT',23)+'<path d="M860 68 L824 118" stroke="#d38b44" stroke-width="5"/><circle cx="824" cy="118" r="14" fill="none" stroke="#d38b44" stroke-width="3"/>'+text(35,287,'Quiet, asynchronous adjustments')+text(530,287,'Localized response, then recovery',22),310,'Resting and local response concepts; schematic pose only')

top = ['<circle cx="255" cy="150" r="116" fill="#b394c7" stroke="#78509d" stroke-width="4"/>']
for k in range(5):
    a=2*math.pi*k/5-math.pi/2
    ex,ey=255+108*math.cos(a),150+108*math.sin(a)
    top.append(f'<path d="M255 150 L{ex} {ey}" stroke="#167e83" stroke-width="9"/>')
    for j in range(1,6):
        x,y=255+j*17*math.cos(a),150+j*17*math.sin(a)
        for s in (-1,1):
            top.append(f'<circle cx="{x+s*7*math.sin(a)}" cy="{y-s*7*math.cos(a)}" r="3" fill="#f7f4e9"/>')
top += ['<rect x="543" y="40" width="390" height="190" rx="9" fill="#78509d"/>']
for k in range(40):
    x,y=566+(k*47)%345,59+(k*31)%151
    top.append(f'<circle cx="{x}" cy="{y}" r="{3+k%4}" fill="#a784bc"/><circle cx="{x}" cy="{y}" r="2" fill="#523b6e"/>')
top += [text(45,292,'Fivefold test organization',22),text(559,269,'256² atlas: pores, tubercles, ridges',20),text(559,298,'Opaque test · selective translucent feet',20)]
mesh = svg(''.join(top),320,'Test organization and proposed texture atlas')

controls = svg('<rect x="15" y="15" width="970" height="370" rx="12" fill="#143543"/>'+urchin(375,257,1.1)+'<path d="M40 339 H661" stroke="#859887" stroke-width="14"/>'+text(42,55,'MARINE PLANTED TANK · PROPOSED CLOSE VIEW',26,'#edf3f1')+'<rect x="681" y="96" width="280" height="230" rx="14" fill="#254e5d"/>'+text(701,136,'D-pad / stick · crawl',21,'#edf3f1')+text(701,184,'Tap A · change view',21,'#edf3f1')+text(701,232,'Hold A · settings',21,'#edf3f1')+text(701,280,'↶ · level selector',21,'#edf3f1')+text(40,376,'Slow traction · planted feet · no boost button · current A behavior retained',20,'#edf3f1'),400,'Proposed close-camera control overlay')

contact = svg('''<path d="M40 244 H960" stroke="#879b98" stroke-width="12"/><ellipse cx="280" cy="103" rx="90" ry="51" fill="#78509d"/><ellipse cx="705" cy="103" rx="90" ry="51" fill="#a080bb"/><path d="M310 143 Q340 208 394 235 M735 143 Q564 194 394 235" stroke="#167e83" stroke-width="7" fill="none"/><ellipse cx="394" cy="235" rx="18" ry="6" fill="#c9d8bd"/><path d="M389 41 H652 l-17 -10 m17 10 l-17 10" stroke="#d38b44" stroke-width="4" fill="none"/>'''+text(55,36,'WORLD-SPACE CONTACT',25)+text(100,300,'Before body movement')+text(594,300,'After body movement')+text(438,228,'Same disc anchor',21)+text(55,350,'Local foot target = world anchor − current body position',23),380,'Foot contact remains fixed while body moves')

pipeline = svg(''.join(f'<rect x="{25+k*250}" y="65" width="220" height="90" rx="12" fill="{["#d7e5de","#d9cce7","#d7e5de","#d9cce7"][k]}"/>'+text(45+k*250,102,label,20)+text(45+k*250,131,sub,18) for k,(label,sub) in enumerate([('Input + modal gate','Forth intent'),('Actual movement','Contact state'),('Anchors + pivots','Existing actor poses'),('Mesh + atlas','Render / measure')]))+'<path d="M245 108 H275 M495 108 H525 M745 108 H775" stroke="#167e83" stroke-width="4"/>'+text(25,210,'One director; bounded contact slots. Full single-mesh articulation is a separate decision.',21),245,'Proposed input, contact and pose data flow')

arts={'anatomy.svg':anatomy,'spine-joint.svg':joint,'locomotion.svg':locomotion,'local-response.svg':local,'mesh-texture.svg':mesh,'controls-mockup.svg':controls,'world-contact.svg':contact,'pipeline.svg':pipeline}
for name,data in arts.items():
    (HERE/name).write_text(data)
    (PLAN/name).write_text(data)

refs=[('1','Purple urchin · Monterey Bay Aquarium','https://www.montereybayaquarium.org/animals-the-ocean/animals-a-to-z/purple-sea-urchin'),('2','Tube-foot secretion · Pjeta et al. (2020)','https://doi.org/10.3390/ijms21030946'),('3','Catch apparatus · Takemae & Motokawa (2005)','https://doi.org/10.2307/3593098'),('4','Spine coordination · Motokawa & Fuchigami (2015)','https://doi.org/10.1242/jeb.115972'),('5','Adhesion and movement · Garner et al. (2024)','https://academic.oup.com/icb/article/64/2/257/7623019'),('6','Fivefold test · ODFW','https://www.dfw.state.or.us/mrp/shellfish/commercial/urchin/life_history.asp')]
reference_html=' · '.join(f'<a href="{url}">[{n}] {escape(label)}</a>' for n,label,url in refs)
html=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Sea urchins · A3 portrait research poster</title><style>
@page{{size:A3 portrait;margin:0}}*{{box-sizing:border-box}}body{{margin:0;background:#ccd7d5;color:{INK};font-family:"DejaVu Sans",sans-serif}}.page{{width:297mm;height:420mm;padding:11mm 12mm;background:#faf7ee;margin:auto;display:flex;flex-direction:column;gap:4mm}}header{{border-bottom:3px solid {TEAL};padding-bottom:3mm}}h1{{font-size:39pt;letter-spacing:-1px;margin:0}}h2{{font-size:14pt;margin:0 0 2mm}}p{{font-size:10.5pt;line-height:1.4;margin:1.5mm 0}}.strap{{font-size:12pt;letter-spacing:1px;color:{PURPLE}}}.hero{{display:grid;grid-template-columns:1.8fr 1fr;gap:5mm;align-items:center;height:91mm}}svg{{width:100%;display:block}}.row{{display:grid;grid-template-columns:1fr 1fr;gap:5mm}}.panel{{background:#edf3f1;border-radius:3mm;padding:3.5mm}}.bottom{{background:#263c48;color:#faf7ee;padding:4mm;border-radius:3mm}}.bottom h2{{color:#b8dbca}}pre{{font-size:9.5pt;line-height:1.5;white-space:pre-wrap}}footer{{margin-top:auto;font-size:8.3pt;line-height:1.45}}a{{color:inherit}}.small{{font-size:9.2pt}}@media screen{{.page{{margin:20px auto;box-shadow:0 5px 25px #55716e}}}}@media print{{body{{background:white}}.page{{margin:0}}}}</style>
<main class="page"><header><div class="strap">ADHESIVE FEET · ARTICULATED SPINES · A RIGID TEST</div><h1>Sea urchins</h1><p>A slow crawl built from many small contacts.</p></header>
<section class="hero">{anatomy}<div><h2>Two kinds of moving parts</h2><p>The test is the inner shell. Purple urchins move with tube feet; their spines pivot on ball-and-socket joints. The mouth lies underneath. [1]</p><p><i>Strongylocentrotus purpuratus</i> is our proposed visual reference: a short-spined resident of eastern Pacific rocky shores, with a test up to about 7 cm across. [1]</p><p class="small">Original schematics, not photographs. Different species supply different evidence below.</p></div></section>
<div class="row"><section class="panel"><h2>01 · Attach, pull, let go</h2>{locomotion}<p>Tube feet make and release adhesive contacts; spines also assist movement. The discs use secretions rather than simple suction. [2,5]</p><p>The sequence above is an animation abstraction. Overlapping contacts should hold their world position as the body passes.</p></section><section class="panel"><h2>02 · Tilt at the base; hold the pose</h2>{joint}<p>Muscle moves a spine. Mutable collagenous catch tissue changes stiffness and helps maintain its orientation. [3]</p><p>Animate the basal joint and rigid shaft. Soft tentacle-like bending would give the wrong mechanical impression.</p></section></div>
<div class="row"><section class="panel"><h2>03 · A response can be local</h2>{local}<p>In <i>Diadema setosum</i>, touch coordinates nearby spines; a shadow can trigger waving. [4]</p><p>Do not transfer that shadow reflex to every species. For our short-spined model, sparse adjustments and held poses are a proposed starting point.</p></section><section class="panel"><h2>04 · Texture supports the anatomy</h2>{mesh}<p>The test has fivefold organization. [6] Distinguish shaft bases, fine secondary spines and soft foot discs.</p><p class="small">Game proposal: 256² atlas, surface markings and ridges; selective foot translucency. Geometry carries the silhouette.</p></section></div>
<section class="bottom"><h2>05 · Small Forth ideas for planted feet</h2><div class="row"><div><pre>\\ Keep a planted disc in world space
: contact-local ( anchor body -- offset ) - ;
\\ Bounded response; tau must be positive
: lag-step ( x target dt tau -- x' )
  / 1 min 0 max &gt;r over - r&gt; * + ;</pre></div><div><p>Move slowly in the requested substrate direction. Advance traction from actual travel; blocked input must not make the animal skate.</p><p>Keep tap A for camera and hold A for plant settings. Separate foot traction, exploratory feet and local spine response.</p><p class="small">Illustrative fragments. Angles, timing and speed are game choices to tune from footage and measure on hardware.</p></div></div></section>
<footer><b>Separate research:</b> <a href="../sea-urchin-research.md">sea-urchin-research.md</a> · Checked 5 October 2026.<br>{reference_html}<br>A3 portrait · 297 × 420 mm · Marine animals; freshwater is not a suitable habitat. Sources name their study species; pose drawings are conceptual, not measured kinematic traces.</footer></main></html>'''
(HERE/'poster.html').write_text(html)
print(HERE/'poster.html')
