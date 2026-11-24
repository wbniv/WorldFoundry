"""Generate the Corolla Gauge botanical clock with a genuinely hinged petal."""
import json,math,subprocess,sys
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
sys.path[:0]=[str(ROOT/'wftools'),str(ROOT/'wflevels/clock_common')]
import wf_blender,wf_core
from wf_blender.export_level import _seed_defaults
from clock_mesh import Mesh
OAS=ROOT/'wfsource/source/oas'
bpy.ops.wm.read_factory_settings(use_empty=True);wf_blender.register()
COLORS={'bench':(.30,.18,.11),'benchlight':(.47,.29,.16),'pot':(.57,.25,.12),'potedge':(.76,.40,.20),
        'soil':(.11,.071,.045),'green':(.20,.42,.12),'leaf':(.30,.50,.15),'leaflight':(.45,.59,.20),
        'ivory':(.9,.83,.68),'rose':(.67,.13,.21),'brass':(.76,.55,.23),'lightbrass':(.95,.77,.40),
        'dark':(.055,.042,.045),'pollen':(.62,.35,.10),'anther':(.45,.29,.12),'pistil':(.4,.6,.15),'rose_fold':(.5,.1,.1),'ivory_fold':(.7,.6,.5),'label':(.77,.68,.46)}
materials={}
for key,rgb in COLORS.items():
    mat=bpy.data.materials.new(key);mat.use_nodes=True;mat.diffuse_color=(*rgb,1)
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*rgb,1)
    mat['wf_prelit']=True;mat['wf_double_sided']=True;materials[key]=mat
for key in ('ivory','rose','ivory_fold','rose_fold','leaf','pot','bench','brass','anther','pistil'):
    mat=materials[key];mat.diffuse_color=(1,1,1,1);tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
    filename={'ivory':'petal-ivory-index.png','rose':'petal-rose-index.png','ivory_fold':'petal-ivory-fold-index.png','rose_fold':'petal-rose-fold-index.png','leaf':'generated-leaf-source.png','pot':'terracotta-natural-source.png','bench':'bench-source.png','brass':'protractor-brass-source.png','anther':'anther-pollen-source.png','pistil':'pistil-veined-source.png'}[key]
    tex.image=bpy.data.images.load(str(HERE/filename));_ = len(tex.image.pixels)
    if key in ('ivory','rose','ivory_fold','rose_fold'):
        mat['wf_indexed_palette']=True  # PNG stores exact RGB555-encoded indices.
    else:
        size=1024 if key=='pot' else 256
        tex.image.scale(size,size)
        tex.image.filepath_raw=str(HERE/(key+'-texture.tga'));tex.image.file_format='TARGA';tex.image.save()
    mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])

