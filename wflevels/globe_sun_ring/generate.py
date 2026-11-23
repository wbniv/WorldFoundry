"""Build the standalone 3D globe clock with the existing level exporter."""
import json
import math
import subprocess
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(ROOT / 'wftools'), str(HERE)]
import wf_blender
import wf_core
from wf_blender.export_level import _seed_defaults
import model

OAS = ROOT / 'wfsource/source/oas'
bpy.ops.wm.read_factory_settings(use_empty=True)
wf_blender.register()


def actor(name, cls, data=None, pos=(0, 0, 0), fields=None, bounds=None):
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = pos
    schema = OAS / (cls + '.oad')
    obj['wf_schema_path'] = str(schema)
    _seed_defaults(obj, wf_core.load_schema(str(schema)))
    values = {'Mobility': 'Anchored', 'Mass': 0.0, 'Model Type': 'Mesh' if data else 'None',
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


def material(name, rgb, prelit=True):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*rgb, 1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*rgb, 1)
    mat['wf_prelit'] = prelit
    mat['wf_double_sided'] = True
    return mat


def mesh(name, vertices, faces, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.materials.append(mat)
    data.update()
    return data


def globe_mesh(mat):
    # Equirectangular image: longitude -180..180 left to right; north at the top.
    cols, rows, radius = 48, 24, 3.0
    vertices = []
    for j in range(rows + 1):
        lat = -math.pi/2 + math.pi*j/rows
        for i in range(cols + 1):
            lon = -math.pi + math.tau*i/cols
            vertices.append((radius*math.cos(lat)*math.cos(lon), radius*math.cos(lat)*math.sin(lon), radius*math.sin(lat)))
    faces = []
    for j in range(rows):
        for i in range(cols):
            a = j*(cols+1)+i
            faces.append((a, a+1, a+cols+2, a+cols+1))
    data = mesh('earth', vertices, faces, mat)
    uv = data.uv_layers.new(name='UVMap')
    for poly in data.polygons:
        for loop in poly.loop_indices:
            index = data.loops[loop].vertex_index
            uv.data[loop].uv = ((index % (cols+1))/cols, 1-(index // (cols+1))/rows)
    return data


def annulus(name, inner, outer, z, mat, n=96):
    vertices = []
    for i in range(n):
        theta = math.tau*i/n
        vertices.extend(((inner*math.cos(theta), inner*math.sin(theta), z),
                         (outer*math.cos(theta), outer*math.sin(theta), z)))
    return mesh(name, vertices, [(2*i, 2*((i+1)%n), 2*((i+1)%n)+1, 2*i+1) for i in range(n)], mat)


def strip_mesh(name, strips, mat):
    vertices, faces = [], []
    for strip in strips:
        start = len(vertices)
        vertices.extend(strip)
        faces.append(tuple(range(start, start+len(strip))))
    return mesh(name, vertices, faces, mat)


def surface(lat, lon, radius=3.045):
    lat, lon = math.radians(lat), math.radians(lon)
    return (radius*math.cos(lat)*math.cos(lon), radius*math.cos(lat)*math.sin(lon), radius*math.sin(lat))


def surface_patch(lat, lon, size=.36):
    return [surface(lat-size, lon-size), surface(lat-size, lon+size),
            surface(lat+size, lon+size), surface(lat+size, lon-size)]


def label_mesh(name, text, mat):
    curve = bpy.data.curves.new(name, 'FONT')
    curve.body = text
    curve.size = .34
    obj = bpy.data.objects.new(name + '-source', curve)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    data = obj.data.copy()
    for vertex in data.vertices:
        vertex.co = (vertex.co.x, 0, vertex.co.y)
    data.materials.clear()
    data.materials.append(mat)
    bpy.data.objects.remove(obj, do_unlink=True)
    return data


gold = material('brass', (.72, .46, .18))
ivory = material('ring-markings', (1.0, .87, .58))
red = material('home-pin', (1.0, .24, .12))
lights = material('city-lights', (1.0, .72, .24))
earth = material('earth-texture', (1, 1, 1), prelit=False)
tex = earth.node_tree.nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(str(HERE / 'blue-marble-nasa.png'))
# Textile consumes TGA textures. Preserve the original PNG as the source.
_ = len(tex.image.pixels)  # force Blender to load pixels before changing the path
tex.image.filepath_raw = str(HERE / 'blue-marble.tga')
tex.image.file_format = 'TARGA'
tex.image.save()
earth.node_tree.links.new(tex.outputs['Color'], earth.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])

actor('Level', 'levelobj')
actor('Room', 'room', bounds=(-40, -40, -30, 40, 40, 30))
director = actor('Director', 'director')
actor('Player', 'player', pos=(0, 12, 0))
actor('Camera', 'camera', pos=(0, -9.5, 7.6), fields={'Mobility': 'Camera', 'Moves Between Rooms': 'True',
      'FoggingStartDistance': 900., 'FoggingCompleteDistance': 1000.})
actor('LookAt', 'target', pos=(0, 0, 3))
actor('cs_wide', 'camshot', pos=(0, -9.5, 7.6), fields={'Follow': 'LookAt', 'Target': 'LookAt',
      'Track Object': 'LookAt', 'Rotation': 'Fixed', 'Position X': 'Absolute', 'Position Y': 'Absolute',
      'Position Z': 'Absolute', 'Hither': 1., 'Yon': 200., 'FOV': 50., 'Pan Time In Seconds': 0.})
sunlight = actor('SunLight', 'light', fields={'lightType': 'Directional', 'lightRed': .85, 'lightGreen': .85, 'lightBlue': .85})
sunlight.rotation_euler = (0, 0, math.pi)
actor('Ambient', 'light', fields={'lightType': 'Ambient', 'lightRed': .25, 'lightGreen': .25, 'lightBlue': .31})
actor('Background', 'matte', fields={'Matte Type': 'Color', 'Background Color': 0x101828})
actor('GlobeSunRingSettings', 'globesunringsettings', fields={'Editor Label': 'Globe Sun Ring'})
actor('Earth', 'platform', globe_mesh(earth), pos=(0, 0, 3))
actor('Ring', 'platform', annulus('ring', 3.75, 3.98, 0, gold), pos=(0, 0, 3))

# The fixed dial: 12 faces the sun at +X; ticks progress around the ring.
tick_strips = []
for i in range(24):
    theta = math.tau*(i-12)/24
    c, s = math.cos(theta), math.sin(theta)
    length = .30 if i % 6 == 0 else .16
    w = .024 if i % 6 == 0 else .012
    tick_strips.append([(r*c-w*s, r*s+w*c, .03) for r in (3.72-length, 3.72)] +
                       [(r*c+w*s, r*s-w*c, .03) for r in (3.72, 3.72-length)])
actor('RingTicks', 'platform', strip_mesh('ring-ticks', tick_strips, ivory), pos=(0, 0, 3))

# Seven-segment numerals are actual geometry on the ring, not a screen label.
digit_segments = ((-.40,.84,.40,1.0), (.32,.06,.48,.88), (.32,-.88,.48,-.06),
                  (-.40,-1.0,.40,-.84), (-.48,-.88,-.32,-.06),
                  (-.48,.06,-.32,.88), (-.40,-.08,.40,.08))
digit_masks = (63, 6, 91, 79, 102, 109, 125, 7, 127, 111)
number_strips = []
for hour in range(24):
    theta = math.tau*(hour-12)/24
    c, s = math.cos(theta), math.sin(theta)
    digits = str(hour)
    for digit_index, digit in enumerate(digits):
        for segment, (x0,y0,x1,y1) in enumerate(digit_segments):
            if not (digit_masks[int(digit)] & (1 << segment)):
                continue
            xoff = (digit_index - (len(digits)-1)/2) * .32
            poly = []
            for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):
                tangential, radial = x*.27 + xoff, 4.30 + y*.27
                poly.append((radial*c-tangential*s, radial*s+tangential*c, .05))
            number_strips.append(poly)
actor('RingNumbers', 'platform', strip_mesh('ring-numbers', number_strips, ivory), pos=(0, 0, 3))

sun_vertices = [(5.1, 0, .06)] + [(5.1 + .35*math.cos(math.tau*i/20), .35*math.sin(math.tau*i/20), .06) for i in range(20)]
actor('SunSymbol', 'platform', mesh('sun-symbol', sun_vertices,
      [(0, i+1, (i+1)%20+1) for i in range(20)], lights), pos=(0, 0, 3))

# One representative per UTC offset. Only the chosen home mesh is visible;
# all coordinates rotate with the globe. Offset alone does not identify a city.
homes = sorted(model.HOME_BY_OFFSET.items())
for home_index, (offset, (city_name, latitude, longitude)) in enumerate(homes):
    home_strips = []
    for lat in range(-80, 80, 5):
        home_strips.append([surface(lat, longitude-.22, 3.055), surface(lat, longitude+.22, 3.055),
                            surface(lat+5, longitude+.22, 3.055), surface(lat+5, longitude-.22, 3.055)])
    lon = math.radians(longitude)
    home_strips.append([(r*math.cos(lon+w), r*math.sin(lon+w), .04)
                        for r,w in ((3.0,-.007),(3.75,-.007),(3.75,.007),(3.0,.007))])
    home_strips.append(surface_patch(latitude, longitude, 2.0))
    name = f'Home{home_index:02d}'
    actor(name, 'platform', strip_mesh(name, home_strips, red), pos=(0, 0, 3),
          fields={'Visibility Mailbox': 750+home_index})
actor('HomeLabel', 'platform', label_mesh('HomeLabel', 'HOME (UTC OFFSET ESTIMATE)', ivory), pos=(-4.4, 0, 7.0))

cities = [('Bangkok',13.76,100.50), ('Tokyo',35.68,139.69), ('Singapore',1.35,103.82),
          ('Delhi',28.61,77.21), ('Dubai',25.20,55.27), ('London',51.51,-.13),
          ('Paris',48.86,2.35), ('Lagos',6.52,3.38), ('Cairo',30.04,31.24),
          ('NewYork',40.71,-74.01), ('Chicago',41.88,-87.63), ('LosAngeles',34.05,-118.24),
          ('MexicoCity',19.43,-99.13), ('SaoPaulo',-23.55,-46.63), ('Sydney',-33.87,151.21)]
for index, (name, lat, lon) in enumerate(cities):
    cluster = [surface_patch(lat+dy, lon+dx, size) for dy,dx,size in
               ((0,0,.65), (.7,1.0,.26), (-.8,.6,.25), (.35,-1.1,.28), (-.5,-.9,.22))]
    actor('City'+name, 'platform', strip_mesh('city'+name, cluster, lights),
          pos=(0, 0, 3), fields={'Visibility Mailbox': 700+index})

bpy.context.view_layer.update()
objects = [o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
indices = {o.name: i+1 for i,o in enumerate(objects)}
catalog = json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),
                                               str(OAS/'globesunringsettings.oad')], text=True))
