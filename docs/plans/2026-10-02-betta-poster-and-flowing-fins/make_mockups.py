"""Original vector design concepts; not engine captures or measured kinematics."""
from pathlib import Path
import math
OUT=Path(__file__).resolve().parent
STYLE='''<style>text{font-family:DejaVu Sans,sans-serif;fill:#213845}.title{font-size:34px;font-weight:bold}.head{font-size:24px;font-weight:bold}.body{font-size:19px}.small{font-size:16px}.label{font-size:18px;font-weight:bold}</style>'''
def svg(name,content,w=1200,h=800):
    (OUT/(name+'.svg')).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{STYLE}<rect width="{w}" height="{h}" fill="#f6f1e6"/>{content}</svg>')
def fish(phase=0,wire=False):
    f='<path d="M421 319 Q396 229 431 180 Q460 121 521 176 Q559 210 593 284 Z" fill="#933e76" stroke="#632b60" stroke-width="3"/>'
    f+='<path d="M422 343 Q471 465 512 485 Q611 497 660 370 L675 345 Z" fill="#be4773" stroke="#80315d" stroke-width="3"/>'
    # Caudal fan, closed opaque outline. Distal deflection is deliberately illustrative.
    root=(408,330);rows=[]
    for j in range(9):
        r=j/8;pts=[]
        for i in range(41):
            a=math.pi/2+math.pi*i/40
            pts.append((root[0]+165*r*math.cos(a),root[1]+165*r*math.sin(a)+12*r*r*math.sin(phase+i*.28+r*2)))
        rows.append(pts)
    outline=[root,*rows[-1],root]
    f+='<polygon points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in outline)+'" fill="#c74869" stroke="#753154" stroke-width="3"/>'
    for i in range(0,41,2):
        points=[row[i] for row in rows]
        f+='<polyline points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in points)+'" fill="none" stroke="#ed867f" stroke-width="2"/>'
    if wire:
        for row in rows[1:]:f+='<polyline points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in row)+'" fill="none" stroke="#732f59" stroke-width="1"/>'
    for i in range(14):
        x=437+i*12
        f+=f'<path d="M{x} 348 Q{x-3} 398 {x+10} {448-abs(i-6)*5}" stroke="#ee8d93" stroke-width="2" fill="none"/>'
    f+='<path d="M406 302 Q480 262 585 274 Q660 277 711 314 L733 329 Q697 358 645 364 Q512 393 405 355 Z" fill="#257185" stroke="#18475a" stroke-width="4"/>'
    f+='<path d="M425 310 Q524 284 638 302" fill="none" stroke="#4e9fa8" stroke-width="10"/>'
    for row in range(4):
        for i in range(13):
            x=451+i*15+(row%2)*6;y=310+row*13
            f+=f'<path d="M{x} {y} q-7 5 0 10" fill="none" stroke="#438e9b" stroke-width="1.7"/>'
    f+='<path d="M659 292 Q632 329 660 360" fill="none" stroke="#174456" stroke-width="5"/>'
    f+='<path d="M641 330 Q602 297 561 321 Q553 346 597 371 Q630 368 646 340 Z" fill="#905b93" stroke="#58325f" stroke-width="3"/>'
    f+='<path d="M645 349 Q606 407 544 474 Q550 489 570 475 Q624 417 655 351 Z" fill="#c44c72" stroke="#7b325c" stroke-width="2"/>'
    f+='<path d="M663 352 Q643 422 592 478 L604 493 Q657 428 670 353 Z" fill="#824879" stroke="#5b315d" stroke-width="2"/>'
    f+='<circle cx="693" cy="308" r="12" fill="#152b39"/><circle cx="697" cy="304" r="4" fill="#e3e8d6"/><path d="M724 326 l9 3 -10 5" fill="none" stroke="#183d50" stroke-width="3"/>'
    return f

def callout(x,y,text,tx,ty):
    return f'<path d="M{x} {y+7} L{tx} {ty}" fill="none" stroke="#58707c" stroke-width="2"/><text x="{x}" y="{y}" class="label">{text}</text>'

def location_map():
    # Original schematic outline and regional positions, not a surveyed basemap
    # or the paper's exact collection coordinates. Names checked in Kwon Fig. 1.
    b='<path d="M80 0L120 15L150 30L155 70L175 100L235 95L240 150L290 175L305 240L275 270L250 258L237 255L240 290L205 305L190 280L150 280L145 340L162 400L205 455L192 476L163 446L120 399L117 343L128 298L115 274L126 245L100 195L95 156L72 143L68 90L45 80L60 30Z" fill="#a9c9bc" stroke="#4c756d" stroke-width="3"/>'
    for i,(x,y) in enumerate([(105,80),(117,223),(156,259),(134,280)]):
        b+=f'<circle cx="{x}" cy="{y}" r="12" fill="#27768b"/><text x="{x}" y="{y+5}" text-anchor="middle" font-size="15" font-weight="bold" style="fill:white">{i+1}</text>'
    b+='<text x="175" y="180" class="small">THAILAND</text><path d="M280 35V5l-7 13m7-13 7 13" stroke="#35595c" stroke-width="2" fill="none"/><text x="275" y="58" class="small">N</text>'
    return b

