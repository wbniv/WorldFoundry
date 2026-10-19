#!/usr/bin/env python3
"""Planning SVGs only: no engine/model changes or engine captures."""
from pathlib import Path
from html import escape
P=Path(__file__).resolve().parent

def label(x,y,t,size=18,color='#183440'):
 return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}">{escape(t)}</text>'
def shrimp(x,y,scale=1,kind='jelly',flip=False):
 col='#218cd1' if kind=='jelly' else '#123ea0'
 op='.28' if kind=='jelly' else '.88'
 z=f'<g transform="translate({x} {y}) scale({-scale if flip else scale} {scale})">'
 # Articulated silhouette; alpha applies to shell, not opaque eyes/internal cue.
 z+='<path d="M-30,-8 Q-5,-32 26,-14 Q45,-12 47,2 L28,12 Q9,3 -19,17 L-35,12 Z" fill="'+col+'" fill-opacity="'+op+'" stroke="#45a6d4" stroke-opacity=".65" stroke-width="1.2"/>'
 z+='<path d="M-35,5 L-56,-7 L-55,15 L-40,19 L-27,11 Z" fill="'+col+'" fill-opacity="'+op+'"/>'
 z+='<path d="M-25,-8 L-19,13 M-13,-15 L-7,10 M0,-19 L6,7 M13,-19 L19,7" fill="none" stroke="#73bedd" stroke-opacity=".65" stroke-width="1.2"/>'
 if kind=='jelly':
  z+='<path d="M-29,7 Q-4,-1 24,-3" fill="none" stroke="#827263" stroke-width="2" opacity=".7"/><ellipse cx="26" cy="-2" rx="8" ry="5" fill="#b7a582" opacity=".5"/>'
 z+='<path d="M-17,13 L-24,29 M-4,10 L-8,30 M9,9 L13,29 M23,11 L30,29 M34,9 L45,25 M43,-4 Q68,-28 92,-19 M44,-2 Q70,-10 101,1" fill="none" stroke="#59aeca" stroke-opacity=".48" stroke-width="1.4"/>'
 z+='<circle cx="42" cy="-9" r="3.3" fill="#071a26"/><circle cx="42.8" cy="-10" r=".8" fill="white"/>'
 z+='</g>'
 return z

def svg(content,w=1200,h=700):
 return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" fill="#f3f8fa"/><g font-family="sans-serif">{content}</g></svg>'

z=label(28,36,'Blue Jelly + Blue Dream — material and silhouette study',25)
z+=label(28,65,'Illustrative mockups, not engine renders. Proposed opacities are art tuning, not biological measurements.',15)
for x,name,kind in [(30,'Blue Jelly','jelly'),(625,'Blue Dream','dream')]:
 z+=f'<rect x="{x}" y="94" width="545" height="267" rx="8" fill="#d0e5e6"/>'
 for bx in range(x+15,x+535,40):z+=f'<path d="M{bx},105 V347" stroke="#66939c" opacity=".24" stroke-width="12"/>'
 z+=shrimp(x+242,230,3.15,kind)+label(x+18,123,name,22)
 z+=label(x+18,327,'Body opacity 0.28; pale blue shell' if kind=='jelly' else 'Body opacity 0.88; deep blue coverage',16)
z+=label(30,395,'Blue Jelly: tank scenery shows through the body;',17)+label(30,421,'dark eyes and a restrained internal cue retain its shape.',17)
z+=label(625,395,'Blue Dream: much denser body colour;',17)+label(625,421,'legs and antennae remain lightly translucent.',17)
z+=label(30,471,'Same rig and body proportions; distinct material variants',20)
z+=shrimp(155,559,1.3,'jelly')+shrimp(470,559,1.3,'dream')
z+=label(30,625,'Keep both readable at the wide camera; do not make pale shrimp disappear against bright sand.',16)
(P/'varieties.svg').write_text(svg(z,h=670))