def actor(name,cls,mesh=None,pos=(0,0,0),fields=None,bounds=None):
    data=None
    if mesh:
        data=bpy.data.meshes.new(name);data.from_pydata(mesh.vertices,[],mesh.faces);keys=list(dict.fromkeys(mesh.colors))
        for k in keys:data.materials.append(materials[k])
        for poly,k in zip(data.polygons,mesh.colors):poly.material_index=keys.index(k)
        data.update()
        if any(k in keys for k in ('ivory','rose','ivory_fold','rose_fold','leaf','pot','bench','brass','anther','pistil')):
            uv=data.uv_layers.new(name='UVMap')
            for poly in data.polygons:
                pot_angles=[(math.atan2(data.vertices[data.loops[l].vertex_index].co.x,data.vertices[data.loops[l].vertex_index].co.y)/math.tau)%1 for l in poly.loop_indices] if name=='PotAndStem' and keys[poly.material_index]=='pot' else []
                wrap=bool(pot_angles) and max(pot_angles)-min(pot_angles)>.5
                for loop in poly.loop_indices:
                    p=data.vertices[data.loops[loop].vertex_index].co
                    if name=='Leaves': uv.data[loop].uv=mesh.leaf_uv[data.loops[loop].vertex_index]
                    elif keys[poly.material_index] in ('ivory','rose','ivory_fold','rose_fold'): uv.data[loop].uv=mesh.petal_uv[data.loops[loop].vertex_index]
                    elif keys[poly.material_index]=='anther': uv.data[loop].uv=mesh.anther_uv[data.loops[loop].vertex_index]
                    elif keys[poly.material_index]=='pistil':
                        v=(p.z-1.4)/1.85 if name=='PotAndStem' else p.z/1.75
                        uv.data[loop].uv=((math.atan2(p.x,p.y)/math.tau)%1,max(0,min(1,v)))
                    elif name=='Protractor': uv.data[loop].uv=(p.x/3.0,p.z/3.0)
                    elif name=='Bench': uv.data[loop].uv=((p.x+7)/14,(p.y+4)/8)
                    elif pot_angles:
                        u=(math.atan2(p.x,p.y)/math.tau)%1
                        uv.data[loop].uv=(u+1 if wrap and u<.5 else u,max(0,min(1,p.z/1.4)))
                    else: uv.data[loop].uv=(max(0,min(1,(p.x+1.1)/2.2)),max(0,min(1,p.z/2.4)))
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);obj.location=pos
    schema=OAS/(cls+'.oad');obj['wf_schema_path']=str(schema);_seed_defaults(obj,wf_core.load_schema(str(schema)))
    values={'Mobility':'Anchored','Mass':0.,'Model Type':'Mesh' if data else 'None','Visibility Mailbox':1 if data else 0,
            'Script':'','Script Controls Input':'False','Moves Between Rooms':'False','Number Of Local Mailboxes':0}
    values.update(fields or {})
    for k,v in values.items():obj['wf_'+k]=v
    if data:obj['wf_Mesh Name']=name+'.iff';obj['wf_original_mesh_name']=name+'.iff'
    if bounds or not data:obj['wf_original_bbox']=tuple(bounds or (-.05,-.05,-.05,.05,.05,.05));obj['wf_had_authored_bbox']=True
    return obj

def frustum(m,z0,z1,r0,r1,color,n=36):
    for i in range(n):
        a,b=math.tau*i/n,math.tau*(i+1)/n
        m.face([(r*math.sin(t),r*math.cos(t),z) for r,t,z in ((r0,a,z0),(r0,b,z0),(r1,b,z1),(r1,a,z1))],color)

def stamen(m,x_end,height,depth):
    """A tapered curved filament rooted at the ovary, with a rounded anther."""
    def center(t):
        return (x_end*(.14+.86*t*t),-.43+depth*t,.08+height*t)
    sides=16;steps=12
    def ring(t,r):
        x,y,z=center(t)
        return [(x+r*math.cos(math.tau*j/sides),y+r*math.sin(math.tau*j/sides),z) for j in range(sides)]
    for i in range(steps):
        t=i/steps;lo=ring(t,.034-.012*t);hi=ring((i+1)/steps,.034-.012*(i+1)/steps)
        for j in range(sides):m.face([lo[j],lo[(j+1)%sides],hi[(j+1)%sides],hi[j]],'pollen')
    # Oval anther with softly rounded ends, seated directly on the filament.
    x,y,z=center(1);rings=12
    def anther_ring(t):
        a=math.pi*t;radius=.069*math.sin(a)
        return [(x+radius*math.cos(math.tau*j/sides),y+radius*math.sin(math.tau*j/sides),z+.16-.16*math.cos(a)) for j in range(sides)]
    if not hasattr(m,'anther_uv'):m.anther_uv={}
    for i in range(rings):
        lo=anther_ring(i/rings);hi=anther_ring((i+1)/rings)
        for j in range(sides):
            points=list(dict.fromkeys(tuple(round(v,8) for v in p) for p in (lo[j],lo[(j+1)%sides],hi[(j+1)%sides],hi[j])))
            if len(points)>=3:
                start=len(m.vertices);m.face(points,'anther')
                # Each small face samples the pollen surface independently.
                for k,p in enumerate(points):
                    m.anther_uv[start+k]=((math.atan2(p[1]-y,p[0]-x)/math.tau)%1,(p[2]-z)/.32)