map_b='<text x="45" y="60" class="title">Wild bettas: reported study localities</text><text x="45" y="100" class="body">Thailand · mainland Southeast Asia context · Betta splendens</text>'
map_b+='<g transform="translate(100 155) scale(1.08)">'+location_map()+'</g>'
map_b+='<text x="55" y="300" class="small">Myanmar</text><text x="445" y="270" class="small">Lao PDR</text><text x="475" y="470" class="small">Cambodia</text>'
for i,name in enumerate(['Chiang Mai','Kanchanaburi','Bang Phlat','Phetchaburi']):
    map_b+=f'<text x="650" y="{205+i*70}" class="head">{i+1}. {name}</text>'
map_b+='<text x="650" y="520" class="body">Four wild-population labels in</text><text x="650" y="553" class="body">Kwon et al. 2022, Fig. 1A/B.</text><text x="650" y="608" class="small">Not a complete distribution map.</text><text x="650" y="640" class="small">Dots mark approximate regions, not GPS sites.</text>'
map_b+='<text x="45" y="738" class="small">MAP CONCEPT · schematic outline; final basemap and locality precision require verification.</text><text x="45" y="770" class="small">Distinguish wild B. splendens from related species, introduced occurrences and ornamental breeders.</text>'
svg('location-map',map_b)

b='<text x="50" y="60" class="title">Opaque fin anatomy + mesh design</text><text x="50" y="94" class="body">Eight anatomical groups · 6,000–10,000 target triangles · no translucency</text>'
b+='<g transform="translate(100 30) scale(1.25)">'+fish(wire=True)+'</g>'
for args in [(50,245,'Caudal fan',510,450),(480,165,'Dorsal sail',730,255),(480,705,'Anal skirt',780,625),(875,520,'Near/far pectorals',895,458),(830,685,'Paired pelvic ribbons',880,600),(950,280,'Shaped head + gills',963,425)]:b+=callout(*args)
b+='<text x="50" y="760" class="small">CONCEPT · radial topology shown schematically; counts and deformation remain implementation targets.</text>'
svg('mesh-design',b)

