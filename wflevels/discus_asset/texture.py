"""Create discus-inspired palettes and separate photographic pattern families."""
from PIL import Image, ImageOps
from pathlib import Path
import colorsys,json
P=Path(__file__).resolve().parent
# Modest hue shifts retain natural-looking brown, blue and green ranges.
variants={
 'wild-brown':(0,1,1), 'warm-brown':(-.025,1,1), 'copper-brown':(-.045,.88,1),
 'golden-brown':(.012,1.05,1), 'olive-brown':(.035,.85,1), 'pale-brown':(.0,.68,1.08),
 'blue-brown':(.105,.82,1), 'green-brown':(.065,.85,1), 'amber':(-.012,1.12,1),
 'smoky-brown':(.0,.55,.86), 'light-olive':(.045,.60,1.06), 'cool-brown':(.075,.62,.96)}
photo=Image.open(P/'brian-gratwicke-source.jpg').convert('RGB').crop((200,760,1850,2530)).resize((1024,1024),Image.Resampling.LANCZOS)
photo.save(P/'texture-photo-v1.png')
master=photo.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
master.save(P/'master-index.png');base=master.getpalette();manifest={}
for name,(rotation,sat,val) in variants.items():
 pal=[]
 for i in range(0,768,3):
  r,g,b=(v/255 for v in base[i:i+3]);h,s,v=colorsys.rgb_to_hsv(r,g,b)
  rgb=colorsys.hsv_to_rgb((h+rotation)%1,min(1,s*sat),min(1,v*val));pal.extend(round(x*255) for x in rgb)
 out=master.copy();out.putpalette(pal);out.save(P/(name+'.png'));out.convert('RGB').save(P/(name+'.tga'))
 manifest[name]={'pattern':'brown-photograph','hue_rotation':rotation,'saturation_scale':sat,'value_scale':val}
# Different photographs deliberately create different pattern families.
spotted=Image.open(P/'source-spotted-green.jpg').convert('RGB').crop((90,70,745,750)).resize((1024,1024),Image.Resampling.LANCZOS)
turquoise=Image.open(P/'source-spotted.jpg').convert('RGB').crop((1200,200,4050,2950))
turquoise=ImageOps.mirror(turquoise).resize((1024,1024),Image.Resampling.LANCZOS)
for name,image in [('spotted-reference',spotted),('turquoise-pattern',turquoise)]:
 image.save(P/(name+'-source.png'))
 indexed=image.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
 indexed.save(P/(name+'.png'));indexed.convert('RGB').save(P/(name+'.tga'))
 manifest[name]={'pattern':name,'hue_rotation':0,'saturation_scale':1,'value_scale':1}
(P/'palettes.json').write_text(json.dumps(manifest,indent=2)+'\n')
