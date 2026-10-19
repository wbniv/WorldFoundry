import math
from pathlib import Path
from math import sin, cos, pi

OUT = Path(__file__).resolve().parent
STYLE = '<style>text{font-family:system-ui,sans-serif;fill:#e9f2f4}.title{font-size:30px;font-weight:650}.sub{font-size:15px;fill:#acc2ce}.note{font-size:17px;fill:#b6cbd6}</style>'

def svg(name, body):
    (OUT / f'{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 620" role="img" aria-label="{name} concept">{STYLE}<rect width="1000" height="620" rx="18" fill="#101e2c"/>{body}</svg>')

def scene(title, subtitle, items, caption, jelly=False):
    b = f'<text x="38" y="48" class="title">{title}</text><text x="38" y="78" class="sub">SCHEMATIC CONCEPT · {subtitle}</text>'
    b += '<defs><linearGradient id="water" x2="0" y2="1"><stop stop-color="#21485b"/><stop offset="1" stop-color="#081c30"/></linearGradient><linearGradient id="sand" x2="0" y2="1"><stop stop-color="#d4c3a0"/><stop offset="1" stop-color="#897b61"/></linearGradient></defs>'
    b += '<rect x="45" y="108" width="910" height="410" rx="18" fill="url(#water)" stroke="#7e9aab" stroke-width="3"/>'
    if jelly:
        b += '<path d="M190 510 Q60 310 190 120 M810 510 Q940 310 810 120" fill="none" stroke="#376a86" stroke-width="12"/>'
    else:
        b += '<path d="M48 475 Q330 461 550 480 T952 473 V514 H48Z" fill="url(#sand)"/>'
        for i in range(40):
            x = 70 + i * 22
            b += f'<circle cx="{x}" cy="{485+(i*13)%21}" r="1.4" fill="#eadcc1"/>'
    b += items
    b += f'<text x="45" y="560" class="note">{caption}</text><text x="45" y="591" class="sub">Composition and proposed population only; no engine rendering or animation claim.</text>'
    return b

def leaf(x,y,angle,scale=1):
    return f'<g transform="translate({x} {y}) rotate({angle}) scale({scale})"><path d="M0 0 Q-34 -36 -21 -94 Q35 -84 0 0" fill="#427955" stroke="#83aa69" stroke-width="2"/><path d="M0 0 L-10 -78" stroke="#aac58c" fill="none"/></g>'

plants=''
for x,y,a,s in [(100,477,-15,1.7),(365,477,15,2),(400,479,55,1.4),(780,478,-25,1.8),(840,475,28,2.2),(882,480,60,1.1)]:
    plants += f'<path d="M{x} {y} Q{x-15} {y-80} {x-20} {y-115}" fill="none" stroke="#476e42" stroke-width="7"/>' + leaf(x,y,a,s)
    plants += leaf(x,y-90,a+30,s*.75)
betta='<g transform="translate(505 320)"><path d="M-55 -12 Q-145 -97 -162 -70 Q-142 -10 -162 65 Q-107 85 -52 15" fill="#9b415a" stroke="#ea8a9e" stroke-width="3"/>'
for dy in range(-60,61,20):
    betta+=f'<path d="M-55 0 Q-105 {dy/2} -147 {dy}" fill="none" stroke="#dfa0b4" stroke-width="2"/>'
