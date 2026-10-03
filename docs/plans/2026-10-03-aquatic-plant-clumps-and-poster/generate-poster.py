#!/usr/bin/env python3
"""Original vector botanical schematics, A3 portrait poster and plan diagrams."""
from pathlib import Path
import math,random,textwrap,html,os
HERE=Path(__file__).resolve().parent
W,H=1188,1680
class SVG:
 def __init__(self,w=W,h=H,physical=False):
  self.w,self.h=w,h;self.s=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '+('width="297mm" height="420mm" ' if physical else '')+f'viewBox="0 0 {w} {h}"><style>text{{font-family:DejaVu Sans,sans-serif}}</style>']
 def rect(self,x,y,w,h,c,rx=0):self.s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" rx="{rx}"/>')
 def path(self,d,c='none',stroke='#456d4e',sw=2,opacity=1):self.s.append(f'<path d="{d}" fill="{c}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round"/>')
 def circle(self,x,y,r,c):self.s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>')
 def text(self,x,y,s,size=20,color='#22372d',weight='normal',mono=False):self.s.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}"'+(' style="font-family:DejaVu Sans Mono,monospace"' if mono else '')+'>'+html.escape(s)+'</text>')
 def lines(self,x,y,s,width=40,size=20,color='#375145',spacing=29):
  for i,line in enumerate(textwrap.wrap(s,width)):self.text(x,y+i*spacing,line,size,color)
 def save(self,name):self.s.append('</svg>');(HERE/name).write_text(''.join(self.s))
def blade(s,x,y,dx,dy,width,c):
 a=f'M{x},{y} Q{x+dx*.35-width},{y+dy*.35} {x+dx},{y+dy} Q{x+dx*.65+width},{y+dy*.65} {x},{y}'
 s.path(a,c,'#41683f',1.5);s.path(f'M{x},{y} Q{x+dx*.5},{y+dy*.6} {x+dx},{y+dy}','none','#bdd68b',1)
def tuft(s,x,y,h=120,c='#699348',n=7):
 for j in range(n):
  a=(j/(n-1)-.5)*1.5;blade(s,x,y,math.sin(a)*h*.60,-h*(.72+.25*math.cos(j*1.8)),4 if h>100 else 2,c)
def rosette(s,x,y,h=95,c='#637f43'):
 for j in range(7):
  a=j*math.tau/7;blade(s,x,y,math.cos(a)*h*.72,-h*(.50+.45*(j%3)/2),h*.15,c if j%2 else '#84975b')
def paddle(s,x,y):
 s.path(f'M{x-85},{y} Q{x},{y-22} {x+100},{y+8}',stroke='#936b42',sw=5)
 for k in range(5):
  xx=x-70+k*37;yy=y-9+math.sin(k)*5
  for side in (-1,1):blade(s,xx,yy,side*17,-35-(k%2)*12,13,'#8aac6b')
  s.path(f'M{xx},{yy} l-8,21 m8,-21 l10,17',stroke='#a18558',sw=2)
def branch(s,x,y,length,depth=3,angle=0,c='#956d3e'):
 xx=x+math.sin(angle)*length;yy=y-math.cos(angle)*length
 s.path(f'M{x},{y} Q{(x+xx)/2+5},{(y+yy)/2} {xx},{yy}',stroke=c,sw=3+depth*2)
 if depth:
  branch(s,xx,yy,length*.70,depth-1,angle-.40,c);branch(s,xx,yy,length*.64,depth-1,angle+.46,c)
def stem(s,x,y,h=140):
 s.path(f'M{x},{y} Q{x+15},{y-h*.5} {x+6},{y-h}',stroke='#6b934d',sw=3)
 for j in range(6):
  yy=y-h*(.15+j*.14)
  for side in (-1,1):
   s.path(f'M{x+5},{yy} l{side*38},-15',stroke='#56956c',sw=2)
   for k in range(1,5):s.path(f'M{x+5+side*k*7},{yy-k*3} l{side*3},-13',stroke='#6ca979',sw=2)
def card(s,x,y,title,sub,desc,kind):
 s.rect(x,y,530,288,'#eef1df',14)
 if kind=='tuft':tuft(s,x+104,y+218,172)
 if kind=='paddle':paddle(s,x+105,y+179)
 if kind=='branch':branch(s,x+101,y+241,80,3)
 if kind=='rosette':rosette(s,x+103,y+225,145)
 if kind=='stem':stem(s,x+102,y+237,207)
 s.lines(x+216,y+34,title,22,25,'#233f32',spacing=29)
 s.lines(x+216,y+92,sub,30,17,'#536b57',spacing=23)
 s.lines(x+216,y+155,desc,28,18,spacing=25)
