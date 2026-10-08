#!/usr/bin/env python3
"""Original vector diagrams for the generic deformation design proposal."""
from pathlib import Path
import math
HERE=Path(__file__).resolve().parent
INK='#183b43';TEAL='#167c86';PINK='#b86580';GOLD='#b88832'
def text(x,y,s,size=20,color=INK):
 return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-family="DejaVu Sans,sans-serif">{s}</text>'
def box(x,y,w,h,title,lines,color='#e3eee7'):
 return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{color}" stroke="#9ab8af"/>'+text(x+18,y+31,title,22)+''.join(text(x+18,y+62+i*26,line,17) for i,line in enumerate(lines))
def arrow(points):
 return '<polyline points="'+points+'" stroke="'+TEAL+'" stroke-width="3" fill="none" marker-end="url(#arrow)"/>'
def save(name,body,w=1200,h=520,title='Design diagram'):
 content=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title"><title id="title">{title}</title><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9Z" fill="{TEAL}"/></marker></defs><rect width="{w}" height="{h}" rx="18" fill="#f0f4ef"/>{body}</svg>'
 (HERE/name).write_text(content)
body=text(28,40,'AUTHORED DATA + FORTH BEHAVIOR → SHARED MESH EVALUATION',25)
body+=box(25,80,330,130,'OAS → OAD',['Parameter names, ranges, defaults','Explicit channel/settings bindings'])
body+=box(25,250,330,145,'Mesh + rig authoring',['Rest geometry, roots, pivots','Curves, vertex influences, UVs'])
body+=box(435,155,300,155,'Validate + cook',['DFRM descriptors / numeric indices','Cache immutable rest data'])
body+=arrow('355,145 395,145 395,195 435,195')+arrow('355,315 395,315 395,270 435,270')
body+=box(820,80,355,130,'Forth controller',['Flow / withdrawal / action timing','Publish one channel block per actor'])
body+=box(820,270,355,140,'Shared native evaluator',['Snapshot channels; evaluate rig','Update one writable mesh'])
body+=arrow('735,235 780,235 780,340 820,340')+arrow('995,210 995,270')
body+=text(30,463,'Texture UVs remain texture UVs. Behavior stays in Forth. Curves are data inside the actor.',20)
body+=text(30,496,'Proposed architecture · no engine implementation or performance result implied',17)
save('data-flow.svg',body)
body=text(28,40,'THREE OPERATIONS, MANY POSSIBLE ACTORS',25)
for k,title in enumerate(['ROOTED CURVE','WEIGHTED TRANSFORM','TRAVELLING WAVE']):
 x=20+k*395
 body+=f'<rect x="{x}" y="65" width="375" height="330" rx="12" fill="#e3eee7"/>'+text(x+20,100,title,23)
 if k==0:
  body+=f'<path d="M{x+90} 300 L{x+90} 150" stroke="#839b97" stroke-width="12" stroke-dasharray="8 7"/>'
  body+=f'<path d="M{x+90} 300 C{x+90} 230 {x+145} 195 {x+245} 145" stroke="{PINK}" stroke-width="16" fill="none" stroke-linecap="round"/>'
  for j in range(9):
   u=j/8;cx=x+90+155*u*u;cy=300-155*u
   body+=f'<circle cx="{cx}" cy="{cy}" r="4" fill="{TEAL}"/>'
  body+=f'<circle cx="{x+90}" cy="300" r="10" fill="{TEAL}"/>'+text(x+24,341,'Stable root; centerline bends',18)+text(x+24,374,'Tentacle · stem · antenna',18)
 elif k==1:
  body+=f'<path d="M{x+88} 280 L{x+285} 280" stroke="#839b97" stroke-width="12" stroke-dasharray="8 7"/>'
  body+=f'<path d="M{x+88} 280 L{x+270} 170" stroke="{PINK}" stroke-width="16" stroke-linecap="round"/>'
  body+=f'<path d="M{x+150} 280 Q{x+155} 240 {x+140} 221" stroke="{TEAL}" stroke-width="3" fill="none" marker-end="url(#arrow)"/>'
  body+=f'<circle cx="{x+88}" cy="280" r="10" fill="{TEAL}"/>'+text(x+24,341,'Pivot + weights + transform',18)+text(x+24,374,'Jaw · fin fold · body contraction',18)
 else:
  pts=[]
  for j in range(61):
   u=j/60;pts.append(f'{x+30+315*u:.1f},{235+45*u*u*math.sin(u*math.tau*1.5):.1f}')
  body+=f'<path d="M{x+30} 235 H{x+345}" stroke="#839b97" stroke-width="6" stroke-dasharray="8 7"/>'
  body+=f'<polyline points="{" ".join(pts)}" stroke="{PINK}" stroke-width="10" fill="none"/>'
  body+=arrow(f'{x+140},160 {x+290},160')+text(x+24,341,'Phase travels through a mask',18)+text(x+24,374,'Fish tail · membrane · leaf',18)
