"""Compare the Fixed scene's cooked geometry and baked colours, before vs after W5b."""
import re, struct, sys, json
from collections import Counter
from pathlib import Path

def actors(level_dir, hero_cells):
    name = level_dir.name
    out = {}
    for block in (level_dir / f'{name}.lev').read_text().split("\t{ 'OBJ'")[1:]:
        n = re.search(r"\{ 'NAME' \"([^\"]+)\" \}", block).group(1)
        mesh = re.search(r'"Mesh Name" \} \{ \'STR\' "([^"]+)"', block)
        cls = re.search(r'"Class Name" \} \{ \'DATA\' "([^"]+)"', block).group(1)
        pos = re.search(r'"Position" \} \{ \'DATA\' (\S+)\(1\.15\.16\) (\S+)\(1\.15\.16\) (\S+)\(1\.15\.16\)', block)
        vm = re.search(r"\"Visibility Mailbox\" \} \{ 'DATA' (\d+)l", block); vis = int(vm.group(1)) if vm else 1
        if not mesh or cls == 'statplat' or mesh.group(1) == 'player_hull.iff' or not (vis == 1 or vis in hero_cells):
            continue
        out[n] = (mesh.group(1), tuple(float(pos.group(i)) for i in (1, 2, 3)))
    return out

def tris(path, pos):
    d = path.read_bytes(); ch = {}; p = 8
    while p + 8 <= len(d):
        t, s = struct.unpack_from('<4sI', d, p); ch.setdefault(t, d[p+8:p+8+s]); p += 8 + ((s+3) & ~3)
    v = [struct.unpack_from('<iiIiii', ch[b'VRTX'], i) for i in range(0, len(ch[b'VRTX']), 24)]
    out = []
    for i in range(0, len(ch[b'FACE']), 8):
        a = struct.unpack_from('<hhh', ch[b'FACE'], i)
        out.append(tuple(sorted((round(v[k][3]/65536+pos[0], 3), round(v[k][4]/65536+pos[1], 3), round(v[k][5]/65536+pos[2], 3),
                                 round(v[k][0]/65536, 3), round(v[k][1]/65536, 3)) for k in a)))
    cols = [v[k][2] & 255 for k in range(len(v))]
    return out, cols

for style in sys.argv[1:]:
    before, after = Path(f'/src/build-docker/w5b/before/{style}'), Path(f'/src/wflevels/{style}')
    am = json.loads((after / 'actor-map.json').read_text())
    cells = {m['cell'] for m in am['kit']['modules'] if m['role'] == 'hero'}
    A, B = Counter(), Counter(); ca, cb = [], []
    for n, (m, p) in actors(before, set()).items():
        t, c = tris(before / m, p); B.update(t); cb += c
    for n, (m, p) in actors(after, cells).items():
        t, c = tris(after / m, p); A.update(t); ca += c
    print(style, 'triangles before', sum(B.values()), 'after', sum(A.values()),
          'identical (pos+uv, 1 mm)' if A == B else f'DIFFER: {sum((A-B).values())} only-after, {sum((B-A).values())} only-before')
    import statistics as S
    print('  baked grey level mean/median before', round(S.mean(cb), 2), S.median(cb), 'after', round(S.mean(ca), 2), S.median(ca))

# Tolerance check: every after-triangle has a before-triangle within 1e-4 (positions) / 1e-4 (UV).
import math
def verts_of(level_dir, hero_cells):
    out = []
    for n, (m, p) in actors(level_dir, hero_cells).items():
        d = (level_dir / m).read_bytes(); ch = {}; q = 8
        while q + 8 <= len(d):
            t, s = struct.unpack_from('<4sI', d, q); ch.setdefault(t, d[q+8:q+8+s]); q += 8 + ((s+3) & ~3)
        for i in range(0, len(ch[b'VRTX']), 24):
            u, v, c, x, y, z = struct.unpack_from('<iiIiii', ch[b'VRTX'], i)
            out.append((x/65536+p[0], y/65536+p[1], z/65536+p[2], u/65536, v/65536, c))
    return out
for style in sys.argv[1:]:
    before, after = Path(f'/src/build-docker/w5b/before/{style}'), Path(f'/src/wflevels/{style}')
    am = json.loads((after / 'actor-map.json').read_text())
    cells = {m['cell'] for m in am['kit']['modules'] if m['role'] == 'hero'}
    B = verts_of(before, set()); A = verts_of(after, cells)
    grid = {}
    for b in B: grid.setdefault(tuple(int(math.floor(c / .01)) for c in b[:3]), []).append(b)
    worst_p = worst_uv = 0.0; colour_diff = Counter()
    for a in A:
        cell = tuple(int(math.floor(c / .01)) for c in a[:3])
        best = min((q for dx in (-1,0,1) for dy in (-1,0,1) for dz in (-1,0,1)
                    for q in grid.get((cell[0]+dx, cell[1]+dy, cell[2]+dz), ())),
                   key=lambda q: math.dist(a[:3], q[:3]) + abs(a[3]-q[3]) + abs(a[4]-q[4]) + abs((a[5]&255)-(q[5]&255))/1e4)
        worst_p = max(worst_p, math.dist(a[:3], best[:3])); worst_uv = max(worst_uv, abs(a[3]-best[3]), abs(a[4]-best[4]))
        colour_diff[abs((a[5]&255)-(best[5]&255))] += 1
    print(style, 'vertices', len(B), len(A), 'max position offset', f'{worst_p:.6f}', 'max UV offset', f'{worst_uv:.6f}',
          'baked grey |diff| histogram', sorted(colour_diff.items())[:6], '...', 'max', max(colour_diff))
