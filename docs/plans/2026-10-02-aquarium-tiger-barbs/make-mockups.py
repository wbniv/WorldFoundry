"""Generate native SVG design diagrams and a browser comparison; no game assets edited."""
from pathlib import Path
import html
import base64

OUT = Path(__file__).resolve().parent
RASTER = 'data:image/png;base64,' + base64.b64encode((OUT / 'tiger-barb-texture-concept.png').read_bytes()).decode('ascii')
TEXTURE = '#barbTexture'
def svg(body, width=1200, height=650):
    if TEXTURE in body:
        body = f'<defs><symbol id="barbTexture" viewBox="0 0 1536 1024"><image width="1536" height="1024" href="{RASTER}"/></symbol></defs>' + body
    return f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><style>text{{font-family:Arial,sans-serif;fill:#e7edf4}} .small{{font-size:16px}} .wire{{fill:none;stroke:#78e8ec;stroke-width:1.5}}</style>{body}</svg>'

def clown(x, y, length):
    return f'''<g transform="translate({x},{y}) scale({length/100})"><path d="M0 0 L17 -18 L17 -8 Q52 -33 91 -6 L100 0 L91 6 Q52 33 17 8 L17 18 Z" fill="#ef761c" stroke="#242a30" stroke-width="2"/><path d="M32 -18 L38 18 M61 -19 L67 17 M85 -10 L89 8" stroke="white" stroke-width="7"/><circle cx="90" cy="-4" r="3" fill="#171c22"/></g>'''

# Exact-count schematic, physically scaled against the 47-inch inner tank width.
# Fish are illustrative images; positions are fixed for comparison, not a simulation.
def tank(population):
    body = '<rect width="1200" height="590" fill="#111b29"/><rect x="40" y="60" width="1120" height="395" rx="3" fill="#163747" stroke="#83a4b4" stroke-width="4"/><path d="M40 410 Q320 399 650 413 T1160 410 L1160 455 L40 455Z" fill="#ad966f"/>'
    body += '<path d="M40 85 H1160" stroke="#7eb5bd" stroke-width="2"/><path d="M915 411 Q885 310 960 308 Q1035 310 1040 411" fill="#82646f"/>'
    for i in range(12):
        x = 908+i*11
        body += f'<path d="M{x} 405 Q{x-24} {345-i%4*12} {x+6} {322+i%3*13}" fill="none" stroke="#c18c9c" stroke-width="8" stroke-linecap="round"/>'
    body += clown(385, 255, 8.89/119.38*1120)
    if population == 11:
        for i in range(10):
            body += clown(190+(i%5)*165, 170+(i//5)*145, 8.89*(.60+((i+1)*7%10)*.0367)/119.38*1120)
    elif population == 30:
        for i in range(29):
            length_cm = 4.5+1.5*((i*11)%29)/28
            # Native layout of the unmodified generated raster reference.
            w = length_cm/119.38*1120
            x = 132+(i%8)*123+(i//8%2)*27
            y = 140+(i//8)*68+(i%3-1)*14
            body += f'<use x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{w*2/3:.2f}" xlink:href="{TEXTURE}"/>'
    desc = '1 player clownfish + 29 tiger barbs • 4.5–6 cm total length' if population == 30 else f'{population} clownfish • reference population'
    body += f'<text x="40" y="32" font-size="22">{desc}</text><text x="40" y="500" class="small">Density mockup • 47-inch interior width • fish drawn at proposed side-view scale</text><text x="40" y="529" class="small">Concept layout, not an engine capture. Quad, low-poly and refined phases share these 29 positions.</text><text x="40" y="558" class="small">Player stays 8.89 cm. Grey-pink anemone is a schematic location marker.</text>'
    return svg(body, height=590)
for n in (1,11,30):
    (OUT/f'population-{n}.svg').write_text(tank(n))

body = '<rect width="1200" height="720" fill="#111b29"/><text x="30" y="37" font-size="25">Tiger barb asset phases — design diagrams, not exported meshes</text>'
labels = [('Phase 1 · two-sided quad','4 vertices · 2 triangles · no deformation'), ('Phase 2 · one low-poly mesh','76 vertices · 128 triangles · includes fins'), ('Phase 3 · refined one-piece mesh','Start ~160 triangles · profile before adopting')]
for i,(title,subtitle) in enumerate(labels):
    x=30+i*395
    body += f'<text x="{x}" y="82" font-size="20">{title}</text><text x="{x}" y="110" font-size="14">{subtitle}</text><use x="{x}" y="140" width="355" height="237" xlink:href="{TEXTURE}"/>'
    if i == 0:
        body += f'<rect x="{x}" y="140" width="355" height="237" class="wire"/><path d="M{x} 140 L{x+355} 377" class="wire"/>'
    else:
        # Schematic ring topology over the texture reference, not a claimed UV/mesh bake.
        stations = [(35,236,294),(88,223,306),(145,209,320),(205,211,318),(266,229,303),(320,253,283)]
        if i == 2:
            stations = [(25+j*27,235-28*__import__('math').sin(j/10*3.14159),294+25*__import__('math').sin(j/10*3.14159)) for j in range(11)]
        prev=None
        for dx,top,bottom in stations:
            body += f'<path d="M{x+dx} {top} L{x+dx} {bottom}" class="wire"/>'
            if prev:
                px,pt,pb=prev
                body += f'<path d="M{x+px} {pt} L{x+dx} {top} L{x+px} {pb} L{x+dx} {bottom} M{x+px} {pt} L{x+dx} {bottom}" class="wire"/>'
            prev=(dx,top,bottom)
    body += f'<text x="{x}" y="423" class="small">End-on silhouette:</text>'
    if i == 0:
        body += f'<path d="M{x+178} 447 V540" stroke="#78e8ec" stroke-width="2"/><text x="{x}" y="575" class="small">Flat card becomes edge-on when turning.</text>'
    else:
        pts = [(178,447),(157,464),(148,502),(166,535),(178,543),(190,535),(208,502),(199,464)]
        body += f'<polygon points="'+ ' '.join(f'{x+dx},{y}' for dx,y in pts)+ '" fill="#d4a354" stroke="#78e8ec" stroke-width="2"/>'
        body += f'<path d="M{x+178} 447 V543 M{x+148} 502 H{x+208}" class="wire"/><text x="{x}" y="575" class="small">Body has volume; fins belong to this mesh.</text>'
    body += f'<text x="{x}" y="607" class="small">'+ ['No animation in this phase.','Add a small tail/body vertex cycle.','Improve silhouette and deformation.'][i]+'</text>'
body += '<text x="30" y="677" class="small">Wire overlays are schematic. P1/P2 counts are exported counts; P3 is a design target. No speedup is implied.</text>'
(OUT/'mesh-phases.svg').write_text(svg(body,height=720))

old=[('600–638','Player clownfish rig · retained'),('700–719 / 720–739 / 740–759','Swim / anemone / camera · retained'),('800–953','11 × 14 school state'),('960–981 / 985–1009','School parameters / scratch'),('1015–1039','Follower director / scratch'),('1040–1089','10 × 5 part actor indices'),('1090–1099','10 last-update timestamps'),('1100–1499','10 × 40 clownfish rig cells')]
new=[('600–638','Player clownfish rig · retained'),('700–719 / 720–739 / 740–759','Swim / anemone / camera · retained'),('800–1219','30 × 14 school state'),('1220–1241 / 1242–1266','School parameters / scratch'),('1267–1299','Follower director / scratch'),('1300–1328','29 single-mesh actor indices'),('1330–1358','29 last-update timestamps'),('1360–1388','29 animation phases · phase 2+'),('1390–1499','Reserved · no follower five-part rigs')]
body='<rect width="1200" height="820" fill="#111b29"/><text x="30" y="38" font-size="26">Mailbox allocation — baseline → implemented for 30 fish</text>'
for column,rows,title in [(0,old,'Baseline: 1 leader + 10 followers'),(1,new,'Implemented: 1 leader + 29 followers')]:
    x=30+column*590
    body += f'<text x="{x}" y="87" font-size="22">{title}</text>'
    for i,(address,label) in enumerate(rows):
        y=110+i*69
        body+=f'<rect x="{x}" y="{y}" width="550" height="61" rx="4" fill="{("#274557" if column else "#293344")}"/><text x="{x+12}" y="{y+24}" font-size="18">{html.escape(address)}</text><text x="{x+12}" y="{y+47}" font-size="15">{html.escape(label)}</text>'
body+='<text x="30" y="765" class="small">Inclusive ranges; row heights are schematic. Global user mailboxes: 2–1900. Generate all bases together.</text><text x="30" y="793" class="small">Player offset = 0, real delta time. Old pointers at 1016/1037 are forbidden: those cells now hold school state.</text>'
(OUT/'mailboxes.svg').write_text(svg(body,height=820))

(OUT/'mockups.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Aquarium tiger barb mockups</title><style>body{background:#111b29;color:#e7edf4;font:17px system-ui;max-width:1200px;margin:30px auto;padding:0 20px}img{width:100%;display:block}button,a{color:#b0f3f4}button{background:#274557;border:1px solid #587587;padding:12px;margin:4px;font:inherit;cursor:pointer}p{line-height:1.5}.asset{width:400px;max-width:100%;background:repeating-conic-gradient(#32414c 0 25%,#23343f 0 50%) 0/24px 24px}</style><h1>One clownfish + 29 tiger barbs</h1><p>Reviewed concept mockups. Phases 1 and 2 are now implemented; actual captures and measured comparisons are in the plan. The barbs are proposed at 4.5–6 cm total length; the player is 8.89 cm.</p><button onclick="set(1)">1 clownfish baseline</button><button onclick="set(11)">Current 11 clownfish</button><button onclick="set(30)">30 fish proposal</button><img id="tank" src="population-30.svg"><img src="mesh-phases.svg"><h2>Texture concept on transparency</h2><img class="asset" src="tiger-barb-texture-concept.png"><p>Generated side-profile art; production alpha, UV and geometry checks passed; see actual game captures in the plan.</p><h2>Expanded mailbox layout</h2><img src="mailboxes.svg"><script>function set(n){document.getElementById('tank').src='population-'+n+'.svg'}</script></html>''')
