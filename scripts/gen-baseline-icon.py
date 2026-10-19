#!/usr/bin/env python3
"""gen-baseline-icon.py: draw the baseline level's launcher icon and TV banner.

The art is the baseline scene in miniature: a perspective floor grid under the three RGB unit axes (X red,
Y green, Z blue), each ending in an arrowhead. The art carries no text. The World Foundry logo is stamped
bottom-right by scripts/add-wf-logo.py, per docs/reference/android-brand-badge.md; the banner also carries
the game's name bottom-left, as that standard requires for every TV banner.

Writes into --out (default android/app/art-src/baseline-icon-2026-10-11/):
  icon-art.png, banner-art.png   the clean art, no logo (always stamp clean art, never stamped art)
  icon.png (256 x 256), tv_banner.png (640 x 360)   what wflevels/baseline/build.py ships
  preview.png                    both, side by side, for review

It does not touch wflevels/baseline/build.py or any APK.

Usage: scripts/gen-baseline-icon.py [--out DIR]
"""
import argparse
import importlib.util
import math
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("addlogo", REPO_ROOT / "scripts" / "add-wf-logo.py")
addlogo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(addlogo)

BG = (23, 32, 40)                      # build.py's #172028
MINOR, MAJOR = (46, 62, 76), (82, 108, 130)
AXES = {"x": ((1, 0, 0), (239, 83, 80)), "y": ((0, 1, 0), (102, 187, 106)), "z": ((0, 0, 1), (66, 165, 245))}
SS = 2                                 # supersample factor, then Lanczos down
FONT_DIRS = ("/usr/share/fonts/truetype/ibm-plex", "/usr/share/fonts/truetype/dejavu")
FONT_NAMES = ("IBMPlexSans-SemiBold.ttf", "DejaVuSans-Bold.ttf")


def font(size):
    for d in FONT_DIRS:
        for n in FONT_NAMES:
            p = pathlib.Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    sys.exit("gen-baseline-icon: no IBM Plex Sans or DejaVu Sans font found")


class Camera:
    """Pinhole camera looking at `target` from `eye`, world Z up (World Foundry: X right, Y depth, Z up)."""

    def __init__(self, eye, target, focal, centre):
        self.eye, self.focal, self.centre = eye, focal, centre
        f = self._norm(self._sub(target, eye))
        r = self._norm(self._cross(f, (0, 0, 1)))
        u = self._cross(r, f)
        self.f, self.r, self.u = f, r, u

    @staticmethod
    def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    @staticmethod
    def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    @staticmethod
    def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    @classmethod
    def _norm(cls, a):
        n = math.sqrt(cls._dot(a, a))
        return (a[0] / n, a[1] / n, a[2] / n)

    def project(self, p):
        """-> (screen x, screen y, depth)"""
        v = self._sub(p, self.eye)
        z = self._dot(v, self.f)
        return (self.centre[0] + self.focal * self._dot(v, self.r) / z,
                self.centre[1] - self.focal * self._dot(v, self.u) / z, z)


def mix(c, bg, t):
    return tuple(round(bg[i] + (c[i] - bg[i]) * t) for i in range(3))


