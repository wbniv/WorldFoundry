"""Blue Jelly palette atlas on the existing shrimp model; opacity is OPAC metadata."""
import struct
from pathlib import Path

# Matches geometry.PALETTE slot order. No geometry or rig changes.
JELLY_PALETTE = [(57,156,207), (80,184,218), (149,218,236), (45,120,161),
                 (130,199,220), (168,224,237), (4,7,9), (205,242,255)]

def write_jelly_texture(path):
    # 64x32 RGB TGA, top-left origin. Uniform 16x16 swatches avoid filtering seams.
    # UV v=0 starts at the bottom in Blender, so emit upper swatches first.
    header = struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,64,32,24,0x20)
    pixels = bytearray()
    for y in range(32):
        for x in range(64):
            slot = x//16 + (1-y//16)*4
            r,g,b = JELLY_PALETTE[slot]
            pixels.extend((b,g,r))
    Path(path).write_bytes(header+pixels)

if __name__ == '__main__':
    write_jelly_texture(Path(__file__).with_name('blue_jelly.tga'))
