#!/usr/bin/env python3
"""Generate the original, deterministic color atlas for the village assets."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import random

OUT = Path(__file__).resolve().parent / 'village_atlas.tga'
random.seed(48)
tile = 256
colors = [(130,75,44),(220,200,166),(144,66,44),(92,91,82),
          (44,88,49),(105,68,42),(247,193,91),(228,213,178),
          (87,49,35),(111,144,90),(162,134,85),(55,48,39),
          (205,153,77),(131,42,38),(68,98,119),(236,224,190)]
im = Image.new('RGB', (1024,1024))
for n, base in enumerate(colors):
    x,y = n % 4 * tile,n // 4 * tile
    patch=Image.new('RGB',(tile,tile),base); d=ImageDraw.Draw(patch)
    for _ in range(1400):
        px,py=random.randrange(tile),random.randrange(tile); q=random.randrange(-20,21)
        c=tuple(max(0,min(255,v+q)) for v in base)
        d.line((px,py,px+random.randrange(1,8),py),fill=c)
    if n in (0,5,8):
        for j in range(30):
            yy=random.randrange(tile); d.line([(0,yy),(75,yy+random.randrange(-4,5)),(160,yy+random.randrange(-5,6)),(255,yy)],fill=tuple(int(v*.76) for v in base),width=1)
    if n==2:
        for yy in range(0,256,30):
            d.line((0,yy,256,yy),fill=(85,42,34),width=3)
            for xx in range(-30+(yy//30%2)*25,256,50): d.line((xx,yy,xx+4,yy+30),fill=(102,49,37),width=2)
    if n==3:
        for yy in range(0,256,42):
            d.line((0,yy,256,yy),fill=(63,62,59),width=3)
            for xx in range(-30+(yy//42%2)*34,256,68): d.line((xx,yy,xx,yy+42),fill=(68,68,63),width=2)
    if n==4:
        for _ in range(350):
            px,py=random.randrange(256),random.randrange(256);d.line((px,py,px+random.randrange(-8,9),py-12),fill=random.choice([(47,100,53),(77,122,65),(31,72,41)]),width=2)
    im.paste(patch,(x,y))
im.save(OUT)
print(OUT)
