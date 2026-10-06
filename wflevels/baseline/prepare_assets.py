"""Small deterministic textures; no generated bitmap artwork or external assets."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
LABELS = [str(i) for i in range(-100, 101, 10)] + [
    'X (1,0,0)', 'Y (0,1,0)', 'Z (0,0,1)', '(0,0,0)',
    'SPAWN +Y', '1 x 1 x 1', '10 units', 'PLAYER BOX', 'UV +U +V']

def prepare():
    image = Image.new('RGB', (256, 256), '#222b32')
    draw = ImageDraw.Draw(image)
    for k in range(10):
        q = round(k * 256 / 10)
        colour = '#83949d' if k == 0 else '#3f4b54'
        draw.line((q, 0, q, 255), fill=colour, width=3 if k == 0 else 1)
        draw.line((0, q, 255, q), fill=colour, width=3 if k == 0 else 1)
    image.save(HERE / 'grid.tga')
    atlas = Image.new('RGB', (512, 256), '#172028')
    draw = ImageDraw.Draw(atlas)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
    for i, label in enumerate(LABELS):
        x, y = (i % 4) * 128, (i // 4) * 32
        draw.text((x + 64, y + 16), label, font=font, anchor='mm', fill='#f0f3f4')
    atlas.save(HERE / 'labels.tga')
    swatch = Image.new('RGB', (128, 128), '#152c40')
    draw = ImageDraw.Draw(swatch)
    for y in range(8):
        for x in range(8):
            draw.rectangle((x*16, y*16, x*16+15, y*16+15), fill='#d3dfd7' if (x+y)%2 else '#355b73')
    draw.text((4, 4), '+U >', fill='#ef5350', font=font)
    draw.text((4, 98), '+V ^', fill='#66bb6a', font=font)
    swatch.save(HERE / 'uv.tga')

if __name__ == '__main__':
    prepare()
