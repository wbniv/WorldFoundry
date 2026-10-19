"""Build schematic SVG/HTML review artifacts; these do not generate a WF level."""
from pathlib import Path
from html import escape
OUT=Path(__file__).parent

def pos(x,y,z=0):return 570+(x-y)*2.6,330+(x+y)*1.25-z*8

def line(a,b,color,width=1,extra=''):
 return f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{color}" stroke-width="{width}" {extra}/>'

def text(x,y,t,color='#b5c4cf',size=13):return f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}">{escape(t)}</text>'

def cube(x,y,w,h,color):
 a,b,c,d=[pos(*v) for v in [(x,y,0),(x+w,y,0),(x+w,y+w,0),(x,y+w,0)]]
 at,bt,ct,dt=[pos(*v) for v in [(x,y,h),(x+w,y,h),(x+w,y+w,h),(x,y+w,h)]]
 points=lambda ps:' '.join(f'{p[0]},{p[1]}' for p in ps)
 return ''.join(f'<polygon points="{points(ps)}" fill="{color}" stroke="#d1dce5" stroke-width="1" fill-opacity="{op}"/>' for ps,op in [([a,b,bt,at],'.45'),([b,c,ct,bt],'.65'),([at,bt,ct,dt],'.95')])
svg=['<svg viewBox="0 0 1140 650" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Schematic 200 by 200 unit grid floor with origin, spawn and optional diagnostics" font-family="system-ui,sans-serif">']
svg.append('<polygon points="570,80 1090,330 570,580 50,330" fill="#26313b" stroke="#6c8294"/>')
for i in range(-100,101,10):
 for a,b in [((i,-100),(i,100)),((-100,i),(100,i))]:svg.append(line(pos(*a),pos(*b),'#6b7f8d' if i%50==0 else '#435360',1.5 if i%50==0 else .7))
for i in range(-10,11):
 svg.append(line(pos(i,-10),pos(i,10),'#68808e',.65));svg.append(line(pos(-10,i),pos(10,i),'#68808e',.65))
svg.append(line(pos(-100,0),pos(100,0),'#ef5350',2));svg.append(line(pos(0,-100),pos(0,100),'#66bb6a',2))
for x,y,t in [(100,0,'+X / +100'),(-100,0,'−X / −100'),(0,100,'+Y / +100'),(0,-100,'−Y / −100')]:
 px,py=pos(x,y);svg.append(text(px+8,py-9,t,'#ef5350' if x else '#66bb6a',14))
