#!/usr/bin/env python3
"""Build the lionfish research/proposal diagrams and an A3 portrait poster.
Original SVG schematics, not photographs or implemented game assets.
Run python3 make_poster.py, then print poster.html at its CSS A3 page size.
"""
from pathlib import Path
import math

HERE = Path(__file__).resolve().parent
PLAN = HERE.parents[1] / 'plans/2026-10-05-lionfish-realism'
PLAN.mkdir(parents=True, exist_ok=True)

def svg(body, w=1000, h=510):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img">{body}</svg>'

def fish(annotated=True):
    body = 'M270 254 Q315 196 422 187 Q559 177 634 209 Q675 211 710 250 L738 262 Q722 281 684 293 Q617 328 466 316 Q342 314 270 270Z'
    fin = 'M595 255 Q503 277 259 371 Q332 449 470 475 Q587 469 683 385 Q641 295 595 255Z'
    s = ['<defs><linearGradient id="skin" x2="0" y2="1"><stop stop-color="#f3dec1"/><stop offset=".5" stop-color="#d3b394"/><stop offset="1" stop-color="#936b53"/></linearGradient><linearGradient id="fan" x2="0" y2="1"><stop stop-color="#d5b6a7"/><stop offset="1" stop-color="#e7d6c6" stop-opacity=".25"/></linearGradient>',f'<clipPath id="body"><path d="{body}"/></clipPath><clipPath id="fin"><path d="{fin}"/></clipPath></defs>',
         '<rect width="1000" height="510" rx="14" fill="#e9f1f0"/>']
    # Far fan, rounded spotted tail, then dorsal spines and soft dorsal.
    s += [f'<path d="{fin}" transform="translate(25,-60)" fill="#b78979" opacity=".3"/>',
          '<path d="M287 251 Q243 205 167 198 Q127 252 165 308 Q237 301 287 270Z" fill="url(#fan)" stroke="#976858" stroke-width="3"/>']
    for i in range(9):
        y=207+i*11
        s.append(f'<path d="M278 262 Q226 {y} 165 {y}" fill="none" stroke="#8a4a42" stroke-width="2"/>')
        for j in range(3): s.append(f'<circle cx="{180+j*24}" cy="{y+j%2*4}" r="3" fill="#683e36"/>')
    s.append('<path d="M301 220 Q308 153 348 156 L390 201Z" fill="url(#fan)" stroke="#976858" stroke-width="2"/>')
    for i in range(13):
        x=345+i*22; height=80+102*math.sin(math.pi*i/12)
        tipx=x-30; tipy=200-height
        s.append(f'<path d="M{x} 207 Q{x-7} {tipy+45:.1f} {tipx} {tipy:.1f}" fill="none" stroke="#6c3f3b" stroke-width="5"/>')
        s.append(f'<path d="M{x} 205 Q{x-8} {tipy+45:.1f} {tipx} {tipy:.1f}" fill="none" stroke="#f4ddc5" stroke-width="2"/>')
    s.append(f'<path d="{body}" fill="url(#skin)" stroke="#63463b" stroke-width="3"/>')
    # Unequal curved stripes across the body rather than material-colour rings.
    for i in range(13):
        x=300+i*28; width=10+(i%3)*5
        s.append(f'<path d="M{x} 160 Q{x+23} 225 {x-7} 280 L{x+18} 343 L{x+width+18} 343 Q{x+width-9} 281 {x+width+8} 232 L{x+width} 160Z" clip-path="url(#body)" fill="#793e37"/>')
    s += ['<path d="M657 224 Q630 258 651 301" fill="none" stroke="#5d463b" stroke-width="3"/>',
          '<path d="M682 263 Q703 257 732 262" fill="none" stroke="#4e332e" stroke-width="3"/>',
          '<path d="M669 221 Q668 190 650 183 L666 188 L679 216" fill="#9f6954"/>',
          '<ellipse cx="682" cy="237" rx="16" ry="18" fill="#986b42"/><ellipse cx="686" cy="237" rx="10" ry="13" fill="#17282c"/><circle cx="689" cy="232" r="3" fill="#fff4df"/>',
          f'<path d="{fin}" fill="url(#fan)" stroke="#926254" stroke-width="2"/>']
    for i in range(16):
        a=math.pi*(.15+i*.70/15); x=485-230*math.cos(a); y=270+195*math.sin(a)
        s.append(f'<path d="M595 255 Q{(595+x)/2:.1f} {y-80:.1f} {x:.1f} {y:.1f}" fill="none" stroke="#884c42" stroke-width="4" clip-path="url(#fin)"/>')
        for j in range(1,5):
            t=j/5; px=595+(x-595)*t; py=255+(y-255)*t
            s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="#a46a57" clip-path="url(#fin)"/>')
    labels=[(50,35,'13 dorsal spines',430,75),(747,82,'Eye stays with skull',685,232),(752,321,'Protrusible mouth',725,265),(45,463,'Curved, flexible fan',378,392),(49,164,'Spotted soft fins',206,248)] if annotated else []
    for x,y,text,tx,ty in labels:
        s.append(f'<path d="M{x+100} {y+10} L{tx} {ty}" stroke="#247c83" stroke-width="1.6" fill="none"/><text x="{x}" y="{y}" font-family="sans-serif" font-size="20" fill="#153e46">{text}</text>')
    return svg(''.join(s))

