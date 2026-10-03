#!/usr/bin/env python3
"""Plan-only runtime-generation diagrams and three independently seeded compositions."""
import importlib.util,math,random
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('poster_art',HERE/'generate-poster.py');art=importlib.util.module_from_spec(spec);spec.loader.exec_module(art)
s=art.SVG(1200,680);s.rect(0,0,1200,680,'#f4f3e9');s.text(30,42,'A new ecosystem each selection — watch its colonies grow',30,weight='bold')
boxes=[(35,85,330,125,'1. Enter Planted Tank','Fresh logged seed; fixed override','for comparisons and bug reports.'),(435,85,330,125,'2. Grow connected colonies','Forth chooses nodes and branches.','Native code stores bounded graphs.'),(835,85,330,125,'3. Seed young plant meshes','Ribbons, rosettes, whorls; eight','groups, not 384 plant actors.'),(835,285,330,125,'4. Grow during play','Runners, daughters, leaf unfurling;','publish validated dirty groups.'),(435,285,330,125,'5. Gentle shared water','Root-pinned native vertex bend;','Forth updates a few coefficients.'),(35,285,330,125,'6. Leave / select again','Release level-owned buffers.','Next selection gets a new seed.')]
for x,y,w,h,title,line1,line2 in boxes:
 s.rect(x,y,w,h,'#dce7cc',12);s.text(x+16,y+35,title,20,weight='bold');s.text(x+16,y+70,line1,17);s.text(x+16,y+99,line2,17)
for a,b,y in [(365,435,147),(765,835,147),(835,765,347),(435,365,347)]:s.path(f'M{a} {y} L{b} {y}',stroke='#638175',sw=3);s.path(f'M{b-9 if b>a else b+9} {y-6} L{b} {y} L{b-9 if b>a else b+9} {y+6}',stroke='#638175',sw=3)
s.path('M1000 210 V285',stroke='#638175',sw=3)
s.text(36,475,'Biological data: founders → connected daughter shoots → age/size → leaf arrangement',24)
s.text(36,527,'Render packaging: merge completed colonies by spatial bounds, independent of lineage',24)
s.text(36,580,'Runtime: young founders → spreading colonies → mature canopy; gentle sway throughout.',21)
s.text(36,631,'Profile loading, generation, mesh construction, deformation, rendering and memory separately.',21)
s.save('runtime-generation-diagram.svg')
s=art.SVG(1200,1370);s.rect(0,0,1200,1370,'#0c2229');s.text(30,42,'Three seeds; different mature outcomes after visible growth',29,'#dfead6');s.text(30,75,'Concepts only — runtime geometry and seed controls still require implementation.',18,'#b9d0bf')
for row,seed in enumerate([713,2049,9173]):
 rng=random.Random(seed);top=110+row*405;s.rect(42,top,1116,320,'#174a4c');s.rect(42,top+286,1116,34,'#b7a987');centres=[]
 for k in range(12):
  cx=rng.uniform(90,1110);radius=rng.uniform(40,115);height=rng.uniform(115,275);kind=rng.choice(['ribbon','rosette','whorl']);centres.append((cx,radius,height,kind))
 for cx,r,h,kind in sorted(centres,key=lambda c:-c[2]):
  for j in range(rng.randint(8,15)):
   x=max(58,min(1140,cx+rng.gauss(0,r*.45)));y=top+290+rng.uniform(-9,8);hh=h*rng.uniform(.6,1)
   if kind=='ribbon':art.tuft(s,x,y,hh,'#71954c',5)
   elif kind=='rosette':art.rosette(s,x,y,hh*.65)
   else:art.stem(s,x,y,hh)
 s.path(f'M42 {top} H1158 V{top+320} H42Z',stroke='#8bbfc7',sw=5)
 s.text(45,top+354,f'Seed {seed}: connected colonies, mixed ages, irregular canopy and local gaps.',21,'#dfead6')
s.text(35,1350,'Mature coverage stays consistent. Each visit starts young and develops along a different growth path.',20,'#dfead6');s.save('seed-variation-mockups.svg')

# Time progression at one seed, distinct from the three-seed mature comparisons.
s=art.SVG(1200,620);s.rect(0,0,1200,620,'#edf1e4');s.text(30,42,'Watch the same seeded colonies spread and mature',29,weight='bold')
for i,(label,scale,n) in enumerate([('Young founders',.22,3),('Expanding colonies',.58,8),('Mature canopy',1.,15)]):
 x0=30+i*400;s.rect(x0,95,370,350,'#174a4c');s.rect(x0,409,370,36,'#b7a987');rng=random.Random(713)
 for centre in [70,175,280]:
  for j in range(n):
   x=x0+centre+rng.uniform(-42,42)*scale;y=415+rng.uniform(-7,7);art.tuft(s,x,y,rng.uniform(185,285)*scale,'#71954c',5)
 s.text(x0,480,label,23,weight='bold')