fields = {f['key']: f for f in catalog['fields']}
assert fields['Camera drift']['live'] and fields['City lights']['live']
settings = indices['GlobeSunRingSettings']
lines = [r'\ Globe Sun Ring: civil-time calibrated home meridian.', ': gs-tick']
for i, (offset, (_, latitude, longitude)) in enumerate(homes):
    lower = -2000 if i == 0 else (homes[i-1][0] + offset)//2 + 1
    upper = 2001 if i+1 == len(homes) else (offset + homes[i+1][0])//2 + 1
    lines += [f'  INDEXOF_WALL_UTC_OFFSET read-mailbox {lower} >=',
              f'  INDEXOF_WALL_UTC_OFFSET read-mailbox {upper} < &',
              f'  dup {750+i} write-mailbox',
              f'  if {longitude/360:.10f} 650 write-mailbox then']
lines += [
         '  INDEXOF_WALL_HOUR read-mailbox INDEXOF_WALL_MINUTE read-mailbox 60 / +',
         '  INDEXOF_WALL_SECOND read-mailbox 3600 / + 12 - 24 /',
         '  650 read-mailbox -',
         f'  dup INDEXOF_ROTATION_C {indices["Earth"]} write-actor-mailbox']
for i in range(len(homes)):
    lines.append(f'  dup INDEXOF_ROTATION_C {indices[f"Home{i:02d}"]} write-actor-mailbox')
