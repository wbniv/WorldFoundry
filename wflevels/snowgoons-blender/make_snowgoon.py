#!/usr/bin/env python3
"""Add one original Snowgoons snowman to the classic yard; retain the shared source model."""
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
from add_ambient_light import _split_objects
from audit_face_hand import chunks
from relight_level import _fx


def model():
    data = bytearray((HERE / "snowman01.iff").read_bytes())
    _, _, start, end = next(c for c in chunks(data, 8, len(data)) if c[0] == b"VRTX")
    points = [struct.unpack_from("<iii", data, i+12) for i in range(start,end,24)]
    lo = [min(p[j] for p in points) for j in range(3)]
    hi = [max(p[j] for p in points) for j in range(3)]
    offset = [(lo[0]+hi[0])//2, (lo[1]+hi[1])//2, lo[2]]
    shifted = [tuple(p[j]-offset[j] for j in range(3)) for p in points]
    for i, point in zip(range(start,end,24), shifted):
        struct.pack_into("<iii", data, i+12, *point)
    bounds = tuple(op(p[j] for p in shifted)/65536 for op in [min,max] for j in range(3))
    return bytes(data), bounds


def actor(bounds):
    def vector(tag, name, values):
        return f'    {{ \'{tag}\' {{ \'NAME\' "{name}" }} {{ \'DATA\' ' + ' '.join(_fx(v) for v in values) + ' } }\n'

    return ('''  { 'OBJ'
    { 'NAME' "Snowgoon" }
'''+vector('VEC3','Position',(5,-3,-0.60))
        +vector('EULR','Orientation',(0,0,0))
        +vector('BOX3','Global Bounding Box',bounds)+'''    { 'STR' { 'NAME' "Class Name" } { 'DATA' "enemy" } }
    { 'I32' { 'NAME' "MovementClass" } { 'DATA' 6l } }
    { 'I32' { 'NAME' "Mobility" } { 'DATA' 1l } { 'STR' "Physics" } }
    { 'I32' { 'NAME' "Moves Between Rooms" } { 'DATA' 1l } }
    { 'I32' { 'NAME' "Model Type" } { 'DATA' 1l } { 'STR' "Mesh" } }
    { 'FILE' { 'NAME' "Mesh Name" } { 'STR' "snowgoon.iff" } }
    { 'FX32' { 'NAME' "hp" } { 'DATA' 100.0(1.15.16) } }
    { 'FX32' { 'NAME' "Running Acceleration" } { 'DATA' 0.0(1.15.16) } }
    { 'FX32' { 'NAME' "Max Ground Speed" } { 'DATA' 0.0(1.15.16) } }
    { 'FX32' { 'NAME' "Falling Acceleration" } { 'DATA' 9.81(1.15.16) } }
  }
''')


def patch_level(text, bounds):
    lines = text.splitlines(keepends=True)
    replacement = actor(bounds)
    for start,end in _split_objects(text):
        block = ''.join(lines[start:end])
        if re.search(r"'NAME'\s+\"Snowgoon\"", block):
            lines[start:end] = replacement.splitlines(keepends=True)
            return ''.join(lines)
    closing = text.rfind('}')
    return text[:closing] + replacement + text[closing:]


def main():
    data,bounds = model()
    (HERE/'snowgoon.iff').write_bytes(data)
    path = HERE/'snowgoons.lev'
    path.write_text(patch_level(path.read_text(),bounds))
    print(f'Snowgoon: original snowman mesh, {bounds[5]:.2f} m tall, at (5, -3, -0.60)')


if __name__ == '__main__':
    main()
