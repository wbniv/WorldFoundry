"""Author the standalone lava-lamp clock in Blender."""
import json
import math
import subprocess
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(ROOT / 'wftools'), str(ROOT / 'wflevels/clock_common'), str(HERE)]
import wf_blender
import wf_core
from wf_blender.export_level import _seed_defaults
from clock_mesh import Mesh
import model

OAS = ROOT / 'wfsource/source/oas'
SCALE = 48.0  # Keeps small metaball triangles above the fixed-point normal threshold.
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()

COLORS = {'wax': (1., .235, .025), 'waxlight': (1., .52, .075),
          'wax_highlight': (1., .48, .09), 'wax_shade': (.72, .11, .012),
          'dark': (.05, .047, .075), 'metal': (.16, .17, .21),
          'edge': (.37, .36, .42), 'glass': (.30, .20, .36),
          'liquid': (.105, .035, .13), 'glow': (1., .39, .06),
          'glowdark': (.45, .11, .035), 'black': (.018, .014, .025)}
materials = {}
for key, rgb in COLORS.items():
    mat = bpy.data.materials.new(key)
    mat.use_nodes = True
    mat.diffuse_color = (*rgb, 1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*rgb, 1)
    mat['wf_prelit'] = not key.startswith('wax')
    mat['wf_double_sided'] = True
    materials[key] = mat


