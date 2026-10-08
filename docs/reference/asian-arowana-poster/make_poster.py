#!/usr/bin/env python3
"""Build the A3 poster and plan illustrations from licensed photos + original SVG.

python3 docs/reference/asian-arowana-poster/make_poster.py
Then print poster.html with Chrome, at its CSS A3 size (no headers/footers).
No remote resources, image generation, or game assets are needed by the output.
"""
from pathlib import Path
import base64
import html
import json
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / 'docs/plans/2026-10-02-asian-arowana'
INK, GOLD, SEA = '#153938', '#b18134', '#e9f2ed'


def text(x, y, value, size=17, color=INK, anchor='start', weight=400):
    return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{html.escape(value)}</text>'


def svg(w, h, content, title):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}"><title>{html.escape(title)}</title><g font-family="DejaVu Sans, sans-serif">{content}</g></svg>'


def fish(x=0, y=0, scale=1):
    """Original side-view illustration: head right, seven fins incl. paired fins.
    Drawing proportions are illustrative; this is not a game model/render.
    """
    out = [f'<g transform="translate({x} {y}) scale({scale})" stroke="#54684b" stroke-width="1.2">']
    for pts in ('75,58 95,12 150,25 181,65', '72,108 94,162 198,150 246,113',
                '295,118 316,154 352,133', '382,110 331,162 410,144 438,113',
                ):
        out.append(f'<polygon points="{pts}" fill="#9eaf7a"/>')
    out.append('<path d="M 57,70 L 17,39 Q -9,32 0,83 Q -8,140 17,137 L 62,114 Z" fill="#9eaf7a"/>')
    for i in range(11):
        out.append(f'<path d="M 59,92 L {3+i*1.2},{42+i*8}" fill="none" opacity=".7"/>')
    for i in range(13):
        out.append(f'<path d="M {85+i*11},115 L {96+i*10},{155-i*1.1}" fill="none" opacity=".55"/>')
    for i in range(8):
        out.append(f'<path d="M {92+i*9},64 L {98+i*9},{20+i*2}" fill="none" opacity=".55"/>')
    out.append('<path d="M 58,72 Q 145,42 310,66 Q 419,69 478,100 L 507,101 L 497,114 Q 443,149 367,126 Q 206,148 63,111 Z" fill="#b9c599"/>')
    for row in range(4):
        for col in range(12):
            cx = 80+col*23+(row%2)*11
            cy = 72+row*15
            if cx < 365 and not (row == 0 and cx < 125):
                out.append(f'<path d="M {cx+15},{cy-7} Q {cx-7},{cy} {cx+15},{cy+9}" fill="none" stroke="#80935f" stroke-width="1"/>')
    out.append('<path d="M 400,77 Q 362,100 390,129" fill="none" stroke-width="2"/>')
    out.append('<polygon points="379,112 326,157 412,139 436,116" fill="#a1ad75"/>')
    for i in range(5):
        out.append(f'<path d="M 400,118 L {338+i*14},{152-i*3}" fill="none"/>')
    out.append('<circle cx="459" cy="98" r="9" fill="#e0d998"/><circle cx="461" cy="98" r="5" fill="#152b27"/>')
    out.append('<path d="M 477,117 L 499,108 M 499,110 Q 515,100 527,105 M 497,113 Q 517,111 531,115" fill="none" stroke-width="2"/>')
    out.append('</g>')
    return ''.join(out)


def anatomy():
    out = [fish(48, 62, .91)]
    labels = [(95,35,'Dorsal fin',156,83),(330,35,'Large overlapping scales',309,138),
              (537,58,'Upturned mouth',499,159),(548,94,'Two jaw barbels',529,163),
              (12,256,'Rounded caudal fin',67,149),(174,256,'Anal fin',177,200),
              (302,256,'Pelvic fins (pair)',330,195),(469,256,'Pectoral fins (pair)',398,189)]
    for x,y,label,tx,ty in labels:
        out.append(f'<path d="M {x+12},{y+5 if y<100 else y-23} L {tx},{ty}" fill="none" stroke="{GOLD}" stroke-width="1.4"/><circle cx="{tx}" cy="{ty}" r="3" fill="{GOLD}"/>')
        out.append(text(x,y,label,15))
    return svg(735,280,''.join(out),'Asian arowana anatomy, schematic side view')


