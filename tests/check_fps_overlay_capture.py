"""Check that a default FPS overlay changes only the bottom-right image region."""
import argparse
from compare_renderer_frames import read_png

parser = argparse.ArgumentParser()
parser.add_argument("disabled")
parser.add_argument("enabled")
args = parser.parse_args()
width, height, disabled = read_png(args.disabled)
w, h, enabled = read_png(args.enabled)
assert (width, height) == (w, h), "surface dimensions differ"
changed = [i for i in range(width * height)
           if disabled[3*i:3*i+3] != enabled[3*i:3*i+3]]
assert changed, "overlay did not change any pixels"
xs, ys = zip(*((i % width, i // width) for i in changed))
bounds = min(xs), min(ys), max(xs) + 1, max(ys) + 1
assert bounds[0] >= width * 0.65 and bounds[1] >= height * 0.75, bounds
assert bounds[2] <= width * 0.98 and bounds[3] <= height * 0.98, bounds
white = sum(min(enabled[3*(y*width+x):3*(y*width+x)+3]) >= 240
            for y in range(bounds[1], bounds[3]) for x in range(bounds[0], bounds[2]))
assert white >= 10, "number glyphs are absent"
print(f"PASS: overlay changes only bottom right {bounds}; {white} white glyph pixels")
