#!/usr/bin/env python3
"""Build a finished A3 betta poster with original Blender renders and SVG diagrams."""
from pathlib import Path
import base64
import html
import json

HERE=Path(__file__).resolve().parent
AROWANA=HERE.parent/'asian-arowana-poster'
INK='#153938'

def t(x,y,s,size=16,anchor='start',color=INK,weight=400):
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{color}" font-weight="{weight}">{html.escape(s)}</text>'
def svg(w,h,content,label):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{label}"><title>{label}</title><g font-family="DejaVu Sans,sans-serif">{content}</g></svg>'

def map_svg():
    x=lambda lon: 18+(lon-96)*18
    y=lambda lat: 24+(22-lat)*18
    out=['<rect width="510" height="370" rx="12" fill="#e9f2ed"/><defs><clipPath id="map"><rect x="12" y="20" width="245" height="323"/></clipPath></defs><g clip-path="url(#map)">']
    for f in json.loads((AROWANA/'assets/countries.geojson').read_text())['features']:
        geom=f['geometry'];polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
        for poly in polys:
            d=' '.join('M '+' L '.join(f'{x(lon):.2f},{y(lat):.2f}' for lon,lat,*_ in ring)+' Z' for ring in poly)
            out.append(f'<path d="{d}" fill="#cad8c9" stroke="#6b8a80" stroke-width=".9" fill-rule="evenodd"/>')
    for lat in (20,15,10):
        out.append(f'<path d="M 12,{y(lat)} H 255" stroke="#9fbdb1" stroke-dasharray="3 4"/>')
        out.append(t(16,y(lat)-3,f'{lat}°N',11))
    out.append(t(105,165,'THAILAND',12,weight=600)+t(153,102,'LAO PDR',11)+t(72,98,'MYANMAR',11)+t(193,202,'CAMBODIA',11))
    places=[('Chiang Mai',99.0,18.8),('Kanchanaburi',99.5,14.0),('Bang Phlat',100.5,13.8),('Phetchaburi',99.9,13.1)]
    for n,(name,lon,lat) in enumerate(places,1):
        out.append(f'<circle cx="{x(lon)}" cy="{y(lat)}" r="7" fill="#9b3d67" stroke="#fff" stroke-width="1.5"/>')
        dx=-12 if n in (1,2,4) else 11
        out.append(t(x(lon)+dx,y(lat)+5,str(n),14,'middle',weight=700))
    out.append('</g>')
    out.append(t(279,36,'Wild-population labels',17,weight=700))
    for n,(name,lon,lat) in enumerate(places,1):
        out.append(t(279,76+(n-1)*44,f'{n}. {name}',17,weight=600))
    for yy,s in [(262,'Kwon et al., 2022, Fig. 1.'),(289,'Dots: approximate regional'),(311,'centres, not sampling GPS.'),(340,'Not a complete range map.')]:out.append(t(279,yy,s,14))
    out.append(t(24,360,'N ↑  •  Natural Earth geographic basemap',12))
    (HERE/'map-localities.json').write_text(json.dumps(dict(species='Betta splendens',evidence='Kwon et al. 2022 Figure 1A/B',projection='equirectangular',basemap='Natural Earth 1:110m, public domain',coordinates='Manually placed approximate municipality/district centres, rounded to 0.1 degree, checked against regional positions in Figure 1; NOT sample coordinates',precision='Regional representative only',status='Published wild-population labels, not a claim of extant populations in 2026',localities=[dict(number=n,name=name,longitude=lon,latitude=lat) for n,(name,lon,lat) in enumerate(places,1)]),indent=2)+'\n')
    return svg(510,370,''.join(out),'Thailand context and four published wild Betta splendens population labels')

def silhouette(x,y,s=1,long=True,color='#9b3d67',pose=0):
    out=f'<g transform="translate({x} {y}) scale({s})">'
    if long:
        edge,top,bottom=[(-20,-20,140),(-34,10,114),(-5,-8,150),(-24,-14,130)][pose]
        out+=f'<path d="M 78,57 C 10,{top} {edge},20 {edge},57 C {edge},100 10,{bottom} 78,72 Z M 80,48 Q 85,{top+13} 158,27 L 183,53 Z M 81,74 Q 119,{bottom+2} 182,88 L 201,72 Z" fill="#bb5a81"/>'
    else:out+='<path d="M 77,54 L 31,35 Q 20,57 30,85 L 80,73 Z M 92,49 Q 130,25 170,47 Z M 98,75 L 153,100 L 181,78 Z" fill="#9d705a"/>'
    out+=f'<path d="M 75,50 Q 136,25 196,48 L 225,62 Q 204,87 158,85 Q 101,87 74,72 Z" fill="{color}"/><circle cx="204" cy="57" r="4" fill="#122f35"/><path d="M 170,75 L 143,{124 if long else 96}" stroke="{color}" stroke-width="4"/></g>'
    if pose==2:
        out+=f'<path d="M {x+175*s},{y+63*s} q {-24*s},{-22*s} {-40*s},{9*s} q {24*s},{12*s} {40*s},{-9*s}" fill="#bb5a81"/>'
    return out