def petal(m,azimuth,tilt,color,origin=(0,0,0),length=2.35):
    """Tapered, concave double-sided curved petal; its tip lies on its local z axis."""
    n=40;cols=32
    def point(i,j):
        t=i/n;u=2*j/cols-1;w=(.08+.70*math.sin(math.pi*t)**.8)*(1-.2*t)
        # Cylindrical curl across the petal and shallow lengthwise flex.
        # Roll the margins back and flare the tip, while leaving the centre
        # of the measuring petal's tip on the calibrated gauge radius.
        edge_wave=.12*math.sin(3*math.pi*t)*math.sin(math.pi*t)*abs(u)**4
        x=u*(w+.14*t**5+edge_wave); y=.12*math.sin(math.pi*t)-.24*abs(u)**2*math.sin(math.pi*t)**.7-.07*abs(u)*t**4
        z=length*t-.20*u*u*math.sin(math.pi*t)+.09*u*u*math.sin(3*math.pi*t)*math.sin(math.pi*t)
        x,z=x*math.cos(tilt)+z*math.sin(tilt),z*math.cos(tilt)-x*math.sin(tilt)
        return (origin[0]+x*math.cos(azimuth)-y*math.sin(azimuth),origin[1]+x*math.sin(azimuth)+y*math.cos(azimuth),origin[2]+z)
    if not hasattr(m,'petal_uv'):m.petal_uv={}
    for i in range(n):
        for j in range(cols):
            start=len(m.vertices)
            m.face([point(i,j),point(i,j+1),point(i+1,j+1),point(i+1,j)],color)
            for k,uv in enumerate(((j/cols,1-i/n),((j+1)/cols,1-i/n),((j+1)/cols,1-(i+1)/n),(j/cols,1-(i+1)/n))):
                m.petal_uv[start+k]=uv
    # Fold each margin back on itself as a real curved lip, rather than
    # relying on the shallow bend of the main petal surface.
    for side,j in ((-1,0),(1,cols)):
        def lip(i,k):
            a=math.pi*k/8
            taper=math.sin(math.pi*(i-5)/(n-8))**.7
            inset=4.5*taper*(1-math.cos(a))/2
            x,y,z=point(i,j-side*inset)
            dy=-taper*(.035+.12*math.sin(a)+.02*(1-math.cos(a)))
            return (x-dy*math.sin(azimuth),y+dy*math.cos(azimuth),z)
        for i in range(5,n-3):
            for k in range(8):
                start=len(m.vertices);m.face([lip(i,k),lip(i+1,k),lip(i+1,k+1),lip(i,k+1)],color+'_fold')
                u0=(.02+.10*k/8) if side<0 else (.98-.10*k/8)
                u1=(.02+.10*(k+1)/8) if side<0 else (.98-.10*(k+1)/8)
                for q,uv in enumerate(((u0,1-i/n),(u0,1-(i+1)/n),(u1,1-(i+1)/n),(u1,1-i/n))):m.petal_uv[start+q]=uv

def leaf(m,side):
    """A curved lance-shaped leaf with a raised, light midrib."""
    def pt(i,j):
        t=i/32;u=j/8-1;width=(.025+.30*math.sin(math.pi*t))
        wave=.12*math.sin(3*math.pi*t)*abs(u)**1.6*math.sin(math.pi*t)
        return (side*(.06+1.78*t),-.20-.20*math.sin(math.pi*t)+.20*u*u*math.sin(math.pi*t),
                1.45+1.22*math.sin(math.pi*t/2)+u*width+wave)
    if not hasattr(m,'leaf_uv'):m.leaf_uv={}
    for i in range(32):
        for j in range(16):
            start=len(m.vertices)
            m.face([pt(i,j),pt(i+1,j),pt(i+1,j+1),pt(i,j+1)],'leaf')
            for k,uv in enumerate(((j/16,i/32),(j/16,(i+1)/32),((j+1)/16,(i+1)/32),((j+1)/16,i/32))):m.leaf_uv[start+k]=uv