s=SVG(physical=True);s.rect(0,0,W,H,'#fbf8ef');s.rect(0,0,W,128,'#183c36')
s.text(32,50,'AQUATIC PLANTS:',40,'#f6f3df','bold');s.text(32,92,'HOW PATCHES GROW',40,'#f6f3df','bold')
s.text(650,48,'Real growth forms',19,'#c3d9bf');s.text(650,78,'Connected colonies',19,'#c3d9bf');s.text(650,108,'Gentle water movement',19,'#c3d9bf')
s.rect(0,128,594,1132,'#edf3ea');s.rect(594,128,594,1132,'#f5f0df')
s.text(32,177,'SALTWATER',32,'#275953','bold');s.text(626,177,'FRESHWATER',32,'#56643e','bold')
s.lines(32,211,'Seagrasses are flowering plants; seaweeds are algae. A holdfast is not a root. [S1]',50,18,spacing=23)
s.lines(626,211,'Habitat-informed references for betta and tiger barbs; regional overlap is not co-occurrence. [S7]',50,18,spacing=23)
card(s,32,286,'Eelgrass','Zostera marina • temperate coasts [S1]','Ribbon leaves arise from shoots linked by buried rhizomes. New shoots build connected meadows.','tuft')
card(s,32,591,'Paddle-leaf seagrass','Halophila ovalis • tropical coasts [S2]','Small paired leaves and creeping rhizomes create a low spreading carpet: a different silhouette from eelgrass.','paddle')
card(s,32,896,'Branching brown algae','Fucus vesiculosus • temperate shores [S3]','Tips repeatedly fork. A holdfast anchors the thallus. A branching alga is not a flowering stem.','branch')
card(s,626,286,'Broad-leaf crypt','Cryptocoryne cordata • SE Asia [S4]','Rhizomes and slender runners connect daughter rosettes. Variable leaves overlap in irregular patches.','rosette')
card(s,626,591,'Ribbon-leaf runner','Vallisneria spiralis • Thailand included [S5]','Stolons link new tufts. Spacer length and branching alter how widely the clone occupies the substrate.','tuft')
card(s,626,896,'Feathery stem growth','Limnophila sessiliflora • E / SE Asia [S6]','Finely divided submerged leaves form whorls. Use varied nodes and branches rather than identical paired-leaf ladders.','stem')
s.lines(32,1211,'Marine forms shown separately: Fucus is not a tropical reef plant.',54,16,'#395b4a',spacing=21)
s.lines(626,1206,'Betta: Thai emergent margins. Tiger barb: Sumatran freshwater. Regional flora, not one shared biotope. [S7]',59,15,'#4a5c40',spacing=19)
# Exactly bottom quarter: 315 mm from the top of the portrait page.
s.rect(0,1260,W,420,'#173b35');s.text(32,1297,'CLUMPING & BRANCHING: SMALL RULES, RICH PATTERNS',25,'#f4efd8','bold')
for x,y,label in [(32,1331,'Connected daughters'),(626,1331,'Compact vs spreading'),(32,1494,'Branching tips'),(626,1494,'Root-pinned sway')]:s.text(x,y,label,22,'#d6e2bd','bold')
for k in range(4):
 x=48+k*43;y=1410+math.sin(k*.8)*7
 if k:s.path(f'M{x-43},{1410+math.sin((k-1)*.8)*7} L{x},{y}',stroke='#ac916b',sw=3)
 rosette(s,x,y,24,'#7ca66a')
s.lines(238,1361,'Parent-to-daughter growth makes local connected colonies. [S4, S5]',31,16,'#d4e0d1',spacing=22)
for k in range(14):
 a=k*2.399;r=7+1.5*k;s.circle(667+math.cos(a)*r,1383+math.sin(a)*r*.8,4,'#aed38b')
