"""Opaque, one-material goldfish with fins and eyes in a single deformable mesh."""
import math
from mesh import Mesh
from models import membrane

PALETTE={'gold':(255,151,24),'fin':(255,188,66),'eye':(20,16,12),'glint':(255,246,212)}
BASE=1000
STRIDE=16
SLOTS=3

def geometry():
    m=Mesh('goldfish')
    m.ellipsoid((0,0,0),(.17,.060,.095),'gold',8,5)
    for outline in [[(-.13,.025),(-.30,.10),(-.255,0),(-.30,-.10),(-.13,-.025)],
                    [(-.09,.065),(-.055,.17),(.065,.09)],
                    [(-.045,-.04),(-.09,-.13),(.025,-.055)]]:
        f=membrane('fin',outline,'fin',.012)
        for face,color in zip(f.faces,f.colors):m.face([f.vertices[i] for i in face],color)
    for side in [-1,1]:
        points=[(.07,side*.05,-.025),(.005,side*.11,-.06),(.05,side*.06,-.065)]
        m.face(points,'fin');m.face(list(reversed(points)),'fin')
        eye=[(.105+.020*math.cos(math.tau*j/6),side*.060,.033+.020*math.sin(math.tau*j/6)) for j in range(6)]
        m.face(eye if side<0 else list(reversed(eye)),'eye')
        glint=[(.106,side*.061,.036),(.122,side*.061,.036),(.112,side*.061,.052)]
        m.face(glint if side<0 else list(reversed(glint)),'glint')
    return m

def blender_mesh(bpy, here):
    from PIL import Image
    mesh=geometry();data=bpy.data.meshes.new('goldfish')
    data.from_pydata(mesh.vertices,[],mesh.faces);data.update()
    # Face colours encoded in a tiny opaque palette texture, one material.
    img=Image.new('RGBA',(32,8));keys=list(PALETTE)
    for i,key in enumerate(keys):
        for x in range(i*8,(i+1)*8):
            for y in range(8):img.putpixel((x,y),(*PALETTE[key],255))
    path=here/'goldfish_palette.tga';img.save(path)
    mat=bpy.data.materials.new('goldfish-palette');mat.use_nodes=True;mat['wf_prelit']=True
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(path),check_existing=True)
    mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    data.materials.append(mat);uv=data.uv_layers.new(name='UVMap')
    for poly,key in zip(data.polygons,mesh.colors):
        for loop in poly.loop_indices:uv.data[loop].uv=((keys.index(key)+.5)/4,.5)
    return data

def constants(indices, initial=0, autoeat=True):
    assert 0<=initial<=3
    values={'gf-release':930,'gf-eat':931,'gf-target':932,'gf-count':933,'gf-consumed-player':934,
            'gf-consumed-resident':935,'gf-bite-player':936,'gf-bite-resident':937,
            'gf-i':940,'gf-mouth-x':941,'gf-mouth-y':942,'gf-mouth-z':943,'gf-mouth-yaw':944,
            'gf-mouth-scale':945,'gf-best':946,'gf-best-d':947,'gf-d':948,'gf-want':949,
            'gf-a':950,'gf-b':951,'gf-near':952,'gf-speed':953,'gf-dx':954,'gf-dy':955,'gf-bite':956,
            'gf-spawn-slot':957,'gf-clear':958,'gf-spawn-x':959,
            'gf-owner':960,'gf-elapsed':961,'gf-old':962,'gf-gape':963,
            'gf-see':964,'gf-dot':965,'gf-threat':966,'gf-close':967,'gf-last-d':968,
            'gf-zdelta':969,'gf-ray-clear':970,'gf-sight-range2':30.25,'gf-observe-time':.65,
            'gf-slab-o':971,'gf-slab-d':972,'gf-slab-lo':973,'gf-slab-hi':974,
            'gf-ray-near':975,'gf-ray-far':976,'gf-slab-a':977,'gf-slab-b':978,
            'gf-immediate-range2':.16,'gf-memory-time':.8,'gf-strike-duration':.26,
            'gf-capture-time':.10,
            'gf-rx':1100,'gf-ry':1101,'gf-rz':1102,'gf-ryaw':1103,'gf-rv':1104,
            'gf-rphase':1105,'gf-idle-x':1106,'gf-idle-z':1107,
            'gf-rstate':1108,'gf-rlook':1109,'gf-rpitch':1110,'gf-rroll':1111,'gf-mouth-pitch':979,
            'gf-initial':initial,'gf-autoeat':int(autoeat),'gf-resident':int('animal-01-body' in indices)}
    text=''.join(f': {k} {v} ;\n' for k,v in values.items())
    text+=': gf-actor gf-i read-mailbox 0 = if '+str(indices['goldfish-0'])+' else gf-i read-mailbox 1 = if '+str(indices['goldfish-1'])+' else '+str(indices['goldfish-2'])+' then then ;\n'
    return text