def digit(m,d,x,y,z,size,color='dark'):
    # Seven-segment numerals, placed on the front of the specimen label.
    seg=((0,.66,.38,.71),(.34,.36,.40,.69),(.34,.02,.40,.35),(0,0,.38,.05),(-.02,.02,.04,.35),(-.02,.36,.04,.69),(0,.33,.38,.38))
    mask=('abcdef','bc','abged','abgcd','fgbc','afgcd','afgecd','abc','abcdefg','abfgcd')[d]
    for k,(x0,z0,x1,z1) in zip('abcdefg',seg):
        if k in mask:m.quad_y(x+x0*size,z+z0*size,x+x1*size,z+z1*size,y,color)

actor('Level','levelobj');actor('Room','room',bounds=(-50,-50,-25,50,50,40))
director=actor('Director','director');actor('Player','player',pos=(0,15,0))
actor('Camera','camera',pos=(0,-7,4.8),fields={'Mobility':'Camera','Moves Between Rooms':'True','FoggingStartDistance':900.,'FoggingCompleteDistance':1000.})
actor('LookAt','target',pos=(.3,0,3.05))
actor('cs_wide','camshot',pos=(0,-7,4.8),fields={'Follow':'LookAt','Target':'LookAt','Track Object':'LookAt','Rotation':'Fixed','Position X':'Absolute','Position Y':'Absolute','Position Z':'Absolute','Hither':1.,'Yon':200.,'FOV':42.,'Pan Time In Seconds':0.})
actor('Ambient','light',fields={'lightType':'Ambient','lightRed':.65,'lightGreen':.65,'lightBlue':.65})
actor('Background','matte',fields={'Matte Type':'Color','Background Color':0x151e19})
actor('CorollaGaugeSettings','corollagaugesettings',fields={'Editor Label':'Corolla Gauge'})

bench=Mesh('bench');bench.box((-7,-4,-.38),(7,4,-.14),'bench')
for i in range(-5,6):bench.box((i*1.1,-4,-.14),(i*1.1+.035,4,-.12),'benchlight')
actor('Bench','platform',bench)
pot=Mesh('pot');frustum(pot,0,1.25,.77,1.05,'pot');pot.column_z(0,0,1.20,1.38,1.12,'pot',sides=36)
pot.column_z(0,0,1.38,1.40,.98,'soil',sides=36);pot.column_z(0,0,1.4,3.25,.14,'pistil',sides=18)
# Brass-edged plate on the front of the pot.
pot.box((-.59,-1.03,.38),(.59,-.99,.91),'brass');pot.box((-.53,-1.065,.43),(.53,-1.035,.86),'label')
for x in (-.46,.46):pot.sphere((x,-1.08,.64),.045,'brass',segments=8,rings=4)
# Long tapered pointed green leaves curving away from the stem.
actor('PotAndStem','platform',pot)
leaves=Mesh('leaves')
for side in (-1,1):leaf(leaves,side)
actor('Leaves','platform',leaves)

flower=Mesh('flower')
# Behind the cutaway, five broad curved petals surround the style.
for a in (math.radians(0),math.radians(45),math.radians(90),math.radians(135),math.radians(180)):
    petal(flower,a,.48,'rose',origin=(0,0,0))
actor('Flower','platform',flower,pos=(0,.50,3.25))
for i,(x,height,depth) in enumerate(((-.73,.99,-.04),(-.39,1.19,-.01),(.62,1.10,-.07))):
    filament=Mesh('stamen');stamen(filament,x,height,depth)
    actor(f'Stamen{i+1}','platform',filament,pos=(0,0,3.25))