betta+='<path d="M-45 -18 Q-23 -77 29 -41 L48 -10" fill="#3777a2" stroke="#6bbed0" stroke-width="2"/><path d="M-45 14 Q-21 83 34 48 L47 12" fill="#895577" stroke="#d398ba" stroke-width="2"/><path d="M20 20 Q18 65 38 73 L41 18 M37 21 Q44 62 52 67 L53 15" fill="#cb6571"/><ellipse cx="0" cy="0" rx="66" ry="28" fill="#3c7f9b"/><path d="M-50 -6 Q-15 -25 45 -9" fill="none" stroke="#88c1cc" stroke-width="5"/><circle cx="45" cy="-6" r="6" fill="#101621"/><circle cx="47" cy="-8" r="1.7" fill="#fff"/><path d="M20 -11 Q9 0 21 17" stroke="#1f566d" fill="none" stroke-width="3"/></g>'
temple='<g transform="translate(225 475)"><path d="M-85 0 H85 V-12 H-85Z" fill="#c6baa0"/><path d="M-71 -12 H71 V-22 H-71Z" fill="#cba552"/>'
for x in [-54,0,54]:
    temple+=f'<rect x="{x-5}" y="-111" width="10" height="90" fill="#e0d5b8"/><rect x="{x-8}" y="-34" width="16" height="12" fill="#d3aa48"/>'
for half,eave,peak in [(89,-110,-172),(66,-148,-201)]:
    temple+=f'<path d="M{-half} {eave} L0 {peak} L{half} {eave}Z" fill="#a94134" stroke="#e2b957" stroke-width="4"/><path d="M{-half} {eave} Q{-half-15} {eave-8} {-half-17} {eave-29} M{half} {eave} Q{half+15} {eave-8} {half+17} {eave-29}" fill="none" stroke="#e2b957" stroke-width="4"/>'
temple+='</g>'
svg('betta',scene('Calm Betta','one focal fish · broad leaves · Thai pavilion',plants+temple+betta,'Red/gold temple-style architecture at the rear; empty hall, no figures or statues.'))

def jelly(x,y,s):
    b=f'<g transform="translate({x} {y}) scale({s})">'
    for i in range(9):
        xx=-42+i*10
        b+=f'<path d="M{xx} 12 Q{xx+12} 44 {xx+5} 68" fill="none" stroke="#a1c8d8" stroke-width="2"/>'
    for xx in [-22,-5,13,28]:
        b+=f'<path d="M{xx} 10 Q{xx-18} 42 {xx+5} 66 T{xx-9} 111" fill="none" stroke="#c7dbe4" stroke-width="7"/>'
    b+='<path d="M-57 9 C-55 -58 55 -58 57 9 Q0 40 -57 9Z" fill="#bdd8e0" stroke="#e4eff1" stroke-width="3"/><path d="M-51 8 Q0 -19 51 8 Q0 28 -51 8" fill="#719fb7"/>'
    for xx,yy in [(-13,-16),(13,-16),(-13,0),(13,0)]:
        b+=f'<ellipse cx="{xx}" cy="{yy}" rx="11" ry="8" fill="none" stroke="#e2bfd8" stroke-width="3"/>'
    return b+'</g>'
jellies=''.join(jelly(*args) for args in [(250,208,.64),(487,200,.88),(720,232,.68),(355,360,.8),(618,376,.95),(814,389,.45)])
svg('jellyfish',scene('Jellyfish','six independent drifters · moon-jelly-inspired',jellies,'Slow curved drift; individual bell pulses and trailing oral arms.',True))

def rock(x,y,s):
    return f'<g transform="translate({x} {y}) scale({s})"><path d="M-100 0 L-78 -44 -28 -68 30 -62 84 -24 100 0Z" fill="#626b68" stroke="#87928a" stroke-width="2"/><path d="M-78 -44 L-5 -32 30 -62 M-5 -32 L23 0" stroke="#424f52" fill="none" stroke-width="3"/></g>'
def lion(x,y,s,flip=False):
    b=f'<g transform="translate({x} {y}) scale({-s if flip else s} {s})">'
    for xx,h in [(-35,80),(-17,110),(1,120),(20,95),(34,70)]:
        b+=f'<path d="M{xx} -12 L{xx-22} {-h}" stroke="#e5c4a7" stroke-width="5"/>'
    b+='<path d="M-54 -9 L-102 -35 -116 -15 -113 28 -99 40 -54 10" fill="#dec2a4"/><path d="M-40 0 L-73 47 -47 69 -18 76 10 65 43 39 40 0Z" fill="#dcc1a3" stroke="#a06b59" stroke-width="2"/>'
    for x1,z1,x2,z2 in [(-73,47,-47,69),(-18,76,10,65)]:
        b+=f'<path d="M0 0 L{x1} {z1} L{x2} {z2}Z" fill="#853e37"/>'
    b+='<ellipse cx="0" cy="0" rx="62" ry="27" fill="#dbc0a1"/>'
    for xx in [-43,-18,8,33]:
        b+=f'<path d="M{xx} -24 L{xx+8} 25" stroke="#853e37" stroke-width="11"/>'
    b+='<ellipse cx="49" cy="0" rx="24" ry="20" fill="#cdae8d"/><circle cx="51" cy="-8" r="5" fill="#15202a"/></g>'
    return b
