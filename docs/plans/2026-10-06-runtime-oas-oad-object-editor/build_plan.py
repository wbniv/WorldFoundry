"""Build editable SVG plan diagrams/mockups and the local review document."""
from pathlib import Path
import html
import markdown
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
PLAN=HERE.parent/(HERE.name+'.md')


def svg(w,h,content):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#81d5bc"/></marker></defs>
<rect width="{w}" height="{h}" rx="16" fill="#102833"/>
<g font-family="sans-serif" fill="#e9f3ef">{content}</g></svg>'''


def text(x,y,value,size=17,fill='#e9f3ef'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}">{html.escape(value)}</text>'


def box(x,y,w,h,title,lines=(),fill='#1c404a'):
    result=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="#4e807e"/>'
    result+=text(x+15,y+29,title,19)
    for k,line in enumerate(lines):result+=text(x+15,y+56+k*24,line,15)
    return result


def arrow(points):
    return f'<path d="{points}" fill="none" stroke="#81d5bc" stroke-width="2" marker-end="url(#arrow)"/>'


def build():
    content=text(28,38,'Shared schema and editing behavior; host-specific widgets',24)
    content+=box(28,66,265,100,'OAS → OAD',('Names, types, choices, limits','Authored instance values'))
    content+=box(354,66,310,100,'Shared attribute libraries',('wf_attr_schema / validate','Compact descriptor + editor core'))
    content+=box(730,66,290,100,'Cooked property catalog',('One schema; per-object values','Qualified keys / field handles'))
    content+=arrow('M293 116H348')+arrow('M664 116H724')
    content+=box(354,226,310,100,'Shared draft / validation',('Preferred: small Rust core + C ABI','Fallback: generated parity fixtures'))
    content+=arrow('M509 166V220')+arrow('M875 166V196H650V220')
    content+=box(28,392,290,102,'Blender host',('Existing wf_core Python adapter','bpy property widgets stay here'))
    content+=box(382,392,282,102,'TV host',('Generic focus, keypad and fields','Existing rectangle/text drawing'))
    content+=box(730,392,290,102,'Phone host',('Schema-driven DOM controls','One authoritative native draft'))
    content+=arrow('M415 326V357H173V386')+arrow('M509 326V386')+arrow('M603 326V357H875V386')
    content+=text(30,540,'wf-edit: behavior reference only. No ImGui, CRDT, Blender or Python interpreter in the game.',17)
    (HERE/'architecture.svg').write_text(svg(1050,565,content))

    content=text(28,38,'Edit this object, then read its committed properties',24)
    content+=box(28,73,250,105,'Generic form',('Snapshot revision → draft','TV / phone edits same session'))
    content+=box(347,73,300,105,'Validate / preflight',('Type, bounds, enum, text rules','All valid → one game-thread commit'))
    content+=box(718,73,302,105,'Object instance registry',('Original values + own overrides','Other instances stay unchanged'))
    content+=arrow('M278 125H341')+arrow('M647 125H712')
    content+=box(28,305,250,105,'C++ consumer',('Typed effective-value getter','Plant effects: regenerate / rate'))
    content+=box(347,305,300,105,'Forth consumer',('Generic property@ + generated IDs','Water type → goby / urchin'))
    content+=box(718,305,302,105,'Native cached properties',('Explicit live setter or reload policy','No automatic shared-page patch'))
    content+=arrow('M868 178V236H153V299')+arrow('M868 236H497V299')+arrow('M868 236V299')
    content+=text(28,452,'Cancel discards drafts. Invalid Apply retains errors. Stale sessions / object generations reject edits.',16)
    content+=text(28,481,'Runtime reads see committed values. The schema and packed level remain authoring inputs.',16)
    (HERE/'commit.svg').write_text(svg(1050,510,content))

    content=text(30,38,'Generic object properties · TV mockup',23)
    content+=box(32,62,1036,560,'Planted Tank / Director · Properties',fill='#173c35')
    content+=text(63,133,'Plant growth',21)
    for y,label,value,fill in ((151,'Seed','713 · A: number entry','#244b40'),
                                (225,'Water type','Freshwater       Saltwater','#397559')):
        content+=f'<rect x="60" y="{y}" width="968" height="60" rx="8" fill="{fill}"/>'
        content+=text(77,y+37,label,20)+text(460,y+37,value,20)
    content+='<rect x="60" y="300" width="968" height="101" rx="8" fill="#244b40"/>'
    content+=text(77,338,'Growth speed',20)+text(460,330,'1×',20)
    content+='<path d="M465 353H991" stroke="#bed5bc" stroke-width="5"/>'
    for i in range(7):content+=f'<rect x="{463+i*87}" y="344" width="5" height="20" fill="#bed5bc"/>'
    content+='<circle cx="726" cy="353" r="12" fill="#ebd993"/>'
    content+=text(460,385,'Paused      0.25×      0.5×      1×      2×      4×      8×',15)
    content+=box(60,415,968,50,'Regenerate',fill='#244b40')
    content+=box(60,480,968,50,'New random seed',fill='#244b40')
    content+=text(460,556,'[former Apply speed space remains empty]',14,'#9db5a9')
    content+=box(65,573,150,44,'Cancel',fill='#244b40')
    content+=text(552,602,'← Apply settings and close',19)
    content+=text(40,652,'↑ ↓ rows   A: edit field   Numeric entry opens its own keypad drawer',17)
    (HERE/'tv.svg').write_text(svg(1100,680,content))

    content=text(27,40,'Object properties',22)
    content+=text(27,73,'Planted Tank / Director',16,'#b9d2c7')
    content+=text(27,117,'Seed',17)
    content+=box(25,130,340,62,'713',fill='#254b42')
    content+=text(27,223,'Water type',17)
    content+=box(25,238,166,57,'Freshwater',fill='#397559')
    content+=box(199,238,166,57,'Saltwater',fill='#254b42')
    content+=text(27,333,'Growth speed: 1×',17)
    content+='<path d="M40 362H350" stroke="#bed5bc" stroke-width="5"/><circle cx="195" cy="362" r="12" fill="#ebd993"/>'
    content+=text(28,401,'Paused          1×                         8×',15,'#b9d2c7')
    content+=box(25,434,340,62,'Regenerate',fill='#254b42')
    content+=box(25,509,340,62,'New random seed',fill='#254b42')
    content+=text(29,630,'← Apply settings and close',18)
    content+=box(25,656,340,54,'Cancel',fill='#254b42')
    content+=text(27,749,'TV: editing on connected phone',15,'#b9d2c7')
    (HERE/'phone.svg').write_text(svg(390,780,content))
    content=text(28,38,'Schema layout: order and meaning are shared; placement follows the screen',23)
    content+=box(28,74,286,124,'OAD ordered entries',('Property sheets → sections','Groups → named field groups','Types / showAs → widget family'))
    content+=box(377,74,286,124,'Ordered form tree',('Stable section and field keys','Exposure + apply policy','Labels / help / options'))
    content+=box(726,74,286,124,'Measure and arrange',('TV: label/value rows + rail','Phone: stacked section rows','Wrap labels; scroll overflow'))
    content+=arrow('M314 136H371')+arrow('M663 136H720')
    content+=box(28,275,440,120,'Focus model',('Rail ↔ field list ↔ footer','Field editor / keypad owns its input','Auto-scroll focused rows; retain field identity'))
    content+=box(559,275,453,120,'Many fields / sections',('Keep readable row sizes; virtualize long lists','Scroll rails and choice lists too','No plant coordinate table or legacy OAD x/y'))
    content+=arrow('M869 198V235H780V269')+arrow('M726 165H701V250H249V269')
    content+=text(29,443,'Back: dismiss entry popups first; on form or inline slider → apply/close → game navigation.',17)
    (HERE/'layout.svg').write_text(svg(1040,475,content))

    content=text(30,38,'Generic object editor · large-schema TV mockup',23)
    content+=box(30,62,1040,545,'Player / Properties',fill='#173c35')
    sections=['General','Movement','Appearance','Controls','Behavior','Sound','More sections ↓']
    for k,label in enumerate(sections):content+=box(52,127+k*55,211,46,label,fill='#397559' if k==1 else '#254b42')
    content+=text(296,149,'Movement',22)
    content+=text(296,184,'Locomotion',17,'#b9d2c7')
    rows=[('Mobility','Physics · reload required'),('Max ground speed','4.00'),('Acceleration','2.50'),('Ground friction','0.80'),('Long property label wraps','Current value')]
    for k,(label,value) in enumerate(rows):
        y=198+k*63
        content+=f'<rect x="289" y="{y}" width="730" height="55" rx="6" fill="'+('#397559' if k==1 else '#254b42')+'"/>'
        content+=text(303,y+33,label,18)+text(656,y+33,value,18)
    content+='<rect x="1033" y="196" width="7" height="301" rx="3" fill="#31554b"/><rect x="1033" y="228" width="7" height="61" rx="3" fill="#bed5bc"/>'
    content+=text(296,536,'Focused field help: movement speed in world units per second.',16,'#b9d2c7')
    content+=box(296,554,130,40,'Cancel',fill='#254b42')
    content+=text(693,581,'← Apply and close',19)
    content+=text(34,646,'↑ ↓ rows   ← sections   A edit   Fields 2–6 of 27 · readable rows; additional fields scroll',17)
    (HERE/'large-object-tv.svg').write_text(svg(1100,675,content))
    for name in ('architecture','commit','tv','phone','layout','large-object-tv'):ET.parse(HERE/(name+'.svg'))
    body=markdown.markdown(PLAN.read_text(),extensions=['tables','fenced_code'])
    style='''body{font:17px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 26px;color:#21343b;background:#f5f7f6}h1,h2,h3{line-height:1.2}h2{margin-top:2em}a{color:#146b75}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:15px}th,td{border:1px solid #c6d4d0;padding:10px;vertical-align:top;text-align:left}th{background:#e3ece7}pre{background:#102833;color:#e9f3ef;padding:20px;overflow:auto}code{font-size:.92em}'''
    PLAN.with_suffix('.html').write_text('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Generic runtime OAS/OAD object editor</title><style>'+style+'</style></head><body>'+body+'</body></html>')


if __name__=='__main__':build()
