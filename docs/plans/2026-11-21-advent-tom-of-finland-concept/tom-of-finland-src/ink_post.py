"""Turn the raw shaded + Freestyle render into a hatched ink-and-graphite drawing.

  python3 -I ink_post.py raw.png out.png

Tone becomes hatching: diagonal strokes whose weight follows the shade, a second
cross-stroke layer in the darks, solid ink in the deepest shadow. Bright emitters
(window glow, lamps, numbers, snow) stay paper-white. A thin wash of the original
colour is kept so the red scarves, doors and warm light still read.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter

src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGB")
W, H = im.size
rgb = np.asarray(im, dtype=np.float32) / 255.0
# denoise the tone map a little before turning it into strokes
blur = np.asarray(im.filter(ImageFilter.GaussianBlur(radius=max(1.0, W / 1100))), dtype=np.float32) / 255.0
LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
lum = blur @ LUMA
lum_raw = rgb @ LUMA

tone = np.clip(1.0 - lum ** 0.8, 0, 1) ** 0.9             # 0 paper .. 1 black, slightly deeper darks
scale = W / 1920.0
period = 7.0 * scale
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rng = np.random.default_rng(3)
wob = rng.normal(0, 0.18, size=(H // 16 + 2, W // 16 + 2)).astype(np.float32)
wob = np.asarray(Image.fromarray(wob).resize((W, H), Image.BICUBIC))   # slow hand wobble


def strokes(angle, per, t0, t1):
    c, s = np.cos(angle), np.sin(angle)
    u = (xx * c + yy * s) / per + wob
    wave = 0.5 + 0.5 * np.cos(2 * np.pi * u)               # 1 on a stroke centre
    w = np.clip((tone - t0) / (t1 - t0), 0, 1)             # stroke weight from tone
    return np.clip((wave - (1.0 - w * 0.95)) * 6.0, 0, 1) * (w > 0)


h1 = strokes(np.deg2rad(52), period, 0.12, 0.62)
h2 = strokes(np.deg2rad(-38), period * 1.15, 0.42, 0.85)
fill = np.clip((tone - 0.80) / 0.14, 0, 1)
ink = np.clip(np.maximum.reduce([h1 * 0.9, h2 * 0.9, fill]), 0, 1)
# crisp outlines: the Freestyle lines are near-black in the raw render
line = np.clip((0.07 - lum_raw) / 0.05, 0, 1)
# door numerals: thin dark strokes beside a bright sticker. Kept un-blurred and un-hatched so they stay legible.
near_bright = np.asarray(Image.fromarray((np.clip(lum_raw, 0, 1) * 255).astype(np.uint8)).filter(
    ImageFilter.MaxFilter(2 * max(3, int(round(7 * W / 1920))) + 1)), dtype=np.float32) / 255.0
digits = np.clip((0.55 - lum_raw) / 0.2, 0, 1) * np.clip((near_bright - 0.75) / 0.15, 0, 1)
ink = np.maximum(ink, np.maximum(line, digits))
ink = np.where(digits > 0.5, 1.0, ink)

paper = np.array([0.957, 0.929, 0.862], dtype=np.float32)
pencil = np.array([0.105, 0.098, 0.12], dtype=np.float32)
grain = rng.normal(0, 0.012, size=(H, W, 1)).astype(np.float32)
out = (paper[None, None, :] + grain) * (1 - ink[..., None]) + pencil[None, None, :] * ink[..., None]

# colour wash: keep hue where the original is saturated; lighter wash over bright areas
mx = rgb.max(axis=2); mn = rgb.min(axis=2)
sat = np.clip((mx - mn) / np.maximum(mx, 1e-3) * 1.3, 0, 1)[..., None]
hue = rgb / np.maximum(mx[..., None], 1e-3)
strength = np.where((lum > 0.55)[..., None], 0.45, 0.62)
out = out * (1.0 + (hue - 1.0) * sat * strength)

# paper vignette
vy = (yy / H - 0.5) ** 2 + (xx / W - 0.5) ** 2 * 0.6
out = out * (1.0 - 0.18 * np.clip(vy * 2.0, 0, 1))[..., None]
Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst, optimize=True)
print("wrote", dst, W, H)
