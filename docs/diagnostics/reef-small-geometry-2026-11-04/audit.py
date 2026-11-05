import sys,json,collections
import bpy,bmesh
sys.path[:0]=['/src/wflevels/aquarium_thai_reef','/src/wflevels/aquarium_tanks']
from mesh import Mesh
from reef import life,invertebrates,fishes
objects={'static_life':lambda m:life.populate(m),'boxfish':lambda m:None,'featherstar':lambda m:life._feather_star(m,(0,0,0)),'guardcrab':lambda m:invertebrates.guard_crab(m,(0,0,0)),'shrimp':lambda m:invertebrates.banded_shrimp(m,(0,0,0)),'hermitcrab':lambda m:invertebrates.hermit_crab(m,(0,0,0)),'wormcrowns':lambda m:life._worm_crowns(m,(0,0,0)),'seafan':lambda m:life._sea_fan(m,(0,0,0))}
result={}
for name,builder in objects.items():
 m=fishes.boxfish(Mesh) if name=='boxfish' else Mesh(name);builder(m); data=bpy.data.meshes.new(name);data.from_pydata(m.vertices,[],m.faces);data.update();bm=bmesh.new();bm.from_mesh(data);layer=bm.faces.layers.int.new('original_sides')
 for f in bm.faces:f[layer]=len(f.verts)
 bmesh.ops.triangulate(bm,faces=list(bm.faces));counts=collections.defaultdict(lambda:{'removed':0,'survived':0})
 for f in bm.faces:
  sides=f[layer]; category='triangle' if sides==3 else 'quad' if sides==4 else 'ngon'
  counts[category]['removed' if f.calc_area()<.00008 else 'survived']+=1
 result[name]=dict(counts);bm.free()
print('AUDIT_JSON='+json.dumps(result,sort_keys=True))
