from PIL import Image, ImageDraw, ImageFont
import glob, os

T = 1.5
# ---- layout data (from wflevels/smb_w1_3/blender_create_smb_w1_3.py) ----
START = (-2, 8); END = (135, 164); FLAG = 155
# treetops: (col, width_tiles, top_tiles)
TREES = [("a",14,5,2),("b1",22,4,4),("b2",29,4,4),("c1",37,4,3),("c2",45,5,5),
         ("c3",53,4,3),("d",60,4,2),("e",75,5,6),("f1",94,4,3),("f2",102,6,4),
         ("g",110,4,3),("h",118,4,3),("i1",125,4,3),("i2",131,4,3)]
# static stand-in movers/lift: (col, halfwidth_tiles, top_tiles)
HARD = [("lift",66,1,3),("lift",70,1,5),("mover",82,1.5,4),("mover",87,1.5,4),("stone",138,2,1)]
QBLOCK = (60, 4)                     # col, z_tiles
KOOPAS = [(22,4),(102,4),(125,3)]   # col, canopy_top
GOOMBAS=[(44,5),(47,5),(110,3)]
PARAS  = [107,121]                   # cols (hover over gaps)
COINS  = [(13,3),(16,3),(28,5),(29,5),(30,5),(55,4),(57,4.7),(59,4),
          (73,7),(74.5,7),(76,7),(77.5,7),(81,5.5),(83,5.5),(85,5.5),(87,5.5),
          (82,7),(84,7),(86,7),(88,7),(117,4),(118,4),(119,4)]

# ---- canvas (to scale) ----
COLS=166; ROWS=11           # world cols x tile-rows shown
PX=7                        # px per tile
MX, MGT, MGB = 30, 30, 24   # margins (left, top, bottom)
W = MX*2 + COLS*PX
H = MGT + MGB + ROWS*PX
img = Image.new("RGB",(W,H),(92,148,252))     # SMB sky blue
d = ImageDraw.Draw(img)
def X(col): return MX + (col+2)*PX
def Y(tile): return MGT + (ROWS-tile)*PX       # tile 0 = ground line
GROUND_Y = Y(0)
# death pit band
d.rectangle([X(START[1]),GROUND_Y, X(END[0]),H-2],fill=(20,20,28))
# ground strips
for (a,b) in (START,END):
    d.rectangle([X(a),GROUND_Y, X(b),GROUND_Y+1.5*PX],fill=(150,90,40),outline=(90,55,25))
# tree-tops: stem then canopy
for name,col,wt,top in TREES:
    hw=wt*T/2/T  # halfwidth in tiles
    d.rectangle([X(col-0.4),Y(top-0.5),X(col+0.4),Y(top-0.5-2)],fill=(140,82,26))            # stem
    d.rectangle([X(col-wt/2),Y(top),X(col+wt/2),Y(top-0.5)],fill=(40,158,46),outline=(20,110,28))  # canopy
# hard stand-ins
for kind,col,hw,top in HARD:
    c=(120,72,30) if kind!="stone" else (110,70,35)
    d.rectangle([X(col-hw),Y(top),X(col+hw),Y(0)],fill=c,outline=(70,45,20))
    if kind in("lift","mover"):
        d.text((X(col)-3,Y(top)-9),"⇅" if kind=="lift" else "↔",fill=(255,255,255))
# staircase (8 steps from base 146)
for s in range(8):
    d.rectangle([X(146+s-0.5),Y(s+1),X(146+s+0.5),Y(0)],fill=(120,72,30),outline=(70,45,20))
# flagpole
d.line([X(FLAG),Y(0),X(FLAG),Y(9)],fill=(180,180,180),width=2)
d.polygon([(X(FLAG),Y(8.5)),(X(FLAG)+10,Y(8.2)),(X(FLAG),Y(7.9))],fill=(40,158,46))
d.rectangle([X(159),Y(3),X(163),Y(0)],fill=(150,90,40),outline=(90,55,25))  # castle
# ? block
d.rectangle([X(QBLOCK[0]-0.5),Y(QBLOCK[1]+0.5),X(QBLOCK[0]+0.5),Y(QBLOCK[1]-0.5)],fill=(230,160,30),outline=(120,70,0))
d.text((X(QBLOCK[0])-3,Y(QBLOCK[1])-5),"?",fill=(80,40,0))
# coins
for cx,cz in COINS:
    d.ellipse([X(cx)-2,Y(cz)-3,X(cx)+2,Y(cz)+3],fill=(255,216,0),outline=(180,140,0))
# enemies
for col,top in KOOPAS:
    d.ellipse([X(col)-3,Y(top+0.7)-3,X(col)+3,Y(top+0.7)+3],fill=(24,150,40),outline=(0,0,0)); d.text((X(col)-3,Y(top+0.7)-12),"K",fill=(0,90,0))
for col,top in GOOMBAS:
    d.ellipse([X(col)-3,Y(top+0.7)-3,X(col)+3,Y(top+0.7)+3],fill=(150,80,20),outline=(0,0,0)); d.text((X(col)-3,Y(top+0.7)-12),"G",fill=(90,45,0))
for col in PARAS:
    yy=6
    d.ellipse([X(col)-3,Y(yy)-3,X(col)+3,Y(yy)+3],fill=(24,150,40),outline=(0,0,0))
    d.line([X(col)-5,Y(yy)-1,X(col)-2,Y(yy)],fill=(255,255,255),width=2); d.line([X(col)+2,Y(yy),X(col)+5,Y(yy)-1],fill=(255,255,255),width=2)
    d.text((X(col)-4,Y(yy)-12),"P",fill=(0,90,0))
# Mario spawn
d.rectangle([X(3)-2,Y(1.3)-5,X(3)+2,Y(1.3)+3],fill=(220,40,40))
d.text((X(3)-8,Y(1.3)-15),"Mario",fill=(0,0,0))
# axis ticks every 20 cols
for col in range(0,165,20):
    d.line([X(col),GROUND_Y,X(col),GROUND_Y+4],fill=(0,0,0)); d.text((X(col)-6,H-14),f"col {col}",fill=(0,0,0))
d.text((MX,6),"SMB World 1-3 — side elevation (to scale, 1 tile = 1.5 m).  K=Koopa  G=Goomba  P=Paratroopa  ?=power-up  ⇅/↔=static mover stand-in",fill=(0,0,0))
img.save("/home/will/tmp/smb_w13/LAYOUT_diagram.png")
print("diagram:", img.size)

# ---- contact sheet of the 9 in-game stills ----
shots=sorted(glob.glob("/home/will/tmp/smb_w13/0*.png"))
if shots:
    thumbs=[Image.open(s).resize((320,240)) for s in shots]
    cols=3; rows=(len(thumbs)+2)//3
    sheet=Image.new("RGB",(cols*320, rows*240),(0,0,0))
    for i,t in enumerate(thumbs):
        sheet.paste(t,((i%3)*320,(i//3)*240))
    sheet.save("/home/will/tmp/smb_w13/CONTACT_sheet.png")
    print("contact sheet:", sheet.size, "from", len(shots), "stills")
