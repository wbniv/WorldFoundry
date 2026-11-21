#!/usr/bin/env python3
"""Build the Cuckoo Village level, Classic mode (plan docs/plans/2026-11-21-cuckoo-village.md).

The art is the layout prototype's, unchanged: this script runs wflevels/cuckoo_village_layout/generate.py up to its
review-render section (hillside terrain, lanes, cottages, the carved glockenspiel tower with four pivoted figures and
the bird), so a change to that art flows straight into this level. It then checks that the tower is where
timeline.py assumes, wires the actors, poses everything from timeline.py at the reference time, writes the director
script and exports. Run through build.sh, in the Blender container.

Writes cuckoo_village.lev and actor-map.json.
"""
import json
import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LAYOUT = ROOT / 'wflevels/cuckoo_village_layout'
sys.path.insert(0, str(HERE))
import forth                 # noqa: E402
import timeline as tl        # noqa: E402

TAG = '[cuckoo-village]'
REFERENCE = 10 * 3600 + 8 * 60 + 22.0       # the pose the level starts from: 10:08
GLOW_CELL0, BIRD_CELL = 200, 213

source = (LAYOUT / 'generate.py').read_text()
cut = source.index('scene=bpy.context.scene')       # everything after this is the layout's review render and export
scope = {'__file__': str(LAYOUT / 'generate.py'), '__name__': 'cuckoo_village_layout'}
exec(compile(source[:cut], str(LAYOUT / 'generate.py'), 'exec'), scope)

# The packer finds textures beside the level: bring in the layout's two (git-ignored copies, regenerated every build).
import shutil
for texture in ('village_atlas.tga', 'tower-carved-wood.tga'):
    shutil.copyfile(LAYOUT / texture, HERE / texture)

objs = bpy.data.objects
assert abs(scope['tower_z'] - tl.TZ) < 1e-3, f"tower height {scope['tower_z']} differs from timeline TZ {tl.TZ}"


def near(a, b, what, tol=1e-3):
    assert all(abs(x - y) <= tol for x, y in zip(a, b)), f'{what}: scene has {tuple(round(v, 4) for v in a)}, timeline assumes {tuple(round(v, 4) for v in b)}'


for i, name in enumerate(tl.FIG_NAMES):
    near(objs[name].location, (tl.FIG_X[i], tl.FIG_HOME_Y, tl.FIG_Z0), name)
near(objs[tl.BIRD_NAME].location, tl.BIRD_REST, tl.BIRD_NAME)
near(objs['hour_hand'].location, tl.DIAL, 'hour_hand')
assert [n for n in (f'cottage_light_{i + 1:02}' for i in range(tl.HOUSES)) if n not in objs] == [], 'cottage light actors changed'

# window glow: one visibility mailbox per cottage; the bird is shown only during the hourly calls
for i in range(tl.HOUSES):
    objs[f'cottage_light_{i + 1:02}']['wf_Visibility Mailbox'] = GLOW_CELL0 + i
objs[tl.BIRD_NAME]['wf_Visibility Mailbox'] = BIRD_CELL

poses = tl.all_poses(REFERENCE)
for name, p in poses.items():
    if name in ('cs_wide', 'LookAt'):
        continue
    o = objs[name]
    o.location = p[:3]
    o.rotation_euler = (p[3] * math.tau, p[4] * math.tau, p[5] * math.tau)
objs['LookAt'].location = poses['LookAt'][:3]
wide = objs['cs_wide']
wide.location = poses['cs_wide'][:3]
for axis in 'XYZ':
    wide['wf_Position ' + axis] = 'Absolute'
wide['wf_Rotation'] = 'Fixed'
for key in ('Follow', 'Target', 'Track Object'):
    wide['wf_' + key] = 'LookAt'
objs['Camera'].location = wide.location
objs['Matte']['wf_Matte Type'] = 'Color'
objs['Matte']['wf_Background Color'] = 0x0b1115
objs['Player'].location = (0, -3, 1)

# The user-controlled settings object: an empty carrying the CuckooVillageSettings schema (no model, no mass).
# The director reads each field with property@ using the settings actor's index and the catalog's field index.
import subprocess
settings = bpy.data.objects.new('CuckooVillageSettings', None)
bpy.context.scene.collection.objects.link(settings)
settings['wf_schema_path'] = str(ROOT / 'wfsource/source/oas/cuckoovillagesettings.oad')
settings['wf_Model Type'] = 'None'
settings['wf_Mass'] = 0.0
settings['wf_original_bbox'] = (-.1, -.1, -.1, .1, .1, .1)
settings['wf_had_authored_bbox'] = True
catalog = json.loads(subprocess.check_output([str(ROOT / 'wftools/wf_attr_edit/target/release/catalog'), settings['wf_schema_path']], text=True))
settings_fields = {f['key']: f['index'] for f in catalog['fields'] if f['width'] and f['key'] in tl.SETTINGS_DEFAULTS}
assert set(settings_fields) == set(tl.SETTINGS_DEFAULTS), settings_fields

scene = bpy.context.scene
objects = [o for o in scene.objects if o.get('wf_schema_path')]
indices = {o.name: i + 1 for i, o in enumerate(objects)}
for a, b in zip(tl.FIG_NAMES, tl.FIG_NAMES[1:]):
    assert indices[b] - indices[a] == 1, 'the four figures must be contiguous'
objs['Director']['wf_Script'] = forth.director_script(indices, settings_fields)
(HERE / 'actor-map.json').write_text(json.dumps(dict(indices=indices, reference=REFERENCE), indent=1) + '\n')
print(f'{TAG} {len(objects)} actors')
bpy.ops.wf.export_level(filepath=str(HERE / 'cuckoo_village.lev'))
print(f'{TAG} done')