def region_map():
    # Equirectangular projection; map window 92–122 E, 12 S–23 N.
    x = lambda lon: 28+(lon-92)*14.1
    y = lambda lat: 36+(23-lat)*11.3
    out = [f'<rect width="510" height="463" rx="12" fill="{SEA}"/><defs><clipPath id="region"><rect x="18" y="26" width="465" height="406"/></clipPath></defs><g clip-path="url(#region)">']
    data = json.loads((HERE/'assets/countries.geojson').read_text())
    for feature in data['features']:
        geom = feature['geometry']
        polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
        for poly in polys:
            # Even-odd rings preserve lakes / interior holes.
            d = ' '.join('M '+' L '.join(f'{x(lon):.2f},{y(lat):.2f}' for lon,lat,*_ in ring)+' Z' for ring in poly)
            out.append(f'<path d="{d}" fill="#cad8c9" stroke="#6f8d82" stroke-width=".9" fill-rule="evenodd"/>')
    for lon in (95,105,115):
        out.append(f'<path d="M {x(lon)},26 V 432" stroke="#b5ccc5" stroke-dasharray="3 5"/>')
        out.append(text(x(lon),445,f'{lon}°E',12,anchor='middle'))
    for lat in (20,10,0,-10):
        out.append(f'<path d="M 18,{y(lat)} H 483" stroke="#b5ccc5" stroke-dasharray="3 5"/>')
        out.append(text(474,y(lat)-4,f'{lat}°',11,anchor='end'))
    for lon,lat,name in [(96.8,20.8,'MYANMAR'),(99.2,17.9,'THAILAND'),(103.5,15.9,'CAMBODIA'),(108.4,20.3,'VIETNAM'),(101.5,4.7,'MALAY PENINSULA'),(99.9,-3.8,'SUMATRA'),(114.3,-3.3,'BORNEO')]:
        out.append(text(x(lon),y(lat),name,11,anchor='middle',weight=600))
    # Region centres only, not GPS animal records or a present-day range polygon.
    points = [dict(name='Trat / Chanthaburi',lon=102.25,lat=12.4,label_x=267,label_y=126),
              dict(name='Cardamom region',lon=103.3,lat=11.7,label_x=288,label_y=156),
              dict(name='Danau Sentarum',lon=112.1,lat=.8,label_x=284,label_y=318),
              dict(name='Rajang basin',lon=113,lat=2.3,label_x=316,label_y=275)]
    for p in points:
        px,py=x(p['lon']),y(p['lat'])
        out.append(f'<path d="M {px},{py} L {p["label_x"]},{p["label_y"]-5}" stroke="{GOLD}" fill="none"/>')
        out.append(f'<circle cx="{px}" cy="{py}" r="5" fill="{GOLD}" stroke="#fff" stroke-width="1.6"/>')
        out.append(text(p['label_x'],p['label_y'],p['name'],13,weight=600))
    out.append('</g>'+text(28,20,'N ↑  •  Southeast Asia',14,weight=600))
    (HERE/'locations.json').write_text(json.dumps(dict(projection='equirectangular',bbox=[92,-12,122,23],
        kind='Approximate centres of regions reported in USFWS 2019; not occurrence coordinates or complete/current range',points=points),indent=2)+'\n')
    return svg(510,463,''.join(out),'Southeast Asia with four historically reported Asian arowana regions')


def movement():
    out = [text(12,25,'Proposed game motion • not measured arowana kinematics',16,weight=600)]
    for i,(label,phase) in enumerate((('DRIVE',0),('COAST',.4),('TURN / BRAKE',.7))):
        ox=18+i*238
        out.append(text(ox,56,label,15,color=GOLD,weight=700))
        out.append(fish(ox,70,.39))
        wave=' '.join(f'{ox+203-s*185:.1f},{165+(.8+14*s*s)*math.sin(2*math.pi*(s-phase)):.1f}' for s in [j/50 for j in range(51)])
        out.append(f'<polyline points="{wave}" fill="none" stroke="{GOLD}" stroke-width="2"/>')
        out.append(text(ox,204,['Tail drive → forward swim','Reduced beat → glide','Arc turn; pectoral braking'][i],13))
    return svg(735,220,''.join(out),'Proposed arowana drive, glide and turn/brake phases')


