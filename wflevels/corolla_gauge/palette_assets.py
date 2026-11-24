"""Cook tulip index images and shared lookup tables; never bake color variants."""
import colorsys,json,struct
from pathlib import Path
from PIL import Image
HERE=Path(__file__).resolve().parent
NAMES=('Scarlet','Rose','Apricot','Golden','Violet','Ivory')
# Relative hue rotations and saturation multipliers of the generated source.
TRANSFORMS=((0,1),(-.075,.8),(.075,.8),(.14,.85),(-.18,.75),(0,.12))

def encode(i):
    return ((i>>3)<<3,(i&7)<<3,8)

def build():
    image=Image.open(HERE/'petal-basal-v2-source.png').convert('RGB').resize((512,512),Image.Resampling.LANCZOS)
    indexed=image.quantize(colors=128,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    source=indexed.getpalette()[:384]; assert len(source)==384
    indices=indexed.tobytes()
    for offset,name in ((0,'petal-rose-index.png'),(128,'petal-ivory-index.png')):
        data=bytes(c for index in indices for c in encode(index+offset))
        Image.frombytes('RGB',(512,512),data).save(HERE/name)
    colors=[tuple(source[i:i+3]) for i in range(0,384,3)]
    shade=[]
    for r,g,b in colors:
        shade.append(min(range(128),key=lambda k:sum((colors[k][j]-(r,g,b)[j]*.7)**2 for j in range(3))))
    small=indexed.resize((128,128),Image.Resampling.NEAREST).tobytes()
    for offset,name in ((0,'petal-rose-fold-index.png'),(128,'petal-ivory-fold-index.png')):
        data=bytes(c for index in small for c in encode(shade[index]+offset))
        Image.frombytes('RGB',(128,128),data).save(HERE/name)
    result={};binary=bytearray(b'DPLT'+struct.pack('<HH',1,len(NAMES)))
    for name,(shift,sat) in zip(NAMES,TRANSFORMS):
        red=[];pale=[]
        for i in range(0,384,3):
            r,g,b=(v/255 for v in source[i:i+3]);h,s,v=colorsys.rgb_to_hsv(r,g,b)
            rgb=colorsys.hsv_to_rgb((h+shift)%1,min(1,s*sat),v)
            red.extend(round(c*255) for c in rgb)
            # The measuring petal stays visibly pale against every flower.
            luminance=.2126*r+.7152*g+.0722*b
            blend=max(0,min(1,(luminance-.10)/.16))
            value=(.04+luminance*.7)*(1-blend)+(.52+.48*luminance)*blend
            pale.extend(round(c*255) for c in (value,min(1,value*.94),min(1,value*.82)))
        table=red+pale;assert len(table)==768
        result[name]=table;binary.extend(table)
    (HERE/'tulip-palettes.bin').write_bytes(binary)
    (HERE/'tulip-palettes.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':build()
