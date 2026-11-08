"""Visible actors, faces and material runs in the Fixed scene: P0 (before W5b) vs K0 (W5b)."""
import json, re, struct, sys
from pathlib import Path
def runs(path):
    d = path.read_bytes(); ch = {}; p = 8
    while p + 8 <= len(d):
        t, s = struct.unpack_from('<4sI', d, p); ch.setdefault(t, d[p+8:p+8+s]); p += 8 + ((s+3) & ~3)
    mats = [struct.unpack_from('<h', ch[b'FACE'], i + 6)[0] for i in range(0, len(ch[b'FACE']), 8)]
    return len(mats), len(set(mats)), len(ch[b'VRTX']) // 24
for d, hero in ((Path('/src/build-docker/w5b/before') / sys.argv[1], False), (Path('/src/wflevels') / sys.argv[1], True)):
    am = json.loads((d / 'actor-map.json').read_text())
    cells = {m['cell'] for m in am.get('kit', {}).get('modules', []) if m['role'] == 'hero'}
    order, F, R, V = [], 0, 0, 0
    for block in (d / f'{d.name}.lev').read_text().split("\t{ 'OBJ'")[1:]:
        n = re.search(r"\{ 'NAME' \"([^\"]+)\" \}", block).group(1)
        mesh = re.search(r'"Mesh Name" \} \{ \'STR\' "([^"]+)"', block)
        cls = re.search(r'"Class Name" \} \{ \'DATA\' "([^"]+)"', block).group(1)
        vm = re.search(r"\"Visibility Mailbox\" \} \{ 'DATA' (\d+)l", block); vis = int(vm.group(1)) if vm else 1
        if not mesh or cls == 'statplat' or mesh.group(1) == 'player_hull.iff' or not (vis == 1 or vis in cells):
            continue
        f, r, v = runs(d / mesh.group(1)); F += f; R += r; V += v; order.append(n)
    print(d.parent.name, 'visible mesh actors', len(order), 'faces', F, 'material runs', R, 'vertices', V)
    print('   draw order:', ' '.join(order[:14]))