svg.append(text(570,56,'200 × 200 WORLD UNITS', '#eef5fa',18))
svg.append(text(442,617,'1-unit minor grid · 10-unit major grid',size=15))
svg.append('<circle cx="570" cy="330" r="4" fill="#e9f2f8"/>');svg.append(text(579,319,'ORIGIN (0,0,0)'))
x,y=pos(0,-5);svg.append(f'<ellipse cx="{x}" cy="{y}" rx="8" ry="4" fill="none" stroke="#e5c967" stroke-width="2"/>');svg.append(text(x+15,y-22,'SPAWN + facing','#e5c967'))
svg.append(cube(5,0,1,1,'#cfdfeb'));x,y=pos(5,0,1);svg.append(text(x+14,y+28,'1 × 1 × 1 cube'))
svg.append(line(pos(-5,8),pos(5,8),'#e5c967',4));x,y=pos(-5,8);svg.append(text(x-65,y+27,'10-unit ruler','#e5c967'))
svg.append('<g id="fixtures" style="display:none">')
for x,y,h,c in [(-50,25,4,'#a1c0dd'),(-40,25,8,'#67bed0'),(-30,25,2,'#e5c967')]:svg.append(cube(x,y,5,h,c))
x,y=pos(-50,20);svg.append(text(x-70,y-40,'COLLISION GALLERY','#eef5fa',15))
svg.append(cube(35,25,12,7,'#9488d1'));x,y=pos(35,25,7);svg.append(text(x-25,y-24,'CAMERA / OCCLUSION','#c7baf0',15))
for n in range(5):svg.append(cube(25,-40+n*3,3,1+n*.6,'#d29f66'))
x,y=pos(25,-40);svg.append(text(x-65,y+30,'STEP / SLOPE LANE','#e7bc8b',15))
for i,c in enumerate(['#ef5350','#66bb6a','#42a5f5','#e8eef2']):svg.append(cube(-40,-35+i*5,4,.4,c))
x,y=pos(-40,-35);svg.append(text(x-50,y-16,'UV + MATERIALS','#eef5fa',15))
svg.append('</g></svg>')
scene=''.join(svg)
axes='''<svg viewBox="0 0 280 240" role="img" aria-label="Magnified unit basis vectors: red X, green Y, blue Z"><defs><marker id="r" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#ef5350"/></marker><marker id="g" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#66bb6a"/></marker><marker id="b" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#42a5f5"/></marker></defs><g fill="none" stroke-width="3"><path d="M125 145L230 195" stroke="#ef5350" marker-end="url(#r)"/><path d="M125 145L25 195" stroke="#66bb6a" marker-end="url(#g)"/><path d="M125 145L125 30" stroke="#42a5f5" marker-end="url(#b)"/></g><g font-family="system-ui" font-size="14"><text x="210" y="220" fill="#ef5350">X (1,0,0)</text><text x="0" y="220" fill="#66bb6a">Y (0,1,0)</text><text x="137" y="32" fill="#42a5f5">Z (0,0,1)</text><text x="130" y="143" fill="#dde7ed">(0,0,0)</text></g></svg>'''
html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>World Foundry baseline — review mockups</title><style>*{box-sizing:border-box}body{margin:0;background:#111923;color:#dce7ef;font:15px/1.5 system-ui,sans-serif}header{padding:25px 36px;border-bottom:1px solid #374653;display:flex;align-items:center;justify-content:space-between;gap:20px}h1{font-size:24px;margin:0}small,.muted{color:#99afbf}button{font:inherit;color:inherit;border:1px solid #516779;border-radius:6px;padding:9px 15px;background:#22313f;cursor:pointer}button[aria-pressed=true]{background:#c8e5fa;color:#152636}main{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:22px;padding:24px 30px}.scene{border:1px solid #3d4d5a;border-radius:8px;background:#1b2530;overflow:hidden}.scene header{padding:14px 20px;font-size:13px}.scene>svg{width:100%;display:block;min-height:480px}.legend{padding:15px 22px;border-top:1px solid #374653;display:flex;gap:22px;flex-wrap:wrap}.card{border:1px solid #3d4d5a;border-radius:8px;padding:18px;margin-bottom:16px;background:#1b2530}h2{font-size:15px;margin:0 0 12px}aside svg{width:100%}ul{padding-left:20px;font-size:13px}p{margin:9px 0;font-size:13px}.pill{color:#a8d9f9}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:#e5c967}.diagram-note{padding:0 30px;color:#99afbf}@media(max-width:800px){main{grid-template-columns:1fr}header{flex-wrap:wrap}.scene>svg{min-height:0}}</style><header><div><h1>World Foundry / clean baseline</h1><small>SCHEMATIC REVIEW · proposed scene, not a runtime capture</small></div><div><button id="default" aria-pressed="true">Default baseline</button> <button id="diagnostics" aria-pressed="false">Diagnostics preset</button></div></header><main><section class="scene"><header><strong id="mode">Sparse default · one room</strong><span class="muted">Z-up authoring · verify runtime mapping</span></header>SCENE<div class="legend"><span><i class="dot"></i>Spawn + ruler</span><span class="pill">200 × 200 floor</span><span class="muted">Minor grid shown near origin; major grid across floor</span></div></section><aside><div class="card"><h2>UNIT AXES · magnified detail</h2>AXES<p>Three orthogonal 1-unit arrows. Labels are exported meshes/textures.</p><p class="muted">X red · Y green · Z blue. Magnification is for this review preview.</p></div><div class="card"><h2>DEFAULT INVENTORY</h2><ul><li>Player proxy + camera rig</li><li>Directional + ambient lighting</li><li>Gridded collision floor</li><li>Origin frame + spawn marker</li><li>Unit cube + 10-unit ruler</li></ul></div><div class="card"><h2>OPTIONAL COLLECTIONS</h2><p>Collision shapes · slope / steps · camera targets · UV / material tests</p><p class="muted">Excluded from default export.</p></div></aside></main><p class="diagram-note">Reset to spawn · explicit actor defaults · editable .blend · independent build · existing native runtime</p><script>function select(on){document.getElementById('fixtures').style.display=on?'':'none';document.getElementById('default').setAttribute('aria-pressed',String(!on));document.getElementById('diagnostics').setAttribute('aria-pressed',String(on));document.getElementById('mode').textContent=on?'Diagnostics preset · optional fixtures enabled':'Sparse default · one room';}document.getElementById('default').onclick=()=>select(false);document.getElementById('diagnostics').onclick=()=>select(true);if(location.hash==='#diagnostics')select(true);</script></html>'''.replace('SCENE',scene).replace('AXES',axes,1)
# Replace only the placeholder; keep the unit-axes heading intact.
html=html.replace('UNIT '+axes,'UNIT AXES').replace('>AXES<','>'+axes+'<') if 'UNIT '+axes in html else html
# Placeholder replacement above occurs in heading first; correct by rebuilding explicit section.
start=html.index('<h2>UNIT ');end=html.index('<p>Three orthogonal',start)
html=html[:start]+'<h2>UNIT AXES · magnified detail</h2>'+axes+html[end:]
(OUT/'mockups.html').write_text(html)
layout='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 390" font-family="system-ui,sans-serif"><rect width="1000" height="390" rx="12" fill="#17232e"/><text x="35" y="43" fill="#e6eef5" font-size="24">Baseline collection hierarchy</text>'''
for x,y,w,h,title,sub,color in [(35,75,290,100,'CORE','Player · camera · room · lights','#86bfdc'),(35,205,290,110,'GROUND','200 × 200 · aligned 1/10 grid','#b9c8d4'),(365,75,280,100,'DEBUG_DEFAULT','RGB unit axes · spawn · cube · ruler','#e5c967'),(365,205,280,110,'DEBUG_OPTIONAL','Collision · slopes · UV · camera tests','#ad98df'),(690,130,270,130,'EXPORT PRESET','Default: core + ground + references','#a8d8b2')]:
 layout+=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#223340" stroke="{color}"/><text x="{x+16}" y="{y+32}" fill="{color}" font-size="17">{title}</text><text x="{x+16}" y="{y+62}" fill="#dbe5ed" font-size="12">{sub}</text>'
layout+='<text x="35" y="355" fill="#99afbf" font-size="14">Default export excludes optional fixtures. Configuration replaces inherited Snowgoons content.</text></svg>'
(OUT/'layout.svg').write_text(layout)
print(OUT/'mockups.html')