s.text(30,533,'Small roots first; extending runners; daughter shoots and leaves emerge gradually.',21)
s.text(30,579,'Illustrative growth stages, not engine captures or measured biological timing.',19)
s.save('growth-stages-mockup.svg')
# Seed display and TV-friendly editor concept.
s=art.SVG(1200,800);s.rect(0,0,1200,800,'#0c2229');s.text(30,42,'Seed display and regeneration — proposed controls',29,'#dfead6')
s.rect(35,75,1130,660,'#174a4c');s.rect(35,645,1130,90,'#b7a987')
for i in range(12):art.tuft(s,65+i*95,655,140+70*math.sin(i*.9),'#71954c',5)
s.rect(58,666,430,46,'#102b2a',8);s.text(73,696,'Seed: 713   •   Hold A: change seed',20,'#f5f0df')
s.rect(145,110,910,620,'#f2f1df',16);s.text(182,158,'Plant seed & growth speed',29,weight='bold');s.text(182,196,'Enter seed with the 10-key keypad or phone.',20)
s.rect(182,218,830,52,'#dce7cc',8);s.text(203,253,'713',27,weight='bold')
for i,label in enumerate(['1','2','3','4','5','6','7','8','9','⌫','0','Clear']):
 x=182+(i%3)*116;y=297+(i//3)*73;s.rect(x,y,102,61,'#c6d6ba' if i else '#a2c5a5',7);s.text(x+30,y+40,label,23)
s.text(580,316,'Or type it on your phone',21,weight='bold');s.text(580,348,'Numeric keyboard → same seed field',18)
s.text(580,395,'Growth speed: 1×',21,weight='bold');s.path('M590 422 H990',stroke='#71896a',sw=6);s.circle(755,422,10,'#426954');s.text(580,449,'Paused  0.25×  0.5×  1×  2×  4×  8×',15)
s.rect(580,475,432,50,'#537c5f',8);s.text(605,508,'Regenerate',22,'#f4f3df','bold')
s.rect(580,541,432,48,'#d9dfcd',8);s.text(605,573,'New random seed',21)
s.rect(182,615,830,43,'#d9dfcd',8);s.text(203,644,'Apply speed — keep current plants',20)
s.text(182,696,'← ↑ ↓ → keypad focus   A select   ↶ cancel',19)
s.text(35,777,'Concept: seed is always at bottom left; editor is also available from the selector.',20,'#dfead6');s.save('seed-editor-mockup.svg')
s=art.SVG(1200,460);s.rect(0,0,1200,460,'#f4f3e9');s.text(30,43,'Seed entry → validation → reproducible regeneration',29,weight='bold')
for x,title,body in [(30,'Open editor','Pause growth; keep current tank.'),(420,'Enter decimal seed','0–4294967295; validate first.'),(810,'Regenerate','Fresh young colonies; same rules.')]:
 s.rect(x,93,360,145,'#dce7cc',12);s.text(x+15,132,title,24,weight='bold');s.lines(x+15,172,body,31,19,spacing=26)
s.path('M390 165 H420 M780 165 H810',stroke='#638175',sw=3)
s.text(30,299,'Cancel / ↶: resume the existing tank unchanged. Invalid input: stay in editor with a clear message.',20)
s.text(30,355,'Same seed + generator version + settings → same colony growth at the same simulation time.',21)
s.text(30,410,'New random seed: choose a fresh seed, reset growth time, release old buffers safely, start again.',20)
s.save('seed-regeneration-diagram.svg')

# Complete phone settings; TV is a status mirror when the phone is connected.
s=art.SVG(520,950);s.rect(0,0,520,950,'#eef2e7');s.rect(22,22,476,906,'#faf9f0',24);s.text(47,77,'Plant settings',29,weight='bold');s.text(47,117,'Connected to your aquarium',18,'#53715c');s.text(47,165,'Seed',22,weight='bold');s.rect(47,184,426,62,'#dce7cc',8);s.text(64,225,'713',28);s.text(47,277,'Tap to enter with the numeric keyboard',17);s.text(47,333,'Growth speed',22,weight='bold');s.text(388,333,'1×',22,weight='bold');s.path('M60 368 H454',stroke='#71896a',sw=7);s.circle(215,368,12,'#426954');s.text(47,406,'Paused  0.25×  0.5×  1×  2×  4×  8×',15);s.text(47,456,'Growth age: 24 s · expanding colonies',18);s.text(47,489,'The tank is paused while you edit.',18)
for y,label,color,ink in [(530,'Apply speed','#d3dfc8','#233f32'),(607,'Regenerate with this seed','#537c5f','#faf9f0'),(684,'New random seed','#d3dfc8','#233f32'),(761,'Cancel','#e6e7db','#233f32')]:
 s.rect(47,y,426,60,color,10);s.text(65,y+38,label,21,ink,weight='bold')
s.lines(47,864,'Applying speed keeps your plants. Regenerate starts young colonies again.',42,17,spacing=23)
s.save('phone-settings-mockup.svg')
