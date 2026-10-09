"""Authored level memory settings and a legacy RAM compatibility projection.

These controls are read-only after level load; they never resize live allocators.
"""
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
INT_MAX = 2147483647
MAX_ROOM_SLOTS = 9
FIELDS = [
    (2000, 'object_heap_bytes', 'Object heap bytes', 1, INT_MAX),
    (2001, 'permanent_asset_bytes', 'Permanent asset bytes', 1, INT_MAX),
    (2002, 'room_asset_bytes', 'Room asset bytes per slot', 1, INT_MAX),
    (2003, 'active_room_slots', 'Active room asset slots', 1, MAX_ROOM_SLOTS),
    (2004, 'doom_stick', 'Doom-style joystick', 0, 1),
    (2005, 'bungee_camera', 'Bungee camera', 0, 1),
]

def validate(config):
    expected = {'version', *(f[1] for f in FIELDS)}
    if set(config) != expected or type(config['version']) is not int or config['version'] != 1:
        raise ValueError('Unsupported or incomplete level memory configuration')
    for _, key, _, minimum, maximum in FIELDS:
        value = config[key]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError('Invalid level memory setting: ' + key)
    assets = config['permanent_asset_bytes'] + config['active_room_slots'] * config['room_asset_bytes']
    if assets > INT_MAX:
        raise ValueError('Level asset allocation exceeds signed allocator capacity')
    return config

def load(path=None):
    return validate(json.loads(Path(path or HERE/'memory-settings.json').read_text()))

def sheet(config=None):
    config = validate(config) if config is not None else load()
    lines = ['PROPERTY_SHEET_HEADER(Level Memory,0)', 'GROUP_START(Load-time configuration)']
    bindings = {}
    for field, key, label, minimum, maximum in FIELDS:
        initial = config[key]
        key = 'memory_' + key
        help_text = 'Applied at level load. Read-only now; rebuild/reload to change.'
        if field == 2003:
            help_text += ' Asset residency slots; independent of render policy.'
        quote = json.dumps
        lines.append('{' + ','.join(['4', quote(key), str(minimum), str(maximum), str(initial), '0', '""', '8' if maximum == 1 else '2', '-1', '-1', quote(help_text), '{0,0,'+quote(label)+',"1"}']) + '},')
        bindings[key] = dict(id=field, readonly=True, initial=str(initial))
    return lines + ['GROUP_STOP()', 'PROPERTY_SHEET_FOOTER'], bindings

def project_legacy(level, config=None):
    """Write canonical values into the original RAM fields for older engines.

No sector, level payload or catalog offset moves. SLOT is inserted into RAM's
alignment padding when absent. Unknown RAM extensions remain byte-identical.
"""
    config = validate(config) if config is not None else load()
    data = bytearray(level)
    if len(data) < 4096 or data[2048:2052] != b'RAM\0':
        raise ValueError('Expected standalone level RAM at sector one')
    size = struct.unpack_from('<I', data, 2052)[0]
    end = 2056 + size
    if size < 36 or end + 8 > 4096 or data[end:end+4] != b'ALGN':
        raise ValueError('Malformed RAM or missing alignment padding')
    padding = struct.unpack_from('<I', data, end+4)[0]
    if end + 8 + padding != 4096:
        raise ValueError('RAM padding does not terminate at next sector')
    payload = bytearray(data[2056:end])
    if any(payload[offset:offset+4] != tag for offset, tag in [(0,b'OBJD'),(8,b'PERM'),(16,b'ROOM'),(24,b'FLAG')]):
        raise ValueError('Unsupported legacy RAM layout')
    for offset, key in [(4,'object_heap_bytes'), (12,'permanent_asset_bytes'), (20,'room_asset_bytes'), (28,'doom_stick'), (32,'bungee_camera')]:
        struct.pack_into('<I', payload, offset, config[key])
    if payload[36:40] == b'SLOT':
        if len(payload) < 44: raise ValueError('Truncated legacy SLOT')
        struct.pack_into('<I', payload, 40, config['active_room_slots'])
    else:
        if padding < 8: raise ValueError('Insufficient RAM alignment padding')
        payload[36:36] = b'SLOT' + struct.pack('<I', config['active_room_slots'])
        padding -= 8
    sector = b'RAM\0' + struct.pack('<I', len(payload)) + payload + b'ALGN' + struct.pack('<I', padding) + bytes(padding)
    assert len(sector) == 2048
    data[2048:4096] = sector
    return bytes(data)
