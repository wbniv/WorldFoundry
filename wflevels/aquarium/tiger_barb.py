"""One-actor tiger-barb assets and the shared 30-fish mailbox allocation.

X points toward the nose, Y through the body, Z up. Length includes tail.
The textured card and real mesh share size, atlas and origin conventions.
"""
import math
from pathlib import Path

LENGTH_M = 0.525  # middle of the 4.5–6 cm range at WORLD_SCALE=10
BODY_VERTEX_COUNT = 58  # seven rings and two cap centres; fins follow
RANGES = {
    'state': (800, 1219), 'params': (1220, 1241), 'scratch': (1242, 1266),
    'director': (1267, 1299), 'actors': (1300, 1328), 'times': (1330, 1358),
    'phases': (1360, 1388),
}
assert all(a[1] < b[0] for a, b in zip(RANGES.values(), list(RANGES.values())[1:]))
assert max(b for a,b in RANGES.values()) < 1901

def length(k):
    return .45 + .15 * (((k-1)*11) % 29) / 28

def body_uv(x,z):
    # Follow the flank centre from peduncle to snout; avoid the fin cutout gaps.
    return .03+.91*(x/LENGTH_M+.5), .51-.06*(x/LENGTH_M+.28)/.78+.45*z/LENGTH_M

def geometry(quad=False):
    """Return metre-space vertices and polygons; fins stay in the same mesh."""
    if quad:
        # Texture silhouette occupies about 94% of its width; retain the texture's
        # aspect and account for that margin in the physical card dimensions.
        w=LENGTH_M/.94; h=w*2/3
        return [(-w/2,0,-h/2),(w/2,0,-h/2),(w/2,0,h/2),(-w/2,0,h/2)], [(0,1,2,3)]
    verts=[]; faces=[]
    # Seven cross-sections, eight vertices each. Nose +0.5, tail -0.5.
    sections=[(-.28,.018,.045),(-.20,.06,.12),(-.08,.10,.17),(.08,.115,.175),(.25,.085,.135),(.39,.045,.085),(.50,.02,.035)]
    for x,ry,rz in sections:
        for j in range(8):
            a=2*math.pi*j/8
            verts.append((x,ry*math.sin(a),rz*math.cos(a)))
    for i in range(len(sections)-1):
        for j in range(8):
            # Outward winding, for every body strip.
            faces.append(((i+1)*8+j,(i+1)*8+(j+1)%8,i*8+(j+1)%8,i*8+j))
    # Explicit fans avoid tiny sliver triangles from automatic ngon tessellation.
    # The engine normalises every polygon, even prelit ones, with a minimum area.
    for ring, reverse in ((0,False),(len(sections)-1,True)):
        centre=len(verts); verts.append((sections[ring][0],0,0))
        for j in range(8):
            tri=(centre,ring*8+j,ring*8+(j+1)%8)
            faces.append(tuple(reversed(tri)) if reverse else tri)
    def fin(points, polygons):
        start=len(verts); verts.extend(points)
        for p in polygons:
            face=tuple(start+j for j in p)
            faces.extend((face,tuple(reversed(face))))
    # Forked tail: two lobes sharing the peduncle; reversed fin faces stay in this mesh.
    fin([(-.28,0,-.035),(-.28,0,.035),(-.50,0,.19),(-.43,0,0),(-.50,0,-.19)],[(0,1,3),(1,2,3),(0,3,4)])
    fin([(-.15,0,.145),(.22,0,.145),(.04,0,.34),(-.18,0,.24)],[(0,1,2,3)])
    fin([(-.19,0,-.105),(.04,0,-.165),(-.12,0,-.27)],[(0,1,2)])
    for side in (-1,1):
        fin([(.24,side*.07,-.05),(.13,side*.085,-.10),(.025,side*.19,-.145)],[(0,1,2)])
    return [(x*LENGTH_M,y*LENGTH_M,z*LENGTH_M) for x,y,z in verts], faces

def blender_mesh(bpy, quad, texture):
    name='tiger_barb_quad' if quad else 'tiger_barb_mesh'
    verts,faces=geometry(quad)
    me=bpy.data.meshes.new(name)
    me.from_pydata(verts,[],faces); me.update()
    mat=bpy.data.materials.new('tiger-barb-textured')
    mat.use_nodes=True
    mat['wf_double_sided']=quad
    mat['wf_alpha_cutout']=True
    mat['wf_prelit']=True  # same texture colours on both faces; no dark reversed card
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(Path(texture).resolve()),check_existing=True)
    mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
    me.materials.append(mat)
    uv=me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for loop in poly.loop_indices:
            x,y,z=me.vertices[me.loops[loop].vertex_index].co
            if quad:
                w=LENGTH_M/.94; h=w*2/3
                u,v=x/w+.5,z/h+.5
            else:
                # Project both flanks into the source profile; dorsal/belly use
                # interior texels at their actual positions rather than stretching
                # the entire side card over every ring. Texture pattern stays shared.
                u=.03+.94*(x/LENGTH_M+.5)
                v=.50+1.30*z/LENGTH_M
                v=max(.04,min(.96,v))
                if me.loops[loop].vertex_index < BODY_VERTEX_COUNT:
                    # Keep the closed body inside opaque flank texels. Only fins
                    # sample the cutout silhouette; the nose cap must stay solid.
                    u,v=body_uv(x,z)
            uv.data[loop].uv=(u,v)
    return me

def forth_constants(count, actors, *, updates=5, animate=True, frozen=False):
    assert 0 <= count <= 29
    assert len(actors)==count
    constants={'sch-base':800,'sch-par':1220,'sch-scr':1242,'sch-n':count+1,
               'sd-flag':1267,'sd-ptr':1268,'sd-blend':1269,'sd-mode':1270,
               'sd-prev':1271,'sd-lhead':1274,'sd-lspeed':1277,'sd-clock':1278,
               'sd-px':1279,'sd-py':1280,'sd-pz':1281,'sd-yaw':1282,'sd-pitch':1283,
               'sd-dart-prev':1284,'sd-act':1300,'sd-times':1330,'sd-phases':1360,
               'sd-budget':updates,'sd-animate':int(animate),'sd-frozen':int(frozen)}
    return '\n'.join(f': {n} {v} ;' for n,v in constants.items())+'\n: sd-actors\n'+''.join(f'  {a} {1300+i} write-mailbox\n' for i,a in enumerate(actors))+';\n'