rocks=rock(183,480,.75)+rock(436,481,.42)+rock(787,480,.75)+rock(898,480,.42)
fish=lion(415,306,.86)+lion(768,275,.63,True)
svg('lionfish',scene('Lionfish','two striped animals · sparse rocky reef',rocks+fish,'Slow hovering; long dorsal spines and independent fan and tail motion.'))

plant_scene=''
for x,y,a,scale in [(125,477,-30,2),(180,477,12,2.2),(260,477,45,1.5),(705,477,-20,2.2),(815,477,18,2.4),(890,477,55,1.4)]:
    plant_scene+=leaf(x,y,a,scale)+leaf(x,y-95,a+15,scale*.72)
for x in [330,385,440,520,570,625]:
    plant_scene+=f'<path d="M{x} 477 L{x+10} 270" stroke="#467248" stroke-width="5"/>'
    for j in range(4):plant_scene+=leaf(x+5,445-j*43,(-60 if j%2 else 50),.60)
for x in range(300,710,38):plant_scene+=leaf(x,478,30,.42)+leaf(x+17,478,-35,.37)
urchin_mock='<ellipse cx="560" cy="426" rx="34" ry="20" fill="#543663"/>'
for i in range(21):
    a=math.pi+i*math.pi/20
    x=560+31*math.cos(a);y=426+18*math.sin(a)
    urchin_mock+=f'<path d="M{x} {y} l{22*math.cos(a)} {22*math.sin(a)}" stroke="#9971a6" stroke-width="3"/>'
plant_scene+=urchin_mock
svg('plants',scene('Planted Tank','one sea urchin · broad leaves, stems and low planting',plant_scene,'A slow sea urchin crawls on pale substrate among grouped foliage.'))

rows=['Clownfish & Tiger Barbs','Blue Shrimp','Calm Betta','Jellyfish','Lionfish','Planted Tank']
b='<text x="80" y="73" class="title">WF Aquarium</text><text x="80" y="111" class="note">Choose a tank</text>'
for i,label in enumerate(rows):
    y=145+i*54
    b+=f'<rect x="80" y="{y}" width="840" height="46" rx="7" fill="{"#285e75" if i==2 else "#1a3042"}" stroke="{"#9bdfdf" if i==2 else "#344d60"}"/><text x="110" y="{y+31}" font-size="23">{"▸ " if i==2 else ""}{label}</text><text x="875" y="{y+30}" class="sub">{i}</text>'
b+='<text x="80" y="514" class="sub">↑ / ↓ Choose · OK / A Open · Existing SMB selector behavior</text><text x="80" y="552" class="sub">Planted Tank includes one sea urchin; no fish.</text><text x="80" y="588" class="sub">SCHEMATIC CONCEPT · confirm six-row fit in the actual menu drawer.</text>'
svg('selector',b)

b='<text x="38" y="48" class="title">Independent tanks → coordinated integration</text><text x="38" y="79" class="sub">No edits to the two active tanks during standalone development.</text>'
for i,(title,path) in enumerate([('Calm Betta','aquarium_betta/'),('Jellyfish','aquarium_jellyfish/'),('Lionfish','aquarium_lionfish/'),('Planted Tank','aquarium_plants/')]):
    x=25+i*245
    b+=f'<rect x="{x}" y="115" width="235" height="155" rx="12" fill="#213b4b" stroke="#6b96a7"/><text x="{x+18}" y="149" font-size="21">{title}</text><text x="{x+18}" y="183" class="sub">{path}</text><text x="{x+18}" y="216" class="note">Dedicated scene build</text><text x="{x+18}" y="245" class="sub">→ checked standalone</text><path d="M{x+117} 270 V306 H500 V328" stroke="#8bc2cf" stroke-width="2" fill="none"/>'