body+=text(28,439,'Same evaluator, different rig data and local axes. These are schematic operations, not final poses.',19)
save('operators.svg',body,h=470)
body=text(28,40,'ANEMONE: A DEFORMING DISC OWNS THE TENTACLE ROOT FRAMES',25)
for k,(title,shrink,flow) in enumerate([('REST',1,0),('GENTLE FLOW',1,42),('WITHDRAWAL',.35,12)]):
 cx=190+k*395
 body+=text(cx-95,90,title,22)
 foot=355;disc=foot-90*shrink
 body+=f'<path d="M{cx-55} {foot} Q{cx-40} {disc+25} {cx-80} {disc} L{cx+80} {disc} Q{cx+40} {disc+25} {cx+55} {foot}Z" fill="#bd8890"/>'
 body+=f'<ellipse cx="{cx}" cy="{disc}" rx="80" ry="15" fill="#965d74"/>'
 for j in range(7):
  x=cx-66+j*22;lean=(j-3)*16*shrink;length=(100+(j%3)*13)*shrink
  body+=f'<path d="M{x} {disc} C{x} {disc-length*.4} {x+lean+flow*.5} {disc-length*.75} {x+lean+flow} {disc-length}" stroke="{PINK}" stroke-width="11" stroke-linecap="round" fill="none"/>'
  body+=f'<circle cx="{x}" cy="{disc}" r="5" fill="{TEAL}"/>'
 body+=f'<path d="M{cx-140} {foot+10} H{cx+140}" stroke="#788d86" stroke-width="15"/>'
 body+=f'<path d="M{cx-52} {foot} H{cx+52}" stroke="{TEAL}" stroke-width="7"/>'
 body+=text(cx-144,403,'Foot anchor stays on rock',18)
body+=text(28,447,'Evaluation order: column/disc transform → root frames → 48 curves → vertex positions',21)
body+=text(28,484,'All curve groups belong to one visual actor. A pose call does not create 48 actor updates.',19)
save('anemone-hierarchy.svg',body)
body=text(28,40,'CHANNEL PACKET → ONE ACTOR → MANY INTERNAL GROUPS',25)
body+=box(25,90,325,220,'Pose values',['phase       0..1 turns','flow-x      bounded scalar','flow-y      bounded scalar','withdrawal  0..1','Example only; rig declares bindings'])
body+=box(435,125,270,155,'deform-apply',['One native pose submission','Snapshot and validate all inputs'])+arrow('350,180 435,180')
body+=box(800,75,375,255,'One anemone mesh actor',['Body transform group','48 rooted curve descriptors','3,420 authored vertices','5,756 authored triangles','Geometry counts are measured;','runtime costs remain unmeasured'])+arrow('705,200 800,200')
body+=text(28,376,'Shared per asset: rig, rest curves, influence tables. Per instance: channels, response state, mesh output.',18)
body+=text(28,420,'Forth publishes controls; native evaluation visits curves/vertices. No per-vertex mailbox traffic.',20)
save('pose-packet.svg',body,h=450)
# An analytic design plot, explicitly not benchmark or measured tissue motion.
body=text(28,40,'DESIGN WEIGHT: KEEP THE ROOT QUIET, GIVE THE TIP MORE MOTION',25)
body+=f'<path d="M100 80 V340 H660" stroke="{INK}" stroke-width="2" fill="none"/>'
for i in range(5):
 u=i/4;x=100+560*u;y=340-250*u
 body+=f'<path d="M{x} 340 V80 M100 {y} H660" stroke="#cad9d2" stroke-width="1"/>'+text(x-12,370,f'{u:g}',17)+text(54,y+6,f'{u:g}',17)
points=' '.join(f'{100+560*j/100:.1f},{340-250*(j/100)**2:.1f}' for j in range(101))
body+=f'<polyline points="{points}" stroke="{TEAL}" stroke-width="5" fill="none"/>'+text(290,414,'Root-to-tip coordinate u',20)
body+=box(740,115,415,210,'Illustrative weighting: w = u²',['u = 0       → w = 0: fixed root','u = 0.5     → w = 0.25','u = 1       → w = 1: strongest response','Authored masks may use other curves.'])
body+=text(28,460,'Analytic design curve only: not measured biology, motion amplitude or Chromecast performance.',18)
save('root-weight-chart.svg',body,h=490)
print('Generated 5 SVG design diagrams')