def fin_diagram():
    s=['<rect width="1000" height="290" rx="12" fill="#edf3f1"/>']
    for k,(title,spread) in enumerate([('HOVER · broad',1),('TRAVEL · folded',.48),('TURN · asymmetric',.8)]):
        cx=160+k*330
        s.append(f'<ellipse cx="{cx}" cy="145" rx="22" ry="65" fill="#98594c"/>')
        for side in [-1,1]:
            scale=spread*(.6 if k==2 and side==1 else 1)
            for i in range(9):
                tipx=cx+side*(75+40*math.sin(i*.33))*scale; tipy=110+i*15
                s.append(f'<path d="M{cx} 112 Q{cx+side*45*scale} {tipy-25} {tipx} {tipy}" fill="none" stroke="#b0755f" stroke-width="4"/>')
        s.append(f'<text x="{cx}" y="270" text-anchor="middle" font-family="sans-serif" font-size="21" fill="#153e46">{title}</text>')
    return svg(''.join(s),1000,290)

def strike():
    s=['<rect width="1000" height="230" rx="12" fill="#edf3f1"/>']
    for i,(label,gape) in enumerate([('Aim',0),('Expand',.65),('Capture',1),('Close',.35),('Recover',0)]):
        x=45+i*198
        s += [f'<path d="M{x} 120 Q{x+30} 60 {x+83} 96 L{x+117} {100-gape*20} L{x+125} 117 L{x+91} {129+gape*24} Q{x+50} 170 {x} 120Z" fill="#b27a62" stroke="#643f36" stroke-width="2"/>',
              f'<path d="M{x+87} 114 L{x+123+gape*9} {116+gape*19}" stroke="#342e2c" stroke-width="4"/>',
              f'<circle cx="{x+81}" cy="104" r="6" fill="#203338"/>',
              f'<text x="{x+66}" y="200" text-anchor="middle" font-family="sans-serif" font-size="21" fill="#153e46">{label}</text>']
        if i<3: s.append(f'<ellipse cx="{x+151-i*14}" cy="122" rx="12" ry="7" fill="#db982f"/>')
    return svg(''.join(s),1000,230)

def atlas():
    return svg('''<rect width="1000" height="230" fill="#edf3f1" rx="12"/>
    <defs><pattern id="bands" width="50" height="90" patternUnits="userSpaceOnUse"><rect width="50" height="90" fill="#d9bda0"/><path d="M5 -5 Q35 35 8 95" fill="none" stroke="#7f443a" stroke-width="17"/></pattern><pattern id="spots" width="36" height="28" patternUnits="userSpaceOnUse"><rect width="36" height="28" fill="#c3a78e"/><circle cx="12" cy="12" r="5" fill="#825347"/></pattern></defs>
    <rect x="24" y="20" width="420" height="150" fill="url(#bands)"/><rect x="470" y="20" width="235" height="150" fill="url(#spots)"/><path d="M735 170 Q850 20 976 170Z" fill="url(#spots)" stroke="#925a47" stroke-width="3"/>
    <g font-family="sans-serif" font-size="21" fill="#153e46"><text x="24" y="208">Body: irregular bands</text><text x="470" y="208">Soft fins: spots</text><text x="735" y="208">Rays + membrane</text></g>''',1000,230)

