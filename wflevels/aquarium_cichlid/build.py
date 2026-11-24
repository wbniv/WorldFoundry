#!/usr/bin/env python3
"""Generate cichlid mesh, indexed palette textures, renders and poster."""
import json, math, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
ROOT=Path(__file__).resolve().parent
POSTER=ROOT.parents[1]/'docs/reference/cichlid-poster'
sys.path.insert(0,str(ROOT.parent/'aquarium_tanks'))
from render_goby_asset import raster
from mesh import Mesh

# dark, body, belly, fin, edge, pupil, glint, scale
PALETTES={
'Cobalt':['14264c','3568b4','b9dded','3568a2','a5dfed'],
'Electric blue':['191950','168af0','c1e0ee','319fdf','effaff'],
'Yellow':['514013','eac52d','f9eab4','dcae25','303034'],
'Tangerine':['653519','eb842d','ffd3a7','e97e2b','f7e4bb'],
'Coral':['592431','e75e52','ffd0bd','d74d47','fff0d6'],
'Violet':['382349','8c63bd','ddc5ed','7855a4','e8d8fa'],
'Turquoise':['104b50','20b9b4','b8eee3','209d9d','f1eacb'],
'Emerald':['163f2b','38a56b','c8edce','278b58','f1e6a8'],
'Silver':['333e48','a9b7be','f2f5ee','778993','ffffff'],
'Copper':['4c2c21','b96c3c','ecd0a5','9c5a37','f4e5c7'],
'Rose':['532d42','d989a7','f9dbe2','ad6688','f9e5df'],
'Pearl':['505c66','e2d9c6','fffaf0','d5c8b4','8b9899']}
def rgb(s): return tuple(bytes.fromhex(s))
def slug(s): return s.lower().replace(' ','-')

def make_mesh():
 m=Mesh('cichlid'); sections=[(-.34,.025,.048),(-.28,.045,.070),(-.18,.068,.110),(-.04,.087,.145),(.10,.090,.155),(.22,.076,.143),(.32,.056,.115),(.39,.033,.076),(.43,.018,.035)]
 # Interpolate rings with a smoothstep curve for a rounded, continuous profile.
 refined=[]
 for a,b in zip(sections,sections[1:]):
  for t in (0,.333333,.666667):
   q=t*t*(3-2*t)
   refined.append((a[0]+t*(b[0]-a[0]),a[1]+q*(b[1]-a[1]),a[2]+q*(b[2]-a[2])))
 sections=refined+[sections[-1]]
 n=24
 for x,ry,rz in sections:
  for j in range(n):
   a=math.tau*j/n; m.vertices.append((x,ry*math.sin(a),rz*math.cos(a)))
 for i in range(len(sections)-1):
  for j in range(n): m.faces.append(((i+1)*n+j,(i+1)*n+(j+1)%n,i*n+(j+1)%n,i*n+j))
 for ring,reverse in ((0,False),(len(sections)-1,True)):
  idx=len(m.vertices);m.vertices.append((sections[ring][0],0,0))
  for j in range(n):
   f=(idx,ring*n+j,ring*n+(j+1)%n);m.faces.append(tuple(reversed(f)) if reverse else f)
 def fin(points, faces):
  start=len(m.vertices);m.vertices.extend(points)
  for f in faces:
   f=tuple(start+i for i in f);m.faces.extend((f,tuple(reversed(f))))
 fin([(-.33,0,-.035),(-.33,0,.035),(-.45,0,.16),(-.51,0,.14),(-.53,0,.07),(-.51,0,0),(-.53,0,-.07),(-.51,0,-.14),(-.45,0,-.16)],[(0,1,2),(0,2,3),(0,3,4),(0,4,5),(0,5,6),(0,6,7),(0,7,8)])
 fin([(.31,0,.09),(.25,0,.155),(.16,0,.215),(.04,0,.235),(-.10,0,.25),(-.22,0,.245),(-.32,0,.17),(-.34,0,.045),(-.18,0,.09),(.05,0,.13)],[(0,1,9),(1,2,9),(2,3,9),(3,4,9),(4,5,9),(5,8,9),(5,6,8),(6,7,8)])
 fin([(.05,0,-.14),(-.10,0,-.20),(-.28,0,-.18),(-.33,0,-.05),(-.16,0,-.10)],[(0,1,4),(1,2,4),(2,3,4)])
 for s in [-1,1]:
  fin([(.19,s*.08,-.02),(.07,s*.16,-.07),(-.03,s*.20,-.14),(.12,s*.10,-.10)],[(0,1,3),(1,2,3)])
  fin([(.12,s*.04,-.13),(.03,s*.08,-.22),(-.045,s*.07,-.23),(-.04,s*.04,-.13)],[(0,1,3),(1,2,3)])
 # UV matches the profile atlas; all surfaces use identical indexed image.
 m.uvs=[((x+.54)/.99, (.30-z)/.60) for x,y,z in m.vertices]
 return m

