#!/usr/bin/env python3
"""Build the Sea Stars bestiary PDF and HTML from the authored-asset view manifest."""
from html import escape
import json
from pathlib import Path
import sys
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'docs/reference/sea-stars-bestiary'
ART=ROOT/'docs/reference/sea-stars-art'
config=json.loads((DEST/'catalogue.json').read_text())
views=json.loads((DEST/'views/manifest.json').read_text())
images={row['kind']:row['images'] for row in views['species']}
FONT=Path('/usr/share/fonts/truetype/dejavu')
for name,file in [('Sans','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf'),('Serif','DejaVuSerif.ttf'),('SerifBold','DejaVuSerif-Bold.ttf'),('Italic','DejaVuSerif-Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
BG=colors.HexColor('#171b20');CARD=colors.HexColor('#242a30');INK=colors.HexColor('#eeeae1');MUTED=colors.HexColor('#c7c8c5');GOLD=colors.HexColor('#dbbf83');LINE=colors.HexColor('#575849')
W,H=612,792
pdf=DEST/'sea-stars-bestiary.pdf'
c=canvas.Canvas(str(pdf),pagesize=(W,H),pageCompression=1)
c.setTitle(config['title']);c.setAuthor('World Foundry');c.setSubject('Six authored Sea Stars species: dorsal, side and oral views, player poses and asset references')
page=0

def text(x,y,value,size=11,font='Sans',color=INK):
    c.setFillColor(color);c.setFont(font,size);c.drawString(x,y,value)

def paragraph(x,top,value,width,size=10,leading=15,color=MUTED,max_height=None):
    style=ParagraphStyle('body',fontName='Sans',fontSize=size,leading=leading,textColor=color)
    p=Paragraph(value,style);_,height=p.wrap(width,900)
    if max_height is not None:assert height<=max_height,(value,height,max_height)
    p.drawOn(c,x,top-height);return height

def begin(title,bookmark=None):
    global page
    page+=1;c.setFillColor(BG);c.rect(0,0,W,H,fill=1,stroke=0)
    text(36,758,'WORLD FOUNDRY  /  AQUARIUM',8,'Bold',GOLD)
    if bookmark:c.bookmarkPage(bookmark);c.addOutlineEntry(title,bookmark,0,False)
    c.setStrokeColor(LINE);c.line(36,46,576,46)
    text(36,28,'SEA STARS  ·  BESTIARY',8,'Sans',MUTED)
    c.setFillColor(MUTED);c.setFont('Sans',8);c.drawRightString(576,28,f'{page:02d} / 09')

def image(path,x,y,w,h):
    path=Path(path);assert path.is_file(),path
    c.drawImage(str(path),x,y,width=w,height=h,preserveAspectRatio=True,anchor='c',mask='auto')

def panel(x,y,w,h):
    c.setFillColor(CARD);c.setStrokeColor(colors.HexColor('#42484b'));c.roundRect(x,y,w,h,7,fill=1,stroke=1)

begin('Sea Stars bestiary','cover')
text(36,693,'Sea Stars',46,'SerifBold')
text(38,655,'BESTIARY CATALOGUE',14,'Bold',GOLD)
paragraph(38,625,'An Indo-Pacific display of six species, seen through the actual authored meshes, skins and arm poses.',510,12,18,max_height=54)
image(ART/'01-tank-wide.png',36,253,540,337.5)
text(38,231,'6 species',17,'SerifBold');text(221,231,'10 animals',17,'SerifBold');text(418,231,'18 turnarounds',17,'SerifBold')
paragraph(38,207,'One blue Linckia leads the cast. Nine residents bring contrasting shapes, colours and movement to an open sand flat with three bare outcrops and seagrass.',530,10,15,max_height=45)
text(38,140,'IN THIS CATALOGUE',8,'Bold',GOLD)
for i,row in enumerate(config['species']):
    x=38+(i%2)*273;y=118-(i//2)*20
    text(x,y,f'{i+2:02d}  {row["title"]}',10)
    c.linkRect('',row['kind'],(x,y-3,x+260,y+13),relative=0,thickness=0)
c.showPage()
for index,row in enumerate(config['species'],1):
    begin(row['title'],row['kind'])
    text(36,715,row['title'],29,'SerifBold')
    text(38,686,row['scientific'],15,'Italic',GOLD)
    text(38,660,f'ENTRY {index:02d}  ·  {row["role"].upper()}',8,'Bold',MUTED)
    panel(36,354,342,285);image(ART/f'species-{row["kind"]}.png',39,357,336,279)
    text(397,621,'DEFAULT POPULATION',8,'Bold',GOLD)
    text(397,591,str(row['count']),28,'SerifBold')
    text(397,565,'animal' if row['count']==1 else 'animals',10,color=MUTED)
    text(397,531,'DISPLAY SIZE',8,'Bold',GOLD)
    paragraph(397,510,escape(row['diameter']),175,15,20,INK,max_height=42)
    text(397,463,'APPEARANCE',8,'Bold',GOLD)
    paragraph(397,447,escape(row['appearance']),175,9,13,max_height=130)
    text(39,337,'Three-quarter view · authored model and material',8,color=MUTED)
    labels={'dorsal':'Dorsal · upper surface','side':'Side · body profile','oral':'Oral · underside'}
    for i,view in enumerate(('dorsal','side','oral')):
        x=36+i*183
        panel(x,171,174,139);image(DEST/'views'/images[row['kind']][view]['file'],x+2,174,170,133)
        text(x+3,154,labels[view],8,color=MUTED)
    text(38,128,'PLANNED BEHAVIOUR',8,'Bold',GOLD)
    paragraph(38,114,escape(row['behavior']),536,9,13,max_height=52)
    text(38,57,'Poses: '+row['poses'],7.5,color=MUTED)
    c.showPage()
begin('Player poses','poses')
text(36,711,'The player in motion',29,'SerifBold')
paragraph(38,680,'Blue Linckia · source rig poses. The underside is the view presented to the observer when the star climbs the front glass.',530,10,15,max_height=45)
pose_rows=[('player-leading-arm','Lead','The nearest arm leads; its tip lifts.'),('player-underside','Front glass','Five oral grooves converge on the mouth.'),('player-corner','Corner','Distal arm segments curl onto the next plane.'),('player-reach','Reach','Three arms lift while two support the body.')]
for i,(file,label,caption) in enumerate(pose_rows):
    x=36+(i%2)*276;y=374-(i//2)*270
    panel(x,y,264,223);image(ART/(file+'.png'),x+3,y+3,258,217)
    text(x+3,y-19,label,13,'SerifBold');paragraph(x+3,y-28,escape(caption),258,8,12,max_height=28)
c.showPage()
begin('Asset register and sources','sources')
text(36,711,'Asset register',29,'SerifBold')
paragraph(38,681,'This catalogue follows the Finding Your Way bestiary format: authored model views grouped into named entries, with a source register and separate runtime acceptance.',532,10,15,max_height=45)
text(38,621,'SOURCE MASTER',9,'Bold',GOLD)
paragraph(38,602,'sea_stars_assets.blend · all six species, the ten-animal arrangement, scenery and packed 512 × 512 material atlas.',532,10,15,max_height=45)
text(38,551,'ENTRY / BLENDER OBJECTS',9,'Bold',GOLD)
y=531
for row in config['species']:
    text(38,y,row['title'],10);text(260,y,row['object'],8.5,color=MUTED);y-=23
text(38,365,'SCENE AND MOTION',9,'Bold',GOLD)
paragraph(38,347,'The tank uses 3,474 static triangles across four groups. Five species have five independent arm chains; the cushion star uses transforms. The saved actions include glide, lead, corner, reach, row, hide, burial, emergence and cushion puff.',532,10,15,max_height=60)
text(38,262,'RESEARCH AND INTERPRETATION',9,'Bold',GOLD)
paragraph(38,245,'Display sizes describe the chosen models. Speeds, reaction deadlines and the cushion puff are authored game choices. Source meshes and packed textures pass the asset checks; gameplay and Chromecast acceptance remain pending.',532,9,14,max_height=56)
links=[('Locomotion measurements · Mueller et al. (2011)','https://doi.org/10.3354/ab00326'),('Linckia vision · Garm & Nilsson (2014)','https://doi.org/10.1098/rspb.2013.3011'),('Archaster burrowing · Bos et al. (2011)','https://doi.org/10.1007/s00227-010-1588-0'),('Brittle-star arm length and flexion · Matsuzaka et al. (2017)','https://pmc.ncbi.nlm.nih.gov/articles/PMC5399548/'),('Cushion star · Western Australian Museum','https://museum.wa.gov.au/online-collections/names/Culcita-novaeguineae/')]
y=166
for label,url in links:
    text(38,y,label,8.5,color=GOLD);c.linkURL(url,(38,y-2,565,y+11),relative=0,thickness=0);y-=18
text(38,58,'Authored asset edition · '+config['date'],8,color=MUTED)
c.showPage();assert page==9;c.save()
# Companion HTML uses the same entries and view manifest.
cards=[]
for row in config['species']:
    figure=''.join(f'<figure><img src="views/{images[row["kind"]][view]["file"]}" alt="{escape(row["title"])} — {label}"><figcaption>{label}</figcaption></figure>' for view,label in [('dorsal','Dorsal'),('side','Side'),('oral','Oral')])
    cards.append(f'<article id="{row["kind"]}"><h2>{escape(row["title"])}</h2><p class="latin">{escape(row["scientific"])}</p><div class="views">{figure}</div><p><strong>{row["count"]} animal(s) · {escape(row["diameter"])} · {escape(row["role"])}</strong></p><p>{escape(row["appearance"])}</p><p><b>Planned behaviour.</b> {escape(row["behavior"])}</p><p class="model">Blender objects: {escape(row["object"])}</p></article>')
nav=''.join(f'<a href="#{row["kind"]}">{escape(row["title"])}</a>' for row in config['species'])
(DEST/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sea Stars · Bestiary catalogue</title><style>body{margin:0 auto;max-width:1200px;padding:30px;background:#171b20;color:#eeeae1;font:16px/1.5 system-ui}h1,h2{font-family:Georgia,serif}h1{font-size:48px}a,.latin{color:#dbbf83}nav{display:flex;gap:12px;flex-wrap:wrap}nav a{border:1px solid #75684d;border-radius:30px;padding:5px 14px}article{background:#242a30;border:1px solid #42484b;border-radius:12px;padding:24px;margin:26px 0}.views{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}figure{margin:0}img{width:100%;display:block}figcaption{text-align:center;color:#c7c8c5}.model{font:12px monospace;color:#c7c8c5}@media(max-width:650px){.views{grid-template-columns:1fr}}</style><h1>Sea Stars · Bestiary</h1><p>Six species · eighteen model views · authored asset edition</p><p><a href="sea-stars-bestiary.pdf">Open the nine-page PDF</a> · <a href="../sea-stars-art/index.html">Full artwork review and player poses</a></p><p>These views document the current authored Blender meshes and skins. Gameplay and device acceptance remain pending.</p><nav>'''+nav+'</nav>'+''.join(cards)+'</html>')
print(pdf)