def palettes():
    s=[]
    for i,(label,dark,light) in enumerate([('Wine / cream','#793e37','#f3dec1'),('Umber / sand','#594038','#dcccb0'),('Chestnut / ivory','#9a5143','#eee5d2')]):
        art=fish(False).replace('#793e37',dark).replace('#884c42',dark).replace('#f3dec1',light)
        for name in ['skin','fan','body','fin']:
            art=art.replace(f'id="{name}"',f'id="p{i}{name}"').replace(f'url(#{name})',f'url(#p{i}{name})')
        art=art.replace('viewBox="0 0 1000 510"',f'x="{i*333}" y="0" width="330" height="190" viewBox="0 0 1000 510"')
        s.append(art)
        s.append(f'<text x="{i*333+165}" y="220" text-anchor="middle" font-family="sans-serif" font-size="21" fill="#153e46">{label}</text>')
    return svg(''.join(s),1000,240)

diagrams={'anatomy.svg':fish(),'fin-states.svg':fin_diagram(),'strike.svg':strike(),'texture-study.svg':atlas(),'palette-variants.svg':palettes()}
for name,data in diagrams.items():
    (HERE/name).write_text(data)
    (PLAN/name).write_text(data)

html='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Lionfish — A3 anatomy, texture and motion</title><style>
@page{size:297mm 420mm;margin:0}*{box-sizing:border-box}body{margin:0;background:#d8e3e1;color:#18393e;font-family:"DejaVu Sans",sans-serif}.page{width:297mm;height:420mm;padding:10mm;background:#faf8f1;display:flex;flex-direction:column;gap:3mm;overflow:hidden;margin:auto}h1{font-size:28pt;letter-spacing:-1px;margin:0}h2{font-size:15pt;margin:0 0 2mm}p{font-size:9.5pt;line-height:1.32;margin:0 0 2mm}.eyebrow{font-size:10pt;color:#7c4036;font-weight:bold;letter-spacing:2px}header{border-bottom:2px solid #235c60;padding-bottom:4mm}.legend{display:flex;gap:7mm;font-size:9pt;margin-top:3mm}.hero{background:#e9f1f0;border-radius:3mm;padding:3mm}.hero .hero-images{display:grid;grid-template-columns:1.2fr 1fr;gap:3mm;align-items:center}.hero svg{display:block;width:100%;height:88mm}.hero img{display:block;width:100%;height:70mm;object-fit:contain}.caption{font-size:9pt;color:#4b6669}.cols{display:grid;grid-template-columns:1fr 1fr;gap:5mm}.panel{border-top:1px solid #9fb3b1;padding-top:3mm}.panel svg{display:block;width:100%;height:28mm}strong{color:#7c4036}table{border-collapse:collapse;width:100%;font-size:9pt}td,th{padding:1.3mm;text-align:left;border-bottom:1px solid #c4d1cd}pre{font-size:9pt;line-height:1.45;margin:2mm 0;padding:3mm;background:#18393e;color:#f4ead7}.bottom{background:#e7eee9;padding:3mm;margin-top:auto}footer{font-size:8.5pt;line-height:1.45;border-top:1px solid #9fb3b1;padding-top:3mm}a{color:#145c6b}@media screen{.page{margin:15px auto;box-shadow:0 3px 25px #79918b}}@media print{body{background:white}.page{margin:0;box-shadow:none}}
</style><main class="page"><header><div class="eyebrow">WORLD FOUNDRY · AQUARIUM RESEARCH · 05 OCT 2026</div><h1>LIONFISH<br>Quiet fins. Sudden suction.</h1><p><i>Pterois volitans</i> · Shape, surface and motion in the game asset</p><div class="legend"><span>RESEARCH = cited observations</span><span>PROPOSAL = game design</span><span>SCHEMATIC = original drawing</span></div></header>
<section class="hero"><div class="hero-images"><picture>ANATOMY_SVG</picture><img src="../../plans/2026-10-05-lionfish-realism/runtime/goldfish-close-up.png" alt="Actual Linux engine: two lionfish palettes and a goldfish"></div><p class="caption">LEFT: original anatomy schematic; pectoral ray drawing is illustrative. RIGHT: actual Linux engine capture, shared texture maps and two stable palettes. The mesh includes 13 dorsal, 3 anal and paired pelvic spines. [1, 2]</p></section>
<div class="cols"><section class="panel"><h2>01 · Model the silhouette</h2><p>Deep head, tapering trunk, rounded tail and distinct soft fins. Keep the eye on the skull; open the jaw and throat rather than splitting the entire face. Use 13 tapered dorsal spines and fleshy head tabs. [1, 2]</p><p><strong>IMPLEMENTED:</strong> 4,068 triangles and one visual actor per fish, with named regions and independent UVs. 13 dorsal, 3 anal and paired pelvic spines.</p></section><section class="panel"><h2>02 · Paint a surface, not rings</h2>PALETTE_SVG<p>Uneven red-brown/cream body bands; spotted soft dorsal, anal and tail fins. [1] Separate texture coordinates from deformation weights.</p><p><strong>IMPLEMENTED:</strong> same 256² body/fin maps for every fish; individual stable palettes, including future spawns. Pattern/UVs/alpha stay identical; use existing translucency for fin membranes.</p></section></div>
<div class="cols"><section class="panel"><h2>03 · Fins respond to the task</h2>FINS_SVG<p>Field observations distinguish relaxed posture from travel with fins/spines folded back and more rapid tail strokes. [3] Smooth transitions; keep the roots stable and let curved tips lag.</p><table><tr><th>Observed mean speed</th><th>mm/s</th></tr><tr><td>Relaxed (15 events)</td><td>44.75</td></tr><tr><td>Traverse (12 events)</td><td>138.99</td></tr><tr><td>Strike (5 events)</td><td>625.44</td></tr></table><p class="caption">Small field sample; physical speeds are context, not scene-unit settings or fixed fin frequencies. [3]</p></section><section class="panel"><h2>04 · One coordinated gulp</h2>STRIKE_SVG<p>Suction feeding combines gape, jaw rotation, head motion and hyoid depression. [4] Expansion drives a brief local flow: prey accelerates and can escape. Transfer ownership only on mouth entry; preserve inertia and off-axis convergence. No position tween.</p><p><strong>GAME STARTING POINT:</strong> 0.26 s action / 0.10 s target are game choices. Actual capture requires aperture entry; misses remain possible. Review timing against footage.</p><p>2026 jet-blowing evidence concerns <i>P. miles</i>: useful context, not an automatic behavior rule for this <i>P. volitans</i> asset. [5]</p></section></div>
<section class="bottom"><h2>05 · A small controller, a flexible mesh</h2><div class="cols"><div><p><strong>IMPLEMENTED FORTH INTERFACE</strong></p><pre>\\ phase · drive · turn · gulp
\\ dark · light · actor
: lf-publish ( -- )
  tk-phase tk@ tk-pose-drive tk@
  tk-pose-roll tk@ .012 /
  gf-bite tk@ lf-palette
  650 tk@ lion-pose ;</pre></div><div><p>Publish a compact pose packet; deform cached rest vertices in native code. Keep texture UVs intact. Each fish gets its own phase and turn bias.</p><p>Profile current → mesh/texture → deformation/feeding. Record script/native/render time, draw calls, actors, texture memory and p95 pacing on both Chromecasts. More triangles alone are not a realism or FPS measure.</p></div></div></section>
<footer><b>Sources:</b> <a href="https://www.floridamuseum.ufl.edu/discover-fish/species-profiles/red-lionfish/">[1] Florida Museum: red lionfish</a> · <a href="https://doi.org/10.1242/jeb.197905">[2] Galloway &amp; Porter, spine anatomy/mechanics (2019)</a> · <a href="https://peerj.com/articles/18474/">[3] Kolonay &amp; Glaspie (2025), PeerJ 18474</a> · <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC5192426/">[4] Turingan &amp; Sloan (2016), feeding kinematics</a> · <a href="https://academic.oup.com/beheco/article/37/5/arag087/8741288">[5] Bottacini et al. (2026), jet blowing in P. miles</a>.<br>A3 portrait · 297 × 420 mm · Original editable vector artwork. Anatomy is simplified; wave amplitudes and feeding timing are game settings. Capture is spatial, with pre-entry escape and intraoral transport. Full research and implementation plan accompanies this poster.</footer></main></html>'''
html=html.replace('ANATOMY_SVG',diagrams['anatomy.svg']).replace('ANATOMY<picture>','<picture>')
html=html.replace('PALETTE_SVG',diagrams['palette-variants.svg']).replace('FINS_SVG',diagrams['fin-states.svg']).replace('STRIKE_SVG',diagrams['strike.svg'])
(HERE/'poster.html').write_text(html)
print(HERE/'poster.html')
