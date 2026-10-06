"""Render the moved baseline plan and settings-gallery review schematic."""
from pathlib import Path
from html import escape
import markdown
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
PLAN=HERE.with_suffix('.md')
svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 670" role="img" aria-label="Schematic baseline settings gallery with numeric, enum, slider and planned reference widgets">',
     '<rect width="1120" height="670" rx="14" fill="#132b26"/>']
def text(x,y,value,size=18,color='#e8efdf'):
    svg.append(f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" fill="{color}">{escape(value)}</text>')
text(32,49,'Baseline / SampleSettings · settings-gallery preset',27)
for i,name in enumerate(['General','Numbers','Choices','Assets','References']):
    svg.append(f'<rect x="32" y="{85+i*72}" width="190" height="56" rx="6" fill="'+('#477958' if i==0 else '#223e32')+'"/>')
    text(48,120+i*72,name)
rows=[('Signed count','−12','A: numeric entry'),('Fractional gain','0.75','← / → change'),('Quality','Medium','← / → change'),('Enabled','On','← off / → on'),('Tint','#42A5F5','Colour widget planned'),('Direction','X 1 / Y 0 / Z 0','Vector widget planned'),('Target','UnitCube','Read-only until supported')]
for i,(name,value,hint) in enumerate(rows):
    y=85+i*64
    svg.append(f'<rect x="248" y="{y}" width="840" height="55" rx="6" fill="'+('#477958' if i==2 else '#223e32')+'"/>')
    text(265,y+34,name);text(500,y+34,value);text(755,y+34,hint,15,'#bfd6c6')
text(32,585,'↑ / ↓ selects rows · ← / → changes choices · back arrow applies/closes',18)
text(32,627,'Planning mockup. Unsupported widgets are labelled; this is not runtime evidence.',16,'#bfd6c6')
svg.append('</svg>')
(HERE/'settings-gallery.svg').write_text(''.join(svg))
ET.parse(HERE/'settings-gallery.svg')
body=markdown.markdown(PLAN.read_text(),extensions=['tables','fenced_code'])
# Retain the architecture source while rendering the existing local layout diagram.
start=body.index('<pre><code class="language-mermaid">')
end=body.index('</code></pre>',start)+len('</code></pre>')
body=body[:start]+'<details><summary>Architecture diagram source</summary>'+body[start:end]+'</details>'+body[end:]
style='body{font:17px/1.6 system-ui;max-width:1150px;margin:40px auto;padding:0 26px;color:#21343b;background:#f5f7f6}h1,h2,h3{line-height:1.2}h2{margin-top:2em}a{color:#146b75}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:15px}th,td{border:1px solid #c6d4d0;padding:10px;vertical-align:top;text-align:left}th{background:#e3ece7}pre{background:#102833;color:#e9f3ef;padding:20px;overflow:auto}'
PLAN.with_suffix('.html').write_text('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>World Foundry baseline plan</title><style>'+style+'</style></head><body>'+body+'</body></html>')
