#!/usr/bin/env python3
"""Run the exported reef Director in the species zForth VM and dump the layouts it computes.

Usage (linux-test container, repo at /src): python3 layout-dump.py LEVEL_DIR OUT.json CASE [CASE ...]
CASE = name:layout,rocks,colonies,seed   e.g. rocks3-seed7:1,3,1,7   fixed:0,3,1,0
Writes {case: {"actors": {index: [x, y, z, a, b, c]}, "cells": {cell: value}}} after two ticks.
render-layout.py places the cooked meshes from this file.
"""
import ast, json, re, subprocess, sys, tempfile
from pathlib import Path

if len(sys.argv) < 4 or sys.argv[1] in ('-h', '--help'):
    print(__doc__); raise SystemExit(0)
ROOT = Path(__file__).resolve().parents[3]
level = Path(sys.argv[1]); out = Path(sys.argv[2])
src = (ROOT / 'engine/stubs/scripting_zforth.cc').read_text()
core = re.sub(r'//[^\n]*', '', src[src.index('static const char* kCoreBootstrap ='):src.index('void Init(')])
d = ''.join(ast.literal_eval(x) for x in re.findall(r'"(?:\\.|[^"\\])*"', core))
mailbox = (ROOT / 'wfsource/source/mailbox/mailbox.inc').read_text()
d += '\n' + ''.join(f': INDEXOF_{k} {v} ;\n' for k, v in re.findall(r'MAILBOXENTRY\(\s*(\w+)\s*,\s*(\d+)', mailbox))
d += ''.join(f': JOYSTICK_BUTTON_{k} {1 << i} ;\n' for i, k in enumerate('ABCDEFGHIJK'))
d += ''.join(f': JOYSTICK_BUTTON_{k} {1 << i} ;\n' for i, k in enumerate(('UP', 'DOWN', 'RIGHT', 'LEFT'), 11))
d += (": read-mailbox 128 sys ; : write-mailbox 129 sys ; : write-actor-mailbox 130 sys ; : read-actor-mailbox 152 sys ;"
      " : random 153 sys ; : seed-random 154 sys ; : r@ ' lit , 0 , ' pickr , ; immediate\n")
d += re.search(r'zf_eval\(&g_ctx, "(: profile-begin [^"]*)"\)', src).group(1) + '\n'
tmp = Path(tempfile.mkdtemp())
vendor = ROOT / 'engine/vendor/zforth-41db72d1/src/zforth'
subprocess.run(['cc', '-O1', '-I' + str(ROOT / 'engine/stubs'), '-I' + str(vendor), str(ROOT / 'tests/species_vm.c'),
                str(vendor / 'zforth.c'), '-lm', '-o', str(tmp / 'vm')], check=True)
amap = json.loads((level / 'actor-map.json').read_text())
text = (level / f'{level.name}.lev').read_text()
paths = []
for name, entry in (('Player', 'tk-player-tick'), ('Director', 'reef-tick')):
    block = text[text.index('{ \'NAME\' "' + name + '" }'):].split("{ 'OBJ'", 1)[0]
    script = json.loads(re.search(r'\{ \'STR\' \{ \'NAME\' "Script" \} \{ \'STR\' ("(?:\\.|[^"\\])*")', block).group(1))
    (tmp / f'{name}.fth').write_text(d + script.removesuffix('\n' + entry + '\n'))
    paths.append(tmp / f'{name}.fth')
director, player = amap['indices']['Director'], amap['indices']['Player']
spawn = amap['anchors']['boxfish_spawn']
result = {}
for case in sys.argv[3:]:
    name, values = case.split(':')
    layout, rocks, colonies, seed = values.split(',')
    trace = f'reset {spawn[0]} {spawn[1]} {spawn[2]}\n'
    trace += ''.join(f'prop {director} {f} {v}\n' for f, v in ((1, layout), (2, rocks), (3, colonies), (4, seed)))
    trace += f'step 2 0 .0166667\ndumpa 1 {len(amap["indices"]) + 1}\ndumpg 0 1100\n'
    r = subprocess.run([str(tmp / 'vm'), *map(str, paths), str(player), str(director), 'tk-player-tick', 'reef-tick'],
                       input=trace, text=True, capture_output=True, check=True)
    actors, cells = {}, {}
    for line in r.stdout.splitlines():
        f = line.split()
        if line.startswith('A '):
            actors[f[1]] = [float(v) for v in f[2:8]]
        elif line.startswith('G '):
            cells = {str(int(f[1]) + i): float(v) for i, v in enumerate(f[2:])}
    result[name] = {'actors': actors, 'cells': cells}
out.write_text(json.dumps(result))
print('wrote', out, list(result))