pistil=Mesh('pistil');pistil.column_z(0,0,0,1.57,.105,'pistil',sides=32)
for i in range(3):
    a=math.tau*i/3;pistil.sphere((.09*math.sin(a),.09*math.cos(a),1.60),.115,'pistil',segments=24,rings=12)
actor('Pistil','platform',pistil,pos=(0,-.50,3.25))
outer=Mesh('outer');petal(outer,0,0,'ivory');actor('MinutePetal','platform',outer,pos=(0,-.32,3.25))

# A broad, thick engraved brass arc centered on the pale petal hinge. The
# inner edge follows the tip, while the etched marks sit on the brass face.
gauge=Mesh('gauge');radius=2.38
for i in range(60):
    a,b=math.radians(i),math.radians(i+1)
    for y in (-.48,-.38):
        gauge.face([(r*math.sin(t),y,r*math.cos(t)) for r,t in ((radius,a),(radius+.46,a),(radius+.46,b),(radius,b))],'brass')
    for r in (radius,radius+.46):
        gauge.face([(r*math.sin(t),y,r*math.cos(t)) for t,y in ((a,-.48),(b,-.48),(b,-.38),(a,-.38))],'brass')
    for r0,r1 in ((radius,radius+.025),(radius+.435,radius+.46)):
        gauge.face([(r*math.sin(t),-.49,r*math.cos(t)) for r,t in ((r0,a),(r1,a),(r1,b),(r0,b))],'lightbrass')
for i in range(61):
    a=math.radians(i);r0=radius+.04;r1=radius+(.22 if i%5==0 else .13)
    gauge.beam((r0*math.sin(a),r0*math.cos(a)),(r1*math.sin(a),r1*math.cos(a)),.012 if i%5 else .022,-.52,-.50,'dark')