def forms():
    out=silhouette(35,38,.9,False,'#54785c')+silhouette(327,38,.9,True)
    out+=t(38,169,'Wild-type form',17,weight=600)+t(330,169,'Ornamental long-fin form',17,weight=600)
    out+=t(38,191,'Compact fins • schematic comparison; not to scale',14)
    return svg(640,202,out,'Wild-type compact fins versus ornamental long-fin betta, schematic')

def motion():
    out=t(10,22,'GAME STUDY • flexible surfaces, anchored roots',16,weight=700)
    for i,label in enumerate(['HOVER','SWIM','TURN','SETTLE']):
        out+=silhouette(18+i*163,53,.51,True,pose=i)
        out+=t(12+i*163,46,label,14,color='#9b3d67',weight=700)
        out+=t(12+i*163,132,['Pectoral scull','Tips trail drive','Asymmetric fins','Damped recovery'][i],12)
    return svg(660,148,out,'Proposed hover, swim, turn and settle fin states, not measured kinematics')

def image(name):
    return 'data:image/png;base64,'+base64.b64encode((HERE/'assets'/name).read_bytes()).decode()

def main():
    diagrams={'location-map.svg':map_svg(),'wild-and-ornamental.svg':forms(),'motion.svg':motion()}
    for name,content in diagrams.items():(HERE/name).write_text(content)
    css='''@page{size:A3 portrait;margin:0}*{box-sizing:border-box}body{margin:0;background:#c9d6d2;color:#153938;font-family:"DejaVu Sans",sans-serif}.sheet{margin:20px auto;background:#faf8f0;width:297mm;height:420mm;padding:12mm;display:grid;grid-template-rows:23mm 130mm 18mm 100mm 47mm 40mm 20mm;gap:3mm}h1,h2,p,figure{margin:0}h1{font-size:31pt;line-height:1}.kicker{color:#9b3d67;font-size:9pt;font-weight:700;letter-spacing:2px;margin-bottom:2mm}.sub{font-size:11pt;margin-top:2mm}h2{font-size:14pt;line-height:1.2;margin-bottom:2mm}p{font-size:10pt;line-height:1.38;margin-bottom:2.5mm}.hero{position:relative;display:grid;grid-template-rows:122mm 8mm}.hero img{width:100%;height:122mm;object-fit:contain}.hero figcaption{font-size:8.5pt;line-height:1.3;text-align:center}.label{position:absolute;font-size:10pt;color:#843959;border-left:2px solid #b86a86;padding-left:2mm}.history{display:grid;grid-template-columns:1fr 1fr 1fr;background:#e9eee1;padding:2.5mm 3mm;gap:5mm;border-radius:2mm}.history b{font-size:10pt}.history p{font-size:9pt;line-height:1.25;margin:1mm 0 0}.range{display:grid;grid-template-columns:133mm 1fr;gap:6mm}.range svg{width:130mm;height:90mm}.tag{font-size:8.5pt;color:#8a3c63;font-weight:700;letter-spacing:1px;margin:0 0 2mm}.compare{display:grid;grid-template-columns:171mm 1fr;gap:5mm;border-top:1px solid #bfcbbf;padding-top:2mm}.compare svg{width:171mm;height:36mm}.detail img{width:100%;height:36mm;object-fit:contain}.detail figcaption{font-size:8.5pt;line-height:1.2}.motion{display:grid;grid-template-columns:171mm 1fr;gap:5mm}.motion svg{width:171mm;height:31mm}.motion p{font-size:9pt;line-height:1.3}.footer{border-top:1px solid #bfcbbf;padding-top:2mm}.footer p{font-size:8.5pt;line-height:1.25;margin:0 0 1mm}a{color:inherit;text-decoration:none}.n{color:#9b3d67;font-weight:700}@media print{body{background:white}.sheet{margin:0}}'''
    poster=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Betta — the art of flowing fins · A3</title><style>{css}</style><main class="sheet">
    <header><div class="kicker">SIAMESE FIGHTING FISH • THAILAND</div><h1>Betta — the art of flowing fins</h1><div class="sub"><i>Betta splendens</i> · Ornamental long-fin form · Family Osphronemidae</div></header>
    <figure class="hero"><img src="{image('runtime-betta-side.png')}" alt="Original opaque 3D betta model, teal body and broad red-violet caudal, dorsal and anal fins"><span class="label" style="left:2mm;top:39mm">Caudal fan</span><span class="label" style="right:3mm;top:17mm">Dorsal sail</span><span class="label" style="right:1mm;top:57mm">Pectoral pair</span><span class="label" style="left:3mm;top:95mm">Anal skirt</span><span class="label" style="right:0;top:104mm">Pelvic ribbons</span><figcaption>Runtime fish • 4,076 triangles • eight mesh groups • opaque membranes.<br>Same geometry and fin deformation as the app; smooth studio lighting.</figcaption></figure>
    <section class="history"><div><b>Centuries of breeding <span class="n">[1]</span></b><p>Historical reports reach the 14th century; an exact domestication date is uncertain.</p></div><div><b>Early 20th century <span class="n">[1]</span></b><p>Ornamental breeding expands the range of colours and fin shapes.</p></div><div><b>5 February 2019 <span class="n">[2]</span></b><p>Declared Thailand’s National Aquatic Animal.</p></div></section>
    <section class="range"><div><h2>Wild betta locations <span class="n">[1]</span></h2>{diagrams['location-map.svg']}</div><div><div class="tag">SHALLOW FRESHWATER</div><h2>Vegetation and calm water</h2><p>Floodplain pools, canals, rice paddies, swamps and slow streams are among its recorded habitats. Wild fish have compact fins; the large fins above belong to an ornamental form. <span class="n">[1, 2]</span></p><h2>Air at the surface</h2><p>A labyrinth organ allows air breathing alongside the gills, helping in low-oxygen water. Surface access matters. <span class="n">[2]</span></p><h2>A bubble-nest father</h2><p>Male <i>B. splendens</i> build bubble nests and care for eggs and newly hatched fry. Other <i>Betta</i> species may mouthbrood instead. <span class="n">[3]</span></p></div></section>
    <section class="compare"><div><h2>Wild and ornamental</h2>{diagrams['wild-and-ornamental.svg']}</div><figure class="detail"><img src="{image('runtime-betta-oblique.png')}" alt="Oblique rendering of the same opaque 3D betta model showing fin depth"><figcaption>Same mesh, oblique view.<br>Seven fins, including both paired sets.</figcaption></figure></section>
    <section class="motion"><div><h2>How the fins flow</h2>{diagrams['motion.svg']}</div><div><p>Keep fin roots attached; allow curved rays, trailing edges and delayed tips.</p><p>Ray flexibility is supported by general fish research in <b>bluegill</b>. The sequence illustrates game motion, not measured betta kinematics. <span class="n">[4]</span></p></div></section>
    <footer class="footer"><p><b>Sources:</b> <a href="https://doi.org/10.1126/sciadv.abm4950">[1] Kwon et al., Science Advances 8:eabm4950 (2022), Fig. 1</a> · <a href="https://repository.seafdec.org/bitstream/handle/20.500.12066/5516/Siamese-fighting-fish.pdf">[2] Sermwatanakul, SEAFDEC (2019)</a> · <a href="https://journal.nsm.or.th/sites/default/files/2023-10/THNHMJ01-2017.compressed.pdf">[3] Panijpan et al., Thai Natural History Museum Journal 11(1) (2017)</a> · <a href="https://pubmed.ncbi.nlm.nih.gov/23720195/">[4] Flammang et al., J. Morphology (2013)</a>.</p><p>Original fish geometry, renders and diagrams. Natural Earth basemap: public domain. Regional dots are not collecting coordinates or a complete/current range. The ornamental model does not represent the wild phenotype at those sites.</p><p>A3 portrait · 297 × 420 mm · Research checked 2 October 2026 · Editable model and source notes accompany this poster.</p></footer>
    </main></html>'''
    (HERE/'poster.html').write_text(poster)
    print(HERE/'poster.html')

if __name__=='__main__':main()