def draw_scene(w, h, cam, px):
    """px: pixels per ~1 world unit at the origin, used for line widths."""
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    reach = 7                                      # the grid spans -reach..reach on X and Y
    for i in range(-reach, reach + 1):
        for horizontal in (False, True):
            a = (-reach, i, 0) if horizontal else (i, -reach, 0)
            b = (reach, i, 0) if horizontal else (i, reach, 0)
            steps = 28                             # split each line so the fade follows distance from the origin
            for s in range(steps):
                p0 = tuple(a[k] + (b[k] - a[k]) * s / steps for k in range(3))
                p1 = tuple(a[k] + (b[k] - a[k]) * (s + 1) / steps for k in range(3))
                mid = tuple((p0[k] + p1[k]) / 2 for k in range(3))
                fade = max(0.0, 1 - math.hypot(mid[0], mid[1]) / (reach * 1.25)) ** 1.1
                major = i % 5 == 0
                col = mix(MAJOR if major else MINOR, BG, fade)
                d.line([cam.project(p0)[:2], cam.project(p1)[:2]], fill=col, width=max(1, round(px * (0.035 if major else 0.02))))

    # axes: far ones first so the near ones overlap them
    items = []
    length, head_len, head_r = 3.0, 0.95, 0.34
    for name, (vec, col) in AXES.items():
        tip = tuple(vec[k] * length for k in range(3))
        items.append((cam.project(tip)[2], name, vec, col))
    for _, name, vec, col in sorted(items, reverse=True):
        base = tuple(vec[k] * (length - head_len) for k in range(3))
        tip = tuple(vec[k] * length for k in range(3))
        o, bs = cam.project((0, 0, 0)), cam.project(base)
        width = max(2, round(px * 0.11))
        d.line([o[:2], bs[:2]], fill=col, width=width)
        d.ellipse((o[0] - width / 2, o[1] - width / 2, o[0] + width / 2, o[1] + width / 2), fill=col)
        # the arrowhead: a cone of triangles, back to front, shaded by a fixed light so it reads as solid
        a = (0, 0, 1) if vec != (0, 0, 1) else (1, 0, 0)
        e1 = Camera._norm(Camera._cross(vec, a))
        e2 = Camera._cross(vec, e1)
        n = 28
        ring = [tuple(base[k] + head_r * (math.cos(2 * math.pi * i / n) * e1[k] + math.sin(2 * math.pi * i / n) * e2[k]) for k in range(3))
                for i in range(n)]
        tris = []
        for i in range(n):
            p, q = ring[i], ring[(i + 1) % n]
            ctr = tuple((tip[k] + p[k] + q[k]) / 3 for k in range(3))
            mid = ((i + 0.5) / n) * 2 * math.pi
            normal = tuple(math.cos(mid) * e1[k] + math.sin(mid) * e2[k] + 0.35 * vec[k] for k in range(3))
            normal = Camera._norm(normal)
            light = Camera._norm((-0.4, -0.6, 0.7))
            shade = 0.62 + 0.38 * max(0.0, Camera._dot(normal, light))
            tris.append((cam.project(ctr)[2], (tip, p, q), mix(col, (0, 0, 0), shade)))
        d.polygon([cam.project(p)[:2] for p in ring], fill=mix(col, (0, 0, 0), 0.5))   # the base cap
        for _, tri, c in sorted(tris, key=lambda t: -t[0]):
            d.polygon([cam.project(p)[:2] for p in tri], fill=c)
    return img


def render(w, h, centre, focal):
    cam = Camera(eye=(-7.0, -7.0, 6.2), target=(0.6, 0.6, 0.9), focal=focal * SS, centre=(centre[0] * SS, centre[1] * SS))
    big = draw_scene(w * SS, h * SS, cam, px=focal * SS / 9.5)
    return big.resize((w, h), Image.LANCZOS)


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    icon_art = render(1024, 1024, centre=(470, 520), focal=1450)
    banner_art = render(1920, 1080, centre=(930, 500), focal=1700)
    icon_art.save(out / "icon-art.png", optimize=True)
    banner_art.save(out / "banner-art.png", optimize=True)

    # Baseline packages one drawable icon. Google TV displays that square through
    # a round mask, so place the badge inside the visible circle.
    icon = addlogo.add_logo(icon_art.resize((256, 256), Image.LANCZOS),
                            scale=0.24, margin=0.05, safe_circle=1.0).convert("RGB")
    icon.save(out / "icon.png", optimize=True)

    banner = banner_art.resize((640, 360), Image.LANCZOS).convert("RGBA")
    shade = Image.new("RGBA", banner.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(70):
        sd.line((0, 359 - i, 639, 359 - i), fill=(0, 0, 0, int(150 * (1 - i / 70) ** 1.6)))
    banner = Image.alpha_composite(banner, shade)
    d = ImageDraw.Draw(banner)
    f = font(34)
    x0, y0, x1, y1 = d.textbbox((0, 0), "baseline", font=f)
    d.text((22 - x0 + 1, 360 - 22 - (y1 - y0) - y0 + 2), "baseline", font=f, fill=(0, 0, 0, 160))
    d.text((22 - x0, 360 - 22 - (y1 - y0) - y0), "baseline", font=f, fill=(255, 255, 255, 255))
    banner = addlogo.add_logo(banner, scale=0.22, margin=0.05).convert("RGB")
    banner.save(out / "tv_banner.png", optimize=True)

    sheet = Image.new("RGB", (640 + 256 + 3 * 24, 360 + 2 * 24), (40, 40, 40))
    sheet.paste(banner, (24, 24))
    round_mask = Image.new("L", icon.size, 0)
    ImageDraw.Draw(round_mask).ellipse((0, 0, 255, 255), fill=255)
    sheet.paste(icon, (640 + 2 * 24, 24), round_mask)
    sheet.save(out / "preview.png", optimize=True)
    print(f"gen-baseline-icon: wrote icon.png, tv_banner.png, the clean art and preview.png under {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=pathlib.Path, default=REPO_ROOT / "android/app/art-src/baseline-icon-2026-10-11")
    build(ap.parse_args().out)


if __name__ == "__main__":
    main()
