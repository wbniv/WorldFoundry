#!/usr/bin/env python3
"""Check palette invariance and source mesh integrity."""
import json, math
from pathlib import Path
from PIL import Image
from build import make_mesh, slug
p=Path(__file__).resolve().parent
master=Image.open(p/'master-index.png'); indices=master.tobytes()
manifest=json.loads((p/'palettes.json').read_text())
assert len(manifest)==12 and master.size==(256,256)
for name,colors in manifest.items():
 im=Image.open(p/(slug(name)+'.png'))
 assert im.mode=='P' and im.size==master.size and im.tobytes()==indices, name
 assert im.getpalette()[:24]==[int(c[i:i+2],16) for c in colors for i in (1,3,5)], name
m=make_mesh()
for face in m.faces:
 assert len(set(face))==len(face)
 a,b,c=(m.vertices[i] for i in face[:3])
 u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
 cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
 assert math.sqrt(sum(x*x for x in cross))>1e-9,face
assert all(0<=u<=1 and 0<=v<=1 for u,v in m.uvs)
print('12 palette mappings, UV bounds and nondegenerate mesh faces: OK')