b+='<rect x="200" y="330" width="600" height="91" rx="12" fill="#375742" stroke="#8aad85"/><text x="230" y="365" font-size="23">One manifest + verified six-tank bundle</text><text x="230" y="398" class="sub">Preserve original standalone; package Android selector</text><path d="M500 421 V451" stroke="#8bc2cf" stroke-width="2"/><rect x="200" y="453" width="600" height="82" rx="12" fill="#294a60" stroke="#8bc2cf"/><text x="230" y="487" font-size="23">Six-entry Aquarium menu</text><text x="230" y="516" class="sub">Indices 0, 1 preserved · new tanks append 2, 3, 4, 5</text><text x="40" y="586" class="sub">Existing Aquarium + Blue Shrimp remain separate until the packaging pass.</text>'
svg('flow',b)

(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aquarium — four more tanks</title><style>body{margin:0;background:#0b1520;color:#e9f2f4;font:17px system-ui}main{max-width:1050px;margin:35px auto;padding:0 24px}h1{font-size:32px;margin-bottom:8px}p{color:#b6cbd6;line-height:1.55}button{background:#20384a;border:1px solid #668395;border-radius:8px;padding:12px 22px;color:#eff8fa;font:inherit;cursor:pointer;margin:0 8px 12px 0}button[aria-pressed=true]{background:#37667b;border-color:#a7e5e4}img{width:100%;display:block;margin:15px 0 28px;border-radius:15px}a{color:#a2dfec}h2{margin-top:38px}</style><main><h1>Aquarium: four more tanks</h1><p>Design review · Betta, Jellyfish, Lionfish and Planted Tank. Schematic mockups, not engine captures.<br>Standalone development first; shared menu integration when conflicts permit.</p><nav aria-label="Tank concept"><button aria-pressed="true" data-scene="betta">Calm Betta</button><button aria-pressed="false" data-scene="jellyfish">Jellyfish</button><button aria-pressed="false" data-scene="lionfish">Lionfish</button><button aria-pressed="false" data-scene="plants">Planted Tank</button></nav><img id="scene" src="betta.svg" alt="Calm Betta tank concept"><p id="description">One focal betta, broad leaves and a red/gold Thai temple-style pavilion. Empty hall, no Buddha figure or statue; open foreground for flowing fins.</p><h2>Six selectable tanks</h2><img src="selector.svg" alt="Six-entry planned tank selector mockup"><h2>Files and integration</h2><img src="flow.svg" alt="Standalone builds before coordinated integration"><p><a href="../2026-10-02-aquarium-three-more-tanks.md">Full implementation plan</a> · <a href="make-mockups.py">Visual source</a></p></main><script>const names={betta:'Calm Betta',jellyfish:'Jellyfish',lionfish:'Lionfish',plants:'Planted Tank'}, descriptions={betta:'One focal betta, broad leaves and a red/gold Thai temple-style pavilion. Empty hall, no Buddha figure or statue; open foreground for flowing fins.',jellyfish:'Six independent drifters with bell pulses and trailing appendages. Pale solid rendering is the first engine spike; translucency remains a visual risk.',lionfish:'Two striped lionfish over sparse reef rocks: slow hovering, long spines and spreading fins.',plants:'One slow sea urchin among broad leaves, upright stems, low planting and pale substrate. A changes views; no fish.'};document.querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));const key=button.dataset.scene;document.getElementById('scene').src=key+'.svg';document.getElementById('scene').alt=names[key]+' tank concept';document.getElementById('description').textContent=descriptions[key];}));</script></html>''')
