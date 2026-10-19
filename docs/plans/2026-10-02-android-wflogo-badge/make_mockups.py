#!/usr/bin/env python3
"""Render proposal assets only; never write Android shipping resources."""
import importlib.util
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CROP = (4, 25, 82, 129)  # graphic interior, excluding every black frame edge

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

gen = load('icons', ROOT / 'scripts/gen-android-icons.py')
source = Image.open(ROOT / 'wflogo.png').convert('RGBA')
graphic = source.crop(CROP)
graphic.save(HERE / 'proposed-badge-crop.png')
transparent_border = False
no_border = False

def render_graphic(_path, size):
    return ImageOps.contain(graphic, (size, size), Image.Resampling.LANCZOS)

def stamp(img, logo_path=None, scale=.26, margin=.05, safe_inset=0., circle=False, safe_circle=0.):
    img = img.convert('RGBA')
    w, h = img.size
    short = min(w, h)
    side = max(8, round(short * scale))
    framed = ImageOps.expand(render_graphic(None, side), border=0 if no_border else max(1, round(side*.07)),
                            fill=(0, 0, 0, 0) if transparent_border else 'white')
    fw, fh = framed.size
    if circle or safe_circle:
        radius = short * (safe_circle or 1.) / 2
        # Bound the whole rectangular badge by its circumcircle.
        reach = radius - math.hypot(fw, fh)/2 - short*margin*.5
        cx, cy = w/2 + reach/math.sqrt(2), h/2 + reach/math.sqrt(2)
        pos = (round(cx-fw/2), round(cy-fh/2))
        if circle:
            mask = Image.new('L', (w*4,h*4))
            ImageDraw.Draw(mask).ellipse((0,0,w*4-1,h*4-1),fill=255)
            img.putalpha(mask.resize((w,h),Image.Resampling.LANCZOS))
    else:
        inset = round(short*max(margin,safe_inset))
        pos = (w-inset-fw,h-inset-fh)
    img.alpha_composite(framed,pos)
    return img

# Substitute only inside this preview process; source scripts remain unchanged.
gen.addlogo.render_svg_rects = render_graphic
gen.addlogo.add_logo = stamp
canvas = Image.new('RGB', (780, 350), '#e8e8e8')
d = ImageDraw.Draw(canvas)
for x, title in ((20,'Original wflogo.png'),(280,'Borderless crop'),(540,'Badge with white keyline')):
    d.text((x,12),title,fill='black')
canvas.paste(source.resize((216,266), Image.Resampling.NEAREST),(20,42))
canvas.paste(graphic.resize((160,210),Image.Resampling.NEAREST),(280,55))
tile = render_graphic(None, 180)
framed = ImageOps.expand(tile,border=13,fill='white')
canvas.paste(framed,(540,55))
canvas.save(HERE/'badge-proposal.png')

def app_previews(filename):
    preview = Image.new('RGB',(1000,570),'#eeeeee')
    d = ImageDraw.Draw(preview)
    for i,(game,g) in enumerate(gen.GAMES.items()):
        x = i*200
        d.text((x+10,12),game,fill='black')
        art = Image.open(g['icon']).convert('RGB').crop(g['icon_crop'])
        m = round(art.width*(1-gen.LEGACY_INNER)/2)
        inner = art.crop((m,m,art.width-m,art.width-m)).resize((192,192),Image.Resampling.LANCZOS)
        preview.paste(gen.addlogo.add_logo(inner,scale=.26).convert('RGB'),(x+4,40))
        fg = gen.addlogo.add_logo(art.resize((432,432),Image.Resampling.LANCZOS),scale=.17,safe_circle=gen.LEGACY_INNER)
        circle = fg.crop((72,72,360,360)).resize((192,192),Image.Resampling.LANCZOS)
        mask = Image.new('L',(192,192)); ImageDraw.Draw(mask).ellipse((0,0,191,191),fill=255)
        preview.paste(circle,(x+4,245),mask)
        preview.paste(gen.banner(g).resize((192,108),Image.Resampling.LANCZOS),(x+4,442))
    preview.save(HERE / filename)

app_previews('proposed-app-previews.png')
with_globes = graphic.copy()
# The globe background occupies the light neutral palette (187..255).
# Keep the black silhouette's darker antialias pixels and all red pixels intact.
for y in range(graphic.height):
    for x in range(graphic.width):
        r, g, b, a = graphic.getpixel((x, y))
        if r == g == b and r >= 187:
            graphic.putpixel((x, y), (255, 255, 255, a))
graphic.save(HERE / 'proposed-badge-no-globes.png')
app_previews('proposed-app-previews-no-globes.png')

comparison = Image.new('RGB', (620, 330), '#e8e8e8')
d = ImageDraw.Draw(comparison)
for x, title, art in ((40, 'A: with background globes', with_globes),
                       (350, 'B: without background globes', graphic)):
    d.text((x, 15), title, fill='black')
    framed = ImageOps.expand(ImageOps.contain(art, (180, 240), Image.Resampling.LANCZOS),
                            border=17, fill='white')
    comparison.paste(framed, (x, 45))
comparison.save(HERE / 'badge-comparison.png')

# Set C starts from B: remove its white matte, retaining smooth black edges.
for y in range(graphic.height):
    for x in range(graphic.width):
        r, g, b, a = graphic.getpixel((x, y))
        if r == g == b:
            graphic.putpixel((x, y), (0, 0, 0, round(a * (255-r)/255)))
transparent_border = True
graphic.save(HERE / 'proposed-badge-transparent.png')
app_previews('proposed-app-previews-transparent.png')

# Export the complete third set here, keeping Android shipping resources untouched.
for game, g in gen.GAMES.items():
    res = HERE / 'set-c' / game / 'res'
    (res / 'drawable').mkdir(parents=True, exist_ok=True)
    gen.banner(g).save(res / 'drawable/tv_banner.png')
    art = Image.open(g['icon']).convert('RGB').crop(g['icon_crop'])
    m = round(art.width * (1-gen.LEGACY_INNER)/2)
    inner = art.crop((m, m, art.width-m, art.width-m))
    for density, px in gen.DENSITIES.items():
        dest = res / f'mipmap-{density}'
        dest.mkdir(parents=True, exist_ok=True)
        stamp(art.resize((px, px), Image.Resampling.LANCZOS), scale=.17,
              safe_circle=gen.LEGACY_INNER).save(dest / 'ic_launcher_foreground.png')
    for density, px in gen.LEGACY.items():
        dest = res / f'mipmap-{density}'
        square = inner.resize((px, px), Image.Resampling.LANCZOS)
        stamp(square, scale=.26).convert('RGB').save(dest / 'ic_launcher.png')
        stamp(square, scale=.24, circle=True).save(dest / 'ic_launcher_round.png')

# Set D keeps A's globe background and removes only its white outer border.
graphic = with_globes.copy()
transparent_border = False
no_border = True
graphic.save(HERE / 'proposed-badge-globes-no-border.png')
app_previews('proposed-app-previews-globes-no-border.png')