b='<text x="45" y="60" class="title">Anchored roots, flexible free edges</text><text x="45" y="97" class="body">Independent fin motion · illustrative sequence, not a measured betta waveform</text>'
for i,(name,note,phase) in enumerate([('Hover','Small sculling; restrained body movement',0),('Swim','Tail sweep; membrane tips trail the roots',1.2),('Turn','Pectoral asymmetry; fan curves into turn',2.4),('Settle','Gentle recovery; no abrupt phase reset',3.6)]):
    x=35+(i%2)*590;y=125+(i//2)*315
    b+=f'<rect x="{x}" y="{y}" width="565" height="295" rx="12" fill="#e4e8e0"/>'
    b+=f'<text x="{x+20}" y="{y+35}" class="head">{i+1}. {name}</text><g transform="translate({x-95} {y-35}) scale(.77)">'+fish(phase)+'</g>'
    b+=f'<text x="{x+20}" y="{y+276}" class="small">{note}</text>'
    b+=f'<circle cx="{x+219}" cy="{y+219}" r="5" fill="#bd9c35"/>'
b+='<text x="45" y="780" class="small">GAME DESIGN · root-to-tip lag and amplitudes will be tuned against documented reference footage.</text>'
svg('motion-sequence',b,h=820)

b='<text x="55" y="77" class="title">BETTA</text><text x="55" y="118" class="head">THE ART OF FLOWING FINS</text><text x="55" y="157" class="body">Betta splendens · Siamese fighting fish · ornamental long-fin form</text>'
b+='<g transform="translate(35 50) scale(1.4)">'+fish()+'</g>'
b+='<rect x="75" y="275" width="235" height="160" rx="8" fill="#e4e8e0" stroke="#b6c4bb"/><text x="95" y="322" class="label">OBLIQUE DETAIL</text><text x="95" y="356" class="small">Second actual fish render</text><text x="95" y="385" class="small">Curved rays + paired fins</text>'
b+='<text x="55" y="808" class="small">RENDERED HERO SLOT · drawn stand-in now; replace with the actual upgraded opaque fish render</text>'
b+='<path d="M55 850 H1145" stroke="#bd9c35" stroke-width="3"/>'
for i,(title,text) in enumerate([('Centuries of breeding','Thailand: historical reports of fighting-fish selection'),('Early 20th century','Ornamental breeding expands color and fin forms'),('5 February 2019','Thailand’s National Aquatic Animal designation')]):
    x=55+i*365
    lines=[('Thailand: reported breeding history','Exact starting date remains uncertain'),('Ornamental selection develops','many colors and elaborate fin forms'),('Thailand’s National Aquatic Animal','official designation')][i]
    b+=f'<text x="{x}" y="893" class="label">{title}</text>'
    for j,line in enumerate(lines):b+=f'<text x="{x}" y="{925+j*25}" class="small">{line}</text>'
b+='<rect x="55" y="1000" width="545" height="400" rx="9" fill="#e4e8e0"/><text x="73" y="1037" class="label">WHERE WILD BETTAS LIVE</text><g transform="translate(95 1050) scale(.61)">'+location_map()+'</g>'
for i,name in enumerate(['1. Chiang Mai','2. Kanchanaburi','3. Bang Phlat','4. Phetchaburi']):
    b+=f'<text x="330" y="{1098+i*40}" class="small">{name}</text>'
b+='<text x="330" y="1290" class="small">Wild B. splendens localities</text><text x="330" y="1322" class="small">Kwon 2022, Fig. 1A/B</text><text x="73" y="1365" class="small">MAP CONCEPT · approximate regions</text><text x="73" y="1390" class="small">Not GPS sites or a complete range.</text>'
panels=[
    (625,1000,140,'HOME IN SHALLOW WATER',['Vegetated pools, canals and rice paddies.','A labyrinth organ supports air breathing; gills also work.']),
    (625,1150,140,'WILD VS ORNAMENTAL',['Wild-type forms have compact fins.','The extravagant hero is a domesticated long-fin variety.']),
    (625,1300,140,'BUBBLE-NEST CARE',['B. splendens males care for eggs in bubble nests.','Other Betta species may use mouth brooding.']),
    (625,1450,140,'BEAUTY HAS A COST',['Larger caudal fins are linked with lower burst speed.','The 2026 abstract does not supply full fin-wave motion.']),
    (55,1430,160,'FLOW, TURN, SETTLE',['Fin roots stay attached; free edges curve and lag.','Diagram values are game choices, not measured betta rates.'])]
for x,y,h,title,lines in panels:
    b+=f'<rect x="{x}" y="{y}" width="545" height="{h}" rx="9" fill="#e4e8e0"/><text x="{x+18}" y="{y+37}" class="label">{title}</text>'
    for j,line in enumerate(lines):b+=f'<text x="{x+18}" y="{y+78+j*30}" class="small">{line}</text>'
b+='<text x="55" y="1610" class="small">Sources: Kwon 2022 · SEAFDEC 2019 · Thai Natural History Museum 2017 · Smith/Hopkins 2026</text><text x="55" y="1642" class="small">A3 LAYOUT MOCKUP · rendered hero + oblique detail required; final renders and PDF pending</text>'
svg('poster-layout',b,h=1697)
(OUT/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Betta poster and flowing fins — concepts</title><style>body{background:#0c202b;color:#edf3ec;font:18px/1.5 system-ui;margin:0}main{max-width:1050px;margin:auto;padding:30px}h1{font-size:32px}img{width:100%;background:#f6f1e6;margin:20px 0 45px;border-radius:9px}a{color:#9bdddb}nav{display:flex;gap:25px;flex-wrap:wrap}p{color:#bbccd1}</style><main><h1>Betta: poster + ornate flowing fins</h1><p><a href="../../reference/betta-history-and-biomechanics-poster/poster.html">Finished A3 poster with actual model-study renders</a> · <a href="../../reference/betta-history-and-biomechanics-poster/poster.pdf">Print PDF</a>. The concepts below remain earlier design studies; runtime integration is pending.</p><p>Original design mockups and diagrams. These are not engine captures, a finished poster, or measured motion. Every planned fin uses opaque geometry; no translucency dependency.</p><nav><a href="#poster">A3 poster</a><a href="#map">Location map</a><a href="#mesh">Mesh diagram</a><a href="#motion">Motion sequence</a><a href="../2026-10-02-betta-poster-and-flowing-fins.md">Full plan and sources</a></nav><h2 id="poster">A3 poster layout</h2><img src="poster-layout.svg" alt="Portrait betta poster concept with rendered-fish slots, history, location map, habitat and motion panels"><h2 id="map">Wild-fish locations</h2><p>Four locality names checked in Kwon et al. 2022, Fig. 1. Approximate regions on a schematic outline; final basemap and collection precision are pending. This is not a complete range map.</p><img src="location-map.svg" alt="Thailand regional map concept with Chiang Mai, Kanchanaburi, Bang Phlat and Phetchaburi marked approximately"><h2 id="mesh">Detailed opaque mesh</h2><img src="mesh-design.svg" alt="Labeled betta fin groups with illustrative radial tail topology"><h2 id="motion">Flowing-fin motion</h2><img src="motion-sequence.svg" alt="Four concept poses for hover, swim, turn and settle"></main></html>''')