for k in range(7):s.circle(736+k*11,1367+(k%3)*18,4,'#aed38b')
s.path('M700 1383 L727 1383',stroke='#c4b183',sw=2)
s.lines(830,1361,'Short spacers pack shoots; longer steps spread them. Species differ. [S8]',33,16,'#d4e0d1',spacing=22)
branch(s,119,1583,29,2,c='#bdb27a')
s.lines(238,1524,'Tip grammar: F → F[+F][-F]. Add unequal growth, varying angles and stops. [S8]',33,16,'#d4e0d1',spacing=22)
s.path('M687 1572 Q675 1535 687 1514',stroke='#bdd792',sw=4);s.path('M687 1572 Q705 1535 720 1514',stroke='#bdd792',sw=4,opacity=.65);s.circle(687,1572,5,'#e4d0a3')
s.lines(830,1524,'Roots stay fixed; tips bend more. Neighbours share slow flow. Visual model, not CFD. [S9]',33,16,'#d4e0d1',spacing=22)
for x,y,code in [(32,1447,': cluster-j + 1 - ;'),(626,1447,': fork-angle .08 * + ;'),(32,1610,': leaf-turn / ;'),(626,1610,': tip-weight 0 max 1 min dup * ;')]:s.text(x,y,code,17,'#ffe0a5',mono=True)
s.text(32,1637,'Forth inputs: two uniform values • headings in turns, ±1 side • index/count • normalized tip height.',14,'#b4cfbf')
s.text(32,1657,'S1 NOAA / S2 Kew / S3 Turku / S4 Kew + Wong / S5 Kew + experiment / S6 UF',13,'#b4cfbf')
s.text(32,1674,'S7 habitat studies / S8 growth models / S9 flow model. Illustrative code; source links in companion plan.',13,'#b4cfbf')
s.save('aquatic-plants-a3.svg')
# root network top-down diagram
s=SVG(1200,570);s.rect(0,0,1200,570,'#f6f4e8');s.text(35,43,'Biological clumps are independent of render chunks',29,weight='bold')
rng=random.Random(92)
for cx,cy,r in [(200,190,100),(430,285,135),(700,155,105),(890,320,140),(1080,180,70)]:
 s.circle(cx,cy,r,'#dce6c8');nodes=[(cx,cy)]
 for k in range(22):
  px,py=rng.choice(nodes);a=rng.uniform(0,math.tau);step=rng.uniform(18,46);x=px+math.cos(a)*step;y=py+math.sin(a)*step
  if math.hypot(x-cx,y-cy)>r:continue
  nodes.append((x,y));s.path(f'M{px},{py} L{x},{y}',stroke='#8c7d52',sw=2);s.circle(x,y,6,'#658a4e')
for x in [300,600,900]:s.path(f'M{x} 70 L{x} 445',stroke='#a7adb0',sw=1,opacity=.55)
s.text(35,486,'Brown edges: connected parent/daughter growth. Green dots: rooted shoots.',22)
s.text(35,522,'Faint boundaries: packaging only. Never use them to align the plants into rows.',22)
s.save('clumping-diagram.svg')
# water bending conceptual diagram
s=SVG(1200,510);s.rect(0,0,1200,510,'#eef3e6');s.text(30,45,'Shared flow; fixed roots; increasing bend toward tips',28,weight='bold')
for i in range(5):
 x=110+i*210;tuft(s,x,340,190,'#74954e',5);s.path(f'M{x} 340 Q{x+15} 245 {x+34} 158',stroke='#345d68',sw=3,opacity=.6);s.circle(x,340,7,'#916e43')
s.path('M45 348 L1155 348',stroke='#ab9569',sw=4)
s.text(40,407,'displacement = amplitude × shared_wave(time, position) × height_fraction²',23)
s.text(40,452,'Small neighbour phase offsets; no root translation, chunk rotation or per-plant actors.',21)
s.save('sway-diagram.svg')
# clump composition with irregular upper silhouette
s=SVG(1200,650);s.rect(0,0,1200,650,'#0c2229');s.text(35,40,'Clumped tank — proposed composition, not an engine capture',27,'#dfead6')
s.rect(50,80,1100,480,'#174a4c');s.rect(50,525,1100,35,'#b7a987');rng=random.Random(34)
for cx,r,h in [(135,95,290),(340,120,405),(560,130,325),(820,150,420),(1050,95,310)]:
 for j in range(18):
  x=cx+rng.uniform(-r,r);y=527+rng.uniform(-10,10);stem(s,x,y,h*rng.uniform(.65,1))
 for j in range(9):rosette(s,cx+rng.uniform(-r,r),540,rng.uniform(60,145))
s.path('M50 80 H1150 V560 H50Z',stroke='#8bbfc7',sw=6)
s.text(35,614,'Overlapping colonies • varied height and age • local gaps • winding substrate route',22,'#dfead6')
s.save('tank-clumps-mockup.svg')
# Browser print preserves vector artwork at physical A3 size.
svg=(HERE/'aquatic-plants-a3.svg').read_text()
(HERE/'poster-print.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>Aquatic plants: how patches grow</title><style>@page{size:297mm 420mm;margin:0}html,body{margin:0;width:297mm;height:420mm}svg{display:block;width:297mm;height:420mm}</style></head><body>'+svg+'</body></html>')
print(HERE/'poster-print.html')