def actor(name, cls, mesh=None, pos=(0, 0, 0), fields=None, bounds=None):
    data = None
    if mesh is not None:
        data = bpy.data.meshes.new(name)
        data.from_pydata(mesh.vertices, [], mesh.faces)
        keys = list(dict.fromkeys(mesh.colors))
        for key in keys:
            data.materials.append(materials[key])
        for poly, key in zip(data.polygons, mesh.colors):
            poly.material_index = keys.index(key)
        data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema = OAS / (cls + '.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj, wf_core.load_schema(str(schema)))
    values = {'Mobility': 'Anchored', 'Mass': 0., 'Model Type': 'Mesh' if data else 'None',
              'Visibility Mailbox': 1 if data else 0, 'Script': '', 'Script Controls Input': 'False',
              'Moves Between Rooms': 'False', 'Number Of Local Mailboxes': 0}
    values.update(fields or {})
    for key, value in values.items():
        obj['wf_' + key] = value
    if data:
        obj['wf_Mesh Name'] = name + '.iff'
        obj['wf_original_mesh_name'] = name + '.iff'
    if bounds or not data:
        obj['wf_original_bbox'] = tuple(bounds or (-.05, -.05, -.05, .05, .05, .05))
        obj['wf_had_authored_bbox'] = True
    return obj


# Segments are smooth unions of overlapping metaballs. The four complete
# numbers use one union each; separate matching strokes animate the transition.
SEGMENT_LINES = {
    'a': ((-.42, .72), (.42, .72)), 'b': ((.42, .72), (.42, 0)),
    'c': ((.42, 0), (.42, -.72)), 'd': ((-.42, -.72), (.42, -.72)),
    'e': ((-.42, -.72), (-.42, 0)), 'f': ((-.42, 0), (-.42, .72)),
    'g': ((-.42, 0), (.42, 0)),
}


def molten(segments):
    data = bpy.data.metaballs.new('wax_field')
    data.resolution = .105
    data.render_resolution = .09
    obj = bpy.data.objects.new('wax_field', data)
    bpy.context.scene.collection.objects.link(obj)
    for seg in segments:
        (x0, z0), (x1, z1) = SEGMENT_LINES[seg]
        for i in range(7):
            t = i / 6
            el = data.elements.new()
            wobble = .055 * math.sin(math.pi*t) * math.sin(i*2.1+ord(seg))
            el.co = (x0 + (x1-x0)*t + (wobble if x0==x1 else 0), 0,
                     z0 + (z1-z0)*t + (wobble if z0==z1 else 0))
            el.radius = .28 + .07 * math.sin((i + ord(seg)) * 1.7)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.view_layer.objects.active
    out = Mesh('wax')
    out.vertices = [tuple(v.co) for v in obj.data.vertices]
    out.faces = [tuple(p.vertices) for p in obj.data.polygons]
    out.colors = [('wax_highlight' if p.normal.z > .55 and p.normal.y < -.20 else
                   'wax_shade' if p.normal.z < -.60 else 'wax') for p in obj.data.polygons]
    bpy.data.objects.remove(obj, do_unlink=True)
    return out


actor('Level', 'levelobj')
actor('Room', 'room', bounds=(-50, -50, -25, 50, 50, 40))
director = actor('Director', 'director')
actor('Player', 'player', pos=(0, 15, 0))
actor('Camera', 'camera', pos=(0, -8.5, 4.6), fields={'Mobility':'Camera', 'Moves Between Rooms':'True', 'FoggingStartDistance':900., 'FoggingCompleteDistance':1000.})
actor('LookAt', 'target', pos=(0, 0, 2.35))
actor('cs_wide', 'camshot', pos=(0, -8.5, 4.6), fields={'Follow':'LookAt', 'Target':'LookAt', 'Track Object':'LookAt', 'Rotation':'Fixed', 'Position X':'Absolute', 'Position Y':'Absolute', 'Position Z':'Absolute', 'Hither':1., 'Yon':200., 'FOV':50., 'Pan Time In Seconds':0.})
actor('Ambient', 'light', fields={'lightType':'Ambient', 'lightRed':.50, 'lightGreen':.50, 'lightBlue':.50})
sun = actor('Sun', 'light', fields={'lightType':'Directional', 'lightRed':1., 'lightGreen':.8, 'lightBlue':.6})
sun.rotation_euler = (0, math.radians(40), math.radians(90))
actor('Background', 'matte', fields={'Matte Type':'Color', 'Background Color':0x080710})
actor('LavaLampDigitsSettings', 'lavalampdigitssettings', fields={'Editor Label':'Lava-lamp digits'})

tank = Mesh('tank')
tank.box((-5.8,-.72,-.2), (5.8,.72,.25), 'metal')
tank.box((-5.8,-.72,4.65), (5.8,.72,5.0), 'metal')
tank.box((-5.72,-.735,.09), (5.72,-.725,.14), 'edge')
tank.box((-5.72,-.735,4.90), (5.72,-.725,4.94), 'edge')
tank.box((-5.55,.48,.25), (5.55,.56,4.65), 'liquid')
for x in (-5.56,5.46):
    tank.box((x,-.6,.25), (x+.1,.6,4.65), 'glass')
    tank.box((x,-.65,.25), (x+.045,-.6,4.65), 'edge')
tank.box((-5.45,-.64,.27), (5.45,-.60,.34), 'glow')
tank.box((-5.48,-.65,.18), (5.48,-.62,.24), 'glowdark')
tank.box((-5.6,-.66,4.57), (5.6,-.63,4.62), 'edge')
actor('Tank', 'platform', tank)

digit_mesh = [molten(model.DIGITS[n]) for n in range(10)]
segment_mesh = {s: molten(s) for s in model.SEGMENTS}
xs = (-3.75, -1.6, 1.6, 3.75)
for place, x in enumerate(xs):
    for n in range(10):
        actor(f'Digit{place}_{n}', 'platform', digit_mesh[n], pos=(x, -.20, 3.25),
              fields={'Visibility Mailbox':800+place*10+n})
    for seg in model.SEGMENTS:
        actor(f'Segment{place}_{seg}', 'platform', segment_mesh[seg], pos=(x, -.20, 3.25),
              fields={'Visibility Mailbox':840+place*7+model.SEGMENTS.index(seg)})
colon = Mesh('colon')
for z in (2.95, 3.65):
    colon.sphere((0,-.2,z), .19, 'wax', segments=14, rings=8)
actor('Colon', 'platform', colon)

for i in range(16):
    blob = Mesh('blob')
    blob.sphere((0,0,0), .15 + (i%4)*.045, 'waxlight' if i%3==0 else 'wax', segments=14, rings=8)
    x = -4.9 + (i*1.37)%9.8
    actor(f'Blob{i}', 'platform', blob, pos=(x, .08, .5), fields={'Visibility Mailbox':1})

bpy.context.view_layer.update()
objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx = {o.name:i+1 for i,o in enumerate(objects)}
catalog = json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'), str(OAS/'lavalampdigitssettings.oad')], text=True))
drift = {f['key']:f for f in catalog['fields']}['Camera drift']['index']
lines = [r'\ Local 24-hour reading; wax strokes fall apart and rise again.',
    ': ll-frac begin dup 1 >= if 1 - 0 else 1 then until ;',
    ': ll-floor dup ll-frac - ;',
    ': ll-digit0 INDEXOF_WALL_HOUR read-mailbox 10 / ll-floor ;',
    ': ll-digit1 INDEXOF_WALL_HOUR read-mailbox 10 mod ;',
    ': ll-digit2 INDEXOF_WALL_MINUTE read-mailbox 10 / ll-floor ;',
    ': ll-digit3 INDEXOF_WALL_MINUTE read-mailbox 10 mod ;',
    ': ll-hold INDEXOF_WALL_SECOND read-mailbox 6 >= INDEXOF_WALL_SECOND read-mailbox 54 < & ;',
    ': ll-linear INDEXOF_WALL_SECOND read-mailbox dup 6 < if 6 / else 60 swap - 6 / then ;',
    ': ll-rise ll-linear dup dup 2 * 3 swap - * * ;',
    ': ll-tick']
for place, x in enumerate(xs):
    for n in range(10):
        lines += [f' ll-digit{place} {n} = ll-hold & dup {800+place*10+n} write-mailbox if',
                  f' INDEXOF_WALL_SECOND read-mailbox 9 / .06 {idx[f"Digit{place}_{n}"]} fish-deform then']
    for j, seg in enumerate(model.SEGMENTS):
        values = [n for n in range(10) if seg in model.DIGITS[n]]
        expression = ' '.join(f'll-digit{place} {n} =' + (' |' if k else '') for k,n in enumerate(values))
        name = f'Segment{place}_{seg}'
        lines += [f' {expression} ll-hold 0 = & dup {840+place*7+j} write-mailbox if',
                  f' {x:.3f} 1 ll-rise - {(j-3)*.22:.3f} * + {SCALE:g} * INDEXOF_X_POS {idx[name]} write-actor-mailbox',
                  f' 3.25 1 ll-rise - {2.55+j*.10:.3f} * - {SCALE:g} * INDEXOF_Z_POS {idx[name]} write-actor-mailbox',
                  f' 1 ll-rise - {(j-3)*.032:.3f} * INDEXOF_ROTATION_B {idx[name]} write-actor-mailbox',
                  f' INDEXOF_WALL_SECOND read-mailbox 9 / .06 {idx[name]} fish-deform then']
for i in range(16):
    name = f'Blob{i}'
    lines += [f' INDEXOF_WALL_SECOND read-mailbox 20 / {i*.137:.4f} + dup ll-floor - 1.65 * .48 + {SCALE:g} * INDEXOF_Z_POS {idx[name]} write-actor-mailbox',
              f' INDEXOF_WALL_SECOND read-mailbox 7 / {i*.13:.3f} + .08 {idx[name]} fish-deform']
lines += [f' {idx["LavaLampDigitsSettings"]} {drift} property@ if 0 <> else drop 0 then if',
          f' 0 INDEXOF_X_POS {idx["cs_wide"]} write-actor-mailbox',
          f' {4.6*SCALE:g} INDEXOF_Z_POS {idx["cs_wide"]} write-actor-mailbox',
          ' else',
          f' INDEXOF_WALL_SECOND read-mailbox 60 / sin-rev {.6*SCALE:g} * INDEXOF_X_POS {idx["cs_wide"]} write-actor-mailbox',
          f' INDEXOF_WALL_SECOND read-mailbox 60 / cos-rev {.20*SCALE:g} * {4.4*SCALE:g} + INDEXOF_Z_POS {idx["cs_wide"]} write-actor-mailbox',
          ' then', ';', 'll-tick']
director['wf_Script'] = '\n'.join(lines)
# Scaling vertices and origins together preserves the intended composition.
for obj in objects:
    obj.location *= SCALE
    if obj.type == 'MESH':
        for vertex in obj.data.vertices:
            vertex.co *= SCALE
    if obj.get('wf_had_authored_bbox'):
        obj['wf_original_bbox'] = tuple(v*SCALE for v in obj['wf_original_bbox'])
    if obj.name == 'cs_wide':
        obj['wf_Hither'] = 24.
        obj['wf_Yon'] = 1000.
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx}, indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'lava_lamp_digits.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'lava_lamp_digits.lev'))
