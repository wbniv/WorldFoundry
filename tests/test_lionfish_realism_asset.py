from pathlib import Path
import sys
import math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'wflevels/aquarium_tanks'))
from lionfish_model import geometry, palette_for, write_textures

def test_realism_geometry_and_deformation_metadata():
    m=geometry()
    assert len(m.vertices)==len(m.uvs)==len(m.regions)==len(m.weights)
    assert 3000<=sum(len(f)-2 for f in m.faces)<=6000
    assert {'jaw','head','tail','pectoral_left','pectoral_right','spines','pelvic','anal'}<=set(m.regions)
    assert all(0<=w<=1 for w in m.weights)
    for face in m.faces:
        for i in range(1,len(face)-1):
            a,b,c=(m.vertices[k] for k in (face[0],face[i],face[i+1]))
            u=[b[j]-a[j] for j in range(3)];v=[c[j]-a[j] for j in range(3)]
            area=math.sqrt(sum((u[(j+1)%3]*v[(j+2)%3]-u[(j+2)%3]*v[(j+1)%3])**2 for j in range(3)))
            assert area>1e-10,(face,i)

def test_palettes_are_stable_and_initial_pair_differs():
    for seed in [0,1,999,2**32-1]:
        ids=[palette_for(seed,i) for i in range(20)]
        assert ids==[palette_for(seed,i) for i in range(20)]
        assert ids[0]!=ids[1]
        assert len(set(ids))==3

def test_shared_texture_maps_are_reproducible(tmp_path):
    from PIL import Image
    a,b=tmp_path/'a',tmp_path/'b';write_textures(a);write_textures(b)
    for name in ['lionfish_body.tga','lionfish_fins.tga']:
        assert (a/name).read_bytes()==(b/name).read_bytes()
        image=Image.open(a/name)
        assert image.size==(256,256) and image.mode=='RGBA'
        # Palette is supplied independently; source map is unchanged per fish.
        assert all(r==g==b for r,g,b,_ in (image.get_flattened_data() if hasattr(image,"get_flattened_data") else image.getdata()))
