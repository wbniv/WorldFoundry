"""The Discus colorways share the source photograph's palette indices."""
import sys
import json
import struct
import subprocess
import pytest
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'wflevels/aquarium'))
import discus_palettes as palettes
sys.path.insert(0, str(ROOT / 'scripts'))
import attach_indexed_palette


def test_brown_variants_preserve_indices_and_default():
    master = Image.open(palettes.ASSET / 'wild-brown.png')
    variants = dict(palettes.variants())
    assert len(variants) == 12
    assert list(variants)[0] == 'wild-brown'
    assert all(image.tobytes() == master.tobytes() for image in variants.values())
    assert variants['wild-brown'].convert('RGB').tobytes() == master.convert('RGB').tobytes()
    assert len({image.convert('RGB').tobytes() for image in variants.values()}) == 12


def test_export_contains_one_indexed_image_and_twelve_tables(tmp_path):
    palettes.write_palette_assets(tmp_path)
    names = [name for name, _ in palettes.brown_variants()]
    assert {p.name for p in tmp_path.iterdir()} == {'discus-indexed.png', 'discus-index-rgb555.png', 'discus-palettes.json', 'discus-palettes.bin'}
    tables = json.loads((tmp_path / 'discus-palettes.json').read_text())
    assert list(tables) == names
    assert all(len(table) == 256 * 3 for table in tables.values())
    data = (tmp_path / 'discus-palettes.bin').read_bytes()
    assert data[:4] == b'DPLT' and struct.unpack_from('<HH', data, 4) == (1, 12)
    assert len(data) == 8 + 12 * 256 * 3
    assert all(data[8 + i * 768:8 + (i + 1) * 768] == bytes(tables[name]) for i, name in enumerate(names))
    with Image.open(tmp_path / 'discus-indexed.png') as image, Image.open(palettes.ASSET / 'wild-brown.png') as source:
        assert image.mode == 'P' and image.tobytes() == source.tobytes()
        assert tables['wild-brown'] == source.getpalette()


def test_settings_schema_matches_palette_order():
    catalog = ROOT / 'wftools/wf_attr_edit/target/release/catalog'
    schema = json.loads(subprocess.check_output(
        [str(catalog), str(ROOT / 'wfsource/source/oas/discussettings.oad')], text=True))
    field = next(f for f in schema['fields'] if f['key'] == 'Palette')
    assert field['live'] and field['default'] == 0
    assert (field['min'], field['max']) == (0, 11)
    expected = [name.replace('-', ' ').title() for name, _ in palettes.brown_variants()]
    assert field['choices'].split('|') == expected
    assert any(f['key'] == 'Show framerate' for f in schema['fields'])


def test_all_indices_survive_rgb555_encoding_and_zero_is_not_transparent():
    for index in range(256):
        red, green, blue = palettes.encoded_index_rgb(index)
        # Textile's RGB555 conversion drops three low bits of each channel.
        assert ((red >> 3) << 3) | (green >> 3) == index
        assert blue >> 3 != 0


def test_encoded_image_uses_indices_not_palette_colors(tmp_path):
    path = tmp_path / 'indices.png'
    palettes.write_encoded_index_image(path, size=(64, 64))
    master = Image.open(palettes.ASSET / 'wild-brown.png').resize((64, 64), Image.Resampling.NEAREST)
    encoded = Image.open(path).convert('RGB')
    assert encoded.tobytes() == bytes(c for i in master.tobytes() for c in palettes.encoded_index_rgb(i))


def test_palette_bundle_preserves_cooked_level_and_locates_tables(tmp_path):
    palettes.write_palette_assets(tmp_path)
    original = (ROOT / 'wflevels/aquarium-standalone.iff').read_bytes()
    table = (tmp_path / 'discus-palettes.bin').read_bytes()
    result = attach_indexed_palette.attach(original, table)
    assert result[4096:len(original)] == original[4096:]
    assert len(result) % 2048 == 0
    pos = result.index(b'IPLT', 2048, 4096)
    offset, length = struct.unpack_from('<II', result, pos + 4)
    chunk = 2048 + offset
    assert result[chunk:chunk + 4] == b'IPLT'
    assert struct.unpack_from('<I', result, chunk + 4)[0] == len(table)
    assert result[chunk + 8:chunk + 8 + len(table)] == table
    assert length % 2048 == 0
    with pytest.raises(ValueError, match='already present'):
        attach_indexed_palette.attach(result, table)


def test_cooked_fish_material_names_the_encoded_index_image():
    mesh = (ROOT / 'wflevels/aquarium_discus/discus.iff').read_bytes()
    offset = 8
    materials = None
    while offset + 8 <= len(mesh):
        tag = mesh[offset:offset + 4]
        size = struct.unpack_from('<I', mesh, offset + 4)[0]
        if tag == b'MATL':
            materials = mesh[offset + 8:offset + 8 + size]
            break
        offset += 8 + (size + 3) // 4 * 4
    assert materials and len(materials) % 264 == 0
    for pos in range(0, len(materials), 264):
        assert struct.unpack_from('<I', materials, pos)[0] & 128
        assert b'discus-index-rgb555.png' in materials[pos:pos + 264]


def test_discus_standalone_contains_palette_and_settings():
    level = (ROOT / 'wflevels/aquarium_discus-standalone.iff').read_bytes()
    assert b'IPLT' in level[2048:4096] and b'DPLT' in level[4096:]
    assert b'Discus Settings' in level and b'Wild Brown' in level


def test_cooked_atlas_preserves_every_index():
    master = Image.open(palettes.ASSET / 'wild-brown.png').resize((512, 512), Image.Resampling.NEAREST)
    tga = (ROOT / 'wflevels/aquarium_discus/Room0.tga').read_bytes()
    width, height = struct.unpack_from('<HH', tga, 12)
    assert (width, height, tga[16]) == (512, 512, 16)
    pixels = struct.unpack_from('<' + str(width * height) + 'H', tga, 18)
    assert all((p & 31) == 1 for p in pixels)
    assert Counter((((p >> 10) & 31) << 3) | ((p >> 5) & 31) for p in pixels) == Counter(master.tobytes())
