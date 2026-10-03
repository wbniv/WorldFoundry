"""Build a self-contained A3 poster from original diagrams and real captures."""
from pathlib import Path
import base64
import json
import re
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=ROOT/'docs/plans/2026-10-02-jellyfish-biomechanics-poster'
sys.path.insert(0,str(ROOT/'wflevels/aquarium_tanks'))
from models import JELLY_OPACITY
motion=(ROOT/'wflevels/aquarium_tanks/jelly_motion.fth').read_text()
deform=(ROOT/'wfsource/source/renderassets/jelly_deform.h').read_text()
assert 'dup .20 <' in motion and 'dup .50 <' in motion
assert 'if 3.2 else 4 then j-period' in motion
assert '1.f-.18f*contraction*margin' in deform
assert '.28f*contraction*z*margin' in deform
settings={'opacity':JELLY_OPACITY,'cycle_fractions':[.2,.3,.5],
          'player_period_s':4,'up_period_s':3.2,'resident_period_s':[4,5.4],
          'margin_radial_coefficient':.18,'weighted_height_coefficient':.28,
          'evidence':'GAME: adopted art/animation settings, not biological measurements',
          'blender':'Blender 5.0.1; Cycles 48 samples; exported bell.iff and arms.iff',
          'game':'Desktop OpenGL engine, aquarium_jellyfish-standalone.iff; six jellies'}
(HERE/'data.json').write_text(json.dumps(settings,indent=2)+'\n')
html=(SOURCE/'layout.html').read_text()
html=html.replace('A3 Moon-jelly poster · review mockup','A3 Moon-jelly biomechanics and translucent model')
html=re.sub(r'<div class="review">.*?</div>','',html,flags=re.S)
html=html.replace('MOON JELLY<br>THE ART OF THE PULSE','MOON JELLY · THE ART OF THE PULSE')
html=html.replace('Phase widths here are an animation proposal.','Phase widths are adopted game choices.')
html=html.replace('GAME proposal:','GAME animation:')
html=html.replace('proposed radial contraction 18%, height change 28%.','margin-weighted radial contraction ≤18%; weighted height coefficient 28%, with a pinned apex.')
html=html.replace('COMPOSITION MOCKUP · 2026-10-02 · explanatory geometry and proposed game curve; no fitted experimental trace.',
                  '2026-10-03 · Original schematic diagrams; illustrative game curve. Renderings use the same exported model and opacity values. No refraction or fluid simulation.')
css='''
.page{padding:38px;display:flex;flex-direction:column;gap:12px}
header{margin:0;padding-top:12px;flex:0 0 139px}h1{font-size:36px;margin:8px 0}.subtitle{font-size:17px}.legend{margin-top:10px}
.renderings{display:grid;grid-template-columns:1fr 1fr;gap:16px;flex:0 0 272px}
figure{margin:0;background:#eaf0ef;border-radius:6px;padding:10px}figure img{width:100%;height:212px;object-fit:contain}figcaption{font-size:13px;line-height:1.4;margin-top:5px}
.grid{gap:12px;flex:0 0 735px;grid-template-rows:repeat(3,1fr)}section{height:auto;padding:12px}section img,section img.plot{height:123px;margin-top:5px}h2{font-size:18px}.panelhead span{width:25px;height:25px;padding-top:1px}p{font-size:13.5px;line-height:1.38}.badge{bottom:9px;left:12px;font-size:9px}
.study{margin:0;padding:10px 14px;gap:20px;flex:0 0 110px}.study h3{font-size:15px}.study p{font-size:13px}footer{margin:0;padding-top:10px;font-size:11.5px;line-height:1.36}.draft{margin-top:8px;font-size:11.5px}
'''
html=html.replace('</style>',css+'</style>')
op=JELLY_OPACITY
band=f'''<div class="renderings"><figure><img src="jellyfish-blender.png" alt="Blender render: checkerboard visible through bell"><figcaption><b>BLENDER · exported model</b><br>Bell {op['jelly']:.0%} opacity · margin/arms {op['edge']:.0%} · fringe {op['trail']:.0%} · internal motifs {op['motif']:.0%}.</figcaption></figure><figure><img src="engine/close-up.png" alt="Actual desktop game capture: six translucent jellies"><figcaption><b>IN GAME · actual OpenGL capture</b><br>Six translucent jellies, native bell deformation and trailing appendages. Alpha compositing; no refraction.</figcaption></figure></div>'''
html=html.replace('</header><div class="grid">','</header>'+band+'<div class="grid">')
# Keep editable source artwork, while embedding all images in the print source.
for path in SOURCE.glob('*.svg'):
    (HERE/path.name).write_bytes(path.read_bytes())
def embed(match):
    path=HERE/match.group(1)
    mime='image/svg+xml' if path.suffix=='.svg' else 'image/png'
    return 'src="data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()+'"'
html=re.sub(r'src="([^"]+)"',embed,html)
(HERE/'poster.html').write_text(html)