def tank(oblique=False):
    out = ['<rect width="1200" height="650" fill="#071d24"/>',text(48,48,'ASIAN AROWANA • BROAD BARE TANK',28,'#e4e9dc',weight=700),text(48,81,'Concept illustration • 4:3 horizontal footprint • one animal',18,'#95b3b9')]
    if oblique:
        out.append('<path d="M 150,300 L 850,300 L 1075,135 L 375,135 Z M 850,300 L 1075,135 L 1075,345 L 850,510 Z M 150,510 L 850,510 L 1075,345 L 375,345 Z" fill="#10303a" stroke="#547783" stroke-width="2"/>')
        out.append('<path d="M 150,300 L 850,300 L 850,510 L 150,510 Z" fill="#0d2932" stroke="#66838a" stroke-width="2"/>')
        out.append(fish(455,355,.223))
        out.append(text(899,237,'3.0 m deep',18,'#c9d7d7'))
        out.append(text(390,536,'4.0 m long',18,'#c9d7d7'))
    else:
        out.append('<rect x="150" y="240" width="800" height="240" fill="#0d2932" stroke="#66838a" stroke-width="2"/>')
        out.append(fish(478,322,.255))
        out.append(text(423,516,'4.0 m long × 1.2 m high',18,'#c9d7d7'))
    out.append(text(120,556,'Bare floor and water column. No substrate, plants, rocks, prey, bubbles or props.',18,'#c9d7d7'))
    out.append(text(120,591,'Simulation design: 4.0 m × 3.0 m × 1.2 m water space; 0.65 m fish.',17,'#95b3b9'))
    out.append(text(120,620,'Wide view reveals the broad footprint; close view keeps the fish readable.',17,'#95b3b9'))
    return svg(1200,650,''.join(out),'Broad oblique bare tank concept' if oblique else 'Broad tank side elevation concept')


def controls():
    out=[f'<rect width="1100" height="425" fill="{SEA}"/>',text(35,42,'Clownfish swimming baseline → arowana proportions',24,weight=700)]
    columns=[('INPUT', ['D-pad: requested heading','OK: short swim burst','Up then new OK: Side / Depth','Desktop: existing A, B/C','Phone baseline: A mode, B burst']),
             ('STEER + SWIM', ['Damped yaw / slower pitch','Speed × current facing','Reverse through a U-turn','Release → glide / fin brake','No sideways axis sliding']),
             ('POSE + CLEARANCE', ['Body wave grows toward tail','Seven fins + two barbels','All parts share yaw/pitch/roll','Nose, tail and fins inside walls','Slow near floor and surface'])]
    for i,(title,lines) in enumerate(columns):
        x=35+i*362
        out.append(text(x,102,title,19,GOLD,weight=700))
        for j,line in enumerate(lines):out.append(text(x,143+j*37,line,16))
        if i<2:out.append(f'<path d="M {x+310},96 H {x+342} l -7,-6 m 7,6 l -7,6" fill="none" stroke="{GOLD}" stroke-width="2"/>')
    out.append(text(35,377,'Chromecast chord is proposed; physical remote validation remains required.',17,weight=600))
    out.append(text(35,404,'Unified phone A=Action / B=Mode belongs to the separate movement-controls integration.',15))
    return svg(1100,425,''.join(out),'Arowana input, swim controller, rig and wall-clearance diagram')


def uri(name):
    return 'data:image/jpeg;base64,'+base64.b64encode((HERE/'assets'/name).read_bytes()).decode()