z=label(28,35,'One planted Blue Shrimp tank — mixed colony',25)+label(28,63,'24 total: 12 Blue Jelly + 12 Blue Dream; one Blue Jelly is the proposed player.',16)
z+='<rect x="30" y="95" width="1140" height="460" rx="10" fill="#bed9dc" stroke="#537780" stroke-width="7"/><path d="M38,136 H1162" stroke="#f4ffff" stroke-width="4"/>'
z+='<path d="M36,491 Q330,472 620,497 Q880,476 1164,490 V550 H36 Z" fill="#d9c9a2"/>'
for x in [90,140,1030,1080,1120]:
 z+=f'<path d="M{x},488 Q{x-35},330 {x-13},211 M{x},482 Q{x+32},360 {x+24},274" stroke="#528c66" stroke-width="12" fill="none"/>'
z+='<ellipse cx="295" cy="463" rx="135" ry="67" fill="#697977"/><ellipse cx="941" cy="475" rx="107" ry="43" fill="#71807a"/><path d="M490,477 Q612,383 747,324 L877,271" stroke="#94765b" stroke-width="24" fill="none"/><path d="M643,397 L613,298" stroke="#94765b" stroke-width="14"/>'
# Fixed design layout: both morphs represented across sand, rock, wood and water.
points=[(90,510),(182,501),(274,504),(372,506),(459,501),(559,513),(662,505),(772,506),(862,514),(965,505),(1065,516),(1131,510),(210,424),(299,402),(384,431),(856,449),(960,435),(1042,460),(571,414),(682,365),(824,306),(401,246),(937,224),(583,269)]
for i,(x,y) in enumerate(points):z+=shrimp(x,y,.48 if i<18 else .56,'jelly' if i%2==0 else 'dream',i%3==0)
z+='<circle cx="90" cy="510" r="29" stroke="#e49324" stroke-width="2" stroke-dasharray="5 4" fill="none"/>'
z+=label(30,594,'Pale blue: Jelly     •     Deep blue: Dream     •     Dashed ring: proposed player framing, not a HUD feature',17)
z+=label(30,626,'Mixed grazing patches and excursions; retain existing routes and total count. Positions here are illustrative.',16)
(P/'mixed-tank.svg').write_text(svg(z,h=655))

z=label(28,35,'Shared rig, two material sets, one colony',25)
boxes=[(30,75,350,105,'Shared five-part rig',['body • tail • near legs • far legs • antennae']),(440,75,330,105,'Blue Jelly materials',['light blue shell + clear appendages','dark eyes; restrained internal cue']),(820,75,350,105,'Blue Dream materials',['deep blue shell + clear appendages','dark eyes; shared silhouette']),(30,237,350,105,'Deterministic assignment',['12 Jelly / 12 Dream at count 24','player included; no extra animals']),(440,237,330,105,'Existing controller + routes',['same actor blocks / pivots / bounds','mixed substrate, rock, wood, swims']),(820,237,350,105,'Shared translucency renderer',['opaque scenery / eyes first','camera-sorted shell triangles'])]
for x,y,w,h,title,lines in boxes:
 z+=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#e0edf2" stroke="#87a9b8"/>'+label(x+14,y+30,title,19)
 for i,t in enumerate(lines):z+=label(x+14,y+59+23*i,t,14)
for d in ['M380,125 H440','M770,125 H820','M205,180 V237','M380,290 H440','M770,290 H820']:
 z+=f'<path d="{d}" stroke="#416477" stroke-width="2" marker-end="url(#arrow)" fill="none"/>'
z+=label(30,399,'Risk to inspect in close-up: intersecting body/tail ellipsoids can accumulate tint.',18)
z+=label(30,435,'Keep intended shell depth; remove accidental duplicate overlap. Do not make every part double-sided.',16)
z+=label(30,477,'First validate 1 Jelly + 1 Dream; then the mixed 24-shrimp colony and device frame cost.',17)
raw=svg(z,h=520).replace('<rect width=', '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#416477"/></marker></defs><rect width=',1)
(P/'rig-and-materials.svg').write_text(raw)
(P/'mockups.html').write_text('<!doctype html><meta charset="utf-8"><title>Mixed blue shrimp — planning mockups</title><style>body{margin:0;background:#f3f8fa}img{display:block;width:1200px;max-width:100%}</style>'+''.join(f'<img src="{n}.svg">' for n in ['varieties','mixed-tank','rig-and-materials']))
