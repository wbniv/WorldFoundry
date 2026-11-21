#!/usr/bin/env python3
"""Assemble labelled review sheets from Blender renders of the actual assets."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
p=argparse.ArgumentParser();p.add_argument('--art-dir',type=Path,default=Path(__file__).resolve().parents[2]/'docs/reference/sea-stars-art');a=p.parse_args()
dest=a.art_dir
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(font_path,25);small=ImageFont.truetype(font_path,20);title=ImageFont.truetype(font_path,46)
manifest=json.loads((dest/'assets.json').read_text())
canvas=Image.new('RGB',(2100,1470),'#102a36');d=ImageDraw.Draw(canvas)
d.text((42,32),'SEA STARS',font=title,fill='#edf2e6')
d.text((44,94),'Six authored species · actual 3D models and skins · source-asset review',font=small,fill='#a9c5c8')
for i,item in enumerate(manifest['species']):
    x=30+(i%3)*690;y=156+(i//3)*640
    im=Image.open(dest/item['image']).convert('RGB');im.thumbnail((670,550))
    canvas.paste(im,(x+(670-im.width)//2,y))
    d.text((x+16,y+565),item['name'],font=font,fill='#edf2e6')
    d.text((x+16,y+601),item['scientific'],font=small,fill='#a9c5c8')
canvas.save(dest/'02-species-sheet.png')
canvas=Image.new('RGB',(2400,1930),'#102a36');d=ImageDraw.Draw(canvas)
d.text((42,32),'THE PLAYER · BLUE LINCKIA',font=title,fill='#edf2e6')
for i,(file,label,caption) in enumerate((
    ('player-leading-arm.png','Any arm can lead','Raised tip and eyespot'),
    ('player-underside.png','Front-glass underside','Five oral grooves and central mouth'),
    ('player-corner.png','Corner roll','Three leading arms bend onto the next surface'),
    ('player-reach.png','Reach','Two arms support the body while three lift'))):
    x=30+(i%2)*1190;y=120+(i//2)*890
    im=Image.open(dest/file).convert('RGB');im.thumbnail((1160,770));canvas.paste(im,(x+(1160-im.width)//2,y))
    d.text((x+20,y+788),label,font=font,fill='#edf2e6');d.text((x+20,y+824),caption,font=small,fill='#a9c5c8')
canvas.save(dest/'03-player-sheet.png')
atlas=Path(__file__).resolve().parent/'stars_atlas.tga'
Image.open(atlas).save(dest/'04-texture-atlas.png')
print(dest/'02-species-sheet.png');print(dest/'03-player-sheet.png')
from html import escape
cards=''.join(f'<figure><a href="{item["image"]}"><img src="{item["image"]}" alt="{escape(item["name"])}"></a><figcaption><strong>{escape(item["name"])}</strong><em>{escape(item["scientific"])}</em></figcaption></figure>' for item in manifest['species'])
poses=''.join(f'<figure><a href="{name}.png"><img src="{name}.png" alt="{label}"></a><figcaption>{label}</figcaption></figure>' for name,label in [('player-leading-arm','Leading arm'),('player-underside','Oral face on the front glass'),('player-corner','Corner bend'),('player-reach','Reach')])
(dest/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Sea Stars — 3D asset review</title><style>
*{box-sizing:border-box}body{margin:0;background:#102a36;color:#edf2e6;font:17px/1.5 system-ui,sans-serif}main{max-width:1450px;margin:auto;padding:40px 30px}h1{font-size:56px;line-height:1;margin:18px 0}h2{font-size:30px;margin:48px 0 20px}p{max-width:850px;color:#b9ced0}a{color:#a9e1dd}figure{margin:0;background:#183845;border:1px solid #31505a;border-radius:8px;overflow:hidden}img{width:100%;display:block}figcaption{padding:16px 20px}strong,em{display:block}em{font-size:15px;color:#b9ced0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}.poses{grid-template-columns:repeat(2,1fr)}.tag{text-transform:uppercase;font-size:13px;letter-spacing:2px;color:#87c9c7}.links{margin:24px 0 32px;display:flex;gap:24px;flex-wrap:wrap}.atlas{max-width:512px}.note{font-size:15px}@media(max-width:850px){.grid{grid-template-columns:repeat(2,1fr)}h1{font-size:44px}}@media(max-width:550px){main{padding:24px 14px}.grid{grid-template-columns:1fr}}
</style><main><div class="tag">Source asset review · 20 November 2026</div><h1>Sea Stars</h1><p>Six species, a sand-flat tank, and the blue Linckia’s underside and arm poses. These views render the authored meshes and skins under presentation lighting. Gameplay and device acceptance remain pending.</p><nav class="links"><a href="../sea-stars-bestiary/sea-stars-bestiary.pdf">Bestiary catalogue PDF</a><a href="../../../wflevels/aquarium_sea_stars/sea_stars_assets.blend" download>Editable Blender master</a><a href="02-species-sheet.png">Species sheet</a><a href="03-player-sheet.png">Player sheet</a><a href="verification.json">Source checks</a></nav><figure><a href="01-tank-wide.png"><img src="01-tank-wide.png" alt="Sea Stars tank with ten animals, three rocks, sand and seagrass"></a></figure><h2>The six species</h2><div class="grid">'''+cards+'''</div><h2>The player</h2><div class="grid poses">'''+poses+'''</div><h2>The texture atlas</h2><figure class="atlas"><a href="04-texture-atlas.png"><img src="04-texture-atlas.png" alt="512-square source material atlas"></a></figure><p class="note">The packed Blender master includes the tank scenery, the default ten-animal arrangement, arm rigs and pose actions. The static scenery uses 3,474 triangles in four groups. D11 live settings are deferred.</p></main></html>''')
print(dest/'index.html')
