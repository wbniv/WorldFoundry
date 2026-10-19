"""Guard actual exported jelly materials and scope of the art change."""
from pathlib import Path
import json
import struct

ROOT = Path(__file__).resolve().parents[1]
LEVEL = ROOT / 'wflevels/aquarium_jellyfish'


def chunks(path):
    data = path.read_bytes()
    assert data[:4] == b'MODL'
    end = struct.unpack_from('<I', data, 4)[0] + 8
    offset, result = 8, {}
    while offset < end:
        tag, length = struct.unpack_from('<4sI', data, offset)
        result[tag] = data[offset + 8:offset + 8 + length]
        offset += 8 + ((length + 3) & ~3)
    assert offset == end
    return result


def test_exported_material_opacity_and_model_integrity():
    for name, expected in [('bell', [.32, .22, .12, .72]),
                           ('arms', [.32]), ('player_hull', [.32, .22, .12, .72])]:
        model = chunks(LEVEL / (name + '.iff'))
        version, count = struct.unpack_from('<II', model[b'OPAC'])
        assert version == 1
        assert count == len(expected) == len(model[b'MATL']) // 264
        assert len(model[b'OPAC']) == 8 + 4 * count
        values = struct.unpack_from('<' + 'I' * count, model[b'OPAC'], 8)
        assert all(abs(value / 65536 - opacity) < 1 / 65536
                   for value, opacity in zip(values, expected))
    # The player collision hull and visible bell still share the rest geometry.
    bell, hull = chunks(LEVEL / 'bell.iff'), chunks(LEVEL / 'player_hull.iff')
    for tag in [b'VRTX', b'FACE']:
        assert bell[tag] == hull[tag]


def test_all_six_jellies_share_the_translucent_models():
    mapping = json.loads((LEVEL / 'actor-map.json').read_text())
    assert mapping['count'] == 6
    assert mapping['parts'] == ['bell', 'arms']
    for k in range(6):
        for part in mapping['parts']:
            assert f'animal-{k:02d}-{part}' in mapping['indices']
    # Representative other animal tanks retain legacy opaque materials.
    for level in ['aquarium_betta', 'aquarium_lionfish']:
        for path in (ROOT / 'wflevels' / level).glob('*.iff'):
            if path.read_bytes()[:4] == b'MODL':
                assert b'OPAC' not in chunks(path)