for i in range(0,61,10):
    a=math.radians(i);r=radius+.32;x,z=r*math.sin(a),r*math.cos(a)
    if i<10:digit(gauge,i,x-.04,-.54,z-.05,.14,'dark')
    else:digit(gauge,i//10,x-.075,-.54,z-.05,.14,'dark');digit(gauge,i%10,x,-.54,z-.05,.14,'dark')
for i in (0,60):
    a=math.radians(i);r=radius+.35
    gauge.sphere((r*math.sin(a),-.53,r*math.cos(a)),.045,'lightbrass',segments=10,rings=6)
# The bow is a solid curved support, not part of the graduated scale. It
# connects the petal hinge to the outer end of the protractor plate.
end=((radius+.22)*math.sin(math.pi/3),(radius+.22)*math.cos(math.pi/3))
def bow(t):
    u=1-t
    return (3*u*u*t*.85+3*u*t*t*2.05+t*t*t*end[0],
            3*u*u*t*(-.12)+3*u*t*t*.37+t*t*t*end[1])
for i in range(24):gauge.beam(bow(i/24),bow((i+1)/24),.095,-.47,-.39,'brass')
gauge.beam((0,.05),(0,radius+.01),.045,-.46,-.40,'lightbrass')
gauge.cylinder_y(0,0,.18,-.58,-.36,'brass',sides=20)
gauge.cylinder_y(0,0,.09,-.60,-.58,'lightbrass',sides=16)
actor('Protractor','platform',gauge,pos=(0,-.32,3.25))

# The slender radial arm turns with the petal and ends at the actual scale.
pointer=Mesh('pointer');pointer.beam((0,.08),(0,radius+.01),.038,-.59,-.55,'lightbrass')
pointer.cylinder_y(0,0,.065,-.61,-.59,'dark',sides=12)
actor('GaugePointer','platform',pointer,pos=(0,-.32,3.25))

for place,x in ((0,-.34),(1,.04)):
    for d in range(10):
        label=Mesh('digit');digit(label,d,x,-1.085,.49,.43)
        actor(f'Hour{place}Digit{d}','platform',label,fields={'Visibility Mailbox':900+place*10+d})

bpy.context.view_layer.update();objects=[o for o in bpy.context.scene.objects if o.get('wf_schema_path')]
idx={o.name:i+1 for i,o in enumerate(objects)}
catalog=json.loads(subprocess.check_output([str(ROOT/'wftools/wf_attr_edit/target/release/catalog'),str(OAS/'corollagaugesettings.oad')],text=True))
drift=next(f['index'] for f in catalog['fields'] if f['key']=='Camera drift')
lines=[r'\ Corolla Gauge: one degree per minute, local 24-hour pot label.',
 ': cg-sub INDEXOF_WALL_SECOND read-mailbox 701 read-mailbox <> if INDEXOF_WALL_SECOND read-mailbox 701 write-mailbox 0 700 write-mailbox else 700 read-mailbox INDEXOF_DELTA_TIME read-mailbox 0 max .1 min + .98 min 700 write-mailbox then ;',
 ': cg-angle INDEXOF_WALL_MINUTE read-mailbox INDEXOF_WALL_SECOND read-mailbox 700 read-mailbox + 60 / + 360 / ;',
 ': cg-arrival INDEXOF_WALL_MINUTE read-mailbox 0 = INDEXOF_WALL_SECOND read-mailbox 3 < & if 1 INDEXOF_WALL_SECOND read-mailbox 700 read-mailbox + 3 / - 0 max 1.3 * else 0 then ;',
 ': cg-tick cg-sub',f' cg-angle INDEXOF_ROTATION_B {idx["MinutePetal"]} write-actor-mailbox',
 f' cg-angle INDEXOF_ROTATION_B {idx["GaugePointer"]} write-actor-mailbox']
for d in range(10):
    lines.append(f' INDEXOF_WALL_HOUR read-mailbox {d*10} >= INDEXOF_WALL_HOUR read-mailbox {(d+1)*10} < & {900+d} write-mailbox')
    lines.append(f' INDEXOF_WALL_HOUR read-mailbox 10 mod {d} = {910+d} write-mailbox')
for name in ['PotAndStem','Leaves','Flower','Pistil','MinutePetal','Protractor','GaugePointer','Stamen1','Stamen2','Stamen3']+[f'Hour{p}Digit{d}' for p in range(2) for d in range(10)]:
    lines.append(f' cg-arrival INDEXOF_X_POS {idx[name]} write-actor-mailbox')
    lines.append(f' 0 0 {idx[name]} fish-deform')
for i in range(3):
    lines.append(f' cg-arrival INDEXOF_TIME read-mailbox {19+i*4} / {i/3:.6f} + sin-rev .055 * + INDEXOF_X_POS {idx[f"Stamen{i+1}"]} write-actor-mailbox')
    lines.append(f' INDEXOF_TIME read-mailbox {23+i*5} / {i/3:.6f} + sin-rev .006 * INDEXOF_ROTATION_B {idx[f"Stamen{i+1}"]} write-actor-mailbox')
lines += [f' {idx["CorollaGaugeSettings"]} {drift} property@ if 0 <> else drop 0 then if 0 else INDEXOF_TIME read-mailbox 90 / sin-rev 1.65 * then INDEXOF_X_POS {idx["cs_wide"]} write-actor-mailbox',
          f' {idx["CorollaGaugeSettings"]} {drift} property@ if 0 <> else drop 0 then if 4.8 else 4.8 INDEXOF_TIME read-mailbox 140 / sin-rev .3 * + then INDEXOF_Z_POS {idx["cs_wide"]} write-actor-mailbox',
          ';','cg-tick']
director['wf_Script']='\n'.join(lines)
(HERE/'actor-map.json').write_text(json.dumps({'indices':idx},indent=2)+'\n')
bpy.ops.wm.save_as_mainfile(filepath=str(HERE/'corolla_gauge.blend'))
bpy.ops.wf.export_level(filepath=str(HERE/'corolla_gauge.lev'))
