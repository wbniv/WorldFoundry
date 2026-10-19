"""Generate static, editable review mockups; no runtime code is installed."""
from pathlib import Path
import colorsys
import html
import math
import xml.etree.ElementTree as ET
import markdown
HERE = Path(__file__).resolve().parent

def text(x,y,s,size=16):
    return f'<text x="{x}" y="{y}" font-size="{size}">{html.escape(s)}</text>'

def rect(x,y,w,h,fill,stroke='none',rx=6):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'

def swatches(x,y,size=34):
    return ''.join(rect(x+i*(size+9),y,size,size,c,'#58A78C' if i==2 else 'none') for i,c in enumerate(['#e59b51','#486eb1','#58A78C','#916fb3','#ddd8bf','#293c44']))

def graphic(kind,x,y,w):
    s=''
    if kind=='a':
        s+=rect(x,y,w,w,'#00ffad',rx=0)+rect(x,y,w,w,'url(#sat)',rx=0)+rect(x,y,w,w,'url(#val)',rx=0)
        s+=f'<circle cx="{x+w*.473}" cy="{y+w*.345}" r="7" fill="none" stroke="#111" stroke-width="5"/><circle cx="{x+w*.473}" cy="{y+w*.345}" r="7" fill="none" stroke="white" stroke-width="2"/>'
        s+=text(x,y+w+24,'Hue · 159.5°',14)+rect(x,y+w+34,w,19,'url(#hue)',rx=3)
        s+=rect(x+w*159.5/360-3,y+w+31,6,25,'none','white',1)
    elif kind=='b':
        cx,cy=x+w/2,y+w/2
        # HSV disc at V=1: a white centre fades to hue at the rim.
        for i in range(180):
            a,b=2*math.pi*i/180,2*math.pi*(i+1)/180
            c='#'+''.join(f'{round(z*255):02x}' for z in colorsys.hsv_to_rgb(i/180,1,1))
            s+=f'<path d="M{cx},{cy} L{cx+math.cos(a)*w/2},{cy+math.sin(a)*w/2} A{w/2},{w/2} 0 0 1 {cx+math.cos(b)*w/2},{cy+math.sin(b)*w/2} Z" fill="{c}"/>'
        s+=f'<circle cx="{cx}" cy="{cy}" r="{w/2}" fill="url(#radial)"/>'
        angle=159.5/360*math.pi*2
        px,py=cx+math.cos(angle)*w*.473/2,cy+math.sin(angle)*w*.473/2
        s+=f'<circle cx="{px}" cy="{py}" r="7" fill="none" stroke="#111" stroke-width="5"/><circle cx="{px}" cy="{py}" r="7" fill="none" stroke="white" stroke-width="2"/>'
        s+=text(x,y+w+24,'Value · 65.5%',14)+rect(x,y+w+34,w,19,'url(#brightness)',rx=3)
        s+=rect(x+w*.655-3,y+w+31,6,25,'none','white',1)
    else:
        palette=['#ea6f69','#e59b51','#ded16c','#87b46c','#58a78c','#6eb6c6','#658cd1','#8c7dce','#be81b7','#d4a6a1','#dedad0','#8f989c','#9d6555','#556d3b','#466d72','#2d414b']
        gap=9; cell=(w-gap*3)/4
        for i,c in enumerate(palette):
            xx,yy=x+(i%4)*(cell+gap),y+(i//4)*(cell+gap)
            s+=rect(xx,yy,cell,cell,c,'white' if i==4 else 'none')
            if i==4:s+=text(xx+cell/2-8,yy+cell/2+6,'✓',23)
        s+=rect(x,y+w+18,w,38,'#264750','#a0c5c3')+text(x+16,y+w+44,'Custom colour…',16)
    return s

DEFS='''<defs><linearGradient id="sat"><stop stop-color="white"/><stop offset="1" stop-color="white" stop-opacity="0"/></linearGradient><linearGradient id="val" x2="0" y2="1"><stop stop-opacity="0"/><stop offset="1"/></linearGradient><linearGradient id="hue"><stop stop-color="red"/><stop offset=".167" stop-color="#ff0"/><stop offset=".333" stop-color="#0f0"/><stop offset=".5" stop-color="#0ff"/><stop offset=".667" stop-color="#00f"/><stop offset=".833" stop-color="#f0f"/><stop offset="1" stop-color="red"/></linearGradient><radialGradient id="radial"><stop stop-color="white"/><stop offset="1" stop-color="white" stop-opacity="0"/></radialGradient><linearGradient id="brightness"><stop/><stop offset="1" stop-color="#86ffd6"/></linearGradient></defs>'''

def wrap(w,h,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img">{DEFS}<rect width="{w}" height="{h}" rx="12" fill="#10222c"/><g fill="#edf4f4" font-family="sans-serif">{body}</g></svg>'

for kind,title in [('a','A · Colour square + hue'),('b','B · Wheel + value'),('c','C · Palette first')]:
    body=text(24,36,title,24)+text(24,65,'TV remote · static proposal',15)
    body+=rect(24,86,740,480,'#182f3b','#3f6675')+text(46,119,'Object tint',22)
    body+=graphic(kind,46,139,250)
    body+=text(330,163,'Original',14)+rect(330,178,140,62,'#486eb1')+text(490,163,'Preview',14)+rect(490,178,140,62,'#58a78c')
    body+=text(330,281,'#58A78C',25)+text(330,313,'RGB   88 / 167 / 140',17)
    if kind=='b':
        for i,(label,frac) in enumerate([('Hue',.443),('Saturation',.473)]):
            body+=text(330,354+i*48,label,14)+rect(425,339+i*48,250,15,'#416777')+rect(425+250*frac,335+i*48,5,23,'white')
    else:
        body+=text(330,352,'Recent colours',15)+swatches(330,369)
    body+=rect(330,440,162,40,'#264750','#a0c5c3')+text(344,466,'RGB / Hex details',15)
    body+=rect(509,440,162,40,'#376c5c')+text(529,466,'Use colour',16)
    body+=text(330,514,'↶  Cancel picker',16)
    hints={'a':'A: adjust square   Arrows: saturation / value','b':'↑ ↓ select bars   ← → adjust   A: confirm','c':'Arrows: select swatch   A: preview / choose'}
    body+=text(46,548,hints[kind],14)
    body+=text(803,65,'Phone / tablet',16)+rect(802,86,324,625,'#182f3b','#3f6675',22)+text(825,123,'↶   Object tint',21)
    body+=graphic(kind,830,147,268)
    body+=text(830,498,'#58A78C',23)+rect(1009,473,86,35,'#58a78c')
    body+=text(830,529,'RGB   88 / 167 / 140',15)+swatches(830,546,36)
    body+=rect(830,607,268,38,'#264750','#a0c5c3')+text(852,631,'RGB / Hex details',16)
    body+=rect(830,657,268,36,'#376c5c')+text(917,681,'Use colour',16)
    body+=text(24,612,'Shared RGB result · Original/preview · Exact values · Cancel/confirm',17)
    body+=text(24,646,'TV: navigate controls first; no keyboard opens automatically.',15)
    body+=text(24,678,'Illustrative palette; no alpha channel or gameplay preview implied.',15)
    path=HERE/f'option-{kind}.svg';path.write_text(wrap(1150,735,body));ET.parse(path)

body=text(24,35,'Picker draft → form draft → applied object',23)
for x,title,desc in [(24,'Open picker','Copy existing form draft'),(324,'Adjust colour','Temporary picker preview'),(624,'Use colour','Update form draft')]:
    body+=rect(x,65,260,100,'#24424e','#729999')+text(x+16,96,title,19)+text(x+16,132,desc,15)
body+=text(289,124,'→',26)+text(589,124,'→',26)+text(40,208,'Cancel / ↶: discard picker preview; retain pre-picker form draft.',17)+text(40,247,'Outer form apply-and-close: validated settings reach the runtime object.',17)
(HERE/'draft-flow.svg').write_text(wrap(920,280,body));ET.parse(HERE/'draft-flow.svg')
# Current Custom control; retain the original A/B/C proposals above for comparison.
body=text(24,36,'Custom · Hue/saturation square + Value',24)
body+=rect(40,75,310,310,'url(#hue)',rx=0)
body+='<rect x="40" y="75" width="310" height="310" fill="url(#neutral)"/>'
body+='<rect x="40" y="75" width="310" height="310" fill="black" opacity=".345"/>'
body+=rect(40,425,310,20,'url(#brightness)',rx=3)+text(40,414,'Value (brightness) · 65.5%',16)
body+=text(390,110,'← / →  Hue',18)+text(390,150,'↑ / ↓  Saturation',18)
body+=text(390,210,'Value slider: ← / → brightness',17)
body+=text(390,260,'Original / Preview · RGB / Hex',17)+text(390,300,'Use colour / Cancel',17)
svg=wrap(800,490,body).replace('</defs>','<linearGradient id="neutral" x2="0" y2="1"><stop stop-color="white" stop-opacity="0"/><stop offset="1" stop-color="white"/></linearGradient></defs>')
(HERE/'custom-value.svg').write_text(svg);ET.parse(HERE/'custom-value.svg')
plan=HERE.parent/(HERE.name+'.md')
page=markdown.markdown(plan.read_text(),extensions=['tables','fenced_code'])
css='body{font:17px/1.65 system-ui,sans-serif;color:#dce8ed;background:#10222c;max-width:1120px;margin:32px auto;padding:0 24px}a{color:#88d9c5}h1,h2,h3{line-height:1.25}h2{margin-top:2em}img{display:block;max-width:100%;height:auto;margin:24px 0;border-radius:12px}table{border-collapse:collapse;width:100%;font-size:15px}td,th{border:1px solid #46606c;padding:10px;text-align:left;vertical-align:top}th{background:#203b48}code{color:#c5dfac}@media print{body{background:white;color:black;font-size:11pt}a{color:#234}h2,h3{break-after:avoid}img,table{break-inside:avoid}}'
plan.with_suffix('.html').write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Runtime colour picker — review choices</title><style>{css}</style><body>{page}</body></html>')
print(f'Built {plan.with_suffix(".html")} and four validated SVGs')