def main():
    PLAN.mkdir(parents=True,exist_ok=True)
    diagrams={'anatomy.svg':anatomy(),'location-map.svg':region_map(),'motion.svg':movement()}
    for name,content in diagrams.items():(HERE/name).write_text(content)
    for name,content in {'tank-side.svg':tank(),'tank-oblique.svg':tank(True),'controls-and-rig.svg':controls(),**diagrams}.items():
        (PLAN/name).write_text(content)
    css='''@page { size:A3 portrait; margin:0; } *{box-sizing:border-box} body{margin:0;background:#c9d6d2;font-family:"DejaVu Sans",sans-serif;color:#153938} .sheet{width:297mm;height:420mm;padding:12mm;background:#faf8f0;margin:20px auto;display:grid;grid-template-rows:25mm 105mm 103mm 73mm 46mm 23mm;gap:4mm} h1,h2,p,figure{margin:0} h1{font-size:31pt;line-height:1.05;letter-spacing:-1px} .kicker{color:#9b7029;font-size:9pt;font-weight:700;letter-spacing:2px;margin-bottom:2mm} .sub{font-size:11pt;margin-top:2mm} h2{font-size:15pt;line-height:1.2;margin-bottom:2.5mm} p{font-size:10pt;line-height:1.4;margin-bottom:2.5mm} a{color:inherit;text-decoration:none} .hero{background:#061721;color:#fff;padding:3mm;border-radius:3mm;display:grid;grid-template-rows:1fr auto;gap:2mm} .hero img{width:100%;height:92mm;object-fit:cover;object-position:50% 18%} figcaption{font-size:8pt;line-height:1.25} .range{display:grid;grid-template-columns:132mm 1fr;gap:6mm} .map svg{width:112mm;height:90mm;display:block;margin:auto} .map-note{font-size:8pt;line-height:1.25;text-align:center} .tag{display:inline-block;background:#e6ecd9;color:#285546;padding:1.2mm 2mm;border-radius:1mm;font-size:8pt;font-weight:700;margin-bottom:2mm} .anatomy{display:grid;grid-template-columns:176mm 1fr;gap:5mm;border-top:1px solid #c9d1be;padding-top:3mm} .anatomy svg{width:176mm;height:63mm} .detail img{width:100%;height:47mm;object-fit:contain;background:#102621;border-radius:2mm} .detail p{font-size:9pt;line-height:1.3;margin-top:2mm} .bottom{display:grid;grid-template-columns:176mm 1fr;gap:5mm}.bottom svg{width:176mm;height:39mm}.trivia p{font-size:9pt;line-height:1.35}.footer{border-top:1px solid #c9d1be;padding-top:2mm;font-size:7.7pt;line-height:1.35}.footer p{font-size:7.7pt;line-height:1.35;margin:0 0 1mm}.num{color:#9b7029;font-weight:700} @media print {body{background:white}.sheet{margin:0}}'''
    content=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Asian Arowana — A3 poster</title><style>{css}</style><main class="sheet">
    <header><div class="kicker">FRESHWATER • SOUTHEAST ASIA</div><h1>Asian Arowana</h1><div class="sub"><i>Scleropages formosus</i> · The dragon fish · Family Osteoglossidae</div></header>
    <figure class="hero"><img src="{uri('fanghong-asian-arowana.jpg')}" alt="Full side-view photograph of an Asian arowana, showing large scales and posterior fins"><figcaption>Photograph: Fanghong, 2006 · <a href="https://commons.wikimedia.org/wiki/File:Honglongyu3.jpg">Wikimedia Commons</a> · CC BY-SA 3.0 · black margins cropped by layout; resized. Photographed specimen; not a wild-location record.</figcaption></figure>
    <section class="range"><div class="map"><h2>Where it lives <span class="num">[1, 2]</span></h2>{diagrams['location-map.svg']}<div class="map-note">Dots are approximate regional centres, not exact sightings.<br>Historical reports; no complete or current range boundary implied.</div></div><div>
    <div class="tag">TROPICAL FRESHWATER</div><h2>Forest waterways</h2><p>Slow rivers, lakes, swamps and flooded forests; blackwater streams can be stained brown by tannins from plant material. <span class="num">[1]</span></p><p>Reported across parts of mainland Southeast Asia, the Malay Peninsula, Sumatra and Borneo. The map selects four named regions from the USFWS account; it does not mark whole countries as occupied habitat. <span class="num">[1, 2]</span></p><h2>Life near the surface</h2><p>Juveniles eat insects at the surface. Larger fish also take fish and small vertebrates. <span class="num">[1, 2]</span></p><div class="tag">ENDANGERED • IUCN 2019</div><p>Habitat loss and collection pressure threaten wild populations. Captive fish and release records should not be mistaken for native populations. <span class="num">[3]</span></p></div></section>
    <section class="anatomy"><div><h2>Built like a dragon <span class="num">[2]</span></h2>{diagrams['anatomy.svg']}</div><div class="detail"><img src="{uri('scoute-dich-asian-arowana.jpg')}" alt="Oblique head photograph showing the arowana's eye, scales and upturned jaw"><p>The head, upturned jaw and plate-like scales in close view. Maximum reported length: <b>90 cm total length</b>, including the tail. <span class="num">[1]</span></p><figcaption>Scoute-dich / Baumann Productions, 2009 · <a href="https://commons.wikimedia.org/wiki/File:Asiatische_Gabelbart_(Scleropages_formosus).jpg">Commons</a> · CC BY-SA 3.0 · full image, resized.</figcaption></div></section>
    <section class="bottom"><div><h2>Swimming study</h2>{diagrams['motion.svg']}</div><div class="trivia"><h2>A father’s nursery</h2><p>The male carries eggs and larvae in his mouth while the young develop. <span class="num">[2]</span></p><p><b>Dragon fish:</b> associated with luck and prosperity; colour forms have a long ornamental-trade history. <span class="num">[2]</span></p><p>Singapore reservoir records include introduced fish, rather than proof of a native range there. <span class="num">[4]</span></p></div></section>
    <footer class="footer"><p><b>Research:</b> <a href="https://www.fws.gov/sites/default/files/documents/Ecological-Risk-Screening-Summary-Asian-Bonytongue.pdf">[1] USFWS, Ecological Risk Screening Summary (2019)</a> · <a href="https://horizon.documentation.ird.fr/exl-doc/pleins_textes/divers19-11/010033034.pdf">[2] Pouyaud, Sudarto &amp; Teugels, Cybium 27:287–305 (2003)</a> · <a href="https://doi.org/10.2305/IUCN.UK.2019-3.RLTS.T152320185A89797267.en">[3] Larson &amp; Vidthayanon, IUCN (2019)</a> · <a href="https://lkcnhm.nus.edu.sg/app/uploads/2017/04/sbr2013-021.pdf">[4] NUS, Singapore Biodiversity Records (2013)</a>.</p><p>Natural Earth 1:110m basemap: public domain. Anatomy and swimming drawings are original schematics; motion is a game proposal. Colour-form taxonomy differs between accounts; this poster uses the broad Asian arowana name. Research checked 2 October 2026.</p><p>Photos and this poster: <a href="https://creativecommons.org/licenses/by-sa/3.0/">Creative Commons Attribution–ShareAlike 3.0</a>. Full image credits and source notes accompany the poster. A3 portrait · 297 × 420 mm.</p></footer>
    </main></html>'''
    (HERE/'poster.html').write_text(content)
    gallery=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Asian arowana — tank plan</title><style>body{{margin:0;padding:35px;background:#071d24;color:#e1eeea;font:18px/1.5 sans-serif}}main{{max-width:1200px;margin:auto}}h1{{margin:0}}img{{width:100%;display:block;border-radius:10px;margin:16px 0 35px}}a{{color:#e1c17e}}.row{{display:flex;gap:25px;flex-wrap:wrap}}</style><main><h1>Asian Arowana</h1><p>One fish. Bare tank. Concept illustrations for the new level; the level is planned.</p><p><a href="../2026-10-02-asian-arowana.md">Plan Markdown</a> · <a href="../../reference/asian-arowana-poster/poster.html">Actual A3 poster</a> · <a href="../../reference/asian-arowana-poster/asian-arowana-a3.pdf">Print PDF</a></p><h2>Side view</h2><img src="tank-side.svg" alt="Bare tank side-view mockup"><h2>Oblique view</h2><img src="tank-oblique.svg" alt="Bare tank oblique-view mockup"><h2>Controls and rig</h2><img src="controls-and-rig.svg" alt="Controls and rig diagram"><h2>Anatomy</h2><img src="anatomy.svg" alt="Fish anatomy diagram"><h2>Movement study</h2><img src="motion.svg" alt="Drive coast brake sequence"><h2>Research map</h2><img src="location-map.svg" style="max-width:700px" alt="Southeast Asia location map"></main></html>'''
    (PLAN/'index.html').write_text(gallery)
    print(f'Built {HERE / "poster.html"} and {PLAN / "index.html"}')


if __name__ == '__main__':
    main()