for index, (name, lat, lon) in enumerate(cities):
    lines += [f'  dup INDEXOF_ROTATION_C {indices["City"+name]} write-actor-mailbox',
              f'  dup {lon/360:.10f} + cos-rev 0 <',
              f'  {settings} {fields["City lights"]["index"]} property@ if 0 <> else drop 1 then &',
              f'  {700+index} write-mailbox']
lines += ['  drop']
# Visibility changes exposed a cached-mesh batching issue in PC captures. A
# zero-amplitude deformation keeps these meshes on the streamed draw path.
for name in ['Earth', 'Ring', 'RingTicks', 'RingNumbers', 'SunSymbol', 'HomeLabel'] + [f'Home{i:02d}' for i in range(len(homes))] + ['City'+name for name, _, _ in cities]:
    lines.append(f'  0 0 {indices[name]} fish-deform')
lines += [
          f'  {settings} {fields["Camera drift"]["index"]} property@ if 0 <> else drop 0 then',
          '  if 0 else INDEXOF_WALL_SECOND read-mailbox 60 / cos-rev .18 * then',
          f'  INDEXOF_X_POS {indices["cs_wide"]} write-actor-mailbox',
          ';\ngs-tick\n']
director['wf_Script'] = '\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices': indices, 'fields': {k: v['index'] for k,v in fields.items()}}, indent=2)+'\n')
bpy.ops.wf.export_level(filepath=str(HERE/'globe_sun_ring.lev'))
