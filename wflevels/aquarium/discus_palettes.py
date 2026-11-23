"""Generate the Discus tank's brown-family palette variants from its indexed master."""
import colorsys
import json
import struct
from pathlib import Path

from PIL import Image

ASSET = Path(__file__).resolve().parent.parent / 'discus_asset'


def brown_variants():
    manifest = json.loads((ASSET / 'palettes.json').read_text())
    return [(name, values) for name, values in manifest.items()
            if values['pattern'] == 'brown-photograph']


def variants():
    master = Image.open(ASSET / 'wild-brown.png')
    if master.mode != 'P' or len(master.getpalette() or []) != 768:
        raise ValueError('wild-brown.png must be the indexed brown-family master')
    original = master.getpalette()
    for name, values in brown_variants():
        palette = []
        for i in range(0, 768, 3):
            r, g, b = (v / 255 for v in original[i:i + 3])
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            rgb = colorsys.hsv_to_rgb((h + values['hue_rotation']) % 1,
                                      min(1, s * values['saturation_scale']),
                                      min(1, v * values['value_scale']))
            palette.extend(round(c * 255) for c in rgb)
        image = master.copy()
        image.putpalette(palette)
        yield name, image


def write_palette_assets(output):
    """Write one indexed image and the lookup tables; do not bake RGB variants."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    images = list(variants())
    images[0][1].save(output / 'discus-indexed.png')
    tables = {name: image.getpalette() for name, image in images}
    (output / 'discus-palettes.json').write_text(json.dumps(tables, indent=2) + '\n')
    # A fixed header and RGB888 tables. Image indices are stored separately and
    # never change when the selected table changes.
    payload = bytearray(b'DPLT' + struct.pack('<HH', 1, len(images)))
    for _, image in images:
        payload.extend(image.getpalette())
    (output / 'discus-palettes.bin').write_bytes(payload)
    write_encoded_index_image(output / 'discus-index-rgb555.png')


def encoded_index_rgb(index):
    """Represent one index exactly through the existing RGB555 texture cook.

    Red carries the high five bits and green the low three; blue is nonzero so
    the standard black-transparent remap does not erase index zero. This is an
    index image, not a palette-baked color texture. A renderer must sample it
    without linear interpolation before applying the selected lookup table.
    """
    if not 0 <= index <= 255:
        raise ValueError('pixel index out of range')
    return ((index >> 3) << 3, (index & 7) << 3, 8)


def write_encoded_index_image(path, size=(512, 512)):
    path = Path(path)
    # Textile's legacy 24-bit TGA fast path interprets channel bytes in a
    # different order; PNG takes the explicitly RGB decoder path.
    if path.suffix.lower() != '.png':
        raise ValueError('encoded index images must use PNG')
    master = Image.open(ASSET / 'wild-brown.png')
    if master.mode != 'P':
        raise ValueError('wild-brown.png must be indexed')
    indices = master.resize(size, Image.Resampling.NEAREST).tobytes()
    image = Image.frombytes('RGB', size, bytes(c for index in indices for c in encoded_index_rgb(index)))
    image.save(path)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    write_palette_assets(parser.parse_args().output)
