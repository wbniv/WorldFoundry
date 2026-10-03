"""Check that a default FPS overlay changes only the bottom-right image region."""
import argparse
from PIL import Image, ImageChops

parser = argparse.ArgumentParser()
parser.add_argument("disabled")
parser.add_argument("enabled")
args = parser.parse_args()
disabled = Image.open(args.disabled).convert("RGB")
enabled = Image.open(args.enabled).convert("RGB")
assert disabled.size == enabled.size, "surface dimensions differ"
width, height = enabled.size
bounds = ImageChops.difference(disabled, enabled).getbbox()
assert bounds, "overlay did not change any pixels"
assert bounds[0] >= width * 0.65 and bounds[1] >= height * 0.75, bounds
assert bounds[2] <= width * 0.98 and bounds[3] <= height * 0.98, bounds
region = enabled.crop(bounds)
white = sum(min(pixel) >= 240 for pixel in region.getdata())
assert white >= 10, "number glyphs are absent"
print(f"PASS: overlay changes only bottom right {bounds}; {white} white glyph pixels")