def build():
 ROOT.mkdir(exist_ok=True);POSTER.mkdir(parents=True,exist_ok=True)
 # Every texel is a named palette index. Atlas covers full profile including fins.
 im=Image.new('P',(256,256),1);d=ImageDraw.Draw(im)
 d.rectangle((0,0,255,35),fill=4);d.rectangle((0,36,255,67),fill=3)
 d.rectangle((0,190,255,255),fill=2)
 for x in (67,94,121,148,175):
  d.polygon([(x,75),(x+8,74),(x+11,92),(x+10,157),(x+7,177),(x+3,176),(x,151),(x-2,96)],fill=0)
 # Dorsal fin rays converge on the body, giving the long fin structure.
 for x in range(61,204,10): d.line((x,40,x+11,78),fill=0,width=1)
 # Caudal ray lines are constrained to the tail's atlas region.
 for y in range(62,193,13): d.line((51,128,5,y),fill=7,width=1)
 for y in range(88,185,13):
  for x in range(25+(y//13%2)*7,210,14): d.arc((x,y,x+12,y+9),0,145,fill=7,width=1)
 d.arc((183,94,214,160),280,80,fill=0,width=1);d.line((239,137,250,134),fill=0,width=2)
 d.ellipse((211,103,224,116),fill=4);d.ellipse((214,105,222,113),fill=5);d.ellipse((216,106,219,109),fill=6)
 im.putpalette([i for j in range(256) for i in (j,j,j)]);im.save(ROOT/'master-index.png')
 manifest={}
 for name,colors in PALETTES.items():
  c=[rgb(x) for x in colors]+[(12,17,20),(250,252,242)]
  c.append(tuple(round((c[1][i]*3+c[2][i])/4) for i in range(3)))
  out=im.copy();out.putpalette([v for t in c for v in t]+[0]*(768-len(c)*3));out.save(ROOT/(slug(name)+'.png'))
  manifest[name]=['#%02x%02x%02x'%v for v in c]
 (ROOT/'palettes.json').write_text(json.dumps(manifest,indent=2)+'\n')
 m=make_mesh()
 with (ROOT/'cichlid.obj').open('w') as f:
  f.write('mtllib cichlid.mtl\no cichlid\n')
  for x,y,z in m.vertices:f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
  for u,v in m.uvs:f.write(f'vt {u:.6f} {1-v:.6f}\n')
  f.write('usemtl cichlid\n')
  for face in m.faces:f.write('f '+' '.join(f'{i+1}/{i+1}' for i in face)+'\n')
 (ROOT/'cichlid.mtl').write_text('newmtl cichlid\nKd 1 1 1\nmap_Kd cobalt.png\n')
 # Scale only review geometry to leave margins in the fixed-framing rasterizer.
 m.vertices=[tuple(v*.72 for v in p) for p in m.vertices]
 # Reuse repository's UV rasterizer, with its expected 256x256 atlas.
 previews=[]
 for name in PALETTES:
  tex=Image.open(ROOT/(slug(name)+'.png')).convert('RGB')
  previews.append((name,raster([(m,tex,1)],width=400,height=260,elevation=8,azimuth=0)))
 for label,angle in [('side',0),('oblique',-30),('front',-90)]:
  raster([(m,Image.open(ROOT/'cobalt.png').convert('RGB'),1)],width=720,height=480,elevation=8,azimuth=angle).save(ROOT/(label+'.png'))
 font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
 sheet=Image.new('RGB',(1600,840),'#102833');draw=ImageDraw.Draw(sheet)
 for i,(name,pic) in enumerate(previews):
  x=(i%4)*400;y=(i//4)*280;sheet.paste(pic,(x,y));draw.text((x+16,y+245),name,font=font,fill='white')
 sheet.save(ROOT/'contact-sheet.png')
 poster(sheet)
 print('vertices',len(m.vertices),'triangles',sum(len(f)-2 for f in m.faces))

def poster(sheet):
 # A3 landscape, points. Original renders, no external imagery.
 w,h=1190.551,841.89;c=canvas.Canvas(str(POSTER/'cichlid-a3.pdf'),pagesize=(w,h))
 c.setFillColorRGB(.035,.12,.15);c.rect(0,0,w,h,fill=1,stroke=0)
 c.setFillColorRGB(.91,.96,.94);c.setFont('Helvetica-Bold',37);c.drawString(42,h-60,'CICHLID  /  COLOUR & FORM')
 c.setFont('Helvetica',14);c.drawString(44,h-84,'A stylised Malawi mbuna-inspired aquarium fish • twelve palettes, one pattern')
 c.drawImage(ImageReader(str(ROOT/'side.png')),42,470,width=465,height=310,mask='auto')
 c.setFont('Helvetica-Bold',19);c.drawString(625,720,'ONE MODEL, MANY COLOURS')
 c.setFont('Helvetica',14)
 for i,line in enumerate(['Deep, compressed body and rounded tail', 'Long dorsal fin and paired pectoral fins', 'Five fixed bars and the same scale marks', 'Palette changes leave the UVs and pattern intact', 'Creative colourways, not species identifications']): c.drawString(625,685-i*27,line)
 c.setFont('Helvetica-Bold',19);c.drawString(42,430,'THE PALETTE COLLECTION')
 c.drawImage(ImageReader(sheet),250,95,width=690,height=362.25,mask='auto')
 c.setFont('Helvetica',11);c.drawString(42,55,'Original procedural model and renders • A3 landscape • World Foundry design study')
 c.drawString(42,37,'Cichlid is a diverse fish family; this illustration is a stylised design, not a species guide.')
 c.showPage();c.save()
if __name__=='__main__':build()
