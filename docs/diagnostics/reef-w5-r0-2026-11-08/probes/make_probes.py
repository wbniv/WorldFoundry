#!/usr/bin/env python3
"""R0 probe levels (reef plan W5, R0 section 7): copy today's reef level dirs, edit the .lev.

Usage: python3 build-docker/r0/make_probes.py
Writes build-docker/r0/<probe>/<style>/ for probes P0..P3 and both styles. Never touches wflevels/.
P0  unchanged copy (build-to-build noise)
P1  + 8 hidden kit modules (copies of reef_left/right/arch meshes, own visibility cells 200-207, value 0)
    + 8 module statplat colliders (copies of the rock colliders) parked at z-offset -4
P2  P1 + a one-shot Director layout on the first tick: rocks 10-12, colliders 21-22, and every kit
    module/collider moved once (X/Y/Z then rotation A, B, C)
P3  P1 + 40 hidden static clumps (one shared copy of reef_life_3.iff), visibility cells 208-247
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
STYLES = ('aquarium_thai_reef', 'aquarium_thai_reef_anime')
ROCKS = ('reef_left', 'reef_right', 'reef_arch')
COLLIDERS = ('rockcolliderleft', 'rockcolliderright')
GUARD = 1112        # free global user cell (original plan's allocation: 1112-1139 unassigned)
VIS_BASE = 200      # free global user cells 200-247 (no literal 100-399 except 256 in reef scripts)
FX = '(1.15.16)'


def blocks_of(text):
    head, *objs = text.split("\t{ 'OBJ'")
    return head, objs


def name_of(block):
    return re.search(r"\{ 'NAME' \"([^\"]+)\" \}", block).group(1)


def fx(v):
    return f'{v:.16f}{FX}'


def clone(block, name, mesh, vis, dz=0.0):
    b = block.replace(f'{{ \'NAME\' "{name_of(block)}" }}', f'{{ \'NAME\' "{name}" }}', 1)
    b = re.sub(r'(\{ \'FILE\' \{ \'NAME\' "Mesh Name" \} \{ \'STR\' ")[^"]+(" \} \})', rf'\g<1>{mesh}\g<2>', b)
    b = re.sub(r'(\{ \'I32\' \{ \'NAME\' "Visibility Mailbox" \} \{ \'DATA\' )\d+l \} \{ \'STR\' "\d+" \}',
               '\\g<1>' + f"{vis}l }} {{ 'STR' \"{vis}\" }}", b)
    if dz:
        def shift_pos(m):
            x, y, z = (float(v) for v in m.group(2, 3, 4))
            return f'{m.group(1)}{fx(x)} {fx(y)} {fx(z + dz)}  //x,y,z'
        b = re.sub(r"(\{ 'VEC3' \{ 'NAME' \"Position\" \} \{ 'DATA' )(-?[\d.]+)\(1\.15\.16\) (-?[\d.]+)\(1\.15\.16\) (-?[\d.]+)\(1\.15\.16\)  //x,y,z", shift_pos, b)
        def shift_box(m):
            v = [float(s) for s in re.findall(r'(-?[\d.]+)\(1\.15\.16\)', m.group(2))]
            v[2] += dz; v[5] += dz
            return m.group(1) + ' '.join(fx(x) for x in v) + '  //min(x,y,z)-max(x,y,z)'
        b = re.sub(r"(\{ 'BOX3' \{ 'NAME' \"Global Bounding Box\" \} \{ 'DATA' )(.*?)  //min\(x,y,z\)-max\(x,y,z\)", shift_box, b)
    assert name_of(b) == name and mesh in b
    return b


def place(actor, x, y, z, c=0.0):
    w = 'write-actor-mailbox'
    return (f' {x} INDEXOF_X_POS {actor} {w} {y} INDEXOF_Y_POS {actor} {w} {z} INDEXOF_Z_POS {actor} {w}'
            f' 0 INDEXOF_ROTATION_A {actor} {w} 0 INDEXOF_ROTATION_B {actor} {w} {c} INDEXOF_ROTATION_C {actor} {w}\n')


def build(probe, style):
    src = ROOT / 'wflevels' / style
    dst = OUT / probe / style
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', 'reef', '*.py', 'textile.log.htm',
                                                            'triangle-diagnostics.json'))
    lev = dst / f'{style}.lev'
    text = lev.read_text()
    head, objs = blocks_of(text)
    names = [name_of(b) for b in objs]
    index = {n: i + 1 for i, n in enumerate(names)}
    assert index['Director'] == 4 and index['reef_left'] == 10 and index['RockColliderLeft'] == 21, index
    assert len(objs) == 40, len(objs)
    if probe == 'P0':
        return dst
    # The file ends "\t}\n}\n": the last object's close, then the LVL close. Peel the LVL close.
    last = objs[-1]
    cut = last.rstrip().rfind('}')
    lvl_close = last[cut:]
    objs[-1] = last[:cut]
    new = []
    template_rock = objs[index['reef_left'] - 1]
    template_col = objs[index['RockColliderLeft'] - 1]
    for k in range(8):
        mesh = f'kitmod{k + 1}.iff'
        shutil.copyfile(dst / f'{ROCKS[k % 3]}.iff', dst / mesh)
        new.append(clone(objs[index[('reef_left', 'reef_right', 'reef_arch')[k % 3]] - 1],
                         f'KitModule{k + 1}', mesh, VIS_BASE + k))
    for k in range(8):
        mesh = f'kitcol{k + 1}.iff'
        shutil.copyfile(dst / f'{COLLIDERS[k % 2]}.iff', dst / mesh)
        new.append(clone(objs[index[('RockColliderLeft', 'RockColliderRight')[k % 2]] - 1],
                         f'KitCollider{k + 1}', mesh, 0, dz=-4.0))
    if probe == 'P3':
        shutil.copyfile(dst / 'reef_life_3.iff', dst / 'kitclump.iff')
        for k in range(40):
            new.append(clone(objs[index['reef_life_3'] - 1], f'KitClump{k + 1}', 'kitclump.iff', VIS_BASE + 8 + k))
    first_new = len(objs) + 1
    if probe == 'P2':
        modules = range(first_new, first_new + 8)
        colliders = range(first_new + 8, first_new + 16)
        body = ''
        for actor in (index['reef_left'], index['reef_right'], index['reef_arch']):
            body += place(actor, .2, 0, 0)
        for actor in (index['RockColliderLeft'], index['RockColliderRight']):
            body += place(actor, .2, 0, 0)
        for k, actor in enumerate(modules):
            body += place(actor, round(-4 + k * 1.1, 3), 0, 0, round(.1 * k, 3))
        for k, actor in enumerate(colliders):
            body += place(actor, round(-4 + k * 1.1, 3), 0, -4)
        once = f': r0-once {GUARD} tk@ 0 = if\n{body} 1 {GUARD} tk! then ;\n'
        director = objs[index['Director'] - 1]
        needle = '\\nreef-tick\\n" } }'
        assert director.count(needle) == 1, director[-200:]
        director = director.replace(needle, '\\n' + once.replace('\n', '\\n') + 'r0-once\\nreef-tick\\n" } }')
        objs[index['Director'] - 1] = director
    text = head + "\t{ 'OBJ'".join([''] + objs) + ''.join("\t{ 'OBJ'" + b for b in new) + lvl_close
    lev.write_text(text)
    check = [name_of(b) for b in blocks_of(text)[1]]
    assert check[:40] == names and len(check) == 40 + len(new), (len(check), len(new))
    return dst


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__); raise SystemExit(0)
    for probe in ('P0', 'P1', 'P2', 'P3'):
        for style in STYLES:
            print(probe, style, build(probe, style))
