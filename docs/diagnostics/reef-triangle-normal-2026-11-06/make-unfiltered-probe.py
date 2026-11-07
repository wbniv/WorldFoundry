"""Create a scratch-only generator that counts and retains small triangles."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
scratch = Path('/tmp/reef-unfiltered-probe')
scratch.mkdir(exist_ok=True)
snapshot = scratch / 'source'
snapshot.mkdir(exist_ok=True)
paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '2652fdfa',
    'wflevels/aquarium_thai_reef/reef', 'wflevels/aquarium_thai_reef/config.py'],
    cwd=root, text=True).splitlines()
for path in paths:
    if not path.endswith('.py'):
        continue
    relative = Path(path).relative_to('wflevels/aquarium_thai_reef')
    dest = snapshot / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(subprocess.check_output(['git', 'show', '2652fdfa:' + path], cwd=root))
text = subprocess.check_output(['git', 'show',
    '2652fdfa:wflevels/aquarium_thai_reef/generate.py'], cwd=root, text=True)
old_here = 'HERE = Path(__file__).resolve().parent'
old_message = "print(f'{obj.name}: removing {len(tiny)} undersized triangles')"
old_delete = "bmesh.ops.delete(bm, geom=tiny, context='FACES')"
assert all(text.count(s) == 1 for s in (old_here, old_message, old_delete))
text = text.replace(old_here, f'HERE = Path({str(snapshot)!r})')
text = text.replace(old_message, "print(f'{obj.name}: retaining {len(tiny)} undersized triangles; "
                    "exactly-zero={sum(f.calc_area() == 0 for f in tiny)}')")
text = text.replace(old_delete, 'pass  # scratch diagnostic: retain all faces')
(scratch / 'generate.py').write_text(text)
print(scratch / 'generate.py')
