"""Asset invariants: repeatable topology, closed body surfaces and five-arm rigs."""
import importlib.util
import math
from pathlib import Path
import struct
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'wflevels/aquarium_sea_stars'),str(ROOT/'wflevels/aquarium_tanks'),str(ROOT/'wftools/wf_blender')]
import stars
from config import SPECIES,STATIC_TRIANGLES_MAX,STATIC_GROUPS_MAX
from mesh import Mesh
import dfrm_chunk

@pytest.mark.parametrize('kind',SPECIES)
def test_finite_deterministic_species_geometry(kind):
    a=stars.mesh(Mesh,kind);b=stars.mesh(Mesh,kind)
    assert (a.vertices,a.faces,a.colors)==(b.vertices,b.faces,b.colors)
    assert all(math.isfinite(v) for p in a.vertices for v in p)
    assert all(3<=len(f)<=8 for f in a.faces)
    # Ignore separately modelled knobs, eyes, plates and spines; the animal's
    # dorsal/ventral body must have closed render surfaces with no boundary edges.
    edges={}
    for face,color in zip(a.faces,a.colors):
        if color not in (kind,'underside') and not (kind=='brittle' and color.startswith(('brittle_disc','brittle_arm'))):continue
        points=[tuple(round(v,6) for v in a.vertices[i]) for i in face]
        for p,q in zip(points,points[1:]+points[:1]):
            assert p!=q
            edge=tuple(sorted((p,q)));edges[edge]=edges.get(edge,0)+1
    assert set(edges.values())=={2}
    assert max(math.hypot(p[0],p[1]) for p in a.vertices)<=SPECIES[kind]['radius']+.04

@pytest.mark.parametrize('kind',SPECIES)
def test_exported_rig_matches_species(kind):
    path=ROOT/'wflevels/aquarium_sea_stars'/('star_'+kind+'.iff')
    data=path.read_bytes();off=8;chunks={}
    while off<len(data):
        tag,size=struct.unpack_from('<4sI',data,off);chunks[tag]=data[off+8:off+8+size];off+=8+((size+3)&~3)
    assert off==len(data)
    if kind=='cushion':assert b'DFRM' not in chunks;return
    rig=dfrm_chunk.decode(chunks[b'DFRM'])
    assert rig['clips'][0]['loop']
    count=16 if kind=='brittle' else 4
    assert all(frame[3*count*arm:3*count*arm+3]==[0,0,0] for frame in rig['frames'] for arm in range(5))
    assert len(rig['curves'])==5
    assert all(c['count']==count for c in rig['curves'])
    assert len(rig['influences'])==len(chunks[b'VRTX'])//24
    assert {b[1]//count for b in rig['influences'] if b[0]==dfrm_chunk.ON_SAMPLE}==set(range(5))

def test_static_and_animal_budget():
    import json
    data=json.loads((ROOT/'wflevels/aquarium_sea_stars/actor-map.json').read_text())
    assert len(data['static_triangles'])<=STATIC_GROUPS_MAX
    assert sum(data['static_triangles'].values())<=STATIC_TRIANGLES_MAX
    # The level holds the maximum population (the player and 17 residents); the director parks
    # the extras, so the default tank shows the player and 9 residents (10 animated actors).
    from config import RESIDENTS, DEFAULT_COUNTS
    assert len(data['animated_triangles'])==1+len(RESIDENTS)==18
    assert 1+sum(DEFAULT_COUNTS.values())==10

def test_texture_is_512_square_and_has_no_transparent_texels():
    data=(ROOT/'wflevels/aquarium_sea_stars/stars_atlas.tga').read_bytes()
    assert struct.unpack_from('<HHBB',data,12)==(512,512,24,32)
    assert len(data)==18+512*512*3

def _brittle_rig():
    import dfrm_ref
    data=(ROOT/'wflevels/aquarium_sea_stars/star_brittle.iff').read_bytes()
    off=8;chunks={}
    while off<len(data):
        tag,size=struct.unpack_from('<4sI',data,off);chunks[tag]=data[off+8:off+8+size];off+=8+((size+3)&~3)
    vertices=[tuple(v/65536 for v in struct.unpack_from('<iii',chunks[b'VRTX'],i+12)) for i in range(0,len(chunks[b'VRTX']),24)]
    faces=[struct.unpack_from('<hhh',chunks[b'FACE'],i) for i in range(0,len(chunks[b'FACE']),8)]
    return dfrm_ref.Rig(dfrm_chunk.decode(chunks[b'DFRM']),vertices,faces)

def test_brittle_rest_pose_has_long_arms_and_curled_tips():
    import dfrm_ref
    rig=_brittle_rig();block=[0.]*60
    for arm in range(5):block[40+4*arm]=1;block[41+4*arm]=1
    pose=dfrm_ref.evaluate(rig,block,0,chain_only=True)
    assert pose['status']==0
    for arm in range(5):
        points=pose['joints'][arm*17:(arm+1)*17]
        length=sum(math.dist(a,b) for a,b in zip(points,points[1:]))
        assert 1.49<length<1.53  # about 15 cm, versus a 3.8 cm disc
        assert length/(2*SPECIES['brittle']['disc'])>3.8
        # Curvature is genuinely present in the exported runtime pose.
        assert math.dist(points[0],points[-1])<length*.92
        radial=(math.cos(arm*math.tau/5),math.sin(arm*math.tau/5))
        assert max(abs(p[0]*radial[1]-p[1]*radial[0]) for p in points)>.12
        last=[points[-1][i]-points[-2][i] for i in range(3)]
        assert last[0]*radial[0]+last[1]*radial[1]<0  # hooked tip turns back

def test_brittle_rowing_moves_distal_joints_without_straightening_every_arm():
    import dfrm_ref
    rig=_brittle_rig();block=[0.]*60
    for arm in range(5):block[40+4*arm]=1;block[41+4*arm]=2
    before=dfrm_ref.evaluate(rig,block,0,chain_only=True)
    after=dfrm_ref.evaluate(rig,block,.4,chain_only=True)
    assert max(math.dist(a,b) for a,b in zip(before['joints'],after['joints']))>.05
    assert sum(abs(v)>8 for v in after['angles'][1])>25
